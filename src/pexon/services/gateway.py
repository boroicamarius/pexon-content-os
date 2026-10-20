"""LLM gateway: PII redaction, usage metrics and JSON validation in one seam."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from pexon.config.settings import Settings
from pexon.guards.json_schema import generate_validated
from pexon.guards.pii import PIIRedactor
from pexon.observability.metrics import MetricsCollector
from pexon.ports.llm import LLMPort, LLMResult

logger = logging.getLogger(__name__)


class LLMGateway:
    """Every LLM call in the system passes through this class."""

    def __init__(self, llm: LLMPort, settings: Settings, metrics: MetricsCollector) -> None:
        self._llm = llm
        self._settings = settings
        self._metrics = metrics
        self._redactor = PIIRedactor(settings)

    @property
    def port(self) -> LLMPort:
        """Underlying provider for doctor and provenance."""
        return self._llm

    def _call(
        self,
        system: str,
        prompt: str,
        *,
        json_mode: bool,
        temperature: float | None,
        max_tokens: int | None,
    ) -> LLMResult:
        safe_system = self._redactor.redact(system)
        safe_prompt = self._redactor.redact(prompt)
        if safe_system.redactions or safe_prompt.redactions:
            self._metrics.inc(
                "pii_redactions",
                {"provider": self._llm.provider},
                safe_system.redactions + safe_prompt.redactions,
            )
        result = self._llm.generate(
            safe_system.text,
            safe_prompt.text,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self._metrics.record_llm(result)
        return result

    def text(
        self,
        system: str,
        prompt: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        """Generate plain text with accounting."""
        return self._call(
            system, prompt, json_mode=json_mode, temperature=temperature, max_tokens=max_tokens
        ).text

    def structured(
        self,
        system: str,
        prompt: str,
        model: type[BaseModel],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> BaseModel:
        """Generate, validate and retry once with the validation error."""

        def call(current: str) -> str:
            return self._call(
                system, current, json_mode=True, temperature=temperature, max_tokens=max_tokens
            ).text

        return generate_validated(
            call, system, prompt, model, retries=self._settings.llm_json_retries
        )
