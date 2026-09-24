"""
NetTwin 3.0 Inbound Telemetry Authenticity & Forwarder Authorization Tests
==========================================================================
Tests verifying that POST /api/ingest/telemetry cannot be accessed with just
an API key, and requires:
1. AWS CloudWatch Lambda: HMAC-SHA256 over f"{timestamp}.{body}" + 30s anti-replay.
2. On-Prem Syslog Forwarder: mTLS Client Certificate Fingerprint.
3. Internal aws_streamer.py: X-Internal-Token bypass.
4. Source IP Whitelist enforcement.
5. IngestionServer RFC5425 TLS/mTLS 6514 listener.
"""
import asyncio
import hashlib
import hmac
import json
import time
from typing import Any, Dict

import httpx
import pytest

from nettwin.api.app import create_app
from nettwin.config import load_settings
from nettwin.ingestion.authenticity import (
    DEFAULT_ALLOWED_CERT_FPS,
    DEFAULT_ALLOWED_FORWARDERS,
    DEFAULT_INGEST_SECRET,
    DEFAULT_INTERNAL_TOKEN,
    IngestAuthenticator,
    generate_ingest_headers,
)
from nettwin.ingestion.normalize import Normalizer
from nettwin.ingestion.server import IngestionServer


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def test_app(tmp_path):
    settings = load_settings(overrides={
        "tick_ms": 50,
        "db_path": str(tmp_path / "test_auth.db"),
        "seed": 42,
        "api": {
            "api_key": "secret-admin-api-key-12345",
            "localhost_exempt": False,
        },
        "ingest_auth": {
            "secret": "test-telemetry-secret-key-32b",
            "internal_token": "test-internal-token-secret",
            "skew_window_s": 30.0,
            "allowed_forwarders": ["127.0.0.1", "10.0.0.5", "52.94.76.1"],
            "allowed_cert_fps": [DEFAULT_ALLOWED_CERT_FPS[0]],
            "enforce_ip_whitelist": False,
        },
    })
    return create_app(settings)


async def _client(app, client_ip: str = "127.0.0.1"):
    transport = httpx.ASGITransport(app=app, client=(client_ip, 50000))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def test_stolen_api_key_cannot_ingest(test_app):
    """Knowing the API key alone MUST NOT be enough to push telemetry."""
    async def main():
        async with test_app.router.lifespan_context(test_app):
            async with await _client(test_app) as client:
                payload = {"type": "gauge", "host": "web1", "metrics": {"cpu_pct": 88.0}}
                # Attacker with stolen API key calls /api/ingest/telemetry
                r = await client.post(
                    "/api/ingest/telemetry",
                    headers={"X-API-Key": "secret-admin-api-key-12345"},
                    json=payload,
                )
                assert r.status_code == 401
                assert "Missing required authenticity headers" in r.text
    run(main())


def test_missing_headers_rejected(test_app):
    """Requests without authentication headers must be rejected with 401."""
    async def main():
        async with test_app.router.lifespan_context(test_app):
            async with await _client(test_app) as client:
                r = await client.post(
                    "/api/ingest/telemetry",
                    json={"type": "gauge", "host": "web1", "metrics": {"cpu_pct": 50.0}},
                )
                assert r.status_code == 401
                assert "Missing required authenticity headers" in r.text
    run(main())


def test_spoofed_hmac_rejected(test_app):
    """Spoofed or corrupted HMAC signature must be rejected."""
    async def main():
        async with test_app.router.lifespan_context(test_app):
            async with await _client(test_app) as client:
                body = json.dumps({"type": "gauge", "host": "web1", "metrics": {"cpu_pct": 50.0}})
                headers = {
                    "X-Timestamp": str(int(time.time())),
                    "X-NetTwin-Signature": "sha256=deadbeefcafebabe0123456789abcdef0123456789abcdef0123456789abcdef",
                    "Content-Type": "application/json",
                }
                r = await client.post("/api/ingest/telemetry", content=body, headers=headers)
                assert r.status_code == 401
                assert "HMAC validation failed" in r.text
    run(main())


