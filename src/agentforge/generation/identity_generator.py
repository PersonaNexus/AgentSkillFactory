"""Generate PersonaNexus AgentIdentity YAML from extraction results."""

from __future__ import annotations

import json
from typing import Any

import yaml
from personanexus.types import AgentIdentity

from agentforge.mapping.role_mapper import RoleMapper
from agentforge.mapping.trait_mapper import TraitMapper
from agentforge.models.extracted_skills import ExtractionResult


class IdentityGenerator:
    """Assembles extraction results into a validated PersonaNexus AgentIdentity."""

    def __init__(
        self,
        trait_mapper: TraitMapper | None = None,
        role_mapper: RoleMapper | None = None,
    ):
        self.trait_mapper = trait_mapper or TraitMapper()
        self.role_mapper = role_mapper or RoleMapper()

    def generate(self, extraction: ExtractionResult) -> tuple[AgentIdentity, str]:
        """Generate a PersonaNexus AgentIdentity from extraction results.

        Returns:
            Tuple of (validated AgentIdentity model, YAML string)
        """
        identity_dict = self._build_identity_dict(extraction)

        # Validate against PersonaNexus
        identity = AgentIdentity.model_validate(identity_dict)

        # Serialize to clean YAML
        yaml_str = self._to_yaml(identity_dict)

        return identity, yaml_str

    def _build_identity_dict(self, extraction: ExtractionResult) -> dict[str, Any]:
        """Build the full identity dictionary."""
        # Map traits
        traits = self.trait_mapper.map_traits(extraction)

        # Ensure at least 2 traits are set for PersonaNexus custom mode validation
        trait_dict = {k: v for k, v in traits.items() if v is not None}

        identity: dict[str, Any] = {
            "schema_version": "1.0",
            "metadata": self.role_mapper.build_metadata(extraction),
            "role": self.role_mapper.build_role(extraction),
            "personality": {
                "traits": trait_dict,
            },
            "communication": self.role_mapper.build_communication(extraction),
            "expertise": self.role_mapper.build_expertise(extraction),
            "principles": self.role_mapper.build_principles(extraction),
            "guardrails": self.role_mapper.build_guardrails(extraction),
        }

        return identity

    def _to_yaml(self, data: dict[str, Any]) -> str:
        """Serialize identity dict to clean YAML.

        Uses json.loads(json.dumps()) to strip Python-specific types
        (datetime, enum) before YAML serialization.
        """
        clean = json.loads(json.dumps(data, default=str))
        return yaml.dump(clean, default_flow_style=False, sort_keys=False, allow_unicode=True)
