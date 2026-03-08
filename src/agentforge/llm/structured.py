"""Structured output helpers for LLM extraction."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from agentforge.llm.client import LLMClient

T = TypeVar("T", bound=BaseModel)


def extract_to_model(
    client: LLMClient,
    prompt: str,
    model_class: type[T],
    system: str | None = None,
) -> T:
    """Convenience wrapper for structured extraction."""
    return client.extract_structured(
        prompt=prompt,
        output_schema=model_class,
        system=system,
    )
