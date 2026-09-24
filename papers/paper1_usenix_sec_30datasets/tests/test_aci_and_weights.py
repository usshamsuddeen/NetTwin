"""ACI (adaptive conformal) + sync divergence-weight configurability tests."""

import os
import sys
from pathlib import Path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REPO_ROOT_PATH = Path(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import math

from nettwin.config import ConformalSettings, SyncSettings, load_settings
from nettwin.ingestion.sync import EntitySync, FIDELITY_METRICS
from nettwin.twin.conformal import ConformalCalibrator


def _aci_calibrator(enabled: bool = True, gamma: float = 0.02) -> ConformalCalibrator:
    s = ConformalSettings(alpha=0.1, aci_enabled=enabled, aci_gamma=gamma)
    return ConformalCalibrator(s)


def test_aci_alpha_decreases_after_misses():
    cal = _aci_calibrator()
    start = cal.alpha_t
    for _ in range(10):
        cal.update_aci(covered=False)
    assert cal.alpha_t < start
    assert cal.alpha_t >= 0.01  # clipped


def test_aci_alpha_increases_after_coverage():
    cal = _aci_calibrator()
    start = cal.alpha_t
    for _ in range(10):
        cal.update_aci(covered=True)
    assert cal.alpha_t > start
    assert cal.alpha_t <= 0.5  # clipped


def test_aci_disabled_keeps_alpha_fixed():
    cal = _aci_calibrator(enabled=False)
    start = cal.alpha_t
    for _ in range(20):
        cal.update_aci(covered=False)
        cal.update_aci(covered=True)
    assert cal.alpha_t == start


def test_aci_coverage_path_drives_alpha():
    cal = _aci_calibrator()
    cal.set_pending_interval(10.0, 20.0)
    before = cal.alpha_t
    cal.check_coverage(999.0)  # outside interval -> miss -> alpha drops
    assert cal.alpha_t < before
    assert cal.realized_coverage() is None  # single observation


def test_aci_gamma_frozen_during_anomaly():
    cal = _aci_calibrator()
    cal.set_pending_interval(10.0, 20.0)
    before = cal.alpha_t
    cal.check_coverage(999.0, anomaly_active=True)  # miss but anomaly -> freeze
    assert cal.alpha_t == before
    # Sanity: without anomaly it would move
    cal2 = _aci_calibrator()
    cal2.set_pending_interval(10.0, 20.0)
    cal2.check_coverage(999.0, anomaly_active=False)
    assert cal2.alpha_t < cal2.s.alpha


def _entity_with_pairs(settings: SyncSettings) -> EntitySync:
    ent = EntitySync("web1", settings)
    sim = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    real = [20.0, 22.0, 24.0, 26.0, 28.0, 30.0]  # 2x level offset, perfect corr
    for m in FIDELITY_METRICS:
        for a, b in zip(sim, real):
            ent.pairs[m].append((a, b))
    return ent


def test_divergence_weights_actually_change_divergence():
    rel_only = _entity_with_pairs(SyncSettings(divergence_w_rel=1.0,
                                               divergence_w_corr=0.0))
    corr_only = _entity_with_pairs(SyncSettings(divergence_w_rel=0.0,
                                                divergence_w_corr=1.0))
    d_rel = rel_only.divergence()
    d_corr = corr_only.divergence()
    # Level offset is large -> rel-weighted divergence is high;
    # shape matches perfectly (corr=1) -> corr-weighted divergence is ~0.
    assert d_rel > 0.2
    assert math.isclose(d_corr, 0.0, abs_tol=1e-9)
    assert d_rel != d_corr


def test_sync_enabled_override_via_load_settings(tmp_path):
    s = load_settings(overrides={"sync": {"enabled": False}})
    assert s.sync.enabled is False


def test_config_unknown_keys_warn(tmp_path, caplog):
    import logging
    from nettwin.config import load_settings
    cfg = tmp_path / "bad_config.json"
    cfg.write_text("""
{
    "tick_ms": 1000,
    "typo_host_name": "127.0.0.1",
    "detector": {
        "ema_alpha": 0.06,
        "typo_enabled": true
    },
    "sync": {
        "enabled": true
    }
}
""", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="nettwin.config"):
        load_settings(path=cfg)
    warnings = caplog.text
    assert "typo_host_name" in warnings
    assert "detector.typo_enabled" in warnings
