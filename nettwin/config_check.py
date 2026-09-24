"""Startup configuration sanity checks (warnings only, never fatal)."""
from __future__ import annotations

import ipaddress
import json
import logging
from pathlib import Path
from typing import Any

from .config import Settings

log = logging.getLogger("nettwin.config_check")


def _raw_config(path: str | Path = "config.json") -> dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        return {}
    try:
        with cfg_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("could not read raw config %s: %s", cfg_path, exc)
        return {}


def check_sync_map_coverage(settings: Settings, raw: dict[str, Any]) -> list[str]:
    """Warn when sync_map entries fall outside the deployed VPC subnets.

    ``sync.vpc_cidrs`` in config.json lists the CIDRs that real telemetry can
    originate from (must match the Terraform subnets). Entries outside every
    CIDR can never receive real telemetry and will stay SIMULATED forever.
    """
    warnings: list[str] = []
    cidrs = raw.get("sync", {}).get("vpc_cidrs") or []
    networks = []
    for cidr in cidrs:
        try:
            networks.append(ipaddress.ip_network(cidr))
        except ValueError:
            warnings.append(f"sync.vpc_cidrs entry {cidr!r} is not a valid CIDR")
    if not networks or not settings.sync.sync_map:
        return warnings
    for ip, entity in sorted(settings.sync.sync_map.items()):
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            warnings.append(f"sync_map entry {ip!r} ({entity}) is not a valid IP")
            continue
        if not any(addr in net for net in networks):
            warnings.append(
                f"sync_map entry {ip} -> {entity} is outside all vpc_cidrs "
                f"({', '.join(cidrs)}); it can never receive real telemetry"
            )
    return warnings


def validate_startup(settings: Settings, config_path: str | Path = "config.json") -> None:
    """Run all startup checks and log warnings. Never raises."""
    raw = _raw_config(config_path)
    for warning in check_sync_map_coverage(settings, raw):
        log.warning("config: %s", warning)
