"""Parse culture documents and convert to PersonaNexus mixins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from agentforge.models.culture import CultureProfile, CultureValue


class CultureParser:
    """Parse culture documents (markdown or YAML) into CultureProfile models."""

    def __init__(self, llm_client: Any | None = None):
        self.llm_client = llm_client

    def parse_yaml(self, path: str | Path) -> CultureProfile:
        """Parse a structured YAML culture file directly."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Culture file not found: {path}")

        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        if not data or not isinstance(data, dict):
            raise ValueError(f"Culture file is empty or not a valid YAML mapping: {path}")
        profile = CultureProfile.model_validate(data)
        profile.source_file = str(file_path.resolve())
        return profile

    def parse_markdown(self, path: str | Path) -> CultureProfile:
        """Parse a freeform markdown culture file via LLM extraction."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Culture file not found: {path}")

        text = file_path.read_text(encoding="utf-8")
        return self.parse_text(text, source=str(file_path.resolve()))

    def parse_text(self, text: str, source: str | None = None) -> CultureProfile:
        """Parse freeform culture text via LLM extraction."""
        if self.llm_client is None:
            from agentforge.llm.client import LLMClient
            self.llm_client = LLMClient()

        prompt = _CULTURE_EXTRACTION_PROMPT.format(culture_text=text)
        profile = self.llm_client.extract_structured(
            prompt=prompt,
            output_schema=CultureProfile,
            system=_CULTURE_SYSTEM_PROMPT,
        )
        profile.source_file = source
        return profile

    def parse_file(self, path: str | Path) -> CultureProfile:
        """Auto-detect file type and parse accordingly."""
        file_path = Path(path)
        suffix = file_path.suffix.lower()

        if suffix in (".yaml", ".yml"):
            return self.parse_yaml(file_path)
        else:
            return self.parse_markdown(file_path)


class CultureMixinConverter:
    """Convert a CultureProfile into a PersonaNexus mixin YAML file."""

    def convert(self, profile: CultureProfile) -> str:
        """Convert a CultureProfile to a PersonaNexus mixin YAML string."""
        mixin_dict = self._build_mixin_dict(profile)
        clean = json.loads(json.dumps(mixin_dict, default=str))
        return yaml.dump(clean, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def convert_and_save(self, profile: CultureProfile, output_path: str | Path) -> Path:
        """Convert and save the mixin YAML to a file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        yaml_str = self.convert(profile)
        path.write_text(yaml_str, encoding="utf-8")
        return path

    def _build_mixin_dict(self, profile: CultureProfile) -> dict[str, Any]:
        """Build a PersonaNexus mixin dictionary from a CultureProfile."""
        # Generate a slug for the mixin ID
        slug = profile.name.lower().replace(" ", "_").replace("-", "_")
        slug = "".join(c for c in slug if c.isalnum() or c == "_")[:30]

        mixin: dict[str, Any] = {
            "schema_version": "1.0",
            "mixin": {
                "id": f"culture_{slug}",
                "name": f"{profile.name} Culture",
                "description": profile.description or f"Cultural values from {profile.name}",
            },
        }

        # Aggregate trait deltas from all values
        aggregated_traits: dict[str, float] = {}
        for value in profile.values:
            for trait, delta in value.trait_deltas.items():
                current = aggregated_traits.get(trait, 0.5)
                # Apply delta, starting from neutral 0.5
                if trait not in aggregated_traits:
                    aggregated_traits[trait] = max(0.0, min(1.0, 0.5 + delta))
                else:
                    aggregated_traits[trait] = max(0.0, min(1.0, current + delta))

        if aggregated_traits:
            mixin["personality"] = {
                "traits": {k: round(v, 2) for k, v in sorted(aggregated_traits.items())},
            }

        # Communication tone from culture
        if profile.communication_tone:
            mixin["communication"] = {
                "tone": {
                    "default": profile.communication_tone,
                },
            }

        # Convert culture values to principles
        principles = []
        for i, value in enumerate(profile.values, start=10):
            principle: dict[str, Any] = {
                "id": f"culture_{slug}_{value.name.lower().replace(' ', '_')[:20]}",
                "priority": i,
                "statement": value.description or f"Embody {value.name}",
            }
            if value.behavioral_indicators:
                principle["implications"] = value.behavioral_indicators[:3]
            principles.append(principle)

        if principles:
            mixin["principles"] = principles

        return mixin


# --- Prompts for LLM-powered culture parsing ---

_CULTURE_SYSTEM_PROMPT = """You are an expert organizational culture analyst. Your job is to \
analyze culture documents and extract structured cultural values, communication styles, and \
behavioral indicators.

For trait_deltas, use PersonaNexus personality traits on a delta scale of -0.3 to +0.3:
- warmth: How warm/friendly the culture encourages being
- verbosity: How detailed/thorough communication should be
- assertiveness: How assertive/proactive people should be
- humor: How much humor is valued
- empathy: How much empathy is emphasized
- directness: How direct/transparent communication should be
- rigor: How rigorous/precise work should be
- creativity: How much innovation/creativity is valued
- epistemic_humility: How much intellectual humility is valued
- patience: How patient/measured the culture is"""

_CULTURE_EXTRACTION_PROMPT = """Analyze this enterprise culture document and extract structured data.

CULTURE DOCUMENT:
---
{culture_text}
---

Extract:

1. **name**: The organization or culture profile name
2. **description**: A brief (1-2 sentence) summary of the culture
3. **values**: Key cultural values. For each value:
   - name: The value name (e.g., "Innovation", "Collaboration")
   - description: What this value means in practice
   - behavioral_indicators: 2-3 observable behaviors that demonstrate this value
   - trait_deltas: How this value adjusts agent personality traits (use -0.3 to +0.3 scale)
4. **communication_tone**: The overall tone the culture encourages (e.g., "collaborative and direct")
5. **decision_style**: How decisions are typically made (e.g., "data-driven consensus")"""
