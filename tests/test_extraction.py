"""Tests for skill extraction (with mocked LLM responses)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentforge.extraction.skill_extractor import SkillExtractor
from agentforge.llm.client import LLMClient, _inline_refs
from agentforge.models.extracted_skills import (
    ExtractionResult,
    ExtractedRole,
    ExtractedSkill,
    SkillCategory,
    SkillProficiency,
    SuggestedTraits,
)
from agentforge.models.job_description import JobDescription, JDSource


def _mock_extraction_result() -> ExtractionResult:
    """Create a mock extraction result for testing."""
    return ExtractionResult(
        role=ExtractedRole(
            title="Senior Data Engineer",
            purpose="Design and maintain data infrastructure",
            scope_primary=["ETL pipelines", "Data warehouse"],
            scope_secondary=["ML operationalization"],
            audience=["Data scientists", "Analysts"],
            seniority="senior",
            domain="Data Engineering",
        ),
        skills=[
            ExtractedSkill(
                name="Python",
                category=SkillCategory.HARD,
                proficiency=SkillProficiency.ADVANCED,
                importance="required",
                context="Primary language for pipelines",
            ),
            ExtractedSkill(
                name="SQL",
                category=SkillCategory.HARD,
                proficiency=SkillProficiency.ADVANCED,
                importance="required",
                context="Data warehouse queries",
            ),
            ExtractedSkill(
                name="Apache Spark",
                category=SkillCategory.TOOL,
                proficiency=SkillProficiency.ADVANCED,
                importance="required",
                context="Distributed data processing",
            ),
        ],
        responsibilities=[
            "Design ETL pipelines",
            "Build data warehouse",
        ],
        qualifications=[
            "5+ years experience",
            "BS in Computer Science",
        ],
        suggested_traits=SuggestedTraits(rigor=0.85, directness=0.7),
        automation_potential=0.35,
        automation_rationale="Requires architectural judgment",
    )


class TestSkillExtractor:
    def test_extract_returns_result(self, sample_jd):
        """Test that extraction returns a valid ExtractionResult."""
        mock_client = MagicMock(spec=LLMClient)
        mock_result = _mock_extraction_result()
        mock_client.extract_structured.return_value = mock_result

        extractor = SkillExtractor(client=mock_client)
        result = extractor.extract(sample_jd)

        assert isinstance(result, ExtractionResult)
        assert result.role.title == "Senior Data Engineer"
        assert len(result.skills) == 3
        assert result.automation_potential == 0.35

    def test_extract_calls_llm_with_jd_text(self, sample_jd):
        """Test that the extractor passes JD text to the LLM."""
        mock_client = MagicMock(spec=LLMClient)
        mock_client.extract_structured.return_value = _mock_extraction_result()

        extractor = SkillExtractor(client=mock_client)
        extractor.extract(sample_jd)

        call_args = mock_client.extract_structured.call_args
        assert sample_jd.full_text[:50] in call_args.kwargs["prompt"]
        assert call_args.kwargs["output_schema"] is ExtractionResult

    def test_extract_default_client_requires_api_key(self):
        """Test that SkillExtractor raises if no API key is set."""
        import os
        from unittest.mock import patch
        from agentforge.config import AgentForgeConfig

        # Remove API keys from env and mock config to test validation
        old_ant = os.environ.pop("ANTHROPIC_API_KEY", None)
        old_oai = os.environ.pop("OPENAI_API_KEY", None)
        try:
            empty_config = AgentForgeConfig(api_key="")
            with patch("agentforge.config.load_config", return_value=empty_config):
                with pytest.raises(ValueError, match="No API key found"):
                    SkillExtractor()
        finally:
            if old_ant is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_ant
            if old_oai is not None:
                os.environ["OPENAI_API_KEY"] = old_oai


class TestLLMClient:
    def test_inline_refs(self):
        """Test that $ref resolution works correctly."""
        from agentforge.llm.client import _inline_refs

        schema = {
            "type": "object",
            "properties": {
                "role": {"$ref": "#/$defs/Role"},
            },
            "$defs": {
                "Role": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                    },
                },
            },
        }
        _inline_refs(schema)
        assert "$defs" not in schema
        assert schema["properties"]["role"]["type"] == "object"
        assert "title" in schema["properties"]["role"]["properties"]

    def test_inline_refs_no_defs(self):
        """Test that _inline_refs is a no-op when no $defs present."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        original = schema.copy()
        _inline_refs(schema)
        assert schema == original

    def test_inline_refs_nested(self):
        """Test that nested $ref resolution works."""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/Item"},
                },
            },
            "$defs": {
                "Item": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                },
            },
        }
        _inline_refs(schema)
        assert schema["properties"]["items"]["items"]["type"] == "object"
