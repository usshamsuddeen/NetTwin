"""TwinState: mirrors latest metrics, ring buffers, health rollup."""
from __future__ import annotations

from collections import deque
from typing import Any

from nettwin.config import Settings
from nettwin.models import KPIs, LinkMetrics, NodeMetrics, TelemetryTick


def link_health(m: LinkMetrics) -> float:
    h = 100.0
    h -= max(0.0, m.utilization_pct - 70.0) * 1.1
    h -= m.packet_loss_pct * 4.0
    h -= max(0.0, m.latency_ms - 8.0) * 0.6
    return float(max(0.0, min(100.0, h)))


def node_health(m: NodeMetrics) -> float:
    h = 100.0
    h -= m.packet_loss_pct * 3.5
    h -= max(0.0, m.latency_ms - 12.0) * 1.2
    h -= max(0.0, m.cpu_pct - 85.0) * 1.2
    h -= max(0.0, m.jitter_ms - 6.0) * 1.0
    return float(max(0.0, min(100.0, h)))


class TwinState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        n = settings.history_len
        self.node_history: dict[str, deque[NodeMetrics]] = {}
        self.link_history: dict[str, deque[LinkMetrics]] = {}
        self._hist_len = n
        self.latest: TelemetryTick | None = None
        self.node_health: dict[str, float] = {}
        self.link_health: dict[str, float] = {}
        self.network_health: float = 100.0
        self.net_tp: deque[float] = deque(maxlen=n)
        self.net_lat: deque[float] = deque(maxlen=n)
        self.net_loss: deque[float] = deque(maxlen=n)
        self.kpis = KPIs()

    def reset(self) -> None:
        self.__init__(self.settings)

    def update(self, tick: TelemetryTick) -> None:
        self.latest = tick
        total_tp = 0.0
        for nid, m in tick.nodes.items():
            buf = self.node_history.setdefault(nid, deque(maxlen=self._hist_len))
            buf.append(m)
            self.node_health[nid] = node_health(m)
            total_tp += m.throughput_mbps
        utils, lats, losses = [], [], []
        for lid, m in tick.links.items():
            buf = self.link_history.setdefault(lid, deque(maxlen=self._hist_len))
            buf.append(m)
            self.link_health[lid] = link_health(m)
            if m.utilization_pct < 400:  # skip failed-link sentinel
                utils.append(m.utilization_pct)
                lats.append(m.latency_ms)
                losses.append(m.packet_loss_pct)
        nh = (0.7 * (sum(self.node_health.values()) / max(1, len(self.node_health)))
              + 0.3 * (sum(self.link_health.values()) / max(1, len(self.link_health))))
        self.network_health = round(nh, 2)
        self.net_tp.append(round(total_tp, 2))
        self.net_lat.append(round(sum(lats) / max(1, len(lats)), 3))
        self.net_loss.append(round(sum(losses) / max(1, len(losses)), 3))
        self.kpis = KPIs(
            tick=tick.tick, network_health=self.network_health,
            total_throughput_mbps=round(total_tp, 2),
            total_pps=round(sum(m.pps for m in tick.nodes.values()) / 2.0, 1),
            avg_latency_ms=round(sum(lats) / max(1, len(lats)), 3),
            avg_loss_pct=round(sum(losses) / max(1, len(losses)), 3),
            max_link_util_pct=round(max(utils) if utils else 0.0, 2),
            active_attacks=len(tick.active_attacks))

    def series(self, entity_id: str, window: int = 120) -> list[dict[str, Any]]:
        buf: deque[Any] | None = self.node_history.get(entity_id)
        if buf is None:
            buf = self.link_history.get(entity_id)
        if buf is None:
            return []
        items = list(buf)[-window:]
        return [m.model_dump() for m in items]

    def health_of(self, entity_id: str) -> float | None:
        if entity_id in self.node_health:
            return self.node_health[entity_id]
        return self.link_health.get(entity_id)
