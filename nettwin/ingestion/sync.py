"""SyncEngine: SIMULATED -> SHADOW -> HYBRID state machine + fidelity metrics."""
from __future__ import annotations

import math
import time
from collections import deque
from typing import Any

from nettwin.config import SyncSettings
from nettwin.models import TelemetryTick
from nettwin.simulator.topology import Topology

FIDELITY_METRICS = ("throughput_mbps", "pps", "latency_ms")


class EntitySync:
    def __init__(self, entity_id: str, settings: SyncSettings | None = None) -> None:
        self.entity_id = entity_id
        self.s = settings or SyncSettings()
        self.mode = "SIMULATED"
        self.forced: str | None = None
        self.last_seen: float = 0.0
        self.real: dict[str, float] = {}
        self.pairs: dict[str, deque[tuple[float, float]]] = {
            m: deque(maxlen=120) for m in FIDELITY_METRICS}
        self.div_ema = 0.0
        self.div_var = 0.0
        self.div_n = 0
        self.fidelity = 100.0
        self.good_streak = 0
        self.bad_streak = 0
        self.seen_once = False

    def divergence(self) -> float:
        """Scale/shape-aware divergence in [0,1] over the pair window.

        Per metric: relative level error between sim and real means, blended
        with (1 - correlation) so a scale offset alone does not dominate.
        """
        divs = []
        for m in FIDELITY_METRICS:
            pairs = list(self.pairs[m])
            if len(pairs) < 5:
                continue
            sim = [p[0] for p in pairs]
            real = [p[1] for p in pairs]
            n = len(pairs)
            mean_s = sum(sim) / n
            mean_r = sum(real) / n
            rel = abs(mean_s - mean_r) / (mean_s + mean_r + 1e-3)
            var_s = sum((a - mean_s) ** 2 for a in sim) / n
            var_r = sum((b - mean_r) ** 2 for b in real) / n
            if var_s < 1e-12 and var_r < 1e-12:
                corr = 1.0  # both flat: shape matches, only level matters
            elif var_s < 1e-12 or var_r < 1e-12:
                corr = 0.0
            else:
                cov = sum((a - mean_s) * (b - mean_r) for a, b in pairs) / n
                corr = max(-1.0, min(1.0, cov / math.sqrt(var_s * var_r)))
            divs.append(min(1.0, self.s.divergence_w_rel * min(1.0, rel)
                            + self.s.divergence_w_corr * (1.0 - corr)))
        return sum(divs) / len(divs) if divs else 0.0

    def adaptive_threshold(self, base: float) -> float:
        if self.div_n < 10:
            return base
        return max(base, self.div_ema + 3.0 * math.sqrt(self.div_var))


