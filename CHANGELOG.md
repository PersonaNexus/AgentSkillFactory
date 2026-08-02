# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Remove triplicated quality CLI command definitions (`prompt-size`, `lint`, `cost`,
  `prompt-diff`, `audit`); commands now live in `agentforge.cli_quality`.
- Path containment checks use `Path.relative_to` instead of string `startswith`
  (avoids same-prefix sibling false negatives).
- Real undefined-name / unused-variable issues surfaced by expanded Ruff gates
  (`OutputTemplate` import, wizard `safe_rel_path`, dead locals).

### Security

- Non-loopback `serve` binds require `AGENTFORGE_API_TOKEN` (or explicit `disabled`).
- Docker Compose requires `AGENTFORGE_API_TOKEN` before start.

### Added

- `agentforge wiki …` CLI entry for wiki-memory (forwards to existing module CLI).
- `SECURITY.md`, this changelog, `py.typed` marker.
- CI web job (`uv sync --extra web` + `-m web` tests).
- Broader CI Ruff/mypy gates and coverage floor (55%).

### Changed

- Docs branding cleanup: AgentSkillFactory → AgentForge in user-facing guides.
- FEATURE_ROADMAP reflects shipped quality tools and skill testing.
