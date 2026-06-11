---
name: report-figures
description: Figurer command for the report skill. Generates supporting charts, tables, and the rendered PDF deliverable for the latest report version. Idempotent on resume.
---

# report-figures — Figurer

**Role**: figurer.
**Reads**: `<project>/_project.md`, latest `<project>/<thread>.{N}/report.md` and `<thread>.{N}/exhibits/`, plus (optional) `.anvil/config.json` `report.figure_adapters` and the design artifacts its globs match.
**Writes**: chart/table files into `<thread>.{N}/exhibits/`, adapter-generated block figures into `<thread>.{N}/exhibits/blocks/<unit>/`, and the rendered deliverable `<thread>.{N}/report.pdf`. Idempotent.

## Inputs

- **Project + thread path** (positional argument).
- **Project context**: `<project>/_project.md` — `delivery_format` field selects `pdf` (pandoc default) or `latex` (if `assets/report.tex` is present). `confidentiality_class` may add a watermark.
- **Latest version directory**: highest `N` with `<thread>.{N}/report.md` existing.
- **Exhibit specifications**: extracted from `report.md` by scanning for exhibit references (e.g., `![Figure 1: Latency over time](exhibits/fig-1.png)` or inline references like `see Figure 2`, `see Table 3`).
- **Rendering pipeline assets**: `anvil/skills/report/assets/pandoc-defaults.yaml` and `assets/style.css` (default), OR the LaTeX path via `assets/report.tex` if present. Consumers can override either set via `.anvil/skills/report/assets/`.
- **Figure-adapter registration** (optional): repo-level `.anvil/config.json`, key `report.figure_adapters` — consumer-registered CLI generators that produce block figures from design artifacts (see `commands/report-figure-adapter.md`). Absent file or absent key → step 5 is a no-op and behavior is identical to a pre-#427 install.

## Outputs

```
<project>/<thread>.{N}/
  report.pdf         Rendered deliverable PDF (primary customer-visible output)
  exhibits/
    fig-1.png        Rendered chart (or .svg, .pdf as appropriate)
    fig-1.csv        Source data for fig-1 (if data-driven)
    fig-2.md         Markdown table exhibit (for tables that render inline in PDF)
    blocks/          (only when figure adapters are registered)
      <unit>/
        <adapter>.svg|png|pdf    Adapter-generated block figure
        <adapter>.<ext>.FAILED.md  (on per-unit adapter failure)
      <adapter>.SKIPPED.md       (when an adapter's binary is missing)
    ...
  _progress.json     Updated with phases.figures.state = done
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/report.md`. Read `<thread>.{N}/_progress.json` to see if `phases.figures.state == done`.
2. **Resume check**: enumerate exhibit references in `report.md`. For each referenced exhibit, check if the file exists in `exhibits/`. Check whether `report.pdf` exists and is newer than `report.md`. If all referenced exhibits exist AND `report.pdf` is up-to-date AND `phases.figures.state == done`, exit early — no work needed.
3. **Initialize `_progress.json`**: write `phases.figures.state = in_progress`, `phases.figures.started = <ISO>`.
4. **Generate missing exhibits**:
   - **Markdown tables** (`.md`): generate from inline data in the report body or from a co-located `.csv`. Tables that fit comfortably inline (≤10 rows, ≤6 columns) should be inlined in `report.md` rather than externalized; only externalize when the table is large enough that inlining hurts readability.
   - **Data-driven charts** (`.png` / `.svg`): if a `.csv` source exists, render it. If not, the figurer should refuse and request that the reviser add the source data — the figurer does not invent data (this would poison the audit phase).
   - **Source data** (`.csv`): if a chart is requested without source data and the report body contains the data inline, extract it to a `.csv` first, then render. The extracted CSV becomes the auditable source for the audit phase.
