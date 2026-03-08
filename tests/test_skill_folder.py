"""Tests for Claude-compatible skill folder generation."""

from __future__ import annotations

import json

import pytest

from agentforge.generation.identity_generator import IdentityGenerator
from agentforge.generation.skill_folder import SkillFolderGenerator, SkillFolderResult
from agentforge.models.extracted_skills import (
    ExtractionResult,
    ExtractedRole,
    ExtractedSkill,
    SkillCategory,
    SuggestedTraits,
)


@pytest.fixture
def sample_identity(sample_extraction):
    """Generate an identity from the sample extraction for testing."""
    gen = IdentityGenerator()
    identity, _ = gen.generate(sample_extraction)
    return identity


class TestSkillFolderResult:
    def test_result_has_required_fields(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert isinstance(result, SkillFolderResult)
        assert result.agent_id
        assert len(result.instructions_md) > 0
        assert len(result.manifest_json) > 0

    def test_result_agent_id_matches_identity(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert sample_identity.metadata.id in result.agent_id


class TestInstructionsMd:
    def test_has_role_title(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "# Senior Data Engineer Agent Skill" in result.instructions_md

    def test_has_purpose(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "Design, build, and maintain scalable data infrastructure" in result.instructions_md

    def test_has_trigger_patterns(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "## Trigger Patterns" in result.instructions_md
        assert "Activate this skill" in result.instructions_md
        # Should include scope_primary items
        assert "ETL pipeline design" in result.instructions_md
        assert "Data warehouse architecture" in result.instructions_md

    def test_triggers_include_responsibilities(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        # Responsibilities should also appear as triggers
        assert "Design and implement scalable ETL/ELT pipelines" in result.instructions_md

    def test_has_identity_and_personality(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "## Identity & Personality" in result.instructions_md
        assert "senior" in result.instructions_md
        assert "Data Engineering" in result.instructions_md

    def test_has_personality_modifiers(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "### Personality Modifiers" in result.instructions_md
        assert "Rigor" in result.instructions_md
        assert "Directness" in result.instructions_md
        assert "Patience" in result.instructions_md
        assert "Creativity" in result.instructions_md

    def test_personality_modifiers_include_prompts(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        # Behavior prompts should be inline (not sub-bullets like SKILL.md)
        assert "Apply rigorous methodology" in result.instructions_md

    def test_has_communication_style(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "### Communication Style" in result.instructions_md
        # rigor=0.85, directness=0.7 → precise and straightforward
        assert "precise and straightforward" in result.instructions_md

    def test_has_core_competencies(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "## Core Competencies" in result.instructions_md

    def test_has_domain_expertise(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "### Domain Expertise" in result.instructions_md
        assert "Data Architecture" in result.instructions_md
        assert "AI-assisted schema evolution" in result.instructions_md

    def test_has_technical_skills(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "### Technical Skills" in result.instructions_md
        assert "Python" in result.instructions_md
        assert "SQL" in result.instructions_md
        # Examples should be shown
        assert "pandas" in result.instructions_md

    def test_has_tools_and_platforms(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "### Tools & Platforms" in result.instructions_md
        assert "Apache Spark" in result.instructions_md
        assert "Spark SQL" in result.instructions_md

    def test_has_workflows(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "## Workflows" in result.instructions_md
        assert "### Workflow 1:" in result.instructions_md
        assert "### Workflow 2:" in result.instructions_md

    def test_workflows_have_steps(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "1. Clarify requirements" in result.instructions_md
        assert "2. Assess the current state" in result.instructions_md
        # Should reference tools
        assert "Leverage relevant tools" in result.instructions_md

    def test_has_mcp_tool_integration(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "## MCP Tool Integration" in result.instructions_md
        assert "Apache Spark" in result.instructions_md
        assert "Auto-tuning Spark jobs" in result.instructions_md

    def test_has_scope_and_boundaries(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "## Scope & Boundaries" in result.instructions_md
        assert "### In Scope" in result.instructions_md
        assert "ETL pipeline design" in result.instructions_md

    def test_has_secondary_scope(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "### Secondary (Defer When Possible)" in result.instructions_md
        assert "ML model operationalization" in result.instructions_md

    def test_has_guardrails(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "### Guardrails" in result.instructions_md
        assert "Data Engineering" in result.instructions_md
        assert "team collaboration" in result.instructions_md

    def test_has_audience(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "## Audience" in result.instructions_md
        assert "Data scientists" in result.instructions_md
        assert "Analysts" in result.instructions_md

    def test_has_footer(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        assert "Generated by AgentForge" in result.instructions_md

    def test_footer_with_jd(self, sample_extraction, sample_identity, sample_jd):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity, jd=sample_jd)

        assert "Senior Data Engineer at Acme Technologies" in result.instructions_md


class TestManifestJson:
    def test_is_valid_json(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert isinstance(data, dict)

    def test_has_name_and_version(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert data["name"] == "senior-data-engineer"
        assert data["version"] == "1.0.0"

    def test_has_description(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert "data infrastructure" in data["description"]

    def test_has_agent_id(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert data["agent_id"] == sample_identity.metadata.id

    def test_has_domain_and_seniority(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert data["domain"] == "Data Engineering"
        assert data["seniority"] == "senior"

    def test_has_triggers(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert "triggers" in data
        assert "ETL pipeline design" in data["triggers"]
        assert "Data warehouse architecture" in data["triggers"]
        assert "Data quality" in data["triggers"]

    def test_has_tool_dependencies(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert "dependencies" in data
        assert "Apache Spark" in data["dependencies"]["tools"]
        assert data["dependencies"]["mcp_servers"] == []

    def test_has_personality_traits(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert "personality" in data
        assert data["personality"]["rigor"] == 0.85
        assert data["personality"]["creativity"] == 0.5

    def test_has_automation_potential(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert data["automation_potential"] == 0.35

    def test_has_skills_summary(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert "skills_summary" in data
        assert "Python" in data["skills_summary"]["hard"]
        assert "SQL" in data["skills_summary"]["hard"]
        assert "Apache Spark" in data["skills_summary"]["tool"]
        assert "Team Collaboration" in data["skills_summary"]["soft"]
        assert "Data Architecture" in data["skills_summary"]["domain"]

    def test_has_audience(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert "Data scientists" in data["audience"]

    def test_has_source_metadata(self, sample_extraction, sample_identity):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity)

        data = json.loads(result.manifest_json)
        assert "source" in data
        assert "generated" in data["source"]
        assert "AgentForge" in data["source"]["generator"]

    def test_source_with_jd(self, sample_extraction, sample_identity, sample_jd):
        generator = SkillFolderGenerator()
        result = generator.generate(sample_extraction, sample_identity, jd=sample_jd)

        data = json.loads(result.manifest_json)
        assert "Senior Data Engineer at Acme Technologies" in data["source"]["title"]


class TestMinimalExtraction:
    def test_minimal_produces_valid_output(self):
        extraction = ExtractionResult(
            role=ExtractedRole(
                title="Test Agent",
                purpose="A test agent for validation",
                domain="general",
            ),
        )
        gen = IdentityGenerator()
        identity, _ = gen.generate(extraction)

        generator = SkillFolderGenerator()
        result = generator.generate(extraction, identity)

        assert result.agent_id
        assert "# Test Agent Agent Skill" in result.instructions_md
        assert len(result.manifest_json) > 0

        # Manifest should be valid JSON
        data = json.loads(result.manifest_json)
        assert data["name"] == "test-agent"
        assert data["version"] == "1.0.0"

    def test_no_traits_still_works(self):
        extraction = ExtractionResult(
            role=ExtractedRole(
                title="Bot",
                purpose="Do stuff",
                domain="general",
            ),
            suggested_traits=SuggestedTraits(),  # all None
        )
        gen = IdentityGenerator()
        identity, _ = gen.generate(extraction)

        generator = SkillFolderGenerator()
        result = generator.generate(extraction, identity)

        # Should still have identity section but no personality modifiers
        assert "## Identity & Personality" in result.instructions_md
        assert "### Personality Modifiers" not in result.instructions_md

        data = json.loads(result.manifest_json)
        assert data["personality"] == {}

    def test_no_responsibilities_skips_workflows(self):
        extraction = ExtractionResult(
            role=ExtractedRole(
                title="Clerk",
                purpose="Process documents",
                domain="admin",
            ),
        )
        gen = IdentityGenerator()
        identity, _ = gen.generate(extraction)

        generator = SkillFolderGenerator()
        result = generator.generate(extraction, identity)

        assert "## Workflows" not in result.instructions_md

    def test_no_tools_skips_mcp(self):
        extraction = ExtractionResult(
            role=ExtractedRole(
                title="Writer",
                purpose="Write content",
                domain="content",
            ),
            skills=[
                ExtractedSkill(
                    name="Writing",
                    category=SkillCategory.SOFT,
                    context="Content creation",
                ),
            ],
        )
        gen = IdentityGenerator()
        identity, _ = gen.generate(extraction)

        generator = SkillFolderGenerator()
        result = generator.generate(extraction, identity)

        assert "## MCP Tool Integration" not in result.instructions_md
