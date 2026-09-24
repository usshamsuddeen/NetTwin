"""API tests via httpx ASGI transport with manual lifespan."""
import asyncio

import httpx
import pytest

from nettwin.api.app import create_app
from nettwin.config import load_settings


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def app(tmp_path):
    settings = load_settings(overrides={
        "tick_ms": 60,
        "db_path": str(tmp_path / "test.db"),
        "seed": 11,
        "detector": {"warmup_ticks": 10},
        "snapshot_every_ticks": 5,
        "llm": {"provider": "ollama"},
    })
    return create_app(settings)


async def _client(app):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def test_health_and_topology(app):
    async def main():
        async with app.router.lifespan_context(app):
            async with await _client(app) as client:
                r = await client.get("/api/health")
                assert r.status_code == 200
                body = r.json()
                assert body["status"] == "ok"
                assert body["llm"]["mode"] in ("ollama", "fallback")
                r = await client.get("/api/topology")
                assert r.status_code == 200
                topo = r.json()
                assert len(topo["nodes"]) >= 28
                assert len(topo["links"]) >= 30
                assert all("health" in n for n in topo["nodes"])
                r = await client.get("/")
                assert r.status_code == 200
                assert "NETTWIN" in r.text
    run(main())


def test_attack_lifecycle_and_alerts(app):
    async def main():
        async with app.router.lifespan_context(app):
            async with await _client(app) as client:
                r = await client.post("/api/attacks/start", json={
                    "type": "ddos", "target_id": "web1", "duration_s": 30})
                assert r.status_code == 200
                attack_id = r.json()["id"]
                r = await client.get("/api/attacks")
                assert len(r.json()["active"]) == 1
                # let the engine tick: warmup (10) + detection window
                for _ in range(30):
                    await asyncio.sleep(0.2)
                    r = await client.get("/api/alerts?status=all")
                    if any("web1" in a["entity_id"] or "web1" in a["message"]
                           for a in r.json()):
                        break
                alerts = r.json()
                assert any("web1" in a["entity_id"] or "web1" in a["message"]
                           for a in alerts), f"no web1 alert in {alerts}"
                alert_id = alerts[0]["id"]
                r = await client.post(f"/api/alerts/{alert_id}/ack")
                assert r.status_code == 200
                assert r.json()["status"] == "acknowledged"
                r = await client.post("/api/attacks/stop", json={"attack_id": attack_id})
                assert r.status_code == 200
                assert r.json()["stopped"] == 1
                r = await client.get("/api/attacks")
                assert r.json()["active"] == []
                assert len(r.json()["history"]) >= 1
    run(main())


def test_kpis_metrics_forecast_config_reset(app):
    async def main():
        async with app.router.lifespan_context(app):
            async with await _client(app) as client:
                await asyncio.sleep(1.0)  # ~15 ticks at 60ms
                r = await client.get("/api/kpis")
                assert r.status_code == 200
                assert 0 <= r.json()["network_health"] <= 100
                r = await client.get("/api/metrics?entity=web1&window=20")
                assert r.status_code == 200
                assert len(r.json()["series"]) > 0
                r = await client.get("/api/forecast?entity=network&horizon=10")
                assert r.status_code == 200
                assert len(r.json()["points"]) == 10
                r = await client.post("/api/config", json={"tick_ms": 100, "paused": True})
                assert r.status_code == 200
                assert r.json()["paused"] is True
                tick1 = (await client.get("/api/health")).json()["tick"]
                await asyncio.sleep(0.3)
                tick2 = (await client.get("/api/health")).json()["tick"]
                assert tick1 == tick2
                await client.post("/api/config", json={"paused": False})
                r = await client.post("/api/twin/reset")
                assert r.status_code == 200
                r = await client.post("/api/analyst/ask",
                                      json={"question": "what is happening?"})
                assert r.status_code == 200
                ans = r.json()
                assert ans["mode"] in ("ollama", "fallback")
                assert len(ans["answer"]) > 20
                assert "network_health" in ans["context_used"]
    run(main())
