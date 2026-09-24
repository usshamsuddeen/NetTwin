"""LLM provider, embeddings, and analyst memory tests."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nettwin.config import Settings
from nettwin.llm.analyst import SecurityAnalyst
from nettwin.llm.embeddings import OllamaEmbedder
from nettwin.llm.providers import AutoProvider, BedrockProvider, OllamaProvider


def _run(coro):
    return asyncio.run(coro)


def test_ollama_provider_available_false_when_server_down():
    from nettwin.config import LLMSettings
    p = OllamaProvider(LLMSettings())
    assert _run(p.available()) is False


def test_bedrock_provider_available_requires_model():
    from nettwin.config import LLMSettings
    p = BedrockProvider(LLMSettings(bedrock_model=""))
    assert _run(p.available()) is False
    p2 = BedrockProvider(LLMSettings(bedrock_model="some-model"))
    assert _run(p2.available()) is True


def test_auto_provider_falls_back_when_none_available():
    from nettwin.config import LLMSettings
    p = AutoProvider(LLMSettings(provider="auto", bedrock_model=""))
    assert _run(p.available()) is False


def test_analyst_uses_fallback_when_llm_unreachable():
    settings = Settings()
    settings.llm.provider = "ollama"
    state = MagicMock()
    state.twin.network_health = 100.0
    state.twin.kpis.model_dump.return_value = {}
    state.detector.scores = {}
    state.detector.signals = {}
    state.alerts.active.return_value = []
    state.engine.tick = 0
    state.engine.attacks = {}
    analyst = SecurityAnalyst(settings, state)
    answer = _run(analyst.ask("what is happening?"))
    assert answer.mode == "fallback"
    assert "network_health" in answer.context_used


def test_analyst_conversation_memory_carries_across_questions():
    settings = Settings()
    settings.llm.provider = "ollama"
    state = MagicMock()
    state.twin.network_health = 95.0
    state.twin.kpis.model_dump.return_value = {}
    state.detector.scores = {}
    state.detector.signals = {}
    state.alerts.active.return_value = []
    state.engine.tick = 1
    state.engine.attacks = {}
    analyst = SecurityAnalyst(settings, state)

    with patch.object(analyst.provider, "available", return_value=True), \
         patch.object(analyst.provider, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "first answer"
        _run(analyst.ask("Q1", session_id="s1"))
        _run(analyst.ask("Q2", session_id="s1"))
        calls = mock_gen.call_args_list
        assert len(calls) == 2
        assert "Q1" in calls[1][0][0] or "first answer" in calls[1][0][0]


def test_ollama_embedder_shapes_and_normalizes():
    import json as _json
    from nettwin.config import LLMSettings
    emb = OllamaEmbedder(LLMSettings(embedding_model="dummy"))
    fake = {"embedding": [3.0, 4.0]}
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value.read.return_value = _json.dumps(fake).encode()
    mock_resp.__exit__.return_value = False
    with patch("urllib.request.urlopen", return_value=mock_resp):
        out = _run(emb.embed(["hello"]))
    assert len(out) == 1
    assert len(out[0]) == 2
    # cosine-normalized -> [0.6, 0.8]
    assert abs(out[0][0] - 0.6) < 1e-6
    assert abs(out[0][1] - 0.8) < 1e-6
