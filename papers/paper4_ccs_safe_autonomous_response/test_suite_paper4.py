"""Test Suite Runner for Paper 4: Sandbox-Gated Thompson Sampling Safe Response (ACM CCS / NDSS).

Target: 19 Tests across 4 modules:
- test_response.py (6 tests: Thompson Sampling bandit, action selection, kill switch latch)
- test_fork.py (4 tests: copy-on-write twin sandbox isolation)
- test_whatif.py (4 tests: counterfactual simulation, SLA preservation)
- test_scenario.py (5 tests: multi-threat resilience validation)
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
    print("Paper 4 [ACM CCS] — Sandbox-Gated Safe Autonomous Response Test Suite")
    print(f"Targeting: {test_dir}")
    print("=" * 78)
    args = [test_dir] + sys.argv[1:]
    sys.exit(pytest.main(args))

if __name__ == '__main__':
    main()
