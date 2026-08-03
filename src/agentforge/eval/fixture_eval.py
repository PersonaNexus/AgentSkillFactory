"""Fixture-based generation eval (no live LLM).

Loads a frozen ``ExtractionResult`` JSON, generates identity + skill folder,
validates PersonaNexus schema, skill layout, and quality gates.

Used by CI to lock generator regressions without API keys.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agentforge.analysis.guardrail_auditor import GuardrailAuditor
from agentforge.analysis.skill_check import SkillChecker, validate_identity_yaml
from agentforge.generation.identity_generator import IdentityGenerator
from agentforge.generation.skill_folder import SkillFolderGenerator
from agentforge.models.extracted_skills import ExtractionResult, MethodologyExtraction


class EvalResult(BaseModel):  # type: ignore[misc]
    """Outcome of one fixture evaluation."""

    fixture: str
    role_title: str
    skill_name: str
    identity_ok: bool
    identity_message: str
    skill_layout_problems: list[str] = Field(default_factory=list)
    check_passed: bool
    check_strict_passed: bool
    check_summary: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Default gate for CI: identity valid, layout clean, non-strict check pass."""
        return (
            self.identity_ok
            and not self.skill_layout_problems
            and self.check_passed
            and not self.errors
        )

    @property
    def passed_strict(self) -> bool:
        return self.passed and self.check_strict_passed


def evaluate_extraction(
    extraction: ExtractionResult,
    *,
    methodology: MethodologyExtraction | None = None,
    domain: str | None = None,
    apply_audit_fix: bool = True,
    fixture_name: str = "inline",
) -> EvalResult:
    """Generate artifacts from extraction and run quality gates.

    If ``apply_audit_fix`` is True, missing guardrails are injected before the
    strict check (mirrors the public example hardening path). Non-strict check
    always runs on the raw generated skill first.
    """
    errors: list[str] = []
    domain = domain or extraction.role.domain or "general"

    try:
        identity, yaml_str = IdentityGenerator().generate(extraction)
    except Exception as exc:  # noqa: BLE001
        return EvalResult(
            fixture=fixture_name,
            role_title=extraction.role.title,
            skill_name="",
            identity_ok=False,
            identity_message=str(exc),
            check_passed=False,
            check_strict_passed=False,
            errors=[f"identity_generate: {exc}"],
        )

    identity_ok, identity_message = validate_identity_yaml(yaml_str)

    try:
        folder = SkillFolderGenerator().generate(
            extraction,
            identity=identity,
            methodology=methodology,
        )
    except Exception as exc:  # noqa: BLE001
        return EvalResult(
            fixture=fixture_name,
            role_title=extraction.role.title,
            skill_name="",
            identity_ok=identity_ok,
            identity_message=identity_message,
            check_passed=False,
            check_strict_passed=False,
            errors=[f"skill_generate: {exc}"],
        )

    # Virtual layout check via temp-less validation of SKILL.md + known keys
    layout_problems: list[str] = []
    if not folder.skill_md.lstrip().startswith("---"):
        layout_problems.append("SKILL.md missing frontmatter")
    for required in (
        "instructions/voice.md",
        "instructions/methodology.md",
        "instructions/scope.md",
    ):
        if required not in folder.supplementary_files:
            layout_problems.append(f"missing recommended file: {required}")

    checker = SkillChecker(domain=domain)
    raw_report = checker.check(
        folder.skill_md,
        identity_yaml=yaml_str,
        skill_path=f"{folder.skill_name}/SKILL.md",
        strict=False,
    )

    skill_md_for_strict = folder.skill_md
    if apply_audit_fix and not raw_report.audit_ok:
        skill_md_for_strict = GuardrailAuditor().fix(folder.skill_md, raw_report.audit)

    strict_report = checker.check(
        skill_md_for_strict,
        identity_yaml=yaml_str,
        skill_path=f"{folder.skill_name}/SKILL.md",
        strict=True,
    )

    return EvalResult(
        fixture=fixture_name,
        role_title=extraction.role.title,
        skill_name=folder.skill_name,
        identity_ok=identity_ok,
        identity_message=identity_message,
        skill_layout_problems=layout_problems,
        check_passed=raw_report.passed,
        check_strict_passed=strict_report.passed,
        check_summary=raw_report.summary_lines() + [
            f"strict: {'PASS' if strict_report.passed else 'FAIL'}",
        ],
        errors=errors,
    )


def evaluate_fixture_file(
    path: Path,
    *,
    methodology_path: Path | None = None,
    domain: str | None = None,
    apply_audit_fix: bool = True,
) -> EvalResult:
    """Load extraction JSON from disk and evaluate."""
    extraction = ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))
    methodology = None
    if methodology_path is not None and methodology_path.is_file():
        methodology = MethodologyExtraction.model_validate_json(
            methodology_path.read_text(encoding="utf-8")
        )
    return evaluate_extraction(
        extraction,
        methodology=methodology,
        domain=domain,
        apply_audit_fix=apply_audit_fix,
        fixture_name=path.name,
    )


def discover_eval_fixtures(root: Path) -> list[Path]:
    """Return ``*_extraction.json`` files under *root*."""
    if not root.is_dir():
        return []
    return sorted(root.glob("*_extraction.json"))
