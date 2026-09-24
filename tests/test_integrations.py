"""Integration exporter tests."""
import asyncio
import time

import httpx

from nettwin.api.app import create_app
from nettwin.config import load_settings
from nettwin.integrations import SIEMExporter, WebhookNotifier
from nettwin.integrations.prometheus import prometheus_metrics


def _run(coro):
    return asyncio.run(coro)


def test_siem_cef_format():
    alert = {
        "id": "a1", "entity_id": "web1", "entity_kind": "node",
        "alert_type": "anomaly:pps", "severity": "critical",
        "message": "High pps", "created_at": time.time(),
        "status": "active", "score": 0.95,
    }
    cef = SIEMExporter().to_cef(alert)
    assert cef.startswith("CEF:0|NetTwin|NetTwin|2.0.0|")
    assert "severity=10" in cef or "|10|" in cef
    assert "web1" in cef


def test_siem_leef_format():
    alert = {
        "id": "a2", "entity_id": "web1", "entity_kind": "node",
        "alert_type": "anomaly:pps", "severity": "warning",
        "message": "High pps", "created_at": time.time(),
        "status": "active", "score": 0.75,
    }
    leef = SIEMExporter().to_leef(alert)
    assert leef.startswith("LEEF:2.0|NetTwin|NetTwin|2.0.0|")
    assert "alertId=a2" in leef


def test_webhook_signs_payload():
    notifier = WebhookNotifier("http://example.com/hook", secret="shh")
    body = b'{"event":"test","payload":{}}'
    sig1 = notifier._sign(body)
    sig2 = notifier._sign(body)
    assert sig1 == sig2
    assert len(sig1) == 64


def test_prometheus_output_contains_metrics():
    from unittest.mock import MagicMock

    state = MagicMock()
    state.twin.network_health = 88.5
    state.twin.kpis.total_throughput_mbps = 120.0
    state.twin.kpis.avg_latency_ms = 12.0
    state.twin.kpis.avg_loss_pct = 0.05
    state.alerts.active.return_value = []
    state.engine.attacks = {}
    node = MagicMock()
    node.kind = "server"
    state.engine.topology.nodes = {"web1": node}
    state.engine.topology.links = {}
    state.detector.scores = {}
    state.twin.health_of.return_value = 95.0

    text = prometheus_metrics(state)
    assert "nettwin_network_health 88.5" in text
    assert "nettwin_total_throughput_mbps 120.0" in text
    assert "nettwin_entity_health" in text


def test_prom_endpoint_returns_metrics():
    settings = load_settings(overrides={
        "tick_ms": 60, "db_path": ":memory:", "seed": 11,
        "llm": {"provider": "ollama"},
    })
    app = create_app(settings)

    async def _main():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
                r = await c.get("/api/prom")
                assert r.status_code == 200
                assert "nettwin_network_health" in r.text
                assert "nettwin_active_alerts" in r.text

    _run(_main())


def test_siem_export_endpoint():
    settings = load_settings(overrides={
        "tick_ms": 60, "db_path": ":memory:", "seed": 11,
        "llm": {"provider": "ollama"},
    })
    app = create_app(settings)

    async def _main():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post("/api/integrations/siem/export", json={"fmt": "cef"})
                assert r.status_code == 200
                body = r.json()
                assert body["fmt"] == "cef"
                assert "events" in body

    _run(_main())
