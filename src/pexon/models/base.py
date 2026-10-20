"""Shared model configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Immutable value object with strict field validation."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class MutableModel(BaseModel):
    """Mutable aggregate root."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
