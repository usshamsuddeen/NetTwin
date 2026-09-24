"""SimulationEngine fork/snapshot tests."""
from nettwin.config import Settings
from nettwin.simulator.engine import SimulationEngine


def test_clone_determinism():
    eng = SimulationEngine(Settings())
    for _ in range(15):
        eng.step()
    snap = eng.snapshot()
    a = SimulationEngine.restore(snap)
    b = SimulationEngine.restore(snap)
    for _ in range(20):
        ta = a.step()
        tb = b.step()
    assert ta.tick == tb.tick
    for nid in ta.nodes:
        assert ta.nodes[nid].throughput_mbps == tb.nodes[nid].throughput_mbps
        assert ta.nodes[nid].latency_ms == tb.nodes[nid].latency_ms
    for lid in ta.links:
        assert ta.links[lid].utilization_pct == tb.links[lid].utilization_pct


def test_clone_independence():
    eng = SimulationEngine(Settings())
    for _ in range(15):
        eng.step()

    clone = eng.clone()
    clone.fail_node("dist1")
    clone.apply_policy("isolate", node="ws2")
    clone.start_attack("ddos", target_id="web1", duration_s=None)
    for _ in range(10):
        clone.step()

    # Original engine state must be untouched.
    assert "dist1" not in eng.failed_nodes
    assert "ws2" not in eng.isolated_nodes
    assert "ws2" not in eng.topology.paths.get(("ws1", "web1"), [])
    assert len(eng.attacks) == 0
    assert len(eng.policies) == 0
    assert eng.tick == 15

    # Stepping the original should still see a healthy topology.
    t = eng.step()
    assert "dist1" in t.nodes
    assert t.nodes["dist1"].packet_loss_pct < 50.0


def test_clone_preserves_attacks_and_policies():
    eng = SimulationEngine(Settings())
    for _ in range(10):
        eng.step()
    eng.start_attack("ddos", target_id="web1", duration_s=None)
    eng.apply_policy("rate_limit", src="attacker", bps=5e7)
    eng.fail_link("core1-dist1")

    clone = eng.clone()
    assert len(clone.attacks) == 1
    assert list(clone.attacks.values())[0].event.attack_type == "ddos"
    assert len(clone.policies) == 1
    assert "core1-dist1" in clone.failed_links

    # Clone continues deterministically from the same RNG state.
    t1 = eng.step()
    t2 = clone.step()
    assert t1.tick == t2.tick
    for nid in t1.nodes:
        assert t1.nodes[nid].throughput_mbps == t2.nodes[nid].throughput_mbps


def test_counterfactual_baseline_matches_live():
    """A clone with no new interventions produces the same ticks as the live engine."""
    eng = SimulationEngine(Settings())
    for _ in range(20):
        eng.step()
    clone = eng.clone()
    for _ in range(15):
        t1 = eng.step()
        t2 = clone.step()
        assert t1.tick == t2.tick
        for nid in t1.nodes:
            assert t1.nodes[nid].throughput_mbps == t2.nodes[nid].throughput_mbps
            assert t1.nodes[nid].latency_ms == t2.nodes[nid].latency_ms
