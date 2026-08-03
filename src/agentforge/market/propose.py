"""Deterministic market→agent proposals from gap analysis.

No LLM. Emits reviewable actions for skills the market demands but the agent
lacks (and optional cleanup for agent-only skills).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from agentforge.market.gap import GapReport


class MarketProposal(BaseModel):
    action: str  # add_coverage | review_stale | reinforce
    priority: str = "medium"
    skill: str
    title: str
    rationale: str
    steps: list[str] = Field(default_factory=list)


class MarketProposalReport(BaseModel):
    schema_version: str = "1"
    corpus_root: str
    agent_skill_dir: str
    generated_at: datetime
    coverage_score: float
    proposals: list[MarketProposal] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _priority(sev: str) -> str:
    return {"critical": "high", "warn": "medium", "info": "low"}.get(sev, "medium")


def propose_from_gap(report: GapReport, *, max_market_only: int = 25) -> MarketProposalReport:
    """Turn gap rows into prioritized maintenance proposals."""
    proposals: list[MarketProposal] = []

    # Highest impact first: critical/warn market gaps
    market_sorted = sorted(
        report.market_only,
        key=lambda g: ({"critical": 0, "warn": 1, "info": 2}.get(g.severity, 3), -g.role_count),
    )
    for g in market_sorted[:max_market_only]:
        proposals.append(MarketProposal(
            action="add_coverage",
            priority=_priority(g.severity),
            skill=g.canonical_name,
            title=f"Add coverage for market skill `{g.canonical_name}`",
            rationale=(
                f"Demanded by {g.role_count} corpus role(s) "
                f"({g.role_share:.0%} share"
                f"{', importance=' + g.importance_max if g.importance_max else ''}); "
                "agent has no matching skill."
            ),
            steps=[
                f"Forge or hand-author a skill for `{g.canonical_name}`",
                "Wire triggers/when-to-use so routing can select it",
                "Re-run `market gap` and confirm the skill moves to shared",
            ],
        ))

    for g in report.agent_only[:15]:
        proposals.append(MarketProposal(
            action="review_stale",
            priority="low",
            skill=g.canonical_name,
            title=f"Review agent-only skill `{g.canonical_name}`",
            rationale=(
                "Present on the agent but absent from the JD corpus — "
                "may be unique value or stale inventory."
            ),
            steps=[
                "Confirm whether the skill still maps to real work",
                "Archive or rewrite description if obsolete",
                "Keep if it is a deliberate differentiator",
            ],
        ))

    notes: list[str] = []
    if report.coverage_score >= 0.85 and not report.market_only:
        notes.append("High coverage with no market gaps — proposals limited to agent-only review.")
    if not proposals:
        notes.append("No gap-driven proposals. Run `market gap` first if this is unexpected.")

    return MarketProposalReport(
        corpus_root=report.corpus_root,
        agent_skill_dir=report.agent_skill_dir,
        generated_at=datetime.now(UTC),
        coverage_score=report.coverage_score,
        proposals=proposals,
        notes=notes,
    )


def render_proposals_markdown(report: MarketProposalReport) -> str:
    lines = [
        "# market propose",
        "",
        f"- Market: `{report.corpus_root}`",
        f"- Agent: `{report.agent_skill_dir}`",
        f"- Coverage: {report.coverage_score:.0%}",
        f"- Generated at: {report.generated_at.isoformat()}",
        f"- Proposals: {len(report.proposals)}",
        "",
        "> Deterministic suggestions from gap analysis. Review before applying.",
        "",
    ]
    if report.notes:
        lines.append("## Notes")
        lines.extend(f"- {n}" for n in report.notes)
        lines.append("")
    for i, p in enumerate(report.proposals, 1):
        lines.append(f"## {i}. {p.title}")
        lines.append("")
        lines.append(f"- **action:** `{p.action}` · **priority:** {p.priority}")
        lines.append("")
        lines.append(p.rationale)
        lines.append("")
        if p.steps:
            lines.append("**Suggested steps**")
            for step in p.steps:
                lines.append(f"1. {step}")
            lines.append("")
    return "\n".join(lines)


def write_proposals(report: MarketProposalReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = report.generated_at.strftime("%Y-%m-%dT%H%M%S")
    md_path = out_dir / f"market-propose-{stamp}.md"
    json_path = out_dir / f"market-propose-{stamp}.json"
    md_path.write_text(render_proposals_markdown(report), encoding="utf-8")
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return md_path
