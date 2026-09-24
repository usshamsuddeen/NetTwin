"""
Downloads benchmark datasets referenced in CY0P5_ML_Datasets repository
(https://github.com/ctinnil/CY0P5_ML_Datasets).

Datasets targeted:
1. CIDDS-001 (Coburg Intrusion Detection Dataset 001) -> real_data/14_cidds001/
2. CIDDS-002 (Coburg Intrusion Detection Dataset 002) -> real_data/15_cidds002/
3. CTU-13 Botnet Scenario 10 Labeled NetFlow -> real_data/16_ctu13/
4. Aposemat IoT-23 Scenario 1 PCAP -> real_data/17_iot23/
5. Hornet Honeypot Dataset -> real_data/18_hornet/
6. DARPA 1998 Official Evaluation raw tcpdump -> real_data/01_darpa/
7. DARPA 1998 Truth Week 1 labels -> real_data/01_darpa/
"""

import os
import sys
import time
import ssl
import urllib.request

ctx = ssl._create_unverified_context()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DATA_DIR = os.path.join(BASE_DIR, "real_data")

DOWNLOADS = [
    {
        "name": "Hornet Honeypot Dataset Summary Table",
        "url": "https://mcfp.felk.cvut.cz/publicDatasets/CTU-Hornet-65-Niner/Hornet65niner-Dataset-Summary-Table.csv",
        "target_dir": os.path.join(REAL_DATA_DIR, "18_hornet"),
        "filename": "Hornet65niner-Dataset-Summary-Table.csv",
        "expected_bytes": 2004,
        "description": "Stratosphere Hornet Honeypot multi-country honeypot summary dataset"
    },
    {
        "name": "DARPA 1998 4-Hour Raw Packet Stream (tcpdump.gz)",
        "url": "https://archive.ll.mit.edu/ideval/data/1998/training/four_hours/tcpdump.gz",
        "target_dir": os.path.join(REAL_DATA_DIR, "01_darpa"),
        "filename": "tcpdump_four_hours.gz",
        "expected_bytes": 37365760,
        "description": "MIT Lincoln Lab 1998 Evaluation authentic raw tcpdump packet stream"
    },
    {
        "name": "DARPA 1998 Truth Week 1 Attack Labels",
        "url": "https://archive.ll.mit.edu/ideval/data/1998/Truth_Week_1.llist.tar.gz",
        "target_dir": os.path.join(REAL_DATA_DIR, "01_darpa"),
        "filename": "Truth_Week_1.llist.tar.gz",
        "expected_bytes": 14382725,
        "description": "MIT Lincoln Lab 1998 Week 1 authentic ground truth attack annotations"
    },
    {
        "name": "Aposemat IoT-23 Scenario 1 PCAP Capture",
        "url": "https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/IndividualScenarios/CTU-IoT-Malware-Capture-1-1/2018-05-09-192.168.100.103.pcap",
        "target_dir": os.path.join(REAL_DATA_DIR, "17_iot23"),
        "filename": "CTU-IoT-Malware-Capture-1-1.pcap",
        "expected_bytes": 145928231,
        "description": "Stratosphere Aposemat IoT-23 malware traffic capture (139.2 MB)"
    },
    {
        "name": "CIDDS-002 Coburg Intrusion Detection Dataset",
        "url": "https://www.hs-coburg.de/wp-content/uploads/2024/11/CIDDS-002.zip",
        "target_dir": os.path.join(REAL_DATA_DIR, "15_cidds002"),
        "filename": "CIDDS-002.zip",
        "expected_bytes": 214257978,
        "description": "Hochschule Coburg CIDDS-002 authentic OpenStack NetFlow dataset (204.3 MB)"
    },
    {
        "name": "CIDDS-001 Coburg Intrusion Detection Dataset",
        "url": "https://www.hs-coburg.de/wp-content/uploads/2024/11/CIDDS-001.zip",
        "target_dir": os.path.join(REAL_DATA_DIR, "14_cidds001"),
        "filename": "CIDDS-001.zip",
        "expected_bytes": 402679606,
        "description": "Hochschule Coburg CIDDS-001 authentic small-business NetFlow dataset (384 MB)"
    },
    {
        "name": "CTU-13 Scenario 10 Labeled NetFlow",
        "url": "https://mcfp.felk.cvut.cz/publicDatasets/CTU-Malware-Capture-Botnet-51/capture20110818.pcap.netflow.labeled",
        "target_dir": os.path.join(REAL_DATA_DIR, "16_ctu13"),
        "filename": "CTU-13-Scenario-10-Rbot.netflow.labeled",
        "expected_bytes": 512952178,
        "description": "Czech Technical University CTU-13 Scenario 10 Rbot Botnet labeled NetFlow (489 MB)"
    }
]

