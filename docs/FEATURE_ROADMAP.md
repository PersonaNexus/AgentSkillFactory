# Feature Roadmap

Features that extend AgentForge from a one-shot forge into a closed-loop agent development platform.

## Shipped

| Surface | Description | Status |
|---------|-------------|--------|
| `agentforge forge` / `extract` / `batch` / `team` | Bootstrap factory from JDs | Shipped |
| `forge --check` / `--check-strict` | Optional post-forge quality gate | Shipped |
| `agentforge check` | One-shot lint + size + audit quality gate | Shipped |
| `agentforge identity validate` | PersonaNexus schema validation | Shipped |
| `agentforge prompt-size` | Measure prompt size per section, detect bloat | Shipped |
| `agentforge lint` | Structural + semantic linting | Shipped |
| `agentforge audit [--fix]` | Safety guardrail audit with auto-fix | Shipped |
| `agentforge cost` | Token cost projection from actual prompt size | Shipped |
| `agentforge prompt-diff` | Section-by-section skill version comparison | Shipped |
| `agentforge test` | Scenario generation + LLM-as-judge skill testing | Shipped |
| `agentforge tend` | Persona drift / A/B / version log | Shipped (Phase 1) |
| `agentforge drill` | Skill-folder inventory, scan, watch, version, propose, apply | Shipped |
| `agentforge department` | Multi-agent team synthesis from JD corpus | Shipped (Phase 1) |
| `agentforge market` | JD-corpus trends + gap + propose | Shipped |
| `agentforge wiki` | Personal wiki memory (entities, candidates, promote) | Shipped (MVP) |
| Local telemetry | Opt-in JSONL pipeline stage timings + llm_usage | Shipped |
| Fixture eval + digests | Offline generation gates (no live LLM) | Shipped |
| PyPI (`personanexus-agentforge`) | Trusted publisher OIDC | Shipped (0.2.2) |
| Web UI + REST + MCP | Optional extras | Shipped |

## Next (prioritized)

1. **Honest quality gates** — expand full Ruff rule set beyond E/F; keep raising coverage floor.
2. **Market → forge brief** — turn coverage gaps into a forge input packet.
3. **MCP check tools** — expose `check` / identity validate on the MCP server.
4. **Remote telemetry** — remains design-only; local mode is the supported path.
5. **Broader eval fixtures** — more frozen roles / domains beyond the current three.

## Design notes

Older detailed design sketches for skill testing, prompt architecture, and wiki memory remain in this `docs/` tree and in historical commits. Prefer the shipped CLI, README hero path, and `docs/day2-products.md` as the source of truth for current behavior.
