"""Deterministic PII redaction applied before every LLM call."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pexon.config.settings import Settings

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}[ ]?[A-Z0-9]{1,4}\b")
_PHONE = re.compile(
    r"(?<!\w)(?:\+49|0049|0)[\s./-]?(?:\(?\d{2,5}\)?[\s./-]?)?\d{3,}[\s./-]?\d{2,}(?!\w)"
)


@dataclass(frozen=True)
class PIIReport:
    """Redacted text and per-category counts."""

    text: str
    redactions: int
    categories: dict[str, int]


class PIIRedactor:
    """Redacts emails, IBANs, phones and configured public figures."""

    def __init__(self, settings: Settings) -> None:
        self._token = settings.pii_redaction_token
        self._names = [
            re.compile(rf"\b{re.escape(n)}\b", re.IGNORECASE) for n in settings.public_figures
        ]

    def redact(self, text: str) -> PIIReport:
        """Return redacted text and a count for metrics."""
        categories: dict[str, int] = {}
        current = text
        for category, pattern in (("email", _EMAIL), ("iban", _IBAN), ("phone", _PHONE)):
            current, hits = pattern.subn(f"{self._token}:{category.upper()}", current)
            if hits:
                categories[category] = hits
        name_hits = 0
        for pattern in self._names:
            current, hits = pattern.subn(f"{self._token}:NAME", current)
            name_hits += hits
        if name_hits:
            categories["name"] = name_hits
        return PIIReport(text=current, redactions=sum(categories.values()), categories=categories)
