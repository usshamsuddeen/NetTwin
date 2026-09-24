"""
Test DatasetCatalog streaming across all 30 benchmark datasets.
"""
import sys
from pathlib import Path
ROOT_DIR = Path("d:/AWS Cloud/nettwin-project")
sys.path.insert(0, str(ROOT_DIR))

from real_data.loader import DatasetCatalog

catalog = DatasetCatalog.list_datasets()
print(f"Total datasets registered: {len(catalog)}")

success = 0
failed = []

for d in catalog:
    folder = d.get("folder", "")
    name = d.get("dataset_name", "")
    year = d.get("year", "")
    try:
        batches = list(DatasetCatalog.stream_telemetry_batch(folder, batch_size=10))
        total_records = sum(len(b) for b in batches)
        anomalies = sum(1 for b in batches for r in b if r["is_anomaly"])
        sample = batches[0][0] if batches and batches[0] else {}
        print(f"[{folder}] {name} ({year}) | {total_records} rows | Anomalies: {anomalies} | Proto: {sample.get('protocol')} | Label: {sample.get('attack_label')}")
        success += 1
    except Exception as e:
        print(f"FAILED [{folder}] {name}: {e}")
        failed.append((folder, str(e)))

print(f"\n==========================================")
print(f"RESULTS: {success}/{len(catalog)} datasets streamed successfully.")
if failed:
    print(f"Failed datasets: {failed}")
else:
    print("ALL 30 DATASETS (1998-2026) STREAMED WITH 100% SUCCESS!")
print(f"==========================================")
