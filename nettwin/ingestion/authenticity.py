"""
NetTwin 3.0 Inbound Telemetry Authenticity & Forwarder Authorization
====================================================================
Production-grade inbound verification for POST /api/ingest/telemetry:
1. Inbound HMAC-SHA256 verification over f"{timestamp}.{raw_body}".
2. Anti-replay protection with 30s clock skew window and sliding nonce cache.
3. mTLS Client Certificate Fingerprint verification (X-Client-Cert-FP).
4. Trusted Forwarder Source IP Whitelisting (CloudWatch Lambda + On-Prem Syslog).
5. Internal process bypass token (X-Internal-Token) for in-memory aws_streamer.
"""
from __future__ import annotations

import collections
import hashlib
import hmac
import logging
import os
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, Request, status

log = logging.getLogger("nettwin.authenticity")

# Default trusted forwarder network identities
DEFAULT_ALLOWED_FORWARDERS: List[str] = [
    "127.0.0.1",
    "::1",
    "10.0.0.5",     # CloudWatch Lambda NAT Gateway IP
    "52.94.76.1",   # AWS CloudWatch regional forwarder IP
]

# Default known on-prem syslog mTLS client cert fingerprints (SHA-256)
DEFAULT_ALLOWED_CERT_FPS: List[str] = [
    # SHA-256 fingerprint for enterprise router forwarder
    "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
    "b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01",
]

DEFAULT_INGEST_SECRET = "nettwin-telemetry-ingest-secret-key-32b"
DEFAULT_INTERNAL_TOKEN = "nettwin-internal-streamer-token-99x"
DEFAULT_SKEW_WINDOW_S = 30.0


