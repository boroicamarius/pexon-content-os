"""Select the official SQLite checkpointer when installed, otherwise the local equivalent."""

from __future__ import annotations

import atexit
import inspect
from pathlib import Path
from typing import Any

try:
    from langgraph.checkpoint.sqlite import SqliteSaver as OfficialSqliteSaver

    _HAS_OFFICIAL = True
except ImportError:
    OfficialSqliteSaver = None  # type: ignore[assignment]
    _HAS_OFFICIAL = False

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from pexon.graph.sqlite_saver import SqliteSaver
from pexon.models.cost import CostBreakdown
from pexon.models.draft import (
    ArticleResponse,
    Citation,
    Direction,
    Draft,
    RankedDraft,
    SampleBatch,
    SampleSpec,
    Section,
)
from pexon.models.funnel import AttributionRow, EconomicsReport, FunnelReport
from pexon.models.gate import FactVerdict, GateReport, GateResult, JudgeAssessment
from pexon.models.geo import GeoQueryResult, GeoReport
from pexon.models.performance import Performance, PerformanceBundle
from pexon.models.prediction import Prediction, PromptMutation, Proposal, TrainingReport
from pexon.models.research import (
    CompetitorPage,
    EngineAnswer,
    ExtractedFact,
    ExtractionResult,
    Fact,
    InsightSet,
    PageFeatures,
    PageRankResponse,
    ResearchSnapshot,
    Source,
)
from pexon.models.topic import Topic
from pexon.models.weights import Weights

_ALLOWED_TYPES = (
    ArticleResponse,
    Citation,
    Direction,
    Draft,
    RankedDraft,
    SampleBatch,
    SampleSpec,
    Section,
    FactVerdict,
    GateReport,
    GateResult,
    JudgeAssessment,
    Performance,
    PerformanceBundle,
    Prediction,
    PromptMutation,
    Proposal,
    TrainingReport,
    CostBreakdown,
    AttributionRow,
    EconomicsReport,
    FunnelReport,
    GeoQueryResult,
    GeoReport,
    CompetitorPage,
    EngineAnswer,
    ExtractedFact,
    ExtractionResult,
    Fact,
    InsightSet,
    PageFeatures,
    PageRankResponse,
    ResearchSnapshot,
    Source,
    Topic,
    Weights,
)


def _serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=list(_ALLOWED_TYPES))


def make_checkpointer(path: Path) -> Any:
    """Build a persistent checkpointer with a stable public API."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serde = _serde()
    if _HAS_OFFICIAL and OfficialSqliteSaver is not None:
        parameters = inspect.signature(OfficialSqliteSaver.from_conn_string).parameters
        checkpointer = (
            OfficialSqliteSaver.from_conn_string(str(path), serde=serde)
            if "serde" in parameters
            else OfficialSqliteSaver.from_conn_string(str(path))
        )
        if hasattr(checkpointer, "__enter__"):
            checkpointer = checkpointer.__enter__()
            atexit.register(lambda: checkpointer.__exit__(None, None, None))
        return checkpointer
    return SqliteSaver.from_conn_string(str(path), serde=serde)
