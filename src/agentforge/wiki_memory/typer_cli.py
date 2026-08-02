"""Typer registration for wiki-memory (forwards args to the argparse CLI)."""

from __future__ import annotations

import typer

from agentforge.wiki_memory.cli import main as wiki_main

# Parent-level flags on the argparse parser (must precede the subcommand).
_PARENT_FLAGS = frozenset({"--root", "-h", "--help"})


def _normalize_argv(args: list[str]) -> list[str]:
    """Move parent flags (e.g. --root) ahead of the subcommand when needed.

    Accepts both:
      agentforge wiki --root ./w init
      agentforge wiki init --root ./w
    """
    if not args:
        return args

    parent: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(args):
        tok = args[i]
        if tok in _PARENT_FLAGS or tok.startswith("--root="):
            parent.append(tok)
            if tok in ("--root",) and i + 1 < len(args) and not args[i + 1].startswith("-"):
                parent.append(args[i + 1])
                i += 2
                continue
            i += 1
            continue
        rest.append(tok)
        i += 1

    # Help with no subcommand → argparse help
    if rest == ["--help"] or rest == ["-h"]:
        return ["--help"]

    return parent + rest


def register(parent: typer.Typer) -> None:
    """Attach ``agentforge wiki …`` by forwarding remaining args to argparse."""

    @parent.command(
        name="wiki",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
        add_help_option=False,
    )
    def wiki_cmd(ctx: typer.Context) -> None:
        """Personal wiki memory — entities, facts, candidates, promotion.

        Examples:
            agentforge wiki init --root ./my-wiki
            agentforge wiki --root ./my-wiki init
            agentforge wiki add --title "AI Gateway" --type entity --kind project
            agentforge wiki search gateway
            agentforge wiki pending
        """
        args = _normalize_argv(list(ctx.args))
        if not args:
            code = wiki_main(["--help"])
            raise typer.Exit(code=code or 0)
        code = wiki_main(args)
        if code:
            raise typer.Exit(code=code)
