"""
Ollama API wrapper with streaming support and retry logic.

Connects to a local Ollama instance for LLM inference via the /api/chat endpoint.
"""

import json
import logging
import time
from typing import Generator, Optional

import requests
from config import OLLAMA_TIMEOUT

logger = logging.getLogger(__name__)


class OllamaConnectionError(Exception):
    """Raised when Ollama server is unreachable."""
    pass


class OllamaResponseError(Exception):
    """Raised when Ollama returns an unexpected response."""
    pass


class OllamaClient:
    """Client for the Ollama /api/chat API with retry and streaming support."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:1.5b",
        max_retries: int = 3,
        timeout: int = OLLAMA_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        self._chat_url = f"{self.base_url}/api/chat"
        self._session_log: list[dict] = []

    # ── public API ────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        stream: bool = False,
        temperature: float | None = None,
        options: dict | None = None,
    ) -> str:
        """
        Send a chat request and return the full assistant response as a string.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            stream: If True, streams internally but still returns full string.
            temperature: Override default temperature (0.0-1.0).
            options: Additional Ollama generation options.

        Returns:
            The assistant's reply text.
        """
        from datamind.security.prompt_guard import PromptGuard
        from datamind.security.rate_limiter import RateLimiter
        import streamlit as st
        import logging

        # Rate Limiting
        if hasattr(st, 'session_state') and 'current_user' in st.session_state and st.session_state.current_user:
            user_id = st.session_state.current_user['id']
            if user_id:
                rate_result = RateLimiter.check_ollama(user_id)
                if not rate_result["allowed"]:
                    return rate_result["message"]
        
        # PromptGuard Injection Scan
        secured_messages = []
        for msg in messages:
            if msg["role"] == "user":
                scan_res = PromptGuard.scan_for_injection(msg["content"])
                if scan_res["threat_level"] == "high":
                    logging.warning(f"HIGH RISK prompt injection blocked: {msg['content'][:100]}")
                    return "I cannot process this request."
                secured_messages.append({"role": "user", "content": scan_res["filtered_text"]})
            elif msg["role"] == "system":
                secured_messages.append({"role": "system", "content": PromptGuard.wrap_system_prompt(msg["content"])})
            else:
                secured_messages.append(msg)
        
        messages = secured_messages

        if stream:
            chunks = list(self.stream_chat(messages, temperature=temperature, options=options))
            return "".join(chunks)

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        # Apply options
        gen_options = dict(options) if options else {}
        if temperature is not None:
            gen_options["temperature"] = temperature
        if gen_options:
            payload["options"] = gen_options

        response_data = self._request_with_retry(payload)
        content = response_data.get("message", {}).get("content", "")

        self._log(messages, content)
        return content

    def stream_chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        options: dict | None = None,
    ) -> Generator[str, None, None]:
        """
        Stream a chat response, yielding text chunks as they arrive.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            temperature: Override default temperature.
            options: Additional Ollama generation options.

        Yields:
            Successive content chunks from the assistant.
        """
        from datamind.security.prompt_guard import PromptGuard
        from datamind.security.rate_limiter import RateLimiter
        import streamlit as st
        import logging

        # Rate Limiting
        if hasattr(st, 'session_state') and 'current_user' in st.session_state and st.session_state.current_user:
            user_id = st.session_state.current_user['id']
            if user_id:
                rate_result = RateLimiter.check_ollama(user_id)
                if not rate_result["allowed"]:
                    yield rate_result["message"]
                    return
        
        # PromptGuard Injection Scan
        secured_messages = []
        for msg in messages:
            if msg["role"] == "user":
                scan_res = PromptGuard.scan_for_injection(msg["content"])
                if scan_res["threat_level"] == "high":
                    logging.warning(f"HIGH RISK prompt injection blocked: {msg['content'][:100]}")
                    yield "I cannot process this request."
                    return
                secured_messages.append({"role": "user", "content": scan_res["filtered_text"]})
            elif msg["role"] == "system":
                secured_messages.append({"role": "system", "content": PromptGuard.wrap_system_prompt(msg["content"])})
            else:
                secured_messages.append(msg)
        
        messages = secured_messages

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        gen_options = dict(options) if options else {}
        if temperature is not None:
            gen_options["temperature"] = temperature
        if gen_options:
            payload["options"] = gen_options

        full_content = []

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    self._chat_url,
                    json=payload,
                    stream=True,
                    timeout=self.timeout,
                    proxies={"http": None, "https": None}
                )
                resp.raise_for_status()

                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_content.append(token)
                        yield token

                    if chunk.get("done"):
                        break

                self._log(messages, "".join(full_content))
                return  # success — exit generator

            except requests.ConnectionError:
                raise OllamaConnectionError(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    "Make sure Ollama is running (`ollama serve`)."
                )
            except requests.HTTPError as exc:
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "Ollama stream attempt %d/%d failed (%s), retrying in %ds…",
                        attempt, self.max_retries, exc, wait
                    )
                    time.sleep(wait)
                else:
                    raise OllamaResponseError(
                        f"Ollama returned an error after {self.max_retries} attempts: {exc}"
                    ) from exc

    def is_available(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5, proxies={"http": None, "https": None})
            return resp.status_code == 200
        except requests.ConnectionError:
            return False

    def list_models(self) -> list[str]:
        """Return a list of locally available model names."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10, proxies={"http": None, "https": None})
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return [m["name"] for m in models]
        except Exception:
            return []

    @property
    def session_log(self) -> list[dict]:
        """Return the session log for debugging."""
        return list(self._session_log)

    # ── internals ─────────────────────────────────────────────────────

    def _request_with_retry(self, payload: dict) -> dict:
        """POST with exponential-backoff retry."""
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Ollama Request: {self._chat_url} - Payload: {payload}")
                resp = requests.post(
                    self._chat_url, json=payload, timeout=self.timeout, proxies={"http": None, "https": None}
                )
                if resp.status_code != 200:
                    logger.error(f"Ollama Error Response: {resp.status_code} - {resp.text}")
                resp.raise_for_status()
                return resp.json()

            except requests.ConnectionError:
                raise OllamaConnectionError(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    "Make sure Ollama is running (`ollama serve`)."
                )
            except requests.HTTPError as exc:
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "Ollama attempt %d/%d failed (%s), retrying in %ds…",
                        attempt, self.max_retries, exc, wait,
                    )
                    time.sleep(wait)
                else:
                    raise OllamaResponseError(
                        f"Ollama returned an error after {self.max_retries} attempts: {exc}"
                    ) from exc

        # Should never reach here, but just in case
        raise OllamaResponseError("Exhausted retries without success.")

    def _log(self, messages: list[dict], response: str) -> None:
        """Append to session log for debugging."""
        self._session_log.append({
            "timestamp": time.time(),
            "model": self.model,
            "messages": messages,
            "response": response,
        })
