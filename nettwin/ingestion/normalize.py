"""Normalize external telemetry into the twin's entity-metric schema.

Accepted JSON record shapes (one per UDP datagram line or HTTP push item):

  gauge / snmp poll:
    {"type": "gauge", "host": "web1"|"10.0.3.11", "ts": 1700000000.0,
     "metrics": {"cpu_pct": 31.2, "mem_pct": 44.0, "latency_ms": 1.2,
                 "packet_loss_pct": 0.01}}
  interface counters (SNMP-like), optional packet rates:
    {"type": "interface", "host": "web1", "in_bps": 12000000, "out_bps": 4000000,
     "in_pps": 1500, "out_pps": 500}
  flow / netflow record:
    {"type": "flow"|"netflow", "src": "10.0.1.5", "dst": "10.0.3.11",
     "proto": "TCP", "bytes": 51200, "packets": 40}
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

GAUGE_KEYS = ("cpu_pct", "mem_pct", "latency_ms", "packet_loss_pct", "jitter_ms")


@dataclass
class NormalizedBatch:
    """Per-entity real-world observations from one ingest call."""
    ts: float = field(default_factory=time.time)
    gauges: dict[str, dict[str, float]] = field(default_factory=dict)
    tx_bytes: dict[str, int] = field(default_factory=dict)
    rx_bytes: dict[str, int] = field(default_factory=dict)
    tx_pkts: dict[str, int] = field(default_factory=dict)
    rx_pkts: dict[str, int] = field(default_factory=dict)
    fanout: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def entities(self) -> set[str]:
        out = set(self.gauges) | set(self.tx_bytes) | set(self.rx_bytes)
        return out


class Normalizer:
    def __init__(self, resolve) -> None:
        self.resolve = resolve  # host/ip -> twin entity id or None

    def normalize(self, records: list[dict[str, Any]],
                  ts: float | None = None) -> NormalizedBatch:
        batch = NormalizedBatch(ts=ts or time.time())
        for rec in records:
            try:
                self._one(rec, batch)
            except Exception as exc:
                batch.errors.append(str(exc))
        return batch

    def _one(self, rec: dict[str, Any], batch: NormalizedBatch) -> None:
        rtype = str(rec.get("type", "flow")).lower()
        if rtype in ("gauge", "snmp"):
            host = self.resolve(rec.get("host", ""))
            if not host:
                return
            metrics = batch.gauges.setdefault(host, {})
            for key, val in (rec.get("metrics") or {}).items():
                if key in GAUGE_KEYS:
                    metrics[key] = float(val)
        elif rtype == "interface":
            host = self.resolve(rec.get("host", ""))
            if not host:
                return
            batch.rx_bytes[host] = batch.rx_bytes.get(host, 0) + int(float(rec.get("in_bps", 0)) / 8)
            batch.tx_bytes[host] = batch.tx_bytes.get(host, 0) + int(float(rec.get("out_bps", 0)) / 8)
            if "in_pps" in rec or "out_pps" in rec:
                batch.rx_pkts[host] = batch.rx_pkts.get(host, 0) + int(float(rec.get("in_pps", 0)))
                batch.tx_pkts[host] = batch.tx_pkts.get(host, 0) + int(float(rec.get("out_pps", 0)))
        elif rtype == "syslog_event":
            # Generic syslog text events carry no numeric telemetry; ignore here.
            return
        elif rtype in ("flow", "netflow"):
            src = self.resolve(rec.get("src", ""))
            dst = self.resolve(rec.get("dst", ""))
            nbytes = int(rec.get("bytes", 0))
            npkts = int(rec.get("packets", 0)) or max(1, nbytes // 900)
            if src:
                batch.tx_bytes[src] = batch.tx_bytes.get(src, 0) + nbytes
                batch.tx_pkts[src] = batch.tx_pkts.get(src, 0) + npkts
                if dst:
                    batch.fanout.setdefault(src, 0)
            if dst:
                batch.rx_bytes[dst] = batch.rx_bytes.get(dst, 0) + nbytes
                batch.rx_pkts[dst] = batch.rx_pkts.get(dst, 0) + npkts
        else:
            batch.errors.append(f"unknown record type: {rtype}")


def parse_payload(data: bytes | str) -> list[dict[str, Any]]:
    """Parse a datagram/HTTP body: JSON object, JSON list, JSON lines, or syslog lines."""
    import json
    from nettwin.ingestion.syslog_parser import parse_syslog
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        obj = json.loads(text)
        return [r for r in obj if isinstance(r, dict)]
    if text.startswith("{"):
        try:
            return [json.loads(text)]
        except json.JSONDecodeError:
            pass  # fall through to JSON-lines / syslog
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            records.append(json.loads(line))
            continue
        rec = parse_syslog(line)
        if rec:
            records.append(rec)
    return records
