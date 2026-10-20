"""German language detection with a zero-dependency fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass

try:
    from langdetect import DetectorFactory, detect_langs

    DetectorFactory.seed = 0
    _HAS_LANGDETECT = True
except Exception:
    _HAS_LANGDETECT = False

_STOPWORDS = {
    "der",
    "die",
    "das",
    "und",
    "oder",
    "für",
    "mit",
    "von",
    "den",
    "dem",
    "des",
    "ein",
    "eine",
    "einer",
    "im",
    "in",
    "ist",
    "sind",
    "wird",
    "werden",
    "nicht",
    "auf",
    "bei",
    "aus",
    "als",
    "auch",
    "sich",
    "durch",
    "zum",
    "zur",
    "können",
    "muss",
    "müssen",
    "soll",
    "sollen",
    "banken",
    "regulierung",
    "daten",
}
_WORD = re.compile(r"[A-Za-zÄÖÜäöüß]+")


@dataclass(frozen=True)
class LanguageVerdict:
    """Detected language plus confidence."""

    language: str
    confidence: float
    german: bool


def detect_german(
    text: str,
    minimum_score: float,
    stopword_multiplier: float = 2.2,
    umlaut_bonus_cap: float = 0.15,
) -> LanguageVerdict:
    """Detect German via langdetect when installed, otherwise stopword density."""
    sample = text[:6000]
    if _HAS_LANGDETECT:
        try:
            ranked = detect_langs(sample)
            german = next((r for r in ranked if r.lang == "de"), None)
            score = float(german.prob) if german else 0.0
            top = ranked[0].lang if ranked else "unknown"
            return LanguageVerdict(language=top, confidence=score, german=score >= minimum_score)
        except Exception:
            pass
    words = [w.lower() for w in _WORD.findall(sample)]
    if not words:
        return LanguageVerdict(language="unknown", confidence=0.0, german=False)
    hits = sum(1 for w in words if w in _STOPWORDS)
    umlauts = sum(1 for w in words if any(c in w for c in "äöüß"))
    density = hits / len(words)
    umlaut_bonus = min(umlaut_bonus_cap, umlauts / max(len(words), 1))
    score = min(1.0, density * stopword_multiplier + umlaut_bonus)
    return LanguageVerdict(
        language="de" if score >= minimum_score else "unknown",
        confidence=round(score, 4),
        german=score >= minimum_score,
    )
