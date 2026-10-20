"""Draft value objects."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field, field_validator

from pexon.models.base import FrozenModel


class Section(FrozenModel):
    """A German Markdown section."""

    heading_de: str
    body_de: str


class Citation(FrozenModel):
    """A claim-to-source link, verifiable by the guard."""

    claim: str
    source_url: str
    verified: bool = False


class Draft(FrozenModel):
    """A complete German blog draft candidate."""

    id: str
    topic_id: str
    batch_id: str = ""
    angle: str = ""
    title_de: str
    body_de: str
    sections: tuple[Section, ...]
    citations: tuple[Citation, ...]
    signals: dict[str, float] = Field(default_factory=dict)
    prompt_version: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("body_de")
    @classmethod
    def _body_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body_de must not be empty")
        return value


class SampleSpec(FrozenModel):
    """Instruction for one parallel sample."""

    index: int
    angle: str
    instruction_de: str
    batch_id: str


class SampleBatch(FrozenModel):
    """Reducer-friendly collection of samples from one generation epoch."""

    batch_id: str
    drafts: tuple[Draft, ...] = Field(default_factory=tuple)


class RankedDraft(FrozenModel):
    """A draft paired with its prediction."""

    draft: Draft
    expected_clicks: float
    expected_impressions: float
    expected_position: float = 0.0
    clicks_ci_low: float
    clicks_ci_high: float
    impressions_ci_low: float
    impressions_ci_high: float
    model_version: str
    qualified: bool = True


class Direction(FrozenModel):
    """Structured editorial direction for one topic."""

    title_de: str = Field(min_length=3)
    angle: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    key_points: tuple[str, ...] = Field(min_length=1)
    compliance_hooks: tuple[str, ...] = ()


class ArticleResponse(FrozenModel):
    """Structured article payload returned by generation and refinement."""

    title_de: str
    sections: tuple[Section, ...]
    citations: tuple[Citation, ...]
    signals: dict[str, float] = Field(default_factory=dict)
