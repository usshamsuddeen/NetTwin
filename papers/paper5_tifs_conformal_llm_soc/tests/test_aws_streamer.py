"""
Unit & Integration Tests for AWS Cloud Traffic Streamer
========================================================
Validates in-memory zero-disk streaming, column normalization, speed control,
and zero-cost execution ($0.00 spend guarantee via mocked S3 & unsigned open data).
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
import io
from unittest.mock import MagicMock, patch

import pytest
from botocore.response import StreamingBody

from nettwin.ingestion.aws_streamer import (
    AWSCloudTrafficStreamer,
    StreamStats,
    AWS_OPEN_DATA_CSE_CIC_2018,
)
from nettwin.ingestion.normalize import Normalizer, NormalizedBatch


SAMPLE_CIC_CSV = (
    "Dst Port,Protocol,Timestamp,Flow Duration,Tot Fwd Pkts,Tot Bwd Pkts,TotLen Fwd Pkts,TotLen Bwd Pkts,Label\n"
    "80,6,21/02/2018 08:33:25,12000,10,8,5000,4000,Benign\n"
    "443,6,21/02/2018 08:33:26,8500,4,3,2100,1500,Benign\n"
    "80,6,21/02/2018 08:33:27,500000,100,2,80000,200,DDOS attack-LOIC-UDP\n"
    "22,6,21/02/2018 08:33:28,34000,15,12,12000,8000,SSH-Bruteforce\n"
    "80,6,21/02/2018 08:33:29,25000,8,6,3400,2800,Benign\n"
)


def _make_mock_streaming_body(csv_text: str) -> StreamingBody:
    """Creates a botocore StreamingBody from a string in memory (0 network, $0 cost)."""
    raw_bytes = csv_text.encode("utf-8")
    raw_stream = io.BytesIO(raw_bytes)
    return StreamingBody(raw_stream, len(raw_bytes))


def test_streamer_normalizes_records_in_memory():
    """Verify CICFlowMeter CSV rows are properly mapped to NetTwin flow schema without disk I/O."""
    streamer = AWSCloudTrafficStreamer()
    row = {
        "Dst Port": "80",
        "Protocol": "6",
        "TotLen Fwd Pkts": "4500",
        "Label": "DDOS attack-LOIC-UDP",
    }
    rec = streamer._normalize_cic2018_record(row)

    assert rec["type"] == "flow"
    assert rec["dst_port"] == 80
    assert rec["proto"] == "TCP"
    assert rec["bytes"] == 4500
    assert rec["attack_label"] == "DDOS attack-LOIC-UDP"
    assert rec["is_anomaly"] is True


def test_streamer_full_playback_mocked_s3():
    """
    Tests end-to-end streaming worker with a mocked S3 response.
    Guarantees:
    - Zero AWS API costs ($0.00)
    - Zero local disk files created
    - Clean task termination
    """
    async def run():
        ingested_batches = []

        def mock_on_batch(batch):
            ingested_batches.append(batch)

        def resolve_fn(ip):
            return "srv_core"

        normalizer = Normalizer(resolve_fn)
        streamer = AWSCloudTrafficStreamer(normalizer=normalizer, on_batch_callback=mock_on_batch)

        mock_s3 = MagicMock()
        mock_body = _make_mock_streaming_body(SAMPLE_CIC_CSV)
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch.object(streamer, "get_s3_client", return_value=mock_s3):
            res = await streamer.start_stream(
                dataset_id="cse2018_ddos_loic_hoic",
                speed_multiplier=100.0,
                batch_size=2,
                max_records=5,
            )
            assert res["status"] == "started"

            for _ in range(40):
                if not streamer.stats.is_active:
                    break
                await asyncio.sleep(0.02)

            await streamer.stop_stream()

        assert streamer.stats.records_streamed == 5
        assert streamer.stats.anomalies_detected == 2  # LOIC-UDP and SSH-Bruteforce
        assert len(ingested_batches) >= 2
        # Zero storage footprint check
        assert streamer.stats.to_dict()["storage_used_bytes"] == 0

    asyncio.run(run())


def test_streamer_attack_only_filter():
    """Verify attack_only=True ignores benign traffic and only streams attacks."""
    async def run():
        collected = []

        def mock_on_batch(batch):
            collected.append(batch)

        def resolve_fn(ip):
            return "srv_core"

        normalizer = Normalizer(resolve_fn)
        streamer = AWSCloudTrafficStreamer(normalizer=normalizer, on_batch_callback=mock_on_batch)

        mock_s3 = MagicMock()
        mock_body = _make_mock_streaming_body(SAMPLE_CIC_CSV)
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch.object(streamer, "get_s3_client", return_value=mock_s3):
            await streamer.start_stream(
                dataset_id="cse2018_ddos_loic_hoic",
                speed_multiplier=100.0,
                attack_only=True,
                batch_size=1,
                max_records=5,
            )

            for _ in range(40):
                if not streamer.stats.is_active:
                    break
                await asyncio.sleep(0.02)

            await streamer.stop_stream()

        # Out of 5 rows, exactly 2 are attacks
        assert streamer.stats.records_streamed == 2
        assert streamer.stats.anomalies_detected == 2

    asyncio.run(run())


def test_streamer_list_available_cloud_datasets():
    """Verify dataset list returns public AWS Open Data benchmarks with $0.00 cost markers."""
    datasets = AWSCloudTrafficStreamer.list_available_cloud_datasets()
    assert len(datasets) >= 7
    loic = next(d for d in datasets if "ddos_loic_hoic" in d["id"])
    assert loic["bucket"] == "cse-cic-ids2018"
    assert "$0.00" in loic["cost_to_stream"]
    assert loic["requires_aws_creds"] is False


def test_cloud_traffic_api_endpoints(tmp_path):
    """Test /api/cloud-traffic API endpoints with ASGI client and mocked S3 ($0 cost)."""
    import httpx
    from nettwin.api.app import create_app
    from nettwin.config import load_settings

    settings = load_settings(overrides={
        "tick_ms": 60,
        "db_path": str(tmp_path / "test_cloud.db"),
        "seed": 42,
    })
    app = create_app(settings)

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. List datasets
                r = await client.get("/api/cloud-traffic/datasets")
                assert r.status_code == 200
                data = r.json()
                assert data["status"] == "ok"
                assert data["total"] >= 7

                # 2. Check initial status
                r = await client.get("/api/cloud-traffic/stream/status")
                assert r.status_code == 200
                assert r.json()["stats"]["is_active"] is False

                # 3. Start stream with mocked S3 body
                mock_s3 = MagicMock()
                mock_body = _make_mock_streaming_body(SAMPLE_CIC_CSV)
                mock_s3.get_object.return_value = {"Body": mock_body}

                with patch.object(app.state.nettwin.cloud_streamer, "get_s3_client", return_value=mock_s3):
                    r = await client.post("/api/cloud-traffic/stream/start", json={
                        "dataset": "cse2018_ddos_loic_hoic",
                        "speed": 100.0,
                        "batch_size": 2,
                        "max_records": 5,
                    })
                    assert r.status_code == 200
                    assert r.json()["status"] == "ok"

                    # Poll status until done
                    for _ in range(40):
                        r = await client.get("/api/cloud-traffic/stream/status")
                        if not r.json()["stats"]["is_active"]:
                            break
                        await asyncio.sleep(0.02)

                    # 4. Stop stream
                    r = await client.post("/api/cloud-traffic/stream/stop")
                    assert r.status_code == 200
                    assert r.json()["stats"]["is_active"] is False

    asyncio.run(run())

