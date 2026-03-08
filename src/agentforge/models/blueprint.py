"""Agent blueprint — the final output of the forge pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentforge.generation.skill_folder import SkillFolderResult
from agentforge.models.culture import CultureProfile
from agentforge.models.extracted_skills import ExtractionResult
from agentforge.models.job_description import JobDescription


class AgentBlueprint(BaseModel):
    """Complete agent blueprint wrapping a PersonaNexus identity."""

    source_jd: JobDescription
    extraction: ExtractionResult
    culture: CultureProfile | None = None
    identity_yaml: str = Field(
        ..., description="Serialized PersonaNexus AgentIdentity YAML"
    )
    skill_file: str | None = Field(
        None, description="Generated SKILL.md content"
    )
    skill_folder: SkillFolderResult | None = Field(
        None, description="Generated Claude-compatible skill folder content"
    )
    coverage_score: float = Field(
        0.0, ge=0.0, le=1.0,
        description="How much of the JD this agent covers",
    )
    coverage_gaps: list[str] = Field(
        default_factory=list,
        description="Skills/responsibilities not covered by the agent",
    )
    automation_estimate: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Estimated percentage of role automatable",
    )
