"""Tests for identity and skill file generation."""

from __future__ import annotations

import json

import yaml
import pytest
from personanexus.types import AgentIdentity

from agentforge.generation.identity_generator import IdentityGenerator
from agentforge.generation.skill_file import SkillFileGenerator
from agentforge.models.extracted_skills import (
    ExtractionResult,
    ExtractedRole,
    ExtractedSkill,
    SkillCategory,
    SkillImportance,
    SkillProficiency,
    SuggestedTraits,
)
from agentforge.models.job_description import JobDescription, JDSource


class TestIdentityGenerator:
    def test_generate_produces_valid_identity(self, sample_extraction):
        generator = IdentityGenerator()
        identity, yaml_str = generator.generate(sample_extraction)

        assert isinstance(identity, AgentIdentity)
        assert identity.metadata.id.startswith("agt_")
        assert identity.schema_version == "1.0"

    def test_generated_yaml_is_parseable(self, sample_extraction):
        generator = IdentityGenerator()
        _, yaml_str = generator.generate(sample_extraction)

        data = yaml.safe_load(yaml_str)
        assert data["schema_version"] == "1.0"
        assert "metadata" in data
        assert "role" in data
        assert "personality" in data

    def test_round_trip_validation(self, sample_extraction):
        """Generated YAML should validate when parsed back through PersonaNexus."""
        generator = IdentityGenerator()
        _, yaml_str = generator.generate(sample_extraction)

        data = yaml.safe_load(yaml_str)
        # This will raise if invalid
        identity = AgentIdentity.model_validate(data)
        assert identity.metadata.name

    def test_expertise_domains_populated(self, sample_extraction):
        generator = IdentityGenerator()
        identity, _ = generator.generate(sample_extraction)

        domain_names = [d.name for d in identity.expertise.domains]
        assert "Python" in domain_names
        assert "SQL" in domain_names

    def test_principles_generated(self, sample_extraction):
        generator = IdentityGenerator()
        identity, _ = generator.generate(sample_extraction)

        assert len(identity.principles) >= 2
        priorities = [p.priority for p in identity.principles]
        assert len(priorities) == len(set(priorities))  # unique priorities

    def test_guardrails_generated(self, sample_extraction):
        generator = IdentityGenerator()
        identity, _ = generator.generate(sample_extraction)

        assert len(identity.guardrails.hard) >= 2

    def test_personality_traits_set(self, sample_extraction):
        generator = IdentityGenerator()
        identity, _ = generator.generate(sample_extraction)

        traits = identity.personality.traits.defined_traits()
        assert len(traits) >= 2  # PersonaNexus requires at least 2

    def test_minimal_extraction(self):
        """Test with minimal extraction data."""
        extraction = ExtractionResult(
            role=ExtractedRole(
                title="Test Agent",
                purpose="A test agent for validation",
                domain="general",
            ),
            skills=[
                ExtractedSkill(name="Testing", category=SkillCategory.HARD),
            ],
            suggested_traits=SuggestedTraits(warmth=0.5, rigor=0.5),
        )
        generator = IdentityGenerator()
        identity, yaml_str = generator.generate(extraction)

        assert identity.metadata.id == "agt_test_agent_001"
        assert len(yaml_str) > 0


