"""PCA subspace + conformal prediction tests."""
import numpy as np

from nettwin.config import ConformalSettings, Settings
from nettwin.simulator.engine import SimulationEngine
from nettwin.twin.conformal import ConformalCalibrator
from nettwin.twin.detector import AnomalyDetector
from nettwin.twin.subspace import SubspaceDetector


def test_pca_spe_separates_injected_anomaly():
    s = Settings()
    eng = SimulationEngine(s)
    sub = SubspaceDetector(s.subspace)
    for _ in range(s.subspace.warmup_ticks + 30):
        sub.update(eng.step(), attacking=False)
    assert sub.trained
    benign_spe, benign_scores = [], []
    for _ in range(30):
        sub.update(eng.step(), attacking=False)
        benign_spe.append(sub.last_spe)
        benign_scores.append(sub.last_score)
    eng.start_attack("ddos", target_id="web1", duration_s=None)
    attack_spe, attack_scores = [], []
    for _ in range(10):
        sub.update(eng.step(), attacking=True)
        attack_spe.append(sub.last_spe)
        attack_scores.append(sub.last_score)
    assert max(attack_scores) >= 0.7, f"attack scores {attack_scores}"
    assert min(attack_spe) > max(benign_spe), "SPE does not separate"
    assert sum(1 for v in benign_scores if v >= 0.7) <= 3
    top_cols = dict(sub.top_residual_columns(5))
    assert "edge3-web1" in top_cols, f"top residual cols {top_cols}"


def test_conformal_pvalues_calibrated_on_benign():
    s = Settings()
    eng = SimulationEngine(s)
    det = AnomalyDetector(s.detector)
    cal = ConformalCalibrator(ConformalSettings())
    for _ in range(s.detector.warmup_ticks + 15):
        det.update(eng.step())
    benign_max = []
    for _ in range(150):
        tick = eng.step()
        scores, _ = det.update(tick)
        m = max(scores.values())
        benign_max.append(m)
        cal.calibrate(m)
    # benign scores should mostly have high p-values (not surprising)
    pvals = [cal.pvalue(v) for v in benign_max[-50:]]
    high = sum(1 for p in pvals if p > 0.1) / len(pvals)
    assert high > 0.85, f"benign p-value mass {high}"
    # an attack-scale score should be highly significant
    assert cal.pvalue(1.0) < 0.05
    assert cal.confidence(1.0) > 0.95


def test_conformal_interval_empirical_coverage():
    cal = ConformalCalibrator(ConformalSettings(alpha=0.1))
    rng = np.random.default_rng(5)
    for e in np.abs(rng.normal(0, 1, 600)):
        cal.observe_forecast_error(float(e))
    samples = np.abs(rng.normal(0, 1, 300))  # non-negative metric domain
    hits = 0
    for x in samples:
        lo, hi = cal.interval(0.0)
        cal.set_pending_interval(lo, hi)
        cal.check_coverage(float(x))
        hits += int(lo <= x <= hi)
    realized = cal.realized_coverage()
    assert realized is not None
    assert abs(realized - 0.9) < 0.08, f"coverage {realized}"
    assert abs(hits / len(samples) - 0.9) < 0.08
