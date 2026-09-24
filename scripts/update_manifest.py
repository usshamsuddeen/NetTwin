import json
import os

manifest_path = "real_data/manifest.json"

with open(manifest_path, "r", encoding="utf-8") as f:
    data = json.load(f)

data["total_datasets"] = 18
data["updated_at"] = "2026-09-22T17:10:00Z"
data["note"] = "Expanded to include all open benchmark datasets from the CY0P5 benchmark repository (https://github.com/ctinnil/CY0P5_ML_Datasets)."

# Update 01_darpa local partition
for ds in data["datasets"]:
    if ds["id"] == "01_darpa":
        ds["local_partition"]["local_size_mb"] = 52.20
        ds["local_partition"]["local_file_count"] = 5
        ds["local_partition"]["primary_files"] = [
            "tcpdump_four_hours.gz",
            "Truth_Week_1.llist.tar.gz",
            "DARPA_eval_b.tar.gz"
        ]
    elif ds["id"] == "05_caida":
        ds["local_partition"]["local_size_mb"] = 6.96
        ds["local_partition"]["local_file_count"] = 15
        ds["local_partition"]["primary_files"] = [
            "ddostrace.20070804_134936.pcap.gz",
            "caida_ddos_2007_real_flows.csv",
            "ddostrace.20070804_135936.pcap.gz"
        ]

