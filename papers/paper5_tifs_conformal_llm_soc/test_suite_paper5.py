"""Test Suite Runner for Paper 5: Conformal-Bounded LLM SOC Analyst (IEEE TIFS / IEEE TNSM).

Target: 61 Tests across 12 modules:
- test_llm.py (6 tests: LLM prompt construction, conformal p-value injection, RAG retrieval)
- test_actuation.py (7 tests: closed-loop cloud actuation, WAF IPSet, SG isolation)
- test_aws_streamer.py (4 tests: zero-disk S3 streaming client)
- test_multi_region_infra.py (5 tests: dual-region routing, latency tracking)
- test_aws_3tier_topology.py (6 tests: production cloud topology)
- test_aws_3tier_scenarios.py (5 tests: production threat response)
- test_org_onboarding.py (4 tests: organization onboarding)
- test_storage.py (5 tests: metric and event storage)
- test_integrations.py (5 tests: webhook, slack, pagerduty integrations)
- test_security.py (5 tests: token auth, RBAC, API security)
- test_api.py (5 tests: REST endpoints)
- test_simulator.py (4 tests: discrete-event simulator engine)
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
    print("Paper 5 [IEEE TIFS/TNSM] — Conformal-Bounded LLM SOC Analyst Test Suite")
    print(f"Targeting: {test_dir}")
    print("=" * 78)
    args = [test_dir] + sys.argv[1:]
    sys.exit(pytest.main(args))

if __name__ == '__main__':
    main()
