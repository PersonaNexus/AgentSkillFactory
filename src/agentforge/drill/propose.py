"""Deterministic skill-maintenance proposals from drill scan findings.

Phase 1.0: pure rules, no LLM. Proposals are human-review suggestions written
under ``<skill-dir>/.drill/`` — never applied automatically.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from agentforge.drill.models import ScanReport


class Proposal(BaseModel):
    """One suggested maintenance action."""

    action: str  # e.g. split_body | differentiate_skills | prune_tools | add_skill_md
    priority: str = "medium"  # low | medium | high
    skill: str | None = None
    title: str
    rationale: str
    steps: list[str] = Field(default_factory=list)
    source_finding_kind: str | None = None


class ProposalReport(BaseModel):
    """Output of ``drill propose``."""

    schema_version: str = "1"
    skill_dir: str
    generated_at: datetime
    proposals: list[Proposal] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


_KIND_TO_ACTION: dict[str, tuple[str, str, list[str]]] = {
    # action, title template, steps
    "bloat": (
        "split_body",
        "Split bloated SKILL.md for `{skill}`",
        [
            "Move long procedures into instructions/*.md files",
            "Keep SKILL.md as a thin routing + identity layer",
            "Re-run `drill scan` and confirm body_word_count drops below threshold",
        ],
    ),
    "overlap": (
        "differentiate_skills",
        "Differentiate overlapping skills",
        [
            "Rewrite descriptions so each skill has a unique trigger/when-to-use",
            "Consider merging if they serve the same user intent",
            "Re-run `drill scan --overlap-threshold` after edits",
        ],
    ),
    "missing_file": (
        "add_skill_md",
        "Restore missing SKILL.md for `{skill}`",
        [
            "Add a SKILL.md with name + description frontmatter",
            "Or remove the empty folder if the skill was decommissioned",
        ],
    ),
    "broken_reference": (
        "fix_references",
        "Fix broken path references in `{skill}`",
        [
            "Create the referenced files or update links in SKILL.md",
            "Prefer relative paths within the skill folder",
        ],
    ),
    "tool_sprawl": (
        "prune_tools",
        "Prune allowed-tools for `{skill}`",
        [
            "Remove tools never mentioned in the body",
            "Document remaining tools in the skill instructions",
            "Keep the allow-list tight for safer agent runs",
        ],
    ),
}


def _priority(severity: str) -> str:
    return {"critical": "high", "warn": "medium", "info": "low"}.get(severity, "medium")


def propose_from_scan(report: ScanReport) -> ProposalReport:
    """Map each scan finding to a concrete, reviewable proposal."""
    proposals: list[Proposal] = []
    seen: set[tuple[str, str | None]] = set()

    for finding in report.findings:
        key = (finding.kind, finding.skill)
        if key in seen:
            continue
        seen.add(key)
        mapping = _KIND_TO_ACTION.get(finding.kind)
        if not mapping:
            proposals.append(Proposal(
                action="review",
                priority=_priority(finding.severity),
                skill=finding.skill,
                title=f"Review finding: {finding.kind}",
                rationale=finding.message,
                steps=["Inspect the finding detail and decide whether to act"],
                source_finding_kind=finding.kind,
            ))
            continue
        action, title_tmpl, steps = mapping
        skill = finding.skill or "skill"
        proposals.append(Proposal(
            action=action,
            priority=_priority(finding.severity),
            skill=finding.skill,
            title=title_tmpl.format(skill=skill),
            rationale=finding.message + (f" — {finding.detail}" if finding.detail else ""),
            steps=list(steps),
            source_finding_kind=finding.kind,
        ))

    notes: list[str] = []
    if not proposals:
        notes.append("No scan findings — nothing to propose. Run `drill scan` first if empty.")

    return ProposalReport(
        skill_dir=report.skill_dir,
        generated_at=datetime.now(UTC),
        proposals=proposals,
        notes=notes,
    )


def render_proposals_markdown(report: ProposalReport) -> str:
    lines = [
        f"# drill propose — {report.skill_dir}",
        "",
        f"- Generated at: {report.generated_at.isoformat()}",
        f"- Proposals: {len(report.proposals)}",
        "",
        "> Deterministic suggestions from scan findings. Review before applying — "
        "drill never edits skill sources automatically.",
        "",
    ]
    if report.notes:
        lines.append("## Notes")
        lines.extend(f"- {n}" for n in report.notes)
        lines.append("")

    if not report.proposals:
        lines.append("_No proposals._")
        lines.append("")
        return "\n".join(lines)

    for i, p in enumerate(report.proposals, 1):
        lines.append(f"## {i}. {p.title}")
        lines.append("")
        lines.append(f"- **action:** `{p.action}`")
        lines.append(f"- **priority:** {p.priority}")
        if p.skill:
            lines.append(f"- **skill:** `{p.skill}`")
        if p.source_finding_kind:
            lines.append(f"- **from finding:** `{p.source_finding_kind}`")
        lines.append("")
        lines.append(p.rationale)
        lines.append("")
        if p.steps:
            lines.append("**Suggested steps**")
            for step in p.steps:
                lines.append(f"1. {step}")
            lines.append("")
    return "\n".join(lines)


def write_proposals(report: ProposalReport, skill_dir: Path) -> Path:
    """Write propose-<ts>.md (and .json) under <skill-dir>/.drill/."""
    stamp = report.generated_at.strftime("%Y-%m-%dT%H%M%S")
    out_dir = skill_dir / ".drill"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"propose-{stamp}.md"
    json_path = out_dir / f"propose-{stamp}.json"
    md_path.write_text(render_proposals_markdown(report), encoding="utf-8")
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return md_path
