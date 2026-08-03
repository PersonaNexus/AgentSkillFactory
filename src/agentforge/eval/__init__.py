"""Offline fixture evaluation — no live LLM required."""

from agentforge.eval.fixture_eval import (
    EvalResult,
    compare_digests,
    digest_path_for_fixture,
    evaluate_extraction,
    evaluate_fixture_file,
    structural_digest,
)

__all__ = [
    "EvalResult",
    "compare_digests",
    "digest_path_for_fixture",
    "evaluate_extraction",
    "evaluate_fixture_file",
    "structural_digest",
]
