"""LLM-powered skill extraction from job descriptions."""

from __future__ import annotations

from agentforge.extraction.prompts import EXTRACTION_PROMPT, SYSTEM_PROMPT
from agentforge.llm.client import LLMClient
from agentforge.models.extracted_skills import ExtractionResult
from agentforge.models.job_description import JobDescription


class SkillExtractor:
    """Extracts structured skills, role info, and automation potential from JDs."""

    def __init__(self, client: LLMClient | None = None):
        self.client = client or LLMClient()

    def extract(self, jd: JobDescription) -> ExtractionResult:
        """Extract skills and role information from a job description."""
        prompt = EXTRACTION_PROMPT.format(jd_text=jd.full_text)

        return self.client.extract_structured(
            prompt=prompt,
            output_schema=ExtractionResult,
            system=SYSTEM_PROMPT,
        )
