---
name: slides-figures
description: Figurer command for the slides skill. Generates diagrams and data plots referenced from deck.md. Mermaid first-class; matplotlib for data plots; external assets supported. Idempotent.
---

# slides-figures — Figurer

**Role**: figurer.
**Reads**: latest `<thread>.{N}/deck.md` and `<thread>.{N}/figures/` (and `<thread>.{N}/figures/_specs.md` if the drafter left one).
**Writes**: figure files into `<thread>.{N}/figures/`. Idempotent.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md`.
- **Figure references**: extracted from `deck.md` by scanning for image references (`![alt](figures/<name>.<ext>)`).
- **Figure specs**: if the drafter wrote `<thread>.{N}/figures/_specs.md`, it lists each referenced figure with intended content, source data location, and rendering recommendation.
- **Brief and refs**: `<thread>/BRIEF.md` and `<thread>/refs/**` provide source data for data-driven plots.

## Outputs

```
<thread>.{N}/figures/
  fig-arch.png       Rendered architecture diagram (Mermaid → SVG → PNG, or matplotlib)
  fig-results.png    Rendered data plot
  fig-results.csv    Source data for fig-results (kept alongside)
  _specs.md          (drafter's input, preserved)
  ...
  _progress.json     (in parent dir) Updated with phases.figures.state = done
```

## Tooling — three asset paths

The figurer picks a rendering path per figure based on the spec (or the drafter's intent inferred from `deck.md` context).

### 1. Mermaid (default for diagrams)

Mermaid is first-class in Marp — fenced ```mermaid blocks render natively without preprocessing. For diagrams referenced as `![](figures/fig-arch.png)` rather than inline `mermaid` blocks, the figurer can:
- Write the Mermaid source to `figures/fig-arch.mmd`.
- Render to SVG (or PNG) via `mmdc` (mermaid-cli) if available.
- If `mmdc` is unavailable, fall back to writing the `.mmd` source and a stub `.md` placeholder noting that the consumer must render before slide export.

Use Mermaid for: architecture diagrams, flowcharts, sequence diagrams, state machines, simple block diagrams.

### 2. matplotlib (default for data plots)

For figures derived from a dataset or computation:
- Source data lives in `figures/<name>.csv` (or `.json`, `.tsv`).
- The figurer writes a small `figures/<name>.py` script that reads the CSV and produces `figures/<name>.png` (or `.svg`).
- The script is committed alongside the rendered PNG so regeneration is trivial after a reviser updates the numbers.
- If matplotlib is unavailable at render time, the script is preserved as a deferred-render specification.

Use matplotlib for: bar charts, line plots, scatter plots, distributions, scientific plots from real data.

### 3. External assets

For screenshots, photos, logos, or pre-existing diagrams:
- Referenced from `<thread>/refs/` or `<thread>/assets/`.
- The figurer copies (or symlinks) them into `figures/` with a clear filename.
- No rendering required; just file movement.

Use external assets for: product screenshots, photos, third-party logos, pre-existing institutional diagrams.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md`. Read `<thread>.{N}/_progress.json` to see if `phases.figures.state == done`.
2. **Resume check**: enumerate figure references in `deck.md`. For each referenced figure, check if the file exists in `figures/`. If all referenced figures exist AND `phases.figures.state == done`, exit early — no work needed.
3. **Initialize `_progress.json`**: write `phases.figures.state = in_progress`, `phases.figures.started = <ISO>`.
4. **For each missing or stale figure**:
   - **Mermaid diagrams** — write the `.mmd` source, attempt to render to SVG/PNG via `mmdc`. If `mmdc` fails (missing dependency, syntax error), produce a stub `.md` noting the attempted source.
   - **Data plots** — require a source `.csv` (or equivalent). If no source data exists AND the brief / refs don't provide it, refuse and surface the gap in `figures/_unresolved.md`. The figurer does not invent data.
   - **External assets** — copy from `refs/` or `assets/` into `figures/` with a clear name.
5. **Tooling preference**: self-contained tools (Mermaid CLI, matplotlib, ImageMagick for conversion) over network-dependent services. Failing renders produce a stub `.md` placeholder noting what was attempted and why it failed, rather than silently leaving a broken image reference.
6. **Update `_progress.json`**: `phases.figures.state = done`, `phases.figures.completed = <ISO>`.
7. **Report**: print a one-line status (e.g., `Rendered 5 figures for kdd-2026-keynote.2/ (3 Mermaid, 2 matplotlib; 1 unresolved — see figures/_unresolved.md)`).

## Validation by file existence

The reviewer scores Dimension 5 (Visual quality) and Dimension 6 (Accessibility) in part on whether figures referenced from the body are actually present and readable. The figurer's job is to make the existence check pass. Validation: for every `![...](figures/<filename>)` reference in `deck.md`, the file `figures/<filename>` must exist. The figurer enumerates and fills this list.

The auditor (Dimension 1) additionally checks that data plots match their source data. The figurer makes this verifiable by keeping source `.csv` alongside the rendered image.

## Idempotence and resumability

- Re-running `slides-figures <thread>` on a thread where all referenced figures exist is a no-op.
- Re-running on a thread where some figures are missing fills the gaps without touching existing figures (unless an existing figure is older than its `.csv` or `.mmd` source — in which case re-render).
- The figurer never deletes figures. Stale figures from prior versions of the deck (no longer referenced) are left in place; cleanup is out of scope.

## Notes for the figurer agent

- **Never invent data.** If a chart is requested without source data, refuse and surface the gap in `figures/_unresolved.md`. A figurer that fabricates data poisons the audit (Dimension 1) and undermines the talk's credibility.
- **Mermaid is the default for diagrams.** It produces consistent output, has no LaTeX-style dependency tail, and renders natively in Marp. Reach for matplotlib only when the figure is data-driven; reach for external assets only when the source is genuinely external (a photograph, a third-party screenshot).
- **Keep `.csv` and `.py` alongside rendered output.** Reproducibility matters when the reviser updates numbers and the figure needs to regenerate.
- **No TikZ.** TikZ requires a LaTeX toolchain, which Marp does not invoke. Consumers needing TikZ are also overriding to Beamer; they handle their own figure pipeline.
- **Accessibility: alt text and contrast.** Every figure reference in `deck.md` should have a meaningful `![alt text](...)`. The drafter sets alt text; the figurer should not silently strip it. Use color-blind-safe palettes (Okabe-Ito or viridis) for matplotlib plots; document the palette choice in the `.py` script.

## `_progress.json` snippet

```json
{
  "phases": {
    "figures": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

Merge rule (shallow): preserve fields not touched by this command. See `anvil/lib/snippets/progress.md` for the full read-merge-write recipe and `anvil/lib/snippets/timestamp.md` for the ISO-8601 UTC format. The figurer only touches `phases.figures`; all other phases and metadata are preserved.

Merge rule: preserve all other phases. The figurer only touches `phases.figures`.
