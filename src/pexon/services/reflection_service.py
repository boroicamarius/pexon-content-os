"""Frame 4: publish, measure, propose, mutate and update."""

from __future__ import annotations

import logging
import re
import shutil
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from pexon.config.prompts import (
    DIRECTION_USER,
    PROMPT_MUTATION_SYSTEM,
    PROMPT_MUTATION_USER,
    PROPOSE_SYSTEM,
    PROPOSE_USER,
    SECTION_USER,
)
from pexon.config.settings import Settings
from pexon.models.draft import Draft
from pexon.models.performance import PerformanceBundle
from pexon.models.prediction import Prediction, PromptMutation, Proposal
from pexon.models.publishing import PublishRequest, ReviewDecision
from pexon.models.research import ResearchSnapshot
from pexon.models.topic import Topic
from pexon.observability.metrics import MetricsCollector
from pexon.ports.analytics import AnalyticsPort
from pexon.ports.publishing import PublishingPort
from pexon.ports.storage import StoragePort
from pexon.services.audit import AuditLog
from pexon.services.economics import EconomicsService
from pexon.services.features import FeatureExtractor
from pexon.services.gateway import LLMGateway
from pexon.services.learner import Learner
from pexon.services.seo import SeoService

logger = logging.getLogger(__name__)


