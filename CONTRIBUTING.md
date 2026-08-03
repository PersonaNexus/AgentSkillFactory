# Contributing to AgentForge

Thanks for helping improve AgentForge. This repo is the **factory** in the PersonaNexus ecosystem ([product map](docs/repo-product-map.md)).

## Setup

```bash
git clone https://github.com/PersonaNexus/agentforge.git
cd agentforge
uv sync --dev
# optional web extras for API/UI tests:
uv sync --dev --extra web
```

Requires Python 3.12+.

## Development loop

```bash
# Full core suite (matches CI coverage floor)
uv run pytest -q --cov=agentforge --cov-fail-under=60

# Web-only tests
uv run pytest -q -m web

# Lint (critical rules across package)
uv run ruff check src/agentforge tests --select E,F --ignore E501

# Typecheck gated modules
uv run mypy --follow-imports=skip --ignore-missing-imports \
  src/agentforge/utils.py \
  src/agentforge/pipeline/forge_pipeline.py \
  src/agentforge/cli_quality.py \
  src/agentforge/analysis/skill_check.py \
  src/agentforge/telemetry/ \
  src/agentforge/web/auth.py
```

Do **not** commit API keys, tokens, or live JD content with PII. Prefer fixtures under `tests/fixtures/` and the sanitized [examples/senior-data-engineer](examples/senior-data-engineer/README.md) package.

## Offline fixture eval

CI runs generation + schema + quality gates on frozen extractions under `tests/fixtures/eval/` (no API keys):

```bash
uv run pytest -q tests/test_fixture_eval.py
```

## Golden example

After changing generation or quality tooling, keep the public example green:

```bash
uv run agentforge check examples/senior-data-engineer/output/skill-folder \
  --domain "data engineering" --strict
uv run agentforge identity validate examples/senior-data-engineer/output/identity.yaml
```

If you regenerate artifacts via `scripts/generate_example_artifacts.py`, re-run the gate and fix guardrails with `agentforge audit --fix` when needed.

## Pull requests

1. Branch from `main` (or stack on an open PR branch if coordinating a stack).
2. Keep PRs focused: one product surface or fix family per PR when practical.
3. Update `CHANGELOG.md` under `[Unreleased]` and README/docs when behavior or CLI surface changes.
4. Ensure CI is green (core + web jobs).

## Security

See [SECURITY.md](SECURITY.md). Non-loopback `serve` requires `AGENTFORGE_API_TOKEN`. Telemetry is off by default; local mode never sends JD/skill bodies.

## Design docs

| Topic | Doc |
|-------|-----|
| Day-2 products | [docs/day2-products.md](docs/day2-products.md) |
| Telemetry | [docs/telemetry-design.md](docs/telemetry-design.md) |
| Showcase examples | [docs/showcase.md](docs/showcase.md) |
| Feature roadmap | [docs/FEATURE_ROADMAP.md](docs/FEATURE_ROADMAP.md) |


## Publishing to PyPI

Releases use GitHub Releases (`vX.Y.Z`). Workflow: `.github/workflows/publish.yml`.

| Job | When | Required check? |
|-----|------|-----------------|
| **Build distributions** | Always on release / dispatch | Verifies wheel/sdist build |
| **Upload to PyPI** | Release (or dispatch with `dry_run=false`) | Needs one-time credential setup |

### One-time credential setup (pick one)

**A) Trusted publishing (recommended)**

1. GitHub → **Settings → Environments** → create environment named `pypi`.
2. On [pypi.org](https://pypi.org) create/claim project **`personanexus-agentforge`**
   (not bare `agentforge` — that name is an unrelated package).
3. **Publishing** → Add trusted publisher:
   - Owner: `PersonaNexus`
   - Repository: `agentforge`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
4. Publish a GitHub Release (or re-run the publish workflow).

**B) API token**

1. Create a PyPI API token with upload rights for **`personanexus-agentforge`**.
2. GitHub → **Settings → Secrets and variables → Actions** → `PYPI_TOKEN`.
3. Re-run the publish workflow.

### Dry-run build only

Actions → **Publish to PyPI** → Run workflow → leave `dry_run=true` (default).

### Install once published

```bash
pip install personanexus-agentforge
# CLI and import stay the same:
agentforge --help
python -c "import agentforge; print(agentforge.__version__)"
```

From GitHub tags (without PyPI):

```bash
pip install git+https://github.com/PersonaNexus/agentforge.git@v0.2.2
```

**Note:** A red **Publish to PyPI** run after a release means credentials/project setup
are incomplete, not that product CI failed. The **CI** workflow (core + web) is the
quality gate.
