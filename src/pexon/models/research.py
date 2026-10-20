"""Research, competitor and insight value objects."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from pexon.models.base import FrozenModel


class Source(FrozenModel):
    """One fetched or searched source."""

    url: str
    title: str = ""
    snippet: str = ""
    content: str = ""
    fetched_at: datetime | None = None
    provider: str = ""
    status: str = "search"


class Fact(FrozenModel):
    """A claim extracted from one source and verified by the judge."""

    id: str
    claim_de: str
    source_url: str
    quote_de: str = ""
    verified: bool = False
    evidence_de: str = ""
    confidence: float = 0.0


class ResearchSnapshot(FrozenModel):
    """Frozen topic ground truth shared by every downstream frame."""

    topic_id: str
    sources: tuple[Source, ...]
    facts: tuple[Fact, ...]
    references: tuple[str, ...]
    snapshot_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FetchedPage(FrozenModel):
    """Raw page returned by a fetch adapter."""

    url: str
    title: str
    content: str
    status_code: int
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_type: str = ""
    truncated: bool = False


class PageFeatures(FrozenModel):
    """Normalised page-level features used by ranking and the learner."""

    seo: float = Field(ge=0.0, le=1.0)
    geo: float = Field(ge=0.0, le=1.0)
    aeo: float = Field(ge=0.0, le=1.0)
    entity_coverage: float = Field(ge=0.0, le=1.0)
    answer_first: float = Field(ge=0.0, le=1.0)
    source_authority: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)

    def as_dict(self) -> dict[str, float]:
        """Return a stable feature vector."""
        return self.model_dump()


class CompetitorPage(FrozenModel):
    """A deduplicated competitor or generative-engine answer."""

    id: str
    url: str
    title: str
    provider: str
    content: str
    features: PageFeatures | None = None
    duplicate_of: str | None = None


class InsightSet(FrozenModel):
    """German insights extracted from the strongest competitor profile."""

    insights_de: tuple[str, ...]
    actions_de: tuple[str, ...]
    top_competitor_url: str = ""


class ExtractedFact(FrozenModel):
    """Fact payload as returned by the extraction LLM."""

    claim_de: str
    source_url: str
    quote_de: str


class ExtractionResult(FrozenModel):
    """Validated research extraction payload."""

    facts: tuple[ExtractedFact, ...]
    references: tuple[str, ...]
    summary_de: str


class EngineAnswer(FrozenModel):
    """Simulated generative-engine answer, produced by a real LLM call."""

    answer_de: str
    key_entities: tuple[str, ...]
    source_notes_de: tuple[str, ...]


class PageRankResponse(FrozenModel):
    """Flat page ranking payload returned by the judge-style ranking prompt."""

    seo: float = Field(ge=0.0, le=1.0)
    geo: float = Field(ge=0.0, le=1.0)
    aeo: float = Field(ge=0.0, le=1.0)
    entity_coverage: float = Field(ge=0.0, le=1.0)
    answer_first: float = Field(ge=0.0, le=1.0)
    source_authority: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    evidence_de: str = ""

    def to_features(self) -> PageFeatures:
        """Drop evidence and return the shared vector."""
        return PageFeatures(
            **{
                key: getattr(self, key)
                for key in (
                    "seo",
                    "geo",
                    "aeo",
                    "entity_coverage",
                    "answer_first",
                    "source_authority",
                    "freshness",
                )
            }
        )
