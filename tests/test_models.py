"""Tests for AgentForge data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentforge.models.blueprint import AgentBlueprint
from agentforge.models.culture import CultureProfile, CultureValue
from agentforge.models.extracted_skills import (
    ExtractionResult,
    ExtractedRole,
    ExtractedSkill,
    SeniorityLevel,
    SkillCategory,
    SkillImportance,
    SkillProficiency,
    SuggestedTraits,
)
from agentforge.models.job_description import JDSection, JDSource, JobDescription


class TestJobDescription:
    def test_basic_creation(self):
        jd = JobDescription(
            source=JDSource.TEXT,
            title="Software Engineer",
            raw_text="We are looking for a software engineer.",
        )
        assert jd.title == "Software Engineer"
        assert jd.source == JDSource.TEXT
        assert jd.company is None

    def test_with_sections(self):
        jd = JobDescription(
            source=JDSource.FILE,
            title="Data Analyst",
            company="Acme Corp",
            raw_text="Full description here with enough characters.",
            sections=[
                JDSection(heading="Requirements", content="Python, SQL"),
                JDSection(heading="Responsibilities", content="Analyze data"),
            ],
        )
        assert len(jd.sections) == 2
        assert jd.section_map["Requirements"] == "Python, SQL"

    def test_title_required(self):
        with pytest.raises(ValidationError):
            JobDescription(source=JDSource.TEXT, title="", raw_text="Some text here for testing")

    def test_raw_text_minimum_length(self):
        with pytest.raises(ValidationError):
            JobDescription(source=JDSource.TEXT, title="Test", raw_text="short")

    def test_full_text_property(self):
        jd = JobDescription(
            source=JDSource.TEXT,
            title="Test Role",
            raw_text="Full description text for testing purposes.",
        )
        assert jd.full_text == jd.raw_text


class TestExtractedSkill:
    def test_basic_skill(self):
        skill = ExtractedSkill(
            name="Python",
            category=SkillCategory.HARD,
            proficiency=SkillProficiency.EXPERT,
            importance=SkillImportance.REQUIRED,
            context="Backend development",
        )
        assert skill.name == "Python"
        assert skill.category == SkillCategory.HARD

    def test_defaults(self):
        skill = ExtractedSkill(name="Communication", category=SkillCategory.SOFT)
        assert skill.proficiency == SkillProficiency.INTERMEDIATE
        assert skill.importance == SkillImportance.REQUIRED
        assert skill.context == ""

    def test_name_required(self):
        with pytest.raises(ValidationError):
            ExtractedSkill(name="", category=SkillCategory.HARD)


class TestExtractedRole:
    def test_basic_role(self):
        role = ExtractedRole(
            title="Senior Engineer",
            purpose="Lead engineering projects",
            domain="Software Engineering",
        )
        assert role.seniority == SeniorityLevel.MID  # default
        assert role.domain == "Software Engineering"

    def test_all_seniority_levels(self):
        for level in SeniorityLevel:
            role = ExtractedRole(
                title="Test", purpose="Test role", seniority=level,
            )
            assert role.seniority == level


class TestSuggestedTraits:
    def test_defined_traits(self):
        traits = SuggestedTraits(warmth=0.8, rigor=0.9)
        defined = traits.defined_traits()
        assert defined == {"warmth": 0.8, "rigor": 0.9}

    def test_empty_traits(self):
        traits = SuggestedTraits()
        assert traits.defined_traits() == {}

    def test_trait_bounds(self):
        with pytest.raises(ValidationError):
            SuggestedTraits(warmth=1.5)
        with pytest.raises(ValidationError):
            SuggestedTraits(rigor=-0.1)


class TestExtractionResult:
    def test_from_fixture(self, sample_extraction):
        assert sample_extraction.role.title == "Senior Data Engineer"
        assert len(sample_extraction.skills) == 5
        assert sample_extraction.automation_potential == 0.35

    def test_defaults(self):
        result = ExtractionResult(
            role=ExtractedRole(title="Test", purpose="Test role"),
        )
        assert result.skills == []
        assert result.automation_potential == 0.0
        assert result.automation_rationale == ""


class TestCultureProfile:
    def test_basic_culture(self):
        culture = CultureProfile(
            name="Acme Corp Culture",
            description="Innovation-driven startup culture",
            values=[
                CultureValue(
                    name="Innovation",
                    description="We push boundaries",
                    behavioral_indicators=["Question assumptions", "Experiment freely"],
                    trait_deltas={"creativity": 0.2, "rigor": -0.1},
                ),
            ],
            communication_tone="collaborative",
        )
        assert len(culture.values) == 1
        assert culture.values[0].trait_deltas["creativity"] == 0.2

    def test_empty_culture(self):
        culture = CultureProfile(name="Minimal")
        assert culture.values == []
        assert culture.communication_tone is None


class TestAgentBlueprint:
    def test_basic_blueprint(self, sample_jd, sample_extraction):
        blueprint = AgentBlueprint(
            source_jd=sample_jd,
            extraction=sample_extraction,
            identity_yaml="schema_version: '1.0'\nmetadata:\n  id: agt_test_001",
            coverage_score=0.85,
            coverage_gaps=["Mentoring capability"],
            automation_estimate=0.35,
        )
        assert blueprint.coverage_score == 0.85
        assert len(blueprint.coverage_gaps) == 1
        assert blueprint.culture is None

    def test_coverage_bounds(self, sample_jd, sample_extraction):
        with pytest.raises(ValidationError):
            AgentBlueprint(
                source_jd=sample_jd,
                extraction=sample_extraction,
                identity_yaml="test",
                coverage_score=1.5,
            )
