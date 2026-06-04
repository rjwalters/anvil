---
name: memo-figures
description: Figurer command for the memo skill. Generates supporting charts, tables, and exhibits for the latest memo version. Idempotent on resume.
---

# memo-figures — Figurer

**Role**: figurer.
**Reads**: latest `<thread>.{N}/<body_filename>` (default `memo.md`) and `<thread>.{N}/exhibits/`.
**Writes**: chart/table files into `<thread>.{N}/exhibits/`. Idempotent.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/<body_filename>` existing. The body filename is resolved at command start via `load_body_filename(<thread_dir>)` — default `"memo.md"`, per-thread override via top-level `body_filename` in `<thread>/.anvil.json` (see SKILL.md §"Body filename customization").
- **Exhibit specifications**: extracted from `<body_filename>` (default `memo.md`) by scanning for exhibit references (e.g., `![Exhibit 1: Unit economics scenarios](exhibits/fig-1.png)` or inline references like `see Exhibit 2`).

## Outputs

```
<thread>.{N}/exhibits/
  fig-1.png          Rendered chart (or .svg, .pdf as appropriate)
  fig-1.csv          Source data for fig-1 (if the figure is data-driven)
  fig-2.md           Markdown table exhibit (for tables that should render inline in PDF export)
  ...
  _progress.json     (in parent dir) Updated with phases.figures.state = done
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/<body_filename>` (default `memo.md`; resolved per the Inputs section above via `load_body_filename(<thread_dir>)`). Read `<thread>.{N}/_progress.json` to see if `phases.figures.state == done`.
2. **Resume check**: enumerate exhibit references in `<body_filename>`. For each referenced exhibit, check if the file exists in `exhibits/`. If all referenced exhibits exist AND `phases.figures.state == done`, exit early — no work needed.
3. **Initialize `_progress.json`**: write `phases.figures.state = in_progress`, `phases.figures.started = <ISO>`.
4. **For each missing or stale exhibit**:
   - **Markdown tables** (`.md`): generate from inline data in the memo body or from a co-located `.csv`. Tables that fit comfortably inline (≤10 rows, ≤6 columns) should be inlined in `<body_filename>` rather than externalized; only externalize when the table is large enough that inlining hurts readability.
   - **Data-driven charts** (`.png` / `.svg`): if a `.csv` source exists, render it. If not, the figurer should refuse and request that the reviser add the source data — the figurer does not invent data.
   - **Source data** (`.csv`): if a chart is requested without source data and the memo body contains the data inline, extract it to a `.csv` first, then render.
5. **Tooling**: the figurer SHOULD prefer self-contained tools (matplotlib, plotly-static, pandoc) over network-dependent services. Failing renders should produce a stub `.md` placeholder noting what was attempted and why it failed, rather than silently leaving a broken reference.
6. **Update `_progress.json`**: `phases.figures.state = done`, `phases.figures.completed = <ISO>`.
7. **Report**: print a one-line status (e.g., `Rendered 3 exhibits for acme-seed.2/ (2 charts, 1 table)`).

## Idempotence and resumability

- Re-running `memo-figures <thread>` on a thread where all referenced exhibits exist is a no-op.
- Re-running on a thread where some exhibits are missing fills the gaps without touching existing exhibits (unless an existing exhibit is older than its `.csv` source — in which case re-render).
- The figurer never deletes exhibits. Stale exhibits from prior versions of the memo (no longer referenced) are left in place; cleanup is out of scope.

## Validation by file existence

The reviewer scores Dimension 8 (Prose & structure) in part on whether exhibits referenced from the body are actually present. The figurer's job is to make that check pass. Validation: for every `![...](exhibits/<filename>)` and `(see Exhibit N)` reference in `<body_filename>` (default `memo.md`), the file `exhibits/<filename>` must exist. The figurer enumerates and fills this list.

## Notes for the figurer agent

- **Never invent data.** If a chart is requested without source data, refuse and surface the gap to the reviser. A figurer that fabricates data poisons the memo's evidence dimension.
- **Prefer plain markdown tables over rendered images** when the data is tabular and small. Markdown tables are inspectable, diff-able, and render in any environment. Images are a fallback for genuinely non-tabular data (line/bar/scatter charts, diagrams).
- **Keep `.csv` source files alongside rendered charts.** This makes regeneration (after a reviser updates the numbers) trivial.

## `_progress.json` snippet

This command updates `phases.figures` only, per the shallow merge rule documented in `anvil/lib/snippets/progress.md`. The full version-dir shape is preserved across the read-merge-write:

```json
{
  "phases": {
    "figures": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

Merge rule (shallow): preserve all other phases and all `metadata` fields. The figurer only touches `phases.figures`. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
