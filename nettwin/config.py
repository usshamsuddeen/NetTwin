"""Settings dataclass + JSON config loader (dependency-free)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any


@dataclass
class DetectorSettings:
    warmup_ticks: int = 25
    ema_alpha: float = 0.06
    z_warn: float = 4.5
    z_alert: float = 7.0
    alert_threshold: float = 0.72
    warn_threshold: float = 0.5
    iforest_enabled: bool = True
    iforest_trees: int = 40
    iforest_sample: int = 128
    iforest_retrain_ticks: int = 120
    iforest_threshold: float = 0.62
    iforest_window: int = 2000
    persistence_ticks: int = 5


@dataclass
class AlertSettings:
    cooldown_ticks: int = 30
    resolve_after_ticks: int = 15


@dataclass
class ForecastSettings:
    default_horizon: int = 15
    damping: float = 0.9
    saturation_warn_pct: float = 55.0
    saturation_horizon: int = 30


@dataclass
class LLMSettings:
    provider: str = "auto"  # ollama | bedrock | auto
    ollama_url: str = "http://localhost:11434"
    model: str = "llama3.2"
    bedrock_model: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    bedrock_region: str = ""  # empty -> use settings.aws.region
    timeout_s: float = 60.0
    embedding_model: str = "nomic-embed-text"
    conversation_history: int = 5


@dataclass
class APISettings:
    api_key: str = ""                         # empty = no API-key enforcement
    api_key_header: str = "X-API-Key"
    localhost_exempt: bool = True
    cors_origins: list[str] = field(default_factory=list)
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_mutations_per_minute: int = 20


@dataclass
class IngestAuthSettings:
    secret: str = ""                         # 32-byte shared secret (or NETTWIN_INGEST_SECRET)
    internal_token: str = ""                 # Internal streamer token (or NETTWIN_INTERNAL_TOKEN)
    skew_window_s: float = 30.0              # Anti-replay timestamp tolerance window
    allowed_forwarders: list[str] = field(default_factory=lambda: [
        "127.0.0.1", "::1", "10.0.0.5", "52.94.76.1"
    ])
    allowed_cert_fps: list[str] = field(default_factory=lambda: [
        "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
        "b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01",
    ])
    enforce_ip_whitelist: bool = False       # Enforce IP whitelist (auto-on in prod)


@dataclass
class SyncSettings:
    enabled: bool = True
    udp_port: int = 5514
    tls_syslog_port: int = 6514              # RFC5425 TLS Syslog port
    tls_cert_file: str = ""                  # Server TLS certificate
    tls_key_file: str = ""                   # Server TLS private key
    tls_ca_file: str = ""                    # CA cert for mTLS client verification
    tls_require_client_cert: bool = True     # Require and verify mTLS client cert
    staleness_s: float = 8.0
    hybrid_after_ticks: int = 8
    drop_after_ticks: int = 5
    drift_after_ticks: int = 12
    fidelity_warn: float = 55.0
    fidelity_hybrid_min: float = 70.0
    divergence_w_rel: float = 0.6
    divergence_w_corr: float = 0.4
    vpc_cidrs: list[str] = field(default_factory=list)
    sync_map: dict[str, str] = field(default_factory=dict)


@dataclass
class SubspaceSettings:
    window: int = 180
    n_components: int = 5
    retrain_ticks: int = 150
    warmup_ticks: int = 40
    z_alert: float = 8.0


@dataclass
class ConformalSettings:
    enabled: bool = True
    alpha: float = 0.1
    calibration_size: int = 400
    coverage_window: int = 200
    aci_enabled: bool = False
    aci_gamma: float = 0.02
    aci_freeze_on_anomaly: bool = True  # Paper 2: freeze γ during anomalies


@dataclass
class DriftSettings:
    enabled: bool = True
    delta: float = 0.02
    lam: float = 30.0
    cooldown_ticks: int = 100


@dataclass
class RiskSettings:
    damping: float = 0.85
    iterations: int = 25
    criticality: dict[str, float] = field(default_factory=lambda: {
        "db": 1.0, "app": 0.8, "web": 0.7, "dns": 0.5,
        "workstation": 0.3, "iot": 0.15,
    })
    vuln_seed: dict[str, float] = field(default_factory=lambda: {
        "server": 0.25, "workstation": 0.35, "iot": 0.45,
        "core_router": 0.05, "distribution_switch": 0.08, "edge_switch": 0.1,
        "firewall": 0.05, "internet_gateway": 0.1, "attacker": 1.0,
    })


@dataclass
class ResponseSettings:
    mode: str = "approval"  # off | approval | auto
    eval_horizon: int = 20
    reward_after_ticks: int = 8
    min_improvement: float = 0.5
    max_active_actions: int = 6
    bandit_state_path: str = "bandit_state.json"
    bandit_noise: float = 0.4


@dataclass
class AWSSettings:
    enabled: bool = False
    region: str = "us-east-1"
    flow_log_group: str = "/vpc/nettwin-flowlogs"     # CloudWatch Log Group (NOT S3)
    flow_log_bucket: str = ""                          # S3 for archive only
    poll_interval_s: float = 10.0                      # CloudWatch Logs poll frequency
    cloudwatch_metrics: bool = True                    # EC2 CPU/Network metrics
    cloudtrail_enabled: bool = False                   # topology change events
    traffic_mirror_enabled: bool = False               # VXLAN packet capture
    traffic_mirror_port: int = 4789                    # AWS Traffic Mirroring VXLAN port
    instance_tags: dict[str, str] = field(default_factory=lambda: {
        "Project": "nettwin"
    })
    cost_limit_daily_usd: float = 5.0                  # auto-alert if exceeded


@dataclass
class ActuationSettings:
    enabled: bool = False
    dry_run: bool = True                               # safe default
    management_cidr: str = "127.0.0.1/32"              # never block this CIDR
    quarantine_sg_name: str = "nettwin-quarantine"
    allowed_actions: list[str] = field(default_factory=lambda: ["isolate", "block_flow"])
    rate_limit_backend: str = "tc"                     # "tc" | "waf"
    web_acl_id: str = ""                               # WAFv2 WebACL ARN (for waf backend)


@dataclass
class StorageSettings:
    retention_days: int = 7          # metric snapshot retention
    research_window_days: int = 30   # how far back to keep research metrics


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    tick_ms: int = 1000
    db_path: str = "nettwin.db"
    history_len: int = 300
    seed: int = 42
    detector: DetectorSettings = field(default_factory=DetectorSettings)
    alerts: AlertSettings = field(default_factory=AlertSettings)
    forecast: ForecastSettings = field(default_factory=ForecastSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)
    api: APISettings = field(default_factory=APISettings)
    sync: SyncSettings = field(default_factory=SyncSettings)
    subspace: SubspaceSettings = field(default_factory=SubspaceSettings)
    conformal: ConformalSettings = field(default_factory=ConformalSettings)
    drift: DriftSettings = field(default_factory=DriftSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    response: ResponseSettings = field(default_factory=ResponseSettings)
    aws: AWSSettings = field(default_factory=AWSSettings)
    actuation: ActuationSettings = field(default_factory=ActuationSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    ingest_auth: IngestAuthSettings = field(default_factory=IngestAuthSettings)
    topology_path: str = ""
    auto_attacks: bool = False
    snapshot_every_ticks: int = 10

    @property
    def tick_s(self) -> float:
        return max(0.05, self.tick_ms / 1000.0)


def _warn_unknown_keys(prefix: str, data: dict[str, Any],
                       allowed: set[str], log: Any) -> None:
    for key in data:
        if key not in allowed:
            log.warning("unknown config key ignored: %s%s", prefix, key)


def _collect_unknown_keys(obj: Any, data: dict[str, Any],
                          log: Any, prefix: str = "") -> None:
    names = {f.name for f in fields(obj)}
    _warn_unknown_keys(prefix, data, names, log)
    for key, value in data.items():
        if key not in names:
            continue
        current = getattr(obj, key)
        if hasattr(current, "__dataclass_fields__") and isinstance(value, dict):
            _collect_unknown_keys(current, value, log, prefix=f"{prefix}{key}.")


def _merge(obj: Any, data: dict[str, Any]) -> Any:
    names = {f.name for f in fields(obj)}
    for key, value in data.items():
        if key not in names:
            continue
        current = getattr(obj, key)
        if hasattr(current, "__dataclass_fields__") and isinstance(value, dict):
            _merge(current, value)
        else:
            setattr(obj, key, value)
    return obj


def load_settings(path: str | os.PathLike[str] | None = None,
                  overrides: dict[str, Any] | None = None,
                  _warn: bool = True) -> Settings:
    settings = Settings()
    cfg_path = Path(path) if path else Path("config.json")
    raw: dict[str, Any] | None = None
    if cfg_path.exists():
        import logging
        log = logging.getLogger("nettwin.config")
        with cfg_path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if _warn:
            _collect_unknown_keys(settings, raw, log)
        _merge(settings, raw)
    if overrides:
        _merge(settings, overrides)
    if not settings.topology_path and os.environ.get("TOPOLOGY"):
        settings.topology_path = os.environ["TOPOLOGY"]
    return settings
