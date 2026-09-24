"""Scenario Studio tests."""
import asyncio

from nettwin.config import Settings
from nettwin.scenario import (
    Scenario,
    ScenarioEngine,
    ScenarioExpectation,
    ScenarioInjection,
)
from nettwin.simulator.engine import SimulationEngine


def _run(coro):
    return asyncio.run(coro)


def test_scenario_engine_runs_ddos_and_reports_drop():
    settings = Settings()
    live = SimulationEngine(settings)
    engine = ScenarioEngine(live)
    scenario = Scenario(
        name="DDoS test",
        duration_ticks=20,
        injections=[ScenarioInjection(kind="attack", params={
            "type": "ddos", "target_id": "web1", "duration_s": 15.0})],
        expectations=[ScenarioExpectation(metric="health_drop_max", operator="gt",
                                          threshold=0.0)],
    )
    result = engine.run(scenario)
    assert result.status in ("pass", "fail")
    assert result.health_drop >= 0.0
    assert result.duration_ticks == 20
    assert len(result.saturation_timeline) > 0 or len(result.affected_entities) > 0


def test_scenario_expectation_health_min_lt_fails():
    settings = Settings()
    live = SimulationEngine(settings)
    engine = ScenarioEngine(live)
    scenario = Scenario(
        name="Big DDoS",
        duration_ticks=20,
        injections=[ScenarioInjection(kind="attack", params={
            "type": "ddos", "target_id": "web1", "duration_s": 15.0})],
        expectations=[ScenarioExpectation(metric="health_min", operator="gt",
                                          threshold=100.0)],
    )
    result = engine.run(scenario)
    assert result.status == "fail"


def test_scenario_node_failure_affects_entities():
    settings = Settings()
    live = SimulationEngine(settings)
    engine = ScenarioEngine(live)
    scenario = Scenario(
        name="Core router failure",
        duration_ticks=15,
        injections=[ScenarioInjection(kind="node_failure", params={"node_id": "core1"})],
        expectations=[ScenarioExpectation(metric="affected_count", operator="gt",
                                          threshold=0.0)],
    )
    result = engine.run(scenario)
    assert result.status == "pass"
    assert any(a["entity_id"] == "core1" for a in result.affected_entities)


def test_scenario_api_create_and_run():
    from nettwin.api.app import create_app
    from nettwin.config import load_settings

    settings = load_settings(overrides={
        "tick_ms": 60,
        "db_path": ":memory:",
        "seed": 11,
        "llm": {"provider": "ollama"},
    })
    app = create_app(settings)

    async def _main():
        from httpx import AsyncClient
        from httpx import ASGITransport
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post("/api/scenario/create", json={
                    "name": "API test",
                    "duration_ticks": 10,
                    "injections": [{"kind": "attack",
                                    "params": {"type": "ddos", "target_id": "web1"}}],
                    "expectations": [{"metric": "health_drop_max",
                                      "operator": "gt", "threshold": 0.0}],
                })
                assert r.status_code == 200
                sid = r.json()["id"]
                r = await c.post(f"/api/scenario/{sid}/run")
                assert r.status_code == 200
                body = r.json()
                assert body["scenario_id"] == sid
                assert "health_drop" in body

    _run(_main())


def test_studio_static_files_served():
    from nettwin.api.app import create_app
    from nettwin.config import load_settings

    settings = load_settings(overrides={
        "tick_ms": 60, "db_path": ":memory:", "seed": 11,
        "llm": {"provider": "ollama"},
    })
    app = create_app(settings)

    async def _main():
        from httpx import AsyncClient, ASGITransport
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.get("/studio/")
                assert r.status_code == 200
                assert "NetTwin Scenario Studio" in r.text
                r = await c.get("/studio/app.css")
                assert r.status_code == 200
                r = await c.get("/studio/app.js")
                assert r.status_code == 200

    _run(_main())
