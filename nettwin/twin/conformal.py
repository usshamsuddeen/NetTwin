"""Conformal prediction: calibrated p-values for alerts + forecast intervals."""
from __future__ import annotations

from collections import deque

import numpy as np

from nettwin.config import ConformalSettings


class ConformalCalibrator:
    """Split-conformal over benign nonconformity scores.

    p(x) = fraction of calibration scores >= x  (empirical upper-tail p-value).
    Alerts carry confidence = 1 - p. Predictive intervals use the (1-alpha)
    quantile of absolute forecast residuals, giving ~1-alpha empirical coverage.
    """

    def __init__(self, settings: ConformalSettings) -> None:
        self.s = settings
        self.calibration: deque[float] = deque(maxlen=settings.calibration_size)
        self.residuals: deque[float] = deque(maxlen=settings.calibration_size)
        self.coverage_hits: deque[int] = deque(maxlen=settings.coverage_window)
        self.pending_interval: tuple[float, float] | None = None
        self.alpha_t: float = float(settings.alpha)
        self.aci_enabled: bool = settings.aci_enabled
        self.aci_gamma: float = settings.aci_gamma

    # ---- anomaly score calibration ---------------------------------------
    def calibrate(self, score: float) -> None:
        self.calibration.append(float(score))

    def pvalue(self, score: float) -> float:
        if len(self.calibration) < 30:
            return 0.5  # uncalibrated
        arr = np.fromiter(self.calibration, dtype=float)
        return float((np.sum(arr >= score) + 1.0) / (len(arr) + 1.0))

    def confidence(self, score: float) -> float:
        return round(1.0 - self.pvalue(score), 3)

    def alert_level(self) -> float:
        """Score threshold corresponding to p <= alpha_t."""
        if len(self.calibration) < 30:
            return 1.0
        arr = np.fromiter(self.calibration, dtype=float)
        return float(np.quantile(arr, 1.0 - self.alpha_t))

    # ---- forecast intervals -------------------------------------------------
    def observe_forecast_error(self, error: float) -> None:
        self.residuals.append(abs(float(error)))

    def interval(self, mean: float) -> tuple[float, float]:
        if len(self.residuals) < 20:
            return (max(0.0, mean * 0.7), mean * 1.3 + 1.0)
        arr = np.fromiter(self.residuals, dtype=float)
        q = float(np.quantile(arr, 1.0 - self.alpha_t))
        return (max(0.0, mean - q), mean + q)

    def set_pending_interval(self, lo: float, hi: float) -> None:
        self.pending_interval = (lo, hi)

    def update_aci(self, covered: bool, anomaly_active: bool = False) -> None:
        """Adapt alpha_t using the Gibbs & Candès (2021) online update.

        err_t is the miscoverage indicator: 0 if the true value fell inside
        the previous prediction interval, 1 otherwise.

        Paper 2 (ConformalGuard): the asymmetric clipped step-size γ is frozen
        whenever an anomaly is active, preventing an attack from corrupting the
        calibration target.
        """
        if not self.aci_enabled:
            return
        if self.s.aci_freeze_on_anomaly and anomaly_active:
            return
        err_t = 0.0 if covered else 1.0
        self.alpha_t += self.aci_gamma * (self.s.alpha - err_t)
        self.alpha_t = float(np.clip(self.alpha_t, 0.01, 0.5))

    def check_coverage(self, actual: float, anomaly_active: bool = False) -> None:
        if self.pending_interval is not None:
            lo, hi = self.pending_interval
            covered = lo <= actual <= hi
            self.coverage_hits.append(1 if covered else 0)
            self.update_aci(covered, anomaly_active=anomaly_active)
            self.pending_interval = None

    def realized_coverage(self) -> float | None:
        if len(self.coverage_hits) < 20:
            return None
        return round(sum(self.coverage_hits) / len(self.coverage_hits), 3)