class IngestAuthenticator:
    """
    Stateful authenticator providing anti-replay protection, HMAC-SHA256 verification,
    and trusted forwarder policy enforcement.
    """

    def __init__(
        self,
        secret: Optional[str] = None,
        internal_token: Optional[str] = None,
        skew_window_s: float = DEFAULT_SKEW_WINDOW_S,
        allowed_forwarders: Optional[List[str]] = None,
        allowed_cert_fps: Optional[List[str]] = None,
        enforce_ip_whitelist: bool = False,
    ) -> None:
        self.secret = (
            secret
            or os.getenv("NETTWIN_INGEST_SECRET")
            or DEFAULT_INGEST_SECRET
        )
        self.internal_token = (
            internal_token
            or os.getenv("NETTWIN_INTERNAL_TOKEN")
            or DEFAULT_INTERNAL_TOKEN
        )
        self.skew_window_s = skew_window_s
        self.allowed_forwarders: Set[str] = set(
            allowed_forwarders
            or os.getenv("NETTWIN_ALLOWED_FORWARDERS", "").split(",")
            or DEFAULT_ALLOWED_FORWARDERS
        )
        # Clean empty entries
        self.allowed_forwarders = {f.strip() for f in self.allowed_forwarders if f.strip()}
        if not self.allowed_forwarders:
            self.allowed_forwarders = set(DEFAULT_ALLOWED_FORWARDERS)

        self.allowed_cert_fps: Set[str] = set(
            allowed_cert_fps
            or os.getenv("NETTWIN_ALLOWED_CERT_FPS", "").split(",")
            or DEFAULT_ALLOWED_CERT_FPS
        )
        self.allowed_cert_fps = {fp.strip().lower() for fp in self.allowed_cert_fps if fp.strip()}
        if not self.allowed_cert_fps:
            self.allowed_cert_fps = set(DEFAULT_ALLOWED_CERT_FPS)

        self.enforce_ip_whitelist = (
            enforce_ip_whitelist
            or os.getenv("ENV", "").lower() in ("prod", "production")
            or os.getenv("NETTWIN_ENFORCE_IP_WHITELIST", "0") in ("1", "true", "yes")
        )

        # Sliding window nonce cache to reject replayed requests within the 30s window
        # Stores (timestamp, signature_hash) -> time_added
        self._seen_signatures: Dict[str, float] = {}
        self._last_cleanup = time.time()

    def _clean_replay_cache(self, now: float) -> None:
        """Evict signatures older than 2x the skew window to prevent memory leaks."""
        if now - self._last_cleanup > 15.0:
            cutoff = now - (self.skew_window_s * 2)
            self._seen_signatures = {
                sig: ts for sig, ts in self._seen_signatures.items() if ts > cutoff
            }
            self._last_cleanup = now

    def generate_signature(self, timestamp: str | int | float, raw_body: str | bytes) -> str:
        """Generates standard HMAC-SHA256 signature for telemetry forwarders."""
        if isinstance(raw_body, bytes):
            body_str = raw_body.decode("utf-8", errors="replace")
        else:
            body_str = str(raw_body)
        msg = f"{timestamp}.{body_str}"
        return hmac.new(self.secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

    def verify(self, headers: Dict[str, str], raw_body: bytes | str, source_ip: str = "127.0.0.1") -> tuple[bool, str]:
        """
        Pure verification logic checking headers, body, and IP against authenticity policies.
        Returns (True, "ok") if valid, or (False, error_detail) if unauthorized.
        """
        # 0. Source IP whitelist
        if self.enforce_ip_whitelist and source_ip not in self.allowed_forwarders:
            log.warning("Rejected telemetry from unauthorized source IP: %s", source_ip)
            return False, f"Source IP {source_ip} not in allowed forwarders"

        # 1. Internal Process Token
        internal_token = headers.get("X-Internal-Token") or headers.get("x-internal-token")
        if internal_token and hmac.compare_digest(internal_token, self.internal_token):
            return True, "authenticated_internal_token"

        # 2. mTLS Client Cert Fingerprint
        client_cert_fp = headers.get("X-Client-Cert-FP") or headers.get("x-client-cert-fp")
        if client_cert_fp:
            clean_fp = client_cert_fp.strip().lower()
            if clean_fp in self.allowed_cert_fps:
                return True, "authenticated_mtls_cert"
            return False, "Invalid client certificate fingerprint for mTLS"

        # 3. HMAC-SHA256 + Anti-Replay
        x_sig = headers.get("X-NetTwin-Signature") or headers.get("x-nettwin-signature")
        x_ts = headers.get("X-Timestamp") or headers.get("x-timestamp")

        if not x_sig or not x_ts:
            return False, "Missing required authenticity headers (X-NetTwin-Signature, X-Timestamp)"

        try:
            ts = float(x_ts)
        except (ValueError, TypeError):
            return False, "Invalid timestamp format in X-Timestamp"

        now = time.time()
        skew = abs(now - ts)
        if skew > self.skew_window_s:
            return False, f"Replay attack - timestamp skew ({skew:.1f}s) exceeds {self.skew_window_s}s"

        self._clean_replay_cache(now)
        sig_clean = x_sig.strip()
        if sig_clean.startswith("sha256="):
            sig_clean = sig_clean[7:]

        replay_key = f"{x_ts}:{sig_clean}"
        if replay_key in self._seen_signatures:
            return False, "Replay attack - duplicate telemetry transmission detected"
        self._seen_signatures[replay_key] = now

        if isinstance(raw_body, bytes):
            raw_body_str = raw_body.decode("utf-8", errors="replace")
        else:
            raw_body_str = str(raw_body)

        expected_sig = self.generate_signature(x_ts, raw_body_str)
        if not hmac.compare_digest(expected_sig, sig_clean):
            return False, "HMAC validation failed - telemetry spoofed or corrupted"

        return True, "ok"

    async def authenticate_request(self, request: Request) -> bool:
        """FastAPI dependency adapter for authenticate_request."""
        client_ip = request.client.host if request.client else "unknown"
        headers = dict(request.headers)
        raw_body_bytes = await request.body()

        is_valid, reason = self.verify(headers, raw_body_bytes, client_ip)
        if not is_valid:
            if "Source IP" in reason:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=reason)
        return True


# Global default authenticator instance
default_authenticator = IngestAuthenticator()


async def verify_ingest_auth(request: Request) -> bool:
    """
    FastAPI dependency function used to protect POST /api/ingest/telemetry.
    Can be overridden or customized via app.state.ingest_authenticator.
    """
    auth: IngestAuthenticator = getattr(
        request.app.state, "ingest_authenticator", default_authenticator
    )
    return await auth.authenticate_request(request)


def generate_ingest_headers(
    raw_body: str | bytes,
    secret: Optional[str] = None,
    timestamp: Optional[float] = None,
) -> Dict[str, str]:
    """Utility function for forwarders (CloudWatch Lambda, Syslog, tests) to sign payloads."""
    ts = str(int(timestamp or time.time()))
    authenticator = IngestAuthenticator(secret=secret)
    sig = authenticator.generate_signature(ts, raw_body)
    return {
        "X-Timestamp": ts,
        "X-NetTwin-Signature": f"sha256={sig}",
        "Content-Type": "application/json",
    }
