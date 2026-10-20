"""Demand-aware content portfolio planning."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pexon.config.settings import Settings
from pexon.models.portfolio import ContentPlan, KeywordDemand, PlanCandidate
from pexon.ports.keywords import KeywordPort
from pexon.ports.storage import StoragePort
from pexon.services.audit import AuditLog


class PortfolioService:
    """Turns keyword demand and existing coverage into a ranked content plan."""

    def __init__(
        self, settings: Settings, keywords: KeywordPort, storage: StoragePort, audit: AuditLog
    ) -> None:
        self._settings = settings
        self._keywords = keywords
        self._storage = storage
        self._audit = audit

    def build_plan(
        self, seeds: list[str], limit: int | None = None, run_id: str = "plan"
    ) -> ContentPlan:
        """Score demand, coverage and difficulty into a selected plan."""
        limit = limit or self._settings.plan_top_n
        demand = self._keywords.demand(seeds, self._settings.plan_candidate_pool)
        if not demand and seeds:
            demand = [
                KeywordDemand(
                    keyword=seed, source="unmeasured", intent="informational", funnel_stage="top"
                )
                for seed in seeds
            ]
        articles = self._storage.find("articles", status="published")
        covered_keywords = {
            str(row.get("target_keyword", "")).strip().lower()
            for row in articles
            if row.get("target_keyword")
        }
        candidates: list[PlanCandidate] = []
        for item in demand:
            if item.volume < self._settings.plan_min_volume:
                continue
            covered = item.keyword.strip().lower() in covered_keywords
            volume_score = min(1.0, item.volume / max(self._settings.plan_volume_ceiling, 1))
            intent_weight = self._settings.plan_intent_map.get(item.intent, 0.5)
            funnel_weight = self._settings.plan_funnel_map.get(item.funnel_stage, 0.5)
            difficulty_factor = 1.0 - min(
                max(item.difficulty, 0.0), self._settings.plan_difficulty_scale
            ) / max(self._settings.plan_difficulty_scale, 1.0)
            coverage_factor = self._settings.plan_coverage_penalty if covered else 1.0
            priority = (
                volume_score
                * intent_weight
                * funnel_weight
                * difficulty_factor
                * coverage_factor
                * self._settings.plan_ctr
            )
            candidates.append(
                PlanCandidate(
                    keyword=item.keyword,
                    topic_name_de=item.keyword[:1].upper() + item.keyword[1:],
                    cluster=item.cluster,
                    funnel_stage=item.funnel_stage,
                    volume=item.volume,
                    difficulty=item.difficulty,
                    cpc=item.cpc,
                    priority=round(priority, 6),
                    covered=covered,
                    rationale=(
                        "bereits abgedeckt"
                        if covered
                        else (
                            "keine Suchdaten; nur als Kandidat markiert"
                            if item.volume == 0
                            else "Suchvolumen, Intent, Funnelstufe und Schwierigkeit gewichtet"
                        )
                    ),
                )
            )
        candidates.sort(key=lambda row: row.priority, reverse=True)
        selected = tuple(candidate for candidate in candidates if not candidate.covered)[:limit]
        plan = ContentPlan(
            source=self._keywords.provider,
            candidates=tuple(candidates),
            selected=selected,
            notes=(
                "Keine Suchdaten gefunden; Seeds sind als unmeasured markiert."
                if not candidates or any(candidate.volume == 0 for candidate in candidates)
                else "Priorität = Volumen × Intent × Funnel × (1 − Schwierigkeit) × Coverage-Faktor."
            ),
        )
        self._storage.write(
            "content_plans",
            {
                "id": f"plan-{uuid.uuid4().hex[:12]}",
                "source": self._keywords.provider,
                "plan_json": plan.model_dump(mode="json"),
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        self._audit.emit(
            run_id,
            "content_plan_created",
            {
                "source": self._keywords.provider,
                "candidates": len(candidates),
                "selected": len(selected),
            },
        )
        return plan
