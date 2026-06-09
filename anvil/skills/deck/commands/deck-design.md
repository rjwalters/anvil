---
name: deck-design
description: Visual / design critic for the deck skill. Renders deck.pdf to per-slide PNGs and evaluates visual hierarchy, density, chart legibility, and consistency. Owns rubric dim 8 (design polish).
---

# deck-design — Visual / design critic

**Role**: design critic.
**Reads**: `<thread>/<thread>.{N}/deck.pdf` (the version dir is nested under the thread root per the artifact contract; renders from `deck.md` if not yet present); produces per-slide PNGs as the artifact actually evaluated.
**Writes**: `<thread>/<thread>.{N}.design/` with per-slide PNGs in `slides/`, plus `_summary.md`, `findings.md`, `comments.md`, `_meta.json`, `_progress.json`. Bare `<thread>.{N}/` / `<thread>.{N}.design/` references below are shorthand for these nested paths.

A markdown-source-only design critic is structurally weak — it can count bullets and word density but cannot see actual visual hierarchy, contrast, or chart legibility. This critic therefore renders the deck to PDF first, splits into per-slide PNGs, and evaluates those.

## Owned rubric dimensions

- **8 — Design polish** (weight 5)

Total ownership: 5/40. Other dimensions remain `null` in this critic's `_summary.md`.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md` under the thread root `<thread>/`.
- **Rendered PDF**: `<thread>.{N}/deck.pdf` — produced by `deck-figures` or by this critic on demand.
- **Marp theme**: `anvil/skills/deck/assets/anvil-deck.css` (or consumer override at `.anvil/skills/deck/templates/<their-theme>.css`).

## Outputs

Nested under the thread root `<thread>/`, as a sibling of the `<thread>.{N}/` version dir under critique:

```
<thread>.{N}.design/
  slides/
    slide-01.png, slide-02.png, ...    Per-slide PNGs at presentation resolution (1920×1080 default)
  _summary.md       8-dim partial scorecard (dim 8 scored; others null) + critical-flag bool
  findings.md       Itemized findings (severity, slide ref, rationale, suggested fix)
  comments.md       Slide-level visual commentary
  _meta.json
  _progress.json
```

