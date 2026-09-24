"""Setup and organize paper test suites with proper sys.path and root directory handling."""
import os
import shutil
from pathlib import Path

MAPPING = {
    'paper1_nsdi_sync': [
        'test_sync.py',
        'test_syslog.py',
        'test_traffic_mirror.py',
        'test_ingest_authenticity.py'
    ],
    'paper2_usenix_conformal': [
        'test_detector.py',
        'test_subspace_conformal.py',
        'test_aci_and_weights.py',
        'test_all_30_datasets.py',
        'test_west_generator.py'
    ],
    'paper3_ccs_causal_risk': [
        'test_causal.py',
        'test_risk.py',
        'test_kb.py',
        'test_attack_kb_update.py'
    ],
    'paper4_ndss_autonomous_mitigation': [
        'test_response.py',
        'test_fork.py',
        'test_whatif.py',
        'test_scenario.py'
    ],
    'paper5_tnsm_aws_closed_loop': [
        'test_actuation.py',
        'test_aws_streamer.py',
        'test_multi_region_infra.py',
        'test_aws_3tier_topology.py',
        'test_aws_3tier_scenarios.py',
        'test_org_onboarding.py',
        'test_llm.py',
        'test_storage.py',
        'test_integrations.py',
        'test_security.py',
        'test_api.py',
        'test_simulator.py'
    ]
}

def insert_preamble(content: str) -> str:
    lines = content.splitlines(keepends=True)
    insert_idx = 0
    in_docstring = False
    doc_quote = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not in_docstring:
            if s.startswith('"""') or s.startswith("'''"):
                doc_quote = '"""' if s.startswith('"""') else "'''"
                rest = s[3:]
                if doc_quote in rest:
                    insert_idx = i + 1
                    continue
                else:
                    in_docstring = True
                    continue
            elif s.startswith('from __future__') or s.startswith('#') or s == '':
                insert_idx = i + 1
                continue
            else:
                break
        else:
            if doc_quote in s:
                in_docstring = False
                insert_idx = i + 1
                continue

    preamble = (
        "\nimport os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))\n"
        "_REPO_ROOT_PATH = Path(_REPO_ROOT)\n"
        "if _REPO_ROOT not in sys.path:\n"
        "    sys.path.insert(0, _REPO_ROOT)\n\n"
    )
    result = ''.join(lines[:insert_idx]) + preamble + ''.join(lines[insert_idx:])
    # Replace relative path parent references that expect original tests/ directory depth
    result = result.replace('Path(__file__).resolve().parent.parent', '_REPO_ROOT_PATH')
    return result

def main():
    total = 0
    for paper_dir, test_files in MAPPING.items():
        dst_dir = os.path.join('papers', paper_dir, 'tests')
        os.makedirs(dst_dir, exist_ok=True)
        for test_file in test_files:
            src = os.path.join('tests', test_file)
            dst = os.path.join(dst_dir, test_file)
            with open(src, 'r', encoding='utf-8') as f_in:
                raw = f_in.read()
            final_code = insert_preamble(raw)
            with open(dst, 'w', encoding='utf-8') as f_out:
                f_out.write(final_code)
            total += 1
            print(f"[{paper_dir}] -> {test_file}")
    print(f"\nSuccessfully populated {total} test files across 5 papers.")

if __name__ == '__main__':
    main()
