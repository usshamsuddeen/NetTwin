"""Prometheus-style exposition format for NetTwin metrics."""
from __future__ import annotations

from typing import Any


def _escape_help(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\n", "\\n")


def prometheus_metrics(state: Any) -> str:
    """Render NetTwin state as Prometheus text."""
    lines: list[str] = []

    def metric(name: str, help_text: str, type_: str, samples: list[tuple[str, float]]) -> None:
        lines.append(f"# HELP {name} {_escape_help(help_text)}")
        lines.append(f"# TYPE {name} {type_}")
        for labels, value in samples:
            lines.append(f'{name}{labels} {value}')

    kpis = state.twin.kpis
    metric("nettwin_network_health", "Aggregated network health 0-100", "gauge",
           [("", state.twin.network_health)])
    metric("nettwin_total_throughput_mbps", "Aggregate throughput", "gauge",
           [("", kpis.total_throughput_mbps)])
    metric("nettwin_avg_latency_ms", "Average link latency", "gauge",
           [("", kpis.avg_latency_ms)])
    metric("nettwin_avg_loss_pct", "Average packet loss", "gauge",
           [("", kpis.avg_loss_pct)])
    metric("nettwin_active_alerts", "Number of active alerts", "gauge",
           [("", len(state.alerts.active()))])
    metric("nettwin_active_attacks", "Number of active attacks", "gauge",
           [("", len(state.engine.attacks))])

    node_samples = []
    for nid, n in state.engine.topology.nodes.items():
        score = state.detector.scores.get(nid, 0.0)
        health = state.twin.health_of(nid) or 100.0
        node_samples.append((f'{{entity="{nid}",kind="{n.kind}"}}', health))
    metric("nettwin_entity_health", "Per-entity health", "gauge", node_samples)

    link_samples = []
    for lid, l in state.engine.topology.links.items():
        score = state.detector.scores.get(lid, 0.0)
        link_samples.append((f'{{entity="{lid}"}}', score))
    metric("nettwin_entity_anomaly_score", "Per-entity anomaly score", "gauge", link_samples)

    return "\n".join(lines) + "\n"
