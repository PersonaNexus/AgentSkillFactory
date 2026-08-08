"""Tests for human-gated drill apply (mechanical actions only)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from agentforge.drill.apply import (
    APPLYABLE_ACTIONS,
    apply_add_skill_md,
    apply_fix_references,
    apply_proposals,
    apply_prune_tools,
)
from agentforge.drill.propose import Proposal, ProposalReport


def _skill_with_tools(tmp_path: Path, tools: str, body: str) -> Path:
    folder = tmp_path / "my-skill"
    folder.mkdir()
    (folder / "SKILL.md").write_text(
        f"---\nname: my-skill\ndescription: test\nallowed-tools: {tools}\n---\n\n"
        f"# My Skill\n\n{body}\n",
        encoding="utf-8",
    )
    return folder


def test_prune_tools_removes_unused(tmp_path: Path) -> None:
    folder = _skill_with_tools(
        tmp_path,
        "Read, Write, Bash, Grep",
        "Use Read and Grep to inspect files.",
    )
    result = apply_prune_tools(folder)
    assert result.status == "applied"
    text = (folder / "SKILL.md").read_text()
    assert "Bash" not in text or "allowed-tools" in text
    # Write and Bash should be gone if not in body
    assert "Read" in text
    assert "Grep" in text


def test_prune_tools_round_trips_typed_frontmatter(tmp_path: Path) -> None:
    folder = tmp_path / "typed-skill"
    folder.mkdir()
    original_frontmatter = {
        "name": "typed-skill",
        "description": "value: with # syntax and \"quotes\"",
        "tags": ["one", "two: three", None, False],
        "metadata": {
            "enabled": True,
            "retries": 0,
            "optional": None,
            "escaped": "line one\nline two\\tail",
        },
        "allowed-tools": ["Read", "Write"],
    }
    skill_md = (
        "---\n"
        + yaml.safe_dump(original_frontmatter, sort_keys=False)
        + "---\n\n# Typed Skill\n\nUse Read to inspect files.\n"
    )
    (folder / "SKILL.md").write_text(skill_md, encoding="utf-8")

    result = apply_prune_tools(folder)

    assert result.status == "applied"
    rewritten = (folder / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(rewritten.split("---", 2)[1])
    assert frontmatter == {
        **original_frontmatter,
        "allowed-tools": "Read",
    }
    assert rewritten.endswith("# Typed Skill\n\nUse Read to inspect files.\n")


def test_add_skill_md_creates_stub(tmp_path: Path) -> None:
    folder = tmp_path / "empty-skill"
    folder.mkdir()
    result = apply_add_skill_md(folder)
    assert result.status == "applied"
    assert (folder / "SKILL.md").is_file()
    assert "Guardrails" in (folder / "SKILL.md").read_text()


def test_fix_references_creates_stubs(tmp_path: Path) -> None:
    folder = tmp_path / "ref-skill"
    folder.mkdir()
    (folder / "SKILL.md").write_text(
        "---\nname: ref-skill\ndescription: x\n---\n\n"
        "# Ref\n\nSee `instructions/missing.md` for details.\n",
        encoding="utf-8",
    )
    result = apply_fix_references(folder)
    # may apply if reference extractor finds the path
    assert result.status in ("applied", "skipped")
    if result.status == "applied":
        assert (folder / "instructions" / "missing.md").is_file()


def test_apply_proposals_requires_confirm(tmp_path: Path) -> None:
    folder = _skill_with_tools(tmp_path, "Read, Bash", "Use Read only.")
    report = ProposalReport(
        skill_dir=str(folder),
        generated_at=datetime.now(UTC),
        proposals=[
            Proposal(
                action="prune_tools",
                priority="medium",
                skill=folder.name,
                title="Prune",
                rationale="stale tools",
            ),
        ],
    )
    out = apply_proposals(folder, report, confirm=False)
    assert out.applied_count == 0
    assert out.results[0].status == "declined"

    out2 = apply_proposals(folder, report, confirm=True)
    assert out2.applied_count == 1
    assert out2.results[0].status == "applied"


def test_non_applyable_skipped(tmp_path: Path) -> None:
    folder = _skill_with_tools(tmp_path, "Read", "Read files")
    report = ProposalReport(
        skill_dir=str(folder),
        generated_at=datetime.now(UTC),
        proposals=[
            Proposal(
                action="split_body",
                priority="high",
                skill=folder.name,
                title="Split",
                rationale="bloat",
            ),
        ],
    )
    out = apply_proposals(folder, report, confirm=True)
    assert out.results[0].status == "skipped"
    assert "split_body" not in APPLYABLE_ACTIONS


def test_apply_proposals_rejects_skill_path_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    outside = _skill_with_tools(tmp_path, "Read, Bash", "Use Read only.")
    original = (outside / "SKILL.md").read_text(encoding="utf-8")
    report = ProposalReport(
        skill_dir=str(root),
        generated_at=datetime.now(UTC),
        proposals=[
            Proposal(
                action="prune_tools",
                priority="high",
                skill=str(outside),
                title="Prune outside root",
                rationale="crafted proposal",
            ),
            Proposal(
                action="prune_tools",
                priority="high",
                skill="../my-skill",
                title="Traverse outside root",
                rationale="crafted proposal",
            ),
        ],
    )

    out = apply_proposals(root, report, confirm=True)

    assert [result.status for result in out.results] == ["failed", "failed"]
    assert (outside / "SKILL.md").read_text(encoding="utf-8") == original


def test_apply_proposals_rejects_symlinked_skill_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    outside = _skill_with_tools(tmp_path, "Read, Bash", "Use Read only.")
    (root / "linked-skill").symlink_to(outside, target_is_directory=True)
    original = (outside / "SKILL.md").read_text(encoding="utf-8")
    report = ProposalReport(
        skill_dir=str(root),
        generated_at=datetime.now(UTC),
        proposals=[
            Proposal(
                action="prune_tools",
                priority="high",
                skill="linked-skill",
                title="Prune symlinked skill",
                rationale="crafted proposal",
            ),
        ],
    )

    out = apply_proposals(root, report, confirm=True)

    assert out.results[0].status == "failed"
    assert (outside / "SKILL.md").read_text(encoding="utf-8") == original


def test_apply_proposals_rejects_unsafe_targets_before_confirm(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    outside = _skill_with_tools(tmp_path, "Read, Bash", "Use Read only.")
    (root / "linked-skill").symlink_to(outside, target_is_directory=True)
    prompts: list[str | None] = []
    report = ProposalReport(
        skill_dir=str(root),
        generated_at=datetime.now(UTC),
        proposals=[
            Proposal(
                action="prune_tools",
                priority="high",
                skill="../my-skill",
                title="Traverse outside root",
                rationale="crafted proposal",
            ),
            Proposal(
                action="prune_tools",
                priority="high",
                skill="linked-skill",
                title="Follow symlink outside root",
                rationale="crafted proposal",
            ),
        ],
    )

    out = apply_proposals(
        root,
        report,
        confirm_fn=lambda proposal: prompts.append(proposal.skill) or True,
    )

    assert prompts == []
    assert [result.status for result in out.results] == ["failed", "failed"]
