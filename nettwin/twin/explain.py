"""Per-alert explainability: z attribution + PCA residual split + occlusion."""
from __future__ import annotations

from typing import Any

from nettwin.twin.detector import AnomalyDetector, LINK_METRICS, NODE_METRICS
from nettwin.twin.subspace import SubspaceDetector


def explain_entity(detector: AnomalyDetector, subspace: SubspaceDetector | None,
                   entity_id: str, hour: float) -> dict[str, Any]:
    """Ranked per-feature attribution for the entity's current anomaly."""
    out: list[dict[str, Any]] = []
    metrics = LINK_METRICS if entity_id in _link_entities(detector) else NODE_METRICS
    baselines = detector.baselines.get(entity_id, {})
    signal = detector.signals.get(entity_id, {})
    values: dict[str, float] = signal.get("metrics", {})

    z_scores: dict[str, float] = {}
    for metric in metrics:
        if metric not in baselines or metric not in values:
            continue
        z = baselines[metric].z(float(values[metric]), hour)
        z_scores[metric] = round(float(z), 2)

    if not z_scores:
        return {"entity_id": entity_id, "attributions": [], "pca": []}

    zmax = max(max(z_scores.values()), 1e-6)
    for metric, z in sorted(z_scores.items(), key=lambda kv: -kv[1]):
        # occlusion: recompute max-z with this metric removed
        rest = [v for k, v in z_scores.items() if k != metric]
        occl = zmax - (max(rest) if rest else 0.0)
        out.append({
            "feature": metric,
            "z": z,
            "contribution": round(max(0.0, z) / (abs(zmax) + 1e-6), 3),
            "occlusion_delta": round(max(0.0, occl), 2),
        })

    pca: list[dict[str, Any]] = []
    if subspace is not None and subspace.trained:
        cols = subspace.last_column_residuals
        related = [c for c in cols if entity_id in c]
        if not related:
            related = sorted(cols, key=lambda c: cols[c], reverse=True)[:3]
        total = sum(cols[c] for c in related) or 1e-9
        for c in sorted(related, key=lambda c: -cols[c])[:5]:
            pca.append({"column": c, "residual": cols[c],
                        "share": round(cols[c] / (sum(cols.values()) or 1e-9), 3)})

    return {"entity_id": entity_id, "attributions": out, "pca": pca,
            "top_metric": signal.get("top_metric"), "score": detector.scores.get(entity_id, 0.0)}


def _link_entities(detector: AnomalyDetector) -> set[str]:
    return {eid for eid, sig in detector.signals.items()
            if sig.get("entity_kind") == "link"}
