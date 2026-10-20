"""Frame 1 subgraph: Research."""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from pexon.graph.state import PexonState
from pexon.services.research_service import ResearchService

logger = logging.getLogger(__name__)


def build_research_subgraph(service: ResearchService):
    """Deep research -> fetch/extract -> verified topic ground truth."""
    builder = StateGraph(PexonState)

    def deep_research(state: PexonState) -> dict:
        sources = service.deep_research(state["topic"], state["run_id"])
        return {"sources": sources}

    def fetch_and_extract(state: PexonState) -> dict:
        sources = service.fetch_sources(state.get("sources", []), state["run_id"])
        return {"sources": sources}

    def ground_truth(state: PexonState) -> dict:
        snapshot = service.extract_ground_truth(
            state["topic"], state.get("sources", []), state["run_id"]
        )
        return {"snapshot": snapshot}

    builder.add_node("deep_research", deep_research)
    builder.add_node("fetch_and_extract", fetch_and_extract)
    builder.add_node("aggregate_extract_references", ground_truth)
    builder.add_edge(START, "deep_research")
    builder.add_edge("deep_research", "fetch_and_extract")
    builder.add_edge("fetch_and_extract", "aggregate_extract_references")
    builder.add_edge("aggregate_extract_references", END)
    return builder.compile(name="research")
