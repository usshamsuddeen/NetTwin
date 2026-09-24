"""API security middleware tests."""
import asyncio

import httpx
import pytest

from nettwin.api.app import create_app
from nettwin.api.security import RateLimitMiddleware
from nettwin.config import load_settings


def run(coro):
    return asyncio.run(coro)


async def _client(app):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture()
def app(tmp_path):
    RateLimitMiddleware.reset()
    settings = load_settings(overrides={
        "tick_ms": 60,
        "db_path": str(tmp_path / "test.db"),
        "seed": 11,
        "detector": {"warmup_ticks": 10},
        "snapshot_every_ticks": 5,
    })
    return create_app(settings)


@pytest.fixture()
def secure_app(tmp_path):
    RateLimitMiddleware.reset()
    settings = load_settings(overrides={
        "tick_ms": 60,
        "db_path": str(tmp_path / "test.db"),
        "seed": 11,
        "detector": {"warmup_ticks": 10},
        "snapshot_every_ticks": 5,
        "api": {
            "api_key": "super-secret-key",
            "localhost_exempt": False,
            "rate_limit_requests_per_minute": 10,
            "rate_limit_mutations_per_minute": 5,
        },
    })
    return create_app(settings)


def test_api_key_required_for_data_endpoints(secure_app):
    async def main():
        async with secure_app.router.lifespan_context(secure_app):
            async with await _client(secure_app) as client:
                # Health/readiness are exempt.
                r = await client.get("/api/health")
                assert r.status_code == 200
                r = await client.get("/api/ready")
                assert r.status_code == 200
                # Data endpoint without key is rejected.
                r = await client.get("/api/topology")
                assert r.status_code == 401
                # Data endpoint with key works.
                r = await client.get("/api/topology",
                                     headers={"X-API-Key": "super-secret-key"})
                assert r.status_code == 200
                assert "nodes" in r.json()
    run(main())


def test_api_key_required_for_mutations(secure_app):
    async def main():
        async with secure_app.router.lifespan_context(secure_app):
            async with await _client(secure_app) as client:
                r = await client.post("/api/attacks/start",
                                      json={"type": "ddos", "target_id": "web1"})
                assert r.status_code == 401
                r = await client.post("/api/attacks/start",
                                      headers={"X-API-Key": "super-secret-key"},
                                      json={"type": "ddos", "target_id": "web1"})
                assert r.status_code == 200
    run(main())


def test_rate_limit_blocks_spam(secure_app):
    async def main():
        async with secure_app.router.lifespan_context(secure_app):
            async with await _client(secure_app) as client:
                headers = {"X-API-Key": "super-secret-key"}
                statuses = []
                for _ in range(20):
                    r = await client.get("/api/topology", headers=headers)
                    statuses.append(r.status_code)
                # Capacity is 10; after that requests are throttled.
                assert 200 in statuses
                assert 429 in statuses
    run(main())


def test_cors_headers_when_configured(tmp_path):
    RateLimitMiddleware.reset()
    settings = load_settings(overrides={
        "tick_ms": 60,
        "db_path": str(tmp_path / "test.db"),
        "api": {"cors_origins": ["http://localhost:3000"]},
    })
    app = create_app(settings)

    async def main():
        async with app.router.lifespan_context(app):
            async with await _client(app) as client:
                r = await client.options("/api/health",
                                         headers={"Origin": "http://localhost:3000",
                                                  "Access-Control-Request-Method": "GET"})
                assert r.status_code == 200
                assert "access-control-allow-origin" in r.headers
    run(main())


def test_no_api_key_by_default(app):
    # The default fixture has no api_key, so all endpoints are open.
    async def main():
        async with app.router.lifespan_context(app):
            async with await _client(app) as client:
                r = await client.get("/api/topology")
                assert r.status_code == 200
    run(main())
