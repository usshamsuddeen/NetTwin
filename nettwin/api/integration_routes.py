"""Outbound integrations API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nettwin.api.app import AppState
from nettwin.integrations import SIEMExporter, WebhookNotifier
from nettwin.integrations.prometheus import prometheus_metrics


class WebhookTestRequest(BaseModel):
    url: str
    secret: str = ""


class SIEMExportRequest(BaseModel):
    fmt: str = "cef"  # cef | leef
    status: str = "all"  # all | active


def build_integration_router(state: AppState) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post("/integrations/webhook/test")
    async def webhook_test(req: WebhookTestRequest) -> dict[str, Any]:
        notifier = WebhookNotifier(req.url, req.secret)
        return await notifier.send("test", {"message": "NetTwin webhook test"})

    @router.post("/integrations/siem/export")
    async def siem_export(req: SIEMExportRequest) -> dict[str, Any]:
        if req.fmt not in ("cef", "leef"):
            raise HTTPException(400, "fmt must be cef or leef")
        alerts = await state.alerts.list(req.status)
        exporter = SIEMExporter()
        events = exporter.export([a.model_dump() for a in alerts], fmt=req.fmt)
        return {"fmt": req.fmt, "count": len(events), "events": events}

    @router.get("/prom")
    async def prom_metrics() -> str:
        return prometheus_metrics(state)

    return router
