"""Paper Test Suite Orchestrator.

Executes tests mapped to specific research papers or all papers combined according to the new high-impact ranking.

Usage:
    python papers/run_paper_tests.py --paper 1          # Run Paper 1 test suite (46 tests)
    python papers/run_paper_tests.py --paper 2          # Run Paper 2 test suite (27 tests) [NSDI/SIGCOMM]
    python papers/run_paper_tests.py --paper 3          # Run Paper 3 test suite (18 tests) [IEEE IoT Journal]
    python papers/run_paper_tests.py --paper 4          # Run Paper 4 test suite (19 tests) [ACM CCS/NDSS]
    python papers/run_paper_tests.py --paper 5          # Run Paper 5 test suite (61 tests) [IEEE TIFS/TNSM]
    python papers/run_paper_tests.py --paper all        # Run All Paper test suites (171 tests)
    python papers/run_paper_tests.py --paper 1 -v       # Pass additional pytest flags
"""
import os
import sys
import argparse
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

PAPER_DIRECTORIES = {
    '1': ('Paper 1: 28 Years Elapsed [29 Years Inclusive] of Intrusion Detection: Reproducible Eval of 30 Benchmarks (DARPA 1998 to ASEADOS-SDN-IoT 2026)', 'paper1_usenix_sec_30datasets'),
    '2': ('Paper 2: NetTwin: Zero-Disk Streaming of 450GB Benchmarks Across 78ms WAN (NSDI/SIGCOMM)', 'paper2_nsdi_zerodisk_sync'),
    '3': ('Paper 3: Edge-IIoTset to CIC IoT 2024: Generalization Across 12 IoT/5G Datasets (IEEE IoT Journal)', 'paper3_ieee_iot_generalization'),
    '4': ('Paper 4: Sandbox-Gated Thompson Sampling: Safe Autonomous Response (ACM CCS/NDSS)', 'paper4_ccs_safe_autonomous_response'),
    '5': ('Paper 5: When LLMs Meet Conformal Prediction: Uncertainty-Aware SOC Analyst (IEEE TIFS/TNSM)', 'paper5_tifs_conformal_llm_soc'),
}


def run_tests_for_paper(paper_key: str, extra_args: list) -> int:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if paper_key.lower() == 'all':
        test_dirs = [os.path.join(base_dir, info[1], 'tests') for info in PAPER_DIRECTORIES.values()]
        print("=" * 78)
        print("Running COMPLETE Unified Test Suite Across All 5 Papers (171 Tests)")
        print("=" * 78)
    else:
        if paper_key not in PAPER_DIRECTORIES:
            print(f"Error: Unknown paper key '{paper_key}'. Choose from 1, 2, 3, 4, 5, or all.")
            return 1
        desc, folder = PAPER_DIRECTORIES[paper_key]
        test_dirs = [os.path.join(base_dir, folder, 'tests')]
        print("=" * 78)
        print(f"Running Test Suite: {desc}")
        print("=" * 78)

    cmd_args = test_dirs + extra_args
    print(f"Pytest target paths: {test_dirs}")
    return pytest.main(cmd_args)


def main():
    parser = argparse.ArgumentParser(description="Run test suites mapped to specific research papers.")
    parser.add_argument('-p', '--paper', default='all', choices=['1', '2', '3', '4', '5', 'all'],
                        help="Paper index to test (1 to 5, or 'all')")
    args, unknown = parser.parse_known_args()

    exit_code = run_tests_for_paper(args.paper, unknown)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
