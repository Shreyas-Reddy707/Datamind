"""DataMind v2 Async LiteLLM Client.

Cost-first model router defaulting to local ollama/qwen2.5-coder:7b with
configurable cloud fallbacks, exponential backoff retries, token usage tracking,
and deterministic 768-dimensional embeddings matching Vector(768).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import time
from collections.abc import AsyncGenerator
from typing import Any

# Crucial: Disable LiteLLM external network probes & telemetry BEFORE importing litellm
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["DISABLE_TELEMETRY"] = "TRUE"
os.environ["LITELLM_TELEMETRY"] = "False"

import httpx
import litellm
from litellm import acompletion

from app.config import settings

logger = logging.getLogger("datamind.llm.client")

litellm.telemetry = False
litellm.drop_params = True
litellm.suppress_debug_info = True
litellm.set_verbose = False


class LLMClient:
    """Async client managing cost-first LLM completions and embeddings."""

    def __init__(
        self,
        default_model: str | None = None,
        base_url: str | None = None,
        quick_timeout: int = 15,
        deep_timeout: int = 45,
    ):
        raw_model = default_model or settings.OLLAMA_MODEL
        # Ensure ollama/ prefix for LiteLLM if not present
        if not raw_model.startswith(("ollama/", "openai/", "anthropic/", "gemini/")):
            self.default_model = f"ollama/{raw_model}"
        else:
            self.default_model = raw_model

        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.quick_timeout = quick_timeout
        self.deep_timeout = deep_timeout
        self._ollama_embed_unavailable_until: float = 0.0
        self._ollama_chat_unavailable_until: float = 0.0

    def is_chat_circuit_open(self, model: str | None = None) -> bool:
        """Return True when local Ollama chat circuit breaker is currently tripped."""
        target_model = model or self.default_model
        return target_model.startswith("ollama/") and time.time() < self._ollama_chat_unavailable_until

    @staticmethod
    def _strip_ollama_prefix(model_name: str) -> str:
        return model_name[7:] if model_name.startswith("ollama/") else model_name

    async def check_ollama_status(self) -> dict[str, Any]:
        """Probe local Ollama HTTP endpoint (/api/tags) and report live/minimal mode status."""
        base = self.base_url.rstrip("/")
        model_bare = self._strip_ollama_prefix(self.default_model)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(1.5, connect=1.0)) as client:
                resp = await client.get(f"{base}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", []) if isinstance(m, dict)]
                    self._ollama_chat_unavailable_until = 0.0
                    self._ollama_embed_unavailable_until = 0.0
                    return {
                        "online": True,
                        "provider": "ollama",
                        "model": model_bare,
                        "available_models": models,
                        "mode_label": f"Ollama Live ({model_bare})",
                    }
        except Exception as exc:
            logger.debug("Ollama status check offline: %s", exc)

        return {
            "online": False,
            "provider": "minimal",
            "model": model_bare,
            "available_models": [],
            "mode_label": "Minimal Mode (DuckDB Engine)",
        }

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout: int | None = None,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        """Execute chat completion via direct httpx for Ollama or LiteLLM for cloud models."""
        target_model = model or self.default_model
        is_ollama = target_model.startswith("ollama/")

        if is_ollama:
            if self.is_chat_circuit_open(target_model):
                return {
                    "content": "",
                    "model": "offline-fallback",
                    "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "finish_reason": "circuit_open",
                }
            base = self.base_url.rstrip("/")
            bare_model = self._strip_ollama_prefix(target_model)
            req_timeout = float(timeout or self.quick_timeout)
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(req_timeout, connect=1.5)
                ) as client:
                    resp = await client.post(
                        f"{base}/api/chat",
                        json={
                            "model": bare_model,
                            "messages": messages,
                            "stream": False,
                            "options": {
                                "temperature": temperature,
                                "num_predict": max_tokens,
                            },
                        },
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                    content = (payload.get("message") or {}).get("content", "")
                    prompt_tokens = int(payload.get("prompt_eval_count", 0) or 0)
                    completion_tokens = int(payload.get("eval_count", 0) or 0)
                    return {
                        "content": content,
                        "model": target_model,
                        "tokens": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": prompt_tokens + completion_tokens,
                        },
                        "finish_reason": payload.get("done_reason", "stop"),
                    }
            except Exception as e:
                self._ollama_chat_unavailable_until = time.time() + 60.0
                logger.info(
                    "Local Ollama chat unavailable (%s); activating 60s circuit breaker.",
                    type(e).__name__,
                )
                return {
                    "content": "",
                    "model": "offline-fallback",
                    "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "finish_reason": "fallback",
                    "error": str(e),
                }

        req_timeout = timeout or self.quick_timeout
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    acompletion(
                        model=target_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ),
                    timeout=req_timeout,
                )
                content = response.choices[0].message.content or ""
                usage = getattr(response, "usage", None)
                tokens_info = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                    "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                    "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
                }
                return {
                    "content": content,
                    "model": target_model,
                    "tokens": tokens_info,
                    "finish_reason": response.choices[0].finish_reason,
                }
            except Exception as e:
                last_error = e
                logger.warning("LLM chat attempt %d failed for %s: %s", attempt + 1, target_model, str(e))
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (2**attempt))

        return {
            "content": "",
            "model": "offline-fallback",
            "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "finish_reason": "fallback",
            "error": str(last_error) if last_error else "offline",
        }

    async def stream_chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat tokens via direct httpx for Ollama or LiteLLM for cloud models."""
        target_model = model or self.default_model
        is_ollama = target_model.startswith("ollama/")

        if is_ollama:
            if self.is_chat_circuit_open(target_model):
                return
            base = self.base_url.rstrip("/")
            bare_model = self._strip_ollama_prefix(target_model)
            req_timeout = float(timeout or self.deep_timeout)
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(req_timeout, connect=1.5)
                ) as client:
                    async with client.stream(
                        "POST",
                        f"{base}/api/chat",
                        json={
                            "model": bare_model,
                            "messages": messages,
                            "stream": True,
                            "options": {
                                "temperature": temperature,
                                "num_predict": max_tokens,
                            },
                        },
                    ) as resp:
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            if not line.strip():
                                continue
                            chunk = json.loads(line)
                            delta = (chunk.get("message") or {}).get("content", "")
                            if delta:
                                yield delta
                            if chunk.get("done"):
                                break
                return
            except Exception as e:
                self._ollama_chat_unavailable_until = time.time() + 60.0
                logger.info(
                    "Local Ollama stream unavailable (%s); activating 60s circuit breaker.",
                    type(e).__name__,
                )
                return

        req_timeout = timeout or self.deep_timeout
        try:
            response = await asyncio.wait_for(
                acompletion(
                    model=target_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                ),
                timeout=req_timeout,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    yield delta
        except Exception as e:
            logger.warning("Streaming failed for %s: %s.", target_model, e)

    async def get_embedding(self, text: str) -> list[float]:
        """
        Generate 768-dimensional normalized embedding matching Vector(768).
        Tries direct Ollama HTTP embeddings first; falls back to deterministic hash projection with circuit breaker.
        """
        clean_text = text.strip()
        if not clean_text:
            return [0.0] * 768

        now = time.time()
        if now >= self._ollama_embed_unavailable_until:
            try:
                base = self.base_url.rstrip("/")
                async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.5)) as client:
                    resp = await client.post(
                        f"{base}/api/embeddings",
                        json={"model": settings.EMBEDDING_MODEL, "prompt": clean_text},
                    )
                    if resp.status_code == 200:
                        raw_vec = resp.json().get("embedding", [])
                        if isinstance(raw_vec, list) and len(raw_vec) == 768:
                            return self._normalize_vector(raw_vec)
                self._ollama_embed_unavailable_until = now + 60.0
            except Exception as exc:
                self._ollama_embed_unavailable_until = now + 60.0
                logger.debug(
                    "Ollama embedding unavailable (%s); activating 60s circuit breaker", exc
                )

        # Deterministic 768-D pseudo-random projection based on SHA-256 + sha512 seeds (<1ms)
        return self.generate_deterministic_embedding(clean_text, dimensions=768)

    @staticmethod
    def _normalize_vector(vec: list[float]) -> list[float]:
        """L2-normalize vector to unit length."""
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return vec
        return [x / norm for x in vec]

    @classmethod
    def generate_deterministic_embedding(cls, text: str, dimensions: int = 768) -> list[float]:
        """Generate high-entropy, deterministic normalized embedding vector."""
        vec: list[float] = []
        base_bytes = text.encode("utf-8")
        # Generate dimensions float coordinates using rotating hash seeds
        chunks_needed = math.ceil(dimensions / 16)  # 64 bytes per sha512 = 16 floats (4 bytes each)
        for i in range(chunks_needed):
            hasher = hashlib.sha512(base_bytes + i.to_bytes(4, byteorder="big"))
            digest = hasher.digest()
            for j in range(0, 64, 4):
                if len(vec) < dimensions:
                    val = int.from_bytes(digest[j : j + 4], byteorder="big", signed=True)
                    vec.append(float(val) / 2147483648.0)

        return cls._normalize_vector(vec)


llm_client = LLMClient()
