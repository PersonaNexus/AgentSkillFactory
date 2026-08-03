# Goal: AgentForge 0.3 hero-path quality

**Status:** shipped on main (#49 + #50 CI fix)  
**Branch:** `feat/0.3-hero-path-forge-check`  
**Success criteria:** A stranger can forge → auto-check → drop skill without reading day-2 docs.

## Loop

1. Stabilize main (CI green) — done baseline  
2. `forge --check` (+ domain, strict options)  
3. Fixture structural digests (anti-drift)  
4. Post-forge next-steps always printed  
5. Tests + full CI gates  
6. PR + merge  

## Explicitly out of scope this loop

- New top-level CLI products  
- Remote telemetry / PyPI OIDC (user config)  
- LLM-based apply  
