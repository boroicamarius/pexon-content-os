"""Technical SEO metadata, internal links, sitemap and robots output."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from pexon.config.settings import Settings
from pexon.models.draft import Draft
from pexon.models.publishing import InternalLink, SeoMetadata
from pexon.models.topic import Topic
from pexon.ports.storage import StoragePort

_WORD = re.compile(r"[A-Za-zÄÖÜäöüß0-9]{4,}")
_MARKDOWN = re.compile(r"[#*_`>\[\]]+")


class SeoService:
    """Builds the metadata a real CMS needs and maintains local crawl files."""

    def __init__(self, settings: Settings, storage: StoragePort) -> None:
        self._settings = settings
        self._storage = storage

    def build(self, draft: Draft, topic: Topic, article_id: str,
              slug: str) -> SeoMetadata:
        """Create canonical, description, keywords, JSON-LD and internal links."""
        canonical = f"{self._settings.site_base_url.rstrip('/')}/blog/{slug}"
        plain = _MARKDOWN.sub(" ", draft.body_de)
        description = re.sub(r"\s+", " ", plain).strip()[: self._settings.meta_description_chars]
        keywords = tuple(dict.fromkeys(
            [*(topic.target_keyword.split() if topic.target_keyword else []),
             *list(_WORD.findall(draft.title_de))[:6]]
        ))[:10]
        links = self._internal_links(draft)
        json_ld: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": draft.title_de,
            "description": description,
            "inLanguage": "de-DE",
            "datePublished": datetime.now(UTC).isoformat(),
            "author": {"@type": "Organization", "name": self._settings.geo_brand_name},
            "publisher": {"@type": "Organization", "name": self._settings.geo_brand_name},
            "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
            "about": [{"@type": "Thing", "name": keyword} for keyword in keywords[:5]],
        }
        return SeoMetadata(
            canonical_url=canonical,
            meta_description=description,
            keywords=keywords,
            json_ld=json_ld,
            internal_links=tuple(links),
        )

    def with_internal_links(self, body: str, metadata: SeoMetadata) -> str:
        """Append a real internal-link section when related articles exist."""
        if not metadata.internal_links:
            return body
        links = "\n".join(
            f"- [{link.title}]({link.url})" for link in metadata.internal_links
        )
        return f"{body.rstrip()}\n\n## Weiterführende Beiträge\n\n{links}\n"

    def frontmatter(self, draft: Draft, topic: Topic, article_id: str,
                    metadata: SeoMetadata, prediction: Any, status: str,
                    extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return the complete YAML frontmatter block."""
        data: dict[str, Any] = {
            "article_id": article_id,
            "title": draft.title_de,
            "topic": topic.name_de,
            "target_keyword": topic.target_keyword,
            "cluster": topic.cluster,
            "funnel_stage": topic.funnel_stage,
            "status": status,
            "canonical_url": metadata.canonical_url,
            "description": metadata.meta_description,
            "keywords": list(metadata.keywords),
            "created_at": datetime.now(UTC).isoformat(),
            "model_version": prediction.model_version,
            "prompt_version": draft.prompt_version,
            "expected": {
                "clicks": prediction.expected_clicks,
                "impressions": prediction.expected_impressions,
                "clicks_ci": [prediction.clicks_ci_low, prediction.clicks_ci_high],
                "impressions_ci": [prediction.impressions_ci_low, prediction.impressions_ci_high],
            },
            "json_ld": metadata.json_ld,
            "provider_config": self._settings.provider_config,
        }
        if extra:
            data.update(extra)
        return data

    def _internal_links(self, draft: Draft) -> list[InternalLink]:
        rows = self._storage.find(
            "articles", limit=self._settings.internal_link_lookback,
            order_by="created_at", desc=True,
        )
        source_words = set(_WORD.findall(draft.title_de.lower()))
        scored: list[tuple[int, InternalLink]] = []
        for row in rows:
            if not row.get("slug"):
                continue
            title = str(row.get("title_de", ""))
            overlap = len(source_words & set(_WORD.findall(title.lower())))
            if overlap:
                scored.append((overlap, InternalLink(
                    title=title,
                    url=f"{self._settings.site_base_url.rstrip('/')}/blog/{row['slug']}",
                )))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [link for _, link in scored[: self._settings.internal_link_count]]

    def write_crawl_files(self) -> None:
        """Write sitemap.xml and robots.txt from published articles."""
        if not self._settings.sitemap_enabled:
            return
        rows = self._storage.find("articles", status="published", order_by="created_at", desc=True)
        urls = []
        for row in rows:
            canonical = row.get("canonical_url")
            if canonical:
                urls.append((str(canonical), str(row.get("created_at", ""))))
        body = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
                "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"]
        for loc, lastmod in urls:
            body.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
        body.append("</urlset>")
        self._settings.sitemap_file.parent.mkdir(parents=True, exist_ok=True)
        self._settings.sitemap_file.write_text("\n".join(body) + "\n", encoding="utf-8")
        sitemap_url = f"{self._settings.site_base_url.rstrip('/')}/sitemap.xml"
        self._settings.robots_file.write_text(
            f"User-agent: *\nAllow: /\nSitemap: {sitemap_url}\n", encoding="utf-8"
        )
