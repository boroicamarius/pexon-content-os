"""Frame 2: directional generation, ranking, refinement and the quality gate."""

from __future__ import annotations

import logging
import math
import uuid
from typing import Any

from pexon.config.prompts import (
    DEFAULT_STYLE_DE,
    DIRECTION_SYSTEM,
    DIRECTION_USER,
    JUDGE_SYSTEM,
    JUDGE_USER,
    PROMPT_VERSIONS,
    REFINE_SYSTEM,
    REFINE_USER,
    SECTION_SYSTEM,
    SECTION_USER,
)
from pexon.config.settings import Settings
from pexon.guards.language import detect_german
from pexon.models.draft import (
    ArticleResponse,
    Citation,
    Direction,
    Draft,
    RankedDraft,
    SampleSpec,
)
from pexon.models.gate import GateReport, GateResult, JudgeAssessment
from pexon.models.prediction import Prediction
from pexon.models.research import PageFeatures, ResearchSnapshot
from pexon.models.topic import Topic
from pexon.observability.metrics import MetricsCollector
from pexon.ports.embeddings import EmbeddingsPort
from pexon.ports.storage import StoragePort
from pexon.services.audit import AuditLog
from pexon.services.features import FeatureExtractor
from pexon.services.gateway import LLMGateway
from pexon.services.predictor import Predictor

logger = logging.getLogger(__name__)