class ReflectionService:
    """One service for the complete Reflection frame."""

    def __init__(
        self,
        settings: Settings,
        generator: LLMGateway,
        analytics: AnalyticsPort,
        storage: StoragePort,
        features: FeatureExtractor,
        learner: Learner,
        audit: AuditLog,
        metrics: MetricsCollector,
        publisher: PublishingPort,
        seo: SeoService,
        economics: EconomicsService,
    ) -> None:
        self._settings = settings
        self._generator = generator
        self._analytics = analytics
        self._storage = storage
        self._features = features
        self._learner = learner
        self._audit = audit
        self._metrics = metrics
        self._publisher = publisher
        self._seo = seo
        self._economics = economics

    def review_and_publish(
        self,
        draft: Draft,
        prediction: Prediction,
        topic: Topic,
        snapshot: ResearchSnapshot,
        run_id: str,
    ) -> tuple[str, str, str]:
        """Persist the article, SEO layer, cost and publishing result."""
        article_id = f"art-{uuid.uuid4().hex[:12]}"
        slug = self._slugify(draft.title_de)
        created = datetime.now(UTC)
        metadata = self._seo.build(draft, topic, article_id, slug)
        body = self._seo.with_internal_links(draft.body_de, metadata)
        review_required = self._settings.require_human_review
        status = "pending_review" if review_required else "published"
        frontmatter = self._seo.frontmatter(
            draft,
            topic,
            article_id,
            metadata,
            prediction,
            status,
            extra={"review_required": review_required},
        )
        staged_path = ""
        external_id = ""
        external_url = metadata.canonical_url
        if review_required:
            self._settings.pending_path.mkdir(parents=True, exist_ok=True)
            path = self._settings.pending_path / f"{slug}.md"
            if path.exists():
                path = self._settings.pending_path / f"{slug}-{article_id[-6:]}.md"
            path.write_text(
                "---\n"
                + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
                + "---\n\n"
                + body.strip()
                + "\n",
                encoding="utf-8",
            )
            staged_path = str(path)
            article_path = str(path)
        else:
            result = self._publisher.publish(
                PublishRequest(
                    article_id=article_id,
                    title=draft.title_de,
                    body_md=body,
                    slug=slug,
                    canonical_url=metadata.canonical_url,
                    frontmatter=frontmatter,
                    status="publish",
                )
            )
            article_path = (
                result.local_path or result.url or str(self._settings.content_path / f"{slug}.md")
            )
            external_id = result.external_id
            external_url = result.url or metadata.canonical_url
            status = (
                "published"
                if result.status in {"publish", "published"}
                else (result.status or "published")
            )
        article = {
            "id": article_id,
            "topic_id": topic.id,
            "title_de": draft.title_de,
            "body_md": body,
            "status": status,
            "prompt_version": draft.prompt_version,
            "model_version": prediction.model_version,
            "slug": slug,
            "target_keyword": topic.target_keyword,
            "cluster": topic.cluster,
            "funnel_stage": topic.funnel_stage,
            "canonical_url": metadata.canonical_url,
            "external_url": "" if review_required else external_url,
            "external_id": external_id,
            "staged_path": staged_path,
            "review_status": "pending" if review_required else "not_required",
            "reviewed_by": None,
            "provider_config_json": self._settings.provider_config,
            "created_at": created.isoformat(),
        }
        self._storage.write("articles", article)
        self._storage.write(
            "drafts",
            {
                "id": f"draft-{article_id}",
                "article_id": article_id,
                "version": 1,
                "body_md": body,
                "signals_json": draft.signals,
                "created_at": created.isoformat(),
            },
        )
        self._storage.write(
            "predictions",
            {
                "id": f"pred-{article_id}",
                "article_id": article_id,
                "model_version": prediction.model_version,
                "clicks": prediction.expected_clicks,
                "impressions": prediction.expected_impressions,
                "position": prediction.expected_position,
                "ci_json": {
                    "clicks": [prediction.clicks_ci_low, prediction.clicks_ci_high],
                    "impressions": [prediction.impressions_ci_low, prediction.impressions_ci_high],
                },
                "created_at": created.isoformat(),
            },
        )
        page_features = self._features.draft_features(draft, topic, snapshot)
        vector = self._features.vector(page_features, draft)
        self._storage.write(
            "features",
            {
                "id": f"feat-{article_id}",
                "article_id": article_id,
                "features_json": vector,
                "created_at": created.isoformat(),
            },
        )
        self._economics.record_article_cost(article_id, run_id)
        if not review_required:
            self._seo.write_crawl_files()
        self._audit.emit(
            run_id,
            "article_staged" if review_required else "article_published",
            {
                "article_id": article_id,
                "path": article_path,
                "model_version": prediction.model_version,
                "publisher": self._publisher.provider,
                "review_required": review_required,
                "canonical_url": metadata.canonical_url,
            },
            article_id=article_id,
        )
        return article_id, article_path, status

    def approve(self, article_id: str, reviewer: str, notes: str, run_id: str) -> tuple[str, str]:
        """Approve a staged article and make it public."""
        article = self._storage.read("articles", article_id)
        if not article:
            raise ValueError(f"unknown article: {article_id}")
        if article.get("status") != "pending_review":
            return str(article.get("status", "")), str(article.get("external_url") or "")
        staged = Path(str(article.get("staged_path") or ""))
        slug = str(article.get("slug") or article_id)
        target = self._settings.content_path / f"{slug}.md"
        if target.exists():
            target = self._settings.content_path / f"{slug}-{article_id[-6:]}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        if staged.exists():
            shutil.move(str(staged), str(target))
            text = target.read_text(encoding="utf-8")
            if text.startswith("---"):
                _, front, body = text.split("---", 2)
                frontmatter = yaml.safe_load(front) or {}
                frontmatter.update(
                    {
                        "status": "published",
                        "reviewed_by": reviewer,
                        "reviewed_at": datetime.now(UTC).isoformat(),
                    }
                )
                target.write_text(
                    "---\n"
                    + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
                    + "---"
                    + body,
                    encoding="utf-8",
                )
        else:
            target.write_text(str(article.get("body_md", "")) + "\n", encoding="utf-8")
        external_url = str(article.get("canonical_url") or "")
        if self._publisher.provider != "markdown":
            result = self._publisher.publish(
                PublishRequest(
                    article_id=article_id,
                    title=str(article.get("title_de", "")),
                    body_md=str(article.get("body_md", "")),
                    slug=slug,
                    canonical_url=external_url,
                    frontmatter={"article_id": article_id, "title": article.get("title_de", "")},
                    status="publish",
                )
            )
            external_url = result.url or external_url
        article.update(
            {
                "status": "published",
                "review_status": "approved",
                "reviewed_by": reviewer,
                "staged_path": "",
                "external_url": external_url,
            }
        )
        self._storage.write("articles", article)
        self._storage.write(
            "reviews",
            ReviewDecision(
                article_id=article_id,
                reviewer=reviewer,
                decision="approved",
                notes=notes,
            ).model_dump(mode="json")
            | {
                "id": f"review-{uuid.uuid4().hex[:12]}",
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        self._seo.write_crawl_files()
        self._audit.emit(
            run_id,
            "review_approved",
            {
                "article_id": article_id,
                "reviewer": reviewer,
                "notes": notes,
            },
            article_id=article_id,
        )
        return "published", str(target)

    def collect_metrics(
        self, article_id: str, run_id: str, wait_seconds: int = 0
    ) -> PerformanceBundle | None:
        """Read real analytics or explicitly record pending measurement."""
        if wait_seconds <= 0:
            self._audit.emit(run_id, "pending_measure", {"article_id": article_id}, article_id)
            return None
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        article = self._storage.read("articles", article_id)
        page_url = ""
        if article:
            slug = article.get("slug") or ""
            page_url = f"{self._settings.site_base_url.rstrip('/')}/blog/{slug}" if slug else ""
        bundle = self._analytics.fetch(
            article_id, window_days=self._settings.analytics_window_days, page_url=page_url or None
        )
        if not bundle.rows:
            self._audit.emit(
                run_id,
                "pending_measure",
                {
                    "article_id": article_id,
                    "reason": "no rows in window",
                    "window_days": self._settings.analytics_window_days,
                },
                article_id,
            )
            return None
        for index, row in enumerate(bundle.rows):
            payload = row.model_dump(mode="json")
            payload["id"] = f"perf-{article_id}-{index}"
            self._storage.write("performance", payload)
        self._audit.emit(
            run_id,
            "metrics_collected",
            {
                "article_id": article_id,
                "clicks": bundle.clicks,
                "impressions": bundle.impressions,
                "position": bundle.position,
                "rows": len(bundle.rows),
                "provider": self._analytics.provider,
            },
            article_id,
        )
        return bundle

    def propose_changes(
        self, prediction: Prediction, performance: PerformanceBundle, run_id: str, article_id: str
    ) -> Proposal | None:
        """Compare prediction with actuals and propose one concrete adjustment."""
        click_error = abs(performance.clicks - prediction.expected_clicks) / max(
            prediction.expected_clicks, 1.0
        )
        impression_error = abs(performance.impressions - prediction.expected_impressions) / max(
            prediction.expected_impressions, 1.0
        )
        error = max(click_error, impression_error)
        if error <= self._settings.propose_error_threshold:
            self._audit.emit(
                run_id,
                "proposal_not_needed",
                {
                    "error": round(error, 4),
                    "threshold": self._settings.propose_error_threshold,
                },
                article_id,
            )
            return None
        prompt = PROPOSE_USER.format(
            article_id=article_id,
            pred_clicks=prediction.expected_clicks,
            pred_impressions=prediction.expected_impressions,
            actual_clicks=performance.clicks,
            actual_impressions=performance.impressions,
            error=round(error, 4),
            threshold=self._settings.propose_error_threshold,
        )
        try:
            proposal = self._generator.structured(
                PROPOSE_SYSTEM,
                prompt,
                Proposal,
                max_tokens=self._settings.reflection_prompt_max_tokens,
            )
            assert isinstance(proposal, Proposal)
        except Exception as exc:
            self._audit.emit(run_id, "proposal_failed", {"error": str(exc)}, article_id)
            return None
        self._audit.emit(
            run_id,
            "proposal_created",
            {
                "error": round(error, 4),
                "proposal": proposal.model_dump(mode="json"),
            },
            article_id,
        )
        return proposal

    def mutate_prompt(self, proposal: Proposal, run_id: str) -> PromptMutation | None:
        """Create a new prompt variant, never editing prompts.py."""
        target = (
            proposal.target_prompt
            if proposal.target_prompt in {"direction", "section"}
            else "direction"
        )
        current = self._storage.latest("prompt_variants", name=target)
        template = (
            str(current["template_de"])
            if current
            else (DIRECTION_USER if target == "direction" else SECTION_USER)
        )
        prompt = PROMPT_MUTATION_USER.format(
            template=template,
            adjustment=proposal.adjustment_de,
            diagnosis=proposal.diagnosis_de,
        )
        try:
            mutation = self._generator.structured(
                PROMPT_MUTATION_SYSTEM,
                prompt,
                PromptMutation,
                max_tokens=self._settings.reflection_prompt_max_tokens,
            )
            assert isinstance(mutation, PromptMutation)
        except Exception as exc:
            self._audit.emit(run_id, "prompt_mutation_failed", {"error": str(exc)})
            return None
        mutation = mutation.model_copy(update={"name": target})
        version = self._next_variant_version(target)
        self._storage.write(
            "prompt_variants",
            {
                "id": f"variant-{uuid.uuid4().hex[:12]}",
                "name": target,
                "version": version,
                "template_de": mutation.template_de,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        self._audit.emit(
            run_id,
            "prompt_variant_created",
            {
                "name": target,
                "version": version,
                "rationale": mutation.rationale_de,
            },
        )
        return mutation

    def update(self, mutation: PromptMutation | None, run_id: str) -> dict[str, Any]:
        """Persist the update and give the learner a chance to promote new weights."""
        training = self._learner.fit(run_id)
        payload = {
            "prompt_variant": mutation.name if mutation else None,
            "weights_version": training.version,
            "trained": training.trained,
        }
        self._audit.emit(run_id, "reflection_updated", payload)
        return payload

    def evaluate(self, since: datetime) -> dict[str, float]:
        """Compute MAE/R2 of predictions against measured performance since a date."""
        predictions = {row["article_id"]: row for row in self._storage.find("predictions")}
        actuals: dict[str, dict[str, Any]] = {}
        for row in self._storage.find("performance"):
            measured = _parse_dt(str(row.get("measured_at", "")))
            if measured < since:
                continue
            current = actuals.get(row["article_id"])
            if current is None:
                actuals[row["article_id"]] = {
                    "clicks": float(row["clicks"]),
                    "impressions": float(row["impressions"]),
                }
            else:
                current["clicks"] += float(row["clicks"])
                current["impressions"] += float(row["impressions"])
        pairs = [
            (predictions[aid], actual) for aid, actual in actuals.items() if aid in predictions
        ]
        if not pairs:
            return {"n": 0.0, "mae_clicks": 0.0, "mae_impressions": 0.0}
        mae_clicks = sum(abs(p["clicks"] - a["clicks"]) for p, a in pairs) / len(pairs)
        mae_impressions = sum(abs(p["impressions"] - a["impressions"]) for p, a in pairs) / len(
            pairs
        )
        return {
            "n": float(len(pairs)),
            "mae_clicks": round(mae_clicks, 4),
            "mae_impressions": round(mae_impressions, 4),
        }

    def _next_variant_version(self, name: str) -> int:
        latest = self._storage.latest("prompt_variants", name=name, order_by="version")
        return int(latest["version"]) + 1 if latest else 1

    def _slugify(self, title: str) -> str:
        replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"}
        value = "".join(replacements.get(char, char) for char in title.lower())
        value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
        return value[: self._settings.slug_max_length] or "beitrag"


def _parse_dt(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return datetime.now(UTC)
