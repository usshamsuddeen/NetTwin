"""Causal root-cause test: injected DDoS must rank the attack path top."""
from nettwin.config import Settings
from nettwin.simulator.engine import SimulationEngine
from nettwin.twin.causal import CausalAnalyzer
from nettwin.twin.detector import AnomalyDetector
from nettwin.twin.state import TwinState

ATTACK_PATH = {"web1", "attacker", "edge3", "edge3-web1", "dist2", "dist2-edge3",
               "core1", "core1-dist2", "fw1", "fw1-core1", "igw", "igw-fw1",
               "attacker-igw"}


def _setup_attack():
    s = Settings()
    eng = SimulationEngine(s)
    twin = TwinState(s)
    det = AnomalyDetector(s.detector)
    for _ in range(s.detector.warmup_ticks + 30):
        tick = eng.step()
        twin.update(tick)
        det.update(tick)
    eng.start_attack("ddos", target_id="web1", duration_s=None)
    for _ in range(25):
        tick = eng.step()
        twin.update(tick)
        det.update(tick)
    return s, eng, twin, det


def test_root_cause_ranks_attack_path_top():
    s, eng, twin, det = _setup_attack()
    causal = CausalAnalyzer(eng.topology)
    ranked = causal.rank(twin, det, focus="web1",
                         warn=s.detector.warn_threshold)
    assert ranked, "no candidates returned"
    assert ranked[0]["entity_id"] in ATTACK_PATH, ranked[0]
    top3 = {r["entity_id"] for r in ranked[:3]}
    assert "web1" in top3, f"web1 not in top3: {ranked[:3]}"
    in_path = sum(1 for r in ranked if r["entity_id"] in ATTACK_PATH)
    assert in_path >= len(ranked) * 0.6, ranked


def test_granger_baseline_ranks_attack_path():
    from eval.baselines import granger_causality_rank
    s, eng, twin, det = _setup_attack()
    ranked = granger_causality_rank(twin, det, focus="web1",
                                    warn=s.detector.warn_threshold, top_n=6)
    # The symptom is web1; root causes are upstream attack-path entities.
    assert any(e in ATTACK_PATH for e in ranked[:6]), ranked


def test_pc_skeleton_baseline_ranks_attack_path():
    from eval.baselines import pc_skeleton_rank
    s, eng, twin, det = _setup_attack()
    ranked = pc_skeleton_rank(twin, eng.topology, det, focus="web1",
                              warn=s.detector.warn_threshold, top_n=6)
    assert any(e in ATTACK_PATH for e in ranked[:6]), ranked


def test_notears_baseline_ranks_attack_path():
    from eval.baselines import notears_rank
    s, eng, twin, det = _setup_attack()
    ranked = notears_rank(twin, eng.topology, det, focus="web1",
                          warn=s.detector.warn_threshold, top_n=6,
                          max_iter=50)
    assert any(e in ATTACK_PATH for e in ranked[:6]), ranked
