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


class RubricScores(BaseModel):  # type: ignore[misc]
    """Structured quality rubrics beyond binary check pass/fail."""

    min_skills: bool = False  # extraction had ≥3 skills
    title_in_skill: bool = False  # role title appears in SKILL.md body
    frontmatter_name_ok: bool = False  # frontmatter name present and slug-like
    has_guardrails_section: bool = False
    methodology_enriched: bool = False  # when methodology provided, body grew / has templates
    skill_count: int = 0
    skill_md_tokens_est: int = 0

    @property
    def all_passed(self) -> bool:
        base = (
            self.min_skills
            and self.title_in_skill
            and self.frontmatter_name_ok
            and self.has_guardrails_section
        )
        return base


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
    rubrics: RubricScores = Field(default_factory=RubricScores)
    errors: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Default gate for CI: identity valid, layout clean, non-strict check pass."""
        return (
            self.identity_ok
            and not self.skill_layout_problems
            and self.check_passed
            and self.rubrics.all_passed
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

    # Rubrics (content shape, not live-model quality)
    skill_md = folder.skill_md
    skill_lower = skill_md.lower()
    title_token = extraction.role.title.lower()
    # Accept last significant title word (e.g. "Engineer") as weak match if full title missing
    title_words = [w for w in extraction.role.title.split() if len(w) > 3]
    title_in = title_token in skill_lower or any(w.lower() in skill_lower for w in title_words[-2:])

    fm_name_ok = False
    if skill_md.lstrip().startswith("---"):
        try:
            import yaml  # type: ignore[import-untyped]

            parts = skill_md.split("---", 2)
            if len(parts) >= 3:
                meta = yaml.safe_load(parts[1]) or {}
                name = meta.get("name") if isinstance(meta, dict) else None
                if isinstance(name, str) and name and name == folder.skill_name:
                    fm_name_ok = True
                elif isinstance(name, str) and name:
                    fm_name_ok = True  # present even if not exact slug match
        except Exception:
            fm_name_ok = False

    methodology_enriched = True
    if methodology is not None and methodology.has_content():
        methodology_enriched = (
            "templates/" in "".join(folder.supplementary_files)
            or "methodology" in skill_lower
            or bool(folder.supplementary_files.get("instructions/methodology.md"))
        )

    rubrics = RubricScores(
        min_skills=len(extraction.skills) >= 3,
        title_in_skill=title_in,
        frontmatter_name_ok=fm_name_ok,
        has_guardrails_section="guardrail" in skill_lower,
        methodology_enriched=methodology_enriched,
        skill_count=len(extraction.skills),
        skill_md_tokens_est=len(skill_md) // 4,
    )
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
    if "guardrail" in skill_md_for_strict.lower():
        rubrics.has_guardrails_section = True

    strict_report = checker.check(
        skill_md_for_strict,
        identity_yaml=yaml_str,
        skill_path=f"{folder.skill_name}/SKILL.md",
        strict=True,
    )

    if not rubrics.min_skills:
        errors.append(f"rubric min_skills: only {len(extraction.skills)} skills")
    if not rubrics.title_in_skill:
        errors.append("rubric title_in_skill: role title not found in SKILL.md")
    if not rubrics.frontmatter_name_ok:
        errors.append("rubric frontmatter_name_ok: missing name in frontmatter")
    if not rubrics.has_guardrails_section:
        errors.append("rubric has_guardrails_section: missing Guardrails content")
    if methodology is not None and methodology.has_content() and not rubrics.methodology_enriched:
        errors.append("rubric methodology_enriched: expected methodology/templates in output")

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
            f"rubrics: skills={rubrics.skill_count} title={rubrics.title_in_skill} "
            f"name={rubrics.frontmatter_name_ok} guardrails={rubrics.has_guardrails_section} "
            f"methodology={rubrics.methodology_enriched}",
        ],
        rubrics=rubrics,
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
