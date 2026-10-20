"""Prompt-injection and HTML sanitisation for untrusted page text."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from pexon.config.settings import Settings

_BLOCK_TAGS = re.compile(
    r"<(script|style|iframe|noscript|svg|form|object|embed)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SPACE = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class SanitizedText:
    """Clean text plus a count of removed injection patterns."""

    text: str
    removed_patterns: int


class Sanitizer:
    """Strips markup, comments and prompt-injection phrases."""

    def __init__(self, settings: Settings) -> None:
        self._patterns = [
            re.compile(pattern, re.IGNORECASE | re.DOTALL)
            for pattern in settings.injection_pattern_list
        ]
        self._max_chars = settings.fetch_max_chars

    def clean(self, raw: str) -> SanitizedText:
        """Return safe plain text truncated to the configured limit."""
        text = html.unescape(raw or "")
        text = _BLOCK_TAGS.sub(" ", text)
        text = _COMMENTS.sub(" ", text)
        text = _TAGS.sub(" ", text)
        text = _CONTROL.sub("", text)
        removed = 0
        for pattern in self._patterns:
            text, hits = pattern.subn(" [entfernt] ", text)
            removed += hits
        text = _SPACE.sub(" ", text)
        text = _BLANKS.sub("\n\n", text).strip()
        return SanitizedText(text=text[: self._max_chars], removed_patterns=removed)
