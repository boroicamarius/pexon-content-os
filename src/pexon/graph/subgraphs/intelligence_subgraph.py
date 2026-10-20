"""Frame 3 subgraph: Intelligence."""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from pexon.graph.state import PexonState
from pexon.services.intelligence_service import IntelligenceService

logger = logging.getLogger(__name__)


def build_intelligence_subgraph(service: IntelligenceService):
    """Providers -> aggregate -> rank pages -> importance -> insights -> drift."""
    builder = StateGraph(PexonState)

    def call_providers(state: PexonState) -> dict:
        pages = service.call_providers(state["topic"], state["run_id"])
        return {"competitor_pages": pages}

    def aggregate(state: PexonState) -> dict:
        pages = service.aggregate(state.get("competitor_pages", []), state["run_id"])
        return {"competitor_pages": pages}

    def rank_pages(state: PexonState) -> dict:
        pages = service.rank_pages(
            state.get("competitor_pages", []), state["topic"], state["run_id"]
        )
        top = service.top_page(pages)
        return {
            "competitor_pages": pages,
            "competitor_features": top.features if top else None,
        }

    def modify_importance(state: PexonState) -> dict:
        report = service.modify_importance(state["run_id"])
        return {"training_report": report, "weights_version": report.version}

    def extract_insights(state: PexonState) -> dict:
        insights = service.extract_insights(
            state["topic"], state.get("competitor_pages", []), state["run_id"]
        )
        return {"insights": insights}

    def drift(state: PexonState) -> dict:
        report = service.check_drift(state["run_id"])
        return {"drift_report": report}

    builder.add_node("call_providers", call_providers)
    builder.add_node("aggregate_results", aggregate)
    builder.add_node("rank_each_page", rank_pages)
    builder.add_node("modify_importance", modify_importance)
    builder.add_node("extract_insights", extract_insights)
    builder.add_node("drift_detection", drift)
    builder.add_edge(START, "call_providers")
    builder.add_edge("call_providers", "aggregate_results")
    builder.add_edge("aggregate_results", "rank_each_page")
    builder.add_edge("rank_each_page", "modify_importance")
    builder.add_edge("modify_importance", "extract_insights")
    builder.add_edge("extract_insights", "drift_detection")
    builder.add_edge("drift_detection", END)
    return builder.compile(name="intelligence")
