"""Tests for gap analysis module."""

from __future__ import annotations

import pytest

from agentforge.analysis.gap_analyzer import GapAnalyzer
from agentforge.models.extracted_skills import (
    ExtractionResult,
    ExtractedRole,
    ExtractedSkill,
    SkillCategory,
    SkillImportance,
    SkillProficiency,
    SuggestedTraits,
)


class TestGapAnalyzer:
    def test_basic_analysis(self, sample_extraction):
        analyzer = GapAnalyzer()
        score, gaps = analyzer.analyze(sample_extraction)

        assert 0.0 <= score <= 1.0
        assert isinstance(gaps, list)

    def test_soft_skills_reduce_coverage(self):
        """Soft skills should have lower coverage than hard skills."""
        hard_only = ExtractionResult(
            role=ExtractedRole(title="Test", purpose="Test", domain="test"),
            skills=[
                ExtractedSkill(name="Python", category=SkillCategory.HARD, importance="required"),
                ExtractedSkill(name="SQL", category=SkillCategory.HARD, importance="required"),
            ],
        )
        soft_only = ExtractionResult(
            role=ExtractedRole(title="Test", purpose="Test", domain="test"),
            skills=[
                ExtractedSkill(name="Leadership", category=SkillCategory.SOFT, importance="required"),
                ExtractedSkill(name="Empathy", category=SkillCategory.SOFT, importance="required"),
            ],
        )
        analyzer = GapAnalyzer()
        hard_score, _ = analyzer.analyze(hard_only)
        soft_score, soft_gaps = analyzer.analyze(soft_only)

        assert hard_score > soft_score
        assert len(soft_gaps) > 0

    def test_human_responsibilities_create_gaps(self):
        result = ExtractionResult(
            role=ExtractedRole(title="Manager", purpose="Lead team", domain="management"),
            responsibilities=[
                "Mentor junior engineers",
                "Interview candidates",
                "Negotiate contracts",
            ],
        )
        analyzer = GapAnalyzer()
        score, gaps = analyzer.analyze(result)

        # All responsibilities require human element
        assert len(gaps) == 3
        assert score < 0.5

    def test_empty_extraction(self):
        result = ExtractionResult(
            role=ExtractedRole(title="Empty", purpose="Nothing", domain="none"),
        )
        analyzer = GapAnalyzer()
        score, gaps = analyzer.analyze(result)

        assert score == 0.0
        assert gaps == []

    def test_importance_weighting(self):
        """Required skills should have more weight than nice-to-have."""
        required_only = ExtractionResult(
            role=ExtractedRole(title="Test", purpose="Test", domain="test"),
            skills=[
                ExtractedSkill(
                    name="Critical Thinking", category=SkillCategory.SOFT,
                    importance=SkillImportance.REQUIRED,
                ),
            ],
        )
        nice_only = ExtractionResult(
            role=ExtractedRole(title="Test", purpose="Test", domain="test"),
            skills=[
                ExtractedSkill(
                    name="Nice Thing", category=SkillCategory.SOFT,
                    importance=SkillImportance.NICE_TO_HAVE,
                ),
            ],
        )
        analyzer = GapAnalyzer()
        _, req_gaps = analyzer.analyze(required_only)
        _, nice_gaps = analyzer.analyze(nice_only)

        # Required soft skills generate gaps, nice-to-have don't
        assert len(req_gaps) > len(nice_gaps)


class TestDetailedAnalysis:
    def test_detailed_returns_skill_scores(self, sample_extraction):
        analyzer = GapAnalyzer()
        score, gaps, skill_scores = analyzer.detailed_analyze(sample_extraction)

        assert 0.0 <= score <= 1.0
        assert isinstance(skill_scores, list)
        assert len(skill_scores) == len(sample_extraction.skills)

    def test_skill_scores_have_required_fields(self, sample_extraction):
        analyzer = GapAnalyzer()
        _, _, skill_scores = analyzer.detailed_analyze(sample_extraction)

        for entry in skill_scores:
            assert "skill" in entry
            assert "score" in entry
            assert "priority" in entry
            assert "weight" in entry
            assert "category" in entry

    def test_skill_scores_sorted_by_weight(self, sample_extraction):
        analyzer = GapAnalyzer()
        _, _, skill_scores = analyzer.detailed_analyze(sample_extraction)

        weights = [s["weight"] for s in skill_scores]
        assert weights == sorted(weights, reverse=True)

    def test_soft_skills_lower_score(self):
        result = ExtractionResult(
            role=ExtractedRole(title="Test", purpose="Test", domain="test"),
            skills=[
                ExtractedSkill(name="Python", category=SkillCategory.HARD, importance="required"),
                ExtractedSkill(name="Empathy", category=SkillCategory.SOFT, importance="required"),
            ],
        )
        analyzer = GapAnalyzer()
        _, _, skill_scores = analyzer.detailed_analyze(result)

        python = next(s for s in skill_scores if s["skill"] == "Python")
        empathy = next(s for s in skill_scores if s["skill"] == "Empathy")
        assert python["score"] > empathy["score"]

    def test_priority_labels(self):
        result = ExtractionResult(
            role=ExtractedRole(title="Test", purpose="Test", domain="test"),
            skills=[
                ExtractedSkill(name="A", category=SkillCategory.HARD, importance="required"),
                ExtractedSkill(name="B", category=SkillCategory.HARD, importance="preferred"),
                ExtractedSkill(name="C", category=SkillCategory.HARD, importance="nice_to_have"),
            ],
        )
        analyzer = GapAnalyzer()
        _, _, skill_scores = analyzer.detailed_analyze(result)

        priorities = {s["skill"]: s["priority"] for s in skill_scores}
        assert priorities["A"] == "critical"
        assert priorities["B"] == "high"
        assert priorities["C"] == "low"
