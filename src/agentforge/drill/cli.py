"""``agentforge drill ...`` sub-CLI (Phase 1.0)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentforge.day2.cli_validators import validate_dir
from agentforge.drill import ingest as ingest_mod
from agentforge.drill import scan as scan_mod
from agentforge.drill import version as version_mod
from agentforge.drill import watch as watch_mod
from agentforge.drill.models import SkillInventory, snapshot_path

app = typer.Typer(
    name="drill",
    help="Day-2+ skill maintenance: ingest, scan, watch, version skill folders.",
    no_args_is_help=True,
)
console = Console()


def _validate_skill_dir(skill_dir: Path) -> Path:
    return validate_dir(skill_dir, entity="skill-dir")


def _write_snapshot(inventory: SkillInventory, skill_dir: Path) -> Path:
    path = snapshot_path(skill_dir, inventory.captured_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(inventory.model_dump_json(indent=2), encoding="utf-8")
    return path


@app.command("ingest")
def cmd_ingest(
    skill_dir: Path = typer.Argument(
        ...,
        help="Skill folder (with SKILL.md) or parent of multiple skill folders.",
    ),
    record_version: bool = typer.Option(
        True, "--record-version/--no-record-version",
        help="Append to versions.jsonl when the inventory fingerprint changes.",
    ),
) -> None:
    """Snapshot a skill directory into <skill-dir>/.drill/snapshots/."""
    skill_dir = _validate_skill_dir(skill_dir)
    inventory = ingest_mod.ingest(skill_dir)
    snap = _write_snapshot(inventory, skill_dir)

    table = Table(title=f"drill ingest — {skill_dir}", show_lines=False)
    table.add_column("Skill", style="cyan")
    table.add_column("Body words", justify="right")
    table.add_column("Files", justify="right")
    table.add_column("Tools", justify="right")
    table.add_column("Notes", style="dim")
    for d in inventory.skills:
        table.add_row(
            d.slug,
            str(d.body_word_count) if d.has_skill_md else "—",
            str(d.file_count) if d.has_skill_md else "—",
            str(len(d.allowed_tools)),
            "; ".join(d.notes) if d.notes else "",
        )
    console.print(table)
    console.print(
        f"[green]✓[/green] {inventory.total_skills} skill(s) · "
        f"layout: {inventory.layout} · snapshot: [bold]{snap}[/bold]"
    )

    if record_version:
        entry = version_mod.record_if_changed(skill_dir, inventory, snap)
        if entry is not None:
            console.print(
                f"[green]✓[/green] version recorded · fp `{entry.inventory_fingerprint[:12]}`"
            )
        else:
            console.print("[dim]inventory unchanged · no new version entry[/dim]")


@app.command("scan")
def cmd_scan(
    skill_dir: Path = typer.Argument(
        ...,
        help="Skill folder or parent directory.",
    ),
    bloat_threshold: int = typer.Option(
        scan_mod.BLOAT_WORD_THRESHOLD, "--bloat-threshold",
        help="SKILL.md body word count above which we flag bloat.",
    ),
    tool_threshold: int = typer.Option(
        scan_mod.TOOL_SPRAWL_THRESHOLD, "--tool-threshold",
        help="allowed-tools count above which we flag tool sprawl.",
    ),
    overlap_threshold: float = typer.Option(
        scan_mod.OVERLAP_JACCARD_THRESHOLD, "--overlap-threshold",
        help="Jaccard similarity above which we flag descriptive overlap.",
    ),
    write: bool = typer.Option(
        True, "--write/--no-write",
        help="Persist scan-<timestamp>.{md,json} under <skill-dir>/.drill/.",
    ),
) -> None:
    """Run deterministic diagnostics over a fresh snapshot."""
    skill_dir = _validate_skill_dir(skill_dir)
    inventory = ingest_mod.ingest(skill_dir)
    report = scan_mod.scan(
        inventory,
        bloat_threshold=bloat_threshold,
        tool_threshold=tool_threshold,
        overlap_threshold=overlap_threshold,
    )

    sev_counts = {"critical": 0, "warn": 0, "info": 0}
    for f in report.findings:
        sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1

    if not report.findings:
        console.print(Panel(
            "[green]No issues detected.[/green]",
            title=f"drill scan — {skill_dir}",
        ))
    else:
        table = Table(title=f"drill scan — {skill_dir}", show_lines=False)
        table.add_column("Severity", style="bold")
        table.add_column("Kind", style="cyan")
        table.add_column("Skill", style="dim")
        table.add_column("Message")
        for f in report.findings:
            color = {"critical": "red", "warn": "yellow", "info": "blue"}.get(f.severity, "white")
            table.add_row(
                f"[{color}]{f.severity}[/{color}]",
                f.kind,
                f.skill or "—",
                f.message,
            )
        console.print(table)

    console.print(
        f"[green]✓[/green] {len(report.findings)} finding(s) — "
        f"critical: {sev_counts['critical']}, "
        f"warn: {sev_counts['warn']}, "
        f"info: {sev_counts['info']}"
    )

    if write:
        out_path = scan_mod.write_report(report, skill_dir)
        console.print(f"  report: [bold]{out_path}[/bold]")


@app.command("watch")
def cmd_watch(
    skill_dir: Path = typer.Argument(...),
    write: bool = typer.Option(
        True, "--write/--no-write",
        help="Persist watch-<date>.md under <skill-dir>/.drill/.",
    ),
) -> None:
    """Diff the two most recent snapshots and emit evolution findings."""
    skill_dir = _validate_skill_dir(skill_dir)
    snaps = watch_mod.list_snapshots(skill_dir)
    if len(snaps) < 2:
        console.print(
            f"[yellow]Need at least 2 snapshots to watch — found {len(snaps)}.[/yellow]"
        )
        console.print("[dim]Run `drill ingest` at least twice with changes in between.[/dim]")
        raise typer.Exit(code=0)

    report = watch_mod.watch(skill_dir)

    if not report.findings:
        console.print(Panel(
            "[green]No evolution detected.[/green]",
            title=f"drill watch — {skill_dir}",
        ))
    else:
        table = Table(title=f"drill watch — {skill_dir}", show_lines=False)
        table.add_column("Severity", style="bold")
        table.add_column("Kind", style="cyan")
        table.add_column("Skill", style="dim")
        table.add_column("Message")
        for f in report.findings:
            color = {"critical": "red", "warn": "yellow", "info": "blue"}.get(f.severity, "white")
            table.add_row(
                f"[{color}]{f.severity}[/{color}]",
                f.kind,
                f.skill or "—",
                f.message,
            )
        console.print(table)

    console.print(f"[green]✓[/green] {len(report.findings)} finding(s)")

    if write:
        out_path = watch_mod.write_report(report, skill_dir)
        console.print(f"  report: [bold]{out_path}[/bold]")


@app.command("snapshots")
def cmd_snapshots(
    skill_dir: Path = typer.Argument(...),
) -> None:
    """List recorded snapshots, oldest → newest."""
    skill_dir = _validate_skill_dir(skill_dir)
    snaps = watch_mod.list_snapshots(skill_dir)
    if not snaps:
        console.print("[dim]no snapshots recorded yet[/dim]")
        return
    table = Table(title=f"snapshots — {skill_dir}")
    table.add_column("#", justify="right")
    table.add_column("Path")
    for i, p in enumerate(snaps, start=1):
        table.add_row(str(i), str(p))
    console.print(table)


@app.command("version")
def cmd_version(
    skill_dir: Path = typer.Argument(...),
    note: str | None = typer.Option(
        None, "--note",
        help="Annotate the most recent version entry with a free-form note.",
    ),
) -> None:
    """Show the inventory version log (or annotate the latest entry with --note)."""
    skill_dir = _validate_skill_dir(skill_dir)
    if note is not None:
        entry = version_mod.annotate_latest(skill_dir, note)
        if entry is None:
            console.print("[yellow]no versions recorded yet[/yellow]")
            raise typer.Exit(code=0)
        console.print(f"[green]✓[/green] annotated v{len(version_mod.load_versions(skill_dir))}")
        return
    entries = version_mod.load_versions(skill_dir)
    console.print(version_mod.render_log(entries))


@app.command("propose")
def cmd_propose(
    skill_dir: Path = typer.Argument(
        ...,
        help="Skill folder or parent directory (same as drill scan).",
    ),
    bloat_threshold: int = typer.Option(
        scan_mod.BLOAT_WORD_THRESHOLD, "--bloat-threshold",
    ),
    tool_threshold: int = typer.Option(
        scan_mod.TOOL_SPRAWL_THRESHOLD, "--tool-threshold",
    ),
    overlap_threshold: float = typer.Option(
        scan_mod.OVERLAP_JACCARD_THRESHOLD, "--overlap-threshold",
    ),
    write: bool = typer.Option(
        True, "--write/--no-write",
        help="Persist propose-<timestamp>.{md,json} under <skill-dir>/.drill/.",
    ),
) -> None:
    """Turn scan findings into deterministic maintenance proposals (no LLM).

    Does not edit skill sources — writes a reviewable plan only.
    """
    from agentforge.drill import propose as propose_mod

    skill_dir = _validate_skill_dir(skill_dir)
    inventory = ingest_mod.ingest(skill_dir)
    scan_report = scan_mod.scan(
        inventory,
        bloat_threshold=bloat_threshold,
        tool_threshold=tool_threshold,
        overlap_threshold=overlap_threshold,
    )
    report = propose_mod.propose_from_scan(scan_report)

    if not report.proposals:
        console.print(Panel(
            "[green]No proposals — scan found nothing actionable.[/green]",
            title=f"drill propose — {skill_dir}",
        ))
    else:
        table = Table(title=f"drill propose — {skill_dir}", show_lines=False)
        table.add_column("Priority", style="bold")
        table.add_column("Action", style="cyan")
        table.add_column("Skill", style="dim")
        table.add_column("Title")
        for p in report.proposals:
            color = {"high": "red", "medium": "yellow", "low": "blue"}.get(p.priority, "white")
            table.add_row(
                f"[{color}]{p.priority}[/{color}]",
                p.action,
                p.skill or "—",
                p.title,
            )
        console.print(table)

    console.print(f"[green]✓[/green] {len(report.proposals)} proposal(s)")
    if write:
        out_path = propose_mod.write_proposals(report, skill_dir)
        console.print(f"  plan: [bold]{out_path}[/bold]")


@app.command("apply")
def cmd_apply(
    skill_dir: Path = typer.Argument(
        ...,
        help="Skill folder or parent directory.",
    ),
    from_file: Path | None = typer.Option(
        None,
        "--from",
        help="propose-*.json path (default: latest under <skill-dir>/.drill/).",
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Apply without interactive confirmation (still only mechanical actions).",
    ),
    only: list[str] | None = typer.Option(
        None,
        "--only",
        help="Only apply these actions (repeatable): prune_tools, add_skill_md, fix_references.",
    ),
    write: bool = typer.Option(
        True, "--write/--no-write",
        help="Persist apply-*.json under <skill-dir>/.drill/.",
    ),
) -> None:
    """Apply mechanical drill proposals under a human gate.

    Safe auto-actions only: prune_tools, add_skill_md, fix_references.
    Design judgments (split_body, differentiate_skills) are always skipped.

    Examples:
        agentforge drill apply ./skills --from .drill/propose-....json
        agentforge drill apply ./skills --yes --only prune_tools
    """
    from agentforge.drill import apply as apply_mod

    skill_dir = _validate_skill_dir(skill_dir)
    plan_path = from_file
    if plan_path is None:
        plan_path = apply_mod.latest_propose_json(skill_dir)
    if plan_path is None or not plan_path.is_file():
        console.print(
            "[red]No propose-*.json found.[/red] Run `drill propose` first "
            "or pass --from path/to/propose-….json"
        )
        raise typer.Exit(code=1)

    report = apply_mod.load_proposal_report(plan_path)
    only_set = set(only) if only else None

    from agentforge.drill.propose import Proposal

    def _confirm(p: Proposal) -> bool:
        return typer.confirm(
            f"Apply {p.action} on {p.skill or skill_dir.name}? {p.title}",
            default=False,
        )

    apply_report = apply_mod.apply_proposals(
        skill_dir,
        report,
        confirm=yes,
        only_actions=only_set,
        confirm_fn=None if yes else _confirm,
    )

    table = Table(title=f"drill apply — {skill_dir}", show_lines=False)
    table.add_column("Status", style="bold")
    table.add_column("Action", style="cyan")
    table.add_column("Skill", style="dim")
    table.add_column("Detail", max_width=50)
    for r in apply_report.results:
        color = {
            "applied": "green",
            "skipped": "yellow",
            "declined": "dim",
            "failed": "red",
        }.get(r.status, "white")
        table.add_row(
            f"[{color}]{r.status}[/{color}]",
            r.action,
            r.skill or "—",
            r.detail,
        )
    console.print(table)
    console.print(
        f"[green]✓[/green] applied: {apply_report.applied_count} · "
        f"skipped/declined: {apply_report.skipped_count}"
    )
    if write:
        out = apply_mod.write_apply_report(apply_report, skill_dir)
        console.print(f"  report: [bold]{out}[/bold]")


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name="drill")
