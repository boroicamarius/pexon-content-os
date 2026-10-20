"""OpenAI-protocol LLM adapter: one wire contract, many providers."""

from __future__ import annotations

import logging
from typing import Any

from pexon.config.prompts import PROBE_SYSTEM, PROBE_USER
from pexon.config.settings import Settings
from pexon.ports.errors import ProviderError
from pexon.ports.llm import LLMPort, LLMResult

try:
    from openai import OpenAI

    _HAS_OPENAI = True
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]
    _HAS_OPENAI = False

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    _HAS_LANGCHAIN = True
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]
    _HAS_LANGCHAIN = False

logger = logging.getLogger(__name__)
AVAILABLE = _HAS_OPENAI or _HAS_LANGCHAIN
UNAVAILABLE_REASON = "install openai or langchain-openai"


class OpenAICompatibleLLM(LLMPort):
    """Any endpoint that speaks the OpenAI chat-completions protocol."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.effective_llm_model
        self._base_url = settings.effective_llm_base_url.rstrip("/")
        self._api_key = settings.effective_llm_api_key or "not-needed"
        self._client = (
            OpenAI(
                base_url=self._base_url, api_key=self._api_key, timeout=settings.llm_timeout_seconds
            )
            if _HAS_OPENAI
            else None
        )
        self._lc = (
            ChatOpenAI(
                model=self._model,
                base_url=self._base_url,
                api_key=self._api_key,
                temperature=settings.llm_temperature,
                timeout=settings.llm_timeout_seconds,
                max_tokens=settings.llm_max_tokens,
            )
            if _HAS_LANGCHAIN
            else None
        )

    @property
    def provider(self) -> str:
        return "openai-compatible"

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
        """Generate through ChatOpenAI when present, otherwise through the OpenAI SDK."""
        if self._lc is not None:  # type: ignore[union-attr]
            try:
                return self._generate_langchain(system, prompt, json_mode, temperature, max_tokens)
            except Exception as exc:
                if self._client is not None:
                    logger.warning("ChatOpenAI failed; retrying through the OpenAI SDK: %s", exc)
                    return self._generate_sdk(system, prompt, json_mode, temperature, max_tokens)
                raise ProviderError(f"ChatOpenAI call failed: {exc}") from exc
        if self._client is None:
            raise ProviderError(UNAVAILABLE_REASON)
        return self._generate_sdk(system, prompt, json_mode, temperature, max_tokens)

    def _generate_langchain(
        self,
        system: str,
        prompt: str,
        json_mode: bool,
        temperature: float | None,
        max_tokens: int | None,
    ) -> LLMResult:
        runnable: Any = self._lc.bind(
            temperature=self._settings.llm_temperature if temperature is None else temperature,
            max_tokens=max_tokens or self._settings.llm_max_tokens,
        )
        if json_mode:
            runnable = runnable.bind(response_format={"type": "json_object"})
        response = runnable.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        text = response.content if isinstance(response.content, str) else str(response.content)
        usage = getattr(response, "usage_metadata", None) or {}
        return LLMResult(
            text=text,
            provider=self.provider,
            model=self._model,
            tokens_in=int(usage.get("input_tokens", 0) or self._estimate(prompt + system)),
            tokens_out=int(usage.get("output_tokens", 0) or self._estimate(text)),
            finish_reason=str(
                (getattr(response, "response_metadata", None) or {}).get("finish_reason", "")
            ),
        )

    def _generate_sdk(
        self,
        system: str,
        prompt: str,
        json_mode: bool,
        temperature: float | None,
        max_tokens: int | None,
    ) -> LLMResult:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": self._settings.llm_temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self._settings.llm_max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = self._client.chat.completions.create(**kwargs)  # type: ignore[union-attr]
        except Exception as first:
            if json_mode:
                kwargs.pop("response_format", None)
                try:
                    response = self._client.chat.completions.create(**kwargs)  # type: ignore[union-attr]
                except Exception as exc:
                    raise ProviderError(f"OpenAI-compatible call failed: {exc}") from exc
            else:
                raise ProviderError(f"OpenAI-compatible call failed: {first}") from first
        choice = response.choices[0]
        text = choice.message.content or ""
        usage = response.usage
        return LLMResult(
            text=text,
            provider=self.provider,
            model=response.model or self._model,
            tokens_in=int(usage.prompt_tokens if usage else self._estimate(prompt + system)),
            tokens_out=int(usage.completion_tokens if usage else self._estimate(text)),
            finish_reason=choice.finish_reason or "",
        )

    @staticmethod
    def _estimate(text: str) -> int:
        return max(1, len(text) // 4)

    def probe(self) -> bool:
        """One-token round trip against the configured endpoint."""
        self.generate(PROBE_SYSTEM, PROBE_USER, temperature=0.0, max_tokens=8)
        return True
