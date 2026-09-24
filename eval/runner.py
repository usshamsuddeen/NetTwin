"""NetTwin 3.0 — Headless Experiment Runner.

Orchestrates simulation runs with configurable seeds, tick counts, and attack
schedules. Collects per-tick metrics into structured arrays for figure generation.
Uses a lightweight synchronous alert tracker (no DB dependency).

v3 changes:
  - 15 seeds for statistical rigor
  - 64-core multiprocessing.Pool support
  - Bug fixes for divergence weight injection, mode overrides, ablation flags
  - Per-tick telemetry storage for campaign analysis
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Any

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nettwin.config import Settings, load_settings
from nettwin.models import Alert, TelemetryTick
from nettwin.ingestion.normalize import Normalizer
from nettwin.ingestion.sync import SyncEngine
from nettwin.simulator.engine import SimulationEngine
from nettwin.twin.detector import AnomalyDetector
from nettwin.twin.state import TwinState, node_health, link_health
from nettwin.twin.subspace import SubspaceDetector
from nettwin.twin.conformal import ConformalCalibrator
from nettwin.twin.drift import DriftMonitor
from nettwin.twin.causal import CausalAnalyzer
from nettwin.twin.predictor import Predictor as HoltPredictor
from nettwin.risk.attack_graph import AttackGraph
from nettwin.response.agent import ResponseAgent
from nettwin.research import ResearchMetrics

from eval.design import RESULTS_DIR


# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_SEEDS = [42, 101, 202, 303, 404, 505, 606, 707, 808, 909,
                 1010, 1111, 1212, 1313, 1414]  # 15 seeds
ATTACK_TYPES = ["ddos", "portscan", "exfiltration", "lateral", "bruteforce"]
ATTACK_TARGETS = {"ddos": "web1", "portscan": "web1", "exfiltration": "db1",
                  "lateral": "app1", "bruteforce": "web1"}
N_CORES = min(64, cpu_count())


# ─── Lightweight synchronous alert manager (no DB) ───────────────────────────

class LightAlertManager:
    """Synchronous alert manager for headless experiment runs.
    No database, no async — just in-memory alert lifecycle."""

    def __init__(self, settings: Settings):
        self.s = settings
        self.alerts: dict[str, Alert] = {}
        self._by_key: dict[tuple[str, str], str] = {}
        self._clear_streak: dict[str, int] = {}

    def update(self, tick: TelemetryTick, scores: dict[str, float],
               signals: dict[str, dict[str, Any]],
               conformal: ConformalCalibrator | None = None) -> list[Alert]:
        changed: list[Alert] = []
        warn_th = self.s.detector.warn_threshold
        alert_th = self.s.detector.alert_threshold
        for entity_id, score in scores.items():
            conf = conformal.confidence(score) if conformal else -1.0
            if score >= alert_th:
                sig = signals.get(entity_id, {})
                metric = sig.get("top_metric", "")
                kind = sig.get("entity_kind", "node")
                severity = "critical" if score >= 0.9 else "warning"
                atype = f"anomaly:{metric or 'score'}"
                msg = f"Anomaly on {entity_id}: score {score:.2f}"
                existing = self._find_by_key(entity_id, atype)
                self._clear_streak[entity_id] = 0
                if existing and tick.tick - existing.tick < self.s.alerts.cooldown_ticks:
                    existing.score = max(existing.score, score)
                    existing.confidence = conf
                    existing.tick = tick.tick
                    existing.hits += 1
                    existing.updated_at = time.time()
                    existing.severity = severity
                    changed.append(existing)
                else:
                    a = Alert(entity_id=entity_id, entity_kind=kind,
                              alert_type=atype, severity=severity,
                              message=msg, score=score, tick=tick.tick,
                              confidence=conf)
                    self._register(a)
                    changed.append(a)
            elif score < warn_th:
                active_id = self._find_active_id(entity_id)
                if active_id:
                    streak = self._clear_streak.get(entity_id, 0) + 1
                    self._clear_streak[entity_id] = streak
                    if streak >= self.s.alerts.resolve_after_ticks:
                        a = self.alerts[active_id]
                        a.status = "resolved"
                        a.updated_at = time.time()
                        changed.append(a)
                        self._clear_streak[entity_id] = 0
        return changed

    def _register(self, a: Alert) -> None:
        self.alerts[a.id] = a
        self._by_key[(a.entity_id, a.alert_type)] = a.id

    def _find_by_key(self, entity_id: str, atype: str) -> Alert | None:
        aid = self._by_key.get((entity_id, atype))
        a = self.alerts.get(aid) if aid else None
        if a and a.status == "resolved":
            return None
        return a

    def _find_active_id(self, entity_id: str) -> str | None:
        for a in self.alerts.values():
            if a.entity_id == entity_id and a.status == "active":
                return a.id
        return None

    def active(self) -> list[Alert]:
        return sorted((a for a in self.alerts.values() if a.status == "active"),
                      key=lambda a: a.updated_at, reverse=True)

    def total_alerts_raised(self) -> int:
        return len(self.alerts)

    def false_positive_count(self, attack_ticks: set[int],
                             window: int = 5) -> int:
        """Count alerts raised during non-attack periods."""
        fp = 0
        for a in self.alerts.values():
            if not any(abs(a.tick - t) <= window for t in attack_ticks):
                fp += 1
        return fp


# ─── Attack Schedule ─────────────────────────────────────────────────────────

@dataclass
class AttackSchedule:
    """When to start/stop attacks during a run."""
    entries: list[dict[str, Any]] = field(default_factory=list)

    def add(self, start_tick: int, attack_type: str,
            target_id: str | None = None,
            duration_ticks: int = 50) -> "AttackSchedule":
        self.entries.append({
            "start": start_tick, "type": attack_type,
            "target": target_id, "duration_ticks": duration_ticks,
        })
        return self

    @classmethod
    def all_attacks(cls, start: int = 200, gap: int = 150,
                    duration: int = 60) -> "AttackSchedule":
        sched = cls()
        types = ["ddos", "portscan", "exfiltration", "lateral", "bruteforce"]
        targets = ["web1", "web1", "db1", "app1", "web1"]
        for i, (at, tgt) in enumerate(zip(types, targets)):
            sched.add(start + i * gap, at, tgt, duration)
        return sched

    @classmethod
    def single_attack(cls, attack_type: str, target: str = "web1",
                      start: int = 200, duration: int = 60) -> "AttackSchedule":
        return cls().add(start, attack_type, target, duration)

    def attack_tick_set(self) -> set[int]:
        """All ticks during which an attack is active."""
        ticks: set[int] = set()
        for e in self.entries:
            for t in range(e["start"], e["start"] + e["duration_ticks"]):
                ticks.add(t)
        return ticks


# ─── Tick record ─────────────────────────────────────────────────────────────

@dataclass
class TickRecord:
    tick: int = 0
    network_health: float = 100.0
    total_throughput: float = 0.0
    avg_latency: float = 0.0
    avg_loss: float = 0.0
    max_anomaly_score: float = 0.0
    num_alerts_active: int = 0
    num_attacks_active: int = 0
    subspace_spe: float = 0.0
    subspace_score: float = 0.0
    conformal_coverage: float = -1.0
    fidelity: float = 100.0
    network_risk: float = 0.0
    cumulative_reward: float = 0.0
    # v3: per-entity scores for detailed analysis
    entity_scores: dict[str, float] = field(default_factory=dict)
    # v3: sync mode per entity
    sync_modes: dict[str, str] = field(default_factory=dict)


def compute_network_health(tick: TelemetryTick) -> float:
    nh = [node_health(m) for m in tick.nodes.values()]
    lh = [link_health(m) for m in tick.links.values() if m.utilization_pct < 400]
    return 0.7 * (sum(nh) / max(1, len(nh))) + 0.3 * (sum(lh) / max(1, len(lh)))


# ─── Experiment Run ──────────────────────────────────────────────────────────

class ExperimentRun:
    """Single headless experiment run with full pipeline.

    Bug fixes in v3:
    - divergence weights flow through SyncSettings into EntitySync
    - sync mode properly set to SIM-only when requested
    - ACI ablation flags propagated to conformal calibrator
    - response mode set before run() entry
    """

    def __init__(self, seed: int = 42, overrides: dict[str, Any] | None = None,
                 topology=None, response_bandit: type | None = None):
        ov = overrides or {}
        ov.setdefault("auto_attacks", False)

        # Back-compat: translate legacy top-level flags into nested settings.
        if ov.pop("sim_only", False):
            ov.setdefault("sync", {})["enabled"] = False
        if ov.pop("disable_aci", False):
            ov.setdefault("conformal", {})["aci_enabled"] = False
        # BUG FIX #6: protected infra attack flag (consumed by p5_system hooks)
        self._attack_protected = ov.pop("attack_protected", False)

        self.settings = load_settings(
            path=Path(__file__).resolve().parent.parent / "config.json",
            overrides=ov)
        self.engine = SimulationEngine(self.settings, topology=topology, seed=seed)
        self.twin = TwinState(self.settings)
        self.detector = AnomalyDetector(self.settings.detector)
        self.subspace = SubspaceDetector(self.settings.subspace)

        # Conformal calibrator (can be ablated)
        if self.settings.conformal.enabled:
            self.conformal = ConformalCalibrator(self.settings.conformal)
        else:
            self.conformal = None  # type: ignore[assignment]

        # Drift monitor (can be ablated)
        if self.settings.drift.enabled:
            self.drift = DriftMonitor(
                self.settings.drift.delta, self.settings.drift.lam,
                self.settings.drift.cooldown_ticks)
        else:
            self.drift = None  # type: ignore[assignment]

        # Real-world sync engine (disabled for SIM-only baselines)
        if self.settings.sync.enabled:
            self.sync = SyncEngine(self.settings.sync, self.engine.topology)
            self.normalizer = Normalizer(self.sync.resolve)
            bias_rng = np.random.default_rng(seed + 888)
            self._sync_bias: dict[str, float] | None = {
                nid: 1.0 + bias_rng.uniform(-0.01, 0.01)
                for nid in self.engine.topology.nodes}
            self._sync_noise_rng: np.random.Generator | None = np.random.default_rng(seed + 999)
        else:
            self.sync = None
            self.normalizer = None
            self._sync_bias = None
            self._sync_noise_rng = None

        self.causal = CausalAnalyzer(self.engine.topology)
        self.risk = AttackGraph(self.engine.topology, self.settings.risk)
        self.alerts = LightAlertManager(self.settings)
        self.predictor = HoltPredictor(self.settings.forecast)
        self.response = ResponseAgent(self.settings, self.engine,
                                      bandit_class=response_bandit)
        self.research = ResearchMetrics()

        self.records: list[TickRecord] = []
        self.detection_events: list[dict[str, Any]] = []
        self.drift_events: list[dict[str, Any]] = []
        self.rca_results: list[dict[str, Any]] = []
        self.response_history: list[dict[str, Any]] = []
        self._detected_attack_ids: set[str] = set()
        # v3: per-tick telemetry storage for campaign analysis
        self.per_tick_telemetry: list[dict[str, Any]] = []

    def _sync_ingest(self, tick: TelemetryTick) -> None:
        """Feed a perturbed copy of the simulated metrics as real telemetry.

        The small deterministic bias + per-tick noise create non-zero divergence
        so that divergence-weight sweeps actually exercise the sync engine.
        """
        if self.sync is None or self.normalizer is None:
            return
        now = tick.tick * self.settings.tick_s
        records: list[dict[str, Any]] = []
        for nid, m in tick.nodes.items():
            bias = self._sync_bias.get(nid, 1.0) if self._sync_bias else 1.0
            noise = float(self._sync_noise_rng.normal(0, 0.01)) if self._sync_noise_rng else 0.0
            factor = bias * (1.0 + noise)
            records.append({"type": "interface", "host": nid,
                            "in_bps": m.rx_mbps * 1e6 * factor,
                            "out_bps": m.tx_mbps * 1e6 * factor})
            records.append({"type": "gauge", "host": nid,
                            "metrics": {"latency_ms": m.latency_ms * factor}})
        batch = self.normalizer.normalize(records)
        self.sync.ingest(batch, self.settings.tick_s, now=now)

    def run(self, n_ticks: int, schedule: AttackSchedule | None = None,
            response_mode: str = "off",
            progress: bool = False,
            store_telemetry: bool = False) -> list[TickRecord]:
        # BUG FIX #5: Set response mode before loop
        self.response.mode = response_mode
        sched = schedule.entries if schedule else []
        active_attacks: dict[str, int] = {}

        for t in range(1, n_ticks + 1):
            # schedule attacks
            for entry in sched:
                if entry["start"] == t:
                    ev = self.engine.start_attack(
                        entry["type"], entry.get("target"))
                    active_attacks[ev.id] = t + entry["duration_ticks"]

            # expire attacks
            for aid, end in list(active_attacks.items()):
                if t >= end and aid in self.engine.attacks:
                    self.engine.stop_attack(aid)
                    del active_attacks[aid]

            # simulation step
            tick = self.engine.step()
            attacking = len(tick.active_attacks) > 0

            # real-world sync: feed perturbed telemetry, then apply HYBRID updates
            if self.settings.sync.enabled and self.sync is not None:
                self._sync_ingest(tick)
                self.sync.update(tick)

            # twin state
            self.twin.update(tick)

            # detection
            scores, signals = self.detector.update(tick)
            spe_score = self.subspace.update(tick, attacking)

            # conformal
            max_score = max(scores.values()) if scores else 0.0
            warmup_done = tick.tick > self.settings.detector.warmup_ticks
            alarmed = any(s >= self.settings.detector.alert_threshold
                          for s in scores.values())
            if self.conformal is not None:
                if not attacking and warmup_done:
                    self.conformal.calibrate(max_score)

                # conformal forecast interval & empirical coverage tracking
                tp = self.twin.kpis.total_throughput_mbps
                lat = self.twin.kpis.avg_latency_ms
                self.conformal.check_coverage(tp, anomaly_active=alarmed)
                fc1 = self.predictor.forecast("network", "throughput_mbps", 1)
                if fc1 and warmup_done:
                    err = abs(fc1.points[0].mean - tp)
                    self.conformal.observe_forecast_error(err)
                    lo, hi = self.conformal.interval(fc1.points[0].mean)
                    self.conformal.set_pending_interval(lo, hi)
                coverage = self.conformal.realized_coverage()
            else:
                coverage = None

            # drift
            nh = compute_network_health(tick)
            if self.drift is not None:
                drift_ev = self.drift.update(
                    tick.tick,
                    self.twin.kpis.total_throughput_mbps,
                    self.twin.kpis.avg_latency_ms,
                    attacking, alarmed)
                if drift_ev:
                    self.drift_events.append({
                        "tick": drift_ev.tick, "metric": drift_ev.metric,
                        "suspected_attack": drift_ev.suspected_attack,
                    })

            # risk
            seeds = {eid: s for eid, s in scores.items()
                     if s >= self.settings.detector.warn_threshold}
            self.risk.recompute(seeds)

            # alerts
            new_alerts = self.alerts.update(tick, scores, signals, self.conformal)

            # detection latency tracking
            for atk in tick.active_attacks:
                if atk.id not in self._detected_attack_ids and new_alerts:
                    self._detected_attack_ids.add(atk.id)
                    self.detection_events.append({
                        "attack_id": atk.id,
                        "attack_type": atk.attack_type,
                        "target": atk.target_id,
                        "start_tick": atk.start_tick,
                        "detect_tick": tick.tick,
                        "latency_ticks": tick.tick - atk.start_tick,
                    })

            # response
            if response_mode != "off":
                active_list = self.alerts.active()
                self.response.propose(active_list, scores)
                if response_mode == "auto":
                    applied = self.response.auto_act(active_list, scores)
                    for act_item in applied:
                        act_item.setdefault("tick", act_item.get("applied_tick", tick.tick))
                        act_item.setdefault("action", act_item.get("kind", ""))
                        tgt = (act_item.get("params", {}).get("dst") or
                               act_item.get("params", {}).get("node") or
                               act_item.get("params", {}).get("src") or "network")
                        act_item.setdefault("target", tgt)
                    self.response_history.extend(applied)
                rewarded = self.response.tick(nh)
                for r in rewarded:
                    self.research.note_reward(r["reward"])

            # record
            rec = TickRecord(
                tick=tick.tick,
                network_health=round(nh, 2),
                total_throughput=round(self.twin.kpis.total_throughput_mbps, 2),
                avg_latency=round(self.twin.kpis.avg_latency_ms, 3),
                avg_loss=round(self.twin.kpis.avg_loss_pct, 3),
                max_anomaly_score=round(max_score, 3),
                num_alerts_active=len(self.alerts.active()),
                num_attacks_active=len(tick.active_attacks),
                subspace_spe=round(self.subspace.last_spe, 3),
                subspace_score=round(spe_score, 3),
                conformal_coverage=round(coverage, 3) if coverage else -1.0,
                network_risk=self.risk.network_risk,
                cumulative_reward=self.research.cumulative_reward,
                entity_scores=dict(scores) if store_telemetry else {},
            )
            self.records.append(rec)

            # BUG FIX #8: Store per-tick telemetry for campaign analysis
            if store_telemetry:
                self.per_tick_telemetry.append({
                    "tick": tick.tick,
                    "health": round(nh, 2),
                    "throughput": round(self.twin.kpis.total_throughput_mbps, 2),
                    "latency": round(self.twin.kpis.avg_latency_ms, 3),
                    "score": round(max_score, 3),
                    "risk": round(self.risk.network_risk, 3),
                    "n_attacks": len(tick.active_attacks),
                    "n_alerts": len(self.alerts.active()),
                    "reward": round(self.research.cumulative_reward, 3),
                })

            if progress and t % 2000 == 0:
                print(f"    tick {t}/{n_ticks}  health={nh:.1f}  score={max_score:.3f}")

        return self.records

    def health_array(self) -> np.ndarray:
        return np.array([r.network_health for r in self.records])

    def score_array(self) -> np.ndarray:
        return np.array([r.max_anomaly_score for r in self.records])

    def throughput_array(self) -> np.ndarray:
        return np.array([r.total_throughput for r in self.records])

    def latency_array(self) -> np.ndarray:
        return np.array([r.avg_latency for r in self.records])

    def coverage_array(self) -> np.ndarray:
        return np.array([r.conformal_coverage for r in self.records])

    def risk_array(self) -> np.ndarray:
        return np.array([r.network_risk for r in self.records])

    def reward_array(self) -> np.ndarray:
        return np.array([r.cumulative_reward for r in self.records])

    def subspace_array(self) -> np.ndarray:
        return np.array([r.subspace_score for r in self.records])

    def spe_array(self) -> np.ndarray:
        return np.array([r.subspace_spe for r in self.records])

    def rca_evaluate(self, attack_type: str, target: str) -> dict[str, Any]:
        true_root = target
        ranked = self.causal.rank(
            self.twin, self.detector, focus=target,
            warn=self.settings.detector.warn_threshold)
        entities = [r["entity_id"] for r in ranked]
        result = {
            "attack_type": attack_type,
            "target": target,
            "true_root": true_root,
            "ranked": entities,
            "scores": {r["entity_id"]: r["causal_score"] for r in ranked},
            "top1_hit": true_root in entities[:1],
            "top3_hit": true_root in entities[:3],
            "top5_hit": true_root in entities[:5],
            "true_root_position": (entities.index(true_root) + 1
                                   if true_root in entities else -1),
        }
        self.rca_results.append(result)
        return result


# ─── Parallel execution helpers ──────────────────────────────────────────────

def _run_single(args: tuple) -> dict[str, Any]:
    """Worker function for parallel seed execution."""
    (seed, n_ticks, schedule_data, response_mode, overrides, store_telemetry,
     response_bandit) = args
    sched = AttackSchedule(entries=schedule_data) if schedule_data else None
    run = ExperimentRun(seed=seed, overrides=overrides,
                        response_bandit=response_bandit)
    run.run(n_ticks, schedule=sched, response_mode=response_mode,
            store_telemetry=store_telemetry)
    return {
        "seed": seed,
        "health": run.health_array().tolist(),
        "scores": run.score_array().tolist(),
        "throughput": run.throughput_array().tolist(),
        "latency": run.latency_array().tolist(),
        "coverage": run.coverage_array().tolist(),
        "risk": run.risk_array().tolist(),
        "reward": run.reward_array().tolist(),
        "detection_events": run.detection_events,
        "drift_events": run.drift_events,
        "response_history": run.response_history,
        "records_summary": {
            "mean_health": float(run.health_array().mean()),
            "mean_score": float(run.score_array().mean()),
            "total_alerts": run.alerts.total_alerts_raised(),
        },
        "per_tick": run.per_tick_telemetry if store_telemetry else [],
    }


def run_multi_seed(n_ticks: int, seeds: list[int],
                   schedule: AttackSchedule | None = None,
                   response_mode: str = "off",
                   overrides: dict[str, Any] | None = None,
                   topology=None,
                   progress: bool = False,
                   response_bandit: type | None = None) -> list[ExperimentRun]:
    """Run experiments across multiple seeds (sequential)."""
    runs = []
    for i, seed in enumerate(seeds):
        if progress:
            print(f"  seed {seed} ({i+1}/{len(seeds)})")
        run = ExperimentRun(seed=seed, overrides=overrides, topology=topology,
                            response_bandit=response_bandit)
        run.run(n_ticks, schedule=schedule, response_mode=response_mode,
                progress=progress)
        runs.append(run)
    return runs


def run_parallel_seeds(n_ticks: int, seeds: list[int],
                       schedule: AttackSchedule | None = None,
                       response_mode: str = "off",
                       overrides: dict[str, Any] | None = None,
                       n_workers: int = 0,
                       store_telemetry: bool = False,
                       response_bandit: type | None = None) -> list[dict[str, Any]]:
    """Run experiments in parallel across seeds using multiprocessing.Pool.
    Returns list of result dicts (one per seed).
    """
    if n_workers <= 0:
        n_workers = N_CORES
    sched_data = schedule.entries if schedule else None
    args = [(seed, n_ticks, sched_data, response_mode,
             overrides, store_telemetry, response_bandit) for seed in seeds]

    print(f"  Launching {len(seeds)} seeds on {n_workers} cores...")
    t0 = time.perf_counter()
    with Pool(n_workers) as pool:
        results = pool.map(_run_single, args)
    elapsed = time.perf_counter() - t0
    print(f"  Completed {len(seeds)} seeds in {elapsed:.1f}s "
          f"({elapsed/len(seeds):.1f}s/seed)")
    return results


def save_results(data: Any, name: str) -> Path:
    path = RESULTS_DIR / f"{name}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  [OK] saved {path.relative_to(RESULTS_DIR.parent)}")
    return path
