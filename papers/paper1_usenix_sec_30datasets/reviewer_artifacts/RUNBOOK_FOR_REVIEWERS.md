# Artifact Evaluation Runbook for Reviewers
## Paper 1: 28 Years Elapsed [29 Years Inclusive] of Intrusion Detection: A Reproducible Evaluation of 30 Benchmarks from DARPA 1998 to ASEADOS-SDN-IoT 2026 with Conformal Guarantees

This document is the official evaluation guide prepared for the **Artifact Evaluation Committee (AEC)**. It provides step-by-step instructions to independently execute, audit, and reproduce all empirical results, mathematical guarantees, figures, and benchmark telemetry tables presented in Paper 1.

---

### 1. Targeted Artifact Badges

This artifact is submitted for evaluation targeting all three standard ACM/USENIX Artifact Badges:

```
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│   ARTIFACTS AVAILABLE   │  │   ARTIFACTS EVALUATED   │  │    RESULTS REPRODUCED   │
│                         │  │       FUNCTIONAL        │  │                         │
│ Complete open codebase, │  │ Clean installation,     │  │ Exact quantitative      │
│ 30 benchmark manifests, │  │ documented APIs, 46/46  │  │ replication of all 30   │
│ & raw data partitions   │  │ green unit/invariant tests│ benchmarks & 7 figures  │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
```

---

### 2. System Prerequisites & Hardware Specifications

#### Minimum Hardware Requirements
- **CPU:** Dual-core x86_64 or ARM64 processor (Tested on AMD Ryzen / Intel Core i7 / AWS Graviton / AWS `c6i.4xlarge`)
- **RAM:** Minimum 4 GB available system memory (8 GB recommended for full parallel sweeps)
- **Disk Space:** ~500 MB for repository code, manifests, and staged test partitions (9.21 GB full evaluation partitions optional)
- **Operating System:** Linux (Ubuntu 20.04/22.04 LTS, Debian 11/12), macOS (12+), or Windows (10/11 64-bit)

#### Software Environment
- **Python:** Python 3.10, 3.11, 3.12, or 3.13 (CPython 64-bit)
- **Virtual Environment:** Recommended (`venv` or `conda`)

```bash
# 1. Clone repository (or extract supplementary zip)
cd nettwin-project

# 2. Create isolated virtual environment
python -m venv .venv

# 3. Activate environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows (cmd/PowerShell):
.venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

### 3. One-Click Verification (Recommended for AEC)

We provide an automated, standalone reproducibility verification script that executes all tests, computes cryptographic checksums, evaluates the 30 benchmarks, inspects the 9 publication figures (18 dual PNG + PDF files), and outputs an audit certificate:

```bash
# Quick verification (~5 seconds: tests core invariants, figures, checksums)
python papers/paper1_usenix_sec_30datasets/reviewer_artifacts/verify_reproducibility.py --quick

# Full reproducibility verification (~2-3 minutes: runs complete 46-test suite and 30-dataset sweep)
python papers/paper1_usenix_sec_30datasets/reviewer_artifacts/verify_reproducibility.py --full
```

#### Expected One-Click Output
When execution finishes successfully, the verifier produces a green banner:
```
[PASS] Step 1: Environment & Dependency Validation (Python 3.12+, NumPy, SciPy, PyTest)
[PASS] Step 2: Cryptographic Hash Verification (Figures, Manifests, Evaluation Data)
[PASS] Step 3: Paper 1 Formal Invariant Test Suite (46 passed in ~3s, 100% green)
[PASS] Step 4: 30-Benchmark Empirical Evaluation Sweep:
       -> Mean Detection Rate: 97.49% (Target: >=97.0%)
       -> Mean Conformal Coverage: 92.47% (Target: >=90.0% Marginal Bound)
       -> Drift False Positive Rate: < 3.0% (Target: < 3.0%)
[PASS] Step 5: Publication Figures Verification (9 PNGs @ 300 DPI + 9 Vector PDFs)

================================================================================
>>> REPRODUCIBILITY AUDIT: 100% VERIFIED & AUTHENTIC <<<
Certificate written to: papers/paper1_usenix_sec_30datasets/reviewer_artifacts/REPRODUCIBILITY_CERTIFICATE.json
================================================================================
```

---

### 4. Modular Step-by-Step Verification Protocol

If you prefer to inspect and execute each experimental component manually:

#### Step 4.1: Audit the 30 Benchmark Catalog & Manifest
Inspect the machine-readable inventory documenting all 30 datasets from 1998 to 2026:
```bash
# View metadata summary for all 30 benchmarks
cat papers/paper1_usenix_sec_30datasets/reviewer_artifacts/dataset_coverage.csv

