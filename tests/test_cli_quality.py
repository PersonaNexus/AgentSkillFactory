"""CLI smoke tests for quality tools and wiki registration."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from agentforge.cli import app

runner = CliRunner()

_MINIMAL_SKILL = """\
---
name: test-skill
description: A minimal skill for CLI quality tests
---

# Test Skill

## Identity
You are a helpful test agent.

## Guardrails
- Never invent credentials
- Refuse harmful requests
"""


def test_prompt_size_cli(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(_MINIMAL_SKILL)
    result = runner.invoke(app, ["prompt-size", str(skill), "--format", "json"])
    assert result.exit_code == 0, result.output
    assert "total_estimated_tokens" in result.output or "estimated" in result.output.lower()


def test_lint_cli(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(_MINIMAL_SKILL)
    result = runner.invoke(app, ["lint", str(skill), "--format", "json"])
    # lint may fail structural checks on minimal skill; command must still run
    assert result.exit_code in (0, 1), result.output
    out = result.output.lower()
    assert "error" in out or "passed" in out or "{" in result.output


def test_cost_cli(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(_MINIMAL_SKILL)
    result = runner.invoke(app, ["cost", str(skill), "--format", "json"])
    assert result.exit_code == 0, result.output


def test_prompt_diff_cli(tmp_path: Path) -> None:
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text(_MINIMAL_SKILL)
    b.write_text(_MINIMAL_SKILL + "\n## Extra\nMore content.\n")
    result = runner.invoke(app, ["prompt-diff", str(a), str(b), "--format", "json"])
    assert result.exit_code == 0, result.output


def test_audit_cli(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(_MINIMAL_SKILL)
    result = runner.invoke(app, ["audit", str(skill), "--format", "json"])
    assert result.exit_code in (0, 1), result.output


def test_quality_commands_registered_once() -> None:
    from typer.main import get_command

    click_app = get_command(app)
    names = list(click_app.commands.keys())
    assert names.count("prompt-size") == 1
    assert names.count("lint") == 1
    assert names.count("cost") == 1
    assert names.count("prompt-diff") == 1
    assert names.count("audit") == 1
    assert "wiki" in names


def test_wiki_cli_help() -> None:
    result = runner.invoke(app, ["wiki", "--help"])
    assert result.exit_code == 0, result.output
    assert "wiki" in result.output.lower() or "init" in result.output.lower()


def test_wiki_init(tmp_path: Path) -> None:
    wiki_root = tmp_path / "wiki"
    # --root may appear before or after the subcommand
    result = runner.invoke(app, ["wiki", "init", "--root", str(wiki_root)])
    assert result.exit_code == 0, result.output
    assert wiki_root.exists() or "Initialized" in result.output

    wiki_root2 = tmp_path / "wiki2"
    result2 = runner.invoke(app, ["wiki", "--root", str(wiki_root2), "init"])
    assert result2.exit_code == 0, result2.output


def test_serve_rejects_public_bind_without_token(monkeypatch) -> None:
    monkeypatch.delenv("AGENTFORGE_API_TOKEN", raising=False)
    monkeypatch.setattr(
        "agentforge.config.load_config",
        lambda: type("C", (), {"web_api_token": None})(),
    )
    # Avoid importing uvicorn path fully — ensure_bind_auth is checked first
    # after uvicorn import. Stub uvicorn as present.
    import sys
    import types

    if "uvicorn" not in sys.modules:
        sys.modules["uvicorn"] = types.ModuleType("uvicorn")
        sys.modules["uvicorn"].run = lambda *a, **k: None  # type: ignore[attr-defined]

    result = runner.invoke(app, ["serve", "--host", "0.0.0.0", "--no-open"])  # noqa: S104
    assert result.exit_code == 1, result.output
    assert "authentication" in result.output.lower() or "API" in result.output
