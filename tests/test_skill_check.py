"""Tests for unified skill check library and CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from agentforge.analysis.skill_check import (
    SkillChecker,
    validate_identity_yaml,
    validate_skill_folder,
)
from agentforge.cli import app

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


def test_checker_on_minimal_skill() -> None:
    report = SkillChecker().check(_GOOD_SKILL)
    assert report.lint is not None
    assert report.size.total_estimated_tokens > 0
    assert report.audit is not None


def test_validate_skill_folder_missing(tmp_path: Path) -> None:
    problems = validate_skill_folder(tmp_path)
    assert any("SKILL.md" in p for p in problems)


def test_validate_skill_folder_ok(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text(_GOOD_SKILL)
    for rel in (
        "instructions/scope.md",
        "instructions/methodology.md",
        "instructions/voice.md",
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# x\n")
    assert validate_skill_folder(tmp_path) == []


def test_validate_identity_invalid() -> None:
    ok, msg = validate_identity_yaml("not: a: identity: structure")
    # may fail parse or validation
    assert ok is False
    assert msg


def test_check_cli(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(_GOOD_SKILL)
    result = runner.invoke(app, ["check", str(skill), "--format", "json"])
    assert result.exit_code in (0, 1), result.output
    assert "lint" in result.output


def test_check_cli_folder(tmp_path: Path) -> None:
    folder = tmp_path / "my-skill"
    folder.mkdir()
    (folder / "SKILL.md").write_text(_GOOD_SKILL)
    result = runner.invoke(app, ["check", str(folder)])
    assert result.exit_code in (0, 1), result.output


def test_identity_validate_cli(tmp_path: Path) -> None:
    # Use the public example if present; otherwise a minimal invalid file
    example = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "senior-data-engineer"
        / "output"
        / "identity.yaml"
    )
    if example.is_file():
        result = runner.invoke(app, ["identity", "validate", str(example)])
        assert result.exit_code == 0, result.output
    else:
        bad = tmp_path / "bad.yaml"
        bad.write_text("foo: bar\n")
        result = runner.invoke(app, ["identity", "validate", str(bad)])
        assert result.exit_code == 1
