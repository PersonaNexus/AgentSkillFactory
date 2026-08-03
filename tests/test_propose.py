"""Tests for deterministic drill/market propose surfaces."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agentforge.drill.models import ScanFinding, ScanReport
from agentforge.drill.propose import propose_from_scan, render_proposals_markdown, write_proposals
from agentforge.market.gap import GapReport, GapSkill
from agentforge.market.propose import propose_from_gap
from agentforge.market.propose import write_proposals as write_market_proposals


def test_drill_propose_from_bloat_finding(tmp_path: Path) -> None:
    scan = ScanReport(
        skill_dir=str(tmp_path),
        scanned_at=datetime.now(UTC),
        inventory_captured_at=datetime.now(UTC),
        findings=[
            ScanFinding(
                kind="bloat",
                severity="warn",
                skill="big-skill",
                message="body is 2000 words",
                detail="split me",
            ),
            ScanFinding(
                kind="tool_sprawl",
                severity="info",
                skill="big-skill",
                message="too many tools",
            ),
        ],
    )
    report = propose_from_scan(scan)
    assert len(report.proposals) == 2
    actions = {p.action for p in report.proposals}
    assert "split_body" in actions
    assert "prune_tools" in actions
    md = render_proposals_markdown(report)
    assert "split_body" in md
    path = write_proposals(report, tmp_path)
    assert path.exists()
    assert path.suffix == ".md"
    assert (tmp_path / ".drill").is_dir() or path.parent.name == ".drill"


def test_drill_propose_empty() -> None:
    scan = ScanReport(
        skill_dir="skills-root",
        scanned_at=datetime.now(UTC),
        inventory_captured_at=datetime.now(UTC),
        findings=[],
    )
    report = propose_from_scan(scan)
    assert report.proposals == []
    assert report.notes


def test_market_propose_from_gap(tmp_path: Path) -> None:
    gap = GapReport(
        corpus_root=str(tmp_path / "jds"),
        agent_skill_dir=str(tmp_path / "skills"),
        generated_at=datetime.now(UTC),
        coverage_score=0.4,
        market_only=[
            GapSkill(
                canonical_name="Kubernetes",
                side="market_only",
                severity="critical",
                role_count=4,
                role_share=0.8,
                importance_max="required",
            ),
        ],
        agent_only=[
            GapSkill(
                canonical_name="legacy-tool",
                side="agent_only",
                severity="info",
            ),
        ],
    )
    report = propose_from_gap(gap)
    assert any(p.action == "add_coverage" and p.skill == "Kubernetes" for p in report.proposals)
    assert any(p.action == "review_stale" for p in report.proposals)
    path = write_market_proposals(report, tmp_path / "out")
    assert path.exists()
