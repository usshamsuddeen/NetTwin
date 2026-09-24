"""Short-horizon forecasting: damped Holt linear trend per entity/metric."""
from __future__ import annotations

import math

from nettwin.config import ForecastSettings
from nettwin.models import ForecastPoint, ForecastResult, TelemetryTick


class HoltFilter:
    def __init__(self, phi: float = 0.9, alpha: float = 0.35, beta: float = 0.1) -> None:
        self.phi = phi
        self.alpha = alpha
        self.beta = beta
        self.level = 0.0
        self.trend = 0.0
        self.n = 0
        self.resid_var = 1.0

    def update(self, x: float) -> None:
        if self.n == 0:
            self.level, self.trend = x, 0.0
        else:
            resid = x - (self.level + self.phi * self.trend)
            self.resid_var = 0.9 * self.resid_var + 0.1 * resid * resid + 1e-6
            prev = self.level
            self.level = self.alpha * x + (1 - self.alpha) * (self.level + self.phi * self.trend)
            self.trend = self.beta * (self.level - prev) + (1 - self.beta) * self.phi * self.trend
        self.n += 1

    def forecast(self, horizon: int) -> list[tuple[float, float, float]]:
        out = []
        phi_sum = 0.0
        power = self.phi
        sigma = math.sqrt(self.resid_var)
        for h in range(1, horizon + 1):
            phi_sum += power
            power *= self.phi
            mean = self.level + phi_sum * self.trend
            band = 1.96 * sigma * math.sqrt(h)
            out.append((mean, mean - band, mean + band))
        return out


class Predictor:
    def __init__(self, settings: ForecastSettings) -> None:
        self.s = settings
        self.filters: dict[str, HoltFilter] = {}
        self.link_caps: dict[str, float] = {}

    def reset(self) -> None:
        self.filters.clear()

    def _f(self, key: str) -> HoltFilter:
        return self.filters.setdefault(key, HoltFilter(phi=self.s.damping))

    def update(self, tick: TelemetryTick, net_throughput: float, net_latency: float) -> None:
        self._f("network:throughput_mbps").update(net_throughput)
        self._f("network:latency_ms").update(net_latency)
        for nid, m in tick.nodes.items():
            self._f(f"{nid}:throughput_mbps").update(m.throughput_mbps)
            self._f(f"{nid}:latency_ms").update(m.latency_ms)
        for lid, m in tick.links.items():
            self._f(f"{lid}:throughput_mbps").update(m.throughput_mbps)

    def forecast(self, entity_id: str, metric: str = "throughput_mbps",
                 horizon: int | None = None) -> ForecastResult | None:
        h = horizon or self.s.default_horizon
        key = f"{entity_id}:{metric}"
        filt = self.filters.get(key)
        if filt is None or filt.n < 3:
            return None
        pts = [ForecastPoint(step=i + 1, mean=round(max(0.0, mn), 3),
                             lower=round(max(0.0, lo), 3), upper=round(max(0.0, hi), 3))
               for i, (mn, lo, hi) in enumerate(filt.forecast(h))]
        sat = None
        cap = self.link_caps.get(entity_id)
        if cap and metric == "throughput_mbps":
            limit = 0.95 * cap
            for p in pts:
                if p.mean >= limit:
                    sat = p.step
                    break
        return ForecastResult(entity_id=entity_id, metric=metric, horizon=h,
                              points=pts, saturate_in_ticks=sat)

    def saturation_warnings(self) -> list[dict[str, object]]:
        """Links currently loaded that are forecast to saturate soon."""
        out = []
        for lid, cap in self.link_caps.items():
            filt = self.filters.get(f"{lid}:throughput_mbps")
            if filt is None or filt.n < 10:
                continue
            current_pct = 100.0 * filt.level / cap if cap else 0.0
            if current_pct < self.s.saturation_warn_pct:
                continue
            fc = filt.forecast(self.s.saturation_horizon)
            for h, (mean, _, _) in enumerate(fc, start=1):
                if mean >= 0.95 * cap:
                    out.append({"link_id": lid, "ticks_to_saturation": h,
                                "current_util_pct": round(current_pct, 1)})
                    break
        return out
