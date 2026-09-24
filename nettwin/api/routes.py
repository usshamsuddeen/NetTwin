"""REST endpoints for NetTwin."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from nettwin.ingestion.authenticity import verify_ingest_auth

from nettwin.api.app import AppState
from nettwin.simulator.attacks import ATTACK_TYPES
from nettwin.twin.whatif import run_whatif


class AttackStartRequest(BaseModel):
    type: str
    target_id: str | None = None
    duration_s: float | None = None


class AttackStopRequest(BaseModel):
    attack_id: str | None = None


class WhatIfRequest(BaseModel):
    scenario: dict[str, Any]
    horizon_ticks: int = 30


class ConfigUpdate(BaseModel):
    tick_ms: int | None = None
    alert_threshold: float | None = None
    warn_threshold: float | None = None
    auto_attacks: bool | None = None
    paused: bool | None = None
    ollama_model: str | None = None


class AskRequest(BaseModel):
    question: str


class SyncModeRequest(BaseModel):
    entity: str
    mode: str  # SIMULATED | SHADOW | HYBRID | auto


class ResponseActionRequest(BaseModel):
    id: str


class ResponseModeRequest(BaseModel):
    mode: str  # auto | approval | off


class CloudStreamStartRequest(BaseModel):
    dataset: str = "cse2018_ddos_loic_hoic"
    speed: float = 1.0
    sample_pct: float = 100.0
    attack_only: bool = False
    batch_size: int = 32
    max_records: int | None = None


class TopologySwitchRequest(BaseModel):
    topology_id: str = "aws-3tier"  # "aws-3tier" | "default"
    topology_name: str | None = None
    path: str | None = None


class OrganizationConnectRequest(BaseModel):
    org_name: str = "Acme Global Cloud"
    environment: str = "AWS Production (us-east-1)"
    vpc_id: str = "vpc-07b94a12ec8"
    cidr: str = "10.0.0.0/16"
    region: str = "us-east-1"
    ingest_mode: str = "aws_vpc_mirror"  # "aws_vpc_mirror" | "live_agent" | "config_upload" | "preconfigured"
    topology_name: str = "aws-3tier"
    custom_topology: dict[str, Any] | None = None


def build_router(state: AppState) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/health")
    async def health() -> dict[str, Any]:
        available = await state.analyst.available()
        return {
            "status": "ok",
            "uptime_s": round(time.time() - state.started_at, 1),
            "tick": state.engine.tick,
            "llm": {"available": available, "model": state.settings.llm.model,
                    "mode": "ollama" if available else "fallback"},
        }

    @router.get("/ready")
    async def ready() -> dict[str, Any]:
        return {
            "status": "ready",
            "tick": state.engine.tick,
            "storage": state.storage.path is not None,
        }

    @router.get("/topology")
    async def topology() -> dict[str, Any]:
        topo = state.engine.topology
        return {
            "name": getattr(topo, "name", "default"),
            "title": getattr(topo, "title", "Enterprise Network"),
            "description": getattr(topo, "description", ""),
            "tiers": getattr(topo, "tiers", []),
            "nodes": [{**n.model_dump(),
                       "health": round(state.twin.health_of(n.id) or 100.0, 1),
                       "anomaly": round(state.detector.scores.get(n.id, 0.0), 3)}
                      for n in topo.nodes.values()],
            "links": [{**l.model_dump(),
                       "health": round(state.twin.health_of(l.id) or 100.0, 1),
                       "anomaly": round(state.detector.scores.get(l.id, 0.0), 3)}
                      for l in topo.links.values()],
        }

    @router.get("/topology/list")
    async def list_topologies() -> list[dict[str, Any]]:
        current_name = getattr(state.engine.topology, "name", "default")
        return [
            {
                "id": "aws-3tier",
                "name": "AWS 3-Tier Enterprise Cloud",
                "nodes_count": 12,
                "description": "12-node 3-tier AWS cloud architecture with WAF, ALB, EC2 ASG, ECS App, RDS Aurora, S3",
                "active": current_name == "aws-3tier",
                "path": "apps/aws-3tier/topology.json",
            },
            {
                "id": "default",
                "name": "Enterprise Campus Network",
                "nodes_count": 35,
                "description": "35-node campus topology across core, distribution, edge switches and endpoints",
                "active": current_name != "aws-3tier",
                "path": "",
            },
        ]

    @router.post("/topology/switch")
    async def switch_topology(req: TopologySwitchRequest) -> dict[str, Any]:
        from pathlib import Path
        from nettwin.simulator.topology import Topology, build_topology
        target = req.topology_name or req.topology_id
        if target == "aws-3tier" or (req.path and "aws-3tier" in req.path):
            topo_path = Path("apps/aws-3tier/topology.json")
            if not topo_path.exists():
                raise HTTPException(404, "AWS 3-tier topology file not found")
            new_topo = Topology.from_json_file(topo_path)
        elif req.path:
            p = Path(req.path)
            if not p.exists():
                raise HTTPException(404, f"Topology file {req.path} not found")
            new_topo = Topology.from_json_file(p)
        else:
            new_topo = build_topology()

        await state.switch_topology(new_topo)
        return {
            "status": "ok",
            "topology": {
                "name": getattr(new_topo, "name", "default"),
                "title": getattr(new_topo, "title", "Enterprise Network"),
                "nodes_count": len(new_topo.nodes),
                "links_count": len(new_topo.links),
            },
        }

    @router.get("/org/current")
    async def get_current_org() -> dict[str, Any]:
        return {
            "status": "ok",
            "organization": state.active_organization,
            "topology": {
                "name": getattr(state.engine.topology, "name", "default"),
                "title": getattr(state.engine.topology, "title", "Enterprise Network"),
                "nodes_count": len(state.engine.topology.nodes),
                "links_count": len(state.engine.topology.links),
                "tiers_count": len(getattr(state.engine.topology, "tiers", [])),
            },
            "twin_fidelity": state.sync.entities["web1"].fidelity if (state.sync and "web1" in state.sync.entities) else 99.4,
            "sync_mode": "HYBRID_LIVE" if (state.cloud_streamer and getattr(state.cloud_streamer, "stats", None) and state.cloud_streamer.stats.is_active) else "SYNCHRONIZED",
        }

    @router.get("/org/environments")
    async def get_org_environments() -> dict[str, Any]:
        return {
            "regions": [
                {"id": "us-east-1", "name": "US East (N. Virginia)", "recommended": True},
                {"id": "us-west-2", "name": "US West (Oregon)"},
                {"id": "eu-west-1", "name": "Europe (Ireland)"},
                {"id": "ap-southeast-1", "name": "Asia Pacific (Singapore)"},
            ],
            "profiles": [
                {
                    "id": "aws-3tier",
                    "name": "AWS 3-Tier Enterprise Cloud",
                    "description": "Public Ingress (WAF v2, ALB), Dual-AZ Web Tier (EC2 ASG), Microservice App Tier (ECS), Aurora RDS PostgreSQL, and Amazon S3 Lakehouse.",
                    "nodes_count": 12,
                    "vpc_cidr": "10.0.0.0/16",
                    "subnets_count": 5,
                },
                {
                    "id": "default",
                    "name": "Enterprise Campus & Data Center",
                    "description": "Multi-tier enterprise campus spanning Core Routers, Distribution Switches, Access Edges, and Endpoints.",
                    "nodes_count": 35,
                    "vpc_cidr": "172.16.0.0/16",
                    "subnets_count": 8,
                },
                {
                    "id": "fintech-zero-trust",
                    "name": "FinTech Zero-Trust Multi-AZ Cloud",
                    "description": "Regulated banking architecture with mutual TLS, PrivateLink VPC endpoints, and strict network segmentation.",
                    "nodes_count": 12,
                    "vpc_cidr": "10.200.0.0/16",
                    "subnets_count": 6,
                }
            ],
        }

    @router.post("/org/connect")
    async def connect_org(req: OrganizationConnectRequest) -> dict[str, Any]:
        from pathlib import Path
        from nettwin.simulator.topology import Topology, build_topology

        # 1. Determine target topology
        if req.custom_topology:
            new_topo = Topology.from_dict(req.custom_topology)
        elif req.topology_name == "aws-3tier" or "aws" in req.environment.lower() or "vpc" in req.ingest_mode.lower():
            topo_path = Path("apps/aws-3tier/topology.json")
            if topo_path.exists():
                new_topo = Topology.from_json_file(topo_path)
            else:
                new_topo = build_topology()
        else:
            new_topo = build_topology()

        # 2. Switch twin topology if different
        current_name = getattr(state.engine.topology, "name", "")
        target_name = getattr(new_topo, "name", "")
        if current_name != target_name or req.custom_topology:
            await state.switch_topology(new_topo)

        # 3. Update active organization
        org_payload = {
            "org_name": req.org_name,
            "environment": req.environment,
            "vpc_id": req.vpc_id or "vpc-07b94a12ec8",
            "cidr": req.cidr or "10.0.0.0/16",
            "region": req.region,
            "ingest_mode": req.ingest_mode,
            "topology_name": target_name,
        }
        await state.set_organization(org_payload)

        # Recalibrate twin detector baseline for this organization
        state.detector.reset()

        return {
            "status": "connected",
            "message": f"Successfully connected to {req.org_name} and synthesized Digital Twin.",
            "organization": state.active_organization,
            "topology": {
                "name": getattr(state.engine.topology, "name", "default"),
                "title": getattr(state.engine.topology, "title", "Enterprise Network"),
                "nodes_count": len(state.engine.topology.nodes),
                "links_count": len(state.engine.topology.links),
            },
        }

    @router.get("/metrics")
    async def metrics(entity: str, window: int = 120) -> dict[str, Any]:
        series = state.twin.series(entity, max(1, min(window, state.settings.history_len)))
        if not series and entity != "network":
            raise HTTPException(404, f"unknown entity: {entity}")
        if entity == "network":
            return {"entity": entity, "series": [
                {"throughput_mbps": tp, "latency_ms": la, "packet_loss_pct": lo}
                for tp, la, lo in zip(state.twin.net_tp, state.twin.net_lat,
                                      state.twin.net_loss)][-window:]}
        return {"entity": entity, "series": series}

    @router.get("/kpis")
    async def kpis() -> dict[str, Any]:
        k = state.twin.kpis.model_dump()
        k["active_alerts"] = len(state.alerts.active())
        k["anomalous_entities"] = sum(
            1 for s in state.detector.scores.values()
            if s >= state.settings.detector.warn_threshold)
        return k

    @router.get("/alerts")
    async def list_alerts(status: str = "active") -> list[dict[str, Any]]:
        alerts = await state.alerts.list(status)
        return [a.model_dump() for a in alerts]

    @router.post("/alerts/{alert_id}/ack")
    async def ack_alert(alert_id: str) -> dict[str, Any]:
        a = await state.alerts.ack(alert_id)
        if not a:
            raise HTTPException(404, "alert not found")
        await state.hub.broadcast({"type": "alerts",
                                   "alerts": [x.model_dump()
                                              for x in state.alerts.active()]})
        return a.model_dump()

    @router.post("/attacks/start")
    async def start_attack(req: AttackStartRequest) -> dict[str, Any]:
        if req.type not in ATTACK_TYPES:
            raise HTTPException(400, f"type must be one of {ATTACK_TYPES}")
        try:
            event = state.engine.start_attack(req.type, req.target_id, req.duration_s)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        await state.storage.save_attack(event)
        await state.hub.broadcast({"type": "attack_events",
                                   "attacks": [a.event.model_dump()
                                               for a in state.engine.attacks.values()]})
        return event.model_dump()

    @router.post("/attacks/stop")
    async def stop_attack(req: AttackStopRequest) -> dict[str, Any]:
        stopped = state.engine.stop_attack(req.attack_id)
        for e in state.engine.attack_history:
            await state.storage.save_attack(e)
        await state.hub.broadcast({"type": "attack_events",
                                   "attacks": [a.event.model_dump()
                                               for a in state.engine.attacks.values()]})
        return {"stopped": stopped}

    @router.get("/attacks")
    async def attacks() -> dict[str, Any]:
        return {
            "active": [a.event.model_dump() for a in state.engine.attacks.values()],
            "history": [e.model_dump() for e in state.engine.attack_history[-50:]],
        }

    @router.post("/whatif")
    async def whatif(req: WhatIfRequest) -> dict[str, Any]:
        try:
            result = await asyncio.to_thread(
                run_whatif, state.engine, req.scenario, req.horizon_ticks)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return result.model_dump()

    @router.get("/forecast")
    async def forecast(entity: str = "network", horizon: int = 15) -> dict[str, Any]:
        fc = state.predictor.forecast(entity, "throughput_mbps", max(1, min(horizon, 60)))
        if fc is None:
            raise HTTPException(404, f"no forecast data for entity: {entity}")
        return fc.model_dump()

    @router.get("/config")
    async def get_config() -> dict[str, Any]:
        s = state.settings
        return {"tick_ms": s.tick_ms, "paused": state.engine.paused,
                "alert_threshold": s.detector.alert_threshold,
                "warn_threshold": s.detector.warn_threshold,
                "z_alert": s.detector.z_alert,
                "auto_attacks": s.auto_attacks,
                "ollama_model": s.llm.model}

    @router.post("/config")
    async def set_config(req: ConfigUpdate) -> dict[str, Any]:
        if req.tick_ms is not None:
            state.settings.tick_ms = max(250, min(int(req.tick_ms), 5000))
            state.engine.tick_s = state.settings.tick_s
        if req.alert_threshold is not None:
            state.settings.detector.alert_threshold = float(req.alert_threshold)
            state.detector.s.alert_threshold = state.settings.detector.alert_threshold
        if req.warn_threshold is not None:
            state.settings.detector.warn_threshold = float(req.warn_threshold)
            state.detector.s.warn_threshold = state.settings.detector.warn_threshold
        if req.auto_attacks is not None:
            state.settings.auto_attacks = bool(req.auto_attacks)
            if req.auto_attacks and state.engine._auto_task is None:
                state.engine._auto_task = asyncio.create_task(
                    state.engine._auto_attack_loop())
        if req.paused is not None:
            state.engine.paused = bool(req.paused)
        if req.ollama_model is not None:
            state.settings.llm.model = req.ollama_model
        return await get_config()

    @router.post("/twin/reset")
    async def reset_twin() -> dict[str, Any]:
        state.twin.reset()
        state.detector.reset()
        state.predictor.reset()
        return {"status": "reset", "tick": state.engine.tick}

    @router.post("/analyst/ask")
    async def analyst_ask(req: AskRequest) -> dict[str, Any]:
        if not req.question.strip():
            raise HTTPException(400, "question must not be empty")
        answer = await state.analyst.ask(req.question)
        return answer.model_dump()

    # ---- v2: real-world sync -------------------------------------------------
    @router.get("/sync")
    async def sync_status() -> dict[str, Any]:
        return {"network_fidelity": state.sync.network_fidelity(),
                "udp_listening": state.ingest_server.listening,
                "entities": state.sync.snapshot()}

    @router.post("/sync/mode")
    async def sync_mode(req: SyncModeRequest) -> dict[str, Any]:
        if req.entity not in state.engine.topology.nodes:
            raise HTTPException(404, f"unknown entity: {req.entity}")
        try:
            state.sync.force_mode(req.entity, req.mode)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return {"entity": req.entity, "mode": req.mode}

    @router.get("/sync/fidelity")
    async def sync_fidelity(entity: str | None = None) -> dict[str, Any]:
        if entity:
            es = state.sync.entities.get(entity)
            if not es:
                raise HTTPException(404, f"no sync state for entity: {entity}")
            return {"entity_id": entity, "mode": es.mode,
                    "fidelity": es.fidelity,
                    "pairs": {m: [[round(a, 3), round(b, 3)] for a, b in es.pairs[m]]
                              for m in es.pairs}}
        snap = state.sync.snapshot()
        return {"network_fidelity": state.sync.network_fidelity(),
                "entities": [{"entity_id": s["entity_id"], "mode": s["mode"],
                              "fidelity": s["fidelity"],
                              "divergence": s["divergence"]} for s in snap],
                "trend": list(state.research.fidelity_trend)[-60:]}

    @router.post("/ingest/telemetry", dependencies=[Depends(verify_ingest_auth)])
    async def ingest_telemetry(request: Request, payload: Any = None) -> dict[str, Any]:
        from nettwin.ingestion.normalize import parse_payload
        import json as _json
        try:
            if payload is None:
                raw_bytes = await request.body()
                if raw_bytes:
                    payload = _json.loads(raw_bytes.decode("utf-8"))
            records = payload if isinstance(payload, (list, dict)) else _json.loads(payload)
            if isinstance(records, dict):
                records = [records]
            batch = state.normalizer.normalize(records)
        except Exception as exc:
            raise HTTPException(400, f"bad telemetry payload: {exc}")
        touched = state.sync.ingest(batch, state.settings.tick_s)
        return {"accepted": len(records), "entities": sorted(set(touched)),
                "errors": batch.errors}

    # ---- v2: explainability + root cause --------------------------------------
    @router.get("/explain/{alert_id}")
    async def explain_alert(alert_id: str) -> dict[str, Any]:
        alert = state.alerts.alerts.get(alert_id)
        if not alert:
            raise HTTPException(404, "alert not found")
        from nettwin.twin.explain import explain_entity
        hour = state.twin.latest.hour_of_day if state.twin.latest else 0.0
        result = explain_entity(state.detector, state.subspace,
                                alert.entity_id, hour)
        result["alert"] = alert.model_dump()
        return result

    @router.get("/rootcause/{alert_id}")
    async def rootcause_alert(alert_id: str) -> dict[str, Any]:
        alert = state.alerts.alerts.get(alert_id)
        if not alert:
            raise HTTPException(404, "alert not found")
        ranked = state.causal.rank(state.twin, state.detector,
                                   focus=alert.entity_id,
                                   warn=state.settings.detector.warn_threshold)
        return {"alert_id": alert_id, "focus": alert.entity_id,
                "chain": ranked}

    # ---- v2: attack-graph risk ---------------------------------------------------
    @router.get("/risk")
    async def risk() -> dict[str, Any]:
        return state.risk.snapshot()

    # ---- v2: response agent -------------------------------------------------------
    @router.get("/response/recommendations")
    async def response_recommendations() -> dict[str, Any]:
        proposed = [{k: v for k, v in a.items() if k != "ctx"}
                    for a in state.response.actions.values()
                    if a["status"] == "proposed"]
        return {"mode": state.response.mode, "recommendations": proposed}

    @router.post("/response/apply")
    async def response_apply(req: ResponseActionRequest) -> dict[str, Any]:
        try:
            return state.response.apply(req.id)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @router.post("/response/revert")
    async def response_revert(req: ResponseActionRequest) -> dict[str, Any]:
        try:
            return state.response.revert(req.id)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @router.post("/response/mode")
    async def response_mode(req: ResponseModeRequest) -> dict[str, Any]:
        if req.mode not in ("auto", "approval", "off"):
            raise HTTPException(400, "mode must be auto|approval|off")
        state.response.mode = req.mode
        state.settings.response.mode = req.mode
        return {"mode": state.response.mode}

    @router.get("/response/history")
    async def response_history() -> dict[str, Any]:
        return {"history": state.response.history,
                "cumulative_reward": state.research.cumulative_reward}

    # ---- v2: research metrics ------------------------------------------------------
    @router.get("/research/metrics")
    async def research_metrics() -> dict[str, Any]:
        return state.research.snapshot()

    # ---- v3: AWS cloud integration ------------------------------------------------
    @router.get("/aws/status")
    async def aws_status() -> dict[str, Any]:
        if state.aws_adapter is not None:
            return state.aws_adapter.status()
        return {"connected": False, "reason": "aws.enabled is false in config"}

    @router.get("/aws/cost")
    async def aws_cost() -> dict[str, Any]:
        if not state.settings.aws.enabled:
            return {"error": "AWS not enabled"}
        try:
            from scripts.aws_cost_guard import tier1_cloudwatch, tier2_local_estimate
            region = state.settings.aws.region
            t1 = tier1_cloudwatch(region)
            t2 = tier2_local_estimate(region)
            return {
                "tier1_cloudwatch": t1,
                "tier2_local_estimate": t2,
                "limit_daily_usd": state.settings.aws.cost_limit_daily_usd,
            }
        except Exception as exc:
            return {"error": str(exc)}

    @router.get("/actuation/status")
    async def actuation_status() -> dict[str, Any]:
        return {
            "enabled": state.settings.actuation.enabled,
            "dry_run": state.settings.actuation.dry_run,
            "allowed_actions": state.settings.actuation.allowed_actions,
        }

    @router.post("/actuation/disable")
    async def actuation_disable() -> dict[str, Any]:
        state.settings.actuation.enabled = False
        return {"enabled": False, "note": "actuation disabled for this process"}

    # ---- Benchmark Datasets (Thakkar & Lohiya 2020 Table 3) ------------------------
    @router.get("/datasets")
    async def list_benchmark_datasets() -> dict[str, Any]:
        try:
            from real_data.loader import DatasetCatalog
            catalog = DatasetCatalog.list_datasets()
            return {"status": "ok", "total": len(catalog), "datasets": catalog}
        except Exception as exc:
            return {"status": "error", "error": str(exc), "datasets": []}

    @router.get("/datasets/{dataset_id}")
    async def get_benchmark_dataset(dataset_id: str, limit: int = 50) -> dict[str, Any]:
        try:
            from real_data.loader import DatasetCatalog
            info = DatasetCatalog.get_dataset_info(dataset_id)
            if not info:
                raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
            records = DatasetCatalog.load_records(dataset_id, max_rows=limit)
            return {"status": "ok", "info": info, "preview_records": records, "preview_count": len(records)}
        except HTTPException:
            raise
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # ---- AWS Cloud Traffic Streamer (Zero Local Disk, $0.00 Cost Open Data) --------
    @router.get("/cloud-traffic/datasets")
    async def list_cloud_traffic_datasets() -> dict[str, Any]:
        """Lists registered AWS S3 cloud datasets with cost and format indicators."""
        from nettwin.ingestion.aws_streamer import AWSCloudTrafficStreamer
        datasets = AWSCloudTrafficStreamer.list_available_cloud_datasets()
        return {"status": "ok", "total": len(datasets), "datasets": datasets}

    @router.post("/cloud-traffic/stream/start")
    async def start_cloud_traffic_stream(req: CloudStreamStartRequest) -> dict[str, Any]:
        """Starts an on-demand in-memory streaming session directly from AWS S3."""
        if state.cloud_streamer is None:
            raise HTTPException(status_code=500, detail="Cloud streamer not initialized")
        res = await state.cloud_streamer.start_stream(
            dataset_id=req.dataset,
            speed_multiplier=req.speed,
            sample_pct=req.sample_pct,
            attack_only=req.attack_only,
            batch_size=req.batch_size,
            max_records=req.max_records,
        )
        return {"status": "ok", "stream": res, "stats": state.cloud_streamer.stats.to_dict()}

    @router.post("/cloud-traffic/stream/stop")
    async def stop_cloud_traffic_stream() -> dict[str, Any]:
        """Immediately stops the cloud stream and cleans up resources."""
        if state.cloud_streamer is None:
            raise HTTPException(status_code=500, detail="Cloud streamer not initialized")
        res = await state.cloud_streamer.stop_stream()
        return {"status": "ok", "result": res, "stats": state.cloud_streamer.stats.to_dict()}

    @router.get("/cloud-traffic/stream/status")
    async def get_cloud_traffic_stream_status() -> dict[str, Any]:
        """Returns live metrics of the active AWS cloud stream."""
        if state.cloud_streamer is None:
            return {"status": "idle", "is_active": False, "storage_used_bytes": 0}
        return {"status": "ok", "stats": state.cloud_streamer.stats.to_dict()}

    return router
