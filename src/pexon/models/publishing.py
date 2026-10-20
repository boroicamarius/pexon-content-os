"""Technical SEO and publishing value objects."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from pexon.models.base import FrozenModel


class InternalLink(FrozenModel):
    """A related internal article link."""

    title: str
    url: str


class SeoMetadata(FrozenModel):
    """Canonical metadata and JSON-LD for a published article."""

    canonical_url: str
    meta_description: str
    keywords: tuple[str, ...] = ()
    json_ld: dict[str, object] = Field(default_factory=dict)
    internal_links: tuple[InternalLink, ...] = ()


class PublishRequest(FrozenModel):
    """Provider-neutral request to publish one article."""

    article_id: str
    title: str
    body_md: str
    slug: str
    canonical_url: str
    frontmatter: dict[str, object]
    status: str = "publish"


class PublishResult(FrozenModel):
    """Result of one publishing adapter call."""

    provider: str
    external_id: str = ""
    url: str = ""
    local_path: str = ""
    status: str = ""
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewDecision(FrozenModel):
    """Human review recorded against a staged article."""

    article_id: str
    reviewer: str
    decision: str
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
