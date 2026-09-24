"""PCA subspace anomaly detection (Lakhina-style) in pure numpy.

Builds a rolling time x entity traffic matrix (link throughput), splits the
feature space into a normal subspace (top-k principal components) and a
residual subspace, and scores each tick by the SPE/Q-statistic (squared
residual norm). Per-column residual decomposition feeds explainability.
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from nettwin.config import SubspaceSettings
from nettwin.models import TelemetryTick


class SubspaceDetector:
    def __init__(self, settings: SubspaceSettings) -> None:
        self.s = settings
        self.window: deque[np.ndarray] = deque(maxlen=settings.window)
        self.columns: list[str] = []
        self.mean = np.zeros(0)
        self.scale = np.ones(0)
        self.components = np.zeros(0)  # k x d
        self.trained = False
        self.last_train_tick = 0
        self.spe_ema = 0.0
        self.spe_var = 1.0
        self.spe_n = 0
        self.last_spe = 0.0
        self.last_score = 0.0
        self.last_column_residuals: dict[str, float] = {}

    def reset(self) -> None:
        self.window.clear()
        self.columns = []
        self.mean = np.zeros(0)
        self.scale = np.ones(0)
        self.components = np.zeros(0)
        self.trained = False
        self.spe_ema = 0.0
        self.spe_var = 1.0
        self.spe_n = 0
        self.last_spe = 0.0
        self.last_score = 0.0
        self.last_column_residuals = {}

    def _row(self, tick: TelemetryTick) -> np.ndarray:
        current_keys = sorted(tick.links.keys())
        if self.columns != current_keys:
            self.columns = current_keys
            self.window.clear()
            self.trained = False
            self.mean = np.zeros(len(self.columns))
            self.scale = np.ones(len(self.columns))
            self.components = np.zeros((0, len(self.columns)))
        return np.array([math.log1p(tick.links[c].throughput_mbps) if c in tick.links else 0.0
                         for c in self.columns], dtype=float)

    def retrain(self) -> bool:
        if len(self.window) < max(30, self.s.n_components * 4):
            return False
        X = np.stack(list(self.window))
        self.mean = X.mean(axis=0)
        self.scale = X.std(axis=0) + 1e-6
        Z = (X - self.mean) / self.scale
        _, _, vt = np.linalg.svd(Z, full_matrices=False)
        k = min(self.s.n_components, vt.shape[0])
        self.components = vt[:k]
        self.trained = True
        return True

    def spe(self, row: np.ndarray) -> tuple[float, np.ndarray]:
        z = (row - self.mean) / self.scale
        proj = self.components @ z
        resid = z - self.components.T @ proj
        return float(resid @ resid), resid

    def update(self, tick: TelemetryTick, attacking: bool) -> float:
        row = self._row(tick)
        warm = tick.tick > self.s.warmup_ticks
        if not attacking:
            self.window.append(row)
        if warm and not attacking and (
                not self.trained
                or tick.tick - self.last_train_tick >= self.s.retrain_ticks):
            if self.retrain():
                self.last_train_tick = tick.tick
        if not self.trained or not warm:
            return 0.0
        spe, resid = self.spe(row)
        self.last_spe = spe
        # calibrated score from benign SPE distribution
        if self.spe_n > 10:
            sigma = math.sqrt(self.spe_var) + 1e-6
            z = (spe - self.spe_ema) / sigma
            score = float(min(1.0, max(0.0, z) / self.s.z_alert))
        else:
            score = 0.0
        if not attacking:
            d = spe - self.spe_ema
            self.spe_ema += 0.05 * d if self.spe_n else 0.0
            if self.spe_n == 0:
                self.spe_ema = spe
            self.spe_var = 0.95 * self.spe_var + 0.05 * d * d
            self.spe_n += 1
        self.last_score = score
        self.last_column_residuals = {
            self.columns[i]: round(float(resid[i] ** 2), 4) for i in range(len(self.columns))}
        return score

    def top_residual_columns(self, n: int = 5) -> list[tuple[str, float]]:
        items = sorted(self.last_column_residuals.items(),
                       key=lambda kv: kv[1], reverse=True)
        return items[:n]
