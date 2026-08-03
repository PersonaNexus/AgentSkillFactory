"""Unit tests for the MCP server surface (no live LLM, no MCP SDK required for most)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentforge.mcp_server import (
    _ALLOWED_MCP_EXTENSIONS,
    ExtractInput,
    ForgeFileInput,
    ForgeInput,
    _context_to_result,
    _do_extract,
    _do_forge,
    _do_forge_file,
    _text_to_jd,
)
from agentforge.models.extracted_skills import (
    ExtractedRole,
    ExtractedSkill,
    ExtractionResult,
    SkillCategory,
    SkillProficiency,
    SuggestedTraits,
)


def _extraction() -> ExtractionResult:
    return ExtractionResult(
        role=ExtractedRole(
            title="Platform Engineer",
            purpose="Keep systems reliable",
            scope_primary=["CI", "Observability"],
            audience=["Engineers"],
            seniority="senior",
            domain="engineering",
        ),
        skills=[
            ExtractedSkill(
                name="Python",
                category=SkillCategory.HARD,
                proficiency=SkillProficiency.ADVANCED,
                importance="required",
                context="Automation",
            )
        ],
        responsibilities=["Build pipelines"],
        suggested_traits=SuggestedTraits(rigor=0.8),
        automation_potential=0.5,
        automation_rationale="Repeatable ops",
    )


class TestInputSchemas:
    def test_extract_input_defaults(self) -> None:
        inp = ExtractInput(jd_text="Role: engineer")
        assert "claude" in inp.model or "gpt" in inp.model or inp.model

    def test_forge_input_flags(self) -> None:
        inp = ForgeInput(jd_text="x", quick=True, deep=False)
        assert inp.quick is True
        assert inp.deep is False

    def test_forge_file_input(self) -> None:
        inp = ForgeFileInput(jd_path="job.txt")
        assert inp.jd_path.endswith("job.txt")


class TestHelpers:
    def test_text_to_jd(self) -> None:
        jd = _text_to_jd("Senior Engineer\nBuild things")
        assert "Build things" in jd.raw_text
        assert jd.sections

    def test_allowed_extensions(self) -> None:
        assert ".txt" in _ALLOWED_MCP_EXTENSIONS
        assert ".pdf" in _ALLOWED_MCP_EXTENSIONS
        assert ".py" not in _ALLOWED_MCP_EXTENSIONS

    def test_context_to_result_minimal(self) -> None:
        result = _context_to_result({"extraction": _extraction()})
        assert "extraction" in result
        assert result["extraction"]["role"]["title"] == "Platform Engineer"

    def test_context_to_result_with_skill_folder(self) -> None:
        sf = MagicMock()
        sf.skill_name = "platform-engineer"
        sf.skill_md_with_references.return_value = "# skill"
        sf.supplementary_files = {"instructions/scope.md": "# scope"}
        result = _context_to_result({
            "extraction": _extraction(),
            "identity_yaml": "role: x",
            "skill_folder": sf,
            "coverage_score": 0.9,
            "coverage_gaps": [],
        })
        assert result["skill_folder"]["skill_name"] == "platform-engineer"
        assert result["coverage_score"] == 0.9


class TestDoExtract:
    def test_extract_mocked(self) -> None:
        extractor = MagicMock()
        extractor.extract.return_value = _extraction()
        client = MagicMock()
        with (
            patch("agentforge.mcp_server._make_client", return_value=client),
            patch(
                "agentforge.extraction.skill_extractor.SkillExtractor",
                return_value=extractor,
            ),
        ):
            out = _do_extract({"jd_text": "Platform Engineer\nRequirements: Python"})
        assert out["role"]["title"] == "Platform Engineer"
        extractor.extract.assert_called_once()


class TestDoForge:
    def test_forge_quick_skips_ingest(self) -> None:
        extraction = _extraction()
        pipeline = MagicMock()
        pipeline.run.side_effect = lambda ctx: {
            **ctx,
            "extraction": extraction,
            "identity_yaml": "id: test",
        }
        pipeline.skip_stage = MagicMock()
        client = MagicMock()

        with (
            patch("agentforge.mcp_server._make_client", return_value=client),
            patch(
                "agentforge.pipeline.forge_pipeline.ForgePipeline.quick",
                return_value=pipeline,
            ),
        ):
            out = _do_forge({"jd_text": "Engineer role", "quick": True})

        pipeline.skip_stage.assert_called_with("ingest")
        assert out["extraction"]["role"]["title"] == "Platform Engineer"
        assert out["identity_yaml"] == "id: test"


class TestDoForgeFile:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            _do_forge_file({"jd_path": str(tmp_path / "nope.txt")})

    def test_rejects_bad_extension(self, tmp_path: Path) -> None:
        bad = tmp_path / "code.py"
        bad.write_text("print('hi')")
        with pytest.raises(ValueError, match="Unsupported file type"):
            _do_forge_file({"jd_path": str(bad)})

    def test_forge_file_ok(self, tmp_path: Path) -> None:
        jd = tmp_path / "job.txt"
        jd.write_text("Platform Engineer\nPython required")
        extraction = _extraction()
        pipeline = MagicMock()
        pipeline.run.side_effect = lambda ctx: {
            **ctx,
            "extraction": extraction,
            "identity_yaml": "id: file",
        }
        client = MagicMock()
        with (
            patch("agentforge.mcp_server._make_client", return_value=client),
            patch(
                "agentforge.pipeline.forge_pipeline.ForgePipeline.default",
                return_value=pipeline,
            ),
        ):
            out = _do_forge_file({"jd_path": str(jd)})
        assert out["identity_yaml"] == "id: file"


class TestEnsureMcp:
    def test_ensure_mcp_exits_without_sdk(self) -> None:
        import builtins

        import agentforge.mcp_server as mod

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "mcp" or (isinstance(name, str) and name.startswith("mcp.")):
                raise ImportError("missing")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            with pytest.raises(SystemExit) as e:
                mod._ensure_mcp()
            assert e.value.code == 1
