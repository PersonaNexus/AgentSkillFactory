"""Tests for ``agentforge forge --check`` post-forge quality gate."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from agentforge.cli import app
from agentforge.models.extracted_skills import (
    ExtractedRole,
    ExtractedSkill,
    ExtractionResult,
    SkillCategory,
    SkillProficiency,
    SuggestedTraits,
)

runner = CliRunner()

_GOOD_SKILL = """\
---
name: good-skill
description: A reasonably complete skill for check tests
---

# Good Skill

## Personality Profile
- Rigor 80%

## Key Responsibilities
- Ship reliable software

## Technical Skills
- Python

## Guardrails
- Never invent credentials
- Stay within domain scope
"""


def _extraction() -> ExtractionResult:
    return ExtractionResult(
        role=ExtractedRole(
            title="Reliability Engineer",
            purpose="Keep agent workflows predictable",
            scope_primary=["Test automation", "Release gates"],
            audience=["Developers"],
            seniority="senior",
            domain="engineering",
        ),
        skills=[
            ExtractedSkill(
                name="Python",
                category=SkillCategory.HARD,
                proficiency=SkillProficiency.ADVANCED,
                importance="required",
                context="Build deterministic tests",
            )
        ],
        responsibilities=["Build tests", "Maintain CI"],
        suggested_traits=SuggestedTraits(rigor=0.9),
        automation_potential=0.6,
        automation_rationale="Well-scoped automation work",
    )


def _mock_pipeline(*, skill_file: str = _GOOD_SKILL) -> MagicMock:
    identity = SimpleNamespace(metadata=SimpleNamespace(id="reliability-engineer"))
    blueprint = SimpleNamespace(coverage_score=0.75, automation_estimate=0.6)
    pipeline = MagicMock()
    pipeline.run.return_value = {
        "extraction": _extraction(),
        "identity": identity,
        "identity_yaml": "schema_version: '1.0'\n",
        "skill_file": skill_file,
    }
    pipeline.to_blueprint.return_value = blueprint
    return pipeline


def test_forge_always_prints_next_steps(tmp_path):
    jd_file = tmp_path / "job.txt"
    jd_file.write_text("Reliability Engineer\nRequirements: Python, CI")
    pipeline = _mock_pipeline()

    with (
        patch("agentforge.cli._make_client", return_value=MagicMock()),
        patch("agentforge.pipeline.forge_pipeline.ForgePipeline.quick", return_value=pipeline),
    ):
        result = runner.invoke(
            app,
            ["forge", str(jd_file), "--quick", "--output-dir", str(tmp_path)],
        )

    assert result.exit_code == 0, result.output
    assert "forged successfully" in result.output
    assert "Next steps" in result.output or "Next:" in result.output
    assert "agentforge check" in result.output
    assert "agentforge identity validate" in result.output
    assert ".claude/skills/" in result.output


def test_forge_check_runs_skill_checker_on_written_skill(tmp_path):
    jd_file = tmp_path / "job.txt"
    jd_file.write_text("Reliability Engineer\nRequirements: Python, CI")
    pipeline = _mock_pipeline()
    mock_report = MagicMock()
    mock_report.passed = True
    mock_report.summary_lines.return_value = [
        "lint: PASS (0 errors, 0 warnings)",
        "size: LEAN (~100 tokens)",
        "audit: PASS (score 100%, 0 failed checks)",
    ]
    mock_checker = MagicMock()
    mock_checker.check_paths.return_value = mock_report

    with (
        patch("agentforge.cli._make_client", return_value=MagicMock()),
        patch("agentforge.pipeline.forge_pipeline.ForgePipeline.quick", return_value=pipeline),
        patch(
            "agentforge.analysis.skill_check.SkillChecker",
            return_value=mock_checker,
        ) as checker_cls,
    ):
        result = runner.invoke(
            app,
            [
                "forge",
                str(jd_file),
                "--quick",
                "--check",
                "--check-domain",
                "engineering",
                "--output-dir",
                str(tmp_path),
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Skill Check" in result.output
    assert "PASSED" in result.output
    checker_cls.assert_called_once_with(domain="engineering")
    mock_checker.check_paths.assert_called_once()
    call_kwargs = mock_checker.check_paths.call_args
    skill_arg = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("skill_file")
    assert skill_arg is not None
    assert skill_arg.name.endswith("_SKILL.md") or skill_arg.name == "SKILL.md"
    assert skill_arg.exists()
    identity_file = call_kwargs.kwargs.get("identity_file")
    assert identity_file is not None
    assert identity_file.name == "reliability-engineer.yaml"
    assert call_kwargs.kwargs.get("strict") is False


def test_forge_check_exit_code_1_when_check_fails(tmp_path):
    jd_file = tmp_path / "job.txt"
    jd_file.write_text("Reliability Engineer\nRequirements: Python, CI")
    pipeline = _mock_pipeline()
    mock_report = MagicMock()
    mock_report.passed = False
    mock_report.summary_lines.return_value = [
        "lint: FAIL (2 errors, 0 warnings)",
        "size: LEAN (~100 tokens)",
        "audit: PASS (score 100%, 0 failed checks)",
    ]
    mock_checker = MagicMock()
    mock_checker.check_paths.return_value = mock_report

    with (
        patch("agentforge.cli._make_client", return_value=MagicMock()),
        patch("agentforge.pipeline.forge_pipeline.ForgePipeline.quick", return_value=pipeline),
        patch(
            "agentforge.analysis.skill_check.SkillChecker",
            return_value=mock_checker,
        ),
    ):
        result = runner.invoke(
            app,
            [
                "forge",
                str(jd_file),
                "--quick",
                "--check",
                "--output-dir",
                str(tmp_path),
            ],
        )

    # Forge wrote files, but --check failure exits 1.
    assert result.exit_code == 1, result.output
    assert "forged successfully" in result.output
    assert "FAILED" in result.output
    assert (tmp_path / "reliability-engineer_SKILL.md").exists()
    # Next steps still printed after successful forge write.
    assert "agentforge check" in result.output


def test_forge_check_strict_implies_check(tmp_path):
    jd_file = tmp_path / "job.txt"
    jd_file.write_text("Reliability Engineer\nRequirements: Python, CI")
    pipeline = _mock_pipeline()
    mock_report = MagicMock()
    mock_report.passed = True
    mock_report.summary_lines.return_value = ["lint: PASS (0 errors, 0 warnings)"]
    mock_checker = MagicMock()
    mock_checker.check_paths.return_value = mock_report

    with (
        patch("agentforge.cli._make_client", return_value=MagicMock()),
        patch("agentforge.pipeline.forge_pipeline.ForgePipeline.quick", return_value=pipeline),
        patch(
            "agentforge.analysis.skill_check.SkillChecker",
            return_value=mock_checker,
        ),
    ):
        result = runner.invoke(
            app,
            [
                "forge",
                str(jd_file),
                "--quick",
                "--check-strict",
                "--output-dir",
                str(tmp_path),
            ],
        )

    assert result.exit_code == 0, result.output
    mock_checker.check_paths.assert_called_once()
    assert mock_checker.check_paths.call_args.kwargs.get("strict") is True


def test_forge_check_prefers_skill_folder_skill_md(tmp_path):
    jd_file = tmp_path / "job.txt"
    jd_file.write_text("Reliability Engineer\nRequirements: Python, CI")

    identity = SimpleNamespace(metadata=SimpleNamespace(id="reliability-engineer"))
    blueprint = SimpleNamespace(coverage_score=0.75, automation_estimate=0.6)
    sf = MagicMock()
    sf.skill_name = "reliability-engineer"
    sf.skill_md_with_references.return_value = _GOOD_SKILL
    sf.supplementary_files = {}
    pipeline = MagicMock()
    pipeline.run.return_value = {
        "extraction": _extraction(),
        "identity": identity,
        "identity_yaml": "schema_version: '1.0'\n",
        "skill_file": "# profile\n",
        "skill_folder": sf,
    }
    pipeline.to_blueprint.return_value = blueprint

    mock_report = MagicMock()
    mock_report.passed = True
    mock_report.summary_lines.return_value = ["lint: PASS (0 errors, 0 warnings)"]
    mock_checker = MagicMock()
    mock_checker.check_paths.return_value = mock_report

    with (
        patch("agentforge.cli._make_client", return_value=MagicMock()),
        patch("agentforge.pipeline.forge_pipeline.ForgePipeline.quick", return_value=pipeline),
        patch(
            "agentforge.analysis.skill_check.SkillChecker",
            return_value=mock_checker,
        ),
    ):
        result = runner.invoke(
            app,
            [
                "forge",
                str(jd_file),
                "--quick",
                "--skill-folder",
                "--check",
                "--output-dir",
                str(tmp_path),
            ],
        )

    assert result.exit_code == 0, result.output
    mock_checker.check_paths.assert_called_once()
    skill_arg = mock_checker.check_paths.call_args.args[0]
    assert skill_arg.name == "SKILL.md"
    assert skill_arg.parent.name == "reliability-engineer"
    # Prefer skill-folder path over profile *_SKILL.md
    assert (tmp_path / "reliability-engineer" / "SKILL.md").is_file()
    assert "agentforge check" in result.output
    assert "Next" in result.output


def test_forge_check_skips_when_no_skill_file(tmp_path):
    jd_file = tmp_path / "job.txt"
    jd_file.write_text("Reliability Engineer\nRequirements: Python, CI")

    identity = SimpleNamespace(metadata=SimpleNamespace(id="reliability-engineer"))
    blueprint = SimpleNamespace(coverage_score=0.75, automation_estimate=0.6)
    pipeline = MagicMock()
    pipeline.run.return_value = {
        "extraction": _extraction(),
        "identity": identity,
        "identity_yaml": "schema_version: '1.0'\n",
        # no skill_file
    }
    pipeline.to_blueprint.return_value = blueprint

    with (
        patch("agentforge.cli._make_client", return_value=MagicMock()),
        patch("agentforge.pipeline.forge_pipeline.ForgePipeline.quick", return_value=pipeline),
        patch("agentforge.analysis.skill_check.SkillChecker") as checker_cls,
    ):
        result = runner.invoke(
            app,
            [
                "forge",
                str(jd_file),
                "--quick",
                "--no-skill-file",
                "--check",
                "--output-dir",
                str(tmp_path),
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Skipping check" in result.output
    checker_cls.assert_not_called()
    # Next steps still printed (placeholder path).
    assert "agentforge check" in result.output
