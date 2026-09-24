"""
NetTwin 3.0 Real Data Loader & Ingestion Adapter
================================================
Unified data loading, exploration, and streaming pipeline for all 13 benchmark datasets:
1.  DARPA (MIT Lincoln Laboratory)
2.  KDD CUP 99 (University of California)
3.  NSL-KDD (University of California)
4.  DEFCON (Shmoo Group)
5.  CAIDA (Center of Applied Internet Data Analysis)
6.  LBNL (Lawrence Berkeley National Laboratory)
7.  CDX (United States Military Academy)
8.  Kyoto (Kyoto University)
9.  Twente (Twente University)
10. ISCX2012 (University of New Brunswick)
11. AFDA / ADFA (University of New South Wales)
12. CIC-IDS2017 (Canadian Institute for Cybersecurity)
13. CSE-CIC-IDS2018 (Canadian Institute for Cybersecurity & AWS)

Reference:
Thakkar, A., & Lohiya, R. (2020). A review of the advancement in intrusion detection datasets.
Procedia Computer Science, 167, 636-645. Table 3.
"""

import os
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator

BASE_DIR = Path("d:/AWS Cloud/nettwin-project")
REAL_DATA_DIR = BASE_DIR / "real_data"

KDD_COLUMN_NAMES = [
    "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes",
    "land", "wrong_fragment", "urgent", "hot", "num_failed_logins", "logged_in",
    "num_compromised", "root_shell", "su_attempted", "num_root", "num_file_creations",
    "num_shells", "num_access_files", "num_outbound_cmds", "is_host_login",
    "is_guest_login", "count", "srv_count", "serror_rate", "srv_serror_rate",
    "rerror_rate", "srv_rerror_rate", "same_srv_rate", "diff_srv_rate",
    "srv_diff_host_rate", "dst_host_count", "dst_host_srv_count",
    "dst_host_same_srv_rate", "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate", "dst_host_srv_serror_rate",
    "dst_host_rerror_rate", "dst_host_srv_rerror_rate", "label", "difficulty_level"
]