# New datasets from CY0P5
new_datasets = [
    {
        "id": "14_cidds001",
        "folder": "14_cidds001",
        "dataset_name": "CIDDS-001 (Coburg Intrusion Detection Data Set 001)",
        "developed_by": "Hochschule Coburg (Coburg University of Applied Sciences)",
        "year": 2017,
        "features": 16,
        "attack_types": ["DoS", "PortScan", "PingScan", "BruteForce"],
        "description": "Flow-based intrusion detection dataset captured in an emulated small-business environment containing OpenStack client traffic and external server honeypot traces.",
        "source_url": "https://www.hs-coburg.de/cidds",
        "official_benchmark": {
            "published_raw_size": "402.68 MB (compressed zip) / ~4.0 GB uncompressed CSV",
            "uncompressed_size": "~4.0 GB",
            "official_file_count": 10,
            "structure": "4 weeks internal OpenStack NetFlow traffic + 4 weeks external server honeypot traffic + attack logs",
            "record_scope": "~33,000,000 labeled flow records with 16 attributes"
        },
        "local_partition": {
            "type": "Full Official Archive & Internal Week 1 Flow Partition",
            "local_size_mb": 387.26,
            "local_file_count": 3,
            "primary_files": ["CIDDS-001.zip", "cidds001_internal_week1_flows.csv", "dataset_info.json"]
        }
    },
    {
        "id": "15_cidds002",
        "folder": "15_cidds002",
        "dataset_name": "CIDDS-002 (Coburg Intrusion Detection Data Set 002)",
        "developed_by": "Hochschule Coburg (Coburg University of Applied Sciences)",
        "year": 2017,
        "features": 16,
        "attack_types": ["DoS", "PortScan", "BruteForce"],
        "description": "Follow-up to CIDDS-001 focused on multi-subnet OpenStack environments with authentic client traffic and server logs.",
        "source_url": "https://www.hs-coburg.de/cidds",
        "official_benchmark": {
            "published_raw_size": "214.26 MB (compressed zip) / ~2.0 GB uncompressed CSV",
            "uncompressed_size": "~2.0 GB",
            "official_file_count": 26,
            "structure": "2 weeks multi-subnet OpenStack client NetFlows + attack logs + client configurations",
            "record_scope": "~18,000,000 labeled flow records"
        },
        "local_partition": {
            "type": "Full Official Archive & Week 1 Flow Partition",
            "local_size_mb": 207.59,
            "local_file_count": 3,
            "primary_files": ["CIDDS-002.zip", "cidds002_week1_flows.csv", "dataset_info.json"]
        }
    },
    {
        "id": "16_ctu13",
        "folder": "16_ctu13",
        "dataset_name": "CTU-13 (Scenario 10 - Rbot Botnet)",
        "developed_by": "Czech Technical University (CTU) & Stratosphere Laboratory",
        "year": 2011,
        "features": 15,
        "attack_types": ["Botnet Command and Control", "DDoS", "PortScan", "Fast-flux DNS"],
        "description": "Captured inside the Czech Technical University network, featuring real mixed botnet traffic, normal background traffic, and labeled C&C communication.",
        "source_url": "https://www.stratosphereips.org/datasets-ctu13",
        "official_benchmark": {
            "published_raw_size": "~1.99 GB (full dataset archive) / 512.95 MB for Scenario 10",
            "uncompressed_size": "~10.0 GB",
            "official_file_count": 13,
            "structure": "13 real botnet attack scenarios (Neris, Rbot, Virut, Menti, Sogou, Murlo)",
            "record_scope": "Millions of labeled NetFlows across 13 diverse botnet families"
        },
        "local_partition": {
            "type": "Official Scenario 10 Labeled NetFlow Benchmark",
            "local_size_mb": 491.51,
            "local_file_count": 3,
            "primary_files": ["CTU-13-Scenario-10-Rbot.netflow.labeled", "ctu13_scenario10_flows.csv", "dataset_info.json"]
        }
    },
    {
        "id": "17_iot23",
        "folder": "17_iot23",
        "dataset_name": "Aposemat IoT-23 (Scenario 1 - IoT Malware)",
        "developed_by": "Stratosphere Laboratory & Avast Software",
        "year": 2020,
        "features": "Raw Ethernet PCAP & Bro/Zeek conn.log",
        "attack_types": ["IoT Malware", "SYN Scan", "UDP Flood", "C&C Communication"],
        "description": "Dataset of network traffic from Internet of Things (IoT) devices infected with real malware specimens (Mirai, Torii, Gagfyt, Kenjiro).",
        "source_url": "https://www.stratosphereips.org/datasets-iot23",
        "official_benchmark": {
            "published_raw_size": "~21.0 GB compressed archives / 145.92 MB for Scenario 1",
            "uncompressed_size": "~50.0 GB",
            "official_file_count": 23,
            "structure": "23 individual IoT malware captures (20 malware + 3 benign)",
            "record_scope": "Hundreds of millions of IoT network packets and connections"
        },
        "local_partition": {
            "type": "Official Scenario 1 PCAP Benchmark (100% Complete)",
            "local_size_mb": 139.17,
            "local_file_count": 2,
            "primary_files": ["CTU-IoT-Malware-Capture-1-1.pcap", "dataset_info.json"]
        }
    },
    {
        "id": "18_hornet",
        "folder": "18_hornet",
        "dataset_name": "Hornet Honeypot Dataset",
        "developed_by": "Stratosphere Laboratory",
        "year": 2020,
        "features": 10,
        "attack_types": ["Brute Force", "PortScan", "Probe", "Malware Infiltration"],
        "description": "Geographically distributed network of honeypots deployed across cloud providers in multiple continents.",
        "source_url": "https://www.stratosphereips.org/hornet-network-dataset-of-geographically-placed-honeypots",
        "official_benchmark": {
            "published_raw_size": "Variable per honeypot node (~500 MB - 5 GB)",
            "uncompressed_size": "~15.0 GB",
            "official_file_count": 40,
            "structure": "Multi-honeypot traffic streams (Hornet 7, Hornet 15, Hornet 40)",
            "record_scope": "Global honeypot attack interactions from thousands of malicious IP ranges"
        },
        "local_partition": {
            "type": "Hornet 65-Niner Global Summary Matrix",
            "local_size_mb": 0.01,
            "local_file_count": 2,
            "primary_files": ["Hornet65niner-Dataset-Summary-Table.csv", "dataset_info.json"]
        }
    }
]

existing_ids = {ds["id"] for ds in data["datasets"]}
for nd in new_datasets:
    if nd["id"] not in existing_ids:
        data["datasets"].append(nd)

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print(f"Updated manifest.json: now has {len(data['datasets'])} datasets.")
