"""Test Suite Runner for Paper 3: Edge-IIoTset to CIC IoT 2024: Generalization Across 12 IoT/5G Datasets (IEEE IoT Journal).

Target: 18 Tests across 6 modules:
- test_iot_12_datasets_integrity.py (4 tests: 12 datasets existence, year >= 2020, 212 MB disclosure, attack taxonomy)
- test_iot_generalization_eval.py (4 tests: cross-dataset generalization drop, protocol classes, conformal bounds)
- test_causal.py (4 tests: topological attack graph causal discovery)
- test_risk.py (2 tests: multi-hop threat propagation risk)
- test_kb.py (2 tests: threat intelligence knowledge base)
- test_attack_kb_update.py (2 tests: dynamic CVE and attack graph updating)
"""
import os
import sys
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

def main():
    test_dir = os.path.join(os.path.dirname(__file__), 'tests')
    print("=" * 78)
    print("Paper 3 [IEEE IoT Journal] — 12 IoT/5G Benchmarks Generalization Test Suite")
    print(f"Targeting: {test_dir}")
    print("=" * 78)
    args = [test_dir] + sys.argv[1:]
    sys.exit(pytest.main(args))

if __name__ == '__main__':
    main()
