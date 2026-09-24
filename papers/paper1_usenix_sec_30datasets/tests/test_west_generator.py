"""
NetTwin 3.0 — West Traffic Generator Test Suite
================================================
Validates:
- HMAC-SHA256 signing and compatibility with IngestAuthenticator
- In-memory dataset record extraction (0 disk footprint)
- Multi-phase execution payloads and parameters
- Cross-region latency calculator statistics
- Anti-replay detection verification
"""

import os
import sys
from pathlib import Path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REPO_ROOT_PATH = Path(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import hashlib
import hmac
import json
import time
import pytest

from scripts.west_traffic_generator import (
    sign_telemetry_batch,
    stream_s3_dataset_records,
    measure_cross_region_latency,
    run_phase_replay,
)
from nettwin.ingestion.authenticity import IngestAuthenticator


def test_hmac_signature_generation_and_verification():
    secret = "nettwin-telemetry-ingest-secret-key-32b"
    body_data = [{"type": "gauge", "host": "web1", "metrics": {"cpu_pct": 55.4}}]
    body_str = json.dumps(body_data)

    headers = sign_telemetry_batch(body_str, secret=secret)

    assert "X-Timestamp" in headers
    assert "X-NetTwin-Signature" in headers
    assert headers["X-Internal-Token"] == "traffic-gen-west"

    # Verify that IngestAuthenticator accepts this exact signature
    auth = IngestAuthenticator(secret=secret, internal_token="traffic-gen-west")
    is_valid, reason = auth.verify(
        headers=headers,
        raw_body=body_str.encode("utf-8"),
        source_ip="127.0.0.1",
    )
    assert is_valid, f"Verification failed: {reason}"


def test_stale_timestamp_rejected_by_anti_replay():
    secret = "nettwin-telemetry-ingest-secret-key-32b"
    body_data = [{"type": "gauge", "host": "web1", "metrics": {"cpu_pct": 99.0}}]
    body_str = json.dumps(body_data)

    # 65 seconds in the past (> 30s tolerance)
    stale_ts = str(int(time.time()) - 65)
    sig = hmac.new(secret.encode(), f"{stale_ts}.{body_str}".encode(), hashlib.sha256).hexdigest()

    headers = {
        "X-Timestamp": stale_ts,
        "X-NetTwin-Signature": sig,
    }

    auth = IngestAuthenticator(secret=secret, internal_token="traffic-gen-west", skew_window_s=30)
    is_valid, reason = auth.verify(
        headers=headers,
        raw_body=body_str.encode("utf-8"),
        source_ip="127.0.0.1",
    )
    assert not is_valid
    assert "skew" in reason.lower() or "timestamp" in reason.lower()


def test_stream_s3_dataset_records_in_memory():
    # In dry/offline mode, returns structured synthetic records matching CSE-CIC-IDS2018 format
    records = stream_s3_dataset_records("Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv", max_records=25)
    assert len(records) > 0
    first = records[0]
    assert "Dst Port" in first or "Protocol" in first or "Label" in first


def test_latency_measurement_calculation():
    # Test against mock responding server or self
    stats = measure_cross_region_latency("http://127.0.0.1:8000/api/health", samples=3)
    assert "min_ms" in stats
    assert "max_ms" in stats
    assert "mean_ms" in stats
    assert stats["min_ms"] >= 0.0


def test_dataset_map_contains_all_benchmarks():
    from scripts.west_traffic_generator import DATASET_MAP
    assert len(DATASET_MAP) == 30
    required_keys = [
        "darpa_98", "kdd99", "nsl_kdd", "defcon", "caida_ddos", "lbnl", "trustlab_2026", "kyoto",
        "twente", "iscx2012", "adfa_ld", "cic2017", "cse2018", "cidds001", "cidds002",
        "ctu13", "iot23", "bccc_darknet_2025", "ton_iot", "bot_iot", "mqtt_iot", "edge_iiot",
        "cic_iot2022", "cic_malmem2022", "cic_iot2023", "hikari2021", "5g_nidd",
        "cic_iot2024", "cic_eiot2025", "aseados_sdn_iot_2026"
    ]
    for k in required_keys:
        assert k in DATASET_MAP, f"Missing benchmark {k} in DATASET_MAP"
        assert "name" in DATASET_MAP[k]
        assert "year" in DATASET_MAP[k]
        assert len(DATASET_MAP[k]["attacks"]) > 0


def test_run_phase_all_datasets_dry_run():
    from scripts.west_traffic_generator import run_phase_all_datasets, DATASET_MAP
    res = run_phase_all_datasets(
        target_url="http://127.0.0.1:8000",
        twin_url="http://127.0.0.1:8000",
        per_dataset_s=1,
        speed_multiplier=1.0,
        dry_run=True,
    )
    assert res["phase"] == "all-datasets"
    assert len(res["datasets"]) == len(DATASET_MAP)
    assert "darpa_98" in res["datasets"]
    assert "cse2018" in res["datasets"]
    assert "cic_iot2023" in res["datasets"]
    for k, d in res["datasets"].items():
        assert d["requests_sent"] > 0
        assert d["successful_alb"] == d["requests_sent"]


def test_p2_detect_eval_all_30_datasets(tmp_path):
    from eval.p2_detect import run_all_datasets_eval
    csv_target = tmp_path / "test_coverage.csv"
    results = run_all_datasets_eval(export_csv_path=str(csv_target), quick=True)
    assert len(results) == 30
    assert csv_target.exists()

    # Verify coverage >= 90% finite-sample guarantee
    for r in results:
        assert r["conformal_coverage"] >= 90.0
        assert r["detection_rate"] >= 85.0

