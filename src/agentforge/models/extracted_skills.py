"""Data models for LLM-extracted skills and role information."""

from __future__ import annotations

import enum

import logging

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class SkillCategory(enum.StrEnum):
    HARD = "hard"
    SOFT = "soft"
    DOMAIN = "domain"
    TOOL = "tool"


class SkillProficiency(enum.StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SkillImportance(enum.StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    NICE_TO_HAVE = "nice_to_have"


class SeniorityLevel(enum.StrEnum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"


def _coerce_enum(value: str, enum_cls: type[enum.StrEnum], default: enum.StrEnum) -> enum.StrEnum:
    """Try to match a value to an enum, falling back to default for LLM hallucinations."""
    if value is None:
        return default
    if isinstance(value, enum_cls):
        return value
    normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    # Try exact match first
    try:
        return enum_cls(normalized)
    except ValueError:
        pass
    # Try substring/prefix match (e.g. "expert_level" → "expert", "hard_skill" → "hard")
    for member in enum_cls:
        if normalized.startswith(member.value) or member.value.startswith(normalized):
            return member
    logger.warning("Coercing invalid %s value %r → %s", enum_cls.__name__, value, default)
    return default


class ExtractedSkill(BaseModel):
    """A single skill extracted from a job description."""

    name: str = Field(..., min_length=1)
    category: SkillCategory
    proficiency: SkillProficiency = SkillProficiency.INTERMEDIATE
    importance: SkillImportance = SkillImportance.REQUIRED
    context: str = Field(default="", description="How this skill is used in the role")
    examples: list[str] = Field(
        default_factory=list,
        description="Specific tools, libraries, or applications (e.g., 'Salesforce for CRM', 'Hugging Face for NLP')",
    )
    genai_application: str = Field(
        default="",
        description="How GenAI/ML can augment or automate this skill area",
    )

    @field_validator("proficiency", mode="before")
    @classmethod
    def coerce_proficiency(cls, v: object) -> SkillProficiency:
        return _coerce_enum(v, SkillProficiency, SkillProficiency.INTERMEDIATE)

    @field_validator("importance", mode="before")
    @classmethod
    def coerce_importance(cls, v: object) -> SkillImportance:
        return _coerce_enum(v, SkillImportance, SkillImportance.REQUIRED)

    @field_validator("category", mode="before")
    @classmethod
    def coerce_category(cls, v: object) -> SkillCategory:
        return _coerce_enum(v, SkillCategory, SkillCategory.HARD)

    @field_validator("context", "genai_application", mode="before")
    @classmethod
    def coerce_none_str(cls, v: object) -> str:
        if v is None:
            return ""
        return v

    @field_validator("examples", mode="before")
    @classmethod
    def coerce_none_examples(cls, v: object) -> list:
        if v is None or v == "":
            return []
        return v


class ExtractedRole(BaseModel):
    """Role information extracted from a job description."""

    title: str
    purpose: str = Field(..., min_length=1)
    scope_primary: list[str] = Field(default_factory=list)
    scope_secondary: list[str] = Field(default_factory=list)
    audience: list[str] = Field(default_factory=list)
    seniority: SeniorityLevel = SeniorityLevel.MID
    domain: str = Field(default="general")

    @field_validator("scope_primary", "scope_secondary", "audience", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v: object) -> list:
        """LLM may return None or empty string for list fields; coerce to empty list."""
        if v is None or v == "":
            return []
        return v

    @field_validator("seniority", mode="before")
    @classmethod
    def coerce_seniority(cls, v: object) -> SeniorityLevel:
        return _coerce_enum(v, SeniorityLevel, SeniorityLevel.MID)

    @field_validator("domain", mode="before")
    @classmethod
    def coerce_domain(cls, v: object) -> str:
        if v is None:
            return "general"
        return v

    @field_validator("title", "purpose", mode="before")
    @classmethod
    def coerce_none_to_empty_string(cls, v: object) -> str:
        if v is None:
            return ""
        return v


class SuggestedTraits(BaseModel):
    """LLM-suggested personality traits for the agent (0-1 scale)."""

    warmth: float | None = Field(None, ge=0.0, le=1.0)
    verbosity: float | None = Field(None, ge=0.0, le=1.0)
    assertiveness: float | None = Field(None, ge=0.0, le=1.0)
    humor: float | None = Field(None, ge=0.0, le=1.0)
    empathy: float | None = Field(None, ge=0.0, le=1.0)
    directness: float | None = Field(None, ge=0.0, le=1.0)
    rigor: float | None = Field(None, ge=0.0, le=1.0)
    creativity: float | None = Field(None, ge=0.0, le=1.0)
    epistemic_humility: float | None = Field(None, ge=0.0, le=1.0)
    patience: float | None = Field(None, ge=0.0, le=1.0)

    def defined_traits(self) -> dict[str, float]:
        """Return only traits that have been explicitly set."""
        return {
            k: v
            for k, v in self.model_dump(exclude_none=True).items()
            if isinstance(v, (int, float))
        }


class ExtractionResult(BaseModel):
    """Complete extraction output from analyzing a job description."""

    role: ExtractedRole
    skills: list[ExtractedSkill] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    suggested_traits: SuggestedTraits = Field(default_factory=SuggestedTraits)
    automation_potential: float = Field(0.0, ge=0.0, le=1.0)
    automation_rationale: str = ""

    salary_min: float | None = Field(
        None, ge=0, description="Minimum annual salary if stated in the JD"
    )
    salary_max: float | None = Field(
        None, ge=0, description="Maximum annual salary if stated in the JD"
    )

    @field_validator("skills", "responsibilities", "qualifications", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v: object) -> list:
        """LLM may return None or empty string for list fields; coerce to empty list."""
        if v is None or v == "":
            return []
        return v

    @field_validator("automation_potential", mode="before")
    @classmethod
    def coerce_none_to_zero(cls, v: object) -> float:
        """LLM may return None for automation_potential; coerce to 0."""
        if v is None:
            return 0.0
        return v

    @field_validator("suggested_traits", mode="before")
    @classmethod
    def coerce_none_to_default_traits(cls, v: object) -> dict | SuggestedTraits:
        """LLM may return None for suggested_traits; coerce to empty traits."""
        if v is None:
            return {}
        return v

    @field_validator("automation_rationale", mode="before")
    @classmethod
    def coerce_none_to_empty_str(cls, v: object) -> str:
        """LLM may return None for string fields; coerce to empty string."""
        if v is None:
            return ""
        return v


# ---------------------------------------------------------------------------
# Methodology layer — procedural knowledge for actionable skill output
# ---------------------------------------------------------------------------


class Heuristic(BaseModel):
    """A concrete decision-making rule derived from a responsibility."""

    trigger: str = Field(..., description="When this situation arises (e.g. 'When evaluating a codebase for enhancements')")
    procedure: str = Field(..., description="Step-by-step procedure to follow")
    source_responsibility: str = Field(default="", description="The original responsibility this was derived from")

    @field_validator("source_responsibility", mode="before")
    @classmethod
    def coerce_none_str(cls, v: object) -> str:
        if v is None:
            return ""
        return v


class OutputTemplate(BaseModel):
    """A role-specific output scaffold or framework."""

    name: str = Field(..., description="Template name (e.g. 'Architecture Decision Record')")
    when_to_use: str = Field(default="", description="Situation that calls for this template")
    template: str = Field(..., description="The template content with placeholders")

    @field_validator("when_to_use", mode="before")
    @classmethod
    def coerce_none_str(cls, v: object) -> str:
        if v is None:
            return ""
        return v


class TriggerTechniqueMapping(BaseModel):
    """Pattern-matched routing: trigger pattern → technique to apply."""

    trigger_pattern: str = Field(..., description="When asked to... (e.g. 'evaluate an open-source project')")
    technique: str = Field(..., description="The specific approach or framework to use")
    output_format: str = Field(default="", description="What the output should look like")

    @field_validator("output_format", mode="before")
    @classmethod
    def coerce_none_str(cls, v: object) -> str:
        if v is None:
            return ""
        return v


class QualityCriterion(BaseModel):
    """A single evaluation criterion for what 'good' looks like."""

    criterion: str = Field(..., description="What to check (e.g. 'Includes quantified impact estimates')")
    description: str = Field(default="", description="Why this matters and how to satisfy it")

    @field_validator("description", mode="before")
    @classmethod
    def coerce_none_str(cls, v: object) -> str:
        if v is None:
            return ""
        return v


class MethodologyExtraction(BaseModel):
    """Procedural knowledge for a role — the 'how you work' layer.

    This is the thick methodology layer that makes skills actionable,
    as opposed to the thin persona layer (identity, traits).
    """

    heuristics: list[Heuristic] = Field(default_factory=list)
    output_templates: list[OutputTemplate] = Field(default_factory=list)
    trigger_mappings: list[TriggerTechniqueMapping] = Field(default_factory=list)
    quality_criteria: list[QualityCriterion] = Field(default_factory=list)

    @field_validator("heuristics", "output_templates", "trigger_mappings", "quality_criteria", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v: object) -> list:
        if v is None or v == "":
            return []
        return v

    def has_content(self) -> bool:
        """Return True if any methodology sections have been populated."""
        return bool(
            self.heuristics
            or self.trigger_mappings
            or self.output_templates
            or self.quality_criteria
        )
