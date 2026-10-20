"""Native Anthropic Messages adapter with a raw-HTTP fallback."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from pexon.config.prompts import PROBE_SYSTEM, PROBE_USER
from pexon.config.settings import Settings
from pexon.ports.errors import ProviderError
from pexon.ports.llm import LLMPort, LLMResult

try:
    from anthropic import Anthropic

    _HAS_ANTHROPIC = True
except ImportError:
    Anthropic = None  # type: ignore[assignment]
    _HAS_ANTHROPIC = False

logger = logging.getLogger(__name__)
AVAILABLE = True
UNAVAILABLE_REASON = ""


class AnthropicLLM(LLMPort):
    """Claude through the native SDK, or the equivalent Messages HTTP endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.effective_llm_model
        self._base_url = settings.effective_llm_base_url.rstrip("/")
        self._key = settings.effective_llm_api_key
        self._client = (
            Anthropic(
                api_key=self._key, base_url=self._base_url, timeout=settings.llm_timeout_seconds
            )
            if _HAS_ANTHROPIC
            else None
        )

    @property
    def provider(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    def generate(
        self,
        system: str,
        prompt: str,
        *,
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        """Call Claude and return text plus usage."""
        if not self._key:
            raise ProviderError("LLM_API_KEY is required for anthropic")
        instructions = system
        if json_mode:
            instructions += "\nAntworte ausschließlich mit gültigem JSON."
        tokens = max_tokens or self._settings.llm_max_tokens
        temp = self._settings.llm_temperature if temperature is None else temperature
        if self._client is not None:
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=tokens,
                    temperature=temp,
                    system=instructions,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = "".join(block.text for block in response.content if hasattr(block, "text"))
                usage = getattr(response, "usage", None)
                return LLMResult(
                    text=text,
                    provider=self.provider,
                    model=self._model,
                    tokens_in=int(getattr(usage, "input_tokens", 0) or 0),
                    tokens_out=int(getattr(usage, "output_tokens", 0) or 0),
                    finish_reason=str(getattr(response, "stop_reason", "") or ""),
                )
            except Exception as exc:
                raise ProviderError(f"Anthropic SDK call failed: {exc}") from exc
        return self._raw_call(instructions, prompt, tokens, temp, json_mode)

    def _raw_call(
        self, system: str, prompt: str, max_tokens: int, temperature: float, json_mode: bool
    ) -> LLMResult:
        url = self._base_url
        if not url.rstrip("/").endswith("/v1"):
            url = url.rstrip("/") + "/v1"
        url += "/messages"
        body: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            response = httpx.post(
                url,
                headers={
                    "x-api-key": self._key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
                timeout=self._settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise ProviderError(f"Anthropic HTTP call failed: {exc}") from exc
        text = "".join(part.get("text", "") for part in data.get("content", []))
        usage = data.get("usage", {})
        return LLMResult(
            text=text,
            provider=self.provider,
            model=data.get("model", self._model),
            tokens_in=int(usage.get("input_tokens", 0)),
            tokens_out=int(usage.get("output_tokens", 0)),
            finish_reason=str(data.get("stop_reason", "")),
        )

    def probe(self) -> bool:
        """Cheap real Claude call."""
        self.generate(PROBE_SYSTEM, PROBE_USER, temperature=0.0, max_tokens=8)
        return True
