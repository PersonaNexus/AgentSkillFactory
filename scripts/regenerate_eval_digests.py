#!/usr/bin/env python3
"""Regenerate structural digests for offline fixture eval anti-drift locks.

Run after intentional generator changes that alter SKILL.md structure, frontmatter,
supplementary layout, identity top-level keys, or normalized body hash:

    uv run python scripts/regenerate_eval_digests.py

Writes ``tests/fixtures/eval/<role>.digest.json`` for each
``*_extraction.json`` fixture (same methodology wiring as CI tests).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agentforge.eval.fixture_eval import (  # noqa: E402
    digest_path_for_fixture,
    discover_eval_fixtures,
    evaluate_fixture_file,
)

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "eval"
METH_PATH = FIXTURE_DIR / "sample_methodology.json"


def main() -> int:
    fixtures = discover_eval_fixtures(FIXTURE_DIR)
    if not fixtures:
        print(f"No fixtures under {FIXTURE_DIR}", file=sys.stderr)
        return 1

    meth = METH_PATH if METH_PATH.is_file() else None
    for path in fixtures:
        result = evaluate_fixture_file(
            path,
            methodology_path=meth,
            apply_audit_fix=True,
            # Pass a non-existent path so we do not compare while regenerating
            digest_path=path.parent / ".__no_digest_compare__",
        )
        if result.digest is None:
            print(f"FAIL {path.name}: no digest produced — {result.errors}", file=sys.stderr)
            return 1

        out = digest_path_for_fixture(path)
        out.write_text(
            json.dumps(result.digest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {out.relative_to(REPO_ROOT)}  skill={result.skill_name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
