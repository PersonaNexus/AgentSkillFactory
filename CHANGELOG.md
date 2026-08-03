# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Web forge quality check** — same `SkillChecker` gate as CLI `forge --check`
  (default on). Form fields `run_check`, `check_strict`, `check_domain`; result
  includes `quality_check` on SSE done / refine. UI panel shows pass/fail.

### Fixed

- **`agentforge init`** — use `config.DEFAULT_MODELS` (broken import of nonexistent
  `_DEFAULT_MODELS` from llm client).
- **Skill write parity** — batch, team CLI/wizard, web forge/batch, and composition
  exports write/store `skill_md_with_references()` so reference links are not dropped.
- **Path safety** — identity import and team teammate ref writes use `safe_rel_path`.

### Changed

- Model option defaults and MCP schemas use `config.DEFAULT_MODEL` / `DEFAULT_MODELS`
  instead of hardcoded Sonnet strings.
- `SkillRefiner` uses shared `safe_filename` / `make_skill_slug` helpers.

## [0.2.2] — 2026-08-03

### Added

- **`forge --check` / `--check-strict` / `--check-domain`** — optional post-forge quality gate (exit 1 on fail).
- Post-forge **Next steps** panel always printed.
- **Fixture structural digests** — anti-drift locks under `tests/fixtures/eval/*.digest.json`;
  regen via `scripts/regenerate_eval_digests.py`.
- `docs/GOAL-0.3.md` — hero-path milestone (shipped).

### Changed

- **PyPI distribution name** is now **`personanexus-agentforge`** (the bare name
  `agentforge` is already used by an unrelated project on PyPI).
- **CLI and import are unchanged:** `agentforge` / `import agentforge`.
- Install docs and publish instructions updated for the new name.
- Publish workflow uses `pypa/gh-action-pypi-publish` (OIDC trusted publishing).

```bash
pip install personanexus-agentforge
pip install "personanexus-agentforge[web]"
```

Published: https://pypi.org/project/personanexus-agentforge/

## [0.2.1] — 2026-08-03

### Added

- **`drill apply`** — human-gated application of mechanical proposals
  (`prune_tools`, `add_skill_md`, `fix_references`) via `--yes` or interactive confirm.
- **Broader fixture eval rubrics** — min skills, title presence, frontmatter name,
  guardrails, methodology enrichment.
- **PyPI publish workflow** (`.github/workflows/publish.yml`) via trusted publishing
  on GitHub Release (requires one-time PyPI OIDC setup for this repo).

### Changed

- README emphasizes hero path; full CLI listed as advanced.
- Package version 0.2.1.

## [0.2.0] — 2026-08-03

Public Alpha hardening release: quality gates, local telemetry, day-2 propose,
docs, and offline fixture eval.

### Added

- `agentforge check` — one-shot lint + prompt-size + guardrail audit (`--strict`).
- `agentforge identity validate` — PersonaNexus schema validation without import.
- `agentforge.analysis.skill_check` library for programmatic gates.
- Golden tests for the public senior-data-engineer example (no live LLM).
- MCP server unit tests (schemas, path allowlist, mocked extract/forge).
- **Local telemetry** (`AGENTFORGE_TELEMETRY_MODE=local`): pipeline stage timings +
  `llm_usage` token counts to JSONL (default off; no bodies; no remote).
- **`drill propose`** / **`market propose`** — deterministic maintenance plans
  (review-only; never auto-edit skill sources).
- Offline **fixture eval** (`agentforge.eval`) for three frozen roles — CI-safe
  generation + schema + quality gates without API keys.
- `CONTRIBUTING.md`, `SECURITY.md`, expanded docs.

### Changed

- CLI quality commands live in `cli_quality` (removed triplicated definitions).
- Non-loopback `serve` requires `AGENTFORGE_API_TOKEN`.
- Path safety uses `Path.relative_to` (not string prefix).
- CI: core + web jobs; coverage floor **60%**; Ruff `E,F,I`; broader mypy allowlist.
- Public example skills pass `check --strict` for data engineering.
- README hero path + quality/telemetry/wiki/CI sections aligned with code.
- Version **0.1.0 → 0.2.0**.

### Security

- Docker Compose requires `AGENTFORGE_API_TOKEN`.
- Telemetry remains opt-in local-only by default.

## [0.1.0]

Initial public Alpha under the AgentForge name (PersonaNexus factory + early day-2 tools).
