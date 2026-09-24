"""FastAPI application factory: lifespan wiring of engine, twin, detector,
sync layer, research stack and response agent."""
from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

log = logging.getLogger("nettwin.api")
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from nettwin.alerts import AlertManager
from nettwin.actuation.bridge import ActuationBridge
from nettwin.actuation.executor import AWSActuator
from nettwin.actuation.safety import ActuationSafety
from nettwin.actuation.translator import ResponseToAWS
from nettwin.api.security import setup_security
from nettwin.api.ws import WebSocketHub
from nettwin.config import Settings, load_settings
from nettwin.ingestion.authenticity import IngestAuthenticator
from nettwin.ingestion.normalize import Normalizer
from nettwin.ingestion.server import IngestionServer
from nettwin.ingestion.sync import SyncEngine
from nettwin.llm.analyst import SecurityAnalyst
from nettwin.models import TelemetryTick
from nettwin.research import ResearchMetrics
from nettwin.response.agent import ResponseAgent
from nettwin.risk.attack_graph import AttackGraph
from nettwin.storage import Storage
from nettwin.simulator.engine import SimulationEngine
from nettwin.twin.causal import CausalAnalyzer
from nettwin.twin.conformal import ConformalCalibrator
from nettwin.twin.detector import AnomalyDetector
from nettwin.twin.drift import DriftMonitor
from nettwin.twin.predictor import Predictor
from nettwin.twin.state import TwinState
from nettwin.twin.subspace import SubspaceDetector

DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "dashboard"
STUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "studio"


class AppState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.started_at = time.time()
        self.storage = Storage(settings.db_path)
        self.hub = WebSocketHub()
        self.engine = SimulationEngine(settings)
        self.twin = TwinState(settings)
        self.detector = AnomalyDetector(settings.detector)
        self.predictor = Predictor(settings.forecast)
        self.alerts = AlertManager(settings, self.storage)
        self.analyst = SecurityAnalyst(settings, self)
        self.ingest_authenticator = IngestAuthenticator(
            secret=settings.ingest_auth.secret,
            internal_token=settings.ingest_auth.internal_token,
            skew_window_s=settings.ingest_auth.skew_window_s,
            allowed_forwarders=settings.ingest_auth.allowed_forwarders,
            allowed_cert_fps=settings.ingest_auth.allowed_cert_fps,
            enforce_ip_whitelist=settings.ingest_auth.enforce_ip_whitelist,
        )
        if settings.sync.enabled:
            self.sync = SyncEngine(settings.sync, self.engine.topology)
            self.normalizer = Normalizer(self.sync.resolve)
            self.ingest_server = IngestionServer(
                port=settings.sync.udp_port,
                normalizer=self.normalizer,
                on_batch=self._on_batch,
                tls_port=settings.sync.tls_syslog_port,
                tls_cert_file=settings.sync.tls_cert_file,
                tls_key_file=settings.sync.tls_key_file,
                tls_ca_file=settings.sync.tls_ca_file,
                tls_require_client_cert=settings.sync.tls_require_client_cert,
                allowed_cert_fps=settings.ingest_auth.allowed_cert_fps,
            )
        else:
            self.sync = None
            self.normalizer = None
            self.ingest_server = None
        self.subspace = SubspaceDetector(settings.subspace)
        self.conformal = ConformalCalibrator(settings.conformal)
        self.drift = DriftMonitor(settings.drift.delta, settings.drift.lam,
                                  settings.drift.cooldown_ticks)
        self.risk = AttackGraph(self.engine.topology, settings.risk)
        self.causal = CausalAnalyzer(self.engine.topology)
        self.response = ResponseAgent(settings, self.engine)
        self.research = ResearchMetrics()
        self.last_confidences: dict[str, float] = {}
        self.last_sync_transitions: dict[str, str] = {}
        self.aws_adapter = None  # set by lifespan if aws.enabled
        self.traffic_mirror_adapter = None  # set by lifespan if aws.traffic_mirror_enabled
        from nettwin.ingestion.aws_streamer import AWSCloudTrafficStreamer
        self.cloud_streamer = AWSCloudTrafficStreamer(
            normalizer=self.normalizer,
            on_batch_callback=self._on_batch,
            sync_engine=self.sync,
        )
        for lid, link in self.engine.topology.links.items():
            self.predictor.link_caps[lid] = link.bandwidth_mbps
        self.active_organization: dict[str, Any] = {
            "org_id": "org-aws-demo",
            "org_name": "Acme Global Cloud",
            "environment": "AWS Production (us-east-1)",
            "vpc_id": "vpc-07b94a12ec8",
            "cidr": "10.0.0.0/16",
            "ingest_mode": "aws_vpc_mirror",
            "topology_name": getattr(self.engine.topology, "name", "aws-3tier"),
            "sync_status": "SYNCHRONIZED",
            "connected_at": time.time(),
        }

    def get_snapshot_message(self) -> dict[str, Any]:
        return {
            "type": "snapshot",
            "organization": self.active_organization,
            "topology": {
                "name": getattr(self.engine.topology, "name", "default"),
                "title": getattr(self.engine.topology, "title", "Enterprise Network"),
                "description": getattr(self.engine.topology, "description", ""),
                "tiers": getattr(self.engine.topology, "tiers", []),
                "nodes": [n.model_dump() for n in self.engine.topology.nodes.values()],
                "links": [l.model_dump() for l in self.engine.topology.links.values()],
            },
            "kpis": self.twin.kpis.model_dump(),
            "alerts": [a.model_dump() for a in self.alerts.active()],
            "attacks": [a.event.model_dump() for a in self.engine.attacks.values()],
            "sync": self.sync.snapshot() if self.sync else [],
            "response": self.response.snapshot(),
            "config": {
                "tick_ms": self.settings.tick_ms,
                "alert_threshold": self.settings.detector.alert_threshold,
                "warn_threshold": self.settings.detector.warn_threshold,
            },
        }

    async def switch_topology(self, new_topo: Any) -> None:
        self.engine.switch_topology(new_topo)
        if self.settings.sync.enabled and self.sync is not None:
            self.sync = SyncEngine(self.settings.sync, self.engine.topology)
            self.normalizer = Normalizer(self.sync.resolve)
            if self.cloud_streamer:
                self.cloud_streamer.normalizer = self.normalizer
                self.cloud_streamer.sync = self.sync
        self.risk = AttackGraph(self.engine.topology, self.settings.risk)
        self.causal = CausalAnalyzer(self.engine.topology)
        self.predictor.link_caps.clear()
        for lid, link in self.engine.topology.links.items():
            self.predictor.link_caps[lid] = link.bandwidth_mbps
        self.subspace.reset()
        self.detector.reset()
        self.active_organization["topology_name"] = getattr(new_topo, "name", "custom")
        snap = self.get_snapshot_message()
        await self.hub.broadcast(snap)

    async def set_organization(self, org_data: dict[str, Any]) -> None:
        self.active_organization.update(org_data)
        self.active_organization["connected_at"] = time.time()
        self.active_organization["sync_status"] = "SYNCHRONIZED"
        await self.hub.broadcast({
            "type": "org_connected",
            "organization": self.active_organization,
        })

    def _on_batch(self, batch) -> None:
        if self.settings.sync.enabled and self.sync is not None:
            self.sync.ingest(batch, self.settings.tick_s)


