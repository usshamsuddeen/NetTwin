"""AWS closed-loop actuation unit tests (boto3 clients mocked)."""
import asyncio

import pytest

from nettwin.actuation import (
    ActuationSafety,
    AWSActuator,
    ResponseToAWS,
)
from botocore.exceptions import ClientError
from nettwin.config import ActuationSettings, Settings


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def translator() -> ResponseToAWS:
    return ResponseToAWS(
        ActuationSettings(enabled=True, dry_run=False),
        entity_to_instance={"web1": "i-123", "attacker": "i-999"},
        entity_to_ip={"web1": "10.0.1.11", "attacker": "10.0.1.99"},
        entity_to_subnet={"web1": "subnet-1"},
        entity_to_nacl={"web1": "acl-1"},
    )


@pytest.fixture
def safety() -> ActuationSafety:
    return ActuationSafety(
        ActuationSettings(enabled=True,
                          allowed_actions=["isolate", "block_flow", "rate_limit", "reroute"]),
        entity_to_instance={"web1": "i-123", "attacker": "i-999"},
        entity_to_kind={"web1": "web", "attacker": "workstation"},
    )


def test_safety_blocks_disabled():
    s = ActuationSafety(
        ActuationSettings(enabled=False),
        entity_to_instance={"web1": "i-123"},
        entity_to_kind={"web1": "web"},
    )
    assert s.check("isolate", {"node": "web1"}) is not None


def test_safety_blocks_isolate_core(safety):
    assert safety.check("isolate", {"node": "core1"}) is not None


def test_safety_allows_isolate_workstation(safety):
    assert safety.check("isolate", {"node": "web1"}) is None


def test_safety_blocks_reroute(safety):
    assert "manual-only" in (safety.check("reroute", {}) or "")


def test_translator_isolate_creates_sg_and_modifies_instance(translator):
    tasks = translator.translate("isolate", {"node": "web1"})
    assert len(tasks) == 2
    assert tasks[0].change_type.value == "create_sg"
    assert tasks[1].change_type.value == "modify_instance_sg"
    assert tasks[1].resource_id == "i-123"


def test_translator_block_flow_creates_nacl_entry(translator):
    tasks = translator.translate("block_flow", {"src": "attacker", "dst": "web1"})
    assert len(tasks) == 1
    t = tasks[0]
    assert t.change_type.value == "create_nacl_entry"
    assert t.params["CidrBlock"] == "10.0.1.99/32"
    assert t.params["RuleAction"] == "deny"


def test_actuator_execute_dry_run_does_not_call_aws(translator, safety, monkeypatch):
    settings = Settings()
    settings.actuation.enabled = True
    settings.actuation.dry_run = True
    actuator = AWSActuator(settings)
    actuator.set_translator(translator)
    actuator.set_safety(safety)

    ec2_calls = []
    monkeypatch.setattr(actuator._ec2, "create_security_group",
                        lambda **kw: ec2_calls.append(kw))

    result = run(actuator.execute("a1", "isolate", {"node": "web1"}))
    assert result.success is True
    assert len(result.changes) == 2
    assert all(c["dry_run"] for c in result.changes)
    assert not ec2_calls


def test_actuator_rolls_back_on_failure(translator, safety, monkeypatch):
    settings = Settings()
    settings.actuation.enabled = True
    settings.actuation.dry_run = False
    actuator = AWSActuator(settings)
    actuator.set_translator(translator)
    actuator.set_safety(safety)

    created = {"n": 0}
    def fake_create(**kw):
        created["n"] += 1
        return {"GroupId": "sg-42", "VpcId": "vpc-1"}
    def fake_modify(**kw):
        raise ClientError({"Error": {"Code": "InvalidParameterValue"}}, "ModifyInstanceAttribute")
    def fake_delete(**kw):
        pass

    monkeypatch.setattr(actuator._ec2, "create_security_group", fake_create)
    monkeypatch.setattr(actuator._ec2, "modify_instance_attribute", fake_modify)
    monkeypatch.setattr(actuator._ec2, "delete_network_acl_entry", fake_delete)

    result = run(actuator.execute("a2", "isolate", {"node": "web1"}))
    assert result.success is False
    assert "InvalidParameterValue" in (result.error or "")
    assert result.rolled_back is True


