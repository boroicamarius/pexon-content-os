"""Deterministic feature extraction shared by ranking and the learner."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from pexon.config.settings import Settings
from pexon.models.draft import Draft
from pexon.models.research import PageFeatures, ResearchSnapshot
from pexon.models.topic import Topic

_WORD = re.compile(r"[A-Za-zÄÖÜäöüß0-9]+")
_HEADING = re.compile(r"^#{2,3}\s+", re.MULTILINE)
_FAQ = re.compile(r"\b(faq|häufige fragen|fragen und antworten)\b", re.IGNORECASE)


class FeatureExtractor:
    """Turns a German draft into the same vector space as competitor pages."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def draft_features(
        self, draft: Draft, topic: Topic, snapshot: ResearchSnapshot | None
    ) -> PageFeatures:
        """Compute seven bounded page features."""
        body = draft.body_de
        title_words = {w.lower() for w in _WORD.findall(draft.title_de)}
        body_lower = body.lower()
        keyword_hits = sum(1 for w in title_words if w in body_lower)
        keyword_coverage = keyword_hits / max(len(title_words), 1)
        headings = len(_HEADING.findall(body))
        sections = max(len(draft.sections), 1)
        section_balance = min(1.0, sections / max(self._settings.heading_target_count, 1))
        body.count("\n- ") + body.count("\n* ") + body.count("\n1. ")
        entities = self._entities(topic, snapshot)
        entity_hits = sum(1 for entity in entities if entity.lower() in body_lower)
        entity_coverage = min(1.0, entity_hits / max(self._settings.entity_target_count, 1))
        first = draft.sections[0].body_de if draft.sections else body
        first_words = len(_WORD.findall(first))
        direct = (
            first.lower().startswith(("ja", "nein", "kurz", "die", "der", "das"))
            or "?" in first[:120]
        )
        answer_first = (
            1.0
            if first_words <= self._settings.answer_first_max_words and direct
            else self._settings.feature_answer_first_fallback
        )
        citations = len(draft.citations)
        source_authority = min(1.0, citations / max(self._settings.citation_target_count, 1))
        freshness = self._freshness(snapshot)
        seo = min(
            1.0,
            self._settings.feature_seo_keyword_weight * keyword_coverage
            + self._settings.feature_seo_structure_weight * section_balance,
        )
        geo = min(
            1.0,
            self._settings.feature_geo_entity_weight * entity_coverage
            + self._settings.feature_geo_structure_weight * section_balance
            + self._settings.feature_geo_heading_weight
            * min(1.0, headings / max(self._settings.heading_target_count, 1)),
        )
        aeo = min(
            1.0,
            self._settings.feature_aeo_answer_weight * answer_first
            + self._settings.feature_aeo_entity_weight * entity_coverage
            + (self._settings.feature_aeo_faq_bonus if _FAQ.search(body) else 0.0),
        )
        return PageFeatures(
            seo=round(seo, 4),
            geo=round(geo, 4),
            aeo=round(aeo, 4),
            entity_coverage=round(entity_coverage, 4),
            answer_first=round(answer_first, 4),
            source_authority=round(source_authority, 4),
            freshness=round(freshness, 4),
        )

    def vector(self, features: PageFeatures, draft: Draft) -> dict[str, float]:
        """Extend page features with content statistics for model training."""
        words = len(_WORD.findall(draft.body_de))
        headings = len(_HEADING.findall(draft.body_de))
        vector = features.as_dict()
        vector.update(
            {
                "word_count": min(1.0, words / max(self._settings.draft_max_words, 1)),
                "heading_count": min(1.0, headings / max(self._settings.heading_target_count, 1)),
                "citation_count": min(
                    1.0, len(draft.citations) / max(self._settings.citation_target_count, 1)
                ),
            }
        )
        return vector

    def gaps(self, own: PageFeatures, competitor: PageFeatures | None) -> dict[str, float]:
        """Positive gaps where the competitor is stronger."""
        if competitor is None:
            return {}
        return {
            key: round(max(0.0, competitor.as_dict()[key] - own.as_dict()[key]), 4)
            for key in own.as_dict()
        }

    def _entities(self, topic: Topic, snapshot: ResearchSnapshot | None) -> list[str]:
        entities = [term for term in topic.name_de.split() if len(term) > 3]
        if snapshot:
            for fact in snapshot.facts[: self._settings.entity_target_count]:
                for word in _WORD.findall(fact.claim_de):
                    if len(word) > 5 and word[0].isupper() and word not in entities:
                        entities.append(word)
        return entities[: self._settings.entity_target_count]

    def _freshness(self, snapshot: ResearchSnapshot | None) -> float:
        if not snapshot:
            return 0.0
        stamps = [s.fetched_at for s in snapshot.sources if s.fetched_at]
        if not stamps:
            return self._settings.feature_freshness_missing
        newest = max(stamps)
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=UTC)
        age_days = max(0.0, (datetime.now(UTC) - newest).total_seconds() / 86400)
        return max(0.0, 1.0 - age_days / max(self._settings.freshness_reference_days, 1))