5. **Dispatch consumer figure adapters** (skipped entirely when no `report.figure_adapters` key exists in `.anvil/config.json` — the defaults-off contract): invoke `anvil/skills/report/lib/figure_adapters.py::run_figure_adapters(version_dir, repo_root=<repo root>)`. Per `commands/report-figure-adapter.md`, for each registered adapter × each `input_glob`-matched design unit this:
   - Substitutes `{input}`/`{output}`/`{unit}` into the command template and runs it as a shell-free subprocess (missing binary → the adapter is skipped wholesale with one `exhibits/blocks/<adapter>.SKIPPED.md` note, and this step continues — graceful degrade per the `check_*_available()` pattern).
   - Validates success (exit 0 + non-empty output + magic-byte/format check for the declared `output_kind`) and lands the output atomically at `exhibits/blocks/<unit>/<adapter>.<ext>`. Per-unit failure writes `<adapter>.<ext>.FAILED.md` with captured stderr and continues with remaining units — adapter failures NEVER abort the figures phase.
   - **Idempotence**: a unit is skipped when its output exists, is at least as new as its matched input (mtime ordering, same rule as the csv→chart logic in step 4), and still passes the format check.
   - **Coverage report**: print the `coverage_report(...)` line — units matched / produced / referenced from the report body. Unreferenced outputs are a WARNING for the reviser, **reported, not gated** (promoting coverage to a scored review dimension is deferred per #427).
6. **Determine render path** (markdown→PDF):
   - If `<thread>.{N}/assets/report.tex` exists in the version dir OR `.anvil/skills/report/assets/report.tex` exists in the consumer repo OR `_project.md` has `delivery_format: latex`: use the LaTeX path. Invoke `pandoc report.md -o report.pdf --template <resolved-tex-path> [+ pandoc-defaults.yaml]`.
   - Else (the common case): use the pandoc + CSS path. Invoke `pandoc report.md -o report.pdf --defaults <assets/pandoc-defaults.yaml> --css <assets/style.css>`. Defaults: A4 or letter (per `_project.md` if specified, else letter), serif body, sans headers, page numbers, cover page from `templates/cover.template.md` rendered metadata.
7. **Apply confidentiality watermark** (if `_project.md` declares `confidentiality_class` ≥ `confidential`): add a footer/header watermark via pandoc metadata (e.g., `--metadata=watermark:CONFIDENTIAL`).
8. **Verify deliverable**: confirm `report.pdf` was written, is non-empty, and that its modification time is newer than `report.md`. If the render produced no PDF (pandoc not installed, template error), write a stub `report.pdf.MISSING` text file noting the failure and what was attempted, and leave `phases.figures.state = failed` for operator intervention rather than silently passing. (Adapter-generated block figures from step 5 are part of the deliverable check the same way chart/table exhibits are: any `exhibits/blocks/...` path referenced from `report.md` must exist for the PDF render to be complete.)
9. **Update `_progress.json`**: `phases.figures.state = done`, `phases.figures.completed = <ISO>`.
10. **Report**: print a one-line status (e.g., `Rendered 4 exhibits + report.pdf for acme-q2/findings.2/ (2 charts, 2 tables, 18 pages)`) plus, when adapters are registered, the dispatch summary and the block-figure coverage line from step 5.

## Idempotence and resumability

- Re-running `report-figures <project>/<thread>` on a thread where all referenced exhibits exist AND `report.pdf` is up-to-date is a no-op.
- Re-running on a thread where some exhibits are missing fills the gaps without touching existing exhibits (unless an existing exhibit is older than its `.csv` source — in which case re-render).
- The figurer never deletes exhibits. Stale exhibits from prior versions of the report (no longer referenced) are left in place; cleanup is out of scope.
- If `report.md` is modified after `report.pdf` was rendered (modtime check), the next `report-figures` invocation re-renders the PDF.
- Adapter-generated block figures follow the same rule: a unit whose output is at least as new as its matched design-artifact input is skipped (`skipped-fresh`); touching the input re-dispatches just that unit. See `commands/report-figure-adapter.md` § "Idempotence".

## Render-pipeline customization

Two layers of override:

1. **Consumer-repo override**: drop replacement files into `.anvil/skills/report/assets/` (`style.css`, `pandoc-defaults.yaml`, `report.tex`). The skill detects and prefers these over its own defaults.
2. **Per-version override** (rare): drop an `assets/` dir into a specific version `<thread>.{N}/assets/` to override only for that version. Useful for one-off recipient-specific branding.

Resolution order: per-version assets → consumer-repo assets → skill defaults.

## Validation by file existence

The reviewer (`report-review`) performs a deterministic existence + freshness check on `report.pdf` as part of Dimension 7 scoring: missing or stale (older than `report.md`) caps Dimension 7 ≤ 2/4 with a `major` finding (see `commands/report-review.md` step 4c). The figurer's job is to keep that check passing. Rendered-content quality (figure legibility, table overflow, page-break artifacts) is scored by the optional `report-vision` critic — not by `report-review`. Validation: for every `![...](exhibits/<filename>)` and `(see Figure N)` / `(see Table N)` reference in `report.md`, the file `exhibits/<filename>` must exist AND `report.pdf` must successfully render.

## Notes for the figurer agent

- **Never invent data.** If a chart is requested without source data, refuse and surface the gap to the reviser. A figurer that fabricates data poisons the audit phase — the auditor will catch it (no source citation), and the cycle wastes an iteration.
- **Prefer plain markdown tables over rendered images** when the data is tabular and small. Markdown tables are inspectable, diff-able, and render in any environment. Images are a fallback for genuinely non-tabular data (line/bar/scatter charts, diagrams).
- **Keep `.csv` source files alongside rendered charts.** This makes regeneration trivial after a reviser updates numbers AND gives the auditor a primary source to verify against.
- **`report.pdf` is customer-visible.** Sloppy pagination, broken figure references, or wrong watermarks reach the recipient. Verify the PDF looks right; do not assume the pandoc invocation succeeded just because it did not error.
- **Stub gracefully on missing tooling.** If pandoc is not installed in the agent's environment, write `report.pdf.MISSING` with a clear note rather than silently leaving no PDF. This lets the orchestrator and operator see exactly why the deliverable is incomplete.

## `_progress.json` snippet

```json
{
  "phases": {
    "figures": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

Merge rule (shallow): preserve fields not touched by this command. See `anvil/lib/snippets/progress.md` for the full read-merge-write recipe and `anvil/lib/snippets/timestamp.md` for the ISO-8601 UTC format.

Merge rule: preserve all other phases. The figurer only touches `phases.figures`.

## Git sync (opt-in, off by default)

If the consumer repo carries `.anvil/config.json` with `git.commit_per_phase: true`, end this phase per the per-phase git commit/sync hook documented in `anvil/lib/snippets/git_sync.md` (`.anvil/lib/snippets/git_sync.md` in an installed consumer repo): after `_progress.json` records `phases.figures.state = done`, stage ONLY the `<thread>.{N}/` version dir this phase wrote into (the `exhibits/` charts and tables, adapter-generated `exhibits/blocks/`, the rendered `report.pdf`, and `_progress.json`), commit as `anvil(report/figures): <thread>.{N} [<state>]` (the bracket carries the thread's current derived state per SKILL.md §State machine — the figures phase does not advance the state machine), and push when `git.push` is also `true`. Git failures (not a git repo, commit failure, offline push) emit a one-line warning and continue — the phase still reports success; artifact-on-disk is the source of truth. When `.anvil/config.json` is absent or `git.commit_per_phase` is false/absent, skip this step entirely — behavior is byte-identical to a pre-#426 install (default off).