def test_actuator_rate_limit_requires_mapped_entity(translator, safety):
    settings = Settings()
    settings.actuation.enabled = True
    settings.actuation.allowed_actions = ["rate_limit"]
    actuator = AWSActuator(settings)
    actuator.set_translator(translator)
    actuator.set_safety(safety)
    result = run(actuator.execute("a3", "rate_limit", {"src": "unmapped", "bps": 1e6}))
    assert result.success is False
    assert "mapped source entity" in (result.error or "")


def test_actuator_lifecycle_state_machine(translator, safety, monkeypatch):
    from nettwin.actuation.models import ActionState
    settings = Settings()
    settings.actuation.enabled = True
    settings.actuation.dry_run = False
    actuator = AWSActuator(settings)
    actuator.set_translator(translator)
    actuator.set_safety(safety)

    monkeypatch.setattr(actuator._ec2, "create_security_group",
                        lambda **kw: {"GroupId": "sg-42", "VpcId": "vpc-1"})
    monkeypatch.setattr(actuator._ec2, "modify_instance_attribute", lambda **kw: None)
    monkeypatch.setattr(actuator._ec2, "describe_instance_attribute",
                        lambda **kw: {"Groups": [{"GroupId": "sg-42"}]})

    result = run(actuator.execute("a4", "isolate", {"node": "web1"}))
    assert result.success is True
    assert result.state == ActionState.ENFORCED
    assert ActionState.PENDING in result.state_entered_at
    assert ActionState.TRANSITIONING in result.state_entered_at
    assert ActionState.ENFORCED in result.state_entered_at


def test_rate_limit_uses_tc_by_default(translator, safety):
    tasks = translator.translate("rate_limit", {"src": "web1", "bps": 10_000_000})
    assert len(tasks) == 1
    assert tasks[0].change_type.value == "ssm_send_command"
    assert "tc qdisc" in tasks[0].params["Parameters"]["commands"][0]


def test_rate_limit_waf_backend_requires_web_acl_id(safety):
    waf_translator = ResponseToAWS(
        ActuationSettings(enabled=True, dry_run=False, rate_limit_backend="waf"),
        entity_to_instance={"web1": "i-123"},
        entity_to_ip={"web1": "10.0.1.11"},
        entity_to_subnet={"web1": "subnet-1"},
        entity_to_nacl={"web1": "acl-1"},
    )
    with pytest.raises(ValueError, match="web_acl_id"):
        waf_translator.translate("rate_limit", {"src": "web1", "bps": 1e6})


def test_rate_limit_waf_backend_produces_rate_rule(safety):
    waf_translator = ResponseToAWS(
        ActuationSettings(enabled=True, dry_run=False, rate_limit_backend="waf",
                          web_acl_id="arn:aws:wafv2:us-east-1:123:regional/webacl/foo/id"),
        entity_to_instance={"web1": "i-123"},
        entity_to_ip={"web1": "10.0.1.11"},
        entity_to_subnet={"web1": "subnet-1"},
        entity_to_nacl={"web1": "acl-1"},
    )
    tasks = waf_translator.translate("rate_limit", {"src": "web1", "bps": 1e6})
    assert len(tasks) == 1
    assert tasks[0].change_type.value == "create_waf_rate_rule"
    assert tasks[0].params["Rules"][0]["Statement"]["RateBasedStatement"]["Limit"] > 0


def test_block_flow_uses_nacl_deny_not_rate_limit(translator):
    tasks = translator.translate("block_flow", {"src": "attacker", "dst": "web1"})
    assert len(tasks) == 1
    assert tasks[0].change_type.value == "create_nacl_entry"
    assert tasks[0].params["RuleAction"] == "deny"
