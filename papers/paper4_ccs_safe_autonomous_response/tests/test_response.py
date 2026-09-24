"""Response agent tests: sandbox safety, apply changes sim, bandit reward."""

import os
import sys
from pathlib import Path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REPO_ROOT_PATH = Path(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest

from nettwin.config import Settings
from nettwin.models import Alert
from nettwin.response.agent import ResponseAgent
from nettwin.simulator.engine import SimulationEngine


def _alert(entity="web1", atype="anomaly:throughput_mbps"):
    return Alert(entity_id=entity, entity_kind="node", alert_type=atype,
                 severity="critical", message="test", score=0.95)


def test_constraint_refusals():
    s = Settings()
    agent = ResponseAgent(s, SimulationEngine(s))
    assert agent.constraint_check("isolate", {"node": "core1"}) is not None
    assert agent.constraint_check("isolate", {"node": "db1"}) is not None
    assert agent.constraint_check("isolate", {"node": "ws2"}) is None
    assert agent.constraint_check("reroute", {"link": "attacker-igw"}) is not None
    assert agent.constraint_check("block_flow",
                                  {"src": "attacker", "dst": "web1"}) is None


def test_recommend_sandbox_apply_changes_simulator():
    s = Settings()
    eng = SimulationEngine(s)
    agent = ResponseAgent(s, eng)
    for _ in range(45):
        eng.step()
    eng.start_attack("ddos", target_id="web1", duration_s=None)
    rx_before = 0.0
    for _ in range(5):
        rx_before = eng.step().nodes["web1"].rx_mbps
    proposals = agent.propose([_alert()], {"web1": 0.95})
    assert proposals, "no proposals generated"
    block = next(p for p in proposals if p["kind"] == "block_flow")
    assert block["sandbox"]["improves"], block["sandbox"]
    assert block["sandbox"]["action_health"] > block["sandbox"]["baseline_health"]
    applied = agent.apply(block["id"])
    assert applied["status"] == "applied"
    rx_after = 0.0
    for _ in range(3):
        rx_after = eng.step().nodes["web1"].rx_mbps
    assert rx_after < rx_before * 0.3, f"{rx_before} -> {rx_after}"
    # reward bookkeeping
    agent.tick(80.0)
    eng.tick += agent.s.response.reward_after_ticks + 1
    rewarded = agent.tick(92.0)
    assert rewarded and rewarded[0]["reward"] > 0
    # revert restores attack visibility
    agent.revert(block["id"])
    rx_reverted = 0.0
    for _ in range(3):
        rx_reverted = eng.step().nodes["web1"].rx_mbps
    assert rx_reverted > rx_after * 3


def test_apply_refuses_unsafe_action():
    s = Settings()
    agent = ResponseAgent(s, SimulationEngine(s))
    agent.actions["act-x"] = {
        "id": "act-x", "kind": "isolate", "params": {"node": "core1"},
        "status": "proposed", "sandbox": {"improves": True}, "ctx": None,
        "created_at": 0.0, "bandit_score": 1.0, "alert_id": None}
    with pytest.raises(ValueError):
        agent.apply("act-x")
    assert agent.actions["act-x"]["status"] == "rejected"


def test_bandit_learns_without_nan():
    import numpy as np
    from nettwin.response.agent import LinearThompsonBandit
    bandit = LinearThompsonBandit(8, 0.4)
    ctx = np.array([1.0, 1.0, 1.0, 0.9, 1.0, 0.0, 0.0, 0.0])
    for reward in (0.5, 0.6, 0.55):
        bandit.update("block_flow", ctx, reward)
    score = bandit.score("block_flow", ctx)
    assert np.isfinite(score)
    assert bandit.b["block_flow"][0] > 1.0


def test_response_agent_bandit_class():
    import numpy as np
    from eval.baselines import UCB1Bandit
    s = Settings()
    eng = SimulationEngine(s)
    agent = ResponseAgent(s, eng, bandit_class=UCB1Bandit)
    assert isinstance(agent.bandit, UCB1Bandit)
    ctx = np.array([1.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0])
    score = agent.bandit.score("block_flow", ctx)
    assert np.isfinite(score)
    agent.bandit.update("block_flow", ctx, 0.5)
    assert agent.bandit.counts["block_flow"] == 1
