"""Anomaly detection: robust EMA/MAD baselines + pure-numpy isolation forest."""
from __future__ import annotations

import math
from collections import deque
from typing import Any

import numpy as np

from nettwin.config import DetectorSettings
from nettwin.models import TelemetryTick

NODE_METRICS = ["throughput_mbps", "pps", "latency_ms", "packet_loss_pct",
                "fanout", "bytes_ratio"]
LINK_METRICS = ["utilization_pct", "throughput_mbps", "latency_ms", "packet_loss_pct"]
MIN_SIGMA = {"throughput_mbps": 0.3, "pps": 1.0, "latency_ms": 0.15,
             "packet_loss_pct": 0.05, "fanout": 0.45, "bytes_ratio": 0.04,
             "utilization_pct": 0.8}


class RobustBaseline:
    """EMA mean + EMA of absolute deviation (MAD proxy) -> robust z-score.
    Points with |z| > freeze_z are treated as anomalies and do not update
    the baseline, keeping it clean during attacks."""

    def __init__(self, alpha: float, min_sigma: float = 0.01, freeze_z: float = 8.0) -> None:
        self.alpha = alpha
        self.min_sigma = min_sigma
        self.freeze_z = freeze_z
        self.mean = 0.0
        self.mad = 0.0
        self.n = 0

    def update(self, x: float) -> None:
        if self.n > 3 and abs(self.z(x)) > self.freeze_z:
            return
        if self.n == 0:
            self.mean = x
            self.mad = abs(x) * 0.05 + 1e-6
        else:
            dev = abs(x - self.mean)
            a = self.alpha
            self.mad = (1 - a) * self.mad + a * dev
            self.mean = (1 - a) * self.mean + a * x
        self.n += 1

    def z(self, x: float) -> float:
        sigma = max(1.4826 * self.mad + 1e-3 * (abs(self.mean) + 1.0), self.min_sigma)
        return (x - self.mean) / sigma


class SeasonalBaseline:
    """Per-hour-of-day robust baselines with a global fallback until a bin
    has enough samples. Handles the diurnal traffic cycle without alerting
    on the morning ramp."""

    BINS = 24

    def __init__(self, alpha: float, min_sigma: float = 0.01) -> None:
        self.global_bl = RobustBaseline(alpha, min_sigma)
        self.bins = [RobustBaseline(min(0.5, alpha * 4.0), min_sigma)
                     for _ in range(self.BINS)]

    def update(self, x: float, hour: float) -> None:
        self.global_bl.update(x)
        self.bins[int(hour) % self.BINS].update(x)

    def z(self, x: float, hour: float) -> float:
        b = self.bins[int(hour) % self.BINS]
        if b.n >= 5 and self._bin_consistent(b):
            return b.z(x)
        return self.global_bl.z(x)

    def _bin_consistent(self, b: "RobustBaseline") -> bool:
        """A bin first observed during an attack learns the attack as normal;
        distrust bins whose mean is wildly inconsistent with the frozen,
        attack-protected global baseline and fall back to the global z."""
        g = self.global_bl
        if g.n < 5:
            return True
        sigma = max(1.4826 * g.mad + 1e-3 * (abs(g.mean) + 1.0), b.min_sigma)
        return abs(b.mean - g.mean) <= 6.0 * sigma


class _ITreeNode:
    __slots__ = ("feature", "split", "left", "right", "size")

    def __init__(self) -> None:
        self.feature = -1
        self.split = 0.0
        self.left: _ITreeNode | None = None
        self.right: _ITreeNode | None = None
        self.size = 0


def _c(n: int) -> float:
    if n <= 1:
        return 1.0
    h = math.log(n - 1) + 0.5772156649
    return 2.0 * h - 2.0 * (n - 1) / n


class IsolationForest:
    """Random partitioning trees in pure numpy."""

    def __init__(self, n_trees: int = 40, sample_size: int = 128, seed: int = 7) -> None:
        self.n_trees = n_trees
        self.sample_size = sample_size
        self.rng = np.random.default_rng(seed)
        self.trees: list[_ITreeNode] = []
        self.trained = False

    def _build(self, X: np.ndarray, depth: int, max_depth: int) -> _ITreeNode:
        node = _ITreeNode()
        node.size = len(X)
        if len(X) <= 1 or depth >= max_depth:
            return node
        ranges = X.max(axis=0) - X.min(axis=0)
        valid = np.where(ranges > 0)[0]
        if len(valid) == 0:
            return node
        f = int(valid[self.rng.integers(0, len(valid))])
        lo, hi = float(X[:, f].min()), float(X[:, f].max())
        node.feature = f
        node.split = float(self.rng.uniform(lo, hi))
        mask = X[:, f] < node.split
        if mask.all() or (~mask).all():
            return node
        node.left = self._build(X[mask], depth + 1, max_depth)
        node.right = self._build(X[~mask], depth + 1, max_depth)
        return node

    def fit(self, X: np.ndarray) -> None:
        if len(X) < 8:
            return
        if len(X) > self.sample_size:
            idx = self.rng.choice(len(X), self.sample_size, replace=False)
            X = X[idx]
        max_depth = int(math.ceil(math.log2(max(2, self.sample_size))))
        self.trees = [self._build(X, 0, max_depth) for _ in range(self.n_trees)]
        self.trained = True

    def _path(self, node: _ITreeNode, x: np.ndarray, depth: int) -> float:
        if node.feature < 0 or node.left is None or node.right is None:
            return depth + _c(node.size)
        nxt = node.left if x[node.feature] < node.split else node.right
        return self._path(nxt, x, depth + 1)

    def score(self, x: np.ndarray) -> float:
        if not self.trained:
            return 0.0
        avg = sum(self._path(t, x, 0) for t in self.trees) / len(self.trees)
        return float(2.0 ** (-avg / _c(self.sample_size)))


