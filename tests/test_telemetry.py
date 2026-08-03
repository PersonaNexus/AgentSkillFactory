"""Tests for opt-in local telemetry (default off, no network)."""

from __future__ import annotations

import json
from pathlib import Path

from agentforge.pipeline.forge_pipeline import ForgePipeline
from agentforge.pipeline.stages import PipelineStage
from agentforge.telemetry import TelemetryEvent, get_sink, reset_sink_for_tests
from agentforge.telemetry.events import SCHEMA_VERSION
from agentforge.telemetry.sink import TelemetrySink


class _OkStage(PipelineStage):
    name = "ok_stage"

    def run(self, context: dict) -> dict:
        context["ok"] = True
        return context


class _BoomStage(PipelineStage):
    name = "boom"

    def run(self, context: dict) -> dict:
        raise RuntimeError("boom")


def test_default_sink_is_off(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("AGENTFORGE_TELEMETRY_MODE", raising=False)
    reset_sink_for_tests(TelemetrySink(mode="off", directory=tmp_path))
    sink = get_sink()
    assert not sink.enabled
    sink.record("pipeline_start", run_id="x")
    assert list(tmp_path.glob("*.jsonl")) == []


def test_local_sink_writes_jsonl(tmp_path: Path) -> None:
    sink = TelemetrySink(mode="local", directory=tmp_path)
    reset_sink_for_tests(sink)
    sink.record(
        "stage",
        run_id="abc",
        stage="extract",
        status="ok",
        duration_ms=12.5,
        model="test-model",
    )
    assert sink.path is not None
    lines = sink.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["event"] == "stage"
    assert payload["stage"] == "extract"
    assert payload["duration_ms"] == 12.5
    assert "jd" not in payload
    assert "prompt" not in json.dumps(payload).lower() or payload.get("detail") == {}


def test_pipeline_records_stage_timings(tmp_path: Path) -> None:
    sink = TelemetrySink(mode="local", directory=tmp_path)
    reset_sink_for_tests(sink)
    pipeline = ForgePipeline()
    pipeline.add_stage(_OkStage())
    pipeline.skip_stage("missing")
    out = pipeline.run({})
    assert out["ok"] is True
    assert sink.path is not None
    events = [json.loads(line) for line in sink.path.read_text().splitlines() if line]
    names = [e["event"] for e in events]
    assert "pipeline_start" in names
    assert "pipeline_end" in names
    stages = [e for e in events if e["event"] == "stage"]
    assert any(s.get("stage") == "ok_stage" and s.get("status") == "ok" for s in stages)
    assert any(s.get("duration_ms") is not None for s in stages)


def test_pipeline_records_error_stage(tmp_path: Path) -> None:
    sink = TelemetrySink(mode="local", directory=tmp_path)
    reset_sink_for_tests(sink)
    pipeline = ForgePipeline()
    pipeline.add_stage(_BoomStage())
    try:
        pipeline.run({})
        raise AssertionError("expected boom")
    except RuntimeError:
        pass
    events = [json.loads(line) for line in sink.path.read_text().splitlines() if line]
    assert any(e.get("status") == "error" and e.get("stage") == "boom" for e in events)
    assert any(e.get("event") == "pipeline_end" and e.get("status") == "error" for e in events)


def test_event_schema_excludes_content_fields() -> None:
    event = TelemetryEvent(
        event="stage",
        stage="generate",
        status="ok",
        detail={"token_estimate": 100},
    )
    data = event.model_dump()
    for forbidden in ("jd_text", "skill_md", "prompt", "identity_yaml"):
        assert forbidden not in data
        assert forbidden not in data.get("detail", {})
