import json
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
manifest_path = repo_root / 'real_data' / 'manifest.json'
with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

dest_dir = repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'reviewer_artifacts'
dest_dir.mkdir(parents=True, exist_ok=True)

inventory = {
    'title': 'NetTwin 3.0 — 30 Intrusion Detection Benchmarks (1998-2026) Official Reviewer Inventory',
    'total_datasets': manifest.get('total_datasets', 30),
    'evaluation_scope': '418,951 Evaluated Flow Records across 4 Research Eras',
    'methodology_disclosure': manifest.get('methodology_disclosure', '9.19 GB Staged Reproducible Partitions vs ~60 GB Full Uncompressed Published Corpora'),
    'datasets': []
}

for ds in manifest.get('datasets', []):
    item = {
        'id': ds.get('id'),
        'dataset_name': ds.get('dataset_name'),
        'year': ds.get('year'),
        'developed_by': ds.get('developed_by'),
        'features': ds.get('features'),
        'attack_types': ds.get('attack_types'),
        'source_url': ds.get('source_url'),
        'staged_rows': ds.get('staged_rows'),
        'full_rows': ds.get('full_rows'),
        'staged_size_mb': ds.get('staged_size_mb'),
        'full_corpus_size_gb': ds.get('full_corpus_size_gb'),
        'evaluation_honesty_note': ds.get('evaluation_honesty_note')
    }
    inventory['datasets'].append(item)

out_file = dest_dir / 'benchmark_data_inventory.json'
with open(out_file, 'w', encoding='utf-8') as f:
    json.dump(inventory, f, indent=2)

print(f"Wrote {len(inventory['datasets'])} datasets to {out_file}")
