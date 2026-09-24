"""Test Suite Runner for Paper 1: 28 Years of Intrusion Detection.

Target: 44 Tests across 5 modules:
- test_all_30_datasets.py (18 tests: 30 datasets streamed and validated)
- test_subspace_conformal.py (7 tests: conformal coverage bounds)
- test_aci_and_weights.py (8 tests: concept drift tracking and ACI)
- test_detector.py (8 tests: subspace anomaly detector)
- test_west_generator.py (3 tests: replay across formats)
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
    print("Paper 1: 28 Years of Intrusion Detection Test Suite")
    print(f"Targeting: {test_dir}")
    print("=" * 78)
    args = [test_dir] + sys.argv[1:]
    sys.exit(pytest.main(args))

if __name__ == '__main__':
    main()
