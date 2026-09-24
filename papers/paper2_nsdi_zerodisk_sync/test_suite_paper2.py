"""Test Suite Runner for Paper 2: NetTwin Zero-Disk Streaming & WAN Sync (NSDI / SIGCOMM).

Target: 27 Tests across 4 modules:
- test_sync.py (10 tests: TVD state fidelity, RMSE bounds, latency sync, drift hysteresis)
- test_syslog.py (6 tests: RFC 5424 ingestion, parsing, security events)
- test_traffic_mirror.py (5 tests: VXLAN packet encapsulation/decapsulation)
- test_ingest_authenticity.py (6 tests: HMAC-SHA256 signature verification, zero-disk buffer)
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
    print("Paper 2 [NSDI/SIGCOMM] — Zero-Disk Streaming & 78ms WAN Digital Twin Sync Test Suite")
    print(f"Targeting: {test_dir}")
    print("=" * 78)
    args = [test_dir] + sys.argv[1:]
    sys.exit(pytest.main(args))

if __name__ == '__main__':
    main()
