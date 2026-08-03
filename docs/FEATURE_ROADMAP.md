# Feature Roadmap

Features that extend AgentForge from a one-shot forge into a closed-loop agent development platform.

## Shipped

| Surface | Description | Status |
|---------|-------------|--------|
| `agentforge forge` / `extract` / `batch` / `team` | Bootstrap factory from JDs | Shipped |
| `agentforge prompt-size` | Measure prompt size per section, detect bloat | Shipped |
| `agentforge lint` | Structural + semantic linting | Shipped |
| `agentforge audit [--fix]` | Safety guardrail audit with auto-fix | Shipped |
| `agentforge cost` | Token cost projection from actual prompt size | Shipped |
| `agentforge prompt-diff` | Section-by-section skill version comparison | Shipped |
| `agentforge test` | Scenario generation + LLM-as-judge skill testing | Shipped |
| `agentforge tend` | Persona drift / A/B / version log | Shipped (Phase 1) |
| `agentforge drill` | Skill-folder inventory, scan, watch, version | Shipped (Phase 1) |
| `agentforge department` | Multi-agent team synthesis from JD corpus | Shipped (Phase 1) |
| `agentforge market` | JD-corpus trends + gap analysis | Shipped (Phase 1) |
| `agentforge wiki` | Personal wiki memory (entities, candidates, promote) | Shipped (MVP) |
| Web UI + REST + MCP | Optional extras | Shipped |

## Next (prioritized)

1. **Honest quality gates** — expand full Ruff rule set beyond E/F; raise coverage floor; schema golden checks for forge outputs without live LLM.
2. **Day-2 propose surfaces** — `drill propose` / `market propose` (LLM only on proposal phase).
3. **Telemetry (opt-in local)** — stage timing and token cost counters; see `docs/telemetry-design.md`.
4. **Eval harness** — fixture-based regression for skill/identity schema stability against PersonaNexus.

## Design notes

Older detailed design sketches for skill testing, prompt architecture, and wiki memory remain in this `docs/` tree and in historical commits. Prefer the shipped CLI and `docs/day2-products.md` as the source of truth for current behavior.
