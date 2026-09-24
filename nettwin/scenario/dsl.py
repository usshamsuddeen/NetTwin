"""Scenario Studio domain language."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScenarioInjection:
    """An event injected into a forked twin."""

    kind: str  # attack | node_failure | link_failure | config_change | surge
    params: dict[str, Any] = field(default_factory=dict)
    at_tick: int | None = None  # None means immediate (tick 0)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "params": self.params, "at_tick": self.at_tick}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScenarioInjection":
        return cls(kind=d["kind"], params=d.get("params", {}), at_tick=d.get("at_tick"))


@dataclass
class ScenarioExpectation:
    """Assertion evaluated against the forked run."""

    metric: str  # health_min | health_drop_max | alert_fired | recovery_ticks | saturation_count
    threshold: float
    operator: str = "gt"  # gt | lt | gte | lte | eq
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"metric": self.metric, "threshold": self.threshold,
                "operator": self.operator, "params": self.params}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScenarioExpectation":
        return cls(metric=d["metric"], threshold=d["threshold"],
                   operator=d.get("operator", "gt"), params=d.get("params", {}))


@dataclass
class Scenario:
    """A resilience-drill scenario."""

    name: str
    description: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    duration_ticks: int = 30
    baseline: str = "live"
    injections: list[ScenarioInjection] = field(default_factory=list)
    expectations: list[ScenarioExpectation] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "duration_ticks": self.duration_ticks,
            "baseline": self.baseline,
            "injections": [i.to_dict() for i in self.injections],
            "expectations": [e.to_dict() for e in self.expectations],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Scenario":
        return cls(
            id=d.get("id") or uuid.uuid4().hex[:12],
            name=d["name"],
            description=d.get("description", ""),
            duration_ticks=d.get("duration_ticks", 30),
            baseline=d.get("baseline", "live"),
            injections=[ScenarioInjection.from_dict(i) for i in d.get("injections", [])],
            expectations=[ScenarioExpectation.from_dict(e) for e in d.get("expectations", [])],
            created_at=d.get("created_at", time.time()),
        )


@dataclass
class ScenarioResult:
    """Outcome of running a scenario."""

    scenario_id: str
    status: str  # pass | fail | error
    duration_ticks: int
    baseline_health: float
    scenario_health: float
    health_drop: float
    affected_entities: list[dict[str, Any]] = field(default_factory=list)
    saturation_timeline: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    expectation_results: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    ran_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "status": self.status,
            "duration_ticks": self.duration_ticks,
            "baseline_health": round(self.baseline_health, 2),
            "scenario_health": round(self.scenario_health, 2),
            "health_drop": round(self.health_drop, 2),
            "affected_entities": self.affected_entities,
            "saturation_timeline": self.saturation_timeline,
            "alerts": self.alerts,
            "expectation_results": self.expectation_results,
            "summary": self.summary,
            "ran_at": self.ran_at,
        }


def scenario_from_dict(d: dict[str, Any]) -> Scenario:
    return Scenario.from_dict(d)
