---
name: report-figures
description: Figurer command for the report skill. Generates supporting charts, tables, and the rendered PDF deliverable for the latest report version. Idempotent on resume.
---

# report-figures — Figurer

**Role**: figurer.
**Reads**: `<project>/_project.md`, latest `<project>/<thread>.{N}/report.md` and `<thread>.{N}/exhibits/`.
**Writes**: chart/table files into `<thread>.{N}/exhibits/`, and the rendered deliverable `<thread>.{N}/report.pdf`. Idempotent.

## Inputs

- **Project + thread path** (positional argument).
- **Project context**: `<project>/_project.md` — `delivery_format` field selects `pdf` (pandoc default) or `latex` (if `assets/report.tex` is present). `confidentiality_class` may add a watermark.
- **Latest version directory**: highest `N` with `<thread>.{N}/report.md` existing.
- **Exhibit specifications**: extracted from `report.md` by scanning for exhibit references (e.g., `![Figure 1: Latency over time](exhibits/fig-1.png)` or inline references like `see Figure 2`, `see Table 3`).
- **Rendering pipeline assets**: `anvil/skills/report/assets/pandoc-defaults.yaml` and `assets/style.css` (default), OR the LaTeX path via `assets/report.tex` if present. Consumers can override either set via `.anvil/skills/report/assets/`.

## Outputs

```
<project>/<thread>.{N}/
  report.pdf         Rendered deliverable PDF (primary customer-visible output)
  exhibits/
    fig-1.png        Rendered chart (or .svg, .pdf as appropriate)
    fig-1.csv        Source data for fig-1 (if data-driven)
    fig-2.md         Markdown table exhibit (for tables that render inline in PDF)
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
5. **Determine render path** (markdown→PDF):
   - If `<thread>.{N}/assets/report.tex` exists in the version dir OR `.anvil/skills/report/assets/report.tex` exists in the consumer repo OR `_project.md` has `delivery_format: latex`: use the LaTeX path. Invoke `pandoc report.md -o report.pdf --template <resolved-tex-path> [+ pandoc-defaults.yaml]`.
   - Else (the common case): use the pandoc + CSS path. Invoke `pandoc report.md -o report.pdf --defaults <assets/pandoc-defaults.yaml> --css <assets/style.css>`. Defaults: A4 or letter (per `_project.md` if specified, else letter), serif body, sans headers, page numbers, cover page from `templates/cover.template.md` rendered metadata.
6. **Apply confidentiality watermark** (if `_project.md` declares `confidentiality_class` ≥ `confidential`): add a footer/header watermark via pandoc metadata (e.g., `--metadata=watermark:CONFIDENTIAL`).
7. **Verify deliverable**: confirm `report.pdf` was written, is non-empty, and that its modification time is newer than `report.md`. If the render produced no PDF (pandoc not installed, template error), write a stub `report.pdf.MISSING` text file noting the failure and what was attempted, and leave `phases.figures.state = failed` for operator intervention rather than silently passing.
8. **Update `_progress.json`**: `phases.figures.state = done`, `phases.figures.completed = <ISO>`.
9. **Report**: print a one-line status (e.g., `Rendered 4 exhibits + report.pdf for acme-q2/findings.2/ (2 charts, 2 tables, 18 pages)`).

## Idempotence and resumability

- Re-running `report-figures <project>/<thread>` on a thread where all referenced exhibits exist AND `report.pdf` is up-to-date is a no-op.
- Re-running on a thread where some exhibits are missing fills the gaps without touching existing exhibits (unless an existing exhibit is older than its `.csv` source — in which case re-render).
- The figurer never deletes exhibits. Stale exhibits from prior versions of the report (no longer referenced) are left in place; cleanup is out of scope.
- If `report.md` is modified after `report.pdf` was rendered (modtime check), the next `report-figures` invocation re-renders the PDF.

## Render-pipeline customization

Two layers of override:

1. **Consumer-repo override**: drop replacement files into `.anvil/skills/report/assets/` (`style.css`, `pandoc-defaults.yaml`, `report.tex`). The skill detects and prefers these over its own defaults.
2. **Per-version override** (rare): drop an `assets/` dir into a specific version `<thread>.{N}/assets/` to override only for that version. Useful for one-off recipient-specific branding.

Resolution order: per-version assets → consumer-repo assets → skill defaults.

## Validation by file existence

The reviewer scores Dimension 7 (Format / presentation quality) in part on whether `report.pdf` exists, is renderable, and contains the expected exhibits. The figurer's job is to make that check pass. Validation: for every `![...](exhibits/<filename>)` and `(see Figure N)` / `(see Table N)` reference in `report.md`, the file `exhibits/<filename>` must exist AND `report.pdf` must successfully render.

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

Merge rule: preserve all other phases. The figurer only touches `phases.figures`.
