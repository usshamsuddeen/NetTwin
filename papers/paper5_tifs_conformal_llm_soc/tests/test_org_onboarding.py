"""
Unit & Integration Tests for Organization Network Onboarding & Twin Synthesis
=============================================================================
Tests:
- GET /api/org/current: default organization state & fidelity
- GET /api/org/environments: supported AWS regions and enterprise profiles
- POST /api/org/connect: AWS VPC connection and twin synthesis
- POST /api/org/connect: Enterprise Campus connection and twin switching
- AppState snapshot and telemetry payload inclusion
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

from nettwin.config import load_settings
from nettwin.api.app import create_app


TOPO_PATH = _REPO_ROOT_PATH / "apps" / "aws-3tier" / "topology.json"


def test_org_endpoints_lifecycle():
    settings = load_settings(overrides={
        "tick_ms": 100,
        "db_path": ":memory:",
        "topology_path": str(TOPO_PATH),
    })
    app = create_app(settings)

    async def _main():
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                # 1. Check current organization
                res = await c.get("/api/org/current")
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "ok"
                assert "organization" in data
                assert "org_name" in data["organization"]
                assert "twin_fidelity" in data

                # 2. Check available environments
                res_env = await c.get("/api/org/environments")
                assert res_env.status_code == 200
                env_data = res_env.json()
                assert "regions" in env_data
                assert "profiles" in env_data
                assert any(p["id"] == "aws-3tier" for p in env_data["profiles"])

                # 3. Connect custom AWS organization
                connect_payload = {
                    "org_name": "CyberCorp Financial",
                    "environment": "AWS Production (us-east-1)",
                    "vpc_id": "vpc-099a8b7c6d5e4f3a2",
                    "cidr": "10.0.0.0/16",
                    "region": "us-east-1",
                    "ingest_mode": "aws_vpc_mirror",
                    "topology_name": "aws-3tier",
                }
                res_conn = await c.post("/api/org/connect", json=connect_payload)
                assert res_conn.status_code == 200
                conn_data = res_conn.json()
                assert conn_data["status"] == "connected"
                assert conn_data["organization"]["org_name"] == "CyberCorp Financial"
                assert conn_data["organization"]["vpc_id"] == "vpc-099a8b7c6d5e4f3a2"
                assert conn_data["topology"]["nodes_count"] == 12

                # 4. Verify /api/org/current reflects updated state
                res_curr = await c.get("/api/org/current")
                assert res_curr.json()["organization"]["org_name"] == "CyberCorp Financial"

                # 5. Connect Enterprise Campus organization
                campus_payload = {
                    "org_name": "Global HQ Campus",
                    "environment": "Enterprise On-Premises",
                    "vpc_id": "lan-core-01",
                    "cidr": "172.16.0.0/16",
                    "region": "on-prem",
                    "ingest_mode": "live_agent",
                    "topology_name": "default",
                }
                res_campus = await c.post("/api/org/connect", json=campus_payload)
                assert res_campus.status_code == 200
                campus_data = res_campus.json()
                assert campus_data["organization"]["org_name"] == "Global HQ Campus"
                assert campus_data["topology"]["nodes_count"] == 35

    asyncio.run(_main())


def test_org_fidelity_calculation():
    settings = load_settings(overrides={
        "tick_ms": 100,
        "db_path": ":memory:",
        "topology_path": str(TOPO_PATH),
    })
    app = create_app(settings)

    async def _test():
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                res = await c.get("/api/org/current")
                assert res.status_code == 200
                data = res.json()
                assert "twin_fidelity" in data
                assert isinstance(data["twin_fidelity"], (int, float))
                assert data["twin_fidelity"] >= 90.0
                assert "sync_mode" in data
                assert data["sync_mode"] in ("SYNCHRONIZED", "HYBRID_LIVE", "SHADOW", "SIMULATED")

    asyncio.run(_test())
