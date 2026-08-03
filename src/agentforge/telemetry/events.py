"""Telemetry event schema (local JSONL)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_run_id() -> str:
    return uuid4().hex[:16]


class TelemetryEvent(BaseModel):  # type: ignore[misc]
    """Single telemetry record. Never includes JD text or skill bodies."""

    schema_version: int = SCHEMA_VERSION
    ts: str = Field(default_factory=now_iso)
    event: str
    run_id: str | None = None
    command: str | None = None
    stage: str | None = None
    status: str | None = None  # ok | error | skipped
    duration_ms: float | None = None
    model: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)

    def to_jsonl(self) -> str:
        return str(self.model_dump_json(exclude_none=True))
