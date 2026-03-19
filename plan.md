# Plan: Adopt Recommended Skill Folder Structure

## Goal
Refactor `SkillFolderGenerator` so generated skill folders follow the recommended structure:

```
skill-name/
├── SKILL.md                    ← thin orchestrator (reads/routes to other files)
├── instructions/
│   ├── voice.md                ← personality traits + communication style
│   ├── methodology.md          ← decision frameworks + trigger→technique router
│   └── scope.md                ← scope, boundaries, guardrails, audience
├── examples/
│   ├── good/                   ← annotated good examples (from user_examples)
│   │   └── *.md
│   └── bad/                    ← anti-patterns (derived from quality criteria)
│       └── anti-patterns.md
├── eval/
│   ├── checklist.md            ← pass/fail quality criteria checklist
│   └── advisory-board.md       ← AI reviewer personas for parallel evaluation
├── templates/
│   └── *.md                    ← output format templates from methodology
└── references/                 ← (existing) user-uploaded files
    └── *.md
```

## Current State
- `SkillFolderGenerator._render_body()` puts everything into a single monolithic SKILL.md
- `supplementary_files` dict already supports arbitrary `{relative_path: content}` — infrastructure is ready
- All consumers (CLI, web routes, MCP, batch, orchestration config, zip export) iterate `supplementary_files` and write files to the correct paths — **no consumer changes needed**

## Changes

### Step 1: Refactor `SkillFolderGenerator.generate()` to populate `supplementary_files`

In `src/agentforge/generation/skill_folder.py`:

1. **New method `_build_supplementary_files()`** — called from `generate()`, returns `dict[str, str]` with:
   - `instructions/voice.md` — extracted from `_render_identity()` content (traits, communication style)
   - `instructions/methodology.md` — extracted from `_render_decision_frameworks()`, `_render_trigger_router()` (or fallback triggers/workflows)
   - `instructions/scope.md` — extracted from `_render_scope()`, `_render_audience()`, `_render_competencies()`
   - `templates/*.md` — one file per output template from methodology (using template name as filename)
   - `eval/checklist.md` — rendered from `methodology.quality_criteria` as a pass/fail checklist
   - `eval/advisory-board.md` — generated reviewer personas relevant to the role's domain
   - `examples/good/*.md` — from `user_examples` if provided
   - `examples/bad/anti-patterns.md` — inverted quality criteria as "don't do this" patterns

2. Each `_render_*` helper continues to work as-is for the body content, but we add parallel `_build_*_file()` methods that return standalone file content (with their own headers and context).

### Step 2: Slim down SKILL.md to be an orchestrator

Modify `_render_body()` so SKILL.md becomes a routing document:
- Keep: header, purpose, identity summary (1-2 lines)
- Keep: `$ARGUMENTS` usage section
- Keep: footer
- **Replace** methodology/templates/quality/competencies/scope sections with file references:
  ```
  ## Instructions
  Read these files for detailed guidance:
  - `instructions/voice.md` — personality and communication style
  - `instructions/methodology.md` — decision frameworks and techniques
  - `instructions/scope.md` — boundaries, competencies, and audience

  ## Templates
  Use output templates from `templates/` when structuring responses.

  ## Evaluation
  Before delivering output, run through `eval/checklist.md`.
  For important deliverables, consult `eval/advisory-board.md` reviewers.

  ## Examples
  See `examples/good/` for reference output and `examples/bad/` for anti-patterns.
  ```

### Step 3: Update `skill_md_with_references()`

The existing method appends a "Reference Files" section. Update it to not duplicate the orchestrator references that are now baked into the slim SKILL.md. Only append entries for files in `references/` (user uploads).

### Step 4: Update `SkillRefiner` file paths

In `src/agentforge/analysis/skill_refiner.py`:
- `_merge_templates()`: write to `templates/` instead of `references/`
- `_merge_examples()`: write to `examples/good/` instead of `references/`
- `_merge_frameworks()`: write to `instructions/` or `references/` (keep as reference)

### Step 5: Update tests

- Update `tests/test_skill_generation.py` assertions for the new slim SKILL.md content
- Add tests verifying supplementary files are populated with the correct paths
- Update any snapshot/string-matching tests

### Step 6: Update team forge path

In `src/agentforge/composition/team_forger.py` — no changes needed since it calls `SkillFolderGenerator.generate()` which will now return the new structure automatically.

## What stays the same
- `SkillFolderResult` model — no schema changes (still `skill_md` + `supplementary_files` dict)
- All CLI/web/MCP consumers — they already iterate `supplementary_files` and write to disk
- `SkillFileGenerator` (the older reference format) — untouched
- LangGraph export — untouched
