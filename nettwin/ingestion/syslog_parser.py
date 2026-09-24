"""RFC3164/RFC5424 syslog parser with embedded key=value telemetry extraction.

The parser is intentionally forgiving: enterprise gear sends many dialects.
We extract the host and a flat set of key=value pairs from the message body,
then map those pairs to NetTwin gauge/interface/flow records.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# RFC3164: <PRI>Mmm dd HH:MM:SS host message
_RFC3164_RE = re.compile(
    r"^<\d{1,3}>(?P<ts>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+(?P<msg>.+)$",
    re.DOTALL,
)

# RFC5424: <PRI>1 ISOTIMESTAMP host app procid msgid [structured-data] msg
_RFC5424_RE = re.compile(
    r"^<\d{1,3}>1\s+(?P<ts>\S+)\s+(?P<host>\S+)\s+\S+\s+\S+\s+\S+\s+"
    r"(?P<sd>-|\[.*?\])\s+(?P<msg>.*)$",
    re.DOTALL,
)

# Flat key=value / key: value pairs. Supports quoted values.
_KV_RE = re.compile(
    r"(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)(?:=|:)\s*"
    r"(?P<val>\"[^\"]*\"|\S+)",
)

_GAUGE_KEYMAP = {
    "cpu": "cpu_pct",
    "cpu_pct": "cpu_pct",
    "cpu_usage": "cpu_pct",
    "mem": "mem_pct",
    "mem_pct": "mem_pct",
    "memory": "mem_pct",
    "latency": "latency_ms",
    "latency_ms": "latency_ms",
    "loss": "packet_loss_pct",
    "packet_loss": "packet_loss_pct",
    "packet_loss_pct": "packet_loss_pct",
    "jitter": "jitter_ms",
    "jitter_ms": "jitter_ms",
}


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _extract_kv(msg: str) -> dict[str, str]:
    return {
        m.group("key").lower(): _strip_quotes(m.group("val"))
        for m in _KV_RE.finditer(msg)
    }


def _coerce_number(value: str) -> float | int | str:
    value = value.strip()
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        # Handle "31.2%" etc.
        if value.endswith("%"):
            try:
                return float(value[:-1])
            except ValueError:
                pass
        return value


def _to_record(kv: dict[str, str], host: str) -> dict[str, Any] | None:
    """Turn extracted key/value pairs into a NetTwin telemetry record."""
    # Explicit type hint inside the message wins.
    rtype = kv.get("type", "gauge").lower()
    if rtype in ("gauge", "snmp"):
        metrics: dict[str, float] = {}
        for k, v in kv.items():
            if k in _GAUGE_KEYMAP:
                metrics[_GAUGE_KEYMAP[k]] = float(_coerce_number(v))
        if not metrics:
            # No recognized gauge keys; treat as generic syslog event with a score.
            return {"type": "syslog_event", "host": host, "message": kv.get("_raw", "")}
        return {"type": "gauge", "host": host, "metrics": metrics}
    if rtype == "interface":
        return {
            "type": "interface",
            "host": host,
            "in_bps": int(float(_coerce_number(kv.get("in_bps", "0")))),
            "out_bps": int(float(_coerce_number(kv.get("out_bps", "0")))),
            "in_pps": int(float(_coerce_number(kv.get("in_pps", "0")))),
            "out_pps": int(float(_coerce_number(kv.get("out_pps", "0")))),
        }
    if rtype in ("flow", "netflow"):
        return {
            "type": "flow",
            "src": kv.get("src", ""),
            "dst": kv.get("dst", ""),
            "proto": kv.get("proto", "TCP").upper(),
            "bytes": int(float(_coerce_number(kv.get("bytes", "0")))),
            "packets": int(float(_coerce_number(kv.get("packets", "0")))),
        }
    return None


def parse_syslog(line: str) -> dict[str, Any] | None:
    """Parse a single syslog line into a NetTwin telemetry record or ``None``."""
    line = line.strip()
    if not line:
        return None

    host: str | None = None
    msg = line
    m = _RFC5424_RE.match(line)
    if not m:
        m = _RFC3164_RE.match(line)
    if m:
        host = m.group("host")
        msg = m.group("msg")

    kv = _extract_kv(msg)
    if not kv:
        return None
    kv["_raw"] = msg

    # If no host was parsed from the syslog header, allow an explicit host= pair.
    if host is None:
        host = kv.get("host", "")
    if not host:
        return None
    return _to_record(kv, host)
