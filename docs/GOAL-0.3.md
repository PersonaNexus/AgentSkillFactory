# Goal: AgentForge 0.3 hero-path quality

**Status:** shipped (main through #49–#53; package **0.2.2** on PyPI)  
**Success criteria:** A stranger can forge → auto-check → drop skill without reading day-2 docs.

## Loop (done)

1. Stabilize main (CI green) — done  
2. `forge --check` (+ domain, strict options) — done  
3. Fixture structural digests (anti-drift) — done  
4. Post-forge next-steps always printed — done  
5. Tests + full CI gates — done  
6. PR + merge — done  
7. PyPI publish as `personanexus-agentforge` via OIDC — done  

## Explicitly out of scope for this goal

- New top-level CLI products  
- Remote telemetry  

## Install (current)

```bash
pip install personanexus-agentforge
agentforge forge job.txt -d ./out --skill-folder --check --check-strict
```
