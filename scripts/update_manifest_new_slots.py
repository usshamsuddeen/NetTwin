import json
from pathlib import Path

manifest_path = Path("d:/AWS Cloud/nettwin-project/real_data/manifest.json")
with open(manifest_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Update dataset list
datasets = data.get("datasets", [])

# 1. Update Slot 07 (index 6)
trustlab_entry = {
    "id": "07_trustlab_2026",
    "folder": "07_trustlab_2026",
    "dataset_name": "TRUSTLab 2026",
    "developed_by": "TRUSTLab, Universidad Politécnica de Cartagena (Villafranca, Tasic, Cano, 2026)",
    "year": 2026,
    "features": 80,
    "doi": "10.3389/fcomp.2026.1803271",
    "source_url": "https://www.frontiersin.org/articles/10.3389/fcomp.2026.1803271",
    "attack_types": [
        "Volumetric Flooding", "Reconnaissance", "Credential Attacks",
        "Application-layer", "DNS Abuse", "MitM", "Evasion", "Tunneling",
        "C2", "TLS Anomalies", "Buffer Overflow", "Slowloris",
        "MQTT Exploits", "ARP Poisoning", "Ransomware", "Benign"
    ],
    "description": "Real-world CICFlowMeter IoT/edge intrusion detection dataset with 4.6 million bi-flows across 15 distinct attack families enforcing single-class session integrity.",
    "official_benchmark": {
        "published_raw_size": "4.6 GB",
        "uncompressed_size": "~12.0 GB",
        "official_file_count": 16,
        "structure": "16 single-class CICFlowMeter CSV files with 80 bi-flow features",
        "record_scope": "4,600,000 bi-flow records with single-class label integrity"
    },
    "local_partition": {
        "type": "Official TRUSTLab 15-Family Stratified Evaluation Partition",
        "local_size_mb": 5.01,
        "local_file_count": 2,
        "primary_files": ["trustlab_flows.csv", "dataset_info.json"],
        "staged_rows": 15000,
        "full_corpus_size_gb": 4.6,
        "public_url": "https://www.frontiersin.org/articles/10.3389/fcomp.2026.1803271",
        "note": "TRUSTLab 15-family single-class session partition; full corpus via Frontiers in Computer Science repository."
    },
    "staged_size_mb": 5.01,
    "full_corpus_size_gb": 4.6,
    "staged_rows": 15000,
    "full_rows": 4600000,
    "public_url": "https://www.frontiersin.org/articles/10.3389/fcomp.2026.1803271",
    "evaluation_honesty_note": "TRUSTLab 15-family single-class session partition; full corpus via Frontiers in Computer Science repository."
}

# 2. Update Slot 18 (index 17)
bccc_darknet_entry = {
    "id": "18_bccc_darknet_2025",
    "folder": "18_bccc_darknet_2025",
    "dataset_name": "BCCC-DarkNet-2025",
    "developed_by": "Behavioral Cybersecurity & Communication Center (BCCC), York University (Arash Habibi Lashkari, 2025)",
    "year": 2025,
    "features": 85,
    "attack_types": [
        "Tor", "VPN", "Non-Tor", "Non-VPN", "Audio-Streaming", "Browsing",
        "Chat", "Email", "File-Transfer", "Video-Streaming", "VOIP", "P2P"
    ],
    "description": "Augmented 2025 darknet and encrypted tunnel flow benchmark capturing anonymized communication protocols, Tor hidden services, and covert channels.",
    "source_url": "https://www.yorku.ca/bccc/datasets/darknet-2025",
    "official_benchmark": {
        "published_raw_size": "2.2 GB",
        "uncompressed_size": "~6.8 GB",
        "official_file_count": 3,
        "structure": "Darknet.CSV and per-activity flow matrices",
        "record_scope": "141,530 darknet and encrypted tunnel flow records"
    },
    "local_partition": {
        "type": "Official BCCC DarkNet Stratified Evaluation Partition",
        "local_size_mb": 7.22,
        "local_file_count": 2,
        "primary_files": ["bccc_darknet_flows.csv", "dataset_info.json"],
        "staged_rows": 15000,
        "full_corpus_size_gb": 2.2,
        "public_url": "https://www.yorku.ca/bccc/datasets/darknet-2025",
        "note": "BCCC DarkNet stratified evaluation partition; full corpus via York University BCCC."
    },
    "staged_size_mb": 7.22,
    "full_corpus_size_gb": 2.2,
    "staged_rows": 15000,
    "full_rows": 141530,
    "public_url": "https://www.yorku.ca/bccc/datasets/darknet-2025",
    "evaluation_honesty_note": "BCCC DarkNet stratified evaluation partition; full corpus via York University BCCC."
}

# 3. Update Slot 30 (index 29)
aseados_entry = {
    "id": "30_aseados_sdn_iot_2026",
    "folder": "30_aseados_sdn_iot_2026",
    "dataset_name": "ASEADOS-SDN-IoT 2026",
    "developed_by": "ASEADOS Lab, University College Dublin (UCD)",
    "year": 2026,
    "features": 83,
    "doi": "10.1016/j.iot.2026.101891",
    "paper_citation": "Yasarathna & Le-Khac, 'ASEADOS-SDN-IoT: A Novel SDN-IoT Network Intrusion Detection Dataset', Internet of Things (2026)",
    "source_url": "https://aseados.ucd.ie/datasets/SDN-IoT/",
    "attack_types": [
        "DoS", "DDoS", "Botnet", "Probe", "Benign"
    ],
    "description": "Comprehensive SDN-IoT intrusion detection dataset capturing synchronized control-plane and data-plane telemetry across physical Raspberry Pi, Echo devices, ONOS controller, and Open vSwitch (OVS).",
    "official_benchmark": {
        "published_raw_size": "1.2 GB",
        "uncompressed_size": "~3.5 GB",
        "official_file_count": 8,
        "structure": "ASEADOS_SDN_IoT.csv and control/data plane PCAP captures",
        "record_scope": "457,044 labeled SDN-IoT network flow instances"
    },
    "local_partition": {
        "type": "Official Stratified Evaluation Partition (100% Authentic)",
        "local_size_mb": 6.23,
        "local_file_count": 2,
        "primary_files": ["aseados_sdn_iot_flows.csv", "dataset_info.json"],
        "staged_rows": 15000,
        "full_corpus_size_gb": 1.2,
        "public_url": "https://aseados.ucd.ie/datasets/SDN-IoT/",
        "note": "Official UCD ASEADOS SDN-IoT evaluation partition; full corpus via UCD portal."
    },
    "staged_size_mb": 6.23,
    "full_corpus_size_gb": 1.2,
    "staged_rows": 15000,
    "full_rows": 457044,
    "public_url": "https://aseados.ucd.ie/datasets/SDN-IoT/",
    "evaluation_honesty_note": "Official UCD ASEADOS SDN-IoT evaluation partition; full corpus via UCD portal."
}

datasets[6] = trustlab_entry
datasets[17] = bccc_darknet_entry
datasets[29] = aseados_entry

data["datasets"] = datasets
data["updated_at"] = "2026-09-23T22:45:00Z"
data["temporal_span"] = "1998-2026 (28 Years Elapsed / 29 Calendar Years Inclusive)"

data["categories"] = {
    "1998-2005_foundational": [
        "01_darpa",
        "02_kddcup99",
        "06_lbnl",
        "08_kyoto"
    ],
    "2007-2013_modern": [
        "03_nsl_kdd",
        "04_defcon",
        "05_caida",
        "09_twente",
        "10_iscx2012",
        "11_adfa"
    ],
    "2017-2019_ml_ready": [
        "12_cic_ids2017",
        "13_cse_cic_ids2018",
        "14_cidds001",
        "15_cidds002",
        "16_ctu13"
    ],
    "2020-2026_iot_5g_cloud_era": [
        "07_trustlab_2026",
        "17_iot23",
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
        "30_aseados_sdn_iot_2026"
    ]
}

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("real_data/manifest.json successfully updated with all 30 datasets!")