class AnomalyDetector:
    def __init__(self, settings: DetectorSettings) -> None:
        self.s = settings
        self.baselines: dict[str, dict[str, SeasonalBaseline]] = {}
        self.iforest = IsolationForest(settings.iforest_trees,
                                       settings.iforest_sample)
        self.if_buffer: deque[np.ndarray] = deque(maxlen=settings.iforest_window)
        self.last_train_tick = 0
        self.scores: dict[str, float] = {}
        self.signals: dict[str, dict[str, Any]] = {}
        self.score_history: dict[str, deque[float]] = {}
        self._streak: dict[str, int] = {}

    def reset(self) -> None:
        self.__init__(self.s)

    def _baseline(self, entity: str, metric: str) -> SeasonalBaseline:
        return self.baselines.setdefault(entity, {}).setdefault(
            metric, SeasonalBaseline(self.s.ema_alpha, MIN_SIGMA.get(metric, 0.01)))

    def update(self, tick: TelemetryTick) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
        warm = tick.tick > self.s.warmup_ticks
        hour = tick.hour_of_day
        scores: dict[str, float] = {}
        signals: dict[str, dict[str, Any]] = {}
        attacking = len(tick.active_attacks) > 0

        for nid, m in tick.nodes.items():
            zmax, zmetric = 0.0, ""
            zvec: list[float] = []
            for metric in NODE_METRICS:
                if metric == "bytes_ratio" and m.throughput_mbps < 0.5:
                    zvec.append(0.0)
                    continue  # ratio is meaningless on idle nodes
                x = float(getattr(m, metric))
                bl = self._baseline(nid, metric)
                z = bl.z(x, hour) if warm else 0.0
                bl.update(x, hour)
                zvec.append(float(min(abs(z), 30.0)))
                if z > zmax:
                    zmax, zmetric = z, metric
            z_score = min(1.2, max(0.0, zmax) / self.s.z_alert)
            vec = np.array(zvec, dtype=float)
            if warm and not attacking and self.s.iforest_enabled:
                self.if_buffer.append(vec)
            if_score = self.iforest.score(vec) if (warm and self.s.iforest_enabled) else 0.0
            if_component = 0.0
            if if_score > self.s.iforest_threshold:
                if_component = min(1.0, 0.55 + (if_score - self.s.iforest_threshold) * 3.0)
            score = float(min(1.0, max(z_score, if_component)))
            scores[nid] = self._gate(nid, score)
            signals[nid] = {
                "entity_kind": "node", "z": round(zmax, 2), "top_metric": zmetric,
                "iforest": round(if_score, 3),
                "metrics": {"throughput_mbps": m.throughput_mbps, "pps": m.pps,
                            "latency_ms": m.latency_ms, "packet_loss_pct": m.packet_loss_pct,
                            "fanout": m.fanout, "bytes_ratio": m.bytes_ratio},
            }

        for lid, m in tick.links.items():
            zmax, zmetric = 0.0, ""
            for metric in LINK_METRICS:
                x = float(getattr(m, metric))
                bl = self._baseline(lid, metric)
                z = bl.z(x, hour) if warm else 0.0
                bl.update(x, hour)
                if z > zmax:
                    zmax, zmetric = z, metric
            score = float(min(1.0, max(0.0, zmax) / self.s.z_alert))
            scores[lid] = self._gate(lid, score)
            signals[lid] = {
                "entity_kind": "link", "z": round(zmax, 2), "top_metric": zmetric,
                "iforest": 0.0,
                "metrics": {"utilization_pct": m.utilization_pct,
                            "throughput_mbps": m.throughput_mbps,
                            "latency_ms": m.latency_ms,
                            "packet_loss_pct": m.packet_loss_pct},
            }

        if (self.s.iforest_enabled and warm and not attacking
                and len(self.if_buffer) >= self.s.iforest_sample
                and (not self.iforest.trained
                     or tick.tick - self.last_train_tick >= self.s.iforest_retrain_ticks)):
            self.iforest.fit(np.stack(list(self.if_buffer)))
            self.last_train_tick = tick.tick

        self.scores = scores
        self.signals = signals
        for eid, v in scores.items():
            self.score_history.setdefault(eid, deque(maxlen=400)).append(v)
        return scores, signals

    def _gate(self, entity: str, raw: float) -> float:
        """Persistence gate: an entity only reports an alert-level score after
        `persistence_ticks` consecutive anomalous ticks, so isolated heavy-tailed
        traffic bursts never raise alerts while persistent attacks always do."""
        need = self.s.persistence_ticks
        if raw < self.s.alert_threshold:
            self._streak[entity] = 0
            return raw
        streak = self._streak.get(entity, 0) + 1
        self._streak[entity] = streak
        if streak >= need:
            return raw
        return min(raw, self.s.warn_threshold * 0.9)
