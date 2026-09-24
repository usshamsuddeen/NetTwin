"""Translate NetTwin response actions into AWS API task lists."""
from __future__ import annotations

import logging
from typing import Any

from nettwin.actuation.models import AWSTask, ChangeType, PriorState, ResourceType
from nettwin.config import ActuationSettings

log = logging.getLogger("nettwin.actuation")


class ResponseToAWS:
    """Convert a response-agent action into concrete AWS changes.

    Parameters
    ----------
    settings : ActuationSettings
    entity_to_instance : dict[str, str]
        twin entity id -> EC2 instance id
    entity_to_ip : dict[str, str]
        twin entity id -> private IP address
    entity_to_subnet : dict[str, str]
        twin entity id -> subnet id
    entity_to_nacl : dict[str, str]
        twin entity id -> network ACL id for its subnet
    """

    def __init__(self, settings: ActuationSettings,
                 entity_to_instance: dict[str, str],
                 entity_to_ip: dict[str, str],
                 entity_to_subnet: dict[str, str],
                 entity_to_nacl: dict[str, str]) -> None:
        self.settings = settings
        self.entity_to_instance = entity_to_instance
        self.entity_to_ip = entity_to_ip
        self.entity_to_subnet = entity_to_subnet
        self.entity_to_nacl = entity_to_nacl
        self._rule_counter = 100

    def translate(self, kind: str, params: dict[str, Any]) -> list[AWSTask]:
        if kind == "isolate":
            return self._isolate_tasks(params)
        if kind == "block_flow":
            return self._block_flow_tasks(params)
        if kind == "rate_limit":
            return self._rate_limit_tasks(params)
        raise ValueError(f"unsupported AWS action: {kind}")

    def _instance_id(self, entity: str) -> str:
        if entity not in self.entity_to_instance:
            raise ValueError(f"no AWS instance mapped for {entity}")
        return self.entity_to_instance[entity]

    def _ip(self, entity: str) -> str | None:
        return self.entity_to_ip.get(entity)

    def _nacl_for(self, entity: str) -> str:
        return self.entity_to_nacl.get(entity, "")

    def _isolate_tasks(self, params: dict[str, Any]) -> list[AWSTask]:
        node = str(params["node"])
        instance_id = self._instance_id(node)
        sg_name = self.settings.quarantine_sg_name
        sg_desc = f"NetTwin quarantine SG for {node}"
        tasks: list[AWSTask] = [
            AWSTask(
                ChangeType.CREATE_SG, ResourceType.SECURITY_GROUP,
                resource_id=sg_name,
                params={"GroupName": sg_name, "Description": sg_desc,
                        "VpcId": None, "TagSpecifications": [{
                            "ResourceType": "security-group",
                            "Tags": [{"Key": "Name", "Value": sg_name},
                                     {"Key": "ManagedBy", "Value": "NetTwin"}]}]}),
            AWSTask(
                ChangeType.MODIFY_INSTANCE_SG, ResourceType.INSTANCE,
                resource_id=instance_id,
                params={"Groups": [sg_name]},
                prior_state=PriorState(
                    resource_id=instance_id,
                    resource_type=ResourceType.INSTANCE,
                    data={"action": "restore_original_sgs", "original_groups": []})),
        ]
        return tasks

    def _block_flow_tasks(self, params: dict[str, Any]) -> list[AWSTask]:
        src = str(params.get("src", ""))
        dst = str(params.get("dst", ""))
        proto = params.get("proto") or "-1"
        proto_num = {"TCP": 6, "UDP": 17, "ICMP": 1}.get(str(proto).upper(), -1)

        # Determine which direction to block: prefer blocking inbound to dst.
        if dst:
            cidr = self._ip(src) + "/32" if src and src in self.entity_to_ip else "0.0.0.0/0"
            nacl_id = self._nacl_for(dst)
            target_subnet = self.entity_to_subnet.get(dst, "")
        elif src:
            cidr = "0.0.0.0/0"
            nacl_id = self._nacl_for(src)
            target_subnet = self.entity_to_subnet.get(src, "")
        else:
            raise ValueError("block_flow requires src or dst")
        if not nacl_id:
            raise ValueError("no network ACL mapped for target entity")

        self._rule_counter += 1
        rule_num = self._rule_counter
        tasks = [
            AWSTask(
                ChangeType.CREATE_NACL_ENTRY, ResourceType.NETWORK_ACL,
                resource_id=nacl_id,
                params={
                    "NetworkAclId": nacl_id,
                    "RuleNumber": rule_num,
                    "Protocol": str(proto_num),
                    "RuleAction": "deny",
                    "CidrBlock": cidr,
                    "Egress": False,
                },
                prior_state=PriorState(
                    resource_id=nacl_id,
                    resource_type=ResourceType.NETWORK_ACL,
                    data={"action": "delete_nacl_entry",
                          "NetworkAclId": nacl_id,
                          "RuleNumber": rule_num})),
        ]
        return tasks

    def _rate_limit_tasks(self, params: dict[str, Any]) -> list[AWSTask]:
        src = str(params.get("src", ""))
        bps = int(params.get("bps", 50_000_000))
        if self.settings.rate_limit_backend == "waf":
            return self._waf_rate_limit_tasks(src, bps)
        return self._tc_rate_limit_tasks(src, bps)

    def _tc_rate_limit_tasks(self, src: str, bps: int) -> list[AWSTask]:
        instance_id = self._instance_id(src) if src in self.entity_to_instance else ""
        if not instance_id:
            raise ValueError("rate_limit requires a mapped source entity")
        cmd = (
            f"tc qdisc add dev eth0 root tbf rate {bps}bit burst 32kbit latency 50ms || "
            f"tc qdisc change dev eth0 root tbf rate {bps}bit burst 32kbit latency 50ms"
        )
        return [
            AWSTask(
                ChangeType.SSM_SEND_COMMAND, ResourceType.SSM_COMMAND,
                resource_id=instance_id,
                params={"InstanceIds": [instance_id],
                        "DocumentName": "AWS-RunShellScript",
                        "Parameters": {"commands": [cmd]}},
                prior_state=PriorState(
                    resource_id=instance_id,
                    resource_type=ResourceType.SSM_COMMAND,
                    data={"action": "ssm_undo_tc",
                          "InstanceIds": [instance_id],
                          "DocumentName": "AWS-RunShellScript",
                          "Parameters": {"commands": ["tc qdisc del dev eth0 root"]}})),
        ]

    def _waf_rate_limit_tasks(self, src: str, bps: int) -> list[AWSTask]:
        """Use AWS WAFv2 rate-based rule to throttle a source IP."""
        web_acl_id = self.settings.web_acl_id
        if not web_acl_id:
            raise ValueError("rate_limit backend 'waf' requires settings.actuation.web_acl_id")
        cidr = self._ip(src) + "/32" if src and src in self.entity_to_ip else None
        if not cidr:
            raise ValueError("rate_limit waf backend requires a mapped source IP")
        # Convert bps to requests/5min using a nominal 10 kB request size.
        rps = max(1, int(bps / (10 * 8192)))
        rule_name = f"nettwin-rate-limit-{src}"
        return [
            AWSTask(
                ChangeType.CREATE_WAF_RATE_RULE, ResourceType.WEB_ACL,
                resource_id=web_acl_id,
                params={
                    "Name": rule_name,
                    "Scope": "REGIONAL",
                    "Id": web_acl_id,
                    "Rules": [{
                        "Name": rule_name,
                        "Priority": 1,
                        "Statement": {
                            "RateBasedStatement": {
                                "Limit": rps,
                                "AggregateKeyType": "IP",
                                "ScopeDownStatement": {
                                    "IPSetReferenceStatement": {
                                        "ARN": "placeholder-ipset-arn"
                                    }
                                } if cidr else None,
                            }
                        },
                        "Action": {"Block": {}},
                        "VisibilityConfig": {
                            "SampledRequestsEnabled": True,
                            "CloudWatchMetricsEnabled": True,
                            "MetricName": rule_name,
                        },
                    }],
                    "VisibilityConfig": {
                        "SampledRequestsEnabled": True,
                        "CloudWatchMetricsEnabled": True,
                        "MetricName": "nettwin-waf",
                    },
                },
                prior_state=PriorState(
                    resource_id=web_acl_id,
                    resource_type=ResourceType.WEB_ACL,
                    data={"action": "delete_waf_rate_rule", "Name": rule_name})),
        ]
