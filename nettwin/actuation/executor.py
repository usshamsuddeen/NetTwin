"""Execute AWS actuation tasks with dry-run support, rollback and audit logging."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import boto3
from botocore.exceptions import ClientError

from nettwin.actuation.models import AWSTask, ActionState, ChangeType, ResourceType
from nettwin.actuation.safety import ActuationSafety
from nettwin.actuation.translator import ResponseToAWS
from nettwin.config import Settings
from nettwin.storage import Storage

log = logging.getLogger("nettwin.actuation")


@dataclass
class ActuationResult:
    action_id: str
    success: bool
    changes: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    rolled_back: bool = False
    state: ActionState = ActionState.PENDING
    state_entered_at: dict[str, float] = field(default_factory=dict)

    def enter_state(self, state: ActionState) -> None:
        self.state = state
        self.state_entered_at[state.value] = time.time()


class AWSActuator:
    """Run response actions against real AWS resources.

    Every execution is recorded via ``Storage.save_response_action`` for audit.
    """

    def __init__(self, settings: Settings, storage: Storage | None = None,
                 translator: ResponseToAWS | None = None,
                 safety: ActuationSafety | None = None,
                 boto3_session: boto3.Session | None = None) -> None:
        self.settings = settings
        self.storage = storage
        self.translator = translator
        self.safety = safety
        self.session = boto3_session or boto3.Session(region_name=settings.aws.region)
        self._ec2 = self.session.client("ec2")
        self._ssm = self.session.client("ssm")
        self._waf = self.session.client("wafv2")
        self._vpc_id: str | None = None
        self._sg_name_to_id: dict[str, str] = {}

    def _resolve_sg_id(self, name_or_id: str) -> str:
        return self._sg_name_to_id.get(name_or_id, name_or_id)

    def set_translator(self, translator: ResponseToAWS) -> None:
        self.translator = translator

    def set_safety(self, safety: ActuationSafety) -> None:
        self.safety = safety

    async def execute(self, action_id: str, kind: str, params: dict[str, Any],
                      dry_run: bool | None = None) -> ActuationResult:
        if self.translator is None or self.safety is None:
            return ActuationResult(action_id, False, error="actuator not configured")
        if dry_run is None:
            dry_run = self.settings.actuation.dry_run

        result = ActuationResult(action_id, True)
        result.enter_state(ActionState.PENDING)

        refusal = self.safety.check(kind, params)
        if refusal:
            result.enter_state(ActionState.FAILED)
            result.success = False
            result.error = f"safety: {refusal}"
            return result

        try:
            tasks = self.translator.translate(kind, params)
        except ValueError as exc:
            result.enter_state(ActionState.FAILED)
            result.success = False
            result.error = str(exc)
            return result

        result.enter_state(ActionState.TRANSITIONING)
        for task in tasks:
            change_record = {"task": task.describe(), "dry_run": dry_run}
            try:
                if not dry_run:
                    self._apply(task)
                change_record["applied"] = True
            except ClientError as exc:
                change_record["applied"] = False
                change_record["error"] = str(exc)
                result.success = False
                result.error = str(exc)
                # Roll back already-applied tasks.
                await self._rollback(result, tasks[:tasks.index(task)])
                break
            result.changes.append(change_record)

        if result.success:
            # Bounded convergence: verify AWS eventual consistency before ENFORCED.
            verified = await self._verify_convergence(tasks, dry_run=dry_run)
            if verified:
                result.enter_state(ActionState.ENFORCED)
            else:
                result.success = False
                result.error = "convergence verification timed out"
                await self._rollback(result, tasks)
                if result.state != ActionState.ROLLED_BACK:
                    result.enter_state(ActionState.FAILED)
        elif result.rolled_back:
            result.enter_state(ActionState.ROLLED_BACK)
        else:
            result.enter_state(ActionState.FAILED)

        if self.storage is not None:
            await self.storage.save_response_action({
                "id": action_id,
                "action_type": kind,
                "entity_id": params.get("node") or params.get("src") or params.get("dst"),
                "status": result.state.value,
                "proposed_at": 0,  # populated by caller
                "applied_at": time.time() if result.success else None,
                "sandbox_delta": 0.0,
                "observed_delta": 0.0,
                "metadata": {
                    "params": params,
                    "dry_run": dry_run,
                    "changes": result.changes,
                    "error": result.error,
                    "rolled_back": result.rolled_back,
                    "state_timestamps": result.state_entered_at,
                },
            })
        return result

    async def _verify_convergence(self, tasks: list[AWSTask],
                                   dry_run: bool = False) -> bool:
        """Poll AWS until all mutable changes are visible or timeout.

        Paper 3 (SafeBandit): bounded convergence model for EC2 API eventual
        consistency.  Dry-run and SSM commands are treated as converged
        immediately.
        """
        if dry_run or not tasks:
            return True
        max_wait_s = 30.0
        interval_s = 2.0
        deadline = time.time() + max_wait_s
        pending = [t for t in tasks
                   if t.change_type in (ChangeType.MODIFY_INSTANCE_SG,
                                        ChangeType.CREATE_NACL_ENTRY)]
        while pending and time.time() < deadline:
            await asyncio.sleep(interval_s)
            still_pending = []
            for task in pending:
                try:
                    if task.change_type == ChangeType.MODIFY_INSTANCE_SG:
                        resp = self._ec2.describe_instance_attribute(
                            InstanceId=task.resource_id, Attribute="groupSet")
                        applied = {g["GroupId"] for g in resp.get("Groups", [])}
                        expected = {self._resolve_sg_id(g)
                                    for g in task.params.get("Groups", [])}
                        if not expected or expected.issubset(applied):
                            continue
                    elif task.change_type == ChangeType.CREATE_NACL_ENTRY:
                        resp = self._ec2.describe_network_acls(
                            NetworkAclIds=[task.resource_id])
                        rules = resp["NetworkAcls"][0].get("Entries", [])
                        target = task.params["RuleNumber"]
                        if any(r.get("RuleNumber") == target for r in rules):
                            continue
                except ClientError as exc:
                    log.debug("convergence poll error: %s", exc)
                still_pending.append(task)
            pending = still_pending
        return not pending

    def _apply(self, task: AWSTask) -> None:
        log.info("applying %s", task.describe())
        if task.change_type == ChangeType.CREATE_SG:
            params = dict(task.params)
            if self._vpc_id:
                params["VpcId"] = self._vpc_id
            resp = self._ec2.create_security_group(**params)
            self._vpc_id = resp.get("VpcId")
            self._sg_name_to_id[task.resource_id] = resp["GroupId"]
            return
        if task.change_type == ChangeType.MODIFY_INSTANCE_SG:
            groups = [self._resolve_sg_id(g) for g in task.params["Groups"]]
            self._ec2.modify_instance_attribute(
                InstanceId=task.resource_id,
                Groups=groups)
            return
        if task.change_type == ChangeType.CREATE_NACL_ENTRY:
            self._ec2.create_network_acl_entry(**task.params)
            return
        if task.change_type == ChangeType.SSM_SEND_COMMAND:
            self._ssm.send_command(**task.params)
            return
        if task.change_type == ChangeType.CREATE_WAF_RATE_RULE:
            self._waf.update_web_acl(**task.params)
            return
        raise ValueError(f"unknown change type: {task.change_type}")

    async def _rollback(self, result: ActuationResult, tasks: list[AWSTask]) -> None:
        if not tasks:
            return
        log.warning("rolling back %d applied tasks", len(tasks))
        for task in reversed(tasks):
            if task.prior_state is None:
                continue
            try:
                self._revert(task)
            except ClientError as exc:
                log.error("rollback failed for %s: %s", task.describe(), exc)
        result.rolled_back = True
        result.enter_state(ActionState.ROLLED_BACK)

    def _revert(self, task: AWSTask) -> None:
        if task.prior_state is None:
            return
        ps = task.prior_state
        log.info("reverting %s", task.describe())
        action = ps.data.get("action")
        if action == "restore_original_sgs":
            self._ec2.modify_instance_attribute(
                InstanceId=ps.resource_id,
                Groups=ps.data.get("original_groups", []))
        elif action == "delete_nacl_entry":
            self._ec2.delete_network_acl_entry(
                NetworkAclId=ps.data["NetworkAclId"],
                RuleNumber=ps.data["RuleNumber"],
                Egress=False)
        elif action == "ssm_undo_tc":
            self._ssm.send_command(**ps.data)
        elif action == "delete_waf_rate_rule":
            # WAFv2 rules are managed via WebACL updates; a full revert would
            # fetch the current rule set, remove our rule, and re-update.
            log.warning("WAF rate-rule revert not yet automated for %s", ps.resource_id)

    async def revert_action(self, action_id: str, tasks: list[AWSTask]) -> ActuationResult:
        result = ActuationResult(action_id, True)
        for task in reversed(tasks):
            try:
                self._revert(task)
                result.changes.append({"task": task.describe(), "reverted": True})
            except ClientError as exc:
                result.success = False
                result.error = str(exc)
                result.changes.append({"task": task.describe(), "reverted": False,
                                       "error": str(exc)})
        return result