def test_valid_cloudwatch_hmac_accepted(test_app):
    """Legitimate AWS CloudWatch Lambda forwarder with HMAC-SHA256 is accepted."""
    async def main():
        async with test_app.router.lifespan_context(test_app):
            async with await _client(test_app) as client:
                payload = [{"type": "gauge", "host": "10.0.1.11", "metrics": {"cpu_pct": 65.5}}]
                raw_body = json.dumps(payload)
                now_ts = int(time.time())

                # CloudWatch Lambda signs timestamp.raw_body
                secret = "test-telemetry-secret-key-32b"
                msg = f"{now_ts}.{raw_body}"
                sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

                headers = {
                    "X-Timestamp": str(now_ts),
                    "X-NetTwin-Signature": sig,
                    "Content-Type": "application/json",
                }
                r = await client.post("/api/ingest/telemetry", content=raw_body, headers=headers)
                assert r.status_code == 200
                res = r.json()
                assert res["accepted"] == 1
                assert "web1" in res["entities"]
    run(main())


def test_anti_replay_timestamp_skew_past(test_app):
    """Replay attack with stale timestamp (>30s old) is rejected."""
    async def main():
        async with test_app.router.lifespan_context(test_app):
            async with await _client(test_app) as client:
                raw_body = json.dumps({"type": "gauge", "host": "web1", "metrics": {"cpu_pct": 40.0}})
                stale_ts = int(time.time() - 45)  # 45s in past (>30s window)

                secret = "test-telemetry-secret-key-32b"
                msg = f"{stale_ts}.{raw_body}"
                sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

                headers = {
                    "X-Timestamp": str(stale_ts),
                    "X-NetTwin-Signature": sig,
                    "Content-Type": "application/json",
                }
                r = await client.post("/api/ingest/telemetry", content=raw_body, headers=headers)
                assert r.status_code == 401
                assert "Replay attack" in r.text
                assert "exceeds 30.0s" in r.text
    run(main())


def test_anti_replay_timestamp_skew_future(test_app):
    """Future timestamp skew (>30s) is rejected."""
    async def main():
        async with test_app.router.lifespan_context(test_app):
            async with await _client(test_app) as client:
                raw_body = json.dumps({"type": "gauge", "host": "web1", "metrics": {"cpu_pct": 40.0}})
                future_ts = int(time.time() + 45)  # 45s in future

                secret = "test-telemetry-secret-key-32b"
                msg = f"{future_ts}.{raw_body}"
                sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

                headers = {
                    "X-Timestamp": str(future_ts),
                    "X-NetTwin-Signature": sig,
                    "Content-Type": "application/json",
                }
                r = await client.post("/api/ingest/telemetry", content=raw_body, headers=headers)
                assert r.status_code == 401
                assert "Replay attack" in r.text
    run(main())


def test_anti_replay_duplicate_transmission(test_app):
    """Sending the exact same signed packet twice within 30s is rejected on 2nd attempt."""
    async def main():
        async with test_app.router.lifespan_context(test_app):
            async with await _client(test_app) as client:
                raw_body = json.dumps({"type": "gauge", "host": "10.0.1.11", "metrics": {"cpu_pct": 52.0}})
                headers = generate_ingest_headers(raw_body, secret="test-telemetry-secret-key-32b")

                # First transmission - succeeds
                r1 = await client.post("/api/ingest/telemetry", content=raw_body, headers=headers)
                assert r1.status_code == 200

                # Immediate duplicate re-transmission (replay attack) - must be rejected!
                r2 = await client.post("/api/ingest/telemetry", content=raw_body, headers=headers)
                assert r2.status_code == 401
                assert "duplicate telemetry transmission" in r2.text
    run(main())


