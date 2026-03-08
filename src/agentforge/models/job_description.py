"""Data models for job description input."""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field


class JDSource(enum.StrEnum):
    FILE = "file"
    TEXT = "text"
    URL = "url"
    API = "api"


class JDSection(BaseModel):
    """A parsed section of a job description."""

    heading: str
    content: str


class JobDescription(BaseModel):
    """Parsed and structured job description input."""

    source: JDSource = JDSource.TEXT
    title: str = Field(..., min_length=1, max_length=200)
    company: str | None = None
    department: str | None = None
    location: str | None = None
    raw_text: str = Field(..., min_length=10)
    sections: list[JDSection] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Return raw text for processing."""
        return self.raw_text

    @property
    def section_map(self) -> dict[str, str]:
        """Return sections as heading→content mapping."""
        return {s.heading: s.content for s in self.sections}
