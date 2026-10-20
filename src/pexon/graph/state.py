"""Shared LangGraph state."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from pexon.models.draft import Direction, Draft, RankedDraft, SampleBatch, SampleSpec
from pexon.models.funnel import FunnelReport
from pexon.models.gate import GateReport
from pexon.models.geo import GeoReport
from pexon.models.performance import PerformanceBundle
from pexon.models.prediction import Prediction, PromptMutation, Proposal, TrainingReport
from pexon.models.research import CompetitorPage, InsightSet, PageFeatures, ResearchSnapshot, Source
from pexon.models.topic import Topic


def merge_sample_batches(
    left: SampleBatch | dict | None, right: SampleBatch | dict | None
) -> SampleBatch | None:
    """Keep only the newest generation batch and append samples from the same batch."""
    if left is None:
        return (
            right
            if right is None or isinstance(right, SampleBatch)
            else SampleBatch.model_validate(right)
        )
    if right is None:
        return left if isinstance(left, SampleBatch) else SampleBatch.model_validate(left)
    left_batch = left if isinstance(left, SampleBatch) else SampleBatch.model_validate(left)
    right_batch = right if isinstance(right, SampleBatch) else SampleBatch.model_validate(right)
    if left_batch.batch_id != right_batch.batch_id:
        return right_batch
    return SampleBatch(batch_id=left_batch.batch_id, drafts=left_batch.drafts + right_batch.drafts)


class PexonState(TypedDict, total=False):
    """State carried by the four frames."""

    run_id: str
    trace_id: str
    topic: Topic
    sources: list[Source]
    snapshot: ResearchSnapshot
    insights: InsightSet
    competitor_pages: list[CompetitorPage]
    competitor_features: PageFeatures
    weights_version: str
    training_report: TrainingReport
    direction: Direction
    batch_id: str
    spec: SampleSpec
    samples: Annotated[SampleBatch, merge_sample_batches]
    refined: list[Draft]
    ranked: list[RankedDraft]
    gates: GateReport
    draft: Draft
    prediction: Prediction
    article_id: str
    article_path: str
    performance: PerformanceBundle
    retries: int
    iterations: int
    decision: str
    retry_reasons: tuple[str, ...]
    proposal: Proposal
    mutation: PromptMutation
    reflection_update: dict[str, object]
    drift_report: dict[str, object]
    geo_report: GeoReport | None
    funnel_report: FunnelReport | None
    pending_measure: bool
    wait_seconds: int
    max_iterations: int
    provider_config: dict[str, object]
    errors: Annotated[list[str], operator.add]
