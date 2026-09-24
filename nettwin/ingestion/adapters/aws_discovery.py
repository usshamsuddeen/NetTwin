"""Auto-discover AWS VPC topology and generate a sync_map.

Uses ``boto3`` to enumerate EC2 instances, subnets, internet gateways,
security groups, and ENIs tagged with ``Project=nettwin``, then produces
a mapping compatible with ``config.json``'s ``sync.sync_map`` section.

The mapping is written to ``aws_sync_map.json`` on first run and can be
re-generated at any time via ``AWSDiscovery.discover()``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger("nettwin.aws.discovery")

# Maps instance Name tag → twin entity ID
# Falls back to a slug of the Name tag if not in this table
_NAME_TO_ENTITY: dict[str, str] = {
    "nettwin-web1": "web1",
    "nettwin-app1": "app1",
    "nettwin-db1": "db1",
    "nettwin-attacker": "attacker",
    "nettwin-nat": "fw1",
    "nettwin-engine": "nettwin",
}


class AWSDiscovery:
    """Discover live VPC topology and produce a sync_map dict.

    Parameters
    ----------
    region : str
        AWS region to query.
    instance_tags : dict[str, str]
        Tag filters for EC2 discovery (default ``{"Project": "nettwin"}``).
    output_path : str | Path
        Where to persist the generated ``aws_sync_map.json``.
    """

    def __init__(self, region: str = "us-east-1",
                 instance_tags: dict[str, str] | None = None,
                 output_path: str | Path = "aws_sync_map.json") -> None:
        self.region = region
        self.instance_tags = instance_tags or {"Project": "nettwin"}
        self.output_path = Path(output_path)

        session = boto3.Session(region_name=region)
        self._ec2 = session.client("ec2")

    def discover(self) -> dict[str, Any]:
        """Run full discovery and return a sync-compatible config dict.

        Returns
        -------
        dict
            Contains ``sync_map`` (private IP → entity ID), ``instances``,
            ``subnets``, ``security_groups``, and ``igw``.
        """
        instances = self._discover_instances()
        subnets = self._discover_subnets(instances)
        igw = self._discover_igw(instances)
        security_groups = self._discover_security_groups(instances)
        enis = self._discover_enis(instances)

        # Build sync_map: private IP → entity ID
        sync_map: dict[str, str] = {}
        for inst in instances:
            ip = inst.get("private_ip")
            entity = inst.get("entity_id")
            if ip and entity:
                sync_map[ip] = entity

        result = {
            "sync_map": sync_map,
            "instances": instances,
            "subnets": subnets,
            "security_groups": security_groups,
            "igw": igw,
            "enis": enis,
        }

        # Persist to disk
        self.output_path.write_text(
            json.dumps(result, indent=2), encoding="utf-8")
        log.info("wrote %d-entry sync_map to %s",
                 len(sync_map), self.output_path)

        return result

    def _discover_instances(self) -> list[dict[str, Any]]:
        """Enumerate running EC2 instances matching the project tags."""
        try:
            resp = self._ec2.describe_instances(Filters=[
                {"Name": f"tag:{k}", "Values": [v]}
                for k, v in self.instance_tags.items()
            ] + [{"Name": "instance-state-name", "Values": ["running"]}])
        except ClientError as exc:
            log.warning("describe_instances failed: %s", exc)
            return []

        instances = []
        for res in resp.get("Reservations", []):
            for inst in res.get("Instances", []):
                tags = {t["Key"]: t["Value"]
                        for t in inst.get("Tags", [])}
                name = tags.get("Name", "")
                entity_id = _NAME_TO_ENTITY.get(
                    name, name.replace("nettwin-", "").lower() or inst["InstanceId"])
                instances.append({
                    "instance_id": inst["InstanceId"],
                    "private_ip": inst.get("PrivateIpAddress"),
                    "public_ip": inst.get("PublicIpAddress"),
                    "instance_type": inst.get("InstanceType"),
                    "subnet_id": inst.get("SubnetId"),
                    "name": name,
                    "entity_id": entity_id,
                    "eni_ids": [
                        ni["NetworkInterfaceId"]
                        for ni in inst.get("NetworkInterfaces", [])
                    ],
                })
        log.info("discovered %d instances", len(instances))
        return instances

    def _discover_subnets(self, instances: list[dict]) -> list[dict[str, Any]]:
        """Map subnets used by discovered instances."""
        subnet_ids = list({i["subnet_id"] for i in instances if i.get("subnet_id")})
        if not subnet_ids:
            return []
        try:
            resp = self._ec2.describe_subnets(SubnetIds=subnet_ids)
        except ClientError as exc:
            log.warning("describe_subnets failed: %s", exc)
            return []
        return [{
            "subnet_id": s["SubnetId"],
            "cidr": s["CidrBlock"],
            "az": s["AvailabilityZone"],
            "public": s.get("MapPublicIpOnLaunch", False),
        } for s in resp.get("Subnets", [])]

    def _discover_igw(self, instances: list[dict]) -> dict[str, Any] | None:
        """Find the Internet Gateway attached to the VPC."""
        vpc_ids = set()
        for inst in instances:
            sid = inst.get("subnet_id")
            if sid:
                try:
                    sr = self._ec2.describe_subnets(SubnetIds=[sid])
                    for s in sr.get("Subnets", []):
                        vpc_ids.add(s["VpcId"])
                except ClientError:
                    pass
        for vpc_id in vpc_ids:
            try:
                resp = self._ec2.describe_internet_gateways(
                    Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}])
                igws = resp.get("InternetGateways", [])
                if igws:
                    return {"igw_id": igws[0]["InternetGatewayId"], "vpc_id": vpc_id}
            except ClientError:
                pass
        return None

    def _discover_security_groups(self, instances: list[dict]) -> list[dict[str, Any]]:
        """Get security groups referenced by discovered instances."""
        sg_ids: set[str] = set()
        for inst in instances:
            try:
                resp = self._ec2.describe_instances(
                    InstanceIds=[inst["instance_id"]])
                for res in resp.get("Reservations", []):
                    for i in res.get("Instances", []):
                        for sg in i.get("SecurityGroups", []):
                            sg_ids.add(sg["GroupId"])
            except ClientError:
                pass
        if not sg_ids:
            return []
        try:
            resp = self._ec2.describe_security_groups(GroupIds=list(sg_ids))
        except ClientError as exc:
            log.warning("describe_security_groups failed: %s", exc)
            return []
        return [{
            "group_id": sg["GroupId"],
            "name": sg["GroupName"],
            "rules_count": len(sg.get("IpPermissions", [])),
        } for sg in resp.get("SecurityGroups", [])]

    def _discover_enis(self, instances: list[dict]) -> list[dict[str, str]]:
        """Get ENI IDs for Traffic Mirroring targets."""
        enis = []
        for inst in instances:
            for eni_id in inst.get("eni_ids", []):
                enis.append({
                    "eni_id": eni_id,
                    "instance_id": inst["instance_id"],
                    "entity_id": inst["entity_id"],
                })
        return enis
