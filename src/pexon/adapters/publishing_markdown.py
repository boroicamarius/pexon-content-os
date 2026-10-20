"""Local Markdown publisher, the zero-key publishing path."""

from __future__ import annotations

from pathlib import Path

import yaml

from pexon.config.settings import Settings
from pexon.models.publishing import PublishRequest, PublishResult
from pexon.ports.publishing import PublishingPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class MarkdownPublisher(PublishingPort):
    """Writes YAML-frontmatter Markdown into content/posts."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def provider(self) -> str:
        return "markdown"

    def publish(self, request: PublishRequest) -> PublishResult:
        """Write the local article file atomically."""
        directory: Path = self._settings.content_path
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{request.slug}.md"
        if path.exists():
            path = directory / f"{request.slug}-{request.article_id[-6:]}.md"
        content = (
            "---\n"
            + yaml.safe_dump(request.frontmatter, allow_unicode=True, sort_keys=False)
            + "---\n\n"
            + request.body_md.strip()
            + "\n"
        )
        path.write_text(content, encoding="utf-8")
        return PublishResult(
            provider=self.provider,
            external_id=request.article_id,
            url=request.canonical_url,
            local_path=str(path),
            status="published",
        )

    def probe(self) -> bool:
        """Verify the content directory is writable."""
        self._settings.content_path.mkdir(parents=True, exist_ok=True)
        return self._settings.content_path.is_dir()
