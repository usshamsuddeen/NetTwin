import json
import os
import platform
import sys
from pathlib import Path
import subprocess

repo_root = Path(__file__).resolve().parent.parent
dest_file = repo_root / 'papers' / 'paper1_usenix_sec_30datasets' / 'reviewer_artifacts' / 'environment_manifest.json'

packages = {}
try:
    import importlib.metadata
    for pkg in ["numpy", "scipy", "matplotlib", "pytest", "pandas", "scikit-learn", "fastapi", "uvicorn", "pydantic", "httpx", "boto3", "seaborn"]:
        try:
            packages[pkg] = importlib.metadata.version(pkg)
        except Exception:
            packages[pkg] = "not installed"
except Exception:
    pass

env_info = {
    "system": {
        "os_name": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_count_logical": os.cpu_count(),
    },
    "python": {
        "version": sys.version,
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
    },
    "core_dependencies": packages,
    "cloud_reference_baseline": {
        "cloud_provider": "Amazon Web Services (AWS)",
        "instance_family": "c6i.4xlarge (Compute Optimized)",
        "vcpus": 16,
        "ram_gb": 32,
        "storage": "EBS gp3 (10,000 IOPS, 500 MB/s throughput) / NVMe ephemeral cache",
        "networking": "Up to 12.5 Gbps enhanced networking (ENA)",
        "operating_system": "Ubuntu 22.04 LTS / Windows 11 Enterprise"
    },
    "reproducibility_invariants": {
        "global_random_seed": 42,
        "conformal_nominal_coverage_1_minus_alpha": 0.90,
        "aci_gamma_step_size": 0.01,
        "page_hinkley_drift_threshold_lambda": 50.0,
        "page_hinkley_alpha_decay": 0.005,
        "pca_subspace_energy_retained": 0.95
    }
}

with open(dest_file, "w", encoding="utf-8") as f:
    json.dump(env_info, f, indent=2)

print(f"Generated environment manifest at {dest_file}")
