"""Concept drift detection (Page-Hinkley, pure numpy) + continual learning."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class DriftEvent:
    tick: int
    metric: str
    statistic: float
    ts: float = field(default_factory=time.time)
    suspected_attack: bool = False


class PageHinkley:
    def __init__(self, delta: float, lam: float) -> None:
        self.delta = delta
        self.lam = lam
        self.mean = 0.0
        self.n = 0
        self.cum = 0.0
        self.min_cum = 0.0

    def update(self, x: float) -> bool:
        self.n += 1
        self.mean += (x - self.mean) / self.n
        self.cum += x - self.mean - self.delta
        self.min_cum = min(self.min_cum, self.cum)
        if self.n > 10 and self.cum - self.min_cum > self.lam:
            self.reset()
            return True
        return False

    def reset(self) -> None:
        self.mean = 0.0
        self.n = 0
        self.cum = 0.0
        self.min_cum = 0.0


class DriftMonitor:
    """Watches key network metrics; on drift (and no concurrent attack
    evidence) triggers retraining of baselines / PCA / isolation forest."""

    def __init__(self, delta: float = 0.02, lam: float = 30.0,
                 cooldown_ticks: int = 100) -> None:
        self.tests = {
            "network_throughput": PageHinkley(delta, lam),
            "network_latency": PageHinkley(delta, lam),
        }
        self.cooldown_ticks = cooldown_ticks
        self.last_drift_tick = -10**9
        self.events: list[DriftEvent] = []
        self.on_drift: Callable[[DriftEvent], None] | None = None

    def update(self, tick: int, network_tp: float, network_lat: float,
               attack_active: bool, detector_alarmed: bool) -> DriftEvent | None:
        values = {"network_throughput": network_tp, "network_latency": network_lat}
        for name, ph in self.tests.items():
            if ph.update(values[name]):
                if tick - self.last_drift_tick < self.cooldown_ticks:
                    continue
                self.last_drift_tick = tick
                event = DriftEvent(tick=tick, metric=name,
                                   statistic=round(ph.lam, 2),
                                   suspected_attack=attack_active or detector_alarmed)
                self.events.append(event)
                self.events = self.events[-100:]
                # legit drift (no attack evidence) -> continual learning
                if not event.suspected_attack and self.on_drift:
                    self.on_drift(event)
                return event
        return None