def _telemetry_message(state: AppState, tick: TelemetryTick,
                       scores: dict[str, float]) -> dict[str, Any]:
    return {
        "type": "telemetry",
        "organization": state.active_organization,
        "tick": tick.tick,
        "t": round(tick.sim_time_s, 1),
        "hour": tick.hour_of_day,
        "nodes": {nid: {"tp": m.throughput_mbps, "tx": m.tx_mbps, "rx": m.rx_mbps,
                        "pps": m.pps, "lat": m.latency_ms, "jit": m.jitter_ms,
                        "loss": m.packet_loss_pct, "cpu": m.cpu_pct,
                        "mem": m.mem_pct, "fan": m.fanout, "br": m.bytes_ratio}
                  for nid, m in tick.nodes.items()},
        "links": {lid: {"tp": m.throughput_mbps, "pps": m.pps,
                        "util": m.utilization_pct, "lat": m.latency_ms,
                        "loss": m.packet_loss_pct, "drop": m.dropped_mbps}
                  for lid, m in tick.links.items()},
        "health": {"net": state.twin.network_health,
                   "nodes": state.twin.node_health,
                   "links": state.twin.link_health},
        "anomalies": {eid: round(s, 3) for eid, s in scores.items() if s >= 0.3},
        "attacks": [e.model_dump() for e in (a.event for a in state.engine.attacks.values())],
        "kpis": state.twin.kpis.model_dump(),
        "sync": {eid: {"mode": es.mode, "fidelity": es.fidelity}
                 for eid, es in (state.sync.entities.items() if state.sync else [])
                 if es.seen_once},
    }


