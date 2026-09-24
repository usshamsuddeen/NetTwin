import os
import sys
import time
import ssl
import urllib.request
import json

ctx = ssl._create_unverified_context()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
target_dir = os.path.join(BASE_DIR, "real_data", "16_ctu13")
os.makedirs(target_dir, exist_ok=True)

url = "https://mcfp.felk.cvut.cz/publicDatasets/CTU-Malware-Capture-Botnet-51/capture20110818.pcap.netflow.labeled"
filename = "CTU-13-Scenario-10-Rbot.netflow.labeled"
dest_path = os.path.join(target_dir, filename)
expected_bytes = 512952178

if os.path.exists(dest_path) and os.path.getsize(dest_path) == expected_bytes:
    print(f"[EXISTS] CTU-13 already downloaded ({expected_bytes:,} bytes). Skipping.")
    sys.exit(0)

print(f"Starting parallel download for CTU-13 Scenario 10 Labeled NetFlow...")
print(f"URL: {url}")
print(f"Destination: {dest_path}")

req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
t0 = time.time()
downloaded = 0

with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
    chunk_size = 1024 * 1024
    with open(dest_path, "wb") as f:
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)

duration = time.time() - t0
final_size = os.path.getsize(dest_path)
print(f"[SUCCESS] CTU-13 downloaded: {final_size:,} bytes in {duration:.1f}s")

info_path = os.path.join(target_dir, "dataset_info.json")
info = {
    "dataset_name": "CTU-13 Scenario 10 Labeled NetFlow (Rbot Botnet)",
    "source_url": url,
    "filename": filename,
    "file_size_bytes": final_size,
    "download_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "description": "Czech Technical University CTU-13 Scenario 10 Rbot Botnet labeled NetFlow (489 MB)"
}
with open(info_path, "w", encoding="utf-8") as f_info:
    json.dump(info, f_info, indent=2)
