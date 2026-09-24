"""What-if sandbox: fork the live simulator and diff the outcomes."""
from __future__ import annotations

from typing import Any

from nettwin.models import TelemetryTick, WhatIfResult
from nettwin.simulator.engine import SimulationEngine
from nettwin.twin.state import link_health, node_health


def _network_health(tick: TelemetryTick) -> float:
    nh = [node_health(m) for m in tick.nodes.values()]
    lh = [link_health(m) for m in tick.links.values() if m.utilization_pct < 400]
    return 0.7 * (sum(nh) / max(1, len(nh))) + 0.3 * (sum(lh) / max(1, len(lh)))


def run_whatif(engine: SimulationEngine, scenario: dict[str, Any],
               horizon_ticks: int = 30) -> WhatIfResult:
    kind = scenario.get("kind")
    params = scenario.get("params", {}) or {}
    horizon = max(5, min(int(horizon_ticks), 200))

    def apply(eng: SimulationEngine) -> None:
        if kind == "link_failure":
            lid = params.get("link_id", "")
            if lid not in eng.topology.links:
                raise ValueError(f"unknown link: {lid}")
            eng.fail_link(lid)
        elif kind == "node_failure":
            nid = params.get("node_id", "")
            if nid not in eng.topology.nodes:
                raise ValueError(f"unknown node: {nid}")
            eng.fail_node(nid)
        elif kind == "surge":
            eng.set_surge(float(params.get("multiplier", 3.0)))
        elif kind == "attack":
            eng.start_attack(params.get("type", "ddos"),
                             target_id=params.get("target_id"),
                             duration_s=None)
        else:
            raise ValueError(f"unknown scenario kind: {kind}")

    base_eng = engine.clone()
    scen_eng = engine.clone()
    apply(scen_eng)

    base_ticks = [base_eng.step() for _ in range(horizon)]
    scen_ticks = [scen_eng.step() for _ in range(horizon)]

    base_health = [_network_health(t) for t in base_ticks]
    scen_health = [_network_health(t) for t in scen_ticks]
    bh = sum(base_health) / len(base_health)
    sh = sum(scen_health) / len(scen_health)

    affected: list[dict[str, Any]] = []
    last_b, last_s = base_ticks[-1], scen_ticks[-1]
    for nid in last_s.nodes:
        hb = node_health(last_b.nodes[nid])
        hs = node_health(last_s.nodes[nid])
        tb = last_b.nodes[nid].throughput_mbps
        ts = last_s.nodes[nid].throughput_mbps
        if hb - hs > 4.0 or (tb > 0.5 and abs(ts - tb) / tb > 0.5) or nid in scen_eng.failed_nodes:
            affected.append({"entity_id": nid, "entity_kind": "node",
                             "health_before": round(hb, 1), "health_after": round(hs, 1),
                             "throughput_delta_mbps": round(ts - tb, 2)})
    for lid in last_s.links:
        ub = last_b.links[lid].utilization_pct
        us = last_s.links[lid].utilization_pct
        if abs(us - ub) > 15.0 or lid in scen_eng.failed_links:
            affected.append({"entity_id": lid, "entity_kind": "link",
                             "util_before_pct": round(ub, 1), "util_after_pct": round(us, 1)})

    saturation: list[dict[str, Any]] = []
    seen_links: set[str] = set()
    for t in scen_ticks:
        for lid, m in t.links.items():
            if m.utilization_pct >= 95.0 and lid not in seen_links:
                seen_links.add(lid)
                saturation.append({"tick_offset": t.tick - scen_ticks[0].tick + 1,
                                   "link_id": lid,
                                   "utilization_pct": round(m.utilization_pct, 1)})

    drop = sum(last_s.nodes[n].packet_loss_pct for n in last_s.nodes) / max(1, len(last_s.nodes))
    dropped_flows = round(drop, 2)

    names = {"link_failure": f"link {params.get('link_id')} failure",
             "node_failure": f"node {params.get('node_id')} failure",
             "surge": f"traffic surge x{params.get('multiplier', 3)}",
             "attack": f"{params.get('type', 'ddos')} attack"}
    summary = (f"Scenario '{names.get(kind, kind)}' over {horizon} ticks: network health "
               f"{bh:.1f} -> {sh:.1f} (drop {bh - sh:.1f}), "
               f"{len(affected)} entities affected, "
               f"{len(saturation)} links reach saturation.")

    return WhatIfResult(
        scenario={"kind": kind, "params": params}, horizon_ticks=horizon,
        affected_entities=affected,
        baseline_network_health=round(bh, 2),
        scenario_network_health=round(sh, 2),
        projected_health_drop=round(bh - sh, 2),
        saturation_timeline=saturation,
        dropped_flows_pct=dropped_flows,
        summary=summary)
