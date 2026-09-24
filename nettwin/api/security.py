"""API security middleware: API-key auth, CORS, and per-IP token-bucket rate limits.

These are intentionally dependency-light: only FastAPI/Starlette stdlib.
"""
from __future__ import annotations

import asyncio
import ipaddress
import time
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from nettwin.config import Settings


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() in ("localhost", "127.0.0.1", "::1")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Require ``X-API-Key`` header when an api_key is configured.

    Localhost callers are exempt by default so local dev stays frictionless.
    Health/readiness endpoints and WebSocket upgrade requests are always exempt.
    """

    def __init__(self, app: Any, settings: APISettings) -> None:
        super().__init__(app)
        self.api_key = settings.api_key
        self.header = settings.api_key_header
        self.exempt_localhost = settings.localhost_exempt
        self._exempt_paths = {"/api/health", "/api/ready", "/api/ingest/telemetry"}

    async def dispatch(self, request: Request, call_next: Any):
        if not self.api_key:
            return await call_next(request)
        if request.scope["type"] == "websocket":
            return await call_next(request)
        if request.url.path in self._exempt_paths:
            return await call_next(request)
        client = request.client.host if request.client else None
        if self.exempt_localhost and _is_loopback(client):
            return await call_next(request)
        if request.headers.get(self.header) != self.api_key:
            return JSONResponse(
                {"detail": "Invalid or missing API key"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP token-bucket rate limiter.

    Two buckets per client: a general bucket for all requests and a tighter
    bucket for mutating (state-changing) requests.
    """

    _buckets: dict[str, dict[str, dict[str, float]]] = {}
    _lock = asyncio.Lock()

    def __init__(self, app: Any, settings: APISettings) -> None:
        super().__init__(app)
        self.enabled = settings.rate_limit_enabled
        self.rpm = settings.rate_limit_requests_per_minute
        self.mpm = settings.rate_limit_mutations_per_minute

    def _bucket_for(self, client: str, kind: str, capacity: int) -> dict[str, float]:
        now = time.monotonic()
        if client not in self._buckets:
            self._buckets[client] = {}
        per_client = self._buckets[client]
        if kind not in per_client:
            per_client[kind] = {
                "tokens": float(capacity),
                "last": now,
            }
        return per_client[kind]

    async def dispatch(self, request: Request, call_next: Any):
        if not self.enabled:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        is_mutation = request.method in ("POST", "PUT", "DELETE", "PATCH")
        async with self._lock:
            # Always consume from the general bucket.
            ok = self._consume(client, "general", self.rpm)
            if ok and is_mutation:
                ok = self._consume(client, "mutation", self.mpm)
        if not ok:
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": "60"},
            )
        return await call_next(request)

    @classmethod
    def reset(cls) -> None:
        cls._buckets.clear()

    def _consume(self, client: str, kind: str, capacity: int) -> bool:
        bucket = self._bucket_for(client, kind, capacity)
        now = time.monotonic()
        elapsed = now - bucket["last"]
        bucket["last"] = now
        bucket["tokens"] = min(
            float(capacity),
            bucket["tokens"] + elapsed * capacity / 60.0,
        )
        if bucket["tokens"] < 1.0:
            return False
        bucket["tokens"] -= 1.0
        return True


def setup_security(app: Any, settings: Settings) -> None:
    """Register CORS, API-key and rate-limit middleware on the app."""
    origins = settings.api.cors_origins
    if origins:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(RateLimitMiddleware, settings=settings.api)
    app.add_middleware(APIKeyMiddleware, settings=settings.api)
