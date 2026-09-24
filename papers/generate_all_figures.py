"""Master Publication Figure Generator for all 5 NetTwin Research Papers.

Follows the New Ranked High-Impact Publication Strategy:
1. Paper 1 (28 Years of Intrusion Detection): 7 figures (PNG 300 DPI + vector PDF)
2. Paper 2 (NSDI / SIGCOMM): 7 figures (PNG 300 DPI + vector PDF)
3. Paper 3 (IEEE IoT Journal): 6 figures (PNG 300 DPI + vector PDF)
4. Paper 4 (ACM CCS / NDSS): 6 figures (PNG 300 DPI + vector PDF)
5. Paper 5 (IEEE TIFS / TNSM): 6 figures (PNG 300 DPI + vector PDF)

Total: 32 distinct publication figures (64 files across formats).

Usage:
    python papers/generate_all_figures.py
"""
import os
import sys
import subprocess
import time

PAPERS = [
    ("Paper 1: 28 Years of Intrusion Detection (DARPA 1998 to CIC Darknet 2025)", "paper1_usenix_sec_30datasets"),
    ("Paper 2: NetTwin Zero-Disk Streaming & 78ms WAN Sync (USENIX NSDI / ACM SIGCOMM)", "paper2_nsdi_zerodisk_sync"),
    ("Paper 3: Edge-IIoTset to CIC IoT 2024 Generalization (IEEE IoT Journal)", "paper3_ieee_iot_generalization"),
    ("Paper 4: Sandbox-Gated Thompson Sampling Safe Response (ACM CCS / NDSS)", "paper4_ccs_safe_autonomous_response"),
    ("Paper 5: Conformal-Bounded LLM SOC Analyst (IEEE TIFS / IEEE TNSM)", "paper5_tifs_conformal_llm_soc"),
]


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    start_time = time.time()
    print("=" * 78)
    print("NetTwin 3.0 — Master Publication Figure Generator")
    print("Generating High-Resolution Figures for the 5 Ranked High-Impact Papers")
    print("=" * 78)

    total_generated = 0
    for name, folder in PAPERS:
        script = os.path.join(root, folder, "generate_figures.py")
        if not os.path.exists(script):
            print(f"[!] Warning: Script not found at {script}")
            continue

        print(f"\n>> Executing: {name} ...")
        cmd = [sys.executable, script]
        ret = subprocess.run(cmd, cwd=root)
        if ret.returncode != 0:
            print(f"[ERROR] Failed generating figures for {folder}")
        else:
            fig_dir = os.path.join(root, folder, "figures")
            files = [f for f in os.listdir(fig_dir) if f.endswith(('.png', '.pdf'))]
            total_generated += len(files)
            print(f"[{folder}] Status: OK ({len(files)} files present in figures/)")

    elapsed = time.time() - start_time
    print("\n" + "=" * 78)
    print(f"COMPLETE: Generated/Verified {total_generated} figure files across all 5 papers in {elapsed:.2f}s")
    print("=" * 78)


if __name__ == '__main__':
    main()
