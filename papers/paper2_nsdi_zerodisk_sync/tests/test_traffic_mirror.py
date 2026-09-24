"""Tests for AWS Traffic Mirroring VXLAN parser."""
from __future__ import annotations


import os
import sys
from pathlib import Path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REPO_ROOT_PATH = Path(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import asyncio
import struct
from unittest.mock import MagicMock

import pytest

from nettwin.ingestion.adapters.traffic_mirror import (
    TrafficMirrorAdapter,
    TrafficMirrorStats,
    VXLANHandler,
    _has_dpkt,
    _parse_vxlan_packet,
    _parse_with_dpkt,
)


def _build_vxlan_tcp_packet(
    src_ip: str = "192.168.1.1",
    dst_ip: str = "192.168.1.2",
    src_port: int = 12345,
    dst_port: int = 80,
) -> bytes:
    """Build a minimal VXLAN-encapsulated IPv4/TCP SYN packet."""
    # VXLAN header: flags(I=1) + reserved(3) + vni(3) + reserved(1)
    vxlan = struct.pack("!B", 0x08) + b"\x00\x00\x00" + b"\x00\x00\x01" + b"\x00"

    # Ethernet header (14 bytes)
    eth = b"\x00" * 12 + struct.pack("!H", 0x0800)

    # IPv4 header (20 bytes)
    src = struct.unpack("!I", bytes(map(int, src_ip.split("."))))[0]
    dst = struct.unpack("!I", bytes(map(int, dst_ip.split("."))))[0]
    tcp_len = 20
    total_len = 20 + tcp_len
    ip = struct.pack(
        "!BBHHHBBHII",
        0x45,       # version + IHL
        0,          # DSCP/ECN
        total_len,  # total length
        0,          # identification
        0,          # flags + fragment offset
        64,         # TTL
        6,          # protocol = TCP
        0,          # checksum (ignored)
        src,
        dst,
    )

    # TCP header (20 bytes)
    tcp = struct.pack(
        "!HHLLBBHHH",
        src_port,
        dst_port,
        0,      # seq
        0,      # ack
        0x50,   # data offset (5 * 4 = 20 bytes)
        0x02,   # SYN
        0,      # window
        0,      # checksum
        0,      # urgent pointer
    )

    return vxlan + eth + ip + tcp


def test_parse_vxlan_packet_tcp():
    data = _build_vxlan_tcp_packet()
    rec = _parse_vxlan_packet(data)
    assert rec is not None
    assert rec["type"] == "flow"
    assert rec["src"] == "192.168.1.1"
    assert rec["dst"] == "192.168.1.2"
    assert rec["proto"] == "TCP"
    assert rec["src_port"] == 12345
    assert rec["dst_port"] == 80
    assert rec["packets"] == 1
    assert rec["mirror"] is True


def test_parse_vxlan_packet_udp():
    data = bytearray(_build_vxlan_tcp_packet())
    # Patch IP protocol to UDP (17) and TCP ports become UDP ports.
    ip_offset = 8 + 14
    data[ip_offset + 9] = 17
    rec = _parse_vxlan_packet(bytes(data))
    assert rec is not None
    assert rec["proto"] == "UDP"


def test_parse_vxlan_packet_too_short():
    assert _parse_vxlan_packet(b"\x00" * 10) is None


def test_vxlan_handler_ingest():
    adapter = MagicMock()
    adapter.stats = TrafficMirrorStats()
    adapter.normalizer.normalize.return_value = MagicMock()
    adapter.tick_s = 1.0

    handler = VXLANHandler(adapter)
    handler.datagram_received(_build_vxlan_tcp_packet(), ("10.0.0.1", 4789))

    assert adapter.stats.packets == 1
    assert adapter.stats.flows == 1
    assert adapter.stats.bytes > 0
    assert adapter.normalizer.normalize.called
    assert adapter.sync.ingest.called


@pytest.mark.skipif(not _has_dpkt(), reason="dpkt not installed")
def test_parse_with_dpkt():
    data = _build_vxlan_tcp_packet()
    rec = _parse_with_dpkt(data)
    assert rec is not None
    assert rec["src"] == "192.168.1.1"
    assert rec["dst"] == "192.168.1.2"
    assert rec["proto"] == "TCP"
    assert rec["src_port"] == 12345
    assert rec["dst_port"] == 80


def test_adapter_start_stop():
    from nettwin.config import Settings

    settings = Settings()
    settings.aws.traffic_mirror_enabled = True
    settings.aws.traffic_mirror_port = 0  # ephemeral

    norm = MagicMock()
    sync = MagicMock()
    adapter = TrafficMirrorAdapter(settings, norm, sync)

    async def _run():
        await adapter.start()
        assert adapter._running is True
        assert adapter._transport is not None
        await adapter.stop()
        assert adapter._running is False

    asyncio.run(_run())
