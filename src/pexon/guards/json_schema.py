"""JSON extraction and Pydantic validation with one corrective retry."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


class StructuredOutputError(ValueError):
    """The model did not produce a valid payload after the retry."""


def extract_json(text: str) -> str:
    """Extract the first JSON object or array from a model response."""
    fenced = _FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    start_obj, start_arr = candidate.find("{"), candidate.find("[")
    starts = [i for i in (start_obj, start_arr) if i >= 0]
    if not starts:
        raise StructuredOutputError("no JSON payload found")
    start = min(starts)
    closing = "}" if candidate[start] == "{" else "]"
    end = candidate.rfind(closing)
    if end <= start:
        raise StructuredOutputError("unterminated JSON payload")
    return candidate[start : end + 1]


def parse_model(text: str, model: type[T]) -> T:
    """Parse JSON and validate against a Pydantic model."""
    payload = json.loads(extract_json(text))
    return model.model_validate(payload)


def generate_validated(
    generate: Callable[[str], str],
    system: str,
    prompt: str,
    model: type[T],
    *,
    retries: int = 1,
) -> T:
    """Call a generator, validate, and retry once with the error appended."""
    attempt = 0
    last_error: Exception | None = None
    current = prompt
    while attempt <= retries:
        raw = generate(current)
        try:
            return parse_model(raw, model)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            current = (
                f"{prompt}\n\nDeine vorherige Antwort war ungültig. Fehler: {exc}\n"
                "Antworte erneut ausschließlich mit gültigem JSON im geforderten Schema."
            )
            attempt += 1
    raise StructuredOutputError(f"structured output failed: {last_error}") from last_error
