# AgentForge Telemetry & Observability Design (Opt-In)

Status: **local mode implemented**. Remote export remains design-only.

## Goals

- Provide operational visibility into local AgentForge usage.
- Help users understand pipeline reliability, latency, and token cost.
- Preserve privacy by default and avoid silent data export.

## No-Default-Exfiltration Guarantee

- Default mode is `off`.
- AgentForge sends no telemetry to any remote endpoint unless the user explicitly opts in.
- Local logs/metrics can be enabled without any network transmission.

## Implemented: local mode

```bash
export AGENTFORGE_TELEMETRY_MODE=local
# optional:
export AGENTFORGE_TELEMETRY_DIR=~/.agentforge/telemetry

agentforge forge job.txt
# appends JSONL events to $AGENTFORGE_TELEMETRY_DIR/events-YYYY-MM-DD.jsonl
```

Events currently emitted by `ForgePipeline.run`:

| event | meaning |
|-------|---------|
| `pipeline_start` | pipeline began (stage list only; no JD text) |
| `stage` | per-stage status (`ok` / `error` / `skipped`) + `duration_ms` |
| `pipeline_end` | overall status + total duration |
| `llm_usage` | prompt/completion token counts from `LLMClient` (no bodies) |

Schema version: `1` (`schema_version` field on every event).

### Explicitly excluded

- Raw JD text
- Generated identity/skill content
- Prompt bodies
- User-supplied supplemental documents
- File paths by default

## Configuration

| Variable | Values | Default |
|----------|--------|---------|
| `AGENTFORGE_TELEMETRY_MODE` | `off`, `local` (`on`/`file` alias → local) | `off` |
| `AGENTFORGE_TELEMETRY_DIR` | directory path | `~/.agentforge/telemetry` |

`remote` / `AGENTFORGE_TELEMETRY_ENDPOINT` are **not** implemented. Setting mode to
`remote` behaves as `off` until a future release.

## Library API

```python
from agentforge.telemetry import get_sink, TelemetryEvent

sink = get_sink()
sink.record("custom", command="my_cmd", status="ok", duration_ms=3.2)
```

## Remaining rollout

1. ~~Implement `local` mode only with unit tests and docs.~~
2. ~~Add token counters from LLM client responses.~~
3. Optional CLI flag `--telemetry local|off` overriding env.
4. Add `remote` mode behind explicit endpoint configuration (opt-in only).
