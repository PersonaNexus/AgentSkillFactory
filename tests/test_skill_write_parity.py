"""Skill write-path parity: always use skill_md_with_references when refs exist."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from agentforge.generation.skill_folder import SkillFolderResult
from agentforge.pipeline.batch import BatchProcessor
from agentforge.utils import safe_rel_path


def _folder_with_refs() -> SkillFolderResult:
    return SkillFolderResult(
        skill_name="senior-data-engineer",
        skill_md="---\nname: senior-data-engineer\n---\n# Senior Data Engineer\n\nBody.\n",
        supplementary_files={
            "references/work-examples.md": "# Examples\nSample workflow",
            "templates/report.md": "# Report\nTemplate body",
        },
    )


def test_skill_md_with_references_includes_links() -> None:
    sf = _folder_with_refs()
    md = sf.skill_md_with_references()
    assert "references/work-examples.md" in md or "work-examples" in md
    assert md != sf.skill_md or "References" in md or "references/" in md


def test_batch_writes_skill_with_references(tmp_path: Path) -> None:
    """BatchProcessor must write skill_md_with_references + supplementary files."""
    sf = _folder_with_refs()
    identity = MagicMock()
    identity.metadata.id = "senior-data-engineer"

    pipeline = MagicMock()
    pipeline.run.return_value = {
        "identity": identity,
        "identity_yaml": "name: senior-data-engineer\n",
        "skill_folder": sf,
        "extraction": MagicMock(),
    }
    pipeline.to_blueprint.return_value = MagicMock()

    proc = BatchProcessor(pipeline=pipeline, output_dir=tmp_path)
    result = proc._process_single("jd.txt", {})
    assert result.success, result.error

    skill_md_path = tmp_path / "senior-data-engineer" / "SKILL.md"
    assert skill_md_path.is_file()
    written = skill_md_path.read_text()
    # Must not be bare body without reference section when refs exist
    assert written == sf.skill_md_with_references()

    ref = tmp_path / "senior-data-engineer" / "references" / "work-examples.md"
    assert ref.is_file()
    assert "Sample workflow" in ref.read_text()


def test_safe_rel_path_stays_within_base(tmp_path: Path) -> None:
    """Traversal components are sanitized; result must stay under base_dir."""
    base = tmp_path / "skill"
    base.mkdir()
    target = safe_rel_path(base, "../escape.md")
    assert target.resolve().is_relative_to(base.resolve())
    # absolute path segments are also neutralized via safe_filename
    target2 = safe_rel_path(base, "references/../../etc/passwd")
    assert target2.resolve().is_relative_to(base.resolve())


def test_forged_teammate_dict_uses_references() -> None:
    from agentforge.analysis.team_composer import AgentTeammate
    from agentforge.composition.models import ForgedTeammate
    from agentforge.models.extracted_skills import (
        ExtractedSkill,
        SkillCategory,
        SkillImportance,
        SkillProficiency,
    )

    sf = _folder_with_refs()
    skill = ExtractedSkill(
        name="SQL",
        category=SkillCategory.HARD,
        proficiency=SkillProficiency.ADVANCED,
        importance=SkillImportance.REQUIRED,
        context="Query work",
    )
    teammate = AgentTeammate(
        name="Analyst",
        archetype="Research Analyst",
        arch_key="research_analyst",
        description="Analyzes data",
        skills=[skill],
        personality={"rigor": 0.8},
        benefit="Faster analysis",
    )
    ft = ForgedTeammate(
        teammate=teammate,
        identity_yaml="name: analyst\n",
        skill_folder=sf,
    )
    d = ft.to_dict()
    assert d["skill_folder"]["skill_md"] == sf.skill_md_with_references()
    assert "Reference Files" in d["skill_folder"]["skill_md"]
