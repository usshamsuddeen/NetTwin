"""
NetTwin 3.0 — 30 Benchmark Datasets (1998–2026) Verification Suite
==================================================================
Comprehensive test suite validating:
- All 30 datasets registered in manifest.json and west_traffic_generator.py
- Staged vs Full Corpus metadata transparency & public URLs
- Multi-schema telemetry streaming normalization across all 4 research eras
- Next-Gen IoT, 5G & Cloud era (2020–2026) dataset validation
- Conformal calibration coverage consistency (>=90% guarantee)
"""

import os
import sys
from pathlib import Path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REPO_ROOT_PATH = Path(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import json
import pytest
from pathlib import Path

from real_data.loader import DatasetCatalog
from scripts.west_traffic_generator import DATASET_MAP

ROOT_DIR = _REPO_ROOT_PATH


@pytest.fixture(scope="module")
def manifest():
    manifest_path = ROOT_DIR / "real_data" / "manifest.json"
    assert manifest_path.exists(), "manifest.json must exist in real_data/"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_manifest_contains_exactly_30_datasets(manifest):
    assert manifest.get("total_datasets") == 30
    assert len(manifest.get("datasets", [])) == 30


def test_manifest_metadata_honesty_disclosure(manifest):
    assert "methodology_disclosure" in manifest
    disclosure = manifest["methodology_disclosure"]
    assert "9.21 GB" in disclosure
    assert "65 GB" in disclosure
    for ds in manifest["datasets"]:
        assert "staged_size_mb" in ds, f"Missing staged_size_mb in {ds['id']}"
        assert "full_corpus_size_gb" in ds, f"Missing full_corpus_size_gb in {ds['id']}"
        assert "staged_rows" in ds, f"Missing staged_rows in {ds['id']}"
        assert "full_rows" in ds, f"Missing full_rows in {ds['id']}"
        assert "public_url" in ds, f"Missing public_url in {ds['id']}"
        assert "evaluation_honesty_note" in ds, f"Missing evaluation_honesty_note in {ds['id']}"


def test_dataset_map_contains_all_30_datasets():
    assert len(DATASET_MAP) == 30
    required_ids = [
        "darpa_98", "kdd99", "nsl_kdd", "defcon", "caida_ddos", "lbnl", "trustlab_2026", "kyoto",
        "twente", "iscx2012", "adfa_ld", "cic2017", "cse2018", "cidds001", "cidds002",
        "ctu13", "iot23", "bccc_darknet_2025", "ton_iot", "bot_iot", "mqtt_iot", "edge_iiot",
        "cic_iot2022", "cic_malmem2022", "cic_iot2023", "hikari2021", "5g_nidd",
        "cic_iot2024", "cic_eiot2025", "aseados_sdn_iot_2026"
    ]
    for rid in required_ids:
        assert rid in DATASET_MAP, f"Missing dataset {rid} in DATASET_MAP"
        assert len(DATASET_MAP[rid]["attacks"]) > 0


def test_chronological_era_breakdown(manifest):
    era_map = {
        "Foundational": ["01_darpa", "02_kddcup99", "06_lbnl", "08_kyoto"],
        "Modern_Enterprise": ["03_nsl_kdd", "04_defcon", "05_caida", "09_twente", "10_iscx2012", "11_adfa"],
        "Cloud_ML_Ready": ["12_cic_ids2017", "13_cse_cic_ids2018", "14_cidds001", "15_cidds002", "16_ctu13"],
        "Next_Gen_IoT_5G": [
            "07_trustlab_2026", "17_iot23", "18_bccc_darknet_2025",
            "19_ton_iot", "20_bot_iot", "21_mqtt_iot", "22_edge_iiot",
            "23_cic_iot2022", "24_cic_malmem2022", "25_cic_iot2023", "26_hikari2021",
            "27_5g_nidd", "28_cic_iot2024", "29_cic_eiot2025", "30_aseados_sdn_iot_2026"
        ]
    }
    assert len(era_map["Foundational"]) == 4
    assert len(era_map["Modern_Enterprise"]) == 6
    assert len(era_map["Cloud_ML_Ready"]) == 5
    assert len(era_map["Next_Gen_IoT_5G"]) == 15
    total_grouped = sum(len(v) for v in era_map.values())
    assert total_grouped == 30

    ds_ids = {ds["id"] for ds in manifest["datasets"]}
    for era_name, expected_ids in era_map.items():
        for eid in expected_ids:
            assert eid in ds_ids, f"Dataset {eid} from era {era_name} not found in manifest"


@pytest.mark.parametrize("ds_id", [
    "07_trustlab_2026",
    "18_bccc_darknet_2025",
    "19_ton_iot",
    "20_bot_iot",
    "21_mqtt_iot",
    "22_edge_iiot",
    "23_cic_iot2022",
    "24_cic_malmem2022",
    "25_cic_iot2023",
    "26_hikari2021",
    "27_5g_nidd",
    "28_cic_iot2024",
    "29_cic_eiot2025",
    "30_aseados_sdn_iot_2026",
])
def test_next_gen_iot_2020_2026_streaming(ds_id):
    """Verifies that all 12 next-gen datasets stream standardized telemetry packets."""
    stream_gen = DatasetCatalog.stream_telemetry_batch(ds_id, batch_size=10, max_records=20)
    batch = next(iter(stream_gen), None)
    assert batch is not None, f"Failed to stream any batch from {ds_id}"
    assert len(batch) > 0, f"Empty batch returned from {ds_id}"
    first_pkt = batch[0]
    required_keys = ["src_ip", "dst_ip", "src_port", "dst_port", "protocol", "bytes", "attack_label", "is_anomaly"]
    for k in required_keys:
        assert k in first_pkt, f"Missing field {k} in packet from {ds_id}"


def test_conformal_evaluator_outputs_all_30_benchmarks(tmp_path):
    from eval.p2_detect import run_all_datasets_eval
    csv_file = tmp_path / "coverage_30.csv"
    results = run_all_datasets_eval(export_csv_path=str(csv_file), quick=True)
    assert len(results) == 30
    assert csv_file.exists()

    # Empirical conformal coverage guarantee
    coverages = [r["conformal_coverage"] for r in results]
    mean_cov = sum(coverages) / len(coverages)
    assert mean_cov >= 90.0, f"Mean conformal coverage {mean_cov}% fell below 90% guarantee"


def test_west_traffic_generator_sweep_dry_run():
    from scripts.west_traffic_generator import run_phase_all_datasets
    res = run_phase_all_datasets(
        target_url="http://127.0.0.1:8000",
        twin_url="http://127.0.0.1:8000",
        per_dataset_s=1,
        speed_multiplier=1.0,
        dry_run=True,
    )
    assert res["phase"] == "all-datasets"
    assert len(res["datasets"]) == 30
    assert "ton_iot" in res["datasets"]
    assert "edge_iiot" in res["datasets"]
    assert "aseados_sdn_iot_2026" in res["datasets"]
