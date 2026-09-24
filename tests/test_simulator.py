"""Simulator tests: topology sanity, engine metrics, attack effects."""
import math

from nettwin.config import Settings
from nettwin.simulator.engine import SimulationEngine
from nettwin.simulator.topology import build_topology


def test_topology_connected_no_dupes():
    topo = build_topology()
    assert 28 <= len(topo.nodes) <= 40
    assert len(topo.nodes) == len({n.id for n in topo.nodes.values()})
    assert len(topo.links) == len({l.id for l in topo.links.values()})
    assert topo.is_connected()
    kinds = {n.kind for n in topo.nodes.values()}
    for required in ("core_router", "distribution_switch", "edge_switch", "server",
                     "workstation", "iot", "firewall", "internet_gateway", "attacker"):
        assert required in kinds
    # every pair routable in the healthy topology
    for (src, dst), path in topo.paths.items():
        assert path[0] == src and path[-1] == dst


def test_engine_step_produces_finite_metrics():
    eng = SimulationEngine(Settings())
    tick = eng.step()
    assert tick.tick == 1
    assert set(tick.nodes) == set(eng.topology.nodes)
    assert set(tick.links) == set(eng.topology.links)
    for m in tick.nodes.values():
        for v in (m.throughput_mbps, m.pps, m.latency_ms, m.jitter_ms,
                  m.packet_loss_pct, m.cpu_pct, m.mem_pct):
            assert math.isfinite(v), v
        assert 0.0 <= m.packet_loss_pct <= 100.0
        assert 0.0 <= m.cpu_pct <= 100.0
    for m in tick.links.values():
        assert math.isfinite(m.utilization_pct) and m.utilization_pct >= 0.0


def test_ddos_raises_target_throughput():
    eng = SimulationEngine(Settings())
    for _ in range(15):
        t = eng.step()
    benign_rx = t.nodes["web1"].rx_mbps
    eng.start_attack("ddos", target_id="web1", duration_s=None)
    for _ in range(5):
        t = eng.step()
    attack_rx = t.nodes["web1"].rx_mbps
    assert attack_rx > benign_rx * 5
    link_id = "edge3-web1"
    assert t.links[link_id].utilization_pct > 100.0
    assert t.links[link_id].packet_loss_pct > 1.0
    stopped = eng.stop_attack()
    assert stopped == 1
    assert eng.attacks == {}
