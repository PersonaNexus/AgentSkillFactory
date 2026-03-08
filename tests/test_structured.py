"""Tests for structured output helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from pydantic import BaseModel

from agentforge.llm.structured import extract_to_model


class SimpleModel(BaseModel):
    name: str
    value: int = 0


class TestExtractToModel:
    def test_delegates_to_client(self):
        mock_client = MagicMock()
        mock_client.extract_structured.return_value = SimpleModel(name="test", value=42)

        result = extract_to_model(mock_client, "extract data", SimpleModel)

        assert result.name == "test"
        assert result.value == 42
        mock_client.extract_structured.assert_called_once_with(
            prompt="extract data",
            output_schema=SimpleModel,
            system=None,
        )

    def test_passes_system_prompt(self):
        mock_client = MagicMock()
        mock_client.extract_structured.return_value = SimpleModel(name="sys")

        extract_to_model(mock_client, "extract", SimpleModel, system="Be precise")

        call_kwargs = mock_client.extract_structured.call_args.kwargs
        assert call_kwargs["system"] == "Be precise"

    def test_returns_correct_type(self):
        mock_client = MagicMock()
        expected = SimpleModel(name="typed", value=99)
        mock_client.extract_structured.return_value = expected

        result = extract_to_model(mock_client, "test", SimpleModel)
        assert isinstance(result, SimpleModel)
        assert result.value == 99
