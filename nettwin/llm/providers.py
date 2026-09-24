"""LLM provider abstraction: Ollama (local) + Amazon Bedrock (cloud)."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

import boto3

log = logging.getLogger("nettwin.llm")


class LLMProvider(ABC):
    """Async-capable LLM interface."""

    @abstractmethod
    async def available(self) -> bool:
        ...

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None,
                       temperature: float = 0.3, max_tokens: int = 512) -> str:
        ...


class OllamaProvider(LLMProvider):
    def __init__(self, settings) -> None:
        self.s = settings
        self._last_check: float = 0.0
        self._cached_available: bool = False

    async def available(self) -> bool:
        now = time.time()
        if now - self._last_check < 30.0:
            return self._cached_available
        self._last_check = now
        def _check() -> bool:
            try:
                req = urllib.request.Request(f"{self.s.ollama_url}/api/tags")
                with urllib.request.urlopen(req, timeout=0.5):
                    return True
            except Exception:
                return False
        self._cached_available = await asyncio.to_thread(_check)
        return self._cached_available

    async def generate(self, prompt: str, system: str | None = None,
                       temperature: float = 0.3, max_tokens: int = 512) -> str:
        payload = json.dumps({
            "model": self.s.model,
            "prompt": prompt,
            "system": system or "",
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }).encode()
        req = urllib.request.Request(
            f"{self.s.ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.s.timeout_s) as resp:
            body = json.loads(resp.read().decode())
        return str(body.get("response", "")).strip()


class BedrockProvider(LLMProvider):
    def __init__(self, settings, aws_region: str = "us-east-1") -> None:
        self.s = settings
        region = self.s.bedrock_region or aws_region
        self._client = boto3.client("bedrock-runtime", region_name=region)

    async def available(self) -> bool:
        # Creating the runtime client is cheap; credential validity is verified
        # on the first generate() call.
        return bool(self.s.bedrock_model)

    async def generate(self, prompt: str, system: str | None = None,
                       temperature: float = 0.3, max_tokens: int = 512) -> str:
        try:
            messages = [{"role": "user", "content": [{"text": prompt}]}]
            system_list = [{"text": system}] if system else []
            resp = self._client.converse(
                modelId=self.s.bedrock_model,
                messages=messages,
                system=system_list,
                inferenceConfig={"temperature": temperature, "maxTokens": max_tokens},
            )
            content = resp.get("output", {}).get("message", {}).get("content", [])
            return "".join(c.get("text", "") for c in content).strip()
        except Exception as exc:
            log.warning("bedrock converse unavailable (%s); routing to deterministic rule engine", exc)
            return ""


class AutoProvider(LLMProvider):
    """Ollama if reachable, otherwise Bedrock if configured, else None."""

    def __init__(self, settings, aws_region: str = "us-east-1") -> None:
        self.ollama = OllamaProvider(settings)
        self.bedrock = BedrockProvider(settings, aws_region)
        self._chosen: LLMProvider | None = None

    async def available(self) -> bool:
        if await self.ollama.available():
            self._chosen = self.ollama
            return True
        if await self.bedrock.available():
            self._chosen = self.bedrock
            return True
        self._chosen = None
        return False

    async def generate(self, prompt: str, system: str | None = None,
                       temperature: float = 0.3, max_tokens: int = 512) -> str:
        if self._chosen is None:
            await self.available()
        if self._chosen is None:
            raise RuntimeError("no LLM provider available")
        return await self._chosen.generate(prompt, system, temperature, max_tokens)


def build_provider(settings, aws_region: str = "us-east-1") -> LLMProvider:
    provider = settings.llm.provider.lower()
    if provider == "ollama":
        return OllamaProvider(settings.llm)
    if provider == "bedrock":
        return BedrockProvider(settings.llm, aws_region)
    return AutoProvider(settings.llm, aws_region)
