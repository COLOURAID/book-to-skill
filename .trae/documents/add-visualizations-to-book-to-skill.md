# Plan: Add Visualizations (Flow Charts, Infographics) to book-to-skill

## Summary

Extend the `book-to-skill` skill template so that every generated book-skill includes **Mermaid diagrams** (primary, always-on) and **optionally rendered PNG images** (when `mermaid-cli` is installed). Today the output is purely linear text (`SKILL.md` + `chapters/` + `glossary.md` + `patterns.md` + `cheatsheet.md`). After this change, a new `diagrams.md` file plus inline Mermaid blocks in `SKILL.md` and each chapter will give users a visual map of the book's structure, framework relationships, and decision flows — enabling "seamless, uninterrupted knowledge" navigation.

**Approach is intentionally minimal:** only two files are edited (`SKILL.md`, `README.md`), no new Python scripts, no new runtime dependencies, no new tests. Generation stays agent-driven per `SKILL.md` instructions, consistent with how chapters/glossary are already produced.

---

## Current State Analysis

### What the repo is
- A **Claude Code skill template** (`SKILL.md`) that instructs an agent through Steps 0–10 to convert a book into a structured markdown skill.
- `scripts/extract.py` + `scripts/extractor/` only handle **text extraction** (PDF/EPUB/DOCX/...). They do NOT generate chapters — the agent does, following `SKILL.md`.
- Output today: `SKILL.md`, `chapters/chNN-*.md`, `glossary.md`, `patterns.md`, `cheatsheet.md` — all plain linear text.
- `tools/validate_skill.py` audits `SKILL.md` frontmatter (name/description/allowed-tools). Body length >500 lines is a WARN, not an ERROR — CI stays green when we add content.
- CI (`.github/workflows/ci.yml`) runs pytest, ruff (E9,F only), a smoke extraction test, and `validate_skill.py`.

