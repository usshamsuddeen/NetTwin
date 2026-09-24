"""AWS Traffic Mirroring live parser.

AWS Traffic Mirroring sends a copy of network traffic to a target as
VXLAN-encapsulated packets (UDP port 4789). This adapter strips the VXLAN
header, parses the inner IPv4/TCP/UDP/ICMP packet, and feeds flow records into
the existing Normalizer → SyncEngine pipeline.

Use of the optional ``dpkt`` package is preferred; a small built-in fallback
parser is provided for deployments that do not install it.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import struct
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("nettwin.aws.traffic_mirror")


def _has_dpkt() -> bool:
    try:
        import dpkt  # type: ignore[import-not-found]
        return True
    except Exception:
        return False


@dataclass
class TrafficMirrorStats:
    """Observable counters."""

    packets: int = 0
    bytes: int = 0
    flows: int = 0
    errors: int = 0
    started_at: float = field(default_factory=time.time)
    last_packet_ts: float = 0.0


def _parse_vxlan_packet(data: bytes) -> dict[str, Any] | None:
    """Strip VXLAN header and parse the inner IPv4 packet.

    VXLAN header is 8 bytes:
        flags(1) + reserved(3) + vni(3) + reserved(1)
    Inner payload is an Ethernet frame.  We expect IPv4 (ethertype 0x0800).
    """
    if len(data) < 8 + 14 + 20:
        return None
    inner = data[8:]
    ethertype = struct.unpack_from("!H", inner, 12)[0]
    if ethertype != 0x0800:
        return None

    ip_start = 14
    ip_data = inner[ip_start:]
    if len(ip_data) < 20:
        return None

    version_ihl = ip_data[0]
    ihl = (version_ihl & 0x0F) * 4
    total_len = struct.unpack_from("!H", ip_data, 2)[0]
    proto = ip_data[9]
    src_ip = str(ipaddress.IPv4Address(ip_data[12:16]))
    dst_ip = str(ipaddress.IPv4Address(ip_data[16:20]))

    payload = ip_data[ihl:]
    src_port: int | None = None
    dst_port: int | None = None

    if proto == 6 and len(payload) >= 4:  # TCP
        src_port, dst_port = struct.unpack_from("!HH", payload, 0)
    elif proto == 17 and len(payload) >= 4:  # UDP
        src_port, dst_port = struct.unpack_from("!HH", payload, 0)
    elif proto == 1:  # ICMP
        src_port = dst_port = None

    proto_name = {1: "ICMP", 6: "TCP", 17: "UDP"}.get(proto, f"IP-{proto}")
    return {
        "type": "flow",
        "src": src_ip,
        "dst": dst_ip,
        "proto": proto_name,
        "src_port": src_port,
        "dst_port": dst_port,
        "bytes": total_len,
        "packets": 1,
        "mirror": True,
    }


def _parse_with_dpkt(data: bytes) -> dict[str, Any] | None:
    import dpkt  # type: ignore[import-not-found]
    try:
        eth = dpkt.ethernet.Ethernet(data[8:])
        ip = eth.data
        if not isinstance(ip, dpkt.ip.IP):
            return None
        src_ip = str(ipaddress.IPv4Address(ip.src))
        dst_ip = str(ipaddress.IPv4Address(ip.dst))
        proto = ip.p
        src_port: int | None = None
        dst_port: int | None = None
        if isinstance(ip.data, (dpkt.tcp.TCP, dpkt.udp.UDP)):
            src_port = ip.data.sport
            dst_port = ip.data.dport
        proto_name = {1: "ICMP", 6: "TCP", 17: "UDP"}.get(proto, f"IP-{proto}")
        return {
            "type": "flow",
            "src": src_ip,
            "dst": dst_ip,
            "proto": proto_name,
            "src_port": src_port,
            "dst_port": dst_port,
            "bytes": len(ip),
            "packets": 1,
            "mirror": True,
        }
    except Exception:
        return None


class VXLANHandler(asyncio.DatagramProtocol):
    """asyncio datagram protocol for VXLAN packets."""

    def __init__(self, adapter: "TrafficMirrorAdapter") -> None:
        self.adapter = adapter
        self._parse = _parse_with_dpkt if _has_dpkt() else _parse_vxlan_packet

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.adapter.stats.packets += 1
        self.adapter.stats.bytes += len(data)
        self.adapter.stats.last_packet_ts = time.time()
        rec = self._parse(data)
        if rec is None:
            self.adapter.stats.errors += 1
            return
        self.adapter.stats.flows += 1
        try:
            batch = self.adapter.normalizer.normalize([rec])
            self.adapter.sync.ingest(batch, self.adapter.tick_s)
        except Exception as exc:
            self.adapter.stats.errors += 1
            log.warning("traffic mirror ingest error: %s", exc)

    def error_received(self, exc: Exception | None) -> None:
        self.adapter.stats.errors += 1
        log.warning("traffic mirror socket error: %s", exc)


class TrafficMirrorAdapter:
    """Live AWS Traffic Mirror target receiver.

    Parameters
    ----------
    settings : Settings
        Reads ``settings.aws.traffic_mirror_enabled`` and
        ``settings.aws.traffic_mirror_port`` (default 4789).
    normalizer : Normalizer
        Shared normalizer wired to ``SyncEngine.resolve``.
    sync : SyncEngine
        Receives normalized batches via ``.ingest()``.
    """

    def __init__(self, settings, normalizer, sync) -> None:
        self.aws = settings.aws
        self.normalizer = normalizer
        self.sync = sync
        self.tick_s: float = settings.tick_s
        self.port: int = getattr(self.aws, "traffic_mirror_port", 4789)
        self.stats = TrafficMirrorStats()
        self._transport: asyncio.DatagramTransport | None = None
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: VXLANHandler(self),
            local_addr=("0.0.0.0", self.port),
        )
        log.info("traffic mirror listener started on UDP:%d", self.port)

    async def stop(self) -> None:
        self._running = False
        if self._transport:
            self._transport.close()
            self._transport = None
        log.info("traffic mirror listener stopped")

    def status(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "port": self.port,
            "packets": self.stats.packets,
            "bytes": self.stats.bytes,
            "flows": self.stats.flows,
            "errors": self.stats.errors,
            "last_packet_ts": self.stats.last_packet_ts,
            "uptime_s": round(time.time() - self.stats.started_at, 1),
        }
