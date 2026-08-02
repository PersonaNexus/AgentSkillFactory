"""Quality & analysis CLI commands (prompt-size, lint, cost, prompt-diff, audit)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from agentforge.analysis.guardrail_auditor import GuardrailReport

console = Console()


def register(parent: typer.Typer) -> None:
    """Register quality commands on the parent Typer app."""
    parent.command(name="prompt-size")(prompt_size)
    parent.command()(lint)
    parent.command()(cost)
    parent.command(name="prompt-diff")(prompt_diff)
    parent.command()(audit)


def prompt_size(
    skill_file: Path = typer.Argument(..., help="Path to a SKILL.md file to analyze"),
    identity: Path | None = typer.Option(
        None, "--identity", "-i", help="Optional identity YAML file to include in analysis"
    ),
    budget: int = typer.Option(
        8000, "--budget", "-b", help="Token budget threshold for warnings"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table or json"
    ),
) -> None:
    """Analyze prompt size and detect bloat in generated SKILL.md files.

    Measures character count, line count, and estimated tokens per section.
    Flags oversized sections, redundant content, and overall bloat.

    Examples:
        agentforge prompt-size output/SKILL.md
        agentforge prompt-size output/SKILL.md --identity output/identity.yaml
        agentforge prompt-size output/SKILL.md --budget 5000
        agentforge prompt-size output/SKILL.md --format json
    """
    if not skill_file.exists():
        console.print(f"[red]Error:[/red] File not found: {skill_file}")
        raise typer.Exit(code=1)

    skill_content = skill_file.read_text()
    identity_content = None
    if identity:
        if not identity.exists():
            console.print(f"[red]Error:[/red] File not found: {identity}")
            raise typer.Exit(code=1)
        identity_content = identity.read_text()

    from agentforge.analysis.prompt_size_analyzer import PromptSizeAnalyzer

    analyzer = PromptSizeAnalyzer(token_budget=budget)

    if identity_content:
        report = analyzer.analyze_combined(skill_content, identity_content)
    else:
        report = analyzer.analyze_skill_md(skill_content)

    if format == "json":
        console.print(Panel(
            json.dumps(report.model_dump(), indent=2),
            title="Prompt Size Report",
            border_style="blue",
        ))
    else:
        # Summary panel
        assessment_color = {
            "lean": "green",
            "moderate": "yellow",
            "bloated": "red",
        }.get(report.overall_assessment, "white")
        console.print(Panel(
            f"[bold]Total:[/bold] {report.total_chars:,} chars | "
            f"{report.total_lines:,} lines | "
            f"~{report.total_estimated_tokens:,} tokens\n"
            f"[bold]Assessment:[/bold] [{assessment_color}]{report.overall_assessment.upper()}[/{assessment_color}]",
            title="Prompt Size Summary",
            border_style=assessment_color,
        ))

        # Section breakdown table
        table = Table(title="Section Breakdown", show_lines=True)
        table.add_column("Section", style="cyan", min_width=20)
        table.add_column("Tokens", style="yellow", justify="right")
        table.add_column("Lines", justify="right")
        table.add_column("%", justify="right")
        table.add_column("Bar", min_width=20)

        for section in sorted(report.sections, key=lambda s: s.estimated_tokens, reverse=True):
            bar_len = min(int(section.percentage / 5), 20)
            bar = "[blue]" + "#" * bar_len + "[/blue]" + "." * (20 - bar_len)
            table.add_row(
                section.name,
                f"{section.estimated_tokens:,}",
                str(section.line_count),
                f"{section.percentage:.1f}%",
                bar,
            )
        console.print(table)

        # Verdicts
        if report.verdicts:
            console.print()
            for verdict in report.verdicts:
                icon = {"warning": "[yellow]!", "bloated": "[red]!!", "ok": "[green]~"}
                sev = icon.get(verdict.severity, "[white]?")
                console.print(f"  {sev}[/] [{verdict.severity}]{verdict.section}[/]: {verdict.message}")
            console.print()

    # Exit code 1 if bloated (useful for CI)
    if report.overall_assessment == "bloated":
        raise typer.Exit(code=1)

def lint(
    skill_file: Path = typer.Argument(..., help="Path to a SKILL.md file to lint"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table or json"
    ),
) -> None:
    """Lint a SKILL.md file for structural, semantic, and coherence issues.

    Checks for missing frontmatter, empty sections, trait contradictions,
    automation mismatches, and scope overlap.

    Examples:
        agentforge lint output/SKILL.md
        agentforge lint output/SKILL.md --format json
    """
    if not skill_file.exists():
        console.print(f"[red]Error:[/red] File not found: {skill_file}")
        raise typer.Exit(code=1)

    from agentforge.analysis.skill_linter import SkillLinter

    linter = SkillLinter()
    report = linter.lint(skill_file.read_text())

    if format == "json":
        console.print(Panel(
            json.dumps(report.model_dump(), indent=2),
            title="Lint Report",
            border_style="blue",
        ))
    else:
        status_color = "green" if report.passed else "red"
        console.print(Panel(
            f"[bold]Errors:[/bold] {report.error_count} | "
            f"[bold]Warnings:[/bold] {report.warning_count} | "
            f"[bold]Info:[/bold] {report.info_count}\n"
            f"[bold]Status:[/bold] [{status_color}]{'PASSED' if report.passed else 'FAILED'}[/{status_color}]",
            title="Lint Summary",
            border_style=status_color,
        ))

        if report.issues:
            table = Table(title="Lint Issues", show_lines=True)
            table.add_column("Rule", style="cyan", min_width=20)
            table.add_column("Severity", min_width=8)
            table.add_column("Section", style="dim")
            table.add_column("Message", max_width=60)

            severity_colors = {"error": "red", "warning": "yellow", "info": "blue"}
            for issue in report.issues:
                color = severity_colors.get(issue.severity, "white")
                table.add_row(
                    issue.rule,
                    f"[{color}]{issue.severity}[/{color}]",
                    issue.section,
                    issue.message,
                )
            console.print(table)

    if not report.passed:
        raise typer.Exit(code=1)

def cost(
    skill_file: Path = typer.Argument(..., help="Path to a SKILL.md file to estimate costs for"),
    daily_calls: int = typer.Option(
        50, "--daily-calls", "-n", help="Expected invocations per working day"
    ),
    cost_per_1k: float = typer.Option(
        0.008, "--cost-per-1k", help="Cost per 1K tokens (USD, blended input+output)"
    ),
    monthly_budget: float = typer.Option(
        500.0, "--budget", "-b", help="Monthly budget (USD) for utilization calculation"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table or json"
    ),
) -> None:
    """Estimate monthly token costs for running a generated SKILL.md.

    Projects costs based on actual prompt size and expected daily usage.

    Examples:
        agentforge cost output/SKILL.md
        agentforge cost output/SKILL.md --daily-calls 100
        agentforge cost output/SKILL.md --cost-per-1k 0.015 --budget 1000
    """
    if not skill_file.exists():
        console.print(f"[red]Error:[/red] File not found: {skill_file}")
        raise typer.Exit(code=1)

    from agentforge.analysis.cost_projector import CostProjector

    projector = CostProjector(cost_per_1k=cost_per_1k, monthly_budget=monthly_budget)
    report = projector.project(skill_file.read_text(), daily_calls=daily_calls)

    if format == "json":
        console.print(Panel(
            json.dumps(report.model_dump(), indent=2),
            title="Cost Projection",
            border_style="blue",
        ))
    else:
        util_color = "green" if report.budget_utilization < 0.5 else "yellow" if report.budget_utilization < 0.8 else "red"
        console.print(Panel(
            f"[bold]Prompt size:[/bold] ~{report.prompt_tokens:,} tokens\n"
            f"[bold]Tokens per call:[/bold] ~{report.tokens_per_call:,} "
            f"(prompt {report.prompt_tokens:,} + completion ~{report.estimated_completion_tokens:,})\n"
            f"[bold]Daily calls:[/bold] {report.estimated_daily_calls}\n"
            f"\n"
            f"[bold]Monthly tokens:[/bold] {report.monthly_token_usage:,}\n"
            f"[bold]Monthly cost:[/bold] ${report.monthly_cost_usd:,.2f}\n"
            f"[bold]Annual cost:[/bold] ${report.annual_cost_usd:,.2f}\n"
            f"[bold]Cost per call:[/bold] ${report.cost_per_call_usd:.4f}\n"
            f"[bold]Budget utilization:[/bold] [{util_color}]{report.budget_utilization:.0%}[/{util_color}]",
            title="Cost Projection",
            border_style="blue",
        ))

def prompt_diff(
    old_file: Path = typer.Argument(..., help="Path to the old SKILL.md file"),
    new_file: Path = typer.Argument(..., help="Path to the new SKILL.md file"),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table or json"
    ),
) -> None:
    """Compare two SKILL.md files section-by-section.

    Shows added, removed, and changed sections, plus personality trait changes.

    Examples:
        agentforge prompt-diff old_SKILL.md new_SKILL.md
        agentforge prompt-diff v1/SKILL.md v2/SKILL.md --format json
    """
    for f in (old_file, new_file):
        if not f.exists():
            console.print(f"[red]Error:[/red] File not found: {f}")
            raise typer.Exit(code=1)

    from agentforge.analysis.prompt_differ import PromptDiffer

    differ = PromptDiffer()
    report = differ.diff(old_file.read_text(), new_file.read_text())

    if format == "json":
        console.print(Panel(
            json.dumps(report.model_dump(), indent=2),
            title="Prompt Diff",
            border_style="blue",
        ))
    else:
        delta_sign = "+" if report.total_token_delta >= 0 else ""
        console.print(Panel(
            f"[bold]Sections added:[/bold] {report.sections_added} | "
            f"[bold]Removed:[/bold] {report.sections_removed} | "
            f"[bold]Changed:[/bold] {report.sections_changed}\n"
            f"[bold]Token delta:[/bold] {delta_sign}{report.total_token_delta:,}",
            title="Prompt Diff Summary",
            border_style="blue",
        ))

        # Section table
        changed_sections = [s for s in report.sections if s.status != "unchanged"]
        if changed_sections:
            table = Table(title="Section Changes", show_lines=True)
            table.add_column("Section", style="cyan", min_width=20)
            table.add_column("Status", min_width=10)
            table.add_column("Old", justify="right")
            table.add_column("New", justify="right")
            table.add_column("Summary", max_width=50)

            status_colors = {"added": "green", "removed": "red", "changed": "yellow"}
            for s in changed_sections:
                color = status_colors.get(s.status, "white")
                table.add_row(
                    s.section,
                    f"[{color}]{s.status}[/{color}]",
                    f"{s.old_size:,}" if s.old_size else "-",
                    f"{s.new_size:,}" if s.new_size else "-",
                    s.change_summary,
                )
            console.print(table)

        # Trait changes
        if report.trait_changes:
            console.print()
            for tc in report.trait_changes:
                old_str = f"{tc.old_value:.0%}" if tc.old_value is not None else "—"
                new_str = f"{tc.new_value:.0%}" if tc.new_value is not None else "—"
                delta_sign = "+" if tc.delta > 0 else ""
                color = "green" if tc.delta > 0 else "red" if tc.delta < 0 else "dim"
                console.print(
                    f"  [{color}]{tc.trait}[/{color}]: {old_str} → {new_str} "
                    f"([{color}]{delta_sign}{tc.delta:.0%}[/{color}])"
                )
            console.print()

def audit(
    skill_file: Path = typer.Argument(..., help="Path to a SKILL.md file to audit"),
    domain: str = typer.Option("general", "--domain", "-d", help="Role domain for domain-specific guardrail checks"),
    fix: bool = typer.Option(False, "--fix", help="Auto-inject missing guardrails into the skill file"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output path for fixed file (defaults to stdout)"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table or json"),
) -> None:
    """Audit a SKILL.md file against a comprehensive guardrail safety checklist."""
    from agentforge.analysis.guardrail_auditor import GuardrailAuditor

    if not skill_file.exists():
        console.print(f"[red]Error: file not found: {skill_file}[/red]")
        raise typer.Exit(code=1)

    content = skill_file.read_text()
    auditor = GuardrailAuditor()
    report = auditor.audit(content, domain=domain)

    def _show_report(rpt: GuardrailReport, label: str = "Guardrail Audit") -> None:
        if format == "json":
            console.print(json.dumps(rpt.model_dump(), indent=2, default=str))
            return

        table = Table(title=label)
        table.add_column("Check", style="bold")
        table.add_column("Category")
        table.add_column("Status")
        table.add_column("Evidence / Recommendation", max_width=60)

        for result in rpt.results:
            if result.passed:
                status = "[green]PASS[/green]"
                detail = result.evidence
            else:
                status = "[red]FAIL[/red]"
                detail = result.recommendation
            table.add_row(result.check.name, result.check.category, status, detail)

        console.print(table)

        overall_status = "[green]PASSED[/green]" if rpt.overall_passed else "[red]FAILED[/red]"
        summary = (
            f"Score: {rpt.score:.0%}  |  "
            f"Passed: {rpt.passed_count}  |  "
            f"Failed: {rpt.failed_count}  |  "
            f"Overall: {overall_status}"
        )
        console.print(Panel(summary, title="Summary"))

    _show_report(report)

    if fix and report.failed_count > 0:
        fixed_content = auditor.fix(content, report)
        if output:
            output.write_text(fixed_content)
            console.print(f"\n[green]Fixed file written to {output}[/green]")
        else:
            console.print("\n[bold]--- Fixed SKILL.md ---[/bold]\n")
            console.print(fixed_content)

        # Re-audit the fixed content
        re_report = auditor.audit(fixed_content, domain=domain)
        console.print()
        _show_report(re_report, label="Re-Audit After Fix")

    if not report.overall_passed:
        raise typer.Exit(code=1)
