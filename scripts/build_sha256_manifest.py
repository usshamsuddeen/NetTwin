import hashlib
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
target_checksum_file = repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'reviewer_artifacts' / 'sha256_checksums.txt'

files_to_hash = [
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_0a_methodology.png',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_0a_methodology.pdf',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_0b_experimental_setup.png',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_0b_experimental_setup.pdf',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_0c_behavior_paradigm.png',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_0c_behavior_paradigm.pdf',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_1_historical_timeline_28_years_detection.png',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_1_historical_timeline_28_years_detection.pdf',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_2_all_30_datasets_detection_and_coverage.png',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_2_all_30_datasets_detection_and_coverage.pdf',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_3_concept_drift_disambiguation_eras.png',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_3_concept_drift_disambiguation_eras.pdf',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_4_dataset_scale_staged_vs_full_disclosure.png',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_4_dataset_scale_staged_vs_full_disclosure.pdf',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_5_conformal_calibration_and_coverage_delta.png',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_5_conformal_calibration_and_coverage_delta.pdf',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_6_adaptive_conformal_aci_ablation.png',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'figures' / 'fig1_6_adaptive_conformal_aci_ablation.pdf',

    # Tests (5 files)
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'tests' / 'test_all_30_datasets.py',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'tests' / 'test_subspace_conformal.py',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'tests' / 'test_aci_and_weights.py',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'tests' / 'test_detector.py',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'tests' / 'test_west_generator.py',

    # Scripts & Data (10 files)
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'generate_figures.py',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'test_suite_paper1.py',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'README.md',
    repo_root / 'eval' / 'results' / 'dataset_coverage.csv',
    repo_root / 'real_data' / 'manifest.json',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'reviewer_artifacts' / 'benchmark_data_inventory.json',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'reviewer_artifacts' / 'dataset_coverage.csv',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'reviewer_artifacts' / 'environment_manifest.json',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'reviewer_artifacts' / 'CLAIMS_AND_EVALUATION_MAPPING.md',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'reviewer_artifacts' / 'RUNBOOK_FOR_REVIEWERS.md',
    repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'reviewer_artifacts' / 'verify_reproducibility.py',
]

lines = ["# SHA-256 Cryptographic Checksum Manifest for Paper 1 Artifacts",
         "# Generated for Artifact Evaluation Committee Verification",
         "# Format: <sha256_hash>  <relative_filepath>\n"]

for p in files_to_hash:
    if p.exists():
        hasher = hashlib.sha256()
        with open(p, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        rel_path = p.relative_to(repo_root).as_posix()
        lines.append(f"{hasher.hexdigest()}  {rel_path}")
    else:
        print(f"Warning: Missing file {p}")

with open(target_checksum_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print(f"Wrote {len(lines)-3} SHA-256 hashes to {target_checksum_file}")
