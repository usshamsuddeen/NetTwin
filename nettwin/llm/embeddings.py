"""Embedding providers: Ollama (local) and Amazon Bedrock (cloud)."""
from __future__ import annotations

import asyncio
import json
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

import boto3


def _cos_norm(v: list[float]) -> list[float]:
    norm = sum(x * x for x in v) ** 0.5
    if norm < 1e-9:
        return v
    return [x / norm for x in v]


class Embedder(ABC):
    """Async text embedder."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    async def embed_one(self, text: str) -> list[float] | None:
        out = await self.embed([text])
        return out[0] if out else None


class OllamaEmbedder(Embedder):
    def __init__(self, settings) -> None:
        self.s = settings
        self._url = f"{settings.ollama_url}/api/embeddings"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        sem = asyncio.Semaphore(4)

        async def _one(text: str) -> list[float]:
            async with sem:
                return await asyncio.to_thread(self._embed_sync, text)

        return await asyncio.gather(*[_one(t) for t in texts])

    def _embed_sync(self, text: str) -> list[float]:
        payload = json.dumps({
            "model": self.s.embedding_model,
            "prompt": text,
        }).encode()
        req = urllib.request.Request(
            self._url,
            data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.s.timeout_s) as resp:
            body = json.loads(resp.read().decode())
        return _cos_norm(body.get("embedding", []))


class BedrockEmbedder(Embedder):
    # Prefer Titan Embed v2; fallback to Cohere Embed v3.
    DEFAULT_MODEL = "amazon.titan-embed-text-v2:0"

    def __init__(self, settings, aws_region: str = "us-east-1") -> None:
        self.s = settings
        region = settings.bedrock_region or aws_region
        self._client = boto3.client("bedrock-runtime", region_name=region)
        self._model = getattr(settings, "embedding_model", "") or self.DEFAULT_MODEL

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.gather(*[self._embed_one(t) for t in texts])

    async def _embed_one(self, text: str) -> list[float]:
        return await asyncio.to_thread(self._embed_sync, text)

    def _embed_sync(self, text: str) -> list[float]:
        model = self._model
        if "cohere" in model.lower():
            body = json.dumps({"texts": [text], "input_type": "search_document"})
        else:
            body = json.dumps({"inputText": text})
        resp = self._client.invoke_model(modelId=model, body=body.encode())
        result = json.loads(resp["body"].read().decode())
        if "embedding" in result:
            emb = result["embedding"]
            if isinstance(emb, list):
                return _cos_norm(emb)
            if isinstance(emb, dict):  # Titan v2 multi-lingual
                return _cos_norm(emb.get("float", []))
        if "embeddings" in result:  # Cohere
            return _cos_norm(result["embeddings"][0])
        raise RuntimeError(f"unexpected bedrock embedding response: {list(result.keys())}")


def build_embedder(settings, aws_region: str = "us-east-1") -> Embedder | None:
    """Build embedder using LLM provider preference."""
    llm = settings.llm
    provider = llm.provider.lower()
    if provider == "ollama":
        return OllamaEmbedder(llm)
    if provider == "bedrock":
        return BedrockEmbedder(llm, aws_region)
    if provider == "auto":
        # Prefer Ollama if it appears reachable; otherwise Bedrock.
        try:
            req = urllib.request.Request(f"{llm.ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=1.0):
                return OllamaEmbedder(llm)
        except Exception:
            pass
        if llm.bedrock_model:
            return BedrockEmbedder(llm, aws_region)
    return None
