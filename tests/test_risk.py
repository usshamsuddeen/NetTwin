"""Attack-graph risk tests."""
from nettwin.config import RiskSettings
from nettwin.risk.attack_graph import AttackGraph
from nettwin.simulator.topology import build_topology


def test_risk_propagation_and_crown_jewel():
    topo = build_topology()
    ag = AttackGraph(topo, RiskSettings())
    assert all(0.0 < p <= 1.0 for p in ag.compromise.values())
    db_losses = [v for nid, v in ag.expected_loss.items()
                 if topo.nodes[nid].role == "db"]
    ws_losses = [v for nid, v in ag.expected_loss.items()
                 if topo.nodes[nid].kind == "workstation"]
    assert max(db_losses) > max(ws_losses)
    ranked_ids = [n["entity_id"] for n in ag.snapshot()["nodes"]]
    non_attacker_top = [e for e in ranked_ids if e != "attacker"][:5]
    assert any(topo.nodes[e].role == "db" for e in non_attacker_top), non_attacker_top
    assert 0 < ag.network_risk < 100
    for path in ag.top_paths:
        assert path["path"][0] == "attacker"
        assert topo.nodes[path["path"][-1]].role == "db"
        assert 0 < path["probability"] <= 1.0


def test_seeds_raise_risk():
    topo = build_topology()
    ag = AttackGraph(topo, RiskSettings())
    base = ag.network_risk
    ag.recompute({"web1": 0.95, "attacker": 1.0})
    assert ag.network_risk > base
    assert ag.compromise["web1"] >= 0.9
