"""Map extracted role and skills to PersonaNexus Role, Expertise, Communication, and Guardrails."""

from __future__ import annotations

from datetime import datetime, timezone

from agentforge.models.extracted_skills import (
    ExtractionResult,
    ExtractedSkill,
    SeniorityLevel,
    SkillCategory,
    SkillImportance,
    SkillProficiency,
)


def _proficiency_to_level(prof: SkillProficiency) -> float:
    """Convert skill proficiency to PersonaNexus expertise level (0-1)."""
    return {
        SkillProficiency.BEGINNER: 0.3,
        SkillProficiency.INTERMEDIATE: 0.5,
        SkillProficiency.ADVANCED: 0.7,
        SkillProficiency.EXPERT: 0.9,
    }[prof]


def _skill_to_category(skill: ExtractedSkill) -> str:
    """Map skill importance to PersonaNexus expertise category."""
    return {
        SkillImportance.REQUIRED: "primary",
        SkillImportance.PREFERRED: "secondary",
        SkillImportance.NICE_TO_HAVE: "tertiary",
    }[skill.importance]


def _seniority_to_register(seniority: SeniorityLevel) -> str:
    """Map seniority level to communication register."""
    return {
        SeniorityLevel.JUNIOR: "casual",
        SeniorityLevel.MID: "consultative",
        SeniorityLevel.SENIOR: "consultative",
        SeniorityLevel.LEAD: "consultative",
        SeniorityLevel.EXECUTIVE: "formal",
    }[seniority]


def _generate_agent_id(title: str) -> str:
    """Generate a PersonaNexus-compatible agent ID from a role title."""
    slug = title.lower()
    slug = slug.replace(" ", "_").replace("-", "_")
    # Keep only alphanumeric and underscores
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    # Truncate and ensure valid
    slug = slug[:30].strip("_")
    return f"agt_{slug}_001"


class RoleMapper:
    """Maps extraction results to PersonaNexus-compatible data structures."""

    def build_metadata(self, extraction: ExtractionResult) -> dict:
        """Build PersonaNexus metadata section."""
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": _generate_agent_id(extraction.role.title),
            "name": extraction.role.title.replace(" ", ""),
            "version": "1.0.0",
            "description": extraction.role.purpose,
            "created_at": now,
            "updated_at": now,
            "status": "draft",
            "tags": ["agentforge", "generated", extraction.role.domain.lower()],
        }

    def build_role(self, extraction: ExtractionResult) -> dict:
        """Build PersonaNexus role section."""
        role = extraction.role
        result: dict = {
            "title": role.title,
            "purpose": role.purpose,
            "scope": {
                "primary": role.scope_primary or [role.purpose],
            },
        }
        if role.scope_secondary:
            result["scope"]["secondary"] = role.scope_secondary
        if role.audience:
            result["audience"] = {
                "primary": role.audience[0] if role.audience else "General users",
            }
            if len(role.audience) > 1:
                result["audience"]["secondary"] = ", ".join(role.audience[1:])
        return result

    def build_expertise(self, extraction: ExtractionResult) -> dict:
        """Build PersonaNexus expertise section from extracted skills."""
        domains = []
        for skill in extraction.skills:
            if skill.category in (SkillCategory.HARD, SkillCategory.DOMAIN, SkillCategory.TOOL):
                domains.append({
                    "name": skill.name,
                    "level": _proficiency_to_level(skill.proficiency),
                    "category": _skill_to_category(skill),
                    "can_teach": skill.proficiency in (
                        SkillProficiency.ADVANCED, SkillProficiency.EXPERT
                    ),
                })
        return {
            "domains": domains,
            "out_of_expertise_strategy": "acknowledge_and_redirect",
        }

    def build_communication(self, extraction: ExtractionResult) -> dict:
        """Build PersonaNexus communication section."""
        register = _seniority_to_register(extraction.role.seniority)
        return {
            "tone": {
                "default": "professional",
                "register": register,
            },
            "language": {
                "primary": "en",
            },
        }

    def build_principles(self, extraction: ExtractionResult) -> list[dict]:
        """Generate core principles from the role context."""
        principles = [
            {
                "id": "accuracy",
                "priority": 1,
                "statement": "Provide accurate, well-researched information",
                "implications": [
                    "Verify facts before presenting them",
                    "Cite sources when possible",
                ],
            },
            {
                "id": "role_alignment",
                "priority": 2,
                "statement": f"Stay focused on {extraction.role.domain.lower()} responsibilities",
                "implications": [
                    f"Prioritize {', '.join(extraction.role.scope_primary[:2]) if extraction.role.scope_primary else 'core tasks'}",
                ],
            },
        ]

        # Add domain-specific principle
        domain = extraction.role.domain.lower()
        if any(kw in domain for kw in ["data", "analytics", "ml", "research"]):
            principles.append({
                "id": "data_integrity",
                "priority": 3,
                "statement": "Maintain data quality and methodological rigor",
                "implications": ["Document assumptions", "Validate data sources"],
            })
        elif any(kw in domain for kw in ["customer", "support", "success"]):
            principles.append({
                "id": "customer_first",
                "priority": 3,
                "statement": "Prioritize customer outcomes and satisfaction",
                "implications": ["Listen actively", "Follow up proactively"],
            })
        elif any(kw in domain for kw in ["engineer", "software", "devops"]):
            principles.append({
                "id": "quality_code",
                "priority": 3,
                "statement": "Write maintainable, well-tested code",
                "implications": ["Follow established patterns", "Document decisions"],
            })
        else:
            principles.append({
                "id": "continuous_improvement",
                "priority": 3,
                "statement": "Continuously seek to improve processes and outcomes",
                "implications": ["Learn from feedback", "Adopt best practices"],
            })

        return principles

    def build_guardrails(self, extraction: ExtractionResult) -> dict:
        """Build PersonaNexus guardrails section."""
        hard_guardrails = [
            {
                "id": "no_harmful_content",
                "rule": "Never generate harmful, misleading, or unethical content",
                "enforcement": "output_filter",
                "severity": "critical",
            },
            {
                "id": "scope_boundary",
                "rule": f"Do not act outside the scope of {extraction.role.title}",
                "enforcement": "prompt_instruction",
                "severity": "high",
            },
        ]

        # Add domain-specific guardrails
        domain = extraction.role.domain.lower()
        if any(kw in domain for kw in ["data", "finance", "legal", "health"]):
            hard_guardrails.append({
                "id": "data_privacy",
                "rule": "Never expose or mishandle sensitive or personal data",
                "enforcement": "output_filter",
                "severity": "critical",
            })

        return {"hard": hard_guardrails}
