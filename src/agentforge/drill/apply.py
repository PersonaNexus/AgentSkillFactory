"""Human-gated application of drill proposals.

Only mechanical, reversible-ish edits are applied automatically:

- ``prune_tools`` — drop allowed-tools not referenced in the body
- ``add_skill_md`` — create a minimal SKILL.md stub for empty folders
- ``fix_references`` — create stub files for broken relative references

Actions that need design judgment (``split_body``, ``differentiate_skills``,
``review``) are **never** auto-applied; they are reported as skipped with steps.

Never runs without an explicit apply call. Callers must pass ``confirm=True``
(CLI ``--yes``) or provide an interactive confirm callback.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from agentforge.day2.frontmatter import split_frontmatter
from agentforge.drill.ingest import discover_skill_folders, ingest_skill_folder
from agentforge.drill.propose import Proposal, ProposalReport

# Actions that have a mechanical implementation.
APPLYABLE_ACTIONS = frozenset({"prune_tools", "add_skill_md", "fix_references"})


class ApplyResult(BaseModel):
    """Outcome of applying one proposal."""

    action: str
    skill: str | None = None
    title: str
    status: str  # applied | skipped | failed | declined
    detail: str = ""
    paths_touched: list[str] = Field(default_factory=list)


class ApplyReport(BaseModel):
    """Summary of a drill apply run."""

    schema_version: str = "1"
    skill_dir: str
    applied_at: datetime
    results: list[ApplyResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def applied_count(self) -> int:
        return sum(1 for r in self.results if r.status == "applied")

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.status in ("skipped", "declined"))


def load_proposal_report(path: Path) -> ProposalReport:
    """Load a propose-*.json written by ``drill propose``."""
    return ProposalReport.model_validate_json(path.read_text(encoding="utf-8"))


def latest_propose_json(skill_dir: Path) -> Path | None:
    """Return newest propose-*.json under <skill-dir>/.drill/, if any."""
    drill = skill_dir / ".drill"
    if not drill.is_dir():
        return None
    files = sorted(drill.glob("propose-*.json"))
    return files[-1] if files else None


def _skill_folder(skill_dir: Path, slug: str | None) -> Path | None:
    """Resolve a skill folder path under *skill_dir* (single or parent layout)."""
    skill_dir = skill_dir.resolve()

    def confined(folder: Path) -> Path | None:
        """Return the resolved folder only when it stays below skill_dir."""
        resolved = folder.resolve()
        try:
            resolved.relative_to(skill_dir)
        except ValueError:
            return None
        return resolved

    # Single-skill layout: SKILL.md lives at the root.
    if (skill_dir / "SKILL.md").is_file():
        return skill_dir
    if slug is None:
        folders = [
            resolved
            for folder in discover_skill_folders(skill_dir)
            if (resolved := confined(folder)) is not None
        ]
        return folders[0] if len(folders) == 1 else None
    candidate = confined(skill_dir / slug)
    if candidate is not None and candidate.is_dir():
        return candidate
    for folder in discover_skill_folders(skill_dir):
        resolved = confined(folder)
        if resolved is not None and folder.name == slug:
            return resolved
    return None


def _rewrite_allowed_tools(skill_md: str, keep: list[str]) -> str:
    """Replace allowed-tools frontmatter with *keep* list."""
    fm, body, _notes = split_frontmatter(skill_md)
    fm.pop("allowed-tools", None)
    fm.pop("allowed_tools", None)
    if keep:
        fm["allowed-tools"] = ", ".join(keep)

    serialized = yaml.safe_dump(
        fm,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip("\n")
    return f"---\n{serialized}\n---\n\n{body.lstrip(chr(10))}"


def apply_prune_tools(skill_folder: Path) -> ApplyResult:
    skill_md_path = skill_folder / "SKILL.md"
    if not skill_md_path.is_file():
        return ApplyResult(
            action="prune_tools",
            skill=skill_folder.name,
            title="Prune tools",
            status="failed",
            detail="SKILL.md missing",
        )
    digest = ingest_skill_folder(skill_folder, skill_folder.parent)

    keep = [t for t in digest.allowed_tools if t in digest.declared_tools_in_body]
    # If nothing would remain but tools were declared, keep tools that appear in body only
    if not keep and digest.allowed_tools:
        # still prune all unused; empty allow-list is valid
        pass
    removed = [t for t in digest.allowed_tools if t not in keep]
    if not removed:
        return ApplyResult(
            action="prune_tools",
            skill=skill_folder.name,
            title="Prune tools",
            status="skipped",
            detail="no unused tools to remove",
        )

    raw = skill_md_path.read_text(encoding="utf-8")
    new_text = _rewrite_allowed_tools(raw, keep)
    skill_md_path.write_text(new_text, encoding="utf-8")
    return ApplyResult(
        action="prune_tools",
        skill=skill_folder.name,
        title="Prune tools",
        status="applied",
        detail=f"removed: {', '.join(removed)}; kept: {', '.join(keep) or '(none)'}",
        paths_touched=[str(skill_md_path)],
    )


def apply_add_skill_md(skill_folder: Path) -> ApplyResult:
    skill_md_path = skill_folder / "SKILL.md"
    if skill_md_path.is_file():
        return ApplyResult(
            action="add_skill_md",
            skill=skill_folder.name,
            title="Add SKILL.md",
            status="skipped",
            detail="SKILL.md already exists",
        )
    skill_folder.mkdir(parents=True, exist_ok=True)
    name = skill_folder.name
    content = (
        f"---\n"
        f"name: {name}\n"
        f'description: "TODO: describe when to use the {name} skill"\n'
        f"---\n\n"
        f"# {name.replace('-', ' ').title()}\n\n"
        f"## Identity\n\n"
        f"You are the `{name}` skill. Fill in role guidance.\n\n"
        f"## Guardrails\n\n"
        f"- Never fabricate facts; state uncertainty explicitly.\n"
        f"- Stay within scope; escalate to a human when needed.\n"
        f"- Never generate harmful or unethical content.\n"
    )
    skill_md_path.write_text(content, encoding="utf-8")
    return ApplyResult(
        action="add_skill_md",
        skill=name,
        title="Add SKILL.md",
        status="applied",
        detail="created minimal SKILL.md stub — edit description before use",
        paths_touched=[str(skill_md_path)],
    )


def apply_fix_references(skill_folder: Path) -> ApplyResult:
    skill_md_path = skill_folder / "SKILL.md"
    if not skill_md_path.is_file():
        return ApplyResult(
            action="fix_references",
            skill=skill_folder.name,
            title="Fix references",
            status="failed",
            detail="SKILL.md missing",
        )
    digest = ingest_skill_folder(skill_folder, skill_folder.parent)

    created: list[str] = []
    for rel in digest.referenced_files:
        # only create safe relative paths without traversal
        if ".." in Path(rel).parts or rel.startswith(("/", "\\")):
            continue
        target = (skill_folder / rel).resolve()
        try:
            target.relative_to(skill_folder.resolve())
        except ValueError:
            continue
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"# {Path(rel).stem}\n\n"
            f"_Stub created by `drill apply fix_references`. "
            f"Replace with real content referenced from SKILL.md._\n",
            encoding="utf-8",
        )
        created.append(str(target))

    if not created:
        return ApplyResult(
            action="fix_references",
            skill=skill_folder.name,
            title="Fix references",
            status="skipped",
            detail="no missing relative references to stub",
        )
    return ApplyResult(
        action="fix_references",
        skill=skill_folder.name,
        title="Fix references",
        status="applied",
        detail=f"created {len(created)} stub file(s)",
        paths_touched=created,
    )


_APPLIERS = {
    "prune_tools": apply_prune_tools,
    "add_skill_md": apply_add_skill_md,
    "fix_references": apply_fix_references,
}


def apply_proposals(
    skill_dir: Path,
    report: ProposalReport,
    *,
    confirm: bool = False,
    only_actions: set[str] | None = None,
    confirm_fn: Callable[[Proposal], bool] | None = None,
) -> ApplyReport:
    """Apply mechanical proposals under human gate.

    Parameters
    ----------
    confirm:
        If True, apply without per-item prompts (CLI ``--yes``).
    only_actions:
        Optional subset of action names to consider.
    confirm_fn:
        Optional ``(Proposal) -> bool`` for interactive confirmation.
        Used when ``confirm`` is False.
    """
    skill_dir = skill_dir.expanduser().resolve()
    results: list[ApplyResult] = []
    notes: list[str] = []

    for proposal in report.proposals:
        if only_actions and proposal.action not in only_actions:
            continue
        if proposal.action not in APPLYABLE_ACTIONS:
            results.append(ApplyResult(
                action=proposal.action,
                skill=proposal.skill,
                title=proposal.title,
                status="skipped",
                detail="not mechanically applyable — follow steps manually",
            ))
            continue

        # Resolve and confine the proposal target before asking the operator to
        # approve it.  A confirmation prompt must never lend legitimacy to a
        # crafted path that would later be rejected (traversal, absolute paths,
        # or symlinks escaping the skill root).
        folder = _skill_folder(skill_dir, proposal.skill)
        if folder is None:
            results.append(ApplyResult(
                action=proposal.action,
                skill=proposal.skill,
                title=proposal.title,
                status="failed",
                detail=f"could not resolve skill folder for {proposal.skill!r}",
            ))
            continue

        if not confirm:
            if confirm_fn is None:
                results.append(ApplyResult(
                    action=proposal.action,
                    skill=proposal.skill,
                    title=proposal.title,
                    status="declined",
                    detail="pass confirm=True / --yes to apply without interactive confirm",
                ))
                continue
            if not confirm_fn(proposal):
                results.append(ApplyResult(
                    action=proposal.action,
                    skill=proposal.skill,
                    title=proposal.title,
                    status="declined",
                    detail="user declined",
                ))
                continue

        applier = _APPLIERS[proposal.action]
        results.append(applier(folder))

    if not any(r.status == "applied" for r in results):
        notes.append("No mechanical changes applied.")
    notes.append(
        "Re-run `drill scan` and `drill propose` after reviewing edits."
    )

    return ApplyReport(
        skill_dir=str(skill_dir),
        applied_at=datetime.now(UTC),
        results=results,
        notes=notes,
    )


def write_apply_report(report: ApplyReport, skill_dir: Path) -> Path:
    out_dir = skill_dir / ".drill"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = report.applied_at.strftime("%Y-%m-%dT%H%M%S")
    path = out_dir / f"apply-{stamp}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path
