"""SNMPv2c polling adapter for interface counters.

Requires the optional ``snmp`` extra: ``pip install nettwin[snmp]``
(which pulls ``pysnmp``). When ``pysnmp`` is unavailable the adapter logs a
warning and refuses to start.

Configured via ``config.json``:

```json
"snmp": {
    "enabled": true,
    "community": "public",
    "targets": [
        {"host": "10.0.1.11", "entity": "web1"},
        {"host": "10.0.2.11", "entity": "app1"}
    ],
    "poll_interval_s": 30
}
```

The adapter polls ``IF-MIB::ifHCInOctets``, ``IF-MIB::ifHCOutOctets``,
``IF-MIB::ifHCInUcastPkts`` and ``IF-MIB::ifHCOutUcastPkts`` for every
interface on the target and emits ``interface`` records into the normalizer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from nettwin.ingestion.adapters.base import BaseAdapter, NormalizedBatch
from nettwin.ingestion.normalize import Normalizer

log = logging.getLogger("nettwin.adapters.snmp")

# Try to import pysnmp; gracefully degrade if not installed.
try:
    from pysnmp.hlapi.v3arch.asyncio import (  # type: ignore[import]
        CommunityData,
        ContextData,
        ObjectType,
        ObjectIdentity,
        SnmpEngine,
        UdpTransportTarget,
        get_cmd,
    )
    _HAS_PYSNMP = True
except Exception:
    _HAS_PYSNMP = False


@dataclass
class SNMPTarget:
    host: str
    entity: str
    port: int = 161


@dataclass
class SNMPSettings:
    enabled: bool = False
    community: str = "public"
    targets: list[dict[str, Any]] = field(default_factory=list)
    poll_interval_s: float = 30.0


_HC_OIDS = [
    ("1.3.6.1.2.1.31.1.1.1.6", "ifHCInOctets"),   # bytes in
    ("1.3.6.1.2.1.31.1.1.1.10", "ifHCOutOctets"),  # bytes out
    ("1.3.6.1.2.1.31.1.1.1.7", "ifHCInUcastPkts"),  # pkts in
    ("1.3.6.1.2.1.31.1.1.1.11", "ifHCOutUcastPkts"),  # pkts out
]


class SNMPAdapter(BaseAdapter):
    """Poll SNMP interface counters and emit NormalizedBatch records."""

    def __init__(self, settings: SNMPSettings, normalizer: Normalizer) -> None:
        super().__init__("snmp", poll_interval_s=settings.poll_interval_s)
        self.settings = settings
        self.normalizer = normalizer
        self._targets = [SNMPTarget(**t) for t in settings.targets]
        self._engine = SnmpEngine() if _HAS_PYSNMP else None

    async def connect(self) -> None:
        if not _HAS_PYSNMP:
            raise RuntimeError(
                "SNMP adapter requires pysnmp. Install with: pip install nettwin[snmp]")
        log.info("snmp adapter monitoring %d targets", len(self._targets))

    async def disconnect(self) -> None:
        pass

    async def poll(self) -> NormalizedBatch | None:
        if not _HAS_PYSNMP or not self._engine:
            return None
        records: list[dict[str, Any]] = []
        for target in self._targets:
            try:
                records.extend(await self._poll_target(target))
            except Exception as exc:
                log.warning("snmp poll failed for %s: %s", target.host, exc)
                self.stats.record_error()
        if not records:
            return None
        self.stats.record_batch()
        return self.normalizer.normalize(records)

    async def _poll_target(self, target: SNMPTarget) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        in_bytes = out_bytes = in_pkts = out_pkts = 0
        for oid, _ in _HC_OIDS:
            value = await self._get(target, oid)
            if value is None:
                continue
            if "InOctets" in oid or oid.endswith(".6"):
                in_bytes += int(value)
            elif "OutOctets" in oid or oid.endswith(".10"):
                out_bytes += int(value)
            elif "InUcastPkts" in oid or oid.endswith(".7"):
                in_pkts += int(value)
            elif "OutUcastPkts" in oid or oid.endswith(".11"):
                out_pkts += int(value)
        if in_bytes or out_bytes:
            records.append({
                "type": "interface",
                "host": target.entity,
                "in_bps": in_bytes * 8 // max(1, int(self.poll_interval_s)),
                "out_bps": out_bytes * 8 // max(1, int(self.poll_interval_s)),
                "in_pps": in_pkts // max(1, int(self.poll_interval_s)),
                "out_pps": out_pkts // max(1, int(self.poll_interval_s)),
            })
        return records

    async def _get(self, target: SNMPTarget, oid: str) -> int | None:
        assert self._engine is not None
        iterator = get_cmd(
            self._engine,
            CommunityData(self.settings.community),
            await UdpTransportTarget.create((target.host, target.port)),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        error_indication, error_status, _, var_binds = await iterator
        if error_indication or error_status:
            return None
        for _, val in var_binds:
            try:
                return int(val)
            except (TypeError, ValueError):
                return None
        return None

    def status(self) -> dict[str, Any]:
        return {
            **self.stats.to_dict(),
            "targets": [{"host": t.host, "entity": t.entity} for t in self._targets],
            "pysnmp_available": _HAS_PYSNMP,
        }
