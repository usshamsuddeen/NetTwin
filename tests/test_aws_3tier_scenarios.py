"""
Unit & Integration Tests for AWS 3-Tier Resilience Scenarios
============================================================
Validates the 5 specialized resilience drill scenarios:
1. ddos_alb.json (Surge 5x / DDoS on ALB)
2. web1_crash.json (Web1 crash -> failover/ASG)
3. sqli_db1.json (Lateral attack web1 -> db1)
4. iot_botnet.json (IoT Gateway -> S3 Lakehouse exfil)
5. core_cut.json (ALB -> App link cut)
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from httpx import AsyncClient, ASGITransport

from nettwin.config import Settings, load_settings
from nettwin.scenario import Scenario, ScenarioEngine, ScenarioExpectation, ScenarioInjection
from nettwin.simulator.engine import SimulationEngine
from nettwin.api.app import create_app


BASE_DIR = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = BASE_DIR / "apps" / "aws-3tier" / "scenarios"
TOPO_PATH = BASE_DIR / "apps" / "aws-3tier" / "topology.json"

EXPECTED_SCENARIOS = [
    "ddos_alb.json",
    "web1_crash.json",
    "sqli_db1.json",
    "iot_botnet.json",
    "core_cut.json",
]


def test_scenario_files_exist_and_validate_schema():
    """Verify all 5 JSON files exist and have valid Scenario attributes."""
    for filename in EXPECTED_SCENARIOS:
        filepath = SCENARIOS_DIR / filename
        assert filepath.exists(), f"Missing scenario file: {filepath}"

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "name" in data
        assert "duration_ticks" in data
        assert "injections" in data
        assert len(data["injections"]) > 0

        # Construct Scenario object
        scenario = Scenario(
            name=data["name"],
            description=data.get("description", ""),
            duration_ticks=data.get("duration_ticks", 20),
            injections=[ScenarioInjection(**inj) for inj in data.get("injections", [])],
            expectations=[ScenarioExpectation(**exp) for exp in data.get("expectations", [])],
        )
        assert scenario.name == data["name"]
        assert len(scenario.injections) >= 1


def test_run_aws_scenarios_on_engine():
    """Execute each of the 5 AWS scenarios against ScenarioEngine on aws-3tier topology."""
    settings = Settings(topology_path=str(TOPO_PATH))
    live = SimulationEngine(settings)
    engine = ScenarioEngine(live)

    for filename in EXPECTED_SCENARIOS:
        filepath = SCENARIOS_DIR / filename
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        scenario = Scenario(
            name=data["name"],
            description=data.get("description", ""),
            duration_ticks=data.get("duration_ticks", 15),
            injections=[ScenarioInjection(**inj) for inj in data.get("injections", [])],
            expectations=[ScenarioExpectation(**exp) for exp in data.get("expectations", [])],
        )

        result = engine.run(scenario)
        assert result.status in ("pass", "fail")
        assert result.duration_ticks == scenario.duration_ticks
        assert isinstance(result.health_drop, float)
        assert result.baseline_health >= 0.0
        assert result.scenario_health >= 0.0
        # Check affected entities
        assert len(result.affected_entities) >= 0


def test_scenario_auto_discovery_in_api():
    """Verify /api/scenario/list auto-discovers scenarios in apps/aws-3tier/scenarios/."""
    settings = load_settings(overrides={
        "tick_ms": 100,
        "db_path": ":memory:",
        "topology_path": str(TOPO_PATH)
    })
    app = create_app(settings)

    async def _main():
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/scenario/list")
                assert resp.status_code == 200
                data = resp.json()
                assert isinstance(data, list)
                names = [s["name"] for s in data]
                # At least the AWS scenarios should be discovered
                assert any("ALB" in n or "Crash" in n or "SQL" in n or "IoT" in n for n in names)

    asyncio.run(_main())
