"""Safe-mode autonomous response agent: linear Thompson-sampling bandit whose
actions are first vetted in the what-if sandbox before touching the twin."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from nettwin.config import Settings
from nettwin.simulator.engine import SimulationEngine
from nettwin.twin.whatif import _network_health

ACTION_KINDS = ["rate_limit", "block_flow", "reroute", "isolate"]
PROTECTED_KINDS = {"core_router", "internet_gateway", "firewall",
                   "distribution_switch"}
ISOLATABLE_KINDS = {"workstation", "iot"}
CTX_DIM = 8


class LinearThompsonBandit:
    """Per-action ridge-linear Thompson sampling."""

    def __init__(self, dim: int, noise: float = 0.4) -> None:
        self.dim = dim
        self.noise = noise
        self.A = {k: np.eye(dim) for k in ACTION_KINDS}
        self.b = {k: np.zeros(dim) for k in ACTION_KINDS}
        self.rng = np.random.default_rng(3)

    def score(self, kind: str, ctx: np.ndarray) -> float:
        A_inv = np.linalg.inv(self.A[kind])
        theta_hat = A_inv @ self.b[kind]
        cov = self.noise ** 2 * A_inv
        theta = self.rng.multivariate_normal(theta_hat, cov)
        return float(theta @ ctx)

    def update(self, kind: str, ctx: np.ndarray, reward: float) -> None:
        self.A[kind] += np.outer(ctx, ctx)
        self.b[kind] += reward * ctx

    def to_dict(self) -> dict[str, Any]:
        return {"dim": self.dim, "noise": self.noise,
                "A": {k: m.tolist() for k, m in self.A.items()},
                "b": {k: v.tolist() for k, v in self.b.items()}}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LinearThompsonBandit":
        bandit = cls(int(data["dim"]), float(data["noise"]))
        for k in ACTION_KINDS:
            if k in data.get("A", {}):
                bandit.A[k] = np.array(data["A"][k])
                bandit.b[k] = np.array(data["b"][k])
        return bandit


def context_vector(alert: dict[str, Any], score: float) -> np.ndarray:
    atype = alert.get("alert_type", "")
    sev = 1.0 if alert.get("severity") == "critical" else 0.5
    is_node = 1.0 if alert.get("entity_kind") == "node" else 0.0
    return np.array([
        1.0, sev, is_node, score,
        1.0 if "throughput" in atype or "utilization" in atype else 0.0,
        1.0 if "pps" in atype or "fanout" in atype else 0.0,
        1.0 if "packet_loss" in atype else 0.0,
        1.0 if "bytes_ratio" in atype else 0.0,
    ])


class ResponseAgent:
    def __init__(self, settings: Settings, engine: SimulationEngine,
                 bandit_class: type | None = None) -> None:
        self.s = settings
        self.engine = engine
        self.mode = settings.response.mode
        self._bandit_class = bandit_class or LinearThompsonBandit
        self.bandit = self._bandit_class(CTX_DIM, settings.response.bandit_noise)
        self.actions: dict[str, dict[str, Any]] = {}
        self.history: list[dict[str, Any]] = []
        self._seq = 0
        self._pending_rewards: list[dict[str, Any]] = []
        self._load_state()
        self.on_apply_aws: Any = None

    # ---- persistence ---------------------------------------------------------
    def _load_state(self) -> None:
        path = Path(self.s.response.bandit_state_path)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                # Use the configured bandit class for deserialization.
                loader = getattr(self._bandit_class, "from_dict", None)
                if loader is not None:
                    self.bandit = loader(data)
            except Exception:
                pass

    def save_state(self) -> None:
        try:
            serializer = getattr(self.bandit, "to_dict", None)
            if serializer is not None:
                Path(self.s.response.bandit_state_path).write_text(
                    json.dumps(serializer()))
        except Exception:
            pass

    # ---- constraints ------------------------------------------------------------
    def constraint_check(self, kind: str, params: dict[str, Any]) -> str | None:
        topo = self.engine.topology
        if kind == "isolate":
            node = params.get("node", "")
            if node not in topo.nodes:
                return "unknown node"
            if topo.nodes[node].kind in PROTECTED_KINDS:
                return f"refused: cannot isolate protected {topo.nodes[node].kind}"
            if topo.nodes[node].kind not in ISOLATABLE_KINDS:
                return "refused: isolate only applies to workstations/iot"
        if kind == "reroute":
            link = topo.links.get(params.get("link", ""))
            if not link:
                return "unknown link"
            for ep in (link.src, link.dst):
                if topo.nodes[ep].kind == "internet_gateway":
                    return "refused: cannot reroute the internet uplink"
        if kind in ("block_flow", "rate_limit"):
            src = params.get("src", "")
            if src and src in topo.nodes and topo.nodes[src].kind in PROTECTED_KINDS:
                return "refused: cannot throttle protected infrastructure"
            for ep in (src, params.get("dst")):
                if ep and ep not in topo.nodes:
                    return f"refused: {ep} is not a node"
        return None

    # ---- sandbox evaluation -------------------------------------------------
    def sandbox_evaluate(self, kind: str, params: dict[str, Any],
                         horizon: int | None = None) -> dict[str, Any]:
        h = horizon or self.s.response.eval_horizon

        def roll(with_action: bool) -> float:
            eng = self.engine.clone()
            if with_action:
                eng.apply_policy(kind, **params)
            healths = [_network_health(eng.step()) for _ in range(h)]
            return sum(healths) / len(healths)

        base = roll(False)
        acted = roll(True)
        return {"baseline_health": round(base, 2), "action_health": round(acted, 2),
                "predicted_delta": round(acted - base, 2),
                "improves": acted > base + self.s.response.min_improvement}

    # ---- proposals -----------------------------------------------------------
    def propose(self, alerts: list[Any], scores: dict[str, float]) -> list[dict[str, Any]]:
        proposals: list[dict[str, Any]] = []
        attack_targets = {a.event.attack_type: a.event.target_id
                          for a in self.engine.attacks.values()}
        for alert in alerts[:6]:
            if alert.status != "active":
                continue
            entity = alert.entity_id
            cands: list[tuple[str, dict[str, Any]]] = []
            atype = alert.alert_type
            tgt = next(iter(attack_targets.values()), None)
            if "ddos" in attack_targets or "throughput" in atype or "utilization" in atype:
                cands.append(("block_flow", {"src": "attacker", "dst": tgt or entity,
                                             "proto": None}))
                cands.append(("rate_limit", {"src": "attacker", "dst": None,
                                             "bps": 5e7}))
            if "portscan" in attack_targets or "bruteforce" in attack_targets or "fanout" in atype:
                cands.append(("block_flow", {"src": "attacker", "dst": None,
                                             "proto": None}))
            if "exfiltration" in attack_targets or "bytes_ratio" in atype:
                src = tgt if "exfiltration" in attack_targets else entity
                cands.append(("block_flow", {"src": src, "dst": "attacker",
                                             "proto": None}))
                cands.append(("rate_limit", {"src": src, "dst": None, "bps": 2e7}))
            if "lateral" in attack_targets and entity in self.engine.topology.nodes:
                cands.append(("isolate", {"node": entity}))
            adict = alert.model_dump() if hasattr(alert, "model_dump") else dict(alert)
            ctx = context_vector(adict, scores.get(entity, 0.5))
            for kind, params in cands:
                refusal = self.constraint_check(kind, params)
                if refusal:
                    continue
                key = (kind, json.dumps(params, sort_keys=True))
                if any(a["kind"] == kind and json.dumps(a["params"], sort_keys=True) == key[1]
                       and a["status"] in ("proposed", "applied")
                       for a in self.actions.values()):
                    continue
                rank_score = self.bandit.score(kind, ctx)
                proposals.append({"kind": kind, "params": params,
                                  "context": adict, "ctx": ctx,
                                  "bandit_score": rank_score, "alert_id": adict.get("id")})
        proposals.sort(key=lambda p: -p["bandit_score"])
        created = []
        for p in proposals[:3]:
            self._seq += 1
            action = {"id": f"act-{self._seq}", "kind": p["kind"],
                      "params": p["params"], "status": "proposed",
                      "created_at": time.time(), "bandit_score": round(p["bandit_score"], 3),
                      "alert_id": p["alert_id"], "ctx": p["ctx"],
                      "sandbox": self.sandbox_evaluate(p["kind"], p["params"])}
            self.actions[action["id"]] = action
            created.append({k: v for k, v in action.items() if k != "ctx"})
        return created

    # ---- apply / revert ------------------------------------------------------
    def apply(self, action_id: str, auto: bool = False) -> dict[str, Any]:
        action = self.actions.get(action_id)
        if not action:
            raise ValueError("unknown action")
        if action["status"] != "proposed":
            raise ValueError(f"action is {action['status']}")
        refusal = self.constraint_check(action["kind"], action["params"])
        if refusal:
            action["status"] = "rejected"
            raise ValueError(refusal)
        if auto and not action["sandbox"]["improves"]:
            action["status"] = "rejected"
            raise ValueError("sandbox predicts no improvement")
        policy = self.engine.apply_policy(action["kind"], **action["params"])
        action["status"] = "applied"
        action["policy_id"] = policy["id"]
        action["applied_at"] = time.time()
        action["applied_tick"] = self.engine.tick
        action["health_at_apply"] = None
        self._pending_rewards.append(action)
        self.history.append({k: v for k, v in action.items() if k != "ctx"})
        self.history = self.history[-100:]
        if self.on_apply_aws:
            self.on_apply_aws(action_id, action["kind"], action["params"])
        return {k: v for k, v in action.items() if k != "ctx"}

    def revert(self, action_id: str) -> dict[str, Any]:
        action = self.actions.get(action_id)
        if not action:
            raise ValueError("unknown action")
        if action["status"] != "applied":
            raise ValueError(f"action is {action['status']}")
        self.engine.revert_policy(action["policy_id"])
        action["status"] = "reverted"
        action["reverted_at"] = time.time()
        return {k: v for k, v in action.items() if k != "ctx"}

    # ---- per-tick -------------------------------------------------------------
    def tick(self, network_health: float) -> list[dict[str, Any]]:
        """Collect rewards for applied actions; auto-apply in auto mode."""
        rewarded = []
        for action in list(self._pending_rewards):
            if action["status"] != "applied":
                self._pending_rewards.remove(action)
                continue
            if action.get("health_at_apply") is None:
                action["health_at_apply"] = network_health
                continue
            if self.engine.tick - action["applied_tick"] >= self.s.response.reward_after_ticks:
                reward = network_health - action["health_at_apply"]
                action["reward"] = round(reward, 3)
                self.bandit.update(action["kind"], action["ctx"], reward / 20.0)
                self.save_state()
                self._pending_rewards.remove(action)
                rewarded.append({"id": action["id"], "reward": action["reward"]})
        return rewarded

    def auto_act(self, alerts: list[Any], scores: dict[str, float]) -> list[dict[str, Any]]:
        applied = []
        if self.mode != "auto":
            return applied
        n_active = sum(1 for a in self.actions.values() if a["status"] == "applied")
        if n_active >= self.s.response.max_active_actions:
            return applied
        for action in list(self.actions.values()):
            if action["status"] == "proposed" and action["sandbox"]["improves"]:
                try:
                    applied.append(self.apply(action["id"], auto=True))
                except ValueError:
                    pass
                break
        return applied

    def snapshot(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "actions": [{k: v for k, v in a.items() if k != "ctx"}
                        for a in sorted(self.actions.values(),
                                        key=lambda a: -a["created_at"])][:20],
            "rewards": [{"id": a["id"], "reward": a.get("reward")}
                        for a in self.history if a.get("reward") is not None],
        }
