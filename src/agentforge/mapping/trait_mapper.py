"""Map extracted skills and role information to PersonaNexus personality traits."""

from __future__ import annotations

from agentforge.models.extracted_skills import (
    ExtractionResult,
    SeniorityLevel,
    SkillCategory,
    SuggestedTraits,
)

# Deterministic base trait profiles by role domain.
# These provide a consistent baseline that LLM suggestions refine.
DOMAIN_TRAIT_PROFILES: dict[str, dict[str, float]] = {
    "engineering": {
        "rigor": 0.8,
        "directness": 0.7,
        "creativity": 0.6,
        "patience": 0.5,
        "warmth": 0.4,
        "verbosity": 0.4,
    },
    "data": {
        "rigor": 0.85,
        "directness": 0.7,
        "epistemic_humility": 0.7,
        "patience": 0.6,
        "creativity": 0.5,
        "verbosity": 0.5,
    },
    "research": {
        "rigor": 0.9,
        "epistemic_humility": 0.8,
        "creativity": 0.7,
        "patience": 0.7,
        "verbosity": 0.6,
        "directness": 0.6,
    },
    "sales": {
        "warmth": 0.8,
        "assertiveness": 0.7,
        "empathy": 0.6,
        "humor": 0.5,
        "directness": 0.6,
        "patience": 0.5,
    },
    "support": {
        "empathy": 0.85,
        "patience": 0.85,
        "warmth": 0.8,
        "directness": 0.5,
        "verbosity": 0.5,
        "rigor": 0.5,
    },
    "management": {
        "assertiveness": 0.7,
        "directness": 0.7,
        "empathy": 0.6,
        "warmth": 0.6,
        "patience": 0.5,
        "rigor": 0.6,
    },
    "marketing": {
        "creativity": 0.8,
        "warmth": 0.6,
        "empathy": 0.6,
        "humor": 0.5,
        "verbosity": 0.6,
        "assertiveness": 0.5,
    },
    "finance": {
        "rigor": 0.9,
        "directness": 0.7,
        "epistemic_humility": 0.6,
        "patience": 0.6,
        "warmth": 0.3,
        "creativity": 0.3,
    },
    "hr": {
        "empathy": 0.8,
        "warmth": 0.8,
        "patience": 0.7,
        "assertiveness": 0.5,
        "directness": 0.5,
        "rigor": 0.5,
    },
    "legal": {
        "rigor": 0.9,
        "directness": 0.7,
        "epistemic_humility": 0.7,
        "patience": 0.6,
        "verbosity": 0.7,
        "warmth": 0.3,
    },
    "general": {
        "warmth": 0.5,
        "verbosity": 0.5,
        "directness": 0.5,
        "patience": 0.5,
        "rigor": 0.5,
        "empathy": 0.5,
    },
}

# Seniority adjustments: deltas applied on top of domain profiles
SENIORITY_DELTAS: dict[SeniorityLevel, dict[str, float]] = {
    SeniorityLevel.JUNIOR: {
        "epistemic_humility": 0.1,
        "patience": 0.05,
        "assertiveness": -0.1,
    },
    SeniorityLevel.MID: {},
    SeniorityLevel.SENIOR: {
        "assertiveness": 0.05,
        "directness": 0.05,
        "rigor": 0.05,
    },
    SeniorityLevel.LEAD: {
        "assertiveness": 0.1,
        "directness": 0.1,
        "empathy": 0.05,
        "warmth": 0.05,
    },
    SeniorityLevel.EXECUTIVE: {
        "assertiveness": 0.15,
        "directness": 0.15,
        "warmth": 0.05,
        "verbosity": -0.1,
    },
}

# Soft skill presence boosts
SOFT_SKILL_BOOSTS: dict[str, dict[str, float]] = {
    "communication": {"warmth": 0.05, "verbosity": 0.05},
    "collaboration": {"warmth": 0.05, "empathy": 0.05},
    "leadership": {"assertiveness": 0.1, "directness": 0.05},
    "mentoring": {"patience": 0.1, "empathy": 0.05, "warmth": 0.05},
    "problem-solving": {"creativity": 0.05, "rigor": 0.05},
    "critical thinking": {"rigor": 0.1, "epistemic_humility": 0.05},
    "presentation": {"assertiveness": 0.05, "verbosity": 0.05},
    "empathy": {"empathy": 0.1, "warmth": 0.05},
    "negotiation": {"assertiveness": 0.05, "empathy": 0.05, "directness": 0.05},
    "creativity": {"creativity": 0.1, "humor": 0.05},
}


def _clamp(value: float) -> float:
    """Clamp a trait value to [0, 1]."""
    return max(0.0, min(1.0, value))


def _match_domain(domain: str) -> str:
    """Match a domain string to our profile keys."""
    domain_lower = domain.lower()

    # Fuzzy matches first (more specific patterns)
    if any(kw in domain_lower for kw in ["data engineer", "data pipeline", "analytics", "bi", "warehouse"]):
        return "data"
    if any(kw in domain_lower for kw in ["ml", "machine learning", "ai", "deep learning"]):
        return "research"
    if any(kw in domain_lower for kw in ["software", "devops", "backend", "frontend", "fullstack"]):
        return "engineering"
    if any(kw in domain_lower for kw in ["customer", "account", "success"]):
        return "support"
    if any(kw in domain_lower for kw in ["product", "program", "project"]):
        return "management"

    # Exact key match
    for key in sorted(DOMAIN_TRAIT_PROFILES.keys(), key=len, reverse=True):
        if key in domain_lower:
            return key

    return "general"


class TraitMapper:
    """Maps extraction results to PersonaNexus personality traits.

    Uses a two-layer approach:
    1. Deterministic baseline from domain + seniority tables
    2. LLM-suggested refinements blended in with configurable weight
    """

    def __init__(self, llm_weight: float = 0.4):
        self.llm_weight = llm_weight

    def map_traits(self, extraction: ExtractionResult) -> dict[str, float]:
        """Produce a complete trait dictionary from extraction results."""
        domain_key = _match_domain(extraction.role.domain)
        base = dict(DOMAIN_TRAIT_PROFILES.get(domain_key, DOMAIN_TRAIT_PROFILES["general"]))

        # Apply seniority deltas
        deltas = SENIORITY_DELTAS.get(extraction.role.seniority, {})
        for trait, delta in deltas.items():
            base[trait] = _clamp(base.get(trait, 0.5) + delta)

        # Apply soft skill boosts
        for skill in extraction.skills:
            if skill.category == SkillCategory.SOFT:
                skill_lower = skill.name.lower()
                for keyword, boosts in SOFT_SKILL_BOOSTS.items():
                    if keyword in skill_lower:
                        for trait, boost in boosts.items():
                            base[trait] = _clamp(base.get(trait, 0.5) + boost)

        # Blend in LLM suggestions
        llm_traits = extraction.suggested_traits.defined_traits()
        if llm_traits:
            det_weight = 1.0 - self.llm_weight
            for trait, llm_val in llm_traits.items():
                det_val = base.get(trait, 0.5)
                base[trait] = _clamp(det_weight * det_val + self.llm_weight * llm_val)

        # Round to 2 decimal places
        return {k: round(v, 2) for k, v in sorted(base.items())}
