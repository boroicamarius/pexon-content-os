"""WordPress REST publishing adapter."""
from __future__ import annotations

import httpx

from pexon.config.settings import Settings
from pexon.models.publishing import PublishRequest, PublishResult
from pexon.ports.errors import ProviderError
from pexon.ports.publishing import PublishingPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class WordPressPublisher(PublishingPort):
    """Publishes through the real WordPress REST API with application passwords."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._user = settings.wordpress_user
        self._password = (
            settings.wordpress_app_password.get_secret_value()
            if settings.wordpress_app_password else ""
        )

    @property
    def provider(self) -> str:
        return "wordpress"

    def publish(self, request: PublishRequest) -> PublishResult:
        """Create a post on WordPress."""
        if not self._settings.wordpress_base_url or not self._user or not self._password:
            raise ProviderError("WordPress URL, user and application password are required")
        try:
            response = httpx.post(
                f"{self._settings.wordpress_base_url.rstrip('/')}/wp-json/wp/v2/posts",
                auth=(self._user, self._password),
                json={
                    "title": request.title,
                    "content": request.body_md,
                    "slug": request.slug,
                    "status": self._settings.wordpress_status,
                },
                timeout=self._settings.publishing_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise ProviderError(f"wordpress publish failed: {exc}") from exc
        return PublishResult(
            provider=self.provider,
            external_id=str(data.get("id", "")),
            url=str(data.get("link", request.canonical_url)),
            status=str(data.get("status", self._settings.wordpress_status)),
        )

    def probe(self) -> bool:
        """Authenticate against the WordPress REST API."""
        if not self._settings.wordpress_base_url or not self._user or not self._password:
            raise ProviderError("WordPress URL, user and application password are required")
        response = httpx.get(
            f"{self._settings.wordpress_base_url.rstrip('/')}/wp-json/wp/v2/users/me",
            auth=(self._user, self._password),
            timeout=self._settings.publishing_timeout_seconds,
        )
        response.raise_for_status()
        return True
