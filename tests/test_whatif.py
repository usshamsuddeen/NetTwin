"""What-if sandbox tests."""
import pytest

from nettwin.config import Settings
from nettwin.simulator.engine import SimulationEngine
from nettwin.twin.whatif import _network_health, run_whatif


def _engine(ticks: int = 20) -> SimulationEngine:
    eng = SimulationEngine(Settings())
    for _ in range(ticks):
        eng.step()
    return eng


def test_link_failure_report():
    res = run_whatif(_engine(),
                     {"kind": "link_failure", "params": {"link_id": "core1-dist1"}},
                     horizon_ticks=25)
    assert res.horizon_ticks == 25
    assert res.baseline_network_health > 50
    affected_ids = {a["entity_id"] for a in res.affected_entities}
    assert "core1-dist1" in affected_ids
    assert res.summary


def test_node_failure_disconnects_downstream():
    res = run_whatif(_engine(),
                     {"kind": "node_failure", "params": {"node_id": "dist1"}},
                     horizon_ticks=25)
    assert res.projected_health_drop > 1.0
    kinds = {a["entity_kind"] for a in res.affected_entities}
    assert "node" in kinds


def test_surge_and_attack_scenarios():
    surge = run_whatif(_engine(), {"kind": "surge", "params": {"multiplier": 6.0}},
                       horizon_ticks=25)
    assert surge.scenario_network_health <= surge.baseline_network_health + 0.01
    attack = run_whatif(_engine(),
                        {"kind": "attack", "params": {"type": "ddos", "target_id": "web1"}},
                        horizon_ticks=25)
    assert attack.saturation_timeline, "expected saturation under ddos"
    assert attack.projected_health_drop > 0.5


def test_unknown_scenario_rejected():
    with pytest.raises(ValueError):
        run_whatif(_engine(0), {"kind": "bogus", "params": {}}, horizon_ticks=10)


def test_baseline_matches_live_rollout():
    """A no-op what-if baseline from a live-state fork should match the live engine's
    own next N ticks (deterministic, no new external inputs)."""
    eng = SimulationEngine(Settings())
    for _ in range(20):
        eng.step()
    snap = eng.snapshot()

    live = SimulationEngine.restore(snap)
    fork = SimulationEngine.restore(snap)
    res = run_whatif(fork, {"kind": "surge", "params": {"multiplier": 1.0}},
                     horizon_ticks=15)

    live_healths = [_network_health(live.step()) for _ in range(15)]
    live_avg = sum(live_healths) / len(live_healths)
    assert abs(res.baseline_network_health - live_avg) < 0.01
    assert abs(res.scenario_network_health - live_avg) < 0.01
