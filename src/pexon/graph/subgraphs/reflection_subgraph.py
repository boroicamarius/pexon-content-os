"""Frame 4 subgraph: Reflection."""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from pexon.graph.state import PexonState
from pexon.services.reflection_service import ReflectionService

logger = logging.getLogger(__name__)


def build_reflection_subgraph(service: ReflectionService):
    """Collect -> propose -> mutate -> update, looping up to MAX_ITERATIONS."""
    builder = StateGraph(PexonState)

    def collect(state: PexonState) -> dict:
        if state.get("performance") is not None:
            return {}
        if state.get("pending_measure"):
            return {}
        bundle = service.collect_metrics(state["article_id"], state["run_id"], wait_seconds=0)
        return {"performance": bundle, "pending_measure": bundle is None}

    def propose(state: PexonState) -> dict:
        performance = state.get("performance")
        prediction = state.get("prediction")
        if performance is None or prediction is None:
            return {"proposal": None}
        proposal = service.propose_changes(
            prediction, performance, state["run_id"], state["article_id"]
        )
        return {"proposal": proposal}

    def route_proposal(state: PexonState) -> str:
        return "generate_variant" if state.get("proposal") else END

    def mutate(state: PexonState) -> dict:
        mutation = service.mutate_prompt(state["proposal"], state["run_id"])
        return {"mutation": mutation}

    def route_mutation(state: PexonState) -> str:
        return "update" if state.get("mutation") else END

    def update(state: PexonState) -> dict:
        result = service.update(state.get("mutation"), state["run_id"])
        iterations = int(state.get("iterations", 0)) + 1
        return {"reflection_update": result, "iterations": iterations}

    def route_update(state: PexonState) -> str:
        if int(state.get("iterations", 0)) < int(state.get("max_iterations", 0)):
            if state.get("performance") is not None and state.get("proposal") is not None:
                return "propose_changes"
        return END

    builder.add_node("collect_metrics", collect)
    builder.add_node("propose_changes", propose)
    builder.add_node("generate_variant", mutate)
    builder.add_node("update", update)
    builder.add_edge(START, "collect_metrics")
    builder.add_conditional_edges(
        "collect_metrics",
        lambda state: END if state.get("pending_measure") else "propose_changes",
        ["propose_changes", END],
    )
    builder.add_conditional_edges("propose_changes", route_proposal, ["generate_variant", END])
    builder.add_conditional_edges("generate_variant", route_mutation, ["update", END])
    builder.add_conditional_edges("update", route_update, ["propose_changes", END])
    return builder.compile(name="reflection")
