"""Tests for trait and role mapping modules."""

from __future__ import annotations

import pytest

from agentforge.mapping.trait_mapper import (
    DOMAIN_TRAIT_PROFILES,
    TraitMapper,
    _clamp,
    _match_domain,
)
from agentforge.mapping.role_mapper import (
    RoleMapper,
    _generate_agent_id,
    _proficiency_to_level,
    _seniority_to_register,
    _skill_to_category,
)
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


class TestTraitMapper:
    def test_basic_mapping(self, sample_extraction):
        mapper = TraitMapper()
        traits = mapper.map_traits(sample_extraction)

        assert isinstance(traits, dict)
        assert len(traits) > 0
        for value in traits.values():
            assert 0.0 <= value <= 1.0

    def test_data_domain_has_high_rigor(self, sample_extraction):
        mapper = TraitMapper()
        traits = mapper.map_traits(sample_extraction)
        assert traits["rigor"] >= 0.7

    def test_llm_weight_blending(self, sample_extraction):
        # With 100% LLM weight, should match LLM suggestions closely
        mapper_full_llm = TraitMapper(llm_weight=1.0)
        traits = mapper_full_llm.map_traits(sample_extraction)
        assert abs(traits["rigor"] - 0.85) < 0.01

        # With 0% LLM weight, should ignore LLM suggestions
        mapper_no_llm = TraitMapper(llm_weight=0.0)
        traits_no_llm = mapper_no_llm.map_traits(sample_extraction)
        # Should use domain profile + seniority deltas only (no LLM), clamped to [0,1]
        expected = min(1.0, DOMAIN_TRAIT_PROFILES["data"]["rigor"] + 0.05)
        assert traits_no_llm["rigor"] == round(expected, 2)

    def test_seniority_adjustment(self):
        junior = ExtractionResult(
            role=ExtractedRole(
                title="Junior Engineer",
                purpose="Write code",
                seniority=SeniorityLevel.JUNIOR,
                domain="engineering",
            ),
        )
        senior = ExtractionResult(
            role=ExtractedRole(
                title="Senior Engineer",
                purpose="Lead projects",
                seniority=SeniorityLevel.SENIOR,
                domain="engineering",
            ),
        )
        mapper = TraitMapper(llm_weight=0.0)
        j_traits = mapper.map_traits(junior)
        s_traits = mapper.map_traits(senior)

        assert s_traits["assertiveness"] > j_traits["assertiveness"]

    def test_soft_skill_boosts(self):
        result = ExtractionResult(
            role=ExtractedRole(title="Manager", purpose="Lead team", domain="management"),
            skills=[
                ExtractedSkill(name="Leadership", category=SkillCategory.SOFT),
                ExtractedSkill(name="Mentoring", category=SkillCategory.SOFT),
            ],
        )
        mapper = TraitMapper(llm_weight=0.0)
        traits = mapper.map_traits(result)
        # Leadership and mentoring should boost assertiveness and patience
        assert traits["assertiveness"] > DOMAIN_TRAIT_PROFILES["management"]["assertiveness"]

    def test_all_traits_clamped(self):
        # Force extreme values
        result = ExtractionResult(
            role=ExtractedRole(title="Test", purpose="Test", domain="engineering"),
            suggested_traits=SuggestedTraits(
                warmth=1.0, rigor=1.0, directness=1.0,
                patience=1.0, creativity=1.0,
            ),
        )
        mapper = TraitMapper(llm_weight=1.0)
        traits = mapper.map_traits(result)
        for v in traits.values():
            assert 0.0 <= v <= 1.0


class TestClampAndMatch:
    def test_clamp(self):
        assert _clamp(0.5) == 0.5
        assert _clamp(-0.1) == 0.0
        assert _clamp(1.5) == 1.0

    def test_match_domain_exact(self):
        assert _match_domain("engineering") == "engineering"
        assert _match_domain("Data Engineering") == "data"
        assert _match_domain("finance") == "finance"

    def test_match_domain_fuzzy(self):
        assert _match_domain("Software Development") == "engineering"
        assert _match_domain("Machine Learning Research") == "research"
        assert _match_domain("Customer Success") == "support"

    def test_match_domain_fallback(self):
        assert _match_domain("Underwater Basket Weaving") == "general"


class TestRoleMapper:
    def test_build_metadata(self, sample_extraction):
        mapper = RoleMapper()
        meta = mapper.build_metadata(sample_extraction)

        assert meta["id"].startswith("agt_")
        assert meta["version"] == "1.0.0"
        assert meta["status"] == "draft"
        assert "agentforge" in meta["tags"]

    def test_build_role(self, sample_extraction):
        mapper = RoleMapper()
        role = mapper.build_role(sample_extraction)

        assert role["title"] == "Senior Data Engineer"
        assert "scope" in role
        assert "primary" in role["scope"]

    def test_build_expertise(self, sample_extraction):
        mapper = RoleMapper()
        expertise = mapper.build_expertise(sample_extraction)

        assert "domains" in expertise
        # Only non-soft skills should be included
        domain_names = [d["name"] for d in expertise["domains"]]
        assert "Python" in domain_names
        assert "Team Collaboration" not in domain_names

    def test_build_communication(self, sample_extraction):
        mapper = RoleMapper()
        comm = mapper.build_communication(sample_extraction)

        assert comm["tone"]["default"] == "professional"
        assert comm["tone"]["register"] == "consultative"  # senior level

    def test_build_principles(self, sample_extraction):
        mapper = RoleMapper()
        principles = mapper.build_principles(sample_extraction)

        assert len(principles) >= 2
        ids = [p["id"] for p in principles]
        assert "accuracy" in ids
        assert "role_alignment" in ids
        # Data domain should get data_integrity
        assert "data_integrity" in ids

    def test_build_guardrails(self, sample_extraction):
        mapper = RoleMapper()
        guardrails = mapper.build_guardrails(sample_extraction)

        assert "hard" in guardrails
        assert len(guardrails["hard"]) >= 2
        # Data domain should get data_privacy
        ids = [g["id"] for g in guardrails["hard"]]
        assert "data_privacy" in ids


class TestHelpers:
    def test_generate_agent_id(self):
        assert _generate_agent_id("Senior Data Engineer") == "agt_senior_data_engineer_001"
        assert _generate_agent_id("ML Research Scientist") == "agt_ml_research_scientist_001"

    def test_proficiency_to_level(self):
        assert _proficiency_to_level(SkillProficiency.BEGINNER) == 0.3
        assert _proficiency_to_level(SkillProficiency.EXPERT) == 0.9

    def test_seniority_to_register(self):
        assert _seniority_to_register(SeniorityLevel.JUNIOR) == "casual"
        assert _seniority_to_register(SeniorityLevel.EXECUTIVE) == "formal"

    def test_skill_to_category(self):
        skill = ExtractedSkill(
            name="Python", category=SkillCategory.HARD, importance=SkillImportance.REQUIRED,
        )
        assert _skill_to_category(skill) == "primary"
