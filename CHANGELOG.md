# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `agentforge check` — one-shot lint + prompt-size + guardrail audit gate
  (`--strict` also fails on incomplete audit coverage).
- `agentforge identity validate` — PersonaNexus schema validation without import.
- Golden tests for the public senior-data-engineer example package (no live LLM).
- MCP server unit tests (schemas, path allowlist, extract/forge with mocks).
- `agentforge.analysis.skill_check` library for programmatic quality gates.

### Changed

- CI coverage floor raised from 55% to 60%.

### Previously

#### Fixed (0.1.0 quality pass)

- Remove triplicated quality CLI command definitions; path `startswith` safety fix;
  Ruff/mypy gate expansion; `agentforge wiki`; secure non-loopback serve defaults.
