"""Knowledge base retrieval tests."""

import os
import sys
from pathlib import Path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REPO_ROOT_PATH = Path(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import asyncio

from nettwin.llm.kb import KnowledgeBase


def _run(coro):
    return asyncio.run(coro)


def test_retrieval_returns_relevant_technique():
    kb = KnowledgeBase()

    async def _check():
        r = await kb.retrieve("brute force ssh password guessing authentication attempts")
        assert r and r[0]["id"].startswith("T1110"), r
        r = await kb.retrieve("volumetric ddos flood saturate bandwidth udp")
        assert r and r[0]["id"] in ("T1498", "T1499"), r
        r = await kb.retrieve("data exfiltration sustained server egress upload")
        assert any(t["id"] in ("T1041", "T1048", "T1567") for t in r), r
        r = await kb.retrieve("lateral movement ssh smb internal hosts compromise")
        assert any(t["id"].startswith("T1021") for t in r), r
        r = await kb.retrieve("port scan reconnaissance many tiny connections fanout")
        assert any(t["id"] == "T1046" for t in r), r

    _run(_check())


def test_retrieval_empty_query_safe():
    kb = KnowledgeBase()

    async def _check():
        assert await kb.retrieve("", k=3) == []
        assert await kb.retrieve("zzzz qqqq", k=3) == []

    _run(_check())
