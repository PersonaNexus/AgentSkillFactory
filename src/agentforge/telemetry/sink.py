"""Telemetry sink: off (default) or local JSONL file."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Literal

from agentforge.telemetry.events import TelemetryEvent

Mode = Literal["off", "local"]

_DEFAULT_DIR = Path.home() / ".agentforge" / "telemetry"
_lock = threading.Lock()
_sink: TelemetrySink | None = None


def _resolve_mode() -> Mode:
    raw = os.environ.get("AGENTFORGE_TELEMETRY_MODE", "off").strip().lower()
    if raw in ("local", "file", "on"):
        return "local"
    # remote is reserved; treat as off until implemented
    return "off"


def _resolve_dir() -> Path:
    override = os.environ.get("AGENTFORGE_TELEMETRY_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return _DEFAULT_DIR


class TelemetrySink:
    """Append-only JSONL writer when mode is local; no-op when off."""

    def __init__(self, mode: Mode | None = None, directory: Path | None = None) -> None:
        self.mode: Mode = mode if mode is not None else _resolve_mode()
        self.directory = directory if directory is not None else _resolve_dir()
        self._path: Path | None = None
        if self.mode == "local":
            self.directory.mkdir(parents=True, exist_ok=True)
            # One file per process day-bucket for simple tailing
            from datetime import UTC, datetime

            day = datetime.now(UTC).strftime("%Y-%m-%d")
            self._path = self.directory / f"events-{day}.jsonl"
            try:
                self._path.touch(exist_ok=True)
                self._path.chmod(0o600)
            except OSError:
                pass

    @property
    def enabled(self) -> bool:
        return self.mode == "local" and self._path is not None

    @property
    def path(self) -> Path | None:
        return self._path

    def emit(self, event: TelemetryEvent) -> None:
        if not self.enabled or self._path is None:
            return
        line = event.to_jsonl() + "\n"
        with _lock, self._path.open("a", encoding="utf-8") as fh:
            fh.write(line)

    def record(
        self,
        event: str,
        *,
        run_id: str | None = None,
        command: str | None = None,
        stage: str | None = None,
        status: str | None = None,
        duration_ms: float | None = None,
        model: str | None = None,
        **detail: object,
    ) -> None:
        if not self.enabled:
            return
        self.emit(
            TelemetryEvent(
                event=event,
                run_id=run_id,
                command=command,
                stage=stage,
                status=status,
                duration_ms=duration_ms,
                model=model,
                detail={k: v for k, v in detail.items() if v is not None},
            )
        )


def get_sink() -> TelemetrySink:
    """Process-wide sink, re-resolved when env mode may have changed for tests."""
    global _sink
    with _lock:
        if _sink is None:
            _sink = TelemetrySink()
        return _sink


def reset_sink_for_tests(sink: TelemetrySink | None = None) -> None:
    """Replace or clear the process sink (tests only)."""
    global _sink
    with _lock:
        _sink = sink
