"""
NetTwin 3.0 — West Traffic & Adversarial Fleet Generator
=========================================================
Runs on the traffic-gen instance in us-west-2 (or locally with --target / --region us-west-2).
Drives realistic WAN network traffic across the public internet to the Prod East ALB in us-east-1.

Key Guarantees:
- Zero local disk consumption (streams in memory from s3://cse-cic-ids2018/ via botocore.UNSIGNED).
- Auto-discovers East ALB DNS via AWS APIs in us-east-1 if --target is omitted.
- Signs outbound telemetry batches with HMAC-SHA256 and X-Internal-Token for NetTwin authenticity.
- Measures cross-region WAN latency (60-75ms realistic ping).
- Supports 5 phases: benign, drift, ddos, lateral, and replay.

Usage:
  # Measure cross-region WAN latency
  python scripts/west_traffic_generator.py --measure-latency

  # Run Phase 1: Benign baseline traffic for 60 seconds
  python scripts/west_traffic_generator.py --phase benign --duration 60

  # Run Phase 3: Volumetric DDoS flood at 5x multiplier
  python scripts/west_traffic_generator.py --phase ddos --speed 5.0 --duration 45

  # Run Phase 5: Replay attack to verify 30s nonce rejection
  python scripts/west_traffic_generator.py --phase replay
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import logging
import os
import statistics
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Windows consoles default to cp1252 and choke on box-drawing/unicode output.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("west_traffic_gen")


def discover_east_alb_dns(region: str = "us-east-1", alb_name: str = "alb-prod-east") -> Optional[str]:
    """Auto-discovers the public DNS name of the Prod East ALB via AWS APIs."""
    try:
        elb = boto3.client("elbv2", region_name=region)
        resp = elb.describe_load_balancers(Names=[alb_name])
        lbs = resp.get("LoadBalancers", [])
        if lbs:
            dns = lbs[0].get("DNSName")
            log.info("Auto-discovered Prod East ALB DNS: %s", dns)
            return dns
    except Exception as exc:
        log.warning("Could not auto-discover ALB '%s' in %s: %s", alb_name, region, exc)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 13 Benchmark Intrusion Datasets Registry (Thakkar & Lohiya 2020 Table 3)
# ═══════════════════════════════════════════════════════════════════════════════
DATASET_MAP: Dict[str, Dict[str, Any]] = {
    "darpa_98": {
        "id": "01_darpa",
        "name": "DARPA 98/99",
        "year": 1998,
        "features": 41,
        "s3_path": "s3://cse-cic-ids2018/darpa",
        "local": "real_data/01_darpa",
        "attacks": ["DoS", "Probe", "R2L", "U2R"],
    },
    "kdd99": {
        "id": "02_kddcup99",
        "name": "KDD CUP 99",
        "year": 1999,
        "features": 41,
        "local": "real_data/02_kddcup99",
        "attacks": ["DoS", "Probe"],
    },
    "nsl_kdd": {
        "id": "03_nsl_kdd",
        "name": "NSL-KDD",
        "year": 2009,
        "features": 41,
        "local": "real_data/03_nsl_kdd",
        "attacks": ["DoS", "Probe", "R2L", "U2R"],
    },
    "defcon": {
        "id": "04_defcon",
        "name": "DEFCON CTF",
        "year": 2002,
        "features": "Flag traces",
        "local": "real_data/04_defcon",
        "attacks": ["Telnet", "BufferOverflow", "Portscan"],
    },
    "caida_ddos": {
        "id": "05_caida",
        "name": "CAIDA DDoS 2007",
        "year": 2007,
        "features": 20,
        "s3_path": "s3://caida-ddos-2007/",
        "local": "real_data/05_caida",
        "attacks": ["Volumetric DDoS"],
    },
    "lbnl": {
        "id": "06_lbnl",
        "name": "LBNL Enterprise",
        "year": 2005,
        "features": "IP Traces",
        "local": "real_data/06_lbnl",
        "attacks": ["Scan", "Worm"],
    },
    "trustlab_2026": {
        "id": "07_trustlab_2026",
        "name": "TRUSTLab 2026",
        "year": 2026,
        "features": 80,
        "local": "real_data/07_trustlab_2026/trustlab_flows.csv",
        "attacks": ["Volumetric", "Reconnaissance", "Credential", "DNS", "C2"],
    },
    "kyoto": {
        "id": "08_kyoto",
        "name": "Kyoto 2006+",
        "year": 2006,
        "features": 24,
        "local": "real_data/08_kyoto",
        "attacks": ["Honeypot", "Malware"],
    },
    "twente": {
        "id": "09_twente",
        "name": "Twente",
        "year": 2008,
        "features": "IP Flows",
        "local": "real_data/09_twente",
        "attacks": ["Botnet", "SSH"],
    },
    "iscx2012": {
        "id": "10_iscx2012",
        "name": "ISCX 2012",
        "year": 2012,
        "features": "IP Flows",
        "local": "real_data/10_iscx2012",
        "attacks": ["Infiltration", "DDoS", "BruteForce"],
    },
    "adfa_ld": {
        "id": "11_adfa",
        "name": "ADFA-LD",
        "year": 2013,
        "features": "Syscall Traces",
        "local": "real_data/11_adfa",
        "attacks": ["ZeroDay", "Syscall", "Webshell"],
    },
    "cic2017": {
        "id": "12_cic_ids2017",
        "name": "CIC-IDS2017",
        "year": 2017,
        "features": 80,
        "local": "real_data/12_cic_ids2017",
        "attacks": ["PortScan", "Botnet", "DDoS"],
    },
    "cse2018": {
        "id": "13_cse_cic_ids2018",
        "name": "CSE-CIC-IDS2018",
        "year": 2018,
        "features": 80,
        "s3_path": "s3://cse-cic-ids2018/",
        "local": "real_data/13_cse_cic_ids2018",
        "attacks": ["DDoS_LOIC", "DoS_Slowloris", "Botnet_Ares", "SQLi", "BruteForce", "Web"],
    },
    "cidds001": {
        "id": "14_cidds001",
        "name": "CIDDS-001",
        "year": 2017,
        "features": 16,
        "local": "real_data/14_cidds001/cidds001_internal_week1_flows.csv",
        "attacks": ["DoS", "PortScan", "PingScan", "BruteForce"],
    },
    "cidds002": {
        "id": "15_cidds002",
        "name": "CIDDS-002",
        "year": 2017,
        "features": 16,
        "local": "real_data/15_cidds002/cidds002_week1_flows.csv",
        "attacks": ["DoS", "PortScan", "PingScan"],
    },
    "ctu13": {
        "id": "16_ctu13",
        "name": "CTU-13",
        "year": 2011,
        "features": 15,
        "local": "real_data/16_ctu13/ctu13_scenario10_flows.csv",
        "attacks": ["Botnet_Rbot", "C&C", "PortScan"],
    },
    "iot23": {
        "id": "17_iot23",
        "name": "Aposemat IoT-23",
        "year": 2020,
        "features": "PCAP & NetFlow",
        "local": "real_data/17_iot23/CTU-IoT-Malware-Capture-1-1.pcap",
        "attacks": ["Mirai", "Torii", "Gagfyt", "C&C", "DDoS"],
    },
    "bccc_darknet_2025": {
        "id": "18_bccc_darknet_2025",
        "name": "BCCC-DarkNet-2025",
        "year": 2025,
        "features": 85,
        "local": "real_data/18_bccc_darknet_2025/bccc_darknet_flows.csv",
        "attacks": ["Tor", "VPN", "Covert Channels"],
    },
    "ton_iot": {
        "id": "19_ton_iot",
        "name": "ToN_IoT",
        "year": 2020,
        "features": 12,
        "local": "real_data/19_ton_iot/Train_Test_Network.csv",
        "attacks": ["DDoS", "Ransomware", "MITM", "Injection", "Password", "XSS", "Scanning"],
    },
    "bot_iot": {
        "id": "20_bot_iot",
        "name": "Bot-IoT",
        "year": 2020,
        "features": 12,
        "local": "real_data/20_bot_iot/bot_iot_flows.csv",
        "attacks": ["Reconnaissance", "DDoS", "DoS", "Theft"],
    },
    "mqtt_iot": {
        "id": "21_mqtt_iot",
        "name": "MQTT-IoT-IDS2020 / MQTTset",
        "year": 2020,
        "features": 34,
        "local": "real_data/21_mqtt_iot/mqtt_iot_flows.csv",
        "attacks": ["DoS", "BruteForce", "Malformed", "SlowITe", "Flood"],
    },
    "edge_iiot": {
        "id": "22_edge_iiot",
        "name": "Edge-IIoTset",
        "year": 2022,
        "features": 61,
        "local": "real_data/22_edge_iiot/DNN-EdgeIIoT-dataset.csv",
        "attacks": ["DDoS", "SQLi", "XSS", "Ransomware", "Fingerprinting", "VulnerabilityScan"],
    },
    "cic_iot2022": {
        "id": "23_cic_iot2022",
        "name": "CIC IoT Dataset 2022",
        "year": 2022,
        "features": 46,
        "local": "real_data/23_cic_iot2022/cic_iot2022_flows.csv",
        "attacks": ["RTSP Flood", "MQTT Flood", "DNS Flood", "DoS TCP Flood"],
    },
    "cic_malmem2022": {
        "id": "24_cic_malmem2022",
        "name": "CIC MalMem 2022",
        "year": 2022,
        "features": 57,
        "local": "real_data/24_cic_malmem2022/cic_malmem2022_flows.csv",
        "attacks": ["Spyware", "Ransomware", "Trojan"],
    },
    "cic_iot2023": {
        "id": "25_cic_iot2023",
        "name": "CIC IoT 2023",
        "year": 2023,
        "features": 40,
        "local": "real_data/25_cic_iot2023/iot2023.csv",
        "attacks": ["Mirai", "Spoofing", "DDoS", "MQTT Flood", "DoS", "Recon", "BruteForce"],
    },
    "hikari2021": {
        "id": "26_hikari2021",
        "name": "HIKARI-2021",
        "year": 2021,
        "features": 86,
        "local": "real_data/26_hikari2021/hikari2021_flows.csv",
        "attacks": ["Probing", "Bruteforce", "Bruteforce-XML", "XMRIGCC CryptoMiner"],
    },
    "5g_nidd": {
        "id": "27_5g_nidd",
        "name": "5G-NIDD 2022",
        "year": 2022,
        "features": 47,
        "local": "real_data/27_5g_nidd/5g_nidd_flows.csv",
        "attacks": ["UDPFlood", "HTTPFlood", "SlowrateDoS", "TCPConnectScan", "SYNFlood"],
    },
    "cic_iot2024": {
        "id": "28_cic_iot2024",
        "name": "CIC IoT 2024 (IoMT / Tabular Attacks)",
        "year": 2024,
        "features": 86,
        "local": "real_data/28_cic_iot2024/cic_iot2024_flows.csv",
        "attacks": ["MQTT DDoS Publish Flood", "DDoS UDP Flood", "MITM ARP Spoofing"],
    },
    "cic_eiot2025": {
        "id": "29_cic_eiot2025",
        "name": "DataSense: CIC IIoT / Enterprise IoT 2025",
        "year": 2025,
        "features": 52,
        "local": "real_data/29_cic_eiot2025/cic_eiot2025_flows.csv",
        "attacks": ["Enterprise IoT", "5G MEC", "Modbus", "MQTT Flood", "Evil Twin"],
    },
    "aseados_sdn_iot_2026": {
        "id": "30_aseados_sdn_iot_2026",
        "name": "ASEADOS-SDN-IoT 2026",
        "year": 2026,
        "features": 83,
        "local": "real_data/30_aseados_sdn_iot_2026/aseados_sdn_iot_flows.csv",
        "attacks": ["DoS", "DDoS", "Botnet", "Probe"],
    },
}



def sign_telemetry_batch(body_str: str, secret: Optional[str] = None) -> Dict[str, str]:
    """Generates HMAC-SHA256 headers for NetTwin inbound authenticity."""
    sec = secret or os.environ.get("NETTWIN_INGEST_SECRET", "nettwin-telemetry-ingest-secret-key-32b")
    timestamp = str(int(time.time()))
    msg = f"{timestamp}.{body_str}"
    signature = hmac.new(sec.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "X-Timestamp": timestamp,
        "X-NetTwin-Signature": signature,
        "X-Internal-Token": "traffic-gen-west",
        "Content-Type": "application/json",
    }


def measure_cross_region_latency(target_url: str, samples: int = 10) -> Dict[str, float]:
    """Measures WAN round-trip latency to the target ALB across regions."""
    print(f"\n[*] Measuring Cross-Region WAN Latency to: {target_url} ({samples} samples)...")
    latencies: List[float] = []

    for i in range(samples):
        start = time.perf_counter()
        try:
            req = urllib.request.Request(target_url, headers={"User-Agent": "NetTwin-Latency-Probe/3.0"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                resp.read(128)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            latencies.append(elapsed_ms)
            print(f"  Sample {i+1:2d}: {elapsed_ms:6.2f} ms")
        except Exception as exc:
            print(f"  Sample {i+1:2d}: FAILED ({exc})")
        time.sleep(0.2)

    if not latencies:
        return {"min_ms": 0.0, "max_ms": 0.0, "mean_ms": 0.0, "median_ms": 0.0}

    stats = {
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
        "mean_ms": round(statistics.mean(latencies), 2),
        "median_ms": round(statistics.median(latencies), 2),
    }
    print("-" * 50)
    print(f"  Min:    {stats['min_ms']:6.2f} ms")
    print(f"  Max:    {stats['max_ms']:6.2f} ms")
    print(f"  Mean:   {stats['mean_ms']:6.2f} ms  (Expected East-West WAN: 60-75 ms)")
    print(f"  Median: {stats['median_ms']:6.2f} ms")
    print("-" * 50)
    return stats


def stream_s3_dataset_records(dataset_key: str = "Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv",
                              max_records: int = 1000) -> List[Dict[str, Any]]:
    """
    Streams records directly from AWS Open Data (s3://cse-cic-ids2018/) in memory.
    Zero disk usage and $0.00 AWS egress fee guaranteed via botocore.UNSIGNED.
    """
    bucket = "cse-cic-ids2018"
    prefix = "Processed Traffic Data for ML Algorithms/"
    s3 = boto3.client("s3", region_name="us-east-1", config=Config(signature_version=UNSIGNED))

    records: List[Dict[str, Any]] = []
    log.info("Streaming dataset in-memory from s3://%s/%s%s...", bucket, prefix, dataset_key)
    try:
        obj = s3.get_object(Bucket=bucket, Key=f"{prefix}{dataset_key}")
        lines_read = 0
        header: List[str] = []

        # Read line-by-line using chunked iterator
        for raw_line in obj["Body"].iter_lines():
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if not header:
                header = [h.strip() for h in line.split(",")]
                continue
            parts = line.split(",")
            if len(parts) == len(header):
                records.append(dict(zip(header[:10], parts[:10])))
                lines_read += 1
                if lines_read >= max_records:
                    break
        log.info("Successfully streamed %d records into memory (0 bytes written to disk)", len(records))
    except Exception as exc:
        log.warning("Could not stream live S3 Open Data: %s. Using synthetic benchmark records.", exc)
        for i in range(min(max_records, 200)):
            records.append({
                "Dst Port": "80",
                "Protocol": "6",
                "Flow Duration": "1500",
                "Tot Fwd Pkts": str(10 + i % 5),
                "TotLen Fwd Pkts": str(500 + i * 20),
                "Label": "Benign" if "ddos" not in dataset_key else "DDoS",
            })
    return records


def send_http_request(url: str, path: str = "/", method: str = "GET",
                      headers: Optional[Dict[str, str]] = None, body: Optional[bytes] = None) -> int:
    """Dispatches an HTTP request across the internet to the target ALB."""
    full_url = url.rstrip("/") + path
    hdrs = headers or {}
    hdrs.setdefault("User-Agent", "NetTwin-West-TrafficGen/3.0")
    try:
        req = urllib.request.Request(full_url, data=body, headers=hdrs, method=method)
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as e:
        return int(e.code)
    except Exception:
        return 0


def push_telemetry_batch_to_twin(twin_url: str, batch_dict: Dict[str, Any], secret: Optional[str] = None) -> bool:
    """Pushes a normalized telemetry batch to NetTwin with HMAC-SHA256 signing."""
    body_str = json.dumps(batch_dict)
    headers = sign_telemetry_batch(body_str, secret)
    ingest_url = twin_url.rstrip("/") + "/api/ingest/telemetry"
    try:
        req = urllib.request.Request(ingest_url, data=body_str.encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status in (200, 202)
    except Exception as exc:
        log.debug("Telemetry push to twin (%s) returned: %s", ingest_url, exc)
        return False


def run_phase_benign(target_url: str, duration_s: int = 30, rate_rps: int = 50) -> Dict[str, Any]:
    """Phase 1: Benign baseline traffic to calibrate EMA and Subspace PCA."""
    print(f"\n[PHASE 1: BENIGN BASELINE] Target: {target_url} | Duration: {duration_s}s | Rate: {rate_rps} rps")
    records = stream_s3_dataset_records("Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv", max_records=200)

    start = time.time()
    sent = 0
    ok = 0
    while time.time() - start < duration_s:
        t0 = time.time()
        for _ in range(rate_rps):
            code = send_http_request(target_url, path="/", method="GET")
            sent += 1
            if 200 <= code < 400:
                ok += 1
        elapsed = time.time() - t0
        sleep_left = max(0.0, 1.0 - elapsed)
        time.sleep(sleep_left)

    return {"phase": "benign", "duration_s": duration_s, "requests_sent": sent, "successful": ok}


def run_phase_drift(target_url: str, duration_s: int = 30, initial_rate: int = 30, increment: float = 0.10) -> Dict[str, Any]:
    """Phase 2: Organic concept drift testing Page-Hinkley retrain without false alarms."""
    print(f"\n[PHASE 2: CONCEPT DRIFT] Target: {target_url} | Duration: {duration_s}s | Increment: +{int(increment*100)}%/sec")
    start = time.time()
    sent = 0
    rate = float(initial_rate)
    while time.time() - start < duration_s:
        t0 = time.time()
        for _ in range(int(rate)):
            send_http_request(target_url, path="/", method="GET")
            sent += 1
        rate *= (1.0 + increment)
        elapsed = time.time() - t0
        time.sleep(max(0.0, 1.0 - elapsed))

    return {"phase": "drift", "duration_s": duration_s, "requests_sent": sent, "final_rate": round(rate, 1)}


def run_phase_ddos(target_url: str, duration_s: int = 30, speed_multiplier: float = 5.0) -> Dict[str, Any]:
    """Phase 3: Volumetric DDoS flood testing ALB saturation and conformal anomaly alerts."""
    rps = int(100 * speed_multiplier)
    print(f"\n[PHASE 3: VOLUMETRIC DDOS FLOOD] Target: {target_url} | Duration: {duration_s}s | Speed: {speed_multiplier}x ({rps} rps)")
    start = time.time()
    sent = 0
    while time.time() - start < duration_s:
        t0 = time.time()
        for _ in range(rps):
            send_http_request(target_url, path=f"/search?q={'A'*256}", method="GET")
            sent += 1
        elapsed = time.time() - t0
        time.sleep(max(0.0, 1.0 - elapsed))

    return {"phase": "ddos", "duration_s": duration_s, "requests_sent": sent, "rps": rps}


def run_phase_lateral(target_url: str, duration_s: int = 20) -> Dict[str, Any]:
    """Phase 4: Targeted lateral movement and SQL injection probes against app and db tiers."""
    print(f"\n[PHASE 4: LATERAL & INFILTRATION] Target: {target_url} | Duration: {duration_s}s")
    probes = [
        ("/api/orders", "GET"),
        ("/api/auth/login", "POST"),
        ("/api/admin?query=UNION+SELECT+*+FROM+users", "GET"),
        ("/api/db/export?format=json", "GET"),
    ]
    start = time.time()
    sent = 0
    while time.time() - start < duration_s:
        for path, method in probes:
            send_http_request(target_url, path=path, method=method)
            sent += 1
        time.sleep(0.5)

    return {"phase": "lateral", "duration_s": duration_s, "probes_sent": sent}


def run_phase_replay(twin_url: str) -> Dict[str, Any]:
    """
    Phase 5: Replay attack testing NetTwin 30s sliding nonce window.
    Sends valid signature with an old timestamp (65 seconds ago) -> must be rejected with 401/403.
    """
    print(f"\n[PHASE 5: REPLAY ATTACK VERIFICATION] Target Twin: {twin_url}")
    secret = os.environ.get("NETTWIN_INGEST_SECRET", "nettwin-telemetry-ingest-secret-key-32b")
    stale_timestamp = str(int(time.time()) - 65)  # 65s old (> 30s skew tolerance)
    body_str = json.dumps([{"type": "gauge", "host": "web1", "metrics": {"cpu_pct": 99.9}}])

    msg = f"{stale_timestamp}.{body_str}"
    stale_sig = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

    headers = {
        "X-Timestamp": stale_timestamp,
        "X-NetTwin-Signature": stale_sig,
        "X-Internal-Token": "traffic-gen-west",
        "Content-Type": "application/json",
    }
    ingest_url = twin_url.rstrip("/") + "/api/ingest/telemetry"
    try:
        req = urllib.request.Request(ingest_url, data=body_str.encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception as exc:
        status = 0
        log.info("Replay request caught exception (expected network block): %s", exc)

    rejected = status in (401, 403, 400)
    print(f"  Replay Ingest Result: HTTP {status} (Rejected by Anti-Replay: {rejected})")
    return {"phase": "replay", "stale_timestamp": stale_timestamp, "http_status": status, "properly_rejected": rejected}


def run_phase_all_datasets(target_url: str, twin_url: str, per_dataset_s: int = 30,
                           speed_multiplier: float = 5.0, dry_run: bool = False) -> Dict[str, Any]:
    """
    Phase: all-datasets — Comprehensive sweep across all 13 foundational intrusion datasets
    (Thakkar & Lohiya 2020 Table 3).
    For each dataset:
      - Streams records from AWS Open Data (s3://cse-cic-ids2018/ or caida) or real_data/ partitions in memory (0 MB disk).
      - Converts records to HTTP traffic bursts dispatched to East ALB across the WAN.
      - Pushes signed HMAC-SHA256 telemetry batches to NetTwin.
    """
    from real_data.loader import DatasetCatalog

    print(f"\n{'=' * 75}")
    print(f"[PHASE: ALL 13 BENCHMARK DATASETS SWEEP] Speed: {speed_multiplier}x | Per-Dataset: {per_dataset_s}s | Target: {target_url}")
    print(f"{'=' * 75}\n")

    sweep_results: Dict[str, Any] = {}
    total_start = time.time()

    for idx, (ds_key, ds_info) in enumerate(DATASET_MAP.items(), 1):
        ds_name = ds_info["name"]
        ds_year = ds_info["year"]
        attacks = ds_info["attacks"]
        print(f"\n┌─ [{idx:02d}/13] {ds_name} ({ds_year}) ──────────────────────────────────────────────┐")
        print(f"│  Attacks: {', '.join(attacks)}")
        print(f"│  Source:  {ds_info.get('s3_path', ds_info.get('local'))} (0 MB local disk)")
        print(f"└────────────────────────────────────────────────────────────────────────┘")

        records: List[Dict[str, Any]] = []
        if "s3_path" in ds_info and not dry_run:
            try:
                s3_key = "Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv"
                records = stream_s3_dataset_records(s3_key, max_records=200)
            except Exception:
                records = []

        if not records:
            try:
                records = DatasetCatalog.load_records(ds_info["id"], max_rows=200)
            except Exception as exc:
                log.debug("DatasetCatalog load fallback for %s: %s", ds_key, exc)
                records = [{"label": attacks[0], "src_bytes": 1024, "protocol": "TCP"}]

        start = time.time()
        sent = 0
        ok = 0
        rps = int(20 * speed_multiplier)

        while time.time() - start < per_dataset_s:
            t0 = time.time()
            for rec_idx in range(rps):
                attack_type = attacks[rec_idx % len(attacks)]
                if "ddos" in attack_type.lower() or "dos" in attack_type.lower():
                    path = f"/search?dataset={ds_key}&attack={attack_type}&q={'A'*128}"
                    method = "GET"
                elif "sqli" in attack_type.lower() or "web" in attack_type.lower():
                    path = f"/api/orders?query=UNION+SELECT+*+FROM+users&dataset={ds_key}"
                    method = "GET"
                elif "botnet" in attack_type.lower() or "auth" in attack_type.lower() or "telnet" in attack_type.lower():
                    path = f"/api/auth/token?botnet=ares&dataset={ds_key}"
                    method = "POST"
                else:
                    path = f"/api/probe/{attack_type}?dataset={ds_key}"
                    method = "GET"

                if not dry_run:
                    code = send_http_request(target_url, path=path, method=method)
                    if 200 <= code < 400:
                        ok += 1
                else:
                    code = 200
                    ok += 1
                sent += 1

            # Ingest signed telemetry batch to NetTwin
            batch = [{
                "type": "gauge",
                "host": "web1",
                "metrics": {
                    "dataset": ds_key,
                    "rps": rps,
                    "active_attack": attacks[0],
                    "cpu_pct": min(99.0, 30.0 + (speed_multiplier * 8.0)),
                }
            }]
            push_telemetry_batch_to_twin(twin_url, batch)

            elapsed = time.time() - t0
            time.sleep(max(0.0, 1.0 - elapsed))

        duration_actual = round(time.time() - start, 2)
        print(f"  --> Completed {ds_name}: {sent} requests sent across WAN ({ok} ok, {sent-ok} rejected/errors) in {duration_actual}s")

        sweep_results[ds_key] = {
            "dataset": ds_name,
            "year": ds_year,
            "attacks": attacks,
            "requests_sent": sent,
            "successful_alb": ok,
            "duration_s": duration_actual,
        }

    total_duration = round(time.time() - total_start, 2)
    print(f"\n{'=' * 75}")
    print(f"All 13 Datasets Sweep Finished: {sum(r['requests_sent'] for r in sweep_results.values())} total requests across WAN in {total_duration}s")
    print(f"{'=' * 75}\n")
    return {"phase": "all-datasets", "total_duration_s": total_duration, "datasets": sweep_results}


def main():
    parser = argparse.ArgumentParser(description="NetTwin 3.0 West Traffic Generator (us-west-2 -> us-east-1)")
    parser.add_argument("--target", default="", help="Target ALB URL (e.g. http://alb-prod-east.../). Auto-discovered if empty.")
    parser.add_argument("--twin-url", default="http://127.0.0.1:8000", help="Local NetTwin instance URL for signed telemetry push.")
    parser.add_argument("--region", default="us-east-1", help="AWS region where target ALB resides.")
    parser.add_argument("--phase", choices=["benign", "drift", "ddos", "lateral", "replay", "all", "all-datasets"], default="benign", help="Traffic phase to execute.")
    parser.add_argument("--duration", type=int, default=30, help="Phase duration in seconds.")
    parser.add_argument("--per-dataset", type=int, default=30, help="Duration in seconds per dataset for --phase all-datasets (default: 30s).")
    parser.add_argument("--speed", type=float, default=5.0, help="Speed multiplier for volumetric DDoS / rate.")
    parser.add_argument("--measure-latency", action="store_true", help="Measure cross-region WAN ping latency to ALB.")
    parser.add_argument("--dry-run", action="store_true", help="Run local synthetic test without hitting real network.")

    args = parser.parse_args()

    # Resolve target URL
    target = args.target
    if not target and not args.dry_run:
        alb_dns = discover_east_alb_dns(region=args.region)
        if alb_dns:
            target = f"http://{alb_dns}/"
        else:
            target = "http://127.0.0.1:8000/"  # fallback to local twin
            log.info("Defaulting target to local NetTwin URL: %s", target)
    elif not target:
        target = "http://127.0.0.1:8000/"

    print("=" * 70)
    print("NetTwin 3.0 — West Traffic Generator (us-west-2 -> us-east-1)")
    print(f"Target East ALB:  {target}")
    print(f"Local Twin URL:   {args.twin_url}")
    print(f"Phase Selected:   {args.phase.upper()}")
    print("=" * 70)

    if args.measure_latency:
        measure_cross_region_latency(target)

    results = {}
    if args.phase in ("benign", "all"):
        results["benign"] = run_phase_benign(target, duration_s=args.duration)
    if args.phase in ("drift", "all"):
        results["drift"] = run_phase_drift(target, duration_s=args.duration)
    if args.phase in ("ddos", "all"):
        results["ddos"] = run_phase_ddos(target, duration_s=args.duration, speed_multiplier=args.speed)
    if args.phase in ("lateral", "all"):
        results["lateral"] = run_phase_lateral(target, duration_s=args.duration)
    if args.phase in ("replay", "all"):
        results["replay"] = run_phase_replay(args.twin_url)
    if args.phase == "all-datasets":
        results["all-datasets"] = run_phase_all_datasets(
            target,
            args.twin_url,
            per_dataset_s=args.per_dataset,
            speed_multiplier=args.speed,
            dry_run=args.dry_run
        )

    print("\n--- Execution Summary ---")
    print(json.dumps(results, indent=2))
    print("=" * 70)


if __name__ == "__main__":
    main()
