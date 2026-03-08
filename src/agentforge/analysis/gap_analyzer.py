"""Gap analysis: compare generated agent capabilities against JD requirements."""

from __future__ import annotations

from typing import Any

from agentforge.models.extracted_skills import ExtractionResult, SkillCategory, SkillImportance


class GapAnalyzer:
    """Analyzes coverage gaps between a generated agent and the source JD."""

    def analyze(self, extraction: ExtractionResult) -> tuple[float, list[str]]:
        """Compute coverage score and identify gaps.

        Returns:
            Tuple of (coverage_score 0-1, list of gap descriptions)
        """
        gaps: list[str] = []
        total_weight = 0.0
        covered_weight = 0.0

        # Weight skills by importance
        importance_weights = {
            SkillImportance.REQUIRED: 1.0,
            SkillImportance.PREFERRED: 0.5,
            SkillImportance.NICE_TO_HAVE: 0.2,
        }

        # Assess skill coverage
        for skill in extraction.skills:
            weight = importance_weights.get(skill.importance, 0.5)
            total_weight += weight

            # Soft skills are harder to automate
            if skill.category == SkillCategory.SOFT:
                covered_weight += weight * 0.5
                if skill.importance == SkillImportance.REQUIRED:
                    gaps.append(
                        f"Soft skill '{skill.name}' may require human judgment"
                    )
            else:
                covered_weight += weight * 0.8

        # Assess responsibility coverage
        responsibility_weight = 0.3  # each responsibility
        for resp in extraction.responsibilities:
            total_weight += responsibility_weight
            resp_lower = resp.lower()

            # Flag responsibilities requiring human judgment
            human_keywords = [
                "mentor", "lead", "negotiate", "present", "interview",
                "hire", "fire", "counsel", "coach", "empathize",
                "relationship", "stakeholder", "executive",
            ]
            if any(kw in resp_lower for kw in human_keywords):
                covered_weight += responsibility_weight * 0.3
                gaps.append(f"Responsibility requires human element: '{resp[:60]}'")
            else:
                covered_weight += responsibility_weight * 0.7

        # Compute coverage
        coverage = covered_weight / total_weight if total_weight > 0 else 0.0
        coverage = round(min(1.0, coverage), 2)

        return coverage, gaps

    def detailed_analyze(
        self, extraction: ExtractionResult
    ) -> tuple[float, list[str], list[dict[str, Any]]]:
        """Deep analysis with per-skill scoring and priority ranking.

        Returns:
            Tuple of (coverage_score, gap_descriptions, skill_scores)
            where skill_scores is a list of dicts with skill, score, priority.
        """
        coverage, gaps = self.analyze(extraction)

        importance_weights = {
            SkillImportance.REQUIRED: 1.0,
            SkillImportance.PREFERRED: 0.5,
            SkillImportance.NICE_TO_HAVE: 0.2,
        }

        priority_labels = {
            SkillImportance.REQUIRED: "critical",
            SkillImportance.PREFERRED: "high",
            SkillImportance.NICE_TO_HAVE: "low",
        }

        skill_scores: list[dict[str, Any]] = []
        for skill in extraction.skills:
            if skill.category == SkillCategory.SOFT:
                score = 0.5
            else:
                score = 0.8

            skill_scores.append({
                "skill": skill.name,
                "category": skill.category.value,
                "score": score,
                "weight": importance_weights.get(skill.importance, 0.5),
                "priority": priority_labels.get(skill.importance, "medium"),
                "context": skill.context,
            })

        # Sort by weight descending, then score ascending (worst coverage first)
        skill_scores.sort(key=lambda x: (-x["weight"], x["score"]))

        return coverage, gaps, skill_scores
