"""Topic value objects."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from pexon.models.base import FrozenModel


class Topic(FrozenModel):
    """A German banking AI topic and its research queries."""

    id: str
    name_de: str
    queries: tuple[str, ...] = Field(default_factory=tuple)
    bank_segment: str = "universalbank"
    target_keyword: str = ""
    cluster: str = ""
    funnel_stage: str = "middle"

    @classmethod
    def from_name(
        cls,
        name: str,
        *,
        bank_segment: str = "universalbank",
        target_keyword: str = "",
        cluster: str = "",
        funnel_stage: str = "middle",
    ) -> Topic:
        """Build a topic from a free-text name without inventing research queries."""
        slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
        return cls(
            id=f"topic-{slug[:48]}",
            name_de=name,
            bank_segment=bank_segment,
            target_keyword=target_keyword,
            cluster=cluster,
            funnel_stage=funnel_stage,
        )


class TopicRun(FrozenModel):
    """A topic bound to one pipeline execution."""

    topic: Topic
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
