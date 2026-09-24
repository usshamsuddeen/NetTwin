"""Pydantic models for NetTwin domain objects."""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

NodeKind = Literal[
    "internet_gateway", "firewall", "core_router", "distribution_switch",
    "edge_switch", "server", "workstation", "iot", "attacker",
]


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Node(BaseModel):
    id: str
    label: str
    kind: NodeKind
    x: float
    y: float
    role: str = ""


class Link(BaseModel):
    id: str
    src: str
    dst: str
    bandwidth_mbps: float
    base_latency_ms: float = 0.5
    kind: str = "ethernet"


class Flow(BaseModel):
    src: str
    dst: str
    protocol: str
    bytes: int
    packets: int
    path: list[str] = Field(default_factory=list)


class NodeMetrics(BaseModel):
    throughput_mbps: float = 0.0
    tx_mbps: float = 0.0
    rx_mbps: float = 0.0
    pps: float = 0.0
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_loss_pct: float = 0.0
    cpu_pct: float = 0.0
    mem_pct: float = 0.0
    fanout: int = 0
    bytes_ratio: float = 0.5


class LinkMetrics(BaseModel):
    throughput_mbps: float = 0.0
    pps: float = 0.0
    utilization_pct: float = 0.0
    latency_ms: float = 0.0
    packet_loss_pct: float = 0.0
    dropped_mbps: float = 0.0


class AttackEvent(BaseModel):
    id: str = Field(default_factory=new_id)
    attack_type: str
    target_id: str | None = None
    source_id: str | None = None
    started_at: float = Field(default_factory=time.time)
    ended_at: float | None = None
    start_tick: int = 0
    duration_s: float | None = None
    active: bool = True


class TelemetryTick(BaseModel):
    tick: int
    sim_time_s: float
    hour_of_day: float
    nodes: dict[str, NodeMetrics]
    links: dict[str, LinkMetrics]
    flows: list[Flow] = Field(default_factory=list)
    active_attacks: list[AttackEvent] = Field(default_factory=list)


class Alert(BaseModel):
    id: str = Field(default_factory=new_id)
    entity_id: str
    entity_kind: str = "node"
    alert_type: str
    severity: Literal["info", "warning", "critical"] = "warning"
    message: str
    score: float = 0.0
    status: Literal["active", "acknowledged", "resolved"] = "active"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    tick: int = 0
    hits: int = 1
    confidence: float = -1.0  # conformal confidence; -1 = uncalibrated


class KPIs(BaseModel):
    tick: int = 0
    network_health: float = 100.0
    total_throughput_mbps: float = 0.0
    total_pps: float = 0.0
    avg_latency_ms: float = 0.0
    avg_loss_pct: float = 0.0
    max_link_util_pct: float = 0.0
    active_alerts: int = 0
    active_attacks: int = 0
    anomalous_entities: int = 0


class ForecastPoint(BaseModel):
    step: int
    mean: float
    lower: float
    upper: float


class ForecastResult(BaseModel):
    entity_id: str
    metric: str
    horizon: int
    points: list[ForecastPoint]
    saturate_in_ticks: int | None = None


class WhatIfResult(BaseModel):
    scenario: dict[str, Any]
    horizon_ticks: int
    affected_entities: list[dict[str, Any]] = Field(default_factory=list)
    baseline_network_health: float = 100.0
    scenario_network_health: float = 100.0
    projected_health_drop: float = 0.0
    saturation_timeline: list[dict[str, Any]] = Field(default_factory=list)
    dropped_flows_pct: float = 0.0
    summary: str = ""


class AnalystAnswer(BaseModel):
    mode: Literal["ollama", "fallback"]
    model: str
    answer: str
    context_used: dict[str, Any] = Field(default_factory=dict)
    elapsed_s: float = 0.0
