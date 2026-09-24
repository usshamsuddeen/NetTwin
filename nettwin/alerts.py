"""AlertManager: dedup, severity, lifecycle, persistence, broadcast."""
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from nettwin.config import Settings
from nettwin.models import Alert, TelemetryTick
from nettwin.storage import Storage

_HINTS = {
    ("fanout",): "high connection fanout (scan-like behavior)",
    ("pps",): "abnormal packet rate (flood / brute-force pattern)",
    ("throughput_mbps",): "abnormal throughput volume",
    ("bytes_ratio",): "asymmetric egress volume (possible exfiltration)",
    ("utilization_pct",): "link congestion / saturation",
    ("packet_loss_pct",): "elevated packet loss",
    ("latency_ms",): "elevated latency",
}


def _hint(metric: str) -> str:
    return _HINTS.get((metric,), f"anomalous {metric}")


class AlertManager:
    def __init__(self, settings: Settings, storage: Storage,
                 broadcast: Callable[[dict[str, Any]], Awaitable[None]] | None = None) -> None:
        self.s = settings
        self.storage = storage
        self.broadcast = broadcast
        self.alerts: dict[str, Alert] = {}
        self._by_key: dict[tuple[str, str], str] = {}
        self._clear_streak: dict[str, int] = {}

    async def process(self, tick: TelemetryTick, scores: dict[str, float],
                      signals: dict[str, dict[str, Any]],
                      confidences: dict[str, float] | None = None) -> list[Alert]:
        changed: list[Alert] = []
        warn_th = self.s.detector.warn_threshold
        alert_th = self.s.detector.alert_threshold
        for entity_id, score in scores.items():
            key_active = self._find_active(entity_id)
            conf = (confidences or {}).get(entity_id, -1.0)
            if score >= alert_th:
                sig = signals.get(entity_id, {})
                metric = sig.get("top_metric", "")
                kind = sig.get("entity_kind", "node")
                severity = "critical" if score >= 0.9 else "warning"
                atype = f"anomaly:{metric or 'score'}"
                msg = (f"Anomaly on {entity_id}: {_hint(metric)} "
                       f"(score {score:.2f}, z={sig.get('z', 0):.1f})")
                a = self._find_by_key(entity_id, atype)
                self._clear_streak[entity_id] = 0
                if a and tick.tick - a.tick < self.s.alerts.cooldown_ticks:
                    a.score = max(a.score, score)
                    a.confidence = conf
                    a.tick = tick.tick
                    a.hits += 1
                    a.updated_at = time.time()
                    if a.status == "active":
                        a.severity = severity
                    await self.storage.upsert_alert(a)
                    changed.append(a)
                else:
                    a = Alert(entity_id=entity_id, entity_kind=kind, alert_type=atype,
                              severity=severity, message=msg, score=score,
                              tick=tick.tick, confidence=conf)
                    self._register(a)
                    await self.storage.upsert_alert(a)
                    changed.append(a)
            elif score < warn_th and key_active:
                streak = self._clear_streak.get(entity_id, 0) + 1
                self._clear_streak[entity_id] = streak
                if streak >= self.s.alerts.resolve_after_ticks:
                    a = self.alerts[key_active]
                    a.status = "resolved"
                    a.updated_at = time.time()
                    await self.storage.upsert_alert(a)
                    changed.append(a)
                    self._clear_streak[entity_id] = 0
        if changed and self.broadcast:
            await self.broadcast({"type": "alerts",
                                  "alerts": [a.model_dump() for a in self.active()]})
        return changed

    def raise_predictive(self, link_id: str, ticks_to_sat: int, tick: int) -> Alert | None:
        a = self._find_by_key(link_id, "predictive:saturation")
        if a and a.status == "active":
            return None
        a = Alert(entity_id=link_id, entity_kind="link",
                  alert_type="predictive:saturation", severity="warning",
                  message=(f"Link {link_id} is forecast to saturate in "
                           f"~{ticks_to_sat} ticks"), score=0.6, tick=tick)
        self._register(a)
        return a

    def raise_adhoc(self, entity_id: str, atype: str, message: str,
                    severity: str = "warning", score: float = 0.6,
                    tick: int = 0) -> Alert | None:
        a = self._find_by_key(entity_id, atype)
        if a and a.status == "active":
            return None
        a = Alert(entity_id=entity_id, entity_kind="node", alert_type=atype,
                  severity=severity, message=message, score=score, tick=tick)  # type: ignore[arg-type]
        self._register(a)
        return a

    def _register(self, a: Alert) -> None:
        self.alerts[a.id] = a
        self._by_key[(a.entity_id, a.alert_type)] = a.id

    def _find_by_key(self, entity_id: str, atype: str) -> Alert | None:
        aid = self._by_key.get((entity_id, atype))
        a = self.alerts.get(aid) if aid else None
        if a and a.status == "resolved":
            return None
        return a

    def _find_active(self, entity_id: str) -> str | None:
        for a in self.alerts.values():
            if a.entity_id == entity_id and a.status == "active":
                return a.id
        return None

    def active(self) -> list[Alert]:
        return sorted((a for a in self.alerts.values() if a.status == "active"),
                      key=lambda a: a.updated_at, reverse=True)

    async def load_active(self) -> None:
        rows = await self.storage.list_alerts("active")
        for row in rows:
            a = Alert(**{k: row[k] for k in (
                "id", "entity_id", "entity_kind", "alert_type", "severity", "message",
                "score", "status", "created_at", "updated_at", "tick", "hits",
                "confidence")})
            self._register(a)
        rows = await self.storage.list_alerts("acknowledged")
        for row in rows:
            a = Alert(**{k: row[k] for k in (
                "id", "entity_id", "entity_kind", "alert_type", "severity", "message",
                "score", "status", "created_at", "updated_at", "tick", "hits",
                "confidence")})
            self._register(a)

    async def ack(self, alert_id: str) -> Alert | None:
        a = self.alerts.get(alert_id)
        if not a:
            return None
        a.status = "acknowledged"
        a.updated_at = time.time()
        await self.storage.upsert_alert(a)
        return a

    async def list(self, status: str = "active") -> list[Alert]:
        if status == "all":
            return sorted(self.alerts.values(), key=lambda a: a.updated_at, reverse=True)
        return [a for a in await self._all_cached() if a.status == status]

    async def _all_cached(self) -> list[Alert]:
        return sorted(self.alerts.values(), key=lambda a: a.updated_at, reverse=True)