def create_app(settings: Settings | None = None,
               overrides: dict[str, Any] | None = None) -> FastAPI:
    settings = settings or load_settings(overrides=overrides)
    if overrides:
        from nettwin.config import _merge
        _merge(settings, overrides)
    state = AppState(settings)
    state.alerts.broadcast = state.hub.broadcast

    def _continual_retrain(event) -> None:
        state.detector.reset()
        state.subspace.trained = False

    state.drift.on_drift = _continual_retrain

    async def on_tick(tick: TelemetryTick) -> None:
        attacking = len(tick.active_attacks) > 0
        # real-world sync: HYBRID entities get real values before twin/detector
        if state.settings.sync.enabled and state.sync is not None:
            transitions = state.sync.update(tick)
            if transitions:
                state.last_sync_transitions.update(transitions)
        state.twin.update(tick)
        scores, signals = state.detector.update(tick)
        state.predictor.update(tick, state.twin.kpis.total_throughput_mbps,
                               state.twin.kpis.avg_latency_ms)
        spe_score = state.subspace.update(tick, attacking)
        # conformal: calibrate on benign ensemble max score, p-values for alerts
        ensemble_max = max([max(scores.values(), default=0.0), spe_score])
        if not attacking:
            state.conformal.calibrate(ensemble_max)
        confidences = {eid: state.conformal.confidence(v)
                       for eid, v in scores.items()
                       if v >= settings.detector.warn_threshold}
        state.last_confidences = confidences
        await state.alerts.process(tick, scores, signals, confidences)
        # forecaster conformal interval + realized coverage
        alarmed = any(v >= settings.detector.alert_threshold for v in scores.values())
        state.conformal.check_coverage(state.twin.kpis.total_throughput_mbps,
                                       anomaly_active=alarmed)
        fc1 = state.predictor.forecast("network", "throughput_mbps", 1)
        if fc1:
            err = abs(fc1.points[0].mean - state.twin.kpis.total_throughput_mbps)
            state.conformal.observe_forecast_error(err)
            lo, hi = state.conformal.interval(fc1.points[0].mean)
            state.conformal.set_pending_interval(lo, hi)
        # drift monitor
        drift_event = state.drift.update(
            tick.tick, state.twin.kpis.total_throughput_mbps,
            state.twin.kpis.avg_latency_ms, attacking, alarmed)
        if drift_event:
            state.research.note_drift(drift_event)
        # predictive saturation alerts
        for warn in state.predictor.saturation_warnings():
            a = state.alerts.raise_predictive(
                str(warn["link_id"]), int(warn["ticks_to_saturation"]), tick.tick)
            if a:
                await state.storage.upsert_alert(a)
        # sync drift alerts
        if state.sync is not None:
            for eid in state.sync.drift_alerts():
                es = state.sync.entities[eid]
                a = state.alerts.raise_adhoc(
                    eid, "sync:divergence",
                    f"Real feed for {eid} diverges from twin "
                    f"(fidelity {es.fidelity:.0f}/100); staying in SHADOW",
                    severity="warning", score=0.55, tick=tick.tick)
                if a:
                    await state.storage.upsert_alert(a)
        # attack-graph risk: recompute seeds from active alerts/attacks
        if tick.tick % 5 == 0 or attacking:
            seeds = {a.entity_id: 0.85 for a in state.alerts.active()
                     if a.severity == "critical"}
            for atk in state.engine.attacks.values():
                if atk.event.target_id:
                    seeds[atk.event.target_id] = 0.9
                if atk.event.source_id:
                    seeds[atk.event.source_id] = 1.0
            state.risk.recompute(seeds)
        # response agent: proposals + rewards + auto actions
        active_alerts = state.alerts.active()
        try:
            if active_alerts and tick.tick % 4 == 0:
                state.response.propose(active_alerts, scores)
            rewarded = state.response.tick(state.twin.network_health)
            for r in rewarded:
                state.research.note_reward(r["reward"])
            state.response.auto_act(active_alerts, scores)
        except Exception:
            pass  # response agent must never stall the twin loop
        # research metrics
        for atk in state.engine.attacks.values():
            alerted = any(a.entity_id in (atk.event.target_id, atk.event.source_id)
                          for a in active_alerts)
            state.research.note_detection(
                atk.event.id, atk.event.start_tick,
                tick.tick if alerted else None)
        state.research.note_tick(
            state.sync.network_fidelity() if state.sync else 100.0, alarmed,
            spe_score >= 0.7, state.conformal.realized_coverage())
        await state.hub.broadcast(_telemetry_message(state, tick, scores))
        if tick.tick % 5 == 0:
            fc = state.predictor.forecast("network", "throughput_mbps", 15)
            if fc:
                await state.hub.broadcast({"type": "forecast",
                                           "forecast": fc.model_dump()})
            await state.hub.broadcast({"type": "research",
                                       "research": state.research.snapshot()})
            await state.hub.broadcast({"type": "risk",
                                       "risk": {"network_risk": state.risk.network_risk,
                                                "top_paths": state.risk.top_paths,
                                                "nodes": state.risk.compromise}})
            await state.hub.broadcast({"type": "response",
                                       "response": state.response.snapshot()})
        if tick.tick % settings.snapshot_every_ticks == 0:
            for nid, m in tick.nodes.items():
                await state.storage.snapshot(tick.tick, nid, "node", m.model_dump())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await state.storage.init()
        await state.alerts.load_active()
        state.engine.subscribe(on_tick)
        await state.engine.start()
        if settings.sync.enabled and state.ingest_server is not None:
            await state.ingest_server.start()
        if settings.aws.enabled and state.sync is not None:
            from nettwin.ingestion.adapters.aws_adapter import AWSAdapter
            state.aws_adapter = AWSAdapter(settings, state.normalizer, state.sync)
            await state.aws_adapter.start()
        if settings.aws.traffic_mirror_enabled and state.sync is not None:
            from nettwin.ingestion.adapters.traffic_mirror import TrafficMirrorAdapter
            state.traffic_mirror_adapter = TrafficMirrorAdapter(
                settings, state.normalizer, state.sync)
            await state.traffic_mirror_adapter.start()
        if settings.actuation.enabled:
            actuator = AWSActuator(settings, storage=state.storage)
            mapping = _load_aws_mapping()
            actuator._vpc_id = mapping.get("vpc_id")
            translator = ResponseToAWS(
                settings.actuation,
                entity_to_instance=mapping.get("entity_to_instance", {}),
                entity_to_ip=mapping.get("entity_to_ip", {}),
                entity_to_subnet=mapping.get("entity_to_subnet", {}),
                entity_to_nacl=mapping.get("entity_to_nacl", {}),
            )
            safety = ActuationSafety(
                settings.actuation,
                entity_to_instance=mapping.get("entity_to_instance", {}),
                entity_to_kind={
                    nid: n.kind for nid, n in state.engine.topology.nodes.items()},
            )
            actuator.set_translator(translator)
            actuator.set_safety(safety)
            bridge = ActuationBridge(actuator)
            state.response.on_apply_aws = bridge.sync_callback
            log.info("aws actuation bridge armed (dry_run=%s)", settings.actuation.dry_run)
        yield
        if state.cloud_streamer is not None:
            await state.cloud_streamer.stop_stream()
        if state.traffic_mirror_adapter is not None:
            await state.traffic_mirror_adapter.stop()
        if state.aws_adapter is not None:
            await state.aws_adapter.stop()
        if state.ingest_server is not None:
            await state.ingest_server.stop()
        await state.engine.stop()
        await state.storage.close()

    def _load_aws_mapping() -> dict[str, Any]:
        """Load entity->AWS resource mapping from discovery output if present."""
        path = Path("aws_sync_map.json")
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            instances = data.get("instances", [])
            subnets = {s["subnet_id"]: s for s in data.get("subnets", [])}
            return {
                "vpc_id": (data.get("igw") or {}).get("vpc_id"),
                "entity_to_instance": {
                    i["entity_id"]: i["instance_id"] for i in instances},
                "entity_to_ip": {
                    i["entity_id"]: i["private_ip"] for i in instances},
                "entity_to_subnet": {
                    i["entity_id"]: i["subnet_id"] for i in instances},
                "entity_to_nacl": {
                    i["entity_id"]: subnets.get(i["subnet_id"], {}).get("nacl_id", "")
                    for i in instances},
            }
        except Exception as exc:
            log.warning("could not load aws_sync_map.json: %s", exc)
            return {}

    app = FastAPI(title="NetTwin", version="2.0.0", lifespan=lifespan)
    setup_security(app, settings)
    app.state.nettwin = state
    app.state.ingest_authenticator = state.ingest_authenticator

    from nettwin.api.routes import build_router
    from nettwin.api.scenario_routes import build_scenario_router
    from nettwin.api.integration_routes import build_integration_router
    app.include_router(build_router(state))
    app.include_router(build_scenario_router(state))
    app.include_router(build_integration_router(state))

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await state.hub.connect(ws, state.get_snapshot_message())

    app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")
    app.mount("/studio", StaticFiles(directory=STUDIO_DIR, html=True), name="studio")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(DASHBOARD_DIR / "index.html")

    @app.get("/styles.css", include_in_schema=False)
    async def styles() -> FileResponse:
        return FileResponse(DASHBOARD_DIR / "styles.css")

    @app.get("/app.js", include_in_schema=False)
    async def app_js() -> FileResponse:
        return FileResponse(DASHBOARD_DIR / "app.js")

    return app
