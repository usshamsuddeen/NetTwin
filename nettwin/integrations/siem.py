"""SIEM export formats: CEF and LEEF."""
from __future__ import annotations

import time
from typing import Any


class SIEMExporter:
    """Convert NetTwin alerts to common SIEM event formats."""

    CEF_VERSION = "0"
    LEEF_VERSION = "2.0"

    def __init__(self, vendor: str = "NetTwin", product: str = "NetTwin",
                 version: str = "2.0.0") -> None:
        self.vendor = vendor
        self.product = product
        self.version = version

    def to_cef(self, alert: dict[str, Any]) -> str:
        # CEF:0|Vendor|Product|Version|Signature ID|Name|Severity|Extension
        severity = {"critical": 10, "warning": 5, "info": 1}.get(
            alert.get("severity", ""), 1)
        name = alert.get("message", "NetTwin alert").replace("|", "\\|")
        sig = f"{alert.get('alert_type', 'nettwin:alert')}:{alert.get('entity_id', 'unknown')}"
        ts = int((alert.get("created_at") or time.time()) * 1000)
        exts = [
            f"rt={ts}",
            f"src={alert.get('entity_id', 'unknown')}",
            f"msg={name}",
            f"cs1={alert.get('id', '')}",
            f"cs1Label=alert_id",
            f"cs2={alert.get('entity_kind', '')}",
            f"cs2Label=entity_kind",
            f"cs3={alert.get('status', '')}",
            f"cs3Label=status",
        ]
        return (f"CEF:{self.CEF_VERSION}|{self.vendor}|{self.product}|{self.version}|"
                f"{sig}|{name}|{severity}|{' '.join(exts)}")

    def to_leef(self, alert: dict[str, Any]) -> str:
        # LEEF:2.0|Vendor|Product|Version|EventID|devTime=...
        event_id = alert.get("alert_type", "nettwin:alert").replace("|", "\\|")
        ts = int((alert.get("created_at") or time.time()) * 1000)
        fields = {
            "devTime": ts,
            "devTimeFormat": "epoch",
            "src": alert.get("entity_id", "unknown"),
            "alertId": alert.get("id", ""),
            "entityKind": alert.get("entity_kind", ""),
            "severity": alert.get("severity", ""),
            "status": alert.get("status", ""),
            "score": alert.get("score", 0),
            "message": alert.get("message", ""),
        }
        ext = "\t".join(f"{k}={v}" for k, v in fields.items())
        return (f"LEEF:{self.LEEF_VERSION}|{self.vendor}|{self.product}|{self.version}|"
                f"{event_id}|{ext}")

    def export(self, alerts: list[dict[str, Any]], fmt: str = "cef") -> list[str]:
        fn = self.to_cef if fmt == "cef" else self.to_leef
        return [fn(a) for a in alerts]
