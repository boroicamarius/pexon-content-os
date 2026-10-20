"""Top-level graph: the CEO's four frames, in order, with audited retries."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from typing import Any

from langgraph.graph import END, START, StateGraph

from pexon.config.settings import Settings
from pexon.graph.checkpoint import make_checkpointer
from pexon.graph.state import PexonState
from pexon.graph.subgraphs.generation_subgraph import build_generation_subgraph
from pexon.graph.subgraphs.intelligence_subgraph import build_intelligence_subgraph
from pexon.graph.subgraphs.reflection_subgraph import build_reflection_subgraph
from pexon.graph.subgraphs.research_subgraph import build_research_subgraph
from pexon.models.draft import SampleBatch
from pexon.models.topic import Topic
from pexon.observability.metrics import MetricsCollector
from pexon.ports.tracing import TracingPort
from pexon.services.attribution import AttributionService
from pexon.services.audit import AuditLog
from pexon.services.generation_service import GenerationService
from pexon.services.geo import GeoService
from pexon.services.intelligence_service import IntelligenceService
from pexon.services.reflection_service import ReflectionService
from pexon.services.research_service import ResearchService

logger = logging.getLogger(__name__)


class PexonGraph:
    """Compiles and runs the four-frame LangGraph workflow."""

    def __init__(
        self,
        settings: Settings,
        research: ResearchService,
        intelligence: IntelligenceService,
        generation: GenerationService,
        reflection: ReflectionService,
        audit: AuditLog,
        metrics: MetricsCollector,
        tracing: TracingPort,
        geo: GeoService,
        attribution: AttributionService,
    ) -> None:
        self._settings = settings
        self._research = research
        self._intelligence = intelligence
        self._generation = generation
        self._reflection = reflection
        self._audit = audit
        self._metrics = metrics
        self._tracing = tracing
        self._geo = geo
        self._attribution = attribution
        self.graph = self._build()

    def _build(self):
        builder = StateGraph(PexonState)
        research = build_research_subgraph(self._research)
        intelligence = build_intelligence_subgraph(self._intelligence)
        generation = build_generation_subgraph(self._generation)
        reflection = build_reflection_subgraph(self._reflection)

        def traced(name: str, function):
            def wrapped(state: PexonState) -> dict:
                topic = state.get("topic")
                with self._tracing.span(
                    name, run_id=state["run_id"], inputs={"topic": topic.name_de if topic else ""}
                ):
                    if hasattr(function, "invoke"):
                        return function.invoke(state)
                    return function(state)

            return wrapped

        def retry(state: PexonState) -> dict:
            retries = int(state.get("retries", 0)) + 1
            self._metrics.inc("retry_count")
            self._audit.emit(
                state["run_id"],
                "generation_retry",
                {
                    "attempt": retries,
                    "reasons": list(state.get("retry_reasons", ())),
                },
            )
            return {"retries": retries, "decision": "retry", "samples": SampleBatch(batch_id="")}

        def publish(state: PexonState) -> dict:
            article_id, path, status = self._reflection.review_and_publish(
                state["draft"],
                state["prediction"],
                state["topic"],
                state["snapshot"],
                state["run_id"],
            )
            return {"article_id": article_id, "article_path": path, "decision": status}

        def measure(state: PexonState) -> dict:
            bundle = self._reflection.collect_metrics(
                state["article_id"], state["run_id"], state.get("wait_seconds", 0)
            )
            return {"performance": bundle, "pending_measure": bundle is None}

        def report(state: PexonState) -> dict:
            topic = state["topic"]
            geo_report = self._geo.measure_topic(
                topic.id, topic.name_de, state["run_id"], state.get("article_id")
            )
            try:
                funnel = self._attribution.build_report(state["run_id"])
            except Exception as exc:
                self._audit.emit(state["run_id"], "funnel_report_failed", {"error": str(exc)})
                funnel = None
            return {"geo_report": geo_report, "funnel_report": funnel}

        def failed(state: PexonState) -> dict:
            self._audit.emit(
                state["run_id"],
                "run_failed",
                {
                    "reasons": list(state.get("retry_reasons", ())),
                    "retries": state.get("retries", 0),
                },
            )
            return {
                "decision": "failed",
                "errors": ["quality gate failed after retries"],
            }

        builder.add_node("research", traced("Research", research))
        builder.add_node("intelligence", traced("Intelligence", intelligence))
        builder.add_node("generation", traced("Generation", generation))
        builder.add_node("retry_direction", traced("GenerationRetry", retry))
        builder.add_node("publish", traced("ReflectionPublish", publish))
        builder.add_node("measure", traced("ReflectionMeasure", measure))
        builder.add_node("reflection", traced("Reflection", reflection))
        builder.add_node("report", traced("MeasurementReport", report))
        builder.add_node("failed", failed)
        builder.add_edge(START, "research")
        builder.add_edge("research", "intelligence")
        builder.add_edge("intelligence", "generation")
        builder.add_conditional_edges(
            "generation",
            self._after_generation,
            {
                "publish": "publish",
                "retry": "retry_direction",
                "failed": "failed",
            },
        )
        builder.add_edge("retry_direction", "generation")
        builder.add_conditional_edges(
            "publish",
            self._after_publish,
            {
                "measure": "measure",
                "reflection": "reflection",
                "end": END,
            },
        )
        builder.add_edge("measure", "reflection")
        builder.add_edge("reflection", "report")
        builder.add_edge("report", END)
        builder.add_edge("failed", END)
        return builder.compile(
            checkpointer=make_checkpointer(self._settings.sqlite_path), name="pexon"
        )

    def _after_generation(self, state: PexonState) -> str:
        if state.get("decision") == "publish":
            return "publish"
        if int(state.get("retries", 0)) < self._settings.max_retries:
            return "retry"
        return "failed"

    def _after_publish(self, state: PexonState) -> str:
        if state.get("decision") in {"pending_review", "draft", "future"}:
            return "end"
        return "measure" if int(state.get("wait_seconds", 0)) > 0 else "reflection"

    def initial_state(
        self, topic: Topic, *, wait_seconds: int = 0, max_iterations: int | None = None
    ) -> PexonState:
        """Create the run state for one topic."""
        run_id = f"run-{uuid.uuid4().hex}"
        return {
            "run_id": run_id,
            "trace_id": uuid.uuid4().hex,
            "topic": topic,
            "wait_seconds": wait_seconds,
            "max_iterations": self._settings.max_iterations
            if max_iterations is None
            else max_iterations,
            "retries": 0,
            "iterations": 0,
            "decision": "",
            "retry_reasons": (),
            "errors": [],
            "provider_config": self._settings.provider_config,
            "samples": SampleBatch(batch_id=""),
        }

    def config(self, run_id: str) -> dict[str, Any]:
        """LangGraph config for a run/thread."""
        return {
            "configurable": {"thread_id": run_id},
            "recursion_limit": self._settings.recursion_limit,
        }

    def stream(self, state: PexonState) -> Iterator[dict[str, Any]]:
        """Stream node updates for one run."""
        return self.graph.stream(
            state, self.config(state["run_id"]), stream_mode=self._settings.stream_mode
        )

    def replay(self, run_id: str) -> Iterator[dict[str, Any]]:
        """Resume a thread; completed nodes are not executed again."""
        config = self.config(run_id)
        snapshot = self.graph.get_state(config)
        if not snapshot.values:
            raise ValueError(f"unknown run: {run_id}")
        return self.graph.stream(None, config, stream_mode=self._settings.stream_mode)

    def final_state(self, run_id: str) -> dict[str, Any]:
        """Read the latest checkpointed values."""
        snapshot = self.graph.get_state(self.config(run_id))
        return dict(snapshot.values)

    def invoke(self, state: PexonState) -> dict[str, Any]:
        """Run to completion and return the final state."""
        return self.graph.invoke(state, self.config(state["run_id"]))
