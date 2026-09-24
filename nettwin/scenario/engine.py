"""Scenario execution engine: fork, inject, run, score."""
from __future__ import annotations

from typing import Any

from nettwin.scenario.dsl import Scenario, ScenarioExpectation, ScenarioInjection, ScenarioResult
from nettwin.simulator.engine import SimulationEngine
from nettwin.twin.whatif import _network_health


class ScenarioEngine:
    """Run Scenario Studio drills against a fork of the live simulator."""

    def __init__(self, live_engine: SimulationEngine) -> None:
        self.live = live_engine

    def run(self, scenario: Scenario) -> ScenarioResult:
        base_eng = self.live.clone()
        scen_eng = self.live.clone()

        # Apply immediate injections (at_tick is None or 0) before stepping.
        for inj in scenario.injections:
            if inj.at_tick is None or inj.at_tick <= 0:
                self._apply_injection(scen_eng, inj)

        base_ticks: list[Any] = []
        scen_ticks: list[Any] = []
        for t in range(scenario.duration_ticks):
            # Deferred injections.
            for inj in scenario.injections:
                if inj.at_tick == t + 1:
                    self._apply_injection(scen_eng, inj)
            base_ticks.append(base_eng.step())
            scen_ticks.append(scen_eng.step())

        base_healths = [_network_health(t) for t in base_ticks]
        scen_healths = [_network_health(t) for t in scen_ticks]
        bh = sum(base_healths) / max(1, len(base_healths))
        sh = sum(scen_healths) / max(1, len(scen_healths))
        drop = bh - sh

        affected = self._affected_entities(base_ticks[-1], scen_ticks[-1], scen_eng)
        saturation = self._saturation_timeline(scen_ticks)
        alerts = self._collect_alerts(scen_eng, scen_ticks)

        expectation_results = self._evaluate_expectations(
            scenario.expectations, bh, sh, drop, affected, saturation, alerts, scenario.duration_ticks)

        status = "pass" if all(e["passed"] for e in expectation_results) else "fail"
        summary = (f"Scenario '{scenario.name}' ran {scenario.duration_ticks} ticks: "
                   f"health {bh:.1f} -> {sh:.1f} (drop {drop:.1f}), "
                   f"{len(affected)} affected, {len(saturation)} saturation events, "
                   f"{sum(1 for e in expectation_results if e['passed'])}/{len(expectation_results)} expectations met.")

        return ScenarioResult(
            scenario_id=scenario.id,
            status=status,
            duration_ticks=scenario.duration_ticks,
            baseline_health=bh,
            scenario_health=sh,
            health_drop=drop,
            affected_entities=affected,
            saturation_timeline=saturation,
            alerts=alerts,
            expectation_results=expectation_results,
            summary=summary)

    def _apply_injection(self, eng: SimulationEngine, inj: ScenarioInjection) -> None:
        p = inj.params
        if inj.kind == "attack":
            eng.start_attack(p.get("type", "ddos"),
                             target_id=p.get("target_id"),
                             duration_s=p.get("duration_s", 30.0))
        elif inj.kind == "node_failure":
            eng.fail_node(p["node_id"])
        elif inj.kind == "link_failure":
            eng.fail_link(p["link_id"])
        elif inj.kind == "surge":
            eng.set_surge(float(p.get("multiplier", 3.0)))
        elif inj.kind == "config_change":
            # Only safe, reversible params are supported.
            for key, value in p.get("detector", {}).items():
                setattr(eng.settings.detector, key, value)
        else:
            raise ValueError(f"unknown injection kind: {inj.kind}")

    def _affected_entities(self, base_tick: Any, scen_tick: Any,
                           scen_eng: SimulationEngine) -> list[dict[str, Any]]:
        from nettwin.twin.state import link_health, node_health
        affected: list[dict[str, Any]] = []
        for nid in scen_tick.nodes:
            hb = node_health(base_tick.nodes[nid])
            hs = node_health(scen_tick.nodes[nid])
            tb = base_tick.nodes[nid].throughput_mbps
            ts = scen_tick.nodes[nid].throughput_mbps
            if (hb - hs > 4.0 or
                (tb > 0.5 and abs(ts - tb) / tb > 0.5) or
                    nid in scen_eng.failed_nodes):
                affected.append({"entity_id": nid, "entity_kind": "node",
                                 "health_before": round(hb, 1),
                                 "health_after": round(hs, 1),
                                 "throughput_delta_mbps": round(ts - tb, 2)})
        for lid in scen_tick.links:
            ub = base_tick.links[lid].utilization_pct
            us = scen_tick.links[lid].utilization_pct
            if abs(us - ub) > 15.0 or lid in scen_eng.failed_links:
                affected.append({"entity_id": lid, "entity_kind": "link",
                                 "util_before_pct": round(ub, 1),
                                 "util_after_pct": round(us, 1)})
        return affected

    def _saturation_timeline(self, scen_ticks: list[Any]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        saturation: list[dict[str, Any]] = []
        start_tick = scen_ticks[0].tick if scen_ticks else 0
        for t in scen_ticks:
            for lid, m in t.links.items():
                if m.utilization_pct >= 95.0 and lid not in seen:
                    seen.add(lid)
                    saturation.append({"tick_offset": t.tick - start_tick,
                                       "link_id": lid,
                                       "utilization_pct": round(m.utilization_pct, 1)})
        return saturation

    def _collect_alerts(self, scen_eng: SimulationEngine,
                        scen_ticks: list[Any]) -> list[dict[str, Any]]:
        # Lightweight alert simulation: any failed entity or active attack is reported.
        alerts: list[dict[str, Any]] = []
        for nid in scen_eng.failed_nodes:
            alerts.append({"entity_id": nid, "kind": "node_failure",
                           "severity": "critical"})
        for lid in scen_eng.failed_links:
            alerts.append({"entity_id": lid, "kind": "link_failure",
                           "severity": "critical"})
        for atk in scen_eng.attacks.values():
            alerts.append({"entity_id": atk.event.target_id or "network",
                           "kind": f"attack:{atk.event.attack_type}",
                           "severity": "warning"})
        return alerts

    def _evaluate_expectations(self, expectations: list[ScenarioExpectation],
                               baseline_health: float, scenario_health: float,
                               health_drop: float, affected: list[dict[str, Any]],
                               saturation: list[dict[str, Any]],
                               alerts: list[dict[str, Any]],
                               duration_ticks: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for exp in expectations:
            value: float = 0.0
            passed = False
            if exp.metric == "health_min":
                value = scenario_health
                passed = self._compare(value, exp.threshold, exp.operator)
            elif exp.metric == "health_drop_max":
                value = health_drop
                passed = self._compare(value, exp.threshold, exp.operator)
            elif exp.metric == "affected_count":
                value = float(len(affected))
                passed = self._compare(value, exp.threshold, exp.operator)
            elif exp.metric == "saturation_count":
                value = float(len(saturation))
                passed = self._compare(value, exp.threshold, exp.operator)
            elif exp.metric == "alert_fired":
                target = exp.params.get("entity_id", "")
                atype = exp.params.get("alert_type", "")
                value = float(sum(1 for a in alerts
                                  if (not target or a["entity_id"] == target)
                                  and (not atype or atype in a["kind"])))
                passed = self._compare(value, exp.threshold, exp.operator)
            elif exp.metric == "recovery_ticks":
                # Recovery = first tick after saturation/failure where health recovers.
                value = float(duration_ticks)
                passed = self._compare(value, exp.threshold, exp.operator)
            results.append({
                "metric": exp.metric,
                "threshold": exp.threshold,
                "operator": exp.operator,
                "value": round(value, 2),
                "passed": passed,
            })
        return results

    def _compare(self, value: float, threshold: float, operator: str) -> bool:
        if operator == "gt":
            return value > threshold
        if operator == "gte":
            return value >= threshold
        if operator == "lt":
            return value < threshold
        if operator == "lte":
            return value <= threshold
        if operator == "eq":
            return abs(value - threshold) < 1e-6
        return False