class DatasetCatalog:
    """Master registry and loader for NetTwin's real-world datasets."""

    @staticmethod
    def list_datasets() -> List[Dict[str, Any]]:
        """Returns metadata for all 13 intrusion detection datasets."""
        manifest_path = REAL_DATA_DIR / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f).get("datasets", [])
        
        datasets = []
        if REAL_DATA_DIR.exists():
            for folder in sorted(REAL_DATA_DIR.iterdir()):
                if folder.is_dir() and folder.name[:2].isdigit():
                    info_file = folder / "dataset_info.json"
                    if info_file.exists():
                        with open(info_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            data["folder"] = folder.name
                            datasets.append(data)
        return datasets

    @staticmethod
    def get_dataset_info(key: str) -> Optional[Dict[str, Any]]:
        """Finds a dataset by index prefix (e.g. '01', '03') or name (e.g. 'NSL-KDD')."""
        datasets = DatasetCatalog.list_datasets()
        for d in datasets:
            folder = d.get("folder", "")
            name = d.get("dataset_name", "")
            if key.lower() in folder.lower() or key.lower() in name.lower():
                return d
        return None

    @staticmethod
    def load_records(dataset_key: str, max_rows: int = 100) -> List[Dict[str, Any]]:
        """Loads a structured sample of rows from the target dataset."""
        info = DatasetCatalog.get_dataset_info(dataset_key)
        if not info:
            raise ValueError(f"Dataset '{dataset_key}' not found in catalog.")

        folder = REAL_DATA_DIR / info["folder"]
        records = []

        # 1. DARPA
        if "darpa" in info["folder"].lower():
            bsm_file = folder / "extracted" / "DARPA_eval_b" / "bsm.list"
            if bsm_file.exists():
                with open(bsm_file, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f):
                        if i >= max_rows:
                            break
                        parts = line.strip().split()
                        records.append({
                            "audit_record": parts[0] if len(parts) > 0 else "BSM_EVENT",
                            "process_id": parts[1] if len(parts) > 1 else "101",
                            "user": parts[2] if len(parts) > 2 else "root",
                            "attack_type": "Probe/U2R",
                            "raw": line.strip()
                        })
                return records

        # 2. KDD CUP 99
        if "kddcup" in info["folder"].lower():
            for fname in ["kddcup.data_10_percent_corrected", "kddcup.data_10_percent"]:
                fpath = folder / fname
                if fpath.exists() and fpath.stat().st_size > 1000:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f):
                            if i >= max_rows:
                                break
                            parts = line.strip().split(",")
                            cols = KDD_COLUMN_NAMES[:len(parts)]
                            records.append(dict(zip(cols, parts)))
                    return records

        # 3. NSL-KDD
        if "nsl" in info["folder"].lower():
            train_file = folder / "KDDTrain+.txt"
            if train_file.exists():
                with open(train_file, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f):
                        if i >= max_rows:
                            break
                        parts = line.strip().split(",")
                        cols = KDD_COLUMN_NAMES[:len(parts)]
                        records.append(dict(zip(cols, parts)))
                return records

        # 4. ISCX2012
        if "iscx" in info["folder"].lower():
            csv_candidates = list(folder.rglob("*Flows.csv"))
            if csv_candidates:
                with open(csv_candidates[0], "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader):
                        if i >= max_rows:
                            break
                        records.append(dict(row))
                return records

        # 5. AFDA / ADFA-LD
        if "adfa" in info["folder"].lower():
            for p in folder.rglob("*.txt"):
                if len(records) >= max_rows:
                    break
                if "Master" in str(p) or "Attack" in str(p) or "Training" in str(p):
                    try:
                        content = p.read_text(encoding="utf-8", errors="ignore").strip()
                        syscalls = content.split()
                        is_attack = "Attack" in str(p)
                        records.append({
                            "trace_id": p.stem,
                            "sequence_length": len(syscalls),
                            "syscall_sequence": syscalls[:15],
                            "attack_type": "Webshell/Stealth" if is_attack else "Normal Execution",
                            "label": "ATTACK" if is_attack else "BENIGN"
                        })
                    except Exception:
                        pass
            if records:
                return records

        # 6. CSV-based datasets (CAIDA, LBNL, CDX, Twente, DEFCON, Kyoto, CIC-IDS2017, CSE-CIC-IDS2018)
        csv_files = sorted(list(folder.glob("*.csv")), key=lambda p: p.stat().st_size, reverse=True)
        if csv_files:
            target_csv = csv_files[0]
            with open(target_csv, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i >= max_rows:
                        break
                    records.append(dict(row))
            return records

        # 7. PCAP-based datasets (IoT-23, CAIDA, raw captures)
        pcap_files = sorted(list(folder.glob("*.pcap")), key=lambda p: p.stat().st_size, reverse=True)
        if pcap_files:
            try:
                import dpkt, socket
                with open(pcap_files[0], "rb") as f:
                    pcap = dpkt.pcap.Reader(f)
                    dlt = pcap.datalink()
                    for ts, buf in pcap:
                        if len(records) >= max_rows:
                            break
                        ip = None
                        if dlt == 1:  # DLT_EN10MB
                            eth = dpkt.ethernet.Ethernet(buf)
                            if isinstance(eth.data, dpkt.ip.IP):
                                ip = eth.data
                        elif dlt in [12, 101]:  # DLT_RAW
                            ip = dpkt.ip.IP(buf)
                        
                        if ip:
                            records.append({
                                "timestamp": ts,
                                "src_ip": socket.inet_ntoa(ip.src),
                                "dst_ip": socket.inet_ntoa(ip.dst),
                                "src_port": ip.data.sport if hasattr(ip.data, "sport") else 0,
                                "dst_port": ip.data.dport if hasattr(ip.data, "dport") else 0,
                                "protocol": "TCP" if ip.p == 6 else ("UDP" if ip.p == 17 else ("ICMP" if ip.p == 1 else str(ip.p))),
                                "bytes": len(buf),
                                "label": "MALWARE_SCAN" if "iot" in folder.name.lower() else "ATTACK",
                                "is_anomaly": True
                            })
                    if records:
                        return records
            except Exception:
                pass

        # Fallback: list files in folder
        return [{"folder": folder.name, "files": [f.name for f in folder.iterdir() if f.is_file()]}]

    @staticmethod
    def stream_telemetry_batch(dataset_key: str, batch_size: int = 32, max_records: Optional[int] = None) -> Iterator[List[Dict[str, Any]]]:
        """
        Streams standardized telemetry batches ready for NetTwin 3.0 digital twin replay.
        """
        fetch_limit = max_records if max_records is not None else 5000
        raw_records = DatasetCatalog.load_records(dataset_key, max_rows=fetch_limit)
        batch = []

        for r in raw_records:
            src_ip = (r.get("src_ip") or r.get("source") or r.get("Source IP") or r.get("Src IP") or
                      r.get("Src IP Addr") or r.get("Src_IP") or r.get("originh") or r.get("IPV4_SRC_ADDR") or "192.168.1.100")
            dst_ip = (r.get("dst_ip") or r.get("destination") or r.get("Destination IP") or r.get("Dst IP") or
                      r.get("Dst IP Addr") or r.get("Dst_IP") or r.get("responh") or r.get("IPV4_DST_ADDR") or "10.0.0.1")
            
            src_p_raw = (r.get("src_port") or r.get("sourcePort") or r.get("Source Port") or r.get("Src Port") or
                         r.get("Src Pt") or r.get("Src_Port") or r.get("L4_SRC_PORT") or r.get("originp") or 49152)
            dst_p_raw = (r.get("dst_port") or r.get("destinationPort") or r.get("Destination Port") or r.get("Dst Port") or
                         r.get("Dst Pt") or r.get("Dst_Port") or r.get("L4_DST_PORT") or r.get("responp") or 80)
            
            proto_raw = (r.get("protocol") or r.get("protocolName") or r.get("protocol_type") or r.get("Protocol Type") or
                         r.get("Proto") or r.get("Protocol") or r.get("PROTOCOL") or "TCP")
            bytes_raw = (r.get("src_bytes") or r.get("totalSourceBytes") or r.get("octets") or r.get("Bytes") or
                         r.get("bytes") or r.get("IN_BYTES") or r.get("Tot size") or r.get("Tot sum") or
                         r.get("Total Length of Fwd Packet") or r.get("tcp.len") or 512)
            attack_raw = (r.get("Attack") or r.get("Attack Type") or r.get("Attack_Type") or
                          r.get("attack_type") or r.get("traffic_category") or r.get("target") or
                          r.get("Category") or r.get("Class") or r.get("traffic_class") or
                          r.get("label") or r.get("Label") or r.get("class") or "normal")

            try:
                src_port = int(str(src_p_raw).strip())
            except Exception:
                src_port = 49152

            try:
                dst_port = int(str(dst_p_raw).strip())
            except Exception:
                dst_port = 80

            try:
                bytes_val = int(float(str(bytes_raw).strip()))
            except Exception:
                bytes_val = 512

            std_record = {
                "src_ip": str(src_ip).strip(),
                "dst_ip": str(dst_ip).strip(),
                "src_port": src_port,
                "dst_port": dst_port,
                "protocol": str(proto_raw).strip(),
                "bytes": bytes_val,
                "attack_label": str(attack_raw).strip(),
            }
            label_clean = std_record["attack_label"].lower().rstrip(".")
            std_record["is_anomaly"] = not (label_clean in ["normal", "benign", "legitimate", "0", "0.0", "false", "---", "background"])

            batch.append(std_record)

            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch


if __name__ == "__main__":
    catalog = DatasetCatalog.list_datasets()
    print(f"NetTwin 3.0 Real Data Loader: {len(catalog)} datasets registered.")
