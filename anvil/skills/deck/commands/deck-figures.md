---
name: deck-figures
description: Figurer for the deck skill. Renders Mermaid diagrams and matplotlib charts from sources in figures/src/, then renders the full deck.pdf via Marp.
---

# deck-figures — Figurer + PDF renderer

**Role**: figurer (and PDF renderer).
**Reads**: latest `<thread>.{N}/deck.md` and `<thread>.{N}/figures/src/**`.
**Writes**: rendered images into `<thread>.{N}/figures/` and the full `<thread>.{N}/deck.pdf`.

This figurer is the asset-pipeline implementer for the deck skill. It handles the two asset categories anvil ships (Mermaid + matplotlib), then renders the complete deck PDF that downstream critics (especially `deck-design`) and the operator consume.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md`.
- **Figure sources**: `<thread>.{N}/figures/src/` containing:
  - `*.mmd` — Mermaid diagram source (architecture, flowchart, sequence).
  - `*.py` — Matplotlib Python script (data-driven chart).
  - `*.csv` — Source data for any matplotlib chart.

## Outputs

```
<thread>.{N}/
  figures/
    src/                    (input, not modified)
    <name>.png              Rendered Mermaid diagrams
    <name>.png              Rendered matplotlib charts (one per .py script)
  deck.pdf                  Rendered deck (Marp)
  deck.pptx                 (Optional, opt-in via --pptx flag) PowerPoint export for handoff
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md`. Read `_progress.json`.
2. **Resume check** + idempotence:
   - For each `figures/src/*.mmd`: check if `figures/<name>.png` exists AND is newer than the `.mmd` source. If so, skip.
   - For each `figures/src/*.py`: check if `figures/<name>.png` exists AND is newer than the `.py` script AND any referenced `.csv`. If so, skip.
   - For `deck.pdf`: check if exists AND is newer than `deck.md` AND newer than any figure it references. If so, skip render.
   - If all figures + PDF up to date AND `phases.figures.state == done` → exit early (no-op).
3. **Initialize `_progress.json`**: `phases.figures.state = in_progress`, `phases.figures.started = <ISO>`.
4. **Resolve Mermaid diagrams (inline-default)**:

   The framework Marp pin (`anvil/lib/marp/config.yml`) sets `html: true`,
   which lets fenced ```mermaid blocks render natively inside `deck.md`. The
   default routing for diagrams is therefore **inline fenced ```mermaid blocks
   in `deck.md`** — no out-of-band rendering, no PNG file, no `mmdc`
   invocation. The drafter is expected to produce mermaid this way; the
   figurer's job for this default path is a no-op (the diagram lives in the
   markdown source and Marp handles it at PDF-render time in step 7).

   **Fallback: `mmdc → PNG` out-of-band rendering.** A `.mmd` source under
   `figures/src/` is the explicit opt-in signal that the diagram has been
   pulled out of `deck.md` and should be rendered as a PNG. This path exists
   for the small number of cases mermaid's inline auto-layout cannot handle:

   - **Custom geometry** — the diagram needs an explicit width/height or
     aspect ratio Marp's default cannot accommodate.
   - **Transparent compositing** — the diagram must be overlaid on a
     theme-colored background and needs `--backgroundColor transparent`.
   - **Auto-layout breakdown** — the diagram is larger than the slide's safe
     area (caught by `slide-content-overflow` lint) and only fits when
     rendered at a forced viewport.
   - **Explicit marker on a fence** — the drafter left a
     `<!-- anvil-figure: png -->` HTML comment on the line directly above a
     ```mermaid fence in `deck.md`. Treat this as a "render this fence
     out-of-band" directive: extract the mermaid body to
     `figures/src/<derived-name>.mmd` and proceed with the PNG path below.

   When triggered, render with:
   ```bash
   mmdc \
     --input figures/src/<name>.mmd \
     --output figures/<name>.png \
     --width 1600 \
     --height 900 \
     --backgroundColor white
   ```
   (`mmdc` from `@mermaid-js/mermaid-cli`; install via `npm install -g @mermaid-js/mermaid-cli`.)

   On render failure: write a stub `figures/<name>.png-FAILED.md` describing
   the error, leave the prior PNG (if any) in place, continue with other
   figures. A failed fallback render does NOT silently re-inline the diagram
   — the drafter chose the PNG path on purpose, so the failure is visible.
5. **Render matplotlib charts**:
   - For each `figures/src/<name>.py`: run the script. Convention: the script accepts the working directory `figures/src/` and writes its output to `figures/<name>.png`.
   - Standard script shape:
     ```python
     #!/usr/bin/env python3
     import matplotlib.pyplot as plt
     import pandas as pd
     from pathlib import Path

     SRC = Path(__file__).parent
     OUT = SRC.parent / "<name>.png"

     df = pd.read_csv(SRC / "<name>.csv")
     fig, ax = plt.subplots(figsize=(12, 7), dpi=120)
     # ... chart-specific plotting ...
     ax.set_title("Chart title")
     ax.set_xlabel("X label")
     ax.set_ylabel("Y label")
     fig.tight_layout()
     fig.savefig(OUT, dpi=150, bbox_inches="tight")
     ```
   - Run with `python3 figures/src/<name>.py`. Capture stdout/stderr; on non-zero exit, write a stub `figures/<name>.png-FAILED.md` describing the error.
6. **Validate references**: walk `deck.md` and enumerate every `![...](figures/...)` and `![...](assets/...)` reference. For each:
   - **`figures/...` references**: file should now exist (either rendered or carried over). If absent, log a `[blocker]` warning — the design critic will fail to render this slide cleanly.
   - **`assets/...` references**: file should exist in `<thread>/assets/`. If absent, log a `[blocker]` warning — the drafter referenced a consumer-provided asset that isn't actually present. Operator must add the asset.
7. **Render deck.pdf via Marp**:
   ```bash
   marp <thread>.{N}/deck.md \
     --pdf \
     --html \
     --config-file anvil/lib/marp/config.yml \
     --theme-set anvil/skills/deck/assets/anvil-deck.css \
     --allow-local-files \
     --output <thread>.{N}/deck.pdf
   ```
   - `--html` is required so inline `<script>`-style mermaid blocks survive into the rendered PDF (per `anvil/lib/marp/config.yml` and the inline-mermaid default in step 4 above).
   - `--config-file anvil/lib/marp/config.yml` pins the framework-shared Marp options (`html`, `allowLocalFiles`, theme search path). In an installed consumer repo this resolves to `.anvil/lib/marp/config.yml`. The explicit `--html`, `--theme-set`, and `--allow-local-files` flags are kept as belt-and-suspenders so the CLI still does the right thing when the config file is missing or has been overridden.
   - `--allow-local-files` is required for Marp to inline local image references.
   - If `marp` is missing: write a stub `<thread>.{N}/deck.pdf-FAILED.md` describing the missing dependency. Exit `phases.figures.state = failed` (the orchestrator surfaces this).
   - If render succeeds but produces zero pages (rare; usually indicates a malformed Marp directive): log `[blocker]` and exit failed.
8. **Optional PPTX export**:
   - If the operator passed `--pptx` to `deck-figures`, also produce `<thread>.{N}/deck.pptx`:
     ```bash
     marp <thread>.{N}/deck.md \
       --pptx \
       --html \
       --config-file anvil/lib/marp/config.yml \
       --theme-set anvil/skills/deck/assets/anvil-deck.css \
       --allow-local-files \
       --output <thread>.{N}/deck.pptx
     ```
   - Default behavior is PDF-only; PPTX is opt-in because PowerPoint export is a handoff feature, not a review-loop artifact.
9. **Update `_progress.json`**: `phases.figures.state = done`, `phases.figures.completed = <ISO>`.
10. **Report**: one-line status (e.g., `Rendered 4 figures + deck.pdf for acme-seed.2/ (2 mermaid, 2 matplotlib; 13 slides in PDF)`).

## Asset-policy guardrails

This figurer renders only the asset categories anvil ships:
- **Mermaid diagrams** (deterministic from plaintext source) — shipped.
- **Matplotlib charts** (deterministic from script + CSV) — shipped.

It does NOT:
- **Generate imagery** (DALL-E, Midjourney, Stable Diffusion, etc.) — out of scope for v0. Generative imagery in a fundraising deck is a credibility liability; deferred to consumer extension via `commands/deck-imagegen.md` override.
- **Fetch logos / screenshots / photos** — consumer-provided in `<thread>/assets/`. The figurer validates references but does not create these assets.
- **Compose composite imagery** (e.g., overlay logos on a background) — out of scope. The drafter references atomic assets; composition is a design-tool job, not an authoring-pipeline job.

This matches the SKILL.md hybrid asset policy.

## Render dependencies

- **Marp** (Node): `npm install -g @marp-team/marp-cli` or `npx @marp-team/marp-cli`. The render call assumes `marp` on PATH.
- **Mermaid CLI** (Node): `npm install -g @mermaid-js/mermaid-cli` (provides `mmdc`).
- **Python + matplotlib + pandas**: `python3 -m pip install matplotlib pandas`.
- **(Optional, for design critic)** **pdftoppm** (poppler): `brew install poppler` / `apt-get install poppler-utils`. Used by `deck-design`, not by this figurer.

If any dependency is missing, the figurer writes a `<name>-FAILED.md` stub describing what was attempted and which dependency to install — rather than silently leaving a broken reference.

## Idempotence and resumability

- Re-running on a thread where all figures + deck.pdf are up-to-date is a no-op.
- Re-running on a thread where some figures are stale (source updated since render) re-renders only the stale figures + the PDF (which depends on them).
- The figurer never deletes figures. Stale figures from prior versions (no longer referenced by `deck.md`) are left in place; cleanup is out of scope. The reviser is responsible for not carrying over orphaned source files.

## Validation by file existence

Downstream critics (especially `deck-design`) and the audit assume:
- Every `![...](figures/<name>.png)` reference in `deck.md` resolves to an actual file.
- `deck.pdf` exists and is newer than `deck.md`.

The figurer's job is to make these checks pass. Validation is by file existence and mtime comparison, not by `_progress.json` flag.

## Notes for the figurer agent

- **Never invent data.** If a matplotlib script references a CSV that doesn't exist, refuse and surface the gap — do not generate placeholder data. A fabricated chart in a fundraising deck is the easiest critical flag to trigger (the audit will catch the data mismatch).
- **Mermaid for diagrams; matplotlib for charts.** Don't render a flowchart with matplotlib or a data chart with Mermaid — both work poorly. Stay in the canonical lane.
- **Render to 150+ DPI.** Slides project; pixelated charts are findings.
- **Failed renders produce stub markdown, not silent omissions.** A `figures/<name>.png-FAILED.md` is a visible, debuggable artifact; a missing PNG is a mystery.
- **Always re-render the PDF last.** Figure renders → reference validation → PDF render. A stale PDF cached from before figure updates is the most common gotcha.

## `_progress.json` snippet

```json
{
  "phases": {
    "figures": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

Merge rule: preserve all other phases. The figurer only touches `phases.figures`.


**Snippet references**: See `anvil/lib/snippets/progress.md` for the `_progress.json` read-merge-write recipe and `anvil/lib/snippets/timestamp.md` for the ISO-8601 UTC timestamp convention. The merge is shallow: preserve fields and phases not touched by this command.
