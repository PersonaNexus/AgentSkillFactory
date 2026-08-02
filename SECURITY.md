# Security Policy

## Supported versions

AgentForge is in early development (0.x). Security fixes land on `main` and are
included in the next release.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

- Prefer emailing the maintainers listed on the GitHub organization, or
- Open a private security advisory on GitHub if available for this repository.

Include: affected version/commit, reproduction steps, impact, and any suggested fix.

## Runtime defaults (web / Docker)

| Scenario | Auth behavior |
|----------|----------------|
| `agentforge serve` on `127.0.0.1` / `localhost` | Open API if no token (local convenience) |
| Bind to non-loopback (`0.0.0.0`, LAN IP) | **Requires** `AGENTFORGE_API_TOKEN` |
| Explicit opt-out | `AGENTFORGE_API_TOKEN=disabled` (not recommended on public interfaces) |

```bash
export AGENTFORGE_API_TOKEN=$(openssl rand -hex 32)
export ANTHROPIC_API_KEY=...
docker compose up
```

API clients must send:

```http
Authorization: Bearer <token>
```

## Secrets handling

- Never commit API keys, tokens, or `.env` files.
- Job descriptions may contain PII; prefer `--anonymize` / anonymize pipeline stage when sharing outputs.
- Telemetry is **off by default** (see `docs/telemetry-design.md`).

## Scope

This project is a local/dev-oriented factory CLI and optional web UI. Treat network
exposure as production only when you have set a strong `AGENTFORGE_API_TOKEN` and
reviewed your reverse proxy / TLS setup.
