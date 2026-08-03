"""Golden validation of public example artifacts (no live LLM).

These tests lock the senior-data-engineer example package so schema drift,
broken frontmatter, or missing skill-folder layout fails CI before a release.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from personanexus.types import AgentIdentity

from agentforge.analysis.skill_check import (
    SkillChecker,
    validate_identity_yaml,
    validate_skill_folder,
)
from agentforge.generation.identity_loader import IdentityLoader

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "senior-data-engineer" / "output"
SKILL_DIR = EXAMPLE / "skill-folder"
IDENTITY = EXAMPLE / "identity.yaml"
PN_IDENTITY = EXAMPLE / "personanexus-deployment" / "agent_identity.yaml"
PN_DEPLOY = EXAMPLE / "personanexus-deployment"


@pytest.fixture(scope="module")
def example_present() -> None:
    if not EXAMPLE.is_dir():
        pytest.skip("examples/senior-data-engineer/output missing")


class TestExampleIdentityGolden:
    def test_identity_yaml_exists(self, example_present: None) -> None:
        assert IDENTITY.is_file()

    def test_identity_validates_personanexus(self, example_present: None) -> None:
        data = yaml.safe_load(IDENTITY.read_text(encoding="utf-8"))
        identity = AgentIdentity.model_validate(data)
        assert identity is not None

    def test_validate_identity_yaml_helper(self, example_present: None) -> None:
        ok, msg = validate_identity_yaml(IDENTITY.read_text(encoding="utf-8"))
        assert ok, msg

    def test_identity_loader_roundtrip(self, example_present: None) -> None:
        extraction, methodology, raw = IdentityLoader().load_file(str(IDENTITY))
        assert extraction.role.title
        assert extraction.skills
        assert raw  # original YAML preserved


class TestExampleSkillFolderGolden:
    def test_skill_folder_layout(self, example_present: None) -> None:
        problems = validate_skill_folder(SKILL_DIR)
        # Recommended files should all be present in the public example
        hard = [p for p in problems if not p.startswith("missing recommended")]
        soft = [p for p in problems if p.startswith("missing recommended")]
        assert not hard, hard
        assert not soft, soft

    def test_skill_check_default_gate(self, example_present: None) -> None:
        report = SkillChecker().check_paths(SKILL_DIR / "SKILL.md")
        assert report.lint_ok, report.lint.model_dump()
        assert report.size_ok, report.size.overall_assessment
        # Default gate ignores audit incompleteness (example is known soft on guardrails)
        assert report.passed

    def test_skill_check_strict_may_fail_audit(self, example_present: None) -> None:
        report = SkillChecker().check_paths(SKILL_DIR / "SKILL.md", strict=True)
        # Document current example quality: strict can fail without being a test failure
        # as long as the checker is consistent.
        if not report.audit_ok:
            assert not report.passed
        else:
            assert report.passed


class TestPersonaNexusDeploymentGolden:
    def test_deployment_package_files(self, example_present: None) -> None:
        assert PN_DEPLOY.is_dir()
        for name in (
            "agent_identity.yaml",
            "compiled_prompt.md",
            "deployment.yaml",
            "README.md",
        ):
            assert (PN_DEPLOY / name).is_file(), name

    def test_deployment_identity_validates(self, example_present: None) -> None:
        ok, msg = validate_identity_yaml(PN_IDENTITY.read_text(encoding="utf-8"))
        assert ok, msg

    def test_deployment_yaml_shape(self, example_present: None) -> None:
        data = yaml.safe_load((PN_DEPLOY / "deployment.yaml").read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        # Manifest should point at validation/runtime in some form
        blob = yaml.dump(data).lower()
        assert "personanexus" in blob or "validate" in blob or "runtime" in blob
