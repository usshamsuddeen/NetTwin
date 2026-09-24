"""Dataclasses representing an AWS-side change produced by a response action."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChangeType(str, Enum):
    CREATE_SG = "create_sg"
    MODIFY_INSTANCE_SG = "modify_instance_sg"
    CREATE_NACL_ENTRY = "create_nacl_entry"
    DELETE_NACL_ENTRY = "delete_nacl_entry"
    SSM_SEND_COMMAND = "ssm_send_command"
    CREATE_WAF_RATE_RULE = "create_waf_rate_rule"


class ResourceType(str, Enum):
    SECURITY_GROUP = "security_group"
    INSTANCE = "instance"
    NETWORK_ACL = "network_acl"
    SSM_COMMAND = "ssm_command"
    WEB_ACL = "web_acl"


class ActionState(str, Enum):
    """Formal lifecycle for a closed-loop AWS response action.

    PENDING → TRANSITIONING → ENFORCED
                       └→ FAILED → ROLLED_BACK
    """
    PENDING = "pending"
    TRANSITIONING = "transitioning"
    ENFORCED = "enforced"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class PriorState:
    """Enough information to undo a change."""
    resource_id: str
    resource_type: ResourceType
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AWSTask:
    """One atomic AWS API call to execute."""
    change_type: ChangeType
    resource_type: ResourceType
    resource_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    prior_state: PriorState | None = None

    def describe(self) -> str:
        return f"{self.change_type.value} on {self.resource_type.value} {self.resource_id or ''}"
