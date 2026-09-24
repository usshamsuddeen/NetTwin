"""Scenario Studio API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nettwin.api.app import AppState
from nettwin.scenario import Scenario, ScenarioEngine, scenario_from_dict


class ScenarioCreateRequest(BaseModel):
    name: str
    description: str = ""
    duration_ticks: int = 30
    baseline: str = "live"
    injections: list[dict[str, Any]] = []
    expectations: list[dict[str, Any]] = []


class ScenarioRunRequest(BaseModel):
    scenario_id: str | None = None
    scenario: dict[str, Any] | None = None


class DrillRequest(BaseModel):
    scenario_ids: list[str]


def build_scenario_router(state: AppState) -> APIRouter:
    import json
    from pathlib import Path

    router = APIRouter(prefix="/api/scenario")
    engine = ScenarioEngine(state.engine)
    scenarios: dict[str, Scenario] = {}
    results: list[dict[str, Any]] = []

    # Auto-discover specialized scenarios
    for scen_dir in [Path("apps/aws-3tier/scenarios"), Path("scenarios")]:
        if scen_dir.exists():
            for f in scen_dir.glob("*.json"):
                try:
                    with f.open("r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    scen = scenario_from_dict(data)
                    scenarios[scen.id] = scen
                except Exception:
                    pass

    @router.post("/create")
    async def create_scenario(req: ScenarioCreateRequest) -> dict[str, Any]:
        from nettwin.scenario.dsl import ScenarioExpectation, ScenarioInjection
        scenario = Scenario(
            name=req.name,
            description=req.description,
            duration_ticks=req.duration_ticks,
            baseline=req.baseline,
            injections=[ScenarioInjection(
                kind=i.get("kind", ""),
                params=i.get("params", {}),
                at_tick=i.get("at_tick")) for i in req.injections],
            expectations=[ScenarioExpectation(
                metric=e.get("metric", ""),
                threshold=e.get("threshold", 0.0),
                operator=e.get("operator", "gt"),
                params=e.get("params", {})) for e in req.expectations],
        )
        scenarios[scenario.id] = scenario
        return scenario.to_dict()

    @router.get("/list")
    async def list_scenarios() -> list[dict[str, Any]]:
        return [s.to_dict() for s in scenarios.values()]

    @router.get("/{scenario_id}")
    async def get_scenario(scenario_id: str) -> dict[str, Any]:
        s = scenarios.get(scenario_id)
        if not s:
            raise HTTPException(404, "scenario not found")
        return s.to_dict()

    @router.post("/{scenario_id}/run")
    async def run_scenario(scenario_id: str) -> dict[str, Any]:
        s = scenarios.get(scenario_id)
        if not s:
            raise HTTPException(404, "scenario not found")
        try:
            result = await _run_sync(engine, s)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        results.append(result.to_dict())
        return result.to_dict()

    @router.post("/run")
    async def run_inline(req: ScenarioRunRequest) -> dict[str, Any]:
        if req.scenario:
            s = scenario_from_dict(req.scenario)
        elif req.scenario_id and req.scenario_id in scenarios:
            s = scenarios[req.scenario_id]
        else:
            raise HTTPException(400, "provide scenario or scenario_id")
        try:
            result = await _run_sync(engine, s)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        results.append(result.to_dict())
        return result.to_dict()

    @router.get("/results")
    async def list_results(limit: int = 20) -> list[dict[str, Any]]:
        return results[-limit:]

    @router.post("/drill")
    async def run_drill(req: DrillRequest) -> dict[str, Any]:
        out = []
        for sid in req.scenario_ids:
            s = scenarios.get(sid)
            if not s:
                raise HTTPException(404, f"scenario not found: {sid}")
            result = await _run_sync(engine, s)
            out.append(result.to_dict())
            results.append(result.to_dict())
        passed = sum(1 for r in out if r["status"] == "pass")
        return {"scenarios_run": len(out), "passed": passed, "failed": len(out) - passed,
                "results": out}

    @router.get("/drill/scorecard")
    async def scorecard() -> dict[str, Any]:
        if not results:
            return {"total": 0, "pass_rate": 0.0, "by_scenario": {}}
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "pass")
        by_scenario: dict[str, dict[str, Any]] = {}
        for r in results:
            sid = r["scenario_id"]
            entry = by_scenario.setdefault(sid, {"runs": 0, "passed": 0, "failed": 0})
            entry["runs"] += 1
            if r["status"] == "pass":
                entry["passed"] += 1
            else:
                entry["failed"] += 1
        return {"total": total, "pass_rate": round(passed / total, 2),
                "by_scenario": by_scenario}

    return router


async def _run_sync(engine: ScenarioEngine, scenario: Scenario) -> Any:
    import asyncio
    return await asyncio.to_thread(engine.run, scenario)
