"""Data models for enterprise culture profiles."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CultureValue(BaseModel):
    """A single cultural value with behavioral indicators and trait effects."""

    name: str = Field(..., min_length=1)
    description: str = ""
    behavioral_indicators: list[str] = Field(default_factory=list)
    trait_deltas: dict[str, float] = Field(
        default_factory=dict,
        description="PersonaNexus trait adjustments (-0.3 to +0.3)",
    )


class CultureProfile(BaseModel):
    """Enterprise culture profile parsed from culture documents."""

    name: str = Field(..., min_length=1)
    description: str = ""
    values: list[CultureValue] = Field(default_factory=list)
    communication_tone: str | None = None
    decision_style: str | None = None
    source_file: str | None = None