def download_file(item):
    name = item["name"]
    url = item["url"]
    target_dir = item["target_dir"]
    filename = item["filename"]
    expected_bytes = item.get("expected_bytes")
    dest_path = os.path.join(target_dir, filename)

    os.makedirs(target_dir, exist_ok=True)

    if os.path.exists(dest_path):
        current_size = os.path.getsize(dest_path)
        if expected_bytes and current_size == expected_bytes:
            print(f"[EXISTS] {name} already downloaded ({current_size:,} bytes). Skipping.")
            return True
        elif expected_bytes and current_size > 0 and current_size != expected_bytes:
            print(f"[INCOMPLETE] {name} has {current_size:,} bytes vs {expected_bytes:,}. Resuming/re-downloading.")

    print(f"\n=======================================================")
    print(f"Downloading: {name}")
    print(f"Source URL:  {url}")
    print(f"Destination: {dest_path}")
    print(f"=======================================================")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    req = urllib.request.Request(url, headers=headers)
    t0 = time.time()
    downloaded = 0

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            total_header = resp.headers.get("Content-Length")
            total_size = int(total_header) if total_header else expected_bytes

            chunk_size = 1024 * 1024  # 1 MB chunk
            last_report = time.time()

            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_report >= 2.0 or (total_size and downloaded >= total_size):
                        elapsed = now - t0
                        speed_mb = (downloaded / (1024 * 1024)) / (elapsed + 0.001)
                        pct = (downloaded / total_size * 100) if total_size else 0
                        mb_done = downloaded / (1024 * 1024)
                        mb_total = (total_size / (1024 * 1024)) if total_size else 0
                        print(f"  --> {mb_done:.1f}/{mb_total:.1f} MB ({pct:.1f}%) | Speed: {speed_mb:.2f} MB/s | Elapsed: {int(elapsed)}s")
                        last_report = now

        duration = time.time() - t0
        final_size = os.path.getsize(dest_path)
        avg_speed = (final_size / (1024 * 1024)) / (duration + 0.001)
        print(f"[SUCCESS] Completed {filename}: {final_size:,} bytes in {duration:.1f}s (Avg {avg_speed:.2f} MB/s)")

        # Create dataset_info.json in the target directory
        info_path = os.path.join(target_dir, "dataset_info.json")
        import json
        info = {
            "dataset_name": name,
            "source_url": url,
            "filename": filename,
            "file_size_bytes": final_size,
            "download_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "description": item.get("description", "")
        }
        with open(info_path, "w", encoding="utf-8") as f_info:
            json.dump(info, f_info, indent=2)

        return True

    except Exception as e:
        print(f"[ERROR] Failed downloading {name}: {e}")
        return False

def main():
    print(f"CY0P5 Benchmark Datasets Downloader")
    print(f"Target directory: {REAL_DATA_DIR}")
    print(f"Datasets queued:  {len(DOWNLOADS)}")

    success_count = 0
    fail_count = 0

    for item in DOWNLOADS:
        ok = download_file(item)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    print("\n=======================================================")
    print(f"Download Summary: {success_count} succeeded, {fail_count} failed")
    print("=======================================================")

if __name__ == "__main__":
    main()
