"""Google Gemini adapter with native SDK and raw REST paths."""

from __future__ import annotations

import logging

import httpx

from pexon.config.prompts import PROBE_SYSTEM, PROBE_USER
from pexon.config.settings import Settings
from pexon.ports.errors import ProviderError
from pexon.ports.llm import LLMPort, LLMResult

try:
    from google import genai
    from google.genai import types as genai_types

    _HAS_GENAI = True
except ImportError:
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]
    _HAS_GENAI = False

logger = logging.getLogger(__name__)
AVAILABLE = True
UNAVAILABLE_REASON = ""


class GeminiLLM(LLMPort):
    """Gemini through google-genai when installed, otherwise REST."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.effective_llm_model
        self._base_url = settings.effective_llm_base_url.rstrip("/")
        self._key = settings.effective_llm_api_key
        self._client = genai.Client(api_key=self._key) if _HAS_GENAI and self._key else None

    @property
    def provider(self) -> str:
        return "gemini"

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
        """Call Gemini and return text plus usage."""
        if not self._key:
            raise ProviderError("LLM_API_KEY is required for gemini")
        temp = self._settings.llm_temperature if temperature is None else temperature
        tokens = max_tokens or self._settings.llm_max_tokens
        if self._client is not None and genai_types is not None:
            try:
                config = genai_types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temp,
                    max_output_tokens=tokens,
                    response_mime_type="application/json" if json_mode else "text/plain",
                )
                response = self._client.models.generate_content(
                    model=self._model, contents=prompt, config=config
                )
                text = response.text or ""
                usage = getattr(response, "usage_metadata", None)
                return LLMResult(
                    text=text,
                    provider=self.provider,
                    model=self._model,
                    tokens_in=int(getattr(usage, "prompt_token_count", 0) or 0),
                    tokens_out=int(getattr(usage, "candidates_token_count", 0) or 0),
                    finish_reason=str(getattr(response, "finish_reason", "") or ""),
                )
            except Exception as exc:
                raise ProviderError(f"Gemini SDK call failed: {exc}") from exc
        return self._raw_call(system, prompt, tokens, temp, json_mode)

    def _raw_call(
        self, system: str, prompt: str, max_tokens: int, temperature: float, json_mode: bool
    ) -> LLMResult:
        base = self._base_url.rstrip("/")
        url = f"{base}/v1beta/models/{self._model}:generateContent"
        generation_config: dict[str, object] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if json_mode:
            generation_config["responseMimeType"] = "application/json"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        try:
            response = httpx.post(
                url,
                headers={"x-goog-api-key": self._key, "content-type": "application/json"},
                json=body,
                timeout=self._settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise ProviderError(f"Gemini HTTP call failed: {exc}") from exc
        candidates = data.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(part.get("text", "") for part in parts)
        usage = data.get("usageMetadata", {})
        return LLMResult(
            text=text,
            provider=self.provider,
            model=self._model,
            tokens_in=int(usage.get("promptTokenCount", 0)),
            tokens_out=int(usage.get("candidatesTokenCount", 0)),
            finish_reason=str(candidates[0].get("finishReason", "")) if candidates else "",
        )

    def probe(self) -> bool:
        """Cheap real Gemini call."""
        self.generate(PROBE_SYSTEM, PROBE_USER, temperature=0.0, max_tokens=8)
        return True
