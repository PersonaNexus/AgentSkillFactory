"""Composable forge pipeline engine."""

from __future__ import annotations

import time
from typing import Any

from agentforge.models.blueprint import AgentBlueprint
from agentforge.pipeline.stages import (
    AnalyzeStage,
    AnonymizeStage,
    ConductorGenerateStage,
    CronEnrichStage,
    CultureStage,
    DeepAnalyzeStage,
    ExtractStage,
    GenerateStage,
    IngestStage,
    MapStage,
    MethodologyStage,
    OpenClawCompileStage,
    PersonaNexusDeploymentCompileStage,
    PipelineStage,
    TeamComposeStage,
    TeamForgeStage,
    ToolMapStage,
)
from agentforge.telemetry import get_sink
from agentforge.telemetry.events import new_run_id


class ForgePipeline:
    """Composable pipeline for transforming JDs into agent blueprints.

    Supports adding, removing, and skipping stages. The pipeline passes
    a context dict through each stage sequentially.

    When ``AGENTFORGE_TELEMETRY_MODE=local``, stage timings are written to
    local JSONL (no JD/skill content, no network).
    """

    def __init__(self) -> None:
        self.stages: list[PipelineStage] = []
        self._skipped: set[str] = set()

    def add_stage(self, stage: PipelineStage) -> ForgePipeline:
        """Add a stage to the pipeline."""
        self.stages.append(stage)
        return self

    def skip_stage(self, name: str) -> ForgePipeline:
        """Skip a named stage during execution."""
        self._skipped.add(name)
        return self

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute all non-skipped stages sequentially."""
        sink = get_sink()
        run_id = context.get("_telemetry_run_id") or new_run_id()
        context["_telemetry_run_id"] = run_id
        model = None
        client = context.get("llm_client")
        if client is not None:
            model = getattr(client, "model", None)

        pipeline_t0 = time.perf_counter()
        sink.record(
            "pipeline_start",
            run_id=run_id,
            command="forge_pipeline",
            status="ok",
            model=model,
            stages=[s.name for s in self.stages if s.name not in self._skipped],
        )

        try:
            for stage in self.stages:
                if stage.name in self._skipped:
                    sink.record(
                        "stage",
                        run_id=run_id,
                        stage=stage.name,
                        status="skipped",
                        model=model,
                    )
                    continue
                t0 = time.perf_counter()
                try:
                    context = stage.run(context)
                except Exception:
                    duration_ms = (time.perf_counter() - t0) * 1000.0
                    sink.record(
                        "stage",
                        run_id=run_id,
                        stage=stage.name,
                        status="error",
                        duration_ms=duration_ms,
                        model=model,
                    )
                    sink.record(
                        "pipeline_end",
                        run_id=run_id,
                        status="error",
                        duration_ms=(time.perf_counter() - pipeline_t0) * 1000.0,
                        model=model,
                        failed_stage=stage.name,
                    )
                    raise
                duration_ms = (time.perf_counter() - t0) * 1000.0
                sink.record(
                    "stage",
                    run_id=run_id,
                    stage=stage.name,
                    status="ok",
                    duration_ms=duration_ms,
                    model=model,
                )

            sink.record(
                "pipeline_end",
                run_id=run_id,
                status="ok",
                duration_ms=(time.perf_counter() - pipeline_t0) * 1000.0,
                model=model,
            )
            return context
        except Exception:
            # pipeline_end already recorded on stage error; re-raise
            raise

    def to_blueprint(self, context: dict[str, Any]) -> AgentBlueprint:
        """Convert pipeline context into an AgentBlueprint."""
        agent_team = context.get("agent_team")
        return AgentBlueprint(
            source_jd=context["jd"],
            extraction=context["extraction"],
            culture=context.get("culture_profile"),
            identity_yaml=context["identity_yaml"],
            skill_file=context.get("skill_file"),
            skill_folder=context.get("skill_folder"),
            coverage_score=context.get("coverage_score", 0.0),
            coverage_gaps=context.get("coverage_gaps", []),
            automation_estimate=context["extraction"].automation_potential,
            agent_team=agent_team.to_dict() if agent_team else None,
        )

    @classmethod
    def default(cls) -> ForgePipeline:
        """Standard pipeline: ingest → extract → map → culture → generate → analyze → team."""
        pipeline = cls()
        pipeline.add_stage(IngestStage())
        pipeline.add_stage(AnonymizeStage())
        pipeline.add_stage(ExtractStage())
        pipeline.add_stage(MethodologyStage())
        pipeline.add_stage(MapStage())
        pipeline.add_stage(CultureStage())
        pipeline.add_stage(GenerateStage())
        pipeline.add_stage(ToolMapStage())
        pipeline.add_stage(AnalyzeStage())
        pipeline.add_stage(TeamComposeStage())
        return pipeline

    @classmethod
    def quick(cls) -> ForgePipeline:
        """Minimal pipeline: ingest -> [anonymize] -> extract -> methodology -> generate -> team."""
        pipeline = cls()
        pipeline.add_stage(IngestStage())
        pipeline.add_stage(AnonymizeStage())
        pipeline.add_stage(ExtractStage())
        pipeline.add_stage(MethodologyStage())
        pipeline.add_stage(GenerateStage())
        pipeline.add_stage(TeamComposeStage())
        return pipeline

    @classmethod
    def deep_analysis(cls) -> ForgePipeline:
        """Deep analysis pipeline with per-skill scoring and priority ranking.

        Runs DeepAnalyzeStage *before* GenerateStage so that per-skill scores
        and gap data are available in the generation context, enabling richer
        personality and skill-file output.
        """
        pipeline = cls()
        pipeline.add_stage(IngestStage())
        pipeline.add_stage(AnonymizeStage())
        pipeline.add_stage(ExtractStage())
        pipeline.add_stage(MethodologyStage())
        pipeline.add_stage(MapStage())
        pipeline.add_stage(CultureStage())
        pipeline.add_stage(DeepAnalyzeStage())
        pipeline.add_stage(GenerateStage())
        pipeline.add_stage(ToolMapStage())
        pipeline.add_stage(TeamComposeStage())
        return pipeline

    @classmethod
    def team(cls) -> ForgePipeline:
        """Team forge: extract once, compose team, forge each member + conductor."""
        pipeline = cls()
        pipeline.add_stage(IngestStage())
        pipeline.add_stage(AnonymizeStage())
        pipeline.add_stage(ExtractStage())
        pipeline.add_stage(MethodologyStage())
        pipeline.add_stage(MapStage())
        pipeline.add_stage(CultureStage())
        pipeline.add_stage(GenerateStage())
        pipeline.add_stage(TeamComposeStage())
        pipeline.add_stage(TeamForgeStage())
        pipeline.add_stage(ConductorGenerateStage())
        pipeline.add_stage(AnalyzeStage())
        return pipeline

    @classmethod
    def openclaw(cls) -> ForgePipeline:
        """Full pipeline with OpenClaw compilation: JD → OpenClaw-ready files."""
        pipeline = cls()
        pipeline.add_stage(IngestStage())
        pipeline.add_stage(AnonymizeStage())
        pipeline.add_stage(ExtractStage())
        pipeline.add_stage(MethodologyStage())
        pipeline.add_stage(MapStage())
        pipeline.add_stage(CultureStage())
        pipeline.add_stage(GenerateStage())
        pipeline.add_stage(ToolMapStage())
        pipeline.add_stage(AnalyzeStage())
        pipeline.add_stage(TeamComposeStage())
        pipeline.add_stage(CronEnrichStage())
        pipeline.add_stage(OpenClawCompileStage())
        return pipeline

    @classmethod
    def personanexus_deployment(cls) -> ForgePipeline:
        """Full pipeline with PersonaNexus deployment package output."""
        pipeline = cls()
        pipeline.add_stage(IngestStage())
        pipeline.add_stage(AnonymizeStage())
        pipeline.add_stage(ExtractStage())
        pipeline.add_stage(MethodologyStage())
        pipeline.add_stage(MapStage())
        pipeline.add_stage(CultureStage())
        pipeline.add_stage(GenerateStage())
        pipeline.add_stage(ToolMapStage())
        pipeline.add_stage(AnalyzeStage())
        pipeline.add_stage(TeamComposeStage())
        pipeline.add_stage(PersonaNexusDeploymentCompileStage())
        return pipeline

    @classmethod
    def cron(cls) -> ForgePipeline:
        """Pipeline for cron/scheduled agents with cron-specific enrichment."""
        pipeline = cls()
        pipeline.add_stage(IngestStage())
        pipeline.add_stage(AnonymizeStage())
        pipeline.add_stage(ExtractStage())
        pipeline.add_stage(MethodologyStage())
        pipeline.add_stage(MapStage())
        pipeline.add_stage(CultureStage())
        pipeline.add_stage(GenerateStage())
        pipeline.add_stage(ToolMapStage())
        pipeline.add_stage(AnalyzeStage())
        pipeline.add_stage(TeamComposeStage())
        pipeline.add_stage(CronEnrichStage())
        return pipeline