# Or inspect JSON metadata schema
cat papers/paper1_usenix_sec_30datasets/reviewer_artifacts/benchmark_data_inventory.json
```
**Verification Check:** Confirm exactly 30 datasets exist, categorized across 4 historical eras:
- Foundational (1998–2005): 4 datasets (DARPA 98/99, KDD 99, LBNL, Kyoto)
- Modern Enterprise (2006–2014): 7 datasets (NSL-KDD, DEFCON, CAIDA, CDX, Twente, ISCX, ADFA)
- Cloud & Hybrid (2015–2019): 6 datasets (CIC-IDS2017, CSE-CIC-IDS2018, CIDDS-001/002, CTU-13, IoT-23)
- Next-Gen IoT/5G/SDN (2020–2026): 13 datasets (TRUSTLab 2026, BCCC-DarkNet-2025, ToN_IoT, Bot-IoT, MQTT-IoT, Edge-IIoTset, CIC IoT 2022/2023/2024, MalMem, HIKARI, 5G-NIDD, CIC-EIoT2025, ASEADOS-SDN-IoT 2026)

#### Step 4.2: Execute the 46-Test Formal Suite
Run pytest on the Paper 1 test suite:
```bash
python -m pytest papers/paper1_usenix_sec_30datasets/tests/ -v
```
**Verification Check:**
- 46 tests collected, 46 passed in $\approx 3$ seconds.
- Invariants checked: PCA projection idempotence, normal/anomaly subspace orthogonality, conformal coverage $\mathbb{P}(\mathbf{x} \in C) \ge 1-\alpha$, Page-Hinkley cumulative sum reset, and live streaming packet normalization.

#### Step 4.3: Execute the 30-Benchmark Conformal Evaluation
Run the standalone evaluation module across all 30 datasets:
```bash
python -m eval.p2_detect --all-datasets
```
**Verification Check:**
- The script prints the unified Table A in your terminal.
- Terminal output confirms:
  ```
  Mean Detection Rate: 97.49%
  Mean Conformal Coverage: 92.47%
  Finite-Sample Invariant (>= 90.0%): SATISFIED across all 30 benchmarks
  ```

#### Step 4.4: Re-render Publication Figures
Regenerate all 9 figures in high-resolution PNG (300 DPI) and Vector PDF:
```bash
python papers/paper1_usenix_sec_30datasets/generate_figures.py
```
**Verification Check:**
- Maintains 18 files (9 publication figures in dual 300 DPI PNG + vector PDF) in `papers/paper1_usenix_sec_30datasets/figures/`.
- Inspect any figure with an image viewer or PDF viewer:
  - `fig1_0a_methodology.png` / `.pdf`: NetTwin 6-stage end-to-end methodology & mathematical dataflow (Figure 1).
  - `fig1_0c_behavior_paradigm.png` / `.pdf`: Behavioral anomaly detection paradigm vs legacy signature matching (Figure 2).
  - `fig1_0b_experimental_setup.png` / `.pdf`: AEC reviewer experimental setup, 30 datasets across 4 eras, and pinned parameters (Figure 3).
  - `fig1_1_historical_timeline_28_years_detection.png`: 28-year timeline across 4 research eras.
  - `fig1_2_all_30_datasets_detection_and_coverage.png`: Dual horizontal bar plot of detection rate and coverage.
  - `fig1_3_concept_drift_disambiguation_eras.png`: Diurnal benign drift vs cyber attack burst.
  - `fig1_4_dataset_scale_staged_vs_full_disclosure.png`: 9.21 GB staged vs ~65 GB full public corpus.
  - `fig1_5_conformal_calibration_and_coverage_delta.png`: Reliability diagram and coverage excess $\Delta_i \ge 0$.
  - `fig1_6_adaptive_conformal_aci_ablation.png`: ACI step size $\gamma$ recovery latency.

---

### 5. Troubleshooting & FAQ

- **Q: On headless Linux servers, matplotlib complains about a missing display (`$DISPLAY`).**  
  *A:* NetTwin automatically sets `matplotlib.use('Agg')` in `generate_figures.py` before importing pyplot, ensuring non-interactive background rendering without X11 or Wayland dependencies.
- **Q: Windows PowerShell displays encoding warnings or unicode question marks.**  
  *A:* All runner scripts configure `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` automatically to preserve box-drawing characters and mathematical symbols.
- **Q: How long does full replication take?**  
  *A:* On a modern 8-core laptop or desktop, the entire pipeline (tests + evaluation + figure generation + certificate generation) takes under **3 minutes**.
