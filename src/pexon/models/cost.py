"""Cost accounting value objects."""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from pexon.models.base import FrozenModel


class CostBreakdown(FrozenModel):
    """What one run or article cost across external services."""

    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    search_calls: int = 0
    fetch_calls: int = 0
    llm_cost: float = 0.0
    search_cost: float = 0.0
    fetch_cost: float = 0.0
    fixed_cost: float = 0.0
    total_cost: float = 0.0
    currency: str = "USD"
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
