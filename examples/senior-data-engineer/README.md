# Senior Data Engineer Example

Sanitized example input/output package generated from AgentForge fixture data.
Used as the **public golden path** for CI (schema + layout + quality gates).

## Layout

```text
input/job_description.txt          # source JD
output/
  identity.yaml                    # PersonaNexus identity
  skill-folder/                    # Claude Code skill (drop into .claude/skills/)
    SKILL.md
    instructions/ …
  personanexus-deployment/         # deploy package
    agent_identity.yaml
    compiled_prompt.md
    deployment.yaml
    README.md
    senior-data-engineer-skills/
```

## Reproduce

```bash
uv sync --dev
uv run python scripts/generate_example_artifacts.py
```

This flow is deterministic and does not call external LLM providers.

## Quality gate on the example

```bash
# Default gate: lint + size (must pass)
uv run agentforge check examples/senior-data-engineer/output/skill-folder

# Strict: also requires full guardrail audit (public example is maintained to pass)
uv run agentforge check examples/senior-data-engineer/output/skill-folder \
  --domain "data engineering" --strict

uv run agentforge identity validate examples/senior-data-engineer/output/identity.yaml
```

If you regenerate artifacts and `check --strict` fails, run:

```bash
uv run agentforge audit examples/senior-data-engineer/output/skill-folder/SKILL.md \
  --domain "data engineering" --fix \
  --output examples/senior-data-engineer/output/skill-folder/SKILL.md
```

…and mirror the same fix into the PersonaNexus deployment skill copy if present.