class SyncEngine:
    def __init__(self, settings: SyncSettings, topology: Topology) -> None:
        self.s = settings
        self.topology = topology
        self.entities: dict[str, EntitySync] = {}
        self.pending: dict[str, dict[str, float]] = {}  # latest real metrics per entity
        self.drift_flags: dict[str, bool] = {}

    # ---- entity resolution ------------------------------------------------
    def resolve(self, host: str) -> str | None:
        if not host:
            return None
        host = str(host).strip()
        if host in self.s.sync_map:
            return self.s.sync_map[host]
        if host in self.topology.nodes:
            return host
        slug = host.lower().split(".")[0]
        slug = "".join(c for c in slug if c.isalnum())
        if slug in self.topology.nodes:
            return slug
        for nid, node in self.topology.nodes.items():
            label_slug = "".join(c for c in node.label.lower() if c.isalnum())
            if slug and (slug == label_slug or slug == nid.lower()):
                return nid
        return None

    def entity(self, entity_id: str) -> EntitySync:
        return self.entities.setdefault(
            entity_id, EntitySync(entity_id, settings=self.s))

    # ---- ingest -------------------------------------------------------------
    def ingest(self, batch, tick_s: float, now: float | None = None) -> list[str]:
        now = now if now is not None else time.time()
        touched = []
        for eid in batch.entities():
            es = self.entity(eid)
            es.last_seen = now
            es.seen_once = True
            real = self.pending.setdefault(eid, {})
            if eid in batch.gauges:
                real.update(batch.gauges[eid])
            tx_b = batch.tx_bytes.get(eid)
            rx_b = batch.rx_bytes.get(eid)
            if tx_b is not None or rx_b is not None:
                tx = (tx_b or 0) * 8.0 / tick_s / 1e6
                rx = (rx_b or 0) * 8.0 / tick_s / 1e6
                real["tx_mbps"] = tx
                real["rx_mbps"] = rx
                real["throughput_mbps"] = tx + rx
            tp = batch.tx_pkts.get(eid, 0) + batch.rx_pkts.get(eid, 0)
            if tp:
                real["pps"] = tp / tick_s
            touched.append(eid)
        return touched

    # ---- per-tick update ----------------------------------------------------
    def update(self, tick: TelemetryTick, now: float | None = None) -> dict[str, str]:
        if not self.s.enabled:
            return {}
        now = now if now is not None else time.time()
        transitions: dict[str, str] = {}
        for eid, es in self.entities.items():
            self._update_entity(es, tick, now, transitions)
        return transitions

    def _update_entity(self, es: EntitySync, tick: TelemetryTick,
                       now: float, transitions: dict[str, str]) -> None:
        stale = (now - es.last_seen) > self.s.staleness_s if es.seen_once else True
        sim = tick.nodes.get(es.entity_id)
        if not stale and es.seen_once:
            es.real = dict(self.pending.get(es.entity_id, {}))
            if sim is not None:
                real_tp = es.real.get("throughput_mbps")
                if real_tp is not None:
                    es.pairs["throughput_mbps"].append((sim.throughput_mbps, real_tp))
                if "pps" in es.real:
                    es.pairs["pps"].append((sim.pps, es.real["pps"]))
                if "latency_ms" in es.real:
                    es.pairs["latency_ms"].append((sim.latency_ms, es.real["latency_ms"]))
                div = es.divergence()
                es.fidelity = round(100.0 * (1.0 - div), 1)
                if es.div_n == 0:
                    es.div_ema, es.div_var = div, 0.0
                else:
                    delta = div - es.div_ema
                    es.div_ema += 0.15 * delta
                    es.div_var = 0.85 * es.div_var + 0.15 * delta * delta
                es.div_n += 1

        target = es.mode
        if es.forced:
            target = es.forced
        elif stale or not es.seen_once:
            target = "SIMULATED"
            if es.mode != "SIMULATED":
                es.good_streak = es.bad_streak = 0
        else:
            if es.mode == "SIMULATED":
                target = "SHADOW"
                es.good_streak = es.bad_streak = 0
            fidelity_ok = es.fidelity >= self.s.fidelity_hybrid_min
            if es.mode == "SHADOW":
                es.good_streak = es.good_streak + 1 if fidelity_ok else 0
                es.bad_streak = 0 if fidelity_ok else es.bad_streak + 1
                if es.good_streak >= self.s.hybrid_after_ticks:
                    target = "HYBRID"
                    es.good_streak = es.bad_streak = 0
            elif es.mode == "HYBRID":
                es.bad_streak = 0 if fidelity_ok else es.bad_streak + 1
                if es.bad_streak >= self.s.drop_after_ticks:
                    target = "SHADOW"
                    es.bad_streak = 0

        if target != es.mode:
            transitions[es.entity_id] = f"{es.mode}->{target}"
            es.mode = target

        # HYBRID: real values drive the twin entity; simulator fills the rest
        if es.mode == "HYBRID" and not stale and sim is not None:
            for key, val in es.real.items():
                if hasattr(sim, key):
                    setattr(sim, key, round(float(val), 3))

    def drift_alerts(self) -> list[str]:
        """Entities stuck in SHADOW with divergence above the adaptive bar."""
        out = []
        for eid, es in self.entities.items():
            if es.mode == "SHADOW" and es.div_n >= self.s.drift_after_ticks:
                if es.divergence() > (1.0 - self.s.fidelity_warn / 100.0):
                    out.append(eid)
        return out

    def force_mode(self, entity_id: str, mode: str) -> None:
        es = self.entity(entity_id)
        if mode == "auto":
            es.forced = None
        elif mode in ("SIMULATED", "SHADOW", "HYBRID"):
            es.forced = mode
        else:
            raise ValueError(f"unknown mode: {mode}")

    def snapshot(self) -> list[dict[str, Any]]:
        now = time.time()
        return [{
            "entity_id": eid,
            "mode": es.mode,
            "forced": es.forced,
            "fidelity": es.fidelity,
            "divergence": round(es.divergence(), 4),
            "last_seen_ago_s": round(now - es.last_seen, 1) if es.seen_once else None,
            "samples": es.div_n,
        } for eid, es in sorted(self.entities.items())]

    def network_fidelity(self) -> float:
        vals = [es.fidelity for es in self.entities.values()
                if es.mode in ("SHADOW", "HYBRID")]
        return round(sum(vals) / len(vals), 1) if vals else 100.0
