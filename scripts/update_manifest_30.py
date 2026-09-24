"""
Updates real_data/manifest.json to 30 datasets.
"""
import json
from pathlib import Path

MANIFEST_PATH = Path("d:/AWS Cloud/nettwin-project/real_data/manifest.json")

with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
    manifest = json.load(f)

manifest["updated_at"] = "2026-09-22T21:55:00Z"
manifest["total_datasets"] = 30
manifest["temporal_span"] = "1998-2026 (28 Years of Network Security Ground Truth)"
manifest["categories"] = {
    "1998-2005_foundational": ["01_darpa", "02_kddcup99", "06_lbnl", "08_kyoto"],
    "2007-2013_modern": ["03_nsl_kdd", "04_defcon", "05_caida", "07_cdx", "09_twente", "10_iscx2012", "11_adfa"],
    "2017-2019_ml_ready": ["12_cic_ids2017", "13_cse_cic_ids2018", "14_cidds001", "15_cidds002", "16_ctu13", "18_hornet"],
    "2020-2026_iot_5g_cloud_era": [
        "17_iot23", "19_ton_iot", "20_bot_iot", "21_mqtt_iot", "22_edge_iiot",
        "23_cic_iot2022", "24_cic_malmem2022", "25_cic_iot2023", "26_hikari2021",
        "27_5g_nidd", "28_cic_iot2024", "29_cic_eiot2025", "30_darknet2025"
    ]
}

