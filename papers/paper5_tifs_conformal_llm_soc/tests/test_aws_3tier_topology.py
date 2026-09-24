"""
Unit & Integration Tests for AWS 3-Tier Cloud Topology
======================================================
Validates loading, graph topology, node count (12 nodes), tier grouping,
simulation engine initialization, dynamic runtime switching, and API routes.
"""
from __future__ import annotations


import os
import sys
from pathlib import Path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REPO_ROOT_PATH = Path(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import asyncio
from pathlib import Path

from httpx import AsyncClient, ASGITransport

from nettwin.config import Settings, load_settings
from nettwin.simulator.topology import Topology
from nettwin.simulator.engine import SimulationEngine
from nettwin.api.app import create_app


TOPO_PATH = _REPO_ROOT_PATH / "apps" / "aws-3tier" / "topology.json"


def test_aws_3tier_topology_file_structure():
    """Verify that apps/aws-3tier/topology.json parses cleanly with 12 nodes and 5 tiers."""
    assert TOPO_PATH.exists(), f"Topology file missing at {TOPO_PATH}"
    topo = Topology.from_json_file(str(TOPO_PATH))

    assert topo.name == "aws-3tier"
    assert "AWS 3-Tier Enterprise Cloud" in topo.title
    assert len(topo.nodes) == 12

    expected_nodes = {
        "igw", "waf", "alb",
        "web1", "web2",
        "app1", "app2",
        "db1", "s3",
        "iot-gw", "iot1", "ws1"
    }
    actual_nodes = set(topo.nodes.keys())
    assert actual_nodes == expected_nodes

    # Check tiers
    tier_names = {t.get("id") for t in topo.tiers}
    assert {"ingress", "web", "app", "data", "edge"}.issubset(tier_names)

    # Check links exist and connect nodes
    assert len(topo.links) >= 12
    for link in topo.links.values():
        assert link.src in actual_nodes
        assert link.dst in actual_nodes


def test_simulation_engine_initializes_with_aws_3tier():
    """Verify SimulationEngine boots directly with aws-3tier topology."""
    settings = Settings(topology_path=str(TOPO_PATH))
    engine = SimulationEngine(settings)

    assert engine.topology.name == "aws-3tier"
    assert len(engine.topology.nodes) == 12
    engine_node_ids = set(engine.topology.nodes.keys())
    assert "alb" in engine_node_ids
    assert "db1" in engine_node_ids

    # Step simulation 3 ticks
    for _ in range(3):
        metrics = engine.step()
        assert metrics is not None
        assert engine.tick > 0
        assert "alb" in metrics.nodes


def test_simulation_engine_switch_topology():
    """Verify runtime switching between campus network and AWS 3-tier cloud."""
    settings = Settings()
    engine = SimulationEngine(settings)
    original_node_count = len(engine.topology.nodes)
    assert original_node_count == 35  # Campus default

    # Switch to AWS 3-Tier
    aws_topo = Topology.from_json_file(str(TOPO_PATH))
    engine.switch_topology(aws_topo)

    assert engine.topology.name == "aws-3tier"
    assert len(engine.topology.nodes) == 12
    new_node_ids = set(engine.topology.nodes.keys())
    assert "alb" in new_node_ids
    assert "core1" not in new_node_ids

    # Step runs clean on new topology
    metrics = engine.step()
    assert "alb" in metrics.nodes


def test_topology_api_list_and_switch():
    """Verify GET /api/topology/list and POST /api/topology/switch routes."""
    settings = load_settings(overrides={
        "tick_ms": 100,
        "db_path": ":memory:",
        "topology_path": str(TOPO_PATH)
    })
    app = create_app(settings)

    async def _main():
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                # 1. List topologies
                resp = await c.get("/api/topology/list")
                assert resp.status_code == 200
                data = resp.json()
                assert isinstance(data, list)
                topos = {t["id"]: t for t in data}
                assert "aws-3tier" in topos
                assert "default" in topos
                assert topos["aws-3tier"]["nodes_count"] == 12

                # 2. Switch to default
                switch_resp = await c.post("/api/topology/switch", json={"topology_id": "default"})
                assert switch_resp.status_code == 200
                sw_data = switch_resp.json()
                assert sw_data["status"] == "ok"
                assert sw_data["topology"]["nodes_count"] == 35

                # 3. Switch back to aws-3tier
                switch_resp2 = await c.post("/api/topology/switch", json={"topology_id": "aws-3tier"})
                assert switch_resp2.status_code == 200
                sw_data2 = switch_resp2.json()
                assert sw_data2["status"] == "ok"
                assert sw_data2["topology"]["nodes_count"] == 12

    asyncio.run(_main())