class TestSkillFileGenerator:
    def test_generate_skill_file(self, sample_extraction):
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "Senior Data Engineer" in content
        assert "Python" in content
        assert "SQL" in content
        assert "Apache Spark" in content

    def test_skill_file_has_sections(self, sample_extraction):
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "## Technical Skills" in content or "## Tools & Platforms" in content
        assert "## Soft Skills" in content
        assert "## Key Responsibilities" in content

    def test_skill_file_automation_section(self, sample_extraction):
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "## Automation Assessment" in content
        assert "35%" in content
        assert "AI-Augmentable Areas" in content
        assert "Human-Critical Areas" in content

    def test_skill_file_importance_badges(self, sample_extraction):
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "[Required]" in content

    def test_minimal_extraction(self):
        extraction = ExtractionResult(
            role=ExtractedRole(title="Tester", purpose="Test things", domain="qa"),
        )
        generator = SkillFileGenerator()
        content = generator.generate(extraction)

        assert "# Tester" in content
        assert "0%" in content  # no automation potential set
        assert "Generated by AgentForge" in content

    # ── Personality Profile tests ──

    def test_personality_profile_section(self, sample_extraction):
        """Personality profile should render traits with descriptions and prompts."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "## Personality Profile" in content
        assert "Rigor" in content
        assert "Directness" in content
        assert "Patience" in content
        assert "Creativity" in content
        # Should include behavior prompts
        assert "Behavior prompt:" in content

    def test_personality_profile_sorted_by_value(self, sample_extraction):
        """Traits should be sorted by value descending (strongest first)."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        # sample_extraction has rigor=0.85, directness=0.7, patience=0.6, creativity=0.5
        rigor_pos = content.index("Rigor")
        directness_pos = content.index("Directness")
        patience_pos = content.index("Patience")
        creativity_pos = content.index("Creativity")
        assert rigor_pos < directness_pos < patience_pos < creativity_pos

    def test_personality_profile_descriptions(self, sample_extraction):
        """High traits should get 'high' descriptions, mid traits get 'mid'."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        # rigor=0.85 → "Highly precise and detail-oriented"
        assert "Highly precise" in content
        # creativity=0.5 → "Open to creative solutions" (mid)
        assert "Open to creative solutions" in content

    def test_personality_customization_note(self, sample_extraction):
        """Personality section should include customization guidance for modularity."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "Customization Note" in content
        assert "hybrid personas" in content
        assert "Community contributions" in content

    def test_no_personality_section_without_traits(self):
        """No personality section if no traits are defined."""
        extraction = ExtractionResult(
            role=ExtractedRole(title="Bot", purpose="Do stuff", domain="general"),
            suggested_traits=SuggestedTraits(),  # all None
        )
        generator = SkillFileGenerator()
        content = generator.generate(extraction)

        assert "## Personality Profile" not in content
        assert "Customization Note" not in content

    # ── Role Context tests ──

    def test_role_context_section(self, sample_extraction, sample_jd):
        """Role context should include company, location, audience when JD is provided."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction, jd=sample_jd)

        assert "## Role Context" in content
        assert "Acme Technologies" in content
        assert "Data Engineering" in content

    def test_role_context_audience(self, sample_extraction):
        """Audience should appear in role context."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "## Role Context" in content
        assert "Data scientists" in content
        assert "Analysts" in content

    def test_role_context_without_jd(self, sample_extraction):
        """Role context should still render domain and audience without JD."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "## Role Context" in content
        assert "Data Engineering" in content

    def test_jd_with_location(self, sample_extraction):
        """Location from JD should appear in role context."""
        jd = JobDescription(
            source=JDSource.TEXT,
            title="Senior Data Engineer",
            company="Acme Corp",
            location="San Francisco, CA",
            department="Engineering",
            raw_text="Build data pipelines for Acme Corp.",
        )
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction, jd=jd)

        assert "San Francisco, CA" in content
        assert "Acme Corp" in content
        assert "Engineering" in content

    # ── Tool & Platform granularity tests ──

    def test_tool_examples_rendered(self, sample_extraction):
        """Tool skills with examples should render them as sub-bullets."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        # Apache Spark has examples: Spark SQL, Spark Streaming, Delta Lake
        assert "Examples:" in content
        assert "Spark SQL" in content
        assert "Delta Lake" in content

    def test_hard_skill_examples_rendered(self, sample_extraction):
        """Hard skills with examples should also render them."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        # Python has examples: pandas, PySpark
        assert "pandas" in content
        assert "PySpark" in content

    def test_genai_application_on_skills(self, sample_extraction):
        """Skills with genai_application should render GenAI notes."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "GenAI Application:" in content
        # Python has genai_application about ML-powered code gen
        assert "ML-powered code generation" in content
        # Apache Spark has auto-tuning note
        assert "Auto-tuning Spark jobs" in content

    # ── Domain Knowledge tests ──

    def test_domain_knowledge_section(self, sample_extraction):
        """Domain knowledge skills should appear in their own section."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "## Domain Knowledge" in content
        assert "Data Architecture" in content
        assert "AI-assisted schema evolution" in content

    # ── Automation breakdown tests ──

    def test_automation_per_area_estimates(self, sample_extraction):
        """AI-Augmentable areas should include percentage estimates."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        # Apache Spark (TOOL, ADVANCED) → 40% estimate
        assert "Apache Spark (40%)" in content

    def test_automation_genai_in_breakdown(self, sample_extraction):
        """Automation breakdown should use genai_application when available."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        # Apache Spark should show its genai_application in the automation section
        assert "Auto-tuning Spark jobs" in content

    def test_automation_hard_skills_with_genai(self, sample_extraction):
        """Hard skills with genai_application should appear in AI-Augmentable."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        # Python has genai_application, should be in AI-Augmentable
        # Check it's in the automation section area
        auto_section = content[content.index("## Automation Assessment"):]
        assert "Python (40%)" in auto_section

    def test_human_critical_soft_skills(self, sample_extraction):
        """Soft skills should appear in Human-Critical with context."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        auto_section = content[content.index("## Automation Assessment"):]
        assert "Team Collaboration" in auto_section
        assert "Cross-functional work" in auto_section

    # ── Embedded data tests ──

    def test_embedded_json_full_skills(self, sample_extraction):
        """Embedded JSON should include full skills grouped by category."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "## Agent Data (Machine-Readable)" in content
        assert "```json" in content

        # Extract and parse the JSON block
        json_start = content.index("```json") + len("```json\n")
        json_end = content.index("```", json_start)
        data = json.loads(content[json_start:json_end])

        # Full skills structure
        assert "skills" in data
        assert "hard" in data["skills"]
        assert "tool" in data["skills"]
        assert "soft" in data["skills"]
        assert "domain" in data["skills"]

        # Check hard skills have examples
        python_skill = next(s for s in data["skills"]["hard"] if s["name"] == "Python")
        assert python_skill["proficiency"] == "advanced"
        assert "pandas" in python_skill["examples"][0]
        assert "genai_application" in python_skill

    def test_embedded_json_domain_knowledge_array(self, sample_extraction):
        """Embedded JSON should include a dedicated domain_knowledge array."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        json_start = content.index("```json") + len("```json\n")
        json_end = content.index("```", json_start)
        data = json.loads(content[json_start:json_end])

        assert "domain_knowledge" in data
        assert len(data["domain_knowledge"]) >= 1
        arch = data["domain_knowledge"][0]
        assert arch["name"] == "Data Architecture"
        assert "genai_application" in arch

    def test_embedded_json_responsibilities(self, sample_extraction):
        """Embedded JSON should include responsibilities and qualifications."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        json_start = content.index("```json") + len("```json\n")
        json_end = content.index("```", json_start)
        data = json.loads(content[json_start:json_end])

        assert "responsibilities" in data
        assert len(data["responsibilities"]) == 4
        assert "qualifications" in data
        assert len(data["qualifications"]) == 2

    def test_embedded_json_scope_and_audience(self, sample_extraction):
        """Embedded JSON should include scope and audience arrays."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        json_start = content.index("```json") + len("```json\n")
        json_end = content.index("```", json_start)
        data = json.loads(content[json_start:json_end])

        assert "scope" in data
        assert "primary" in data["scope"]
        assert len(data["scope"]["primary"]) == 3
        assert "secondary" in data["scope"]
        assert "audience" in data
        assert "Data scientists" in data["audience"]

    def test_embedded_json_personality(self, sample_extraction):
        """Embedded JSON should include personality traits."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        json_start = content.index("```json") + len("```json\n")
        json_end = content.index("```", json_start)
        data = json.loads(content[json_start:json_end])

        assert "personality" in data
        assert data["personality"]["rigor"] == 0.85
        assert data["personality"]["creativity"] == 0.5

    # ── Metadata tests ──

    def test_metadata_footer(self, sample_extraction):
        """Metadata footer should include generation info."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "Generated by AgentForge" in content
        assert "---" in content

    def test_metadata_footer_with_jd(self, sample_extraction, sample_jd):
        """Metadata footer should include source JD info when available."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction, jd=sample_jd)

        assert "Senior Data Engineer at Acme Technologies" in content

    # ── Responsibilities and numbering ──

    def test_numbered_responsibilities(self, sample_extraction):
        """Responsibilities should be numbered (not bulleted)."""
        generator = SkillFileGenerator()
        content = generator.generate(sample_extraction)

        assert "1. Design and implement" in content
        assert "2. Build and maintain" in content

    # ── Skills with no extras still work ──

    def test_skills_without_examples_or_genai(self):
        """Skills without examples or genai_application should render cleanly."""
        extraction = ExtractionResult(
            role=ExtractedRole(title="Clerk", purpose="Process documents", domain="admin"),
            skills=[
                ExtractedSkill(
                    name="Filing",
                    category=SkillCategory.HARD,
                    context="Organize physical and digital documents",
                ),
            ],
        )
        generator = SkillFileGenerator()
        content = generator.generate(extraction)

        assert "Filing" in content
        assert "Organize physical" in content
        # Should NOT have Examples or GenAI lines
        assert "Examples:" not in content
        assert "GenAI Application:" not in content
