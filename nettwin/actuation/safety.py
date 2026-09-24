"""AWS-specific safety constraints for closed-loop response."""
from __future__ import annotations

from typing import Any

from nettwin.config import ActuationSettings


PROTECTED_KINDS = {"core_router", "internet_gateway", "firewall",
                   "distribution_switch"}


class ActuationSafety:
    """Validate that a proposed response action is safe to execute in AWS."""

    def __init__(self, settings: ActuationSettings,
                 entity_to_instance: dict[str, str],
                 entity_to_kind: dict[str, str]) -> None:
        self.settings = settings
        self.entity_to_instance = entity_to_instance
        self.entity_to_kind = entity_to_kind

    def check(self, kind: str, params: dict[str, Any]) -> str | None:
        if not self.settings.enabled:
            return "actuation is disabled"
        if kind not in self.settings.allowed_actions:
            return f"action {kind} not in allowed_actions"
        if kind == "isolate":
            return self._check_isolate(params)
        if kind == "block_flow":
            return self._check_block_flow(params)
        if kind == "reroute":
            return "reroute is manual-only in AWS mode"
        if kind == "rate_limit":
            return self._check_rate_limit(params)
        return None

    def _entity_kind(self, entity: str) -> str | None:
        return self.entity_to_kind.get(entity)

    def _check_isolate(self, params: dict[str, Any]) -> str | None:
        node = str(params.get("node", ""))
        if not node:
            return "isolate requires node"
        if node not in self.entity_to_instance:
            return f"no AWS instance mapped for entity {node}"
        kind = self._entity_kind(node)
        if kind in PROTECTED_KINDS:
            return f"refused: cannot isolate protected {kind}"
        if node.lower() in ("nettwin", "engine", "core1", "fw", "igw"):
            return "refused: cannot isolate NetTwin engine or core infrastructure"
        return None

    def _check_block_flow(self, params: dict[str, Any]) -> str | None:
        src = str(params.get("src", ""))
        dst = str(params.get("dst", ""))
        if not src and not dst:
            return "block_flow requires src or dst"
        for endpoint in (src, dst):
            if not endpoint:
                continue
            if endpoint.lower() in ("core1", "fw", "igw", "internet_gateway"):
                return f"refused: cannot block protected entity {endpoint}"
        mgmt = self.settings.management_cidr
        if mgmt and (src == mgmt or dst == mgmt):
            return "refused: cannot block management CIDR"
        return None

    def _check_rate_limit(self, params: dict[str, Any]) -> str | None:
        src = str(params.get("src", ""))
        if src.lower() in ("core1", "fw", "igw", "internet_gateway"):
            return f"refused: cannot throttle protected entity {src}"
        return None
