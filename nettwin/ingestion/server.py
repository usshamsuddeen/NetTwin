"""Multi-protocol Ingestion Server: RFC3164 UDP 5514 and RFC5425 TLS/mTLS 6514."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import ssl
from pathlib import Path
from typing import Any, Callable, List, Optional, Set

from nettwin.ingestion.normalize import Normalizer, parse_payload

log = logging.getLogger("nettwin.ingestion")


class TelemetryUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, normalizer: Normalizer, on_batch: Callable[[Any], None]) -> None:
        self.normalizer = normalizer
        self.on_batch = on_batch
        self.datagrams = 0
        self.errors = 0

    def datagram_received(self, data: bytes, addr: Any) -> None:
        try:
            records = parse_payload(data)
            batch = self.normalizer.normalize(records)
            self.on_batch(batch)
            self.datagrams += 1
        except Exception as exc:
            self.errors += 1
            log.debug("bad datagram from %s: %s", addr, exc)


class IngestionServer:
    """
    Dual-protocol syslog ingestion server:
    1. RFC3164 / RFC5424 UDP listener on port 5514.
    2. RFC5425 TLS / mTLS TCP stream listener on port 6514 with client cert validation.
    """

    def __init__(
        self,
        port: int = 5514,
        normalizer: Optional[Normalizer] = None,
        on_batch: Optional[Callable[[Any], None]] = None,
        tls_port: int = 6514,
        tls_cert_file: str = "",
        tls_key_file: str = "",
        tls_ca_file: str = "",
        tls_require_client_cert: bool = True,
        allowed_cert_fps: Optional[List[str]] = None,
        ssl_context: Optional[ssl.SSLContext] = None,
    ) -> None:
        self.port = port
        self.normalizer = normalizer or Normalizer(lambda _: None)
        self.on_batch = on_batch or (lambda _: None)
        self.tls_port = tls_port
        self.tls_cert_file = tls_cert_file
        self.tls_key_file = tls_key_file
        self.tls_ca_file = tls_ca_file
        self.tls_require_client_cert = tls_require_client_cert
        self.ssl_context = ssl_context
        self.allowed_cert_fps: Set[str] = {
            fp.strip().lower() for fp in (allowed_cert_fps or []) if fp.strip()
        }

        # UDP state
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.protocol: Optional[TelemetryUDPProtocol] = None
        self.udp_listening = False

        # TLS state
        self.tls_server: Optional[asyncio.Server] = None
        self.tls_listening = False
        self.tls_messages = 0
        self.tls_errors = 0

    @property
    def listening(self) -> bool:
        """True if either UDP or TLS listener is active."""
        return self.udp_listening or self.tls_listening

    def build_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Constructs an SSLContext for RFC5425 mTLS."""
        if self.ssl_context:
            return self.ssl_context

        if not self.tls_cert_file or not self.tls_key_file:
            return None

        cert_p = Path(self.tls_cert_file)
        key_p = Path(self.tls_key_file)
        if not cert_p.exists() or not key_p.exists():
            log.warning("RFC5425 TLS cert or key not found: %s, %s", cert_p, key_p)
            return None

        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(certfile=str(cert_p), keyfile=str(key_p))

        if self.tls_require_client_cert:
            if self.tls_ca_file and Path(self.tls_ca_file).exists():
                ctx.load_verify_locations(cafile=self.tls_ca_file)
                ctx.verify_mode = ssl.CERT_REQUIRED
            else:
                log.warning(
                    "RFC5425 client verification requested but tls_ca_file missing/not found: %s",
                    self.tls_ca_file,
                )
                ctx.verify_mode = ssl.CERT_OPTIONAL
        else:
            ctx.verify_mode = ssl.CERT_NONE

        return ctx

    async def _handle_tls_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Processes incoming RFC5425 TLS syslog TCP connection with mTLS validation."""
        peer = writer.get_extra_info("peername")
        ssl_obj = writer.get_extra_info("ssl_object")

        # Verify client certificate fingerprint if required
        if ssl_obj and self.allowed_cert_fps:
            try:
                peercert_der = ssl_obj.getpeercert(binary_form=True)
                if not peercert_der:
                    log.warning("RFC5425 reject from %s: client certificate missing", peer)
                    writer.close()
                    await writer.wait_closed()
                    return

                peercert_fp = hashlib.sha256(peercert_der).hexdigest().lower()
                if peercert_fp not in self.allowed_cert_fps:
                    log.warning(
                        "RFC5425 reject from %s: client cert FP %s not in allowed set",
                        peer,
                        peercert_fp,
                    )
                    writer.close()
                    await writer.wait_closed()
                    return
                log.debug("RFC5425 client authenticated: FP=%s from %s", peercert_fp[:16], peer)
            except Exception as exc:
                log.warning("RFC5425 client cert check error from %s: %s", peer, exc)
                writer.close()
                await writer.wait_closed()
                return

        # Stream / frame reader for RFC5425 messages
        buffer = b""
        try:
            while not reader.at_eof():
                data = await reader.read(4096)
                if not data:
                    break
                buffer += data

                # Split by newline or handle octet-counted syslog frames
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue

                    # If line starts with octet-count e.g. "124 <165>1 ...", strip count
                    if " " in line_str:
                        parts = line_str.split(" ", 1)
                        if parts[0].isdigit() and parts[1].startswith("<"):
                            line_str = parts[1]

                    try:
                        records = parse_payload(line_str)
                        batch = self.normalizer.normalize(records)
                        self.on_batch(batch)
                        self.tls_messages += 1
                    except Exception as parse_exc:
                        self.tls_errors += 1
                        log.debug("RFC5425 frame parse error from %s: %s", peer, parse_exc)

            # Process any remaining buffer tail
            if buffer.strip():
                try:
                    records = parse_payload(buffer.decode("utf-8", errors="replace"))
                    batch = self.normalizer.normalize(records)
                    self.on_batch(batch)
                    self.tls_messages += 1
                except Exception as exc:
                    self.tls_errors += 1
        except Exception as exc:
            log.debug("RFC5425 connection error from %s: %s", peer, exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        # 1. Start UDP 5514 listener
        if self.port > 0:
            try:
                transport, protocol = await loop.create_datagram_endpoint(
                    lambda: TelemetryUDPProtocol(self.normalizer, self.on_batch),
                    local_addr=("0.0.0.0", self.port),
                )
                self.transport = transport
                self.protocol = protocol  # type: ignore[assignment]
                self.udp_listening = True
                log.info("ingestion UDP listener active on port %d", self.port)
            except OSError as exc:
                self.udp_listening = False
                log.warning(
                    "ingestion UDP port %d unavailable: %s (HTTP push still works)",
                    self.port,
                    exc,
                )

        # 2. Start RFC5425 TLS 6514 listener if SSL context or certificates available
        if self.tls_port > 0:
            ssl_ctx = self.build_ssl_context()
            if ssl_ctx:
                try:
                    self.tls_server = await asyncio.start_server(
                        self._handle_tls_client,
                        host="0.0.0.0",
                        port=self.tls_port,
                        ssl=ssl_ctx,
                    )
                    self.tls_listening = True
                    log.info(
                        "ingestion RFC5425 TLS (mTLS) listener active on port %d",
                        self.tls_port,
                    )
                except OSError as exc:
                    self.tls_listening = False
                    log.warning(
                        "ingestion TLS port %d unavailable: %s",
                        self.tls_port,
                        exc,
                    )
            else:
                log.info(
                    "ingestion RFC5425 TLS listener skipped (no TLS certificates configured)"
                )

    async def stop(self) -> None:
        if self.transport:
            self.transport.close()
            self.transport = None
            self.udp_listening = False

        if self.tls_server:
            self.tls_server.close()
            await self.tls_server.wait_closed()
            self.tls_server = None
            self.tls_listening = False
