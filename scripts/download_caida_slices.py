"""
Downloads official CAIDA DDoS 2007 dataset slices from:
https://publicdata.caida.org/datasets/security/ddos-20070804/
and extracts authentic network flow records into real_data/05_caida/.
"""
import gzip
import time
import urllib.request
from pathlib import Path
import dpkt

BASE_URL = "https://publicdata.caida.org/datasets/security/ddos-20070804/"
DEST_DIR = Path(__file__).resolve().parent.parent / "real_data" / "05_caida"
DEST_DIR.mkdir(parents=True, exist_ok=True)

FILES_TO_DOWNLOAD = [
    "README",
    "md5.md5",
    "ddostrace.20070804_134936.pcap.stats",
    "ddostrace.20070804_135436.pcap.gz",
    "ddostrace.20070804_135436.pcap.stats",
    "ddostrace.20070804_135936.pcap.gz",
    "ddostrace.20070804_135936.pcap.stats",
    "ddostrace.20070804_140436.pcap.gz",
    "ddostrace.20070804_140436.pcap.stats",
    "ddostrace.20070804_140936.pcap.gz",
    "ddostrace.20070804_140936.pcap.stats",
]

def download_file(filename: str) -> bool:
    dest_path = DEST_DIR / filename
    if dest_path.exists() and dest_path.stat().st_size > 0:
        print(f"[SKIP] {filename} already exists ({dest_path.stat().st_size} bytes)")
        return True

    url = BASE_URL + filename
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    print(f"[DOWNLOADING] {filename} from CAIDA...")
    start_t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        elapsed = time.time() - start_t
        sz = dest_path.stat().st_size
        print(f"[SUCCESS] {filename} ({sz / 1024:.1f} KB) in {elapsed:.1f}s")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to download {filename}: {e}")
        return False

def extract_real_caida_flows(max_flows=25000):
    """Parses real downloaded PCAPs and produces an authentic flow feature CSV."""
    pcap_gz_files = sorted(DEST_DIR.glob("*.pcap.gz"))
    if not pcap_gz_files:
        print("No PCAP.GZ files found to parse.")
        return

    csv_out = DEST_DIR / "caida_ddos_2007_real_flows.csv"
    print(f"\nExtracting up to {max_flows} authentic flows from CAIDA PCAP files...")

    header = [
        "timestamp", "src_ip", "src_port", "dst_ip", "dst_port", 
        "protocol", "packet_size", "tcp_flags", "ttl", "attack_type", "label"
    ]

    total_extracted = 0
    with open(csv_out, "w", encoding="utf-8") as out:
        out.write(",".join(header) + "\n")

        for pcap_path in pcap_gz_files:
            print(f"  Parsing {pcap_path.name}...")
            try:
                with gzip.open(pcap_path, "rb") as gz:
                    pcap = dpkt.pcap.Reader(gz)
                    for ts, buf in pcap:
                        try:
                            # CAIDA PCAPs use DLT_RAW (101), so buf starts directly with IPv4 header
                            if len(buf) < 20:
                                continue
                            ip = dpkt.ip.IP(buf)
                            proto = "TCP" if ip.p == dpkt.ip.IP_PROTO_TCP else ("UDP" if ip.p == dpkt.ip.IP_PROTO_UDP else "ICMP")
                            
                            src_ip = f"{ip.src[0]}.{ip.src[1]}.{ip.src[2]}.{ip.src[3]}"
                            dst_ip = f"{ip.dst[0]}.{ip.dst[1]}.{ip.dst[2]}.{ip.dst[3]}"
                            src_port = getattr(ip.data, "sport", 0) if hasattr(ip.data, "sport") else 0
                            dst_port = getattr(ip.data, "dport", 0) if hasattr(ip.data, "dport") else 0
                            flags = getattr(ip.data, "flags", 0) if proto == "TCP" and hasattr(ip.data, "flags") else 0
                            
                            is_syn = (flags & dpkt.tcp.TH_SYN) != 0 and (flags & dpkt.tcp.TH_ACK) == 0
                            attack_type = "SYN Flood" if is_syn else ("ICMP Flood" if proto == "ICMP" else "Volumetric DDoS")
                            label = "DDoS"

                            out.write(f"{ts:.6f},{src_ip},{src_port},{dst_ip},{dst_port},{proto},{len(buf)},{flags},{ip.ttl},{attack_type},{label}\n")
                            total_extracted += 1

                            if total_extracted >= max_flows:
                                break
                        except Exception:
                            continue
            except Exception as exc:
                print(f"  Error reading {pcap_path.name}: {exc}")

            if total_extracted >= max_flows:
                break

    print(f"\n[DONE] Successfully extracted {total_extracted} REAL CAIDA flows into {csv_out.name} ({csv_out.stat().st_size / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    print("Starting CAIDA DDoS 2007 dataset download...")
    for fn in FILES_TO_DOWNLOAD:
        download_file(fn)
    extract_real_caida_flows()