### Key files read during exploration
- [SKILL.md](file:///workspace/SKILL.md) — the agent workflow (Steps 0–10 + Update/Fold-in). ~566 lines.
- [README.md](file:///workspace/README.md) — "What it generates" table + "Repository structure" section.
- [scripts/extract.py](file:///workspace/scripts/extract.py) and [scripts/extractor/utils.py](file:///workspace/scripts/extractor/utils.py) — extraction only; no generation logic to touch.
- [tools/validate_skill.py](file:///workspace/tools/validate_skill.py) — confirms we won't break CI (no frontmatter changes; body length stays WARN-level).
- [.github/workflows/ci.yml](file:///workspace/.github/workflows/ci.yml) — confirms `validate-skill` job will still pass.

### Why Mermaid is the right primary format
- Text-based → lives inside markdown, version-controllable, no binary blobs in the skill folder by default.
- Renders natively in GitHub, VS Code, Claude Code markdown preview, and most doc viewers.
- No new Python deps; stays inside the repo's "density over completeness" philosophy.
- Supports all the user-requested visual types: flowcharts (`flowchart`), infographics/mind-maps (`mindmap`), process flows (`sequenceDiagram`), concept relationships (`graph`/`classDiagram`), state transitions (`stateDiagram-v2`).

---

## Proposed Changes

### Change 1 — Edit `SKILL.md` (primary work)

All edits are additive markdown content. **No frontmatter changes** (so `validate_skill.py` stays green). Five focused insertions:

#### 1a. Add a "Visual Output" note to the "What it generates" intro of Step 0 area
After the existing Modes of Operation section, add a short paragraph stating that every full conversion also produces a `diagrams.md` file with Mermaid diagrams, and that each chapter file includes an inline visual block. Sets expectations up front.

#### 1b. Insert new **Step 7.5 — Generate visual diagrams** (between Step 7 and Step 8)
This is the core addition. New step creates `$SKILLS_HOME/<skill_name>/diagrams.md` containing 4–6 Mermaid blocks:

| Diagram | Mermaid type | Purpose |
|---|---|---|
| Book structure map | `mindmap` | Root = book title; branches = parts/chapters; leaves = key frameworks. Single-glance overview. |
| Framework relationship flowchart | `flowchart TD` | Shows how the author's named frameworks connect, depend on, or feed into each other. |
| Decision flowchart | `flowchart TD` | "Use framework X when Y" rendered as a decision tree — the visual equivalent of `cheatsheet.md`. |
| Process/pipeline sequences | `sequenceDiagram` | For books describing multi-step processes (only when the book actually contains them; skip otherwise). |
| Concept dependency graph | `graph LR` | Which concepts must be understood before others (learning path). |

Rules baked into the step (keeps token budget tight, matches existing philosophy):
- **Max 2,500 tokens** for the whole `diagrams.md` file.
- Each diagram must reference real chapter numbers (`chNN`) as node labels so it doubles as navigation.
- Skip diagram types that don't apply to the book (e.g., skip `sequenceDiagram` for a non-process book).
- Include a one-line caption above each block: what the diagram shows + when to consult it.
- Provide a small "How to view" note at the top of `diagrams.md` (GitHub/VS Code render natively; for PNGs see `visuals/` if generated).

#### 1c. Update **Step 7** chapter template — add an optional inline "Visual" section
Add a small section to the chapter markdown template:
```
## Visual
<!-- Optional: one small Mermaid block (max ~15 lines) summarizing this chapter's
     core framework or flow. Omit entirely if the chapter is purely conceptual
     and a diagram would add no signal. -->
```mermaid
flowchart TD
    ...
```
```
Kept optional and tiny so the 800–1,200 token chapter budget is not blown. The step explicitly says: "omit if a diagram adds no signal."

#### 1d. Update **Step 9** (master SKILL.md) — add a "Visual Map" section
Insert a "Visual Map" section right after "Core Frameworks & Mental Models" and before "Chapter Index", containing ONE high-level `mindmap` Mermaid block (the book at a glance). This is front-loaded so the agent's first load gives a visual overview. Add `diagrams.md` to the "Supporting Files" list with a one-line description.

#### 1e. Update **Step 10** (cleanup and report) — mention `diagrams.md` + add optional image-rendering sub-step
- Add `diagrams.md` to the "Files generated" report block.
- Add an **optional** image-rendering sub-step (only runs if `command -v mmdc` succeeds): for each ` ```mermaid ` block in `diagrams.md` and chapter files, render a PNG into `$SKILLS_HOME/<skill_name>/visuals/`. Use a short bash loop calling `mmdc -i <input.md> -o <output.png>`. If `mmdc` is not installed, print a one-line note: "Install mermaid-cli (`npm i -g @mermaid-js/mermaid-cli`) to render PNGs; Mermaid blocks render natively in GitHub/VS Code." **No Python deps, no failure if absent.**

#### 1f. Update **Update / Fold-in Workflow** — merge diagrams on fold-in
Add a short subsection: when folding new content into an existing skill, regenerate the framework relationship flowchart and concept dependency graph in `diagrams.md` to include new chapters; append new chapter inline visuals per Step 7's updated template. Keep total under 2,500 tokens.

### Change 2 — Edit `README.md` (small, documentation accuracy)

Two small updates so docs match the new behavior:
1. In the "📦 What it generates" table, add a row:
   `| diagrams.md | Mermaid flowcharts, mind-maps, and decision trees | ~2,500 tokens |`
2. In the "📁 Repository structure" tree, add `diagrams.md` and `visuals/` (optional) under the generated skill layout. Note: this is the **generated** skill structure (described in README), not the repo's own tree — keep the edit minimal and accurate.
3. Optionally one line in the "How it works" diagram mentioning the visual pass. Skip if it complicates the ASCII flow.

---

## Assumptions & Decisions

1. **No new Python code.** Generation stays agent-driven via `SKILL.md` instructions (user-confirmed: "Pure SKILL.md instructions"). This matches how chapters/glossary are already produced and avoids a new code path to test/maintain.
2. **Mermaid is primary; images are optional.** User chose "Both Mermaid + images" but emphasized speed/simplicity. Resolved by making images an optional `mmdc` post-step that gracefully no-ops when the tool is absent. No graphviz/matplotlib deps.
3. **No new tests.** Existing `validate_skill.py` continues to pass (no frontmatter changes; body length stays WARN-level, not ERROR). Existing smoke test is unaffected (extraction unchanged). Adding a SKILL.md-content test would be over-engineering for a markdown instruction change.
4. **No frontmatter changes.** `allowed-tools` already includes `Bash` (needed for the optional `mmdc` loop). No new tools required.
5. **Token budgets preserved.** `diagrams.md` capped at 2,500 tokens; chapter inline visuals are tiny and optional; SKILL.md "Visual Map" is one mindmap block. Front-loading principle maintained.
6. **Render-failure tolerant.** Mermaid syntax errors won't break the skill — the agent reads the markdown, and viewers that don't render Mermaid just show the code block as text. The skill remains fully usable.
7. **Update/Fold-in mode supported** so existing skills can gain visuals on re-run, not just freshly-created ones.

---

## Verification Steps

1. **CI stays green:** push the change and confirm `.github/workflows/ci.yml` jobs pass:
   - `test` (pytest) — unchanged extraction code → passes.
   - `lint` (ruff E9,F on scripts/ tests/) — we touch neither → passes.
   - `smoke` (dependency-free extraction) — extraction unchanged → passes.
   - `validate-skill` (`python3 tools/validate_skill.py SKILL.md`) — frontmatter unchanged, body still >500 lines (already a WARN, not ERROR) → passes.
2. **Local skill validation:** run `python3 tools/validate_skill.py SKILL.md` and confirm output is `✓ SKILL.md: no Claude-breaking issues (N warning(s))` with no new ERRORs.
3. **Manual dry-run review:** read the updated `SKILL.md` end-to-end and confirm:
   - Step 7.5 exists between Step 7 and Step 8.
   - Chapter template includes the optional `## Visual` section.
   - Step 9 includes a "Visual Map" section and `diagrams.md` in Supporting Files.
   - Step 10 report lists `diagrams.md` and the optional `mmdc` sub-step is gated on `command -v mmdc`.
   - Update/Fold-in Workflow mentions diagram regeneration.
4. **README accuracy:** confirm the "What it generates" table and "Repository structure" reflect `diagrams.md` and `visuals/`.
5. **Mermaid syntax sanity:** eyeball the example Mermaid blocks in `SKILL.md` to confirm they use valid Mermaid keywords (`mindmap`, `flowchart TD`, `sequenceDiagram`, `graph LR`) so the agent emits valid diagrams.

---

## Files Touched (final, exact list)

| File | Change | Approx. size of edit |
|---|---|---|
| [SKILL.md](file:///workspace/SKILL.md) | Add Step 7.5; add Visual section to Step 7 template; add Visual Map to Step 9; update Step 10 report + optional mmdc sub-step; add diagram-merge note to Update/Fold-in Workflow | ~120–150 lines added |
| [README.md](file:///workspace/README.md) | Add `diagrams.md` row to "What it generates" table; add `diagrams.md` + `visuals/` to "Repository structure" tree | ~5 lines added |

**No other files created or modified. No new scripts. No new tests. No new dependencies.**
