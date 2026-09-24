"""Research observability: fidelity trend, drift, coverage, bandit reward."""
from __future__ import annotations

from collections import deque
from typing import Any


class ResearchMetrics:
    def __init__(self) -> None:
        self.fidelity_trend: deque[float] = deque(maxlen=300)
        self.drift_events: list[dict[str, Any]] = []
        self.coverage_trend: deque[float] = deque(maxlen=300)
        self.agreement: deque[int] = deque(maxlen=300)
        self.reward_trend: deque[float] = deque(maxlen=300)
        self.cumulative_reward = 0.0
        self.detection_latencies: list[int] = []
        self._attack_first_tick: dict[str, int] = {}
        self._alerted_attacks: set[str] = set()

    def note_tick(self, fidelity: float | None, detector_alarm: bool,
                  subspace_alarm: bool, coverage: float | None) -> None:
        if fidelity is not None:
            self.fidelity_trend.append(fidelity)
        self.agreement.append(1 if detector_alarm == subspace_alarm else 0)
        if coverage is not None:
            self.coverage_trend.append(coverage)

    def note_drift(self, event: Any) -> None:
        self.drift_events.append({"tick": event.tick, "metric": event.metric,
                                  "suspected_attack": event.suspected_attack,
                                  "ts": event.ts})

    def note_reward(self, reward: float) -> None:
        self.cumulative_reward = round(self.cumulative_reward + reward, 3)
        self.reward_trend.append(self.cumulative_reward)

    def note_detection(self, attack_id: str, start_tick: int,
                       alert_tick: int | None) -> None:
        self._attack_first_tick.setdefault(attack_id, start_tick)
        if alert_tick is not None and attack_id not in self._alerted_attacks:
            self._alerted_attacks.add(attack_id)
            self.detection_latencies.append(alert_tick - start_tick)
            self.detection_latencies = self.detection_latencies[-100:]

    def snapshot(self) -> dict[str, Any]:
        lat = self.detection_latencies
        return {
            "fidelity_trend": list(self.fidelity_trend)[-120:],
            "fidelity_now": self.fidelity_trend[-1] if self.fidelity_trend else None,
            "drift_events": self.drift_events[-20:],
            "drift_count": len(self.drift_events),
            "coverage_trend": list(self.coverage_trend)[-120:],
            "coverage_now": self.coverage_trend[-1] if self.coverage_trend else None,
            "detector_agreement": (round(sum(self.agreement) / len(self.agreement), 3)
                                   if self.agreement else None),
            "reward_trend": list(self.reward_trend)[-120:],
            "cumulative_reward": self.cumulative_reward,
            "detection_latency_avg_ticks": (round(sum(lat) / len(lat), 2)
                                            if lat else None),
            "detection_latency_max_ticks": max(lat) if lat else None,
        }