**Atomicity** (issue #350, #376): the design sibling dir is written **atomically** via the staged-sidecar primitive at `anvil/lib/sidecar.py`. The five top-level files (`_summary.md`, `findings.md`, `comments.md`, `_meta.json`, `_progress.json`) are staged under a leading-dot sibling `.<thread>.{N}.design.tmp/` during writing; on clean completion the staging dir is renamed (one atomic `Path.rename`) to the final `<thread>.{N}.design/` name. A mid-cycle interrupt leaves a `.<thread>.{N}.design.tmp/` dir on disk that the next invocation's `cleanup_one_staging(<thread>.{N}.design)` per-critic sweep removes; the final-named dir never exists in partial form. Discovery (`anvil/lib/critics.py::discover_critics`) is unchanged — the leading-dot staging shape is invisible to the discovery glob. The `slides/` subdirectory is staged inside the staging dir but is NOT validated by the required-files manifest (per `staged_sidecar`'s flat-manifest contract — subdirectories like `slides/` are not validated).

## Procedure

1. **Discover state** + **resume check** (standard). Then **sweep a stale staging dir from a prior interrupt of THIS critic on THIS version** by invoking `anvil/lib/sidecar.py::cleanup_one_staging(<thread>.{N}.design)` (the per-critic, parallel-safe sweep — issue #376). This removes ONLY a leftover `.<thread>.{N}.design.tmp/` from a previously-killed run of this same critic on THIS version. Sibling critics' in-flight staging dirs under the same thread root are NOT touched (issue #350, #376). The "completed" check is satisfied when the final-named `<thread>.{N}.design/` exists — the atomic-rename contract guarantees the dir only exists when complete.
2. **Open the staged sidecar** for the design dir by invoking the context manager `anvil/lib/sidecar.py::staged_sidecar(final_dir=<thread>.{N}.design, required_files=["_summary.md", "findings.md", "comments.md", "_meta.json", "_progress.json"])`. Every file write below MUST land **inside the yielded staging directory** (the path of the shape `.<thread>.{N}.design.tmp/`), NOT inside the final `<thread>.{N}.design/` path. On clean context exit, the primitive verifies the manifest, then atomically renames the staging dir to its final name (issue #350). Then, **inside the staging dir**, initialize `_progress.json` + `_meta.json`.
3. **Ensure deck.pdf exists**:
   - If `<thread>.{N}/deck.pdf` exists and is newer than `deck.md`, use it.
   - Otherwise, run the Marp renderer (same invocation as `deck-figures` step 7 — single source of truth):
     ```bash
     marp <thread>.{N}/deck.md \
       --pdf \
       --html \
       --config-file anvil/lib/marp/config.yml \
       --theme-set anvil/skills/deck/assets/anvil-deck.css \
       --allow-local-files \
       --output <thread>.{N}/deck.pdf
     ```
     `--html` and `--config-file anvil/lib/marp/config.yml` are required so the rendered PDF matches what `deck-figures` produces — without them, inline fenced ```mermaid blocks drop silently and the design critic critiques a deck that the operator never sees in production.
   - If `marp` is not installed, emit a finding (`[blocker] Marp not installed — design critique cannot run`) and exit early with `_progress.json.design.state = failed`. The orchestrator surfaces this to the operator.
4. **Render per-slide PNGs**:
   - Use a PDF-to-image tool (`pdftoppm` from poppler-utils, or `pdf2image` in Python) to produce one PNG per slide at 1920×1080 (or 1600×900 if disk-space-constrained).
   - Write into `<thread>.{N}.design/slides/` as `slide-NN.png`.
   - These PNGs are the artifact the critic actually evaluates.
5. **Evaluate each slide visually**:
   - **Density**: count visible text on the rendered slide (not the markdown source). Working bar: ≤6 bullets, ≤30 words per content slide. Walls of text are findings.
   - **Visual hierarchy**: is there a clear focal point? Does the eye go where the slide wants it to go? Slides with three equally-weighted columns of bullets fail hierarchy.
   - **Chart legibility**: are axis labels readable at projection scale? Are line/bar colors distinguishable (also for colorblind viewers)? Are data labels present where needed? Are chart titles informative?
   - **Typography consistency**: same font family across slides? Consistent heading sizes? No mixed-case-randomly headings?
   - **Palette consistency**: same color palette across slides? Brand color used purposefully, not decoratively?
   - **Image quality**: are screenshots high-resolution (no pixelation)? Are logos vector (SVG) or high-DPI raster? Stretched/distorted images are findings.
   - **Whitespace**: is there room to breathe, or does every slide feel cramped?
   - **Page numbering and progress**: present and consistent (Marp `paginate: true` directive handles this; flag if disabled).
6. **Evaluate the deck holistically**:
   - **Cover slide**: clean, no clutter, sets tone for the deck?
   - **Section transitions** (if any): visually distinct or just more content slides?
   - **Closing/ask slide**: visually emphasized? An ask slide that looks like every other content slide undersells the moment.
7. **Score Dim 8 — Design polish** (0–5):
   - **5**: Investor would describe the deck as "well-designed" without prompting. Density disciplined throughout. Charts publication-quality. Typography and palette consistent. Visual hierarchy unmistakable on every slide.
   - **4**: Minor inconsistencies (one or two slides with mixed typography, one chart with weak labels). Density mostly disciplined.
   - **3**: Several density violations (walls of text on ≥2 slides) OR multiple inconsistencies. Recognizable as a competent deck but not polished.
   - **2**: Substantial density problems (≥half the slides too dense) OR major chart legibility issues OR major inconsistency.
   - **1**: Reads as a draft / outline rather than a polished deck.
   - **0**: Renders broken (overflowing text, missing images, page-break artifacts).
8. **Identify findings**:
   - Per-slide density violations (with word counts).
   - Chart legibility issues (with specific slides).
   - Inconsistency examples (with two slides illustrating the inconsistency).
   - Image quality issues (with specific slide).
   - Layout / hierarchy issues (with description).
9. **Write `_summary.md`**:
   ```markdown
   # Design critic summary

   ```json
   {
     "critic": "design",
     "for_version": <N>,
     "dimensions": {
       "1_narrative_arc":            null,
       "2_problem_clarity":          null,
       "3_market_size_credibility":  null,
       "4_solution_differentiation": null,
       "5_traction_proof":           null,
       "6_team_credibility":         null,
       "7_ask_specificity":          null,
       "8_design_polish":            { "score": 4, "weight": 5 }
     },
     "critical_flag": false,
     "critical_flag_notes": []
   }
   ```
   ```
   Note: this critic rarely raises critical flags (the four standing flags are content-fabrication-oriented, not design-oriented). A truly broken render (Dim 8 score 0) is a `[blocker]` finding but not a critical flag.
10. **Write `findings.md`** and `comments.md` in the standard format.
11. **Update `_progress.json`** and `_meta.json` inside the staging dir. The `_progress.json` write MUST be the LAST file write before the context manager exits — the manifest verification + atomic rename at exit (issue #350) requires it to be present. Then **exit the `staged_sidecar` context block**: the primitive verifies every name in the required-files manifest exists in the staging dir, then atomically renames `.<thread>.{N}.design.tmp/` → `<thread>.{N}.design/`. The final-named dir only ever exists in **complete** form.
12. **Report**: one-line status (e.g., `Design critic on acme-seed.1 → acme-seed.1.design/ (dim 8: 4/5; 12 slides rendered; 3 findings)`).

## Idempotence and resumability

- Standard: completed = no-op; crashed = re-runnable after deleting partial output.
- **Stale render**: if `<thread>.{N}/deck.pdf` is older than `<thread>.{N}/deck.md` (deck source updated since render), re-render and re-evaluate. The PDF is the source of truth for this critic.

## Renderer dependencies

- **Marp** (Node binary): `npm install -g @marp-team/marp-cli` or `npx @marp-team/marp-cli`. The shipped command assumes `marp` is on PATH.
- **pdftoppm** (poppler): `brew install poppler` (macOS) / `apt-get install poppler-utils` (Debian).
- **Fallback**: if Marp is unavailable, the operator can install pandoc + a Beamer theme as a fallback renderer — but this requires a consumer-side `.anvil/skills/deck/templates/<theme>.tex` override. The shipped renderer is Marp; fallback is consumer territory.

## Notes for the design-critic agent

- **Always evaluate the rendered PNGs, never the markdown source.** The whole point of this critic is that visual hierarchy is invisible in markdown.
- **Density violations are the most common finding.** Drafters reach for bullets; investors read the first three and bounce. Cite specific slides with word counts.
- **Chart legibility is the second most common finding.** Default matplotlib colors and tiny axis labels render unreadably at projection scale. If you can't read the axis labels in the PNG at 50% zoom, the investor can't read them on a conference-room screen either.
- **Consistency is a multiplier.** A deck with three slides that look like a different deck reads as unfinished.
- **Don't critique content here.** Other critics own arc, ask, market, problem, traction, team. Stay in the visual lane.


**Scorecard kind declaration**: This critic's `_meta.json` SHOULD include `"scorecard_kind": "machine-summary"` per `anvil/lib/snippets/scorecard_kind.md`. This is a deck specialist critic — `machine-summary` shape (`_summary.md` + `findings.md`), partial scorecard with non-owned dimensions set to `null`. The deck-review aggregator reads this sibling's `_summary.md` and combines its scores into the composite verdict.
