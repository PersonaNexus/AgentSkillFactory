"""Offline fixture eval — generation + schema + quality gates, no live LLM."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentforge.eval.fixture_eval import (
    discover_eval_fixtures,
    evaluate_extraction,
    evaluate_fixture_file,
)
from agentforge.models.extracted_skills import MethodologyExtraction

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "eval"
METH_PATH = FIXTURE_DIR / "sample_methodology.json"


@pytest.fixture(scope="module")
def methodology() -> MethodologyExtraction | None:
    if METH_PATH.is_file():
        return MethodologyExtraction.model_validate_json(METH_PATH.read_text())
    return None


def test_discover_eval_fixtures() -> None:
    fixtures = discover_eval_fixtures(FIXTURE_DIR)
    assert len(fixtures) >= 3
    names = {p.name for p in fixtures}
    assert "senior_data_engineer_extraction.json" in names
    assert "platform_sre_extraction.json" in names
    assert "customer_success_extraction.json" in names


@pytest.mark.parametrize(
    "fixture_name",
    [
        "senior_data_engineer_extraction.json",
        "platform_sre_extraction.json",
        "customer_success_extraction.json",
    ],
)
def test_fixture_eval_passes(fixture_name: str, methodology: MethodologyExtraction | None) -> None:
    path = FIXTURE_DIR / fixture_name
    assert path.is_file(), f"missing fixture {path}"
    result = evaluate_fixture_file(
        path,
        methodology_path=METH_PATH if methodology else None,
        # Use domain from extraction; data eng fixture benefits from domain keywords
        apply_audit_fix=True,
    )
    assert result.identity_ok, result.identity_message
    assert not result.skill_layout_problems, result.skill_layout_problems
    assert result.check_passed, result.check_summary
    assert result.passed, result.model_dump()
    # After audit fix path, strict should pass for maintained fixtures
    assert result.check_strict_passed, result.check_summary
    assert result.skill_name
    assert result.role_title


def test_evaluate_extraction_inline(methodology: MethodologyExtraction | None) -> None:
    from agentforge.models.extracted_skills import ExtractionResult

    path = FIXTURE_DIR / "platform_sre_extraction.json"
    extraction = ExtractionResult.model_validate_json(path.read_text())
    result = evaluate_extraction(
        extraction,
        methodology=methodology,
        domain="Platform Engineering",
    )
    assert result.passed
    assert result.passed_strict
