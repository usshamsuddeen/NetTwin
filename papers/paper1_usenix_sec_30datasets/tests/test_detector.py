"""Detector tests: benign quiet, attacks detected fast, forecaster trend."""

import os
import sys
from pathlib import Path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REPO_ROOT_PATH = Path(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest

from nettwin.config import Settings
from nettwin.simulator.engine import SimulationEngine
from nettwin.twin.detector import AnomalyDetector
from nettwin.twin.predictor import HoltFilter

WARMUP_MARGIN = 15


def _run(eng, det, n):
    tick = None
    for _ in range(n):
        tick = eng.step()
        det.update(tick)
    return tick


def test_benign_traffic_stays_quiet():
    s = Settings()
    eng = SimulationEngine(s)
    det = AnomalyDetector(s.detector)
    _run(eng, det, s.detector.warmup_ticks + WARMUP_MARGIN)
    anomalous = 0
    total = 0
    for _ in range(120):
        tick = eng.step()
        scores, _ = det.update(tick)
        total += 1
        if any(v >= s.detector.alert_threshold for v in scores.values()):
            anomalous += 1
    assert anomalous / total < 0.05, f"false positive rate {anomalous}/{total}"


@pytest.mark.parametrize("attack_type,target,entity", [
    ("ddos", "web1", "web1"),
    ("portscan", None, "attacker"),
    ("exfiltration", "db1", "db1"),
    ("lateral", None, None),       # moving chain, any entity may fire
    ("bruteforce", "app1", "attacker"),
])
def test_attack_detected_within_15_ticks(attack_type, target, entity):
    s = Settings()
    eng = SimulationEngine(s)
    det = AnomalyDetector(s.detector)
    _run(eng, det, s.detector.warmup_ticks + WARMUP_MARGIN)
    eng.start_attack(attack_type, target_id=target, duration_s=None)
    detected_at = None
    hit_entity = None
    for i in range(1, 16):
        tick = eng.step()
        scores, _ = det.update(tick)
        flagged = {e: v for e, v in scores.items() if v >= s.detector.alert_threshold}
        if flagged:
            detected_at = i
            hit_entity = flagged
            break
    assert detected_at is not None, f"{attack_type} never detected"
    assert detected_at <= 15
    if entity is not None:
        assert entity in hit_entity, f"{attack_type}: expected {entity} in {hit_entity}"


def test_forecaster_tracks_trend():
    filt = HoltFilter()
    for i in range(60):
        filt.update(10.0 + 0.5 * i)
    pts = filt.forecast(10)
    last_mean = pts[-1][0]
    expected = 10.0 + 0.5 * 69
    assert abs(last_mean - expected) < 6.0
    assert pts[-1][2] > pts[-1][0] > pts[-1][1]  # band contains mean


def test_isolation_forest_scores_outliers_higher():
    from nettwin.twin.detector import IsolationForest
    import numpy as np
    rng = np.random.default_rng(1)
    X = rng.normal(0, 1, size=(256, 4))
    forest = IsolationForest(n_trees=30, sample_size=128)
    forest.fit(X)
    inlier = forest.score(np.array([0.1, -0.2, 0.0, 0.3]))
    outlier = forest.score(np.array([8.0, 8.0, -8.0, 8.0]))
    assert outlier > inlier
