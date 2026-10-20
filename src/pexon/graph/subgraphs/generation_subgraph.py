"""Frame 2 subgraph: Generation."""

from __future__ import annotations

import logging
import uuid

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from pexon.graph.state import PexonState
from pexon.models.draft import SampleBatch
from pexon.services.generation_service import GenerationService

logger = logging.getLogger(__name__)


def build_generation_subgraph(service: GenerationService):
    """Direction -> Send fan-out -> rank -> refine -> rank -> remove -> quality gate."""
    builder = StateGraph(PexonState)

    def direction(state: PexonState) -> dict:
        direction_obj = service.direction(
            state["topic"],
            state["snapshot"],
            tuple(state.get("insights").insights_de) if state.get("insights") else (),
            state.get("competitor_features"),
            tuple(state.get("retry_reasons", ())),
            state["run_id"],
        )
        return {"direction": direction_obj}

    def prepare(state: PexonState) -> dict:
        batch_id = f"batch-{uuid.uuid4().hex[:10]}"
        return {"batch_id": batch_id, "samples": SampleBatch(batch_id=batch_id, drafts=())}

    def fan_out(state: PexonState) -> list[Send]:
        specs = service.sample_specs(state["direction"], state["batch_id"])
        return [
            Send(
                "generate_sample",
                {
                    "run_id": state["run_id"],
                    "topic": state["topic"],
                    "snapshot": state["snapshot"],
                    "direction": state["direction"],
                    "spec": spec,
                },
            )
            for spec in specs
        ]

    def generate_sample(payload: PexonState) -> dict:
        try:
            draft = service.generate_sample(
                payload["topic"],
                payload["snapshot"],
                payload["direction"],
                payload["spec"],
                payload["run_id"],
            )
        except Exception as exc:
            service.note_failure(
                payload["run_id"],
                "generate_sample",
                exc,
                {"angle": payload["spec"].angle},
            )
            return {"samples": SampleBatch(batch_id=payload["spec"].batch_id, drafts=())}
        return {"samples": SampleBatch(batch_id=payload["spec"].batch_id, drafts=(draft,))}

    def rank_initial(state: PexonState) -> dict:
        batch = state.get("samples", SampleBatch(batch_id="", drafts=()))
        ranked = service.rank(
            list(batch.drafts),
            state["topic"],
            state["snapshot"],
            state.get("competitor_features"),
        )
        return {"ranked": ranked}

    def refine(state: PexonState) -> dict:
        refined = service.refine(
            state.get("ranked", []),
            state["topic"],
            state["snapshot"],
            state["direction"],
            state.get("competitor_features"),
            state["run_id"],
        )
        return {"refined": refined}

    def rank_second(state: PexonState) -> dict:
        refined = state.get("refined", [])
        refined_source_ids = {draft.id.removesuffix("-r") for draft in refined}
        originals = [
            item.draft
            for item in state.get("ranked", [])
            if item.draft.id not in refined_source_ids
        ]
        ranked = service.rank(
            [*refined, *originals],
            state["topic"],
            state["snapshot"],
            state.get("competitor_features"),
        )
        return {"ranked": ranked}

    def remove_unqualified(state: PexonState) -> dict:
        return {"ranked": service.remove_unqualified(state.get("ranked", []))}

    def quality_gate(state: PexonState) -> dict:
        report, prediction = service.quality_gate(
            state.get("ranked", []), state["topic"], state["snapshot"], state["run_id"]
        )
        candidate = next(
            (item for item in state.get("ranked", []) if item.draft.id == report.candidate_id),
            None,
        )
        return {
            "gates": report,
            "prediction": prediction,
            "draft": candidate.draft if candidate else None,
            "decision": "publish" if report.passed else "retry",
            "retry_reasons": report.reasons,
        }

    builder.add_node("direction", direction)
    builder.add_node("prepare_samples", prepare)
    builder.add_node("generate_sample", generate_sample)
    builder.add_node("rank_initial", rank_initial)
    builder.add_node("refine", refine)
    builder.add_node("rank_second", rank_second)
    builder.add_node("remove_unqualified", remove_unqualified)
    builder.add_node("quality_gate", quality_gate)
    builder.add_edge(START, "direction")
    builder.add_edge("direction", "prepare_samples")
    builder.add_conditional_edges("prepare_samples", fan_out, ["generate_sample"])
    builder.add_edge("generate_sample", "rank_initial")
    builder.add_edge("rank_initial", "refine")
    builder.add_edge("refine", "rank_second")
    builder.add_edge("rank_second", "remove_unqualified")
    builder.add_edge("remove_unqualified", "quality_gate")
    builder.add_edge("quality_gate", END)
    return builder.compile(name="generation")
