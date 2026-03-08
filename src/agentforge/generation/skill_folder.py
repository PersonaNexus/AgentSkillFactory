"""Generate Claude-compatible skill folders from extraction results.

Produces a skill folder containing:
- instructions.md: Structured skill instructions with trigger patterns,
  personality modifiers, workflows, and MCP tool integration stubs.
- manifest.json: Skill metadata, triggers, dependencies, and provenance.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from agentforge.models.extracted_skills import (
    ExtractionResult,
    SkillCategory,
)
from agentforge.models.job_description import JobDescription
from agentforge.generation.skill_file import (
    _TRAIT_DESCRIPTORS,
    _trait_description,
    _trait_prompt,
)
from agentforge.utils import safe_filename


class SkillFolderResult(BaseModel):
    """Container for Claude-compatible skill folder content."""

    agent_id: str = Field(..., description="Sanitized agent ID for folder naming")
    instructions_md: str = Field(..., description="instructions.md content")
    manifest_json: str = Field(..., description="manifest.json content")


class SkillFolderGenerator:
    """Generates Claude-compatible skill folders from extraction results.

    Follows the Anthropic skill folder pattern: instructions.md for Claude
    consumption plus manifest.json for metadata and tooling.
    """

    def generate(
        self,
        extraction: ExtractionResult,
        identity: Any,
        jd: JobDescription | None = None,
    ) -> SkillFolderResult:
        """Generate a skill folder from extraction results.

        Args:
            extraction: LLM-extracted role, skills, and trait data.
            identity: Validated PersonaNexus AgentIdentity instance.
            jd: Optional parsed job description for additional context.

        Returns:
            SkillFolderResult with instructions.md and manifest.json content.
        """
        agent_id = identity.metadata.id

        return SkillFolderResult(
            agent_id=safe_filename(agent_id),
            instructions_md=self._render_instructions(extraction, identity, jd),
            manifest_json=self._render_manifest(extraction, identity, jd),
        )

    # ------------------------------------------------------------------
    # instructions.md rendering
    # ------------------------------------------------------------------

    def _render_instructions(
        self,
        extraction: ExtractionResult,
        identity: Any,
        jd: JobDescription | None,
    ) -> str:
        """Build the full instructions.md content."""
        lines: list[str] = []

        self._render_inst_header(lines, extraction)
        self._render_inst_triggers(lines, extraction)
        self._render_inst_personality(lines, extraction)
        self._render_inst_competencies(lines, extraction)
        self._render_inst_workflows(lines, extraction)
        self._render_inst_mcp(lines, extraction)
        self._render_inst_scope(lines, extraction)
        self._render_inst_audience(lines, extraction)
        self._render_inst_footer(lines, extraction, jd)

        return "\n".join(lines)

    def _render_inst_header(
        self, lines: list[str], extraction: ExtractionResult
    ) -> None:
        """Render title and purpose."""
        lines.append(f"# {extraction.role.title} Agent Skill")
        lines.append("")
        lines.append(f"> {extraction.role.purpose}")
        lines.append("")

    def _render_inst_triggers(
        self, lines: list[str], extraction: ExtractionResult
    ) -> None:
        """Render trigger patterns from scope and responsibilities."""
        triggers: list[str] = list(extraction.role.scope_primary)

        # Add first few responsibilities as secondary triggers
        for resp in extraction.responsibilities[:3]:
            # Use the first phrase of each responsibility
            trigger = resp.split(",")[0].strip()
            if trigger and trigger not in triggers:
                triggers.append(trigger)

        if not triggers:
            return

        lines.append("## Trigger Patterns")
        lines.append("")
        lines.append("Activate this skill when the user's request involves:")
        lines.append("")
        for trigger in triggers:
            lines.append(f"- {trigger}")
        lines.append("")

    def _render_inst_personality(
        self, lines: list[str], extraction: ExtractionResult
    ) -> None:
        """Render identity statement and personality modifiers."""
        lines.append("## Identity & Personality")
        lines.append("")
        lines.append(
            f"You are a {extraction.role.seniority.value}-level "
            f"{extraction.role.title} specializing in {extraction.role.domain}."
        )
        lines.append("")

        defined = extraction.suggested_traits.defined_traits()
        if defined:
            lines.append("### Personality Modifiers")
            lines.append("")

            sorted_traits = sorted(defined.items(), key=lambda x: x[1], reverse=True)

            for trait_name, value in sorted_traits:
                display_name = trait_name.replace("_", " ").title()
                desc = _trait_description(trait_name, value)
                prompt = _trait_prompt(trait_name)
                line = f"- **{display_name}** ({value:.0%}): {desc}"
                if prompt:
                    line += f". {prompt}."
                lines.append(line)
            lines.append("")

            # Communication style summary
            lines.append("### Communication Style")
            lines.append("")
            style_notes = self._derive_communication_style(defined)
            for note in style_notes:
                lines.append(f"- {note}")
            lines.append("")

    def _derive_communication_style(self, traits: dict[str, float]) -> list[str]:
        """Derive communication style notes from trait combination."""
        notes: list[str] = []

        rigor = traits.get("rigor", 0.5)
        directness = traits.get("directness", 0.5)
        warmth = traits.get("warmth", 0.5)
        verbosity = traits.get("verbosity", 0.5)
        patience = traits.get("patience", 0.5)

        if rigor >= 0.65 and directness >= 0.65:
            notes.append("Be precise and straightforward in all communications")
        elif rigor >= 0.65:
            notes.append("Prioritize accuracy and detail in responses")
        elif directness >= 0.65:
            notes.append("Be clear and direct, avoiding unnecessary hedging")

        if warmth >= 0.65:
            notes.append("Maintain a warm, approachable tone")
        elif warmth < 0.35:
            notes.append("Keep communications professional and objective")

        if verbosity >= 0.65:
            notes.append("Provide thorough explanations with supporting detail")
        elif verbosity < 0.35:
            notes.append("Keep responses concise and focused on key points")

        if patience >= 0.65:
            notes.append("Take time to explain concepts step by step when needed")

        if not notes:
            notes.append("Use a balanced, professional communication style")

        return notes

    def _render_inst_competencies(
        self, lines: list[str], extraction: ExtractionResult
    ) -> None:
        """Render core competencies: domain, technical, tools."""
        lines.append("## Core Competencies")
        lines.append("")

        # Domain expertise
        domain_skills = [
            s for s in extraction.skills if s.category == SkillCategory.DOMAIN
        ]
        if domain_skills:
            lines.append("### Domain Expertise")
            lines.append("")
            for skill in domain_skills:
                lines.append(f"- **{skill.name}**: {skill.context or skill.name}")
                if skill.genai_application:
                    lines.append(f"  - GenAI integration: {skill.genai_application}")
            lines.append("")

        # Technical skills
        hard_skills = [
            s for s in extraction.skills if s.category == SkillCategory.HARD
        ]
        if hard_skills:
            lines.append("### Technical Skills")
            lines.append("")
            for skill in hard_skills:
                prof = skill.proficiency.value
                lines.append(f"- **{skill.name}** ({prof})")
                if skill.context:
                    lines.append(f"  - {skill.context}")
                if skill.examples:
                    lines.append(f"  - Tools: {', '.join(skill.examples)}")
                if skill.genai_application:
                    lines.append(f"  - GenAI integration: {skill.genai_application}")
            lines.append("")

        # Tools & platforms
        tool_skills = [
            s for s in extraction.skills if s.category == SkillCategory.TOOL
        ]
        if tool_skills:
            lines.append("### Tools & Platforms")
            lines.append("")
            for skill in tool_skills:
                prof = skill.proficiency.value
                lines.append(f"- **{skill.name}** ({prof})")
                if skill.context:
                    lines.append(f"  - {skill.context}")
                if skill.examples:
                    lines.append(f"  - Components: {', '.join(skill.examples)}")
                if skill.genai_application:
                    lines.append(f"  - GenAI integration: {skill.genai_application}")
            lines.append("")

    def _render_inst_workflows(
        self, lines: list[str], extraction: ExtractionResult
    ) -> None:
        """Render workflows derived from responsibilities."""
        if not extraction.responsibilities:
            return

        # Collect tool/hard skill names for workflow steps
        tool_names = [
            s.name
            for s in extraction.skills
            if s.category in (SkillCategory.TOOL, SkillCategory.HARD)
        ]

        lines.append("## Workflows")
        lines.append("")

        for i, resp in enumerate(extraction.responsibilities, 1):
            lines.append(f"### Workflow {i}: {resp}")
            lines.append("")
            lines.append(f"When asked to {resp.lower()}, follow these steps:")
            lines.append("")
            lines.append("1. Clarify requirements and gather context from the user")
            lines.append("2. Assess the current state and identify key considerations")
            lines.append(f"3. {resp}")
            if tool_names:
                tools_str = ", ".join(tool_names[:3])
                lines.append(
                    f"4. Leverage relevant tools ({tools_str}) as appropriate"
                )
                lines.append("5. Review output and validate against requirements")
                lines.append("6. Document findings and provide clear summary")
            else:
                lines.append("4. Review output and validate against requirements")
                lines.append("5. Document findings and provide clear summary")
            lines.append("")

    def _render_inst_mcp(
        self, lines: list[str], extraction: ExtractionResult
    ) -> None:
        """Render MCP tool integration stubs."""
        mcp_candidates = [
            s
            for s in extraction.skills
            if s.category == SkillCategory.TOOL
            or (s.category == SkillCategory.HARD and s.genai_application)
            or (s.category == SkillCategory.DOMAIN and s.genai_application)
        ]

        if not mcp_candidates:
            return

        lines.append("## MCP Tool Integration")
        lines.append("")
        lines.append("This agent may use the following tool patterns:")
        lines.append("")
        for skill in mcp_candidates:
            detail = skill.genai_application or skill.context or skill.name
            lines.append(f"- **{skill.name}**: {detail}")
        lines.append("")

    def _render_inst_scope(
        self, lines: list[str], extraction: ExtractionResult
    ) -> None:
        """Render scope and boundaries."""
        lines.append("## Scope & Boundaries")
        lines.append("")

        if extraction.role.scope_primary:
            lines.append("### In Scope")
            lines.append("")
            for item in extraction.role.scope_primary:
                lines.append(f"- {item}")
            lines.append("")

        if extraction.role.scope_secondary:
            lines.append("### Secondary (Defer When Possible)")
            lines.append("")
            for item in extraction.role.scope_secondary:
                lines.append(f"- {item}")
            lines.append("")

        # Guardrails
        lines.append("### Guardrails")
        lines.append("")
        lines.append(f"- Stay within {extraction.role.domain} domain expertise")
        lines.append(
            "- Acknowledge limitations in areas outside core competencies"
        )

        soft_skills = [
            s for s in extraction.skills if s.category == SkillCategory.SOFT
        ]
        if soft_skills:
            soft_names = ", ".join(s.name.lower() for s in soft_skills)
            lines.append(
                f"- Defer to human judgment for areas requiring {soft_names}"
            )
        lines.append("")

    def _render_inst_audience(
        self, lines: list[str], extraction: ExtractionResult
    ) -> None:
        """Render audience section."""
        if not extraction.role.audience:
            return

        lines.append("## Audience")
        lines.append("")
        lines.append("This agent is designed to interact with:")
        lines.append("")
        for audience in extraction.role.audience:
            lines.append(f"- {audience}")
        lines.append("")

    def _render_inst_footer(
        self,
        lines: list[str],
        extraction: ExtractionResult,
        jd: JobDescription | None,
    ) -> None:
        """Render metadata footer."""
        source_info = "Unknown"
        if jd:
            source_info = jd.title
            if jd.company:
                source_info += f" at {jd.company}"

        lines.append("---")
        lines.append(
            f"*Generated by AgentForge | "
            f"Source: {source_info} | "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}*"
        )
        lines.append("")

    # ------------------------------------------------------------------
    # manifest.json rendering
    # ------------------------------------------------------------------

    def _render_manifest(
        self,
        extraction: ExtractionResult,
        identity: Any,
        jd: JobDescription | None,
    ) -> str:
        """Build the manifest.json content."""
        from agentforge import __version__

        # Skill name as slug
        name = safe_filename(extraction.role.title).lower().replace("_", "-")

        # Skills grouped by category (just names)
        skills_summary: dict[str, list[str]] = {}
        for skill in extraction.skills:
            cat_key = skill.category.value
            skills_summary.setdefault(cat_key, []).append(skill.name)

        # Tool dependencies
        tools = [
            s.name for s in extraction.skills if s.category == SkillCategory.TOOL
        ]

        # Personality traits
        defined_traits = extraction.suggested_traits.defined_traits()
        personality = {k: round(v, 2) for k, v in defined_traits.items()}

        # Source info
        source_title = "Unknown"
        if jd:
            source_title = jd.title
            if jd.company:
                source_title += f" at {jd.company}"

        manifest: dict[str, Any] = {
            "name": name,
            "version": "1.0.0",
            "description": extraction.role.purpose,
            "agent_id": identity.metadata.id,
            "domain": extraction.role.domain,
            "seniority": extraction.role.seniority.value,
            "triggers": list(extraction.role.scope_primary),
            "dependencies": {
                "tools": tools,
                "mcp_servers": [],
            },
            "personality": personality,
            "automation_potential": extraction.automation_potential,
            "skills_summary": skills_summary,
            "audience": list(extraction.role.audience),
            "source": {
                "title": source_title,
                "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "generator": f"AgentForge v{__version__}",
            },
        }

        return json.dumps(manifest, indent=2)