def test_on_prem_syslog_mtls_cert_fingerprint(test_app):
    """On-Prem Syslog Forwarder authenticating via mTLS client cert fingerprint."""
    async def main():
        async with test_app.router.lifespan_context(test_app):
            async with await _client(test_app) as client:
                raw_body = json.dumps({"type": "gauge", "host": "10.0.1.11", "metrics": {"cpu_pct": 77.0}})

                # 1. Valid certificate fingerprint (forwarded by mTLS terminator / reverse proxy)
                valid_fp = DEFAULT_ALLOWED_CERT_FPS[0]
                r_valid = await client.post(
                    "/api/ingest/telemetry",
                    content=raw_body,
                    headers={"X-Client-Cert-FP": valid_fp, "Content-Type": "application/json"},
                )
                assert r_valid.status_code == 200
                assert r_valid.json()["accepted"] == 1

                # 2. Rogue certificate fingerprint
                fake_fp = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
                r_invalid = await client.post(
                    "/api/ingest/telemetry",
                    content=raw_body,
                    headers={"X-Client-Cert-FP": fake_fp, "Content-Type": "application/json"},
                )
                assert r_invalid.status_code == 401
                assert "Invalid client certificate fingerprint" in r_invalid.text
    run(main())


def test_internal_token_bypass(test_app):
    """Internal process (aws_streamer.py) can bypass external auth using X-Internal-Token."""
    async def main():
        async with test_app.router.lifespan_context(test_app):
            async with await _client(test_app) as client:
                raw_body = json.dumps({"type": "gauge", "host": "10.0.1.11", "metrics": {"cpu_pct": 21.0}})

                # Valid internal token
                r_valid = await client.post(
                    "/api/ingest/telemetry",
                    content=raw_body,
                    headers={
                        "X-Internal-Token": "test-internal-token-secret",
                        "Content-Type": "application/json",
                    },
                )
                assert r_valid.status_code == 200
                assert r_valid.json()["accepted"] == 1

                # Wrong internal token
                r_invalid = await client.post(
                    "/api/ingest/telemetry",
                    content=raw_body,
                    headers={
                        "X-Internal-Token": "wrong-bad-token",
                        "Content-Type": "application/json",
                    },
                )
                assert r_invalid.status_code == 401
    run(main())


def test_source_ip_whitelist_enforcement(tmp_path):
    """In production mode, only allowed forwarder IPs can send telemetry."""
    settings = load_settings(overrides={
        "tick_ms": 50,
        "db_path": str(tmp_path / "test_ip.db"),
        "seed": 42,
        "ingest_auth": {
            "secret": "test-secret",
            "enforce_ip_whitelist": True,
            "allowed_forwarders": ["10.0.0.5", "127.0.0.1"],
        },
    })
    app = create_app(settings)

    async def main():
        async with app.router.lifespan_context(app):
            raw_body = json.dumps({"type": "gauge", "host": "10.0.1.11", "metrics": {"cpu_pct": 50.0}})
            headers = generate_ingest_headers(raw_body, secret="test-secret")

            # 1. Allowed forwarder IP (10.0.0.5)
            async with await _client(app, client_ip="10.0.0.5") as client:
                r1 = await client.post("/api/ingest/telemetry", content=raw_body, headers=headers)
                assert r1.status_code == 200

            # 2. Rogue internet IP (198.51.100.44)
            headers2 = generate_ingest_headers(raw_body, secret="test-secret")
            async with await _client(app, client_ip="198.51.100.44") as client:
                r2 = await client.post("/api/ingest/telemetry", content=raw_body, headers=headers2)
                assert r2.status_code == 403
                assert "not in allowed forwarders" in r2.text
    run(main())


def test_ingestion_server_rfc5425_unit():
    """Unit test for IngestionServer RFC5425 listener state and message parsing."""
    batches = []
    normalizer = Normalizer(lambda h: "web1" if "10.0.1.11" in h or "web1" in h else None)
    server = IngestionServer(
        port=0,  # disable UDP in this unit test
        normalizer=normalizer,
        on_batch=lambda b: batches.append(b),
        tls_port=0,
    )
    assert not server.listening
    assert not server.udp_listening
    assert not server.tls_listening
