"""Tests for Paper 3: IoT & 5G 12-Dataset Integrity and Manifest Verification.

Target Venue: IEEE Internet of Things Journal / ACM IoTDI / NDSS IoT Track
Paper: Edge-IIoTset to CIC IoT 2024: How Well Do Modern IDSes Generalize Across 12 IoT/5G Datasets Spanning 2020-2026?
"""
import os
import sys
import json
import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

MANIFEST_PATH = os.path.join(_REPO_ROOT, 'real_data', 'manifest.json')
REAL_DATA_DIR = os.path.join(_REPO_ROOT, 'real_data')

NEXT_GEN_IDS = [
    '19_ton_iot', '20_bot_iot', '21_mqtt_iot', '22_edge_iiot',
    '23_cic_iot2022', '24_cic_malmem2022', '25_cic_iot2023',
    '26_hikari2021', '27_5g_nidd', '28_cic_iot2024',
    '29_cic_eiot2025', '30_darknet2025'
]

def load_manifest():
    assert os.path.exists(MANIFEST_PATH), f"Manifest file missing: {MANIFEST_PATH}"
    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_all_12_next_gen_datasets_exist():
    """Verify that all 12 next-gen IoT/5G datasets are present in real_data."""
    manifest = load_manifest()
    ds_map = {d['id']: d for d in manifest['datasets']}
    for ds_id in NEXT_GEN_IDS:
        assert ds_id in ds_map, f"Dataset {ds_id} not found in manifest"
        ds_dir = os.path.join(REAL_DATA_DIR, ds_id)
        assert os.path.isdir(ds_dir), f"Directory {ds_dir} does not exist"

def test_12_datasets_chronological_span():
    """Verify all 12 datasets span the 2020-2026 era."""
    manifest = load_manifest()
    ds_map = {d['id']: d for d in manifest['datasets']}
    for ds_id in NEXT_GEN_IDS:
        entry = ds_map[ds_id]
        year = entry['year']
        if isinstance(year, str) and '-' in year:
            year = int(year.split('-')[0])
        else:
            year = int(year)
        assert year >= 2020, f"Dataset {ds_id} year {year} is not in 2020-2026 era"

def test_12_datasets_staged_vs_full_volume_disclosure():
    """Verify reviewer honesty disclosure: ~212 MB staged partitions vs ~35.2 GB full corpus."""
    manifest = load_manifest()
    ds_map = {d['id']: d for d in manifest['datasets']}
    total_staged_mb = 0.0
    total_full_gb = 0.0
    for ds_id in NEXT_GEN_IDS:
        entry = ds_map[ds_id]
        total_staged_mb += float(entry.get('staged_size_mb', entry.get('local_partition', {}).get('local_size_mb', 0)))
        total_full_gb += float(entry.get('full_corpus_size_gb', entry.get('local_partition', {}).get('full_corpus_size_gb', 0)))
    
    # Assert ~212 MB staged and ~35 GB full corpus
    assert 180.0 <= total_staged_mb <= 250.0, f"Staged size {total_staged_mb} MB not in expected range ~212 MB"
    assert 25.0 <= total_full_gb <= 50.0, f"Full corpus {total_full_gb} GB not in expected range ~35 GB"

def test_12_datasets_attack_taxonomy_coverage():
    """Verify coverage of modern attack vectors across IoT and 5G."""
    manifest = load_manifest()
    ds_map = {d['id']: d for d in manifest['datasets']}
    all_attacks = []
    for ds_id in NEXT_GEN_IDS:
        all_attacks.extend(ds_map[ds_id].get('attack_types', []))
    
    text = " ".join(all_attacks).lower()
    assert 'ddos' in text or 'dos' in text, "DDoS/DoS vectors missing"
    assert 'mqtt' in text or 'bruteforce' in text, "MQTT or bruteforce attacks missing"
    assert 'reconnaissance' in text or 'probing' in text or 'scan' in text, "Reconnaissance attacks missing"
