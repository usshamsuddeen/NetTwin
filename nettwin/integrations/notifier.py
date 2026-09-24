"""Async webhook / ChatOps notifier with signature header."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import urllib.request

log = logging.getLogger("nettwin.integrations")


class WebhookNotifier:
    """Post alerts and scenario results to a webhook URL."""

    def __init__(self, url: str, secret: str = "", timeout_s: float = 10.0) -> None:
        self.url = url
        self.secret = secret.encode() if secret else b""
        self.timeout_s = timeout_s

    def _sign(self, body: bytes) -> str:
        if not self.secret:
            return ""
        return hmac.new(self.secret, body, hashlib.sha256).hexdigest()

    async def send(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        envelope = {"event": event_type, "payload": payload}
        body = json.dumps(envelope).encode()
        req = urllib.request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST")
        sig = self._sign(body)
        if sig:
            req.add_header("X-NetTwin-Signature", f"sha256={sig}")
        try:
            resp = await __import__("asyncio").to_thread(
                urllib.request.urlopen, req, timeout=self.timeout_s)
            return {"ok": True, "status": resp.getcode()}
        except Exception as exc:
            log.warning("webhook delivery failed: %s", exc)
            return {"ok": False, "error": str(exc)}
