"""Generic CMS webhook publishing adapter."""
from __future__ import annotations

import httpx

from pexon.config.settings import Settings
from pexon.models.publishing import PublishRequest, PublishResult
from pexon.ports.errors import ProviderError
from pexon.ports.publishing import PublishingPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class WebhookPublisher(PublishingPort):
    """POSTs the full article payload to a customer-controlled CMS webhook."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def provider(self) -> str:
        return "webhook"

    def publish(self, request: PublishRequest) -> PublishResult:
        """Send the article payload to the configured endpoint."""
        if not self._settings.webhook_url:
            raise ProviderError("WEBHOOK_URL is required for webhook publishing")
        headers = {"content-type": "application/json"}
        if self._settings.webhook_token:
            headers["Authorization"] = (
                f"Bearer {self._settings.webhook_token.get_secret_value()}"
            )
        try:
            response = httpx.post(
                self._settings.webhook_url,
                headers=headers,
                json=request.model_dump(mode="json"),
                timeout=self._settings.publishing_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json() if response.content else {}
        except Exception as exc:
            raise ProviderError(f"webhook publish failed: {exc}") from exc
        return PublishResult(
            provider=self.provider,
            external_id=str(data.get("id", "")),
            url=str(data.get("url", request.canonical_url)),
            status=str(data.get("status", "published")),
        )

    def probe(self) -> bool:
        """Check endpoint reachability with a real request."""
        if not self._settings.webhook_url:
            raise ProviderError("WEBHOOK_URL is required for webhook publishing")
        response = httpx.head(
            self._settings.webhook_url,
            timeout=self._settings.publishing_timeout_seconds,
        )
        return response.status_code < 500
