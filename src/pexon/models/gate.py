"""Quality-gate value objects."""

from __future__ import annotations

from pydantic import Field

from pexon.models.base import FrozenModel


class GateResult(FrozenModel):
    """One named, evidence-backed gate decision."""

    name: str
    passed: bool
    reason: str = ""
    evidence: dict[str, float | str | bool] = Field(default_factory=dict)


class GateReport(FrozenModel):
    """All gate decisions for one candidate."""

    passed: bool
    results: tuple[GateResult, ...]
    candidate_id: str
    reasons: tuple[str, ...] = Field(default_factory=tuple)


class ScoreEvidence(FrozenModel):
    """A judge dimension must carry a score and concrete evidence."""

    score: float = Field(ge=0.0, le=1.0)
    evidence: str


class JudgeAssessment(FrozenModel):
    """Structured, evidence-bearing judge verdict."""

    factuality: ScoreEvidence
    compliance: ScoreEvidence
    german_fluency: ScoreEvidence


class FactVerdict(FrozenModel):
    """Whether a claim is present in the cited source excerpt."""

    present: bool
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_de: str