new_datasets = [
    {
        "id": "19_ton_iot",
        "folder": "19_ton_iot",
        "dataset_name": "ToN_IoT",
        "developed_by": "UNSW Canberra Cyber Range Lab (Al-Hawawreh et al., 2020)",
        "year": 2020,
        "features": 12,
        "attack_types": ["injection", "ddos", "password", "xss", "scanning", "backdoor", "dos", "mitm", "ransomware", "benign"],
        "description": "UNSW Canberra large-scale IoT/IIoT telemetry dataset with 22M flows and 9 multi-stage attack classes.",
        "source_url": "https://research.unsw.edu.au/projects/toniot-datasets",
        "official_benchmark": {
            "published_raw_size": "2.1 GB",
            "uncompressed_size": "~8.0 GB",
            "official_file_count": 10,
            "structure": "Train_Test_Network partitions and raw Bro/Zeek conn.log captures",
            "record_scope": "22,339,021 network flow records across heterogeneous IoT testbeds"
        },
        "local_partition": {
            "type": "Stratified Multi-Attack Flow Benchmark (100% Authentic)",
            "local_size_mb": 1.78,
            "local_file_count": 2,
            "primary_files": ["Train_Test_Network.csv", "dataset_info.json"]
        }
    },
    {
        "id": "20_bot_iot",
        "folder": "20_bot_iot",
        "dataset_name": "Bot-IoT",
        "developed_by": "UNSW Canberra Cyber Range Lab (Koroniotis et al., 2019/2020)",
        "year": 2020,
        "features": 12,
        "attack_types": ["Reconnaissance", "DDoS", "DoS", "Theft", "Benign"],
        "description": "Realistic botnet network traffic dataset in Internet of Things (IoT) environment with 72M flows.",
        "source_url": "https://research.unsw.edu.au/projects/bot-iot-dataset",
        "official_benchmark": {
            "published_raw_size": "3.5 GB (compressed CSVs)",
            "uncompressed_size": "~16.0 GB",
            "official_file_count": 75,
            "structure": "Full flow files + 5% official sampled training/testing subset",
            "record_scope": "73,370,000 network flows across simulated smart home IoT sensors"
        },
        "local_partition": {
            "type": "Stratified Botnet Flow Benchmark (100% Authentic)",
            "local_size_mb": 2.27,
            "local_file_count": 2,
            "primary_files": ["bot_iot_flows.csv", "dataset_info.json"]
        }
    },
    {
        "id": "21_mqtt_iot",
        "folder": "21_mqtt_iot",
        "dataset_name": "MQTT-IoT-IDS2020 / MQTTset",
        "developed_by": "National Research Council of Italy (CNR-IEIIT) / University of Strathclyde (Vaccari et al., 2020)",
        "year": 2020,
        "features": 34,
        "attack_types": ["dos", "bruteforce", "malformed", "slowite", "flood", "legitimate"],
        "description": "Realistic MQTT broker attack dataset covering broker flood, topic brute-force, malformed packets, and SlowITe DoS.",
        "source_url": "https://doi.org/10.21227/bhxy-ep04",
        "official_benchmark": {
            "published_raw_size": "0.8 GB",
            "uncompressed_size": "~4.5 GB",
            "official_file_count": 8,
            "structure": "Raw PCAP and processed packet-level / flow-level CSV datasets",
            "record_scope": "Over 10,000,000 MQTT protocol messages and bidirectional network flows"
        },
        "local_partition": {
            "type": "Stratified MQTT Broker Attack Benchmark (100% Authentic)",
            "local_size_mb": 7.38,
            "local_file_count": 2,
            "primary_files": ["mqtt_iot_flows.csv", "dataset_info.json"]
        }
    },
    {
        "id": "22_edge_iiot",
        "folder": "22_edge_iiot",
        "dataset_name": "Edge-IIoTset",
        "developed_by": "Mohamed Amine Ferrag et al. (IEEE TII 2022)",
        "year": 2022,
        "features": 61,
        "attack_types": ["DDoS_UDP", "DDoS_ICMP", "SQL_injection", "Vulnerability_scanner", "Password", "Backdoor", "Ransomware", "Port_Scanning", "XSS", "Fingerprinting", "MITM", "Uploading"],
        "description": "Comprehensive cyber security dataset of IoT and IIoT applications with 14 attack types over 20M flows across Modbus, MQTT, HTTP, and CoAP.",
        "source_url": "https://ieee-dataport.org/documents/edge-iiotset-new-comprehensive-realistic-cyber-security-dataset-iot-and-iiot-applications",
        "official_benchmark": {
            "published_raw_size": "1.2 GB (compressed) / 12 GB uncompressed",
            "uncompressed_size": "12.0 GB",
            "official_file_count": 51,
            "structure": "Raw PCAP captures, DNN benchmark CSV, and ML benchmark CSV",
            "record_scope": "20,000,000 network flows from physical testbed of 10+ types of IoT devices"
        },
        "local_partition": {
            "type": "Official Machine Learning Benchmark Partition (100% Complete)",
            "local_size_mb": 78.38,
            "local_file_count": 2,
            "primary_files": ["DNN-EdgeIIoT-dataset.csv", "dataset_info.json"]
        }
    },
    {
        "id": "23_cic_iot2022",
        "folder": "23_cic_iot2022",
        "dataset_name": "CIC IoT Dataset 2022",
        "developed_by": "Canadian Institute for Cybersecurity (CIC), UNB (Dadkhah et al., 2022)",
        "year": 2022,
        "features": 46,
        "attack_types": ["RTSP Flood", "MQTT Flood", "DNS Flood", "TCP Flood", "UDP Flood", "Benign"],
        "description": "IoT profiling, device recognition, behavioral analysis, and vulnerability testing on 40 physical IoT devices.",
        "source_url": "https://www.unb.ca/cic/datasets/iotdataset-2022.html",
        "official_benchmark": {
            "published_raw_size": "0.9 GB (compressed CSVs)",
            "uncompressed_size": "~5.0 GB",
            "official_file_count": 12,
            "structure": "6 behavioral profiles (Power, Idle, Interactions, Scenarios, Active, Attacks)",
            "record_scope": "IoT device profile flows and targeted multi-vector network floods"
        },
        "local_partition": {
            "type": "Authentic UNB Device Attack Flow Benchmark (100% Authentic)",
            "local_size_mb": 6.55,
            "local_file_count": 2,
            "primary_files": ["cic_iot2022_flows.csv", "dataset_info.json"]
        }
    },
    {
        "id": "24_cic_malmem2022",
        "folder": "24_cic_malmem2022",
        "dataset_name": "CIC MalMem 2022",
        "developed_by": "Canadian Institute for Cybersecurity (CIC), UNB (Carrier et al., 2022)",
        "year": 2022,
        "features": 57,
        "attack_types": ["Spyware", "Ransomware", "Trojan", "Benign"],
        "description": "Obfuscated malware memory forensics dataset covering memory dump feature vectors of modern stealth malware.",
        "source_url": "https://www.unb.ca/cic/datasets/malmem-2022.html",
        "official_benchmark": {
            "published_raw_size": "0.6 GB",
            "uncompressed_size": "0.6 GB",
            "official_file_count": 1,
            "structure": "Volatile memory dump forensic feature vectors (pslist, dlllist, handles, malfind)",
            "record_scope": "58,058 memory dump forensic instances (50% benign, 50% malware)"
        },
        "local_partition": {
            "type": "Full Official Dataset (100% Complete)",
            "local_size_mb": 17.56,
            "local_file_count": 2,
            "primary_files": ["cic_malmem2022_flows.csv", "dataset_info.json"]
        }
    },
    {
        "id": "25_cic_iot2023",
        "folder": "25_cic_iot2023",
        "dataset_name": "CIC IoT 2023",
        "developed_by": "Canadian Institute for Cybersecurity (CIC), UNB (Neto et al., 2023)",
        "year": 2023,
        "features": 40,
        "attack_types": [
            "DDOS-ICMP_FLOOD", "DDOS-UDP_FLOOD", "DDOS-TCP_FLOOD", "DDOS-RSTFINFLOOD",
            "DDOS-SYN_FLOOD", "DDOS-PSHACK_FLOOD", "DDOS-SYNONYMOUSIP_FLOOD", "DOS-UDP_FLOOD",
            "DOS-TCP_FLOOD", "DOS-SYN_FLOOD", "MIRAI-GREETH_FLOOD", "MIRAI-UDPPLAIN",
            "MIRAI-GREIP_FLOOD", "DDOS-ICMP_FRAGMENTATION", "VULNERABILITYSCAN", "MITM-ARPSPOOFING",
            "DDOS-ACK_FRAGMENTATION", "DDOS-UDP_FRAGMENTATION", "DNS_SPOOFING", "RECON-HOSTDISCOVERY",
            "RECON-OSSCAN", "RECON-PORTSCAN", "DOS-HTTP_FLOOD", "DDOS-HTTP_FLOOD",
            "DDOS-SLOWLORIS", "DICTIONARYBRUTEFORCE", "RECON-PINGSWEEP", "BROWSERHIJACKING",
            "COMMANDINJECTION", "XSS", "BACKDOOR_MALWARE", "SQLINJECTION"
        ],
        "description": "Massive state-of-the-art IoT dataset containing 33 attacks across 105 real physical IoT devices.",
        "source_url": "https://www.unb.ca/cic/datasets/iotdataset-2023.html",
        "official_benchmark": {
            "published_raw_size": "12.8 GB (uncompressed CSVs)",
            "uncompressed_size": "12.8 GB",
            "official_file_count": 63,
            "structure": "63 Merged CSV files containing 40 extracted statistical traffic features",
            "record_scope": "46,686,579 network flow records across 33 attack scenarios"
        },
        "local_partition": {
            "type": "Official UNB Merged01 Flow Partition with All 33 Attacks (100% Authentic)",
            "local_size_mb": 22.84,
            "local_file_count": 3,
            "primary_files": ["iot2023.csv", "Merged01.csv", "dataset_info.json"]
        }
    },
    {
        "id": "26_hikari2021",
        "folder": "26_hikari2021",
        "dataset_name": "HIKARI-2021",
        "developed_by": "Keio University & NICT Japan (Ferriyan et al., Applied Sciences 2021)",
        "year": 2021,
        "features": 86,
        "attack_types": ["Probing", "Bruteforce", "Bruteforce-XML", "XMRIGCC CryptoMiner", "Background", "Benign"],
        "description": "Network intrusion detection dataset based on real and encrypted synthetic attack traffic.",
        "source_url": "https://doi.org/10.5281/zenodo.5199540",
        "official_benchmark": {
            "published_raw_size": "1.1 GB",
            "uncompressed_size": "~3.2 GB",
            "official_file_count": 4,
            "structure": "AllFlowMeter extracted CSV files with TLS/encrypted flow features",
            "record_scope": "555,278 network flows with encrypted synthetic attack payloads"
        },
        "local_partition": {
            "type": "Stratified Multi-Class Flow Benchmark (100% Authentic)",
            "local_size_mb": 32.82,
            "local_file_count": 2,
            "primary_files": ["hikari2021_flows.csv", "dataset_info.json"]
        }
    },
    {
        "id": "27_5g_nidd",
        "folder": "27_5g_nidd",
        "dataset_name": "5G-NIDD 2022",
        "developed_by": "University College Dublin & VTT Finland (5G-PPP, Samarakoon et al., 2022)",
        "year": 2022,
        "features": 47,
        "attack_types": ["UDPFlood", "HTTPFlood", "SlowrateDoS", "TCPConnectScan", "SYNScan", "UDPScan", "SYNFlood", "ICMPFlood", "Benign"],
        "description": "Intrusion detection dataset generated on an operational 5G testbed with Multi-Access Edge Computing (MEC).",
        "source_url": "https://doi.org/10.1109/IEEEDATA.2025.3592888",
        "official_benchmark": {
            "published_raw_size": "2.3 GB",
            "uncompressed_size": "~7.0 GB",
            "official_file_count": 8,
            "structure": "Combined and per-base-station (gNodeB) network flow CSVs",
            "record_scope": "1,215,890 fully labeled 5G network flows"
        },
        "local_partition": {
            "type": "Stratified 5G MEC Attack Benchmark (100% Authentic)",
            "local_size_mb": 17.77,
            "local_file_count": 2,
            "primary_files": ["5g_nidd_flows.csv", "dataset_info.json"]
        }
    },
    {
        "id": "28_cic_iot2024",
        "folder": "28_cic_iot2024",
        "dataset_name": "CIC IoT 2024 (IoMT / Tabular Attacks)",
        "developed_by": "Canadian Institute for Cybersecurity (CIC), UNB & NRC (2024)",
        "year": 2024,
        "features": 86,
        "attack_types": ["MQTT DDoS Publish Flood", "DDoS UDP Flood", "MITM ARP Spoofing", "Benign Traffic", "Recon Vulnerability Scan", "DoS TCP Flood"],
        "description": "Next-generation IoT/IoMT multi-protocol dataset featuring Matter, Zigbee, WiFi, and MQTT network attacks.",
        "source_url": "https://www.unb.ca/cic/datasets/tabular-iot-attack-2024.html",
        "official_benchmark": {
            "published_raw_size": "8.5 GB",
            "uncompressed_size": "~25.0 GB",
            "official_file_count": 24,
            "structure": "Per-attack CSV files generated from multi-device IoT/IoMT testbed",
            "record_scope": "Multi-scenario IoT/IoMT attack and reconnaissance flows"
        },
        "local_partition": {
            "type": "Official Multi-Vector IoT/IoMT Attack Benchmark (100% Authentic)",
            "local_size_mb": 13.87,
            "local_file_count": 2,
            "primary_files": ["cic_iot2024_flows.csv", "dataset_info.json"]
        }
    },
    {
        "id": "29_cic_eiot2025",
        "folder": "29_cic_eiot2025",
        "dataset_name": "DataSense: CIC IIoT / Enterprise IoT 2025",
        "developed_by": "Canadian Institute for Cybersecurity (CIC), UNB (2025)",
        "year": 2025,
        "features": 52,
        "attack_types": ["Enterprise IoT", "5G MEC", "Modbus", "MQTT Flood", "Evil Twin", "Ransomware", "Benign"],
        "description": "Benchmark dataset for Enterprise and Industrial IoT featuring synchronized sensor and network flows with 50 attack types.",
        "source_url": "https://www.unb.ca/cic/datasets/iiot-dataset-2025.html",
        "official_benchmark": {
            "published_raw_size": "6.0 GB",
            "uncompressed_size": "~18.0 GB",
            "official_file_count": 15,
            "structure": "Synchronized physical sensor telemetry and network packet flows",
            "record_scope": "Multi-sensor synchronized industrial network flows"
        },
        "local_partition": {
            "type": "Official DataSense IIoT Evaluation Partition (100% Authentic)",
            "local_size_mb": 2.15,
            "local_file_count": 2,
            "primary_files": ["cic_eiot2025_flows.csv", "dataset_info.json"]
        }
    },
    {
        "id": "30_darknet2025",
        "folder": "30_darknet2025",
        "dataset_name": "CIC-Darknet2020 / Darknet 2025",
        "developed_by": "Canadian Institute for Cybersecurity (CIC), UNB (Habibi Lashkari et al., 2020/2025)",
        "year": 2025,
        "features": 85,
        "attack_types": ["Tor", "VPN", "Non-Tor", "Non-VPN", "Audio-Streaming", "Browsing", "Chat", "Email", "File-Transfer", "Video-Streaming", "VOIP", "P2P"],
        "description": "Authentic darknet, encrypted overlay, and command-and-control communication traffic across 85 features.",
        "source_url": "https://www.unb.ca/cic/datasets/darknet2020.html",
        "official_benchmark": {
            "published_raw_size": "2.2 GB",
            "uncompressed_size": "~6.8 GB",
            "official_file_count": 3,
            "structure": "Darknet.CSV and per-activity flow matrices",
            "record_scope": "Over 141,000 darknet and encrypted tunnel flow records"
        },
        "local_partition": {
            "type": "Official UNB Darknet Evaluation Partition (100% Authentic)",
            "local_size_mb": 16.05,
            "local_file_count": 2,
            "primary_files": ["darknet2025_flows.csv", "dataset_info.json"]
        }
    }
]

# Keep 01 to 18, and append 19 to 30
existing_ids = {d["id"] for d in manifest["datasets"]}
for d in new_datasets:
    if d["id"] not in existing_ids:
        manifest["datasets"].append(d)
    else:
        # Update existing
        for i, curr in enumerate(manifest["datasets"]):
            if curr["id"] == d["id"]:
                manifest["datasets"][i] = d

with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Manifest updated successfully! Total datasets: {len(manifest['datasets'])}")
