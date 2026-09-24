"""Script to reorganize NetTwin 3.0 research papers to the new High-Impact Ranking.

New 5 Ranked Papers:
1. Paper 1: "28 Years of Intrusion Detection: A Reproducible Evaluation of 30 Benchmarks from DARPA 1998 to CIC IoT 2024 with Conformal Guarantees" (USENIX Security / IEEE S&P)
2. Paper 2: "NetTwin: Zero-Disk Streaming of 450GB Intrusion Benchmarks Across 78ms WAN for High-Fidelity Digital Twin Sync" (USENIX NSDI / ACM SIGCOMM)
3. Paper 3: "Edge-IIoTset to CIC IoT 2024: How Well Do Modern IDSes Generalize Across 12 IoT/5G Datasets Spanning 2020-2026?" (IEEE Internet of Things Journal)
4. Paper 4: "Sandbox-Gated Thompson Sampling: Safe Autonomous Response with Zero Accidental Mutation via Counterfactual Twin Clones" (ACM CCS / NDSS)
5. Paper 5: "When LLMs Meet Conformal Prediction: Uncertainty-Aware SOC Analyst with RAG over MITRE ATT&CK and 30 Datasets" (IEEE TIFS / IEEE TNSM)
"""
import os
import shutil

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PAPERS_DIR = os.path.join(REPO_ROOT, 'papers')

NEW_PAPERS = {
    'paper1_usenix_sec_30datasets': {
        'src_paper': 'paper2_usenix_conformal',
        'title': '28 Years of Intrusion Detection: A Reproducible Evaluation of 30 Benchmarks from DARPA 1998 to CIC IoT 2024 with Conformal Guarantees',
        'venue': 'USENIX Security 2027 / IEEE S&P 2027 (Dataset/Measurement Track)',
        'target_tests': [
            'test_all_30_datasets.py',
            'test_subspace_conformal.py',
            'test_aci_and_weights.py',
            'test_detector.py',
            'test_west_generator.py'
        ]
    },
    'paper2_nsdi_zerodisk_sync': {
        'src_paper': 'paper1_nsdi_sync',
        'title': 'NetTwin: Zero-Disk Streaming of 450GB Intrusion Benchmarks Across 78ms WAN for High-Fidelity Digital Twin Sync',
        'venue': 'USENIX NSDI 2027 / ACM SIGCOMM 2027 (Systems Track)',
        'target_tests': [
            'test_sync.py',
            'test_syslog.py',
            'test_traffic_mirror.py',
            'test_ingest_authenticity.py'
        ]
    },
    'paper3_ieee_iot_generalization': {
        'src_paper': 'paper3_ccs_causal_risk',
        'title': 'Edge-IIoTset to CIC IoT 2024: How Well Do Modern IDSes Generalize Across 12 IoT/5G Datasets Spanning 2020-2026?',
        'venue': 'IEEE Internet of Things Journal (IF 10.6) / ACM IoTDI 2027 / NDSS 2027 IoT Track',
        'target_tests': [
            'test_causal.py',
            'test_risk.py',
            'test_kb.py',
            'test_attack_kb_update.py'
        ]
    },
    'paper4_ccs_safe_autonomous_response': {
        'src_paper': 'paper4_ndss_autonomous_mitigation',
        'title': 'Sandbox-Gated Thompson Sampling: Safe Autonomous Response with Zero Accidental Mutation via Counterfactual Twin Clones',
        'venue': 'ACM CCS 2027 (Moving Target Defense / Automated Response Session) / NDSS 2027',
        'target_tests': [
            'test_response.py',
            'test_fork.py',
            'test_whatif.py',
            'test_scenario.py'
        ]
    },
    'paper5_tifs_conformal_llm_soc': {
        'src_paper': 'paper5_tnsm_aws_closed_loop',
        'title': 'When LLMs Meet Conformal Prediction: Uncertainty-Aware SOC Analyst with RAG over MITRE ATT&CK and 30 Datasets',
        'venue': 'IEEE TIFS / IEEE TNSM / USENIX Security 2027 AI Sec Workshop',
        'target_tests': [
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
}

def main():
    print("Reorganizing papers to the new high-impact 5-paper structure...")
    for folder, meta in NEW_PAPERS.items():
        dst_dir = os.path.join(PAPERS_DIR, folder)
        os.makedirs(os.path.join(dst_dir, 'figures'), exist_ok=True)
        os.makedirs(os.path.join(dst_dir, 'tests'), exist_ok=True)
        
        src_tests_dir = os.path.join(PAPERS_DIR, meta['src_paper'], 'tests')
        for t_file in meta['target_tests']:
            src_file = os.path.join(src_tests_dir, t_file)
            dst_file = os.path.join(dst_dir, 'tests', t_file)
            if os.path.exists(src_file):
                shutil.copy2(src_file, dst_file)
                print(f"Copied {t_file} -> {folder}/tests/")
            else:
                print(f"[!] Warning: {src_file} not found")
                
    print("Reorganization directory scaffolding complete.")

if __name__ == '__main__':
    main()