class GenerationService:
    """One service for the complete Generation frame."""

    def __init__(
        self,
        settings: Settings,
        generator: LLMGateway,
        judge: LLMGateway,
        embeddings: EmbeddingsPort,
        predictor: Predictor,
        features: FeatureExtractor,
        storage: StoragePort,
        audit: AuditLog,
        metrics: MetricsCollector,
    ) -> None:
        self._settings = settings
        self._generator = generator
        self._judge = judge
        self._embeddings = embeddings
        self._predictor = predictor
        self._features = features
        self._storage = storage
        self._audit = audit
        self._metrics = metrics

    def direction(
        self,
        topic: Topic,
        snapshot: ResearchSnapshot,
        insights: tuple[str, ...],
        competitor: PageFeatures | None,
        retry_reasons: tuple[str, ...],
        run_id: str,
    ) -> Direction:
        """Generate the German title and editorial direction."""
        values = {
            "topic": topic.name_de,
            "segment": topic.bank_segment,
            "facts": self._facts_text(snapshot),
            "insights": "; ".join(insights) or "keine",
            "competitor_features": competitor.as_dict() if competitor else {},
            "retry_reasons": "; ".join(retry_reasons) or "keine",
            "variant": self._variant_text("direction"),
            "max_key_points": self._settings.direction_key_points,
        }
        prompt = self._render("direction", DIRECTION_USER, values, run_id)
        direction = self._generator.structured(
            DIRECTION_SYSTEM,
            prompt,
            Direction,
            max_tokens=self._settings.llm_max_tokens,
        )
        assert isinstance(direction, Direction)
        self._audit.emit(
            run_id,
            "direction_generated",
            {
                "title": direction.title_de,
                "angle": direction.angle,
                "retry_reasons": list(retry_reasons),
            },
        )
        return direction

    def note_failure(
        self, run_id: str, stage: str, error: Exception, extra: dict[str, Any] | None = None
    ) -> None:
        """Record a non-fatal generation failure."""
        payload = {"stage": stage, "error": str(error), **(extra or {})}
        self._audit.emit(run_id, "generation_failure", payload)

    def sample_specs(self, direction: Direction, batch_id: str) -> list[SampleSpec]:
        """Create one distinct German angle per parallel sample."""
        angles = [a.strip() for a in self._settings.gen_angles.split(",") if a.strip()]
        angles = (angles or ["direkt"])[: self._settings.gen_sample_count]
        while len(angles) < self._settings.gen_sample_count:
            angles.append(angles[len(angles) % len(angles or ["direkt"])])
        instructions = {
            "direkt": "Antworte im ersten Absatz direkt auf die Leserfrage und bleibe nüchtern.",
            "deep": "Gehe tief auf Architektur, Datenflüsse und Governance-Mechanismen ein.",
            "compliance": "Stelle DSGVO, DORA, MaRisk und AI Act in den Mittelpunkt.",
            "management": "Schreibe für Vorstand und Bereichsleitung: Entscheidungen, Risiken, Kosten.",
            "praxis": "Zeige konkrete Umsetzungsschritte für eine deutsche Bank.",
        }
        return [
            SampleSpec(
                index=index,
                angle=angle,
                instruction_de=instructions.get(
                    angle, f"Schreibe den Artikel aus der Perspektive {angle}."
                ),
                batch_id=batch_id,
            )
            for index, angle in enumerate(angles)
        ]

    def generate_sample(
        self,
        topic: Topic,
        snapshot: ResearchSnapshot,
        direction: Direction,
        spec: SampleSpec,
        run_id: str,
    ) -> Draft:
        """Generate one complete German draft for a sample angle."""
        values = {
            "topic": topic.name_de,
            "direction": direction.title_de,
            "angle": spec.instruction_de,
            "audience": direction.target_audience,
            "key_points": "; ".join(direction.key_points),
            "facts": self._facts_text(snapshot),
            "variant": self._variant_text("section"),
            "target_words": self._settings.draft_target_words,
            "max_words": self._settings.draft_max_words,
        }
        prompt = self._render("section", SECTION_USER, values, run_id)
        response = self._generator.structured(
            SECTION_SYSTEM,
            prompt,
            ArticleResponse,
            max_tokens=self._settings.draft_max_tokens,
        )
        assert isinstance(response, ArticleResponse)
        draft = self._draft_from_response(topic, response, spec, snapshot, run_id)
        self._audit.emit(
            run_id,
            "sample_generated",
            {
                "draft_id": draft.id,
                "angle": spec.angle,
                "words": len(draft.body_de.split()),
            },
        )
        return draft

    def _draft_from_response(
        self,
        topic: Topic,
        response: ArticleResponse,
        spec: SampleSpec,
        snapshot: ResearchSnapshot,
        run_id: str,
    ) -> Draft:
        body = "\n\n".join(
            f"## {section.heading_de.strip()}\n\n{section.body_de.strip()}"
            for section in response.sections
        ).strip()
        citations = self._verify_citations(response.citations, snapshot, run_id)
        if not citations:
            citations = tuple(Citation(claim="", source_url="", verified=False) for _ in range(0))
        signals = dict(response.signals)
        signals.update(
            {
                "word_count": float(len(body.split())),
                "section_count": float(len(response.sections)),
                "citation_count": float(len(citations)),
            }
        )
        return Draft(
            id=f"draft-{uuid.uuid4().hex[:12]}",
            topic_id=topic.id,
            batch_id=spec.batch_id,
            angle=spec.angle,
            title_de=response.title_de.strip(),
            body_de=body,
            sections=response.sections,
            citations=citations,
            signals=signals,
            prompt_version=f"direction:{PROMPT_VERSIONS['direction']}|section:{PROMPT_VERSIONS['section']}",
        )

    def _verify_citations(
        self, citations: tuple[Citation, ...], snapshot: ResearchSnapshot, run_id: str
    ) -> tuple[Citation, ...]:
        if not citations:
            return ()
        facts = [fact for fact in snapshot.facts if fact.verified]
        if not facts:
            return tuple(citation.model_copy(update={"verified": False}) for citation in citations)
        texts = [citation.claim for citation in citations] + [fact.claim_de for fact in facts]
        try:
            vectors = self._embeddings.embed(texts)
        except Exception as exc:
            self._audit.emit(run_id, "citation_check_failed", {"error": str(exc)})
            return tuple(citation.model_copy(update={"verified": False}) for citation in citations)
        verified: list[Citation] = []
        for index, citation in enumerate(citations):
            citation_vector = vectors[index]
            best = 0.0
            for fact_index, fact in enumerate(facts):
                if citation.source_url and citation.source_url != fact.source_url:
                    continue
                best = max(best, _cosine(citation_vector, vectors[len(citations) + fact_index]))
            verified.append(
                citation.model_copy(
                    update={"verified": best >= self._settings.citation_verify_threshold}
                )
            )
        return tuple(verified)

    def rank(
        self,
        drafts: list[Draft],
        topic: Topic,
        snapshot: ResearchSnapshot,
        competitor: PageFeatures | None,
    ) -> list[RankedDraft]:
        """Predict both targets for every sample and attach calibrated bounds."""
        ranked: list[RankedDraft] = []
        for draft in drafts:
            features = self._features.draft_features(draft, topic, snapshot)
            vector = self._features.vector(features, draft)
            prediction = self._predictor.predict(vector)
            qualified = (
                prediction.clicks_ci_low >= self._settings.baseline_clicks
                and prediction.impressions_ci_low >= self._settings.baseline_impressions
            )
            ranked.append(
                RankedDraft(
                    draft=draft,
                    expected_clicks=prediction.expected_clicks,
                    expected_impressions=prediction.expected_impressions,
                    expected_position=prediction.expected_position,
                    clicks_ci_low=prediction.clicks_ci_low,
                    clicks_ci_high=prediction.clicks_ci_high,
                    impressions_ci_low=prediction.impressions_ci_low,
                    impressions_ci_high=prediction.impressions_ci_high,
                    model_version=prediction.model_version,
                    qualified=qualified,
                )
            )
        return sorted(ranked, key=lambda item: item.expected_clicks, reverse=True)

    def refine(
        self,
        ranked: list[RankedDraft],
        topic: Topic,
        snapshot: ResearchSnapshot,
        direction: Direction,
        competitor: PageFeatures | None,
        run_id: str,
    ) -> list[Draft]:
        """Refine the strongest samples using feature gaps against the top competitor."""
        refined: list[Draft] = []
        for item in ranked[: self._settings.gen_refine_top_k]:
            own = self._features.draft_features(item.draft, topic, snapshot)
            raw_gaps = self._features.gaps(own, competitor)
            importances = self._predictor.feature_importances()
            gaps = {
                key: round(value * importances.get(key, 1.0), 4) for key, value in raw_gaps.items()
            }
            prompt = REFINE_USER.format(
                draft=item.draft.body_de[: self._settings.judge_body_max_chars],
                gaps=gaps,
                facts=self._facts_text(snapshot),
            )
            try:
                response = self._generator.structured(
                    REFINE_SYSTEM,
                    prompt,
                    ArticleResponse,
                    max_tokens=self._settings.draft_max_tokens,
                )
                assert isinstance(response, ArticleResponse)
                spec = SampleSpec(
                    index=0,
                    angle=f"{item.draft.angle}-refined",
                    instruction_de="Ranking-Refinement",
                    batch_id=item.draft.batch_id,
                )
                refined_draft = self._draft_from_response(topic, response, spec, snapshot, run_id)
                refined_draft = refined_draft.model_copy(update={"id": f"{item.draft.id}-r"})
                refined.append(refined_draft)
                self._audit.emit(
                    run_id,
                    "sample_refined",
                    {
                        "draft_id": item.draft.id,
                        "gaps": gaps,
                    },
                )
            except Exception as exc:
                self._audit.emit(
                    run_id,
                    "refine_failed",
                    {
                        "draft_id": item.draft.id,
                        "error": str(exc),
                    },
                )
        refined_ids = {draft.id.removesuffix("-r") for draft in refined}
        return [*refined, *(item.draft for item in ranked if item.draft.id not in refined_ids)]

    def remove_unqualified(self, ranked: list[RankedDraft]) -> list[RankedDraft]:
        """Keep samples whose lower confidence bound clears both baselines."""
        return [item for item in ranked if item.qualified]

    def quality_gate(
        self, ranked: list[RankedDraft], topic: Topic, snapshot: ResearchSnapshot, run_id: str
    ) -> tuple[GateReport, Prediction | None]:
        """Two-pass deterministic and judge gate over the best qualified candidate."""
        candidate = next((item for item in ranked if item.qualified), ranked[0] if ranked else None)
        if candidate is None:
            report = GateReport(
                passed=False,
                results=(GateResult(name="candidate", passed=False, reason="keine Entwürfe"),),
                candidate_id="",
                reasons=("kein Kandidat",),
            )
            self._metrics.inc("gate_failures", {"gate": "candidate"})
            return report, None
        draft = candidate.draft
        results: list[GateResult] = []
        language = detect_german(
            f"{draft.title_de}\n{draft.body_de}",
            self._settings.german_min_score,
            self._settings.german_stopword_multiplier,
            self._settings.german_umlaut_bonus_cap,
            self._settings.german_sample_chars,
        )
        results.append(
            GateResult(
                name="lang",
                passed=language.german,
                reason="" if language.german else "Text ist nicht sicher deutsch",
                evidence={"language": language.language, "confidence": language.confidence},
            )
        )
        citations = draft.citations
        verified = sum(1 for c in citations if c.verified)
        coverage = verified / max(len(citations), 1)
        citation_ok = (
            verified >= self._settings.min_citations
            and coverage >= self._settings.citation_coverage_min
        )
        results.append(
            GateResult(
                name="citation",
                passed=citation_ok,
                reason="" if citation_ok else "zu wenige verifizierte Belege",
                evidence={
                    "verified": verified,
                    "total": len(citations),
                    "coverage": round(coverage, 4),
                },
            )
        )
        matches = [
            term
            for term in self._settings.compliance_terms
            if term.lower() in draft.body_de.lower()
        ]
        compliance_ok = len(matches) >= self._settings.compliance_min_matches
        results.append(
            GateResult(
                name="compliance",
                passed=compliance_ok,
                reason="" if compliance_ok else "Regulierungsbegriffe fehlen",
                evidence={"matches": ", ".join(matches), "count": len(matches)},
            )
        )
        max_similarity, closest = self._duplicate_similarity(draft, run_id)
        duplicate_ok = max_similarity <= self._settings.dup_sim_threshold
        results.append(
            GateResult(
                name="duplicate",
                passed=duplicate_ok,
                reason="" if duplicate_ok else f"zu ähnlich zu {closest}",
                evidence={"max_similarity": round(max_similarity, 4), "closest": closest},
            )
        )
        word_count = len(draft.body_de.split())
        length_ok = word_count >= self._settings.min_article_words
        results.append(
            GateResult(
                name="length",
                passed=length_ok,
                reason="" if length_ok else "Artikel zu kurz",
                evidence={"words": word_count, "minimum": self._settings.min_article_words},
            )
        )
        judge = self._judge_assessment(draft, snapshot, run_id)
        if judge is not None:
            thresholds = {
                "judge_factuality": (judge.factuality.score, self._settings.judge_factuality_min),
                "judge_compliance": (judge.compliance.score, self._settings.judge_compliance_min),
                "judge_fluency": (judge.german_fluency.score, self._settings.judge_fluency_min),
            }
            for name, (score, minimum) in thresholds.items():
                results.append(
                    GateResult(
                        name=name,
                        passed=score >= minimum,
                        reason="" if score >= minimum else f"{name} unter Schwelle",
                        evidence={"score": score, "minimum": minimum},
                    )
                )
        else:
            results.append(
                GateResult(name="judge", passed=False, reason="Richter nicht erreichbar")
            )
        failed = [result for result in results if not result.passed]
        report = GateReport(
            passed=not failed,
            results=tuple(results),
            candidate_id=draft.id,
            reasons=tuple(result.name for result in failed),
        )
        self._audit.emit(
            run_id,
            "quality_gate",
            {
                "candidate": draft.id,
                "passed": report.passed,
                "reasons": list(report.reasons),
                "results": [result.model_dump(mode="json") for result in results],
            },
        )
        if not report.passed:
            for result in failed:
                self._metrics.inc("gate_failures", {"gate": result.name})
        return report, candidate_prediction(candidate)

    def _judge_assessment(
        self, draft: Draft, snapshot: ResearchSnapshot, run_id: str
    ) -> JudgeAssessment | None:
        prompt = JUDGE_USER.format(
            title=draft.title_de,
            body=draft.body_de[: self._settings.judge_body_max_chars],
            facts=self._facts_text(snapshot),
        )
        try:
            assessment = self._judge.structured(
                JUDGE_SYSTEM,
                prompt,
                JudgeAssessment,
                max_tokens=self._settings.judge_llm_max_tokens,
            )
            assert isinstance(assessment, JudgeAssessment)
            return assessment
        except Exception as exc:
            self._audit.emit(run_id, "judge_failed", {"error": str(exc)})
            return None

    def _duplicate_similarity(self, draft: Draft) -> tuple[float, str]:
        articles = self._storage.find(
            "articles",
            limit=self._settings.duplicate_corpus_limit,
            order_by="created_at",
            desc=True,
        )
        if not articles:
            return 0.0, ""
        try:
            vectors = self._embeddings.embed([draft.body_de, *[a["body_md"] for a in articles]])
        except Exception:
            return 0.0, ""
        max_similarity, closest = 0.0, ""
        for index, article in enumerate(articles, start=1):
            similarity = _cosine(vectors[0], vectors[index])
            if similarity > max_similarity:
                max_similarity, closest = similarity, article["id"]
        return max_similarity, closest

    def _facts_text(self, snapshot: ResearchSnapshot) -> str:
        lines = [
            f"- {fact.claim_de} (Quelle: {fact.source_url})"
            for fact in snapshot.facts
            if fact.verified
        ]
        return "\n".join(lines) or "- keine verifizierten Fakten"

    def _variant_text(self, name: str) -> str:
        row = self._latest_variant(name)
        if row:
            return f"Aktive Prompt-Variante v{row.get('version')}; {DEFAULT_STYLE_DE}"
        return DEFAULT_STYLE_DE

    def _latest_variant(self, name: str) -> dict[str, Any] | None:
        return self._storage.latest("prompt_variants", name=name)

    def _render(self, name: str, default: str, values: dict[str, Any], run_id: str) -> str:
        row = self._latest_variant(name)
        if not row:
            return default.format(**values)
        try:
            return str(row["template_de"]).format(**values)
        except Exception as exc:
            self._audit.emit(
                run_id,
                "prompt_variant_invalid",
                {
                    "name": name,
                    "version": row.get("version"),
                    "error": str(exc),
                },
            )
            return default.format(**values)


def candidate_prediction(candidate: RankedDraft) -> Prediction:
    """Rehydrate the gate candidate's prediction for publishing."""
    return Prediction(
        expected_clicks=candidate.expected_clicks,
        expected_impressions=candidate.expected_impressions,
        expected_position=candidate.expected_position,
        clicks_ci_low=candidate.clicks_ci_low,
        clicks_ci_high=candidate.clicks_ci_high,
        impressions_ci_low=candidate.impressions_ci_low,
        impressions_ci_high=candidate.impressions_ci_high,
        model_version=candidate.model_version,
    )


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
