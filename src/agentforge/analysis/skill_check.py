"""Unified skill quality check — lint + size + guardrail audit.

Used by ``agentforge check`` and by tests that want a single structured report
without re-implementing CLI display logic.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from agentforge.analysis.guardrail_auditor import GuardrailAuditor, GuardrailReport
from agentforge.analysis.prompt_size_analyzer import PromptSizeAnalyzer, PromptSizeReport
from agentforge.analysis.skill_linter import LintReport, SkillLinter


class CheckReport(BaseModel):  # type: ignore[misc]
    """Combined quality report for a SKILL.md (and optional identity YAML)."""

    skill_path: str
    identity_path: str | None = None
    lint: LintReport
    size: PromptSizeReport
    audit: GuardrailReport
    strict: bool = False

    @property
    def lint_ok(self) -> bool:
        return bool(self.lint.passed)

    @property
    def size_ok(self) -> bool:
        return bool(self.size.overall_assessment != "bloated")

    @property
    def audit_ok(self) -> bool:
        return bool(self.audit.overall_passed)

    @property
    def passed(self) -> bool:
        """Default gate: lint clean + not bloated. Strict also requires audit pass."""
        base = self.lint_ok and self.size_ok
        if self.strict:
            return base and self.audit_ok
        return base

    def summary_lines(self) -> list[str]:
        lines = [
            f"lint: {'PASS' if self.lint_ok else 'FAIL'} "
            f"({self.lint.error_count} errors, {self.lint.warning_count} warnings)",
            f"size: {self.size.overall_assessment.upper()} "
            f"(~{self.size.total_estimated_tokens:,} tokens)",
            f"audit: {'PASS' if self.audit_ok else 'FAIL'} "
            f"(score {self.audit.score:.0%}, {self.audit.failed_count} failed checks)",
        ]
        if self.strict:
            lines.append("mode: strict (audit failures fail the check)")
        return lines


class SkillChecker:
    """Run lint, prompt-size, and guardrail audit on a skill file."""

    def __init__(
        self,
        *,
        token_budget: int = 8000,
        domain: str = "general",
    ) -> None:
        self.token_budget = token_budget
        self.domain = domain
        self._linter = SkillLinter()
        self._size = PromptSizeAnalyzer(token_budget=token_budget)
        self._auditor = GuardrailAuditor()

    def check(
        self,
        skill_md: str,
        *,
        identity_yaml: str | None = None,
        skill_path: str = "SKILL.md",
        identity_path: str | None = None,
        strict: bool = False,
    ) -> CheckReport:
        lint = self._linter.lint(skill_md)
        if identity_yaml:
            size = self._size.analyze_combined(skill_md, identity_yaml)
        else:
            size = self._size.analyze_skill_md(skill_md)
        audit = self._auditor.audit(skill_md, domain=self.domain)
        return CheckReport(
            skill_path=skill_path,
            identity_path=identity_path,
            lint=lint,
            size=size,
            audit=audit,
            strict=strict,
        )

    def check_paths(
        self,
        skill_file: Path,
        *,
        identity_file: Path | None = None,
        strict: bool = False,
    ) -> CheckReport:
        skill_md = skill_file.read_text(encoding="utf-8")
        identity_yaml = None
        identity_path = None
        if identity_file is not None:
            identity_yaml = identity_file.read_text(encoding="utf-8")
            identity_path = str(identity_file)
        return self.check(
            skill_md,
            identity_yaml=identity_yaml,
            skill_path=str(skill_file),
            identity_path=identity_path,
            strict=strict,
        )


def validate_skill_folder(folder: Path) -> list[str]:
    """Return a list of structural problems for a Claude Code skill folder.

    Empty list means the layout looks deployable.
    """
    problems: list[str] = []
    if not folder.is_dir():
        return [f"not a directory: {folder}"]

    skill_md = folder / "SKILL.md"
    if not skill_md.is_file():
        problems.append("missing SKILL.md")
    else:
        text = skill_md.read_text(encoding="utf-8")
        if not text.lstrip().startswith("---"):
            problems.append("SKILL.md missing YAML frontmatter")
        else:
            # Minimal frontmatter keys
            try:
                import yaml  # type: ignore[import-untyped]

                parts = text.split("---", 2)
                if len(parts) < 3:
                    problems.append("SKILL.md frontmatter is not closed")
                else:
                    meta = yaml.safe_load(parts[1]) or {}
                    if not isinstance(meta, dict):
                        problems.append("SKILL.md frontmatter is not a mapping")
                    else:
                        if not meta.get("name"):
                            problems.append("frontmatter missing name")
                        if not meta.get("description"):
                            problems.append("frontmatter missing description")
            except Exception as exc:  # noqa: BLE001 — report parse errors as problems
                problems.append(f"frontmatter parse error: {exc}")

    # Recommended supplementary layout (warn-level as soft problems prefix)
    for rel in (
        "instructions/scope.md",
        "instructions/methodology.md",
        "instructions/voice.md",
    ):
        if not (folder / rel).is_file():
            problems.append(f"missing recommended file: {rel}")

    return problems


def validate_identity_yaml(yaml_str: str) -> tuple[bool, str]:
    """Validate YAML as a PersonaNexus AgentIdentity.

    Returns (ok, message).
    """
    import yaml
    from personanexus.types import AgentIdentity

    try:
        data = yaml.safe_load(yaml_str)
    except Exception as exc:  # YAMLError or parser issues
        return False, f"invalid YAML: {exc}"
    if not isinstance(data, dict):
        return False, "expected a mapping at top level"
    try:
        identity = AgentIdentity.model_validate(data)
    except Exception as exc:  # noqa: BLE001 — surface validation errors
        return False, f"PersonaNexus validation failed: {exc}"
    # Prefer human title if present
    title = None
    role = getattr(identity, "role", None)
    if role is not None:
        title = getattr(role, "title", None) or getattr(role, "name", None)
    meta = getattr(identity, "metadata", None)
    mid = getattr(meta, "id", None) if meta is not None else None
    label = title or mid or "identity"
    return True, f"valid PersonaNexus identity ({label})"
