"""Opt-in local telemetry for AgentForge.

Default mode is ``off`` — no metrics are written and no network I/O occurs.
Set ``AGENTFORGE_TELEMETRY_MODE=local`` to append JSONL events under
``~/.agentforge/telemetry/`` (or ``AGENTFORGE_TELEMETRY_DIR``).

Remote export is intentionally not implemented yet (see docs/telemetry-design.md).
"""

from __future__ import annotations

from agentforge.telemetry.events import TelemetryEvent, now_iso
from agentforge.telemetry.sink import TelemetrySink, get_sink, reset_sink_for_tests

__all__ = [
    "TelemetryEvent",
    "TelemetrySink",
    "get_sink",
    "now_iso",
    "reset_sink_for_tests",
]
