"""Causal root-cause analysis over the entity-metric graph.

Approach: lagged-correlation (Granger-style) screening between entity metric
series on a rolling window, constrained by topology distance; candidates are
scored by downstream-explained correlation, temporal precedence of anomaly
onset, anomaly magnitude, and topological centrality.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from nettwin.simulator.topology import Topology
from nettwin.twin.detector import AnomalyDetector
from nettwin.twin.state import TwinState

WINDOW = 80
MAX_DIST = 3


class CausalAnalyzer:
    def __init__(self, topology: Topology) -> None:
        self.topo = topology
        self._dist: dict[tuple[str, str], int] = {}
        self._degree: dict[str, int] = {}
        self._precompute()

    def _precompute(self) -> None:
        nodes = list(self.topo.nodes)
        for a in nodes:
            for b in nodes:
                path = self.topo.paths.get((a, b))
                if path is not None:
                    self._dist[(a, b)] = len(path) - 1
        for nid in nodes:
            self._degree[nid] = len(self.topo.links_of(nid))
        # link entities: distance = min distance between endpoints
        for lid, link in self.topo.links.items():
            for nid in nodes:
                d = min(self._dist.get((link.src, nid), 99),
                        self._dist.get((link.dst, nid), 99))
                self._dist[(lid, nid)] = d
                self._dist[(nid, lid)] = d
            for lid2, link2 in self.topo.links.items():
                if lid == lid2:
                    self._dist[(lid, lid2)] = 0
                else:
                    self._dist[(lid, lid2)] = min(
                        self._dist.get((link.src, link2.src), 99),
                        self._dist.get((link.src, link2.dst), 99),
                        self._dist.get((link.dst, link2.src), 99),
                        self._dist.get((link.dst, link2.dst), 99))

    def dist(self, a: str, b: str) -> int:
        if a == b:
            return 0
        return self._dist.get((a, b), 99)

    # ---- series extraction -------------------------------------------------
    def _series(self, twin: TwinState) -> dict[str, np.ndarray]:
        out: dict[str, np.ndarray] = {}
        for nid, buf in twin.node_history.items():
            vals = [m.throughput_mbps for m in list(buf)[-WINDOW:]]
            if len(vals) >= 30:
                out[nid] = np.asarray(vals, dtype=float)
        for lid, buf in twin.link_history.items():
            vals = [m.utilization_pct for m in list(buf)[-WINDOW:]]
            if len(vals) >= 30:
                out[lid] = np.asarray(vals, dtype=float)
        return out

    def _onsets(self, detector: AnomalyDetector, warn: float) -> dict[str, int]:
        onsets: dict[str, int] = {}
        for eid, hist in detector.score_history.items():
            vals = list(hist)[-WINDOW:]
            onset = len(vals)
            for i in range(len(vals) - 1, -1, -1):
                if vals[i] >= warn:
                    onset = i
                else:
                    break
            if onset < len(vals):
                onsets[eid] = onset
        return onsets

    @staticmethod
    def _best_corr(x: np.ndarray, y: np.ndarray, max_lag: int = 3) -> float:
        n = min(len(x), len(y))
        x, y = x[-n:], y[-n:]
        best = 0.0
        for lag in range(0, max_lag + 1):
            a = x[: n - lag] if lag else x
            b = y[lag:] if lag else y
            if len(a) < 10 or a.std() < 1e-9 or b.std() < 1e-9:
                continue
            r = float(np.corrcoef(a, b)[0, 1])
            if not np.isnan(r):
                best = max(best, abs(r))
        return best

    # ---- root-cause ranking --------------------------------------------------
    def rank(self, twin: TwinState, detector: AnomalyDetector,
             focus: str | None = None, warn: float = 0.5,
             top_n: int = 6) -> list[dict[str, Any]]:
        series = self._series(twin)
        onsets = self._onsets(detector, warn)
        scores = detector.scores
        candidates = [e for e in series
                      if scores.get(e, 0.0) >= warn or e in onsets or e == focus]
        if focus and focus not in candidates:
            candidates.append(focus)
        if not candidates:
            return []

        explained_raw: dict[str, float] = {}
        upstream_raw: dict[str, float] = {}
        for cand in candidates:
            total = 0.0
            upstream = 0.0
            xs = series.get(cand)
            if xs is None:
                explained_raw[cand] = 0.0
                upstream_raw[cand] = 0.0
                continue
            for other, ys in series.items():
                if other == cand:
                    continue
                d = self.dist(cand, other)
                if d > MAX_DIST:
                    continue
                r = self._best_corr(xs, ys)
                if onsets.get(other, 10**6) >= onsets.get(cand, 10**6):
                    total += r * r / (1.0 + d)  # downstream-in-time: we explain them
                other_mag = scores.get(other, 0.0)
                my_mag = scores.get(cand, 0.0)
                if (onsets.get(other, 10**6) < onsets.get(cand, 10**6)
                        or (onsets.get(other, 10**6) == onsets.get(cand, 10**6)
                            and other_mag > my_mag)):
                    upstream = max(upstream, r * r / (1.0 + d))  # they explain us
            explained_raw[cand] = total
            upstream_raw[cand] = upstream
        max_expl = max(explained_raw.values()) or 1.0
        max_onset = max(onsets.values()) if onsets else 1
        max_deg = max(self._degree.values()) or 1

        ranked = []
        for cand in candidates:
            mag = min(1.0, scores.get(cand, 0.0))
            expl = explained_raw[cand] / max_expl
            onset = onsets.get(cand, max_onset + 1)
            precedence = 1.0 - onset / (max_onset + 1)
            centrality = self._degree.get(cand, 1) / max_deg
            focus_boost = 0.25 if cand == focus else (
                0.1 if focus and self.dist(cand, focus) <= 1 else 0.0)
            penalty = min(1.0, upstream_raw[cand])
            score = (0.35 * mag + 0.30 * expl + 0.15 * precedence
                     + 0.10 * centrality + focus_boost - 0.35 * penalty)
            ranked.append({
                "entity_id": cand,
                "causal_score": round(score, 3),
                "anomaly_score": round(mag, 3),
                "explained": round(expl, 3),
                "onset_index": onset,
                "distance_to_focus": self.dist(cand, focus) if focus else None,
            })
        ranked.sort(key=lambda r: -r["causal_score"])
        return ranked[:top_n]
