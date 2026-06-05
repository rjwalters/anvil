---
name: slides-vision
description: Vision-model critic for the slides skill. Renders the talk deck to PDF and per-slide PNGs, then uses a vision-language model to score rendered-only defects (vertical overflow, label cropping, axis legibility, palette adherence, mathtext artifacts, slide density) that the markdown-source critics and the deterministic overflow lint cannot see.
---

# slides-vision — Vision-language-model critic

**Role**: rendered-artifact critic.
**Reads**: `<thread>.{N}/deck.md` (renders to `deck.pdf` + per-page PNGs on demand).
**Writes**: `<thread>.{N}.vision/` with `_review.json` (canonical schema, `kind=vision`), `_meta.json`, `_progress.json`, and per-slide PNGs in `slides/`.

This critic exists because the slides markdown-source critics (`slides-review`, `slides-audit`, `slides-rehearse`) never *look at* the rendered output, and the deterministic `slide-content-overflow` lint (`anvil/lib/marp_lint.py`) only catches the source-only patterns it was written for. The lint and the vision critic are deliberately layered: the lint is fast, deterministic, and source-based (it catches the figure-plus-bullets and `_class: ask` overflow patterns from issues #24/#25 at review time); this critic catches the rest — true rendered overflow from font fallback or theme overrides, label cropping, palette adherence, mathtext artifacts, and slide density at projection scale — none of which is visible in the markdown source. See the `slides-review` "What it does NOT catch" list in `SKILL.md`; this critic is what catches those cases.

## Owned vision dimensions (six, scored /5 each, /30 total)

This critic owns a separate **vision rubric subset** alongside the slides skill's main 8-dimension /40 rubric (see `rubric.md`). The vision dims appear in the aggregated scorecard via the existing mean-of-non-null aggregator (`anvil/lib/critics.py::aggregate`); no schema or aggregation changes are required.

| Dim | Name | What it catches | Most relevant slides rubric dim |
|---|---|---|---|
| v1 | `vertical_overflow` | Content cut off below the slide bottom; rendered-bbox-based, not source-based. The deeper companion to the `slide-content-overflow` lint. | D4 (slide density / cognitive load) |
| v2 | `label_cropping` | Chart axis labels, legends, annotations truncated by the slide/figure border. | D5 (visual quality) / D6 (accessibility) |
| v3 | `axis_legibility` | Font size of chart axis labels and tick marks vs projection scale. If illegible at 50% zoom on the PNG, the audience can't read it from row 20. | D6 (accessibility / readability at distance) |
| v4 | `palette_adherence` | Figures match the Marp theme palette (slides ships an Okabe-Ito color-blind-safe palette per `templates/anvil-slides-theme.css`). Default matplotlib colors are a finding. | D5 (visual quality) / D6 (accessibility) |
| v5 | `mathtext_artifacts` | Italic letters adjacent to dollar signs; LaTeX/MathJax source rendered literally; a `$`-delimited token rendered as math instead of intended literal text. | D1 (technical accuracy) |
| v6 | `slide_density` | Walls of text exceeding the slide's working bar at projection scale (talks: ~30 words / ~6 bullets). The visual companion to the `slides-rehearse` deterministic word/bullet density check. | D4 (slide density / cognitive load) |

The slides skill reuses the framework default rubric (`anvil.lib.vision.default_vision_rubric()`), which ships exactly these six dimensions. The four most load-bearing for talks are `vertical_overflow`, `label_cropping`, `axis_legibility`, and `slide_density`; `palette_adherence` and `mathtext_artifacts` apply too (MathJax is the slides math engine, so the `$`-as-math failure mode is live for any slide that quotes a literal dollar amount). A consumer that wants only the talk-critical subset may pass `VisionRubric(dimensions=[...])` to `VisionCritic.critique()`, but the shipped default is the full six.

The six vision dims are scored 0–5 each. The vision critic puts `null` on the slides skill's 8 main-rubric dimensions (it does not own them); other critics put `null` on v1–v6. The aggregator merges the two scorecards cleanly per the existing rules.

## Critical flags (two initial categories)

Two critical-flag types short-circuit the aggregated verdict to `BLOCK`:

- **`rendered_overflow_unrecoverable`** — content cut off in a way that loses load-bearing information (a number, a citation, a result, a name). For a talk, this is a Dimension 1 (technical accuracy) and Dimension 4 (density) failure at once: a clipped equation or result is both wrong-on-screen and over-dense. Raised when the VLM identifies cropped specific named entities within the lost region.
- **`mathtext_artifact_breaks_meaning`** — a `$X` rendered as italic `X` in a context where the dollar sign (or other math-delimited literal) carries semantic weight. Live for slides because the renderer is pinned to MathJax (`math: mathjax`).

These two flag types are defined in `anvil/lib/vision.py` (`CRITICAL_FLAG_RENDERED_OVERFLOW_UNRECOVERABLE`, `CRITICAL_FLAG_MATHTEXT_ARTIFACT_BREAKS_MEANING`); this critic does not invent new flag names. Other vision findings surface as `Finding` items with severity `major` / `minor` / `nit`.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md`.
- **Rendered PDF**: `<thread>.{N}/deck.pdf` — produced by `slides-figures`/`slides-handout` or by this critic on demand via `anvil.lib.render.render_marp_to_pdf` (which invokes Marp with the framework-pinned `--config-file anvil/lib/marp/config.yml` per #32).
- **Per-page PNGs**: produced by `anvil.lib.render.render_pdf_to_pngs` from the PDF.
- **VLM**: Anthropic SDK by default; consumers without an API key inject a callback per `anvil/lib/vision.py`.

## Outputs

```
<thread>.{N}.vision/
  slides/
    page-1.png, page-2.png, ...    Per-page PNGs at 150 DPI (configurable)
  _review.json                     Canonical schema, kind=vision, rendered_artifact=deck.pdf
  _meta.json                       { critic, role, started, finished, model, scorecard_kind }
  _progress.json                   { version, thread, for_version, phases.vision.{state,started,completed} }
```

## Procedure

1. **Discover state** + **resume check** (per `anvil/lib/snippets/progress.md`). Find the highest `N` with `<thread>.{N}/deck.md`. If `<thread>.{N}.vision/_progress.json.phases.vision.state == done` AND `_review.json` exists, exit early (idempotent).
2. **Initialize `_progress.json`**:
   ```json
   {
     "version": 1,
     "thread": "<slug>",
     "for_version": <N>,
     "phases": { "vision": { "state": "in_progress", "started": "<ISO>" } }
   }
   ```
   and **`_meta.json`**:
   ```json
   {
     "critic": "vision",
     "role": "slides-vision.md",
     "started": "<ISO>",
     "finished": null,
     "model": "claude-opus-4-7-20251022",
     "schema_version": 1,
     "scorecard_kind": "machine-summary"
   }
   ```
   See `anvil/lib/snippets/progress.md` and `anvil/lib/snippets/scorecard_kind.md` for the canonical shapes. Note `for_version` — the slides skill's critic siblings carry `for_version: <N>` naming the version they critique.

3. **Ensure `deck.pdf` exists**:
   - If `<thread>.{N}/deck.pdf` exists and is newer than `deck.md`, use it.
   - Otherwise, call `anvil.lib.render.render_marp_to_pdf(deck_md, out_pdf)`. The library helper invokes Marp with `--config-file anvil/lib/marp/config.yml` per #32 — the same pin the slides skill renders with everywhere else, so the rendered PDF matches what the audience sees.

4. **Render per-page PNGs**:
   - Call `anvil.lib.render.render_pdf_to_pngs(pdf, out_dir=<thread>.{N}.vision/slides/, dpi=150)`.
   - Returns a sorted list of PNG paths (`page-1.png`, `page-2.png`, ...).

5. **Run the vision critic**:
   ```python
   from anvil.lib.vision import VisionCritic, default_vision_rubric
   critic = VisionCritic(critic_id="slides-vision")
   review = critic.critique(
       images=slide_pngs,
       rubric=default_vision_rubric(),
       version_dir="<thread>.<N>",
       rendered_artifact="deck.pdf",
       context="This is a {N}-slide conference/lecture talk deck.",
   )
   ```
   Consumers without an Anthropic API key (CI, offline development) construct the critic with a `callback=` instead. The slides-vision unit tests use the callback path exclusively.

6. **Write `_review.json`**:
   - Validate via `Review.model_validate` (the constructor in step 5 already validated).
   - Serialize with `review.model_dump_json(indent=2)` to `<thread>.{N}.vision/_review.json`.

7. **Update `_progress.json`** and `_meta.json` to `state: done` / `finished: <ISO>`.

8. **Report**: one-line status, e.g. `Vision critic on kdd-2026.1 → kdd-2026.1.vision/ (vision total 22/30; 4 findings; 1 critical flag: mathtext_artifact_breaks_meaning)`.

## Idempotence and resumability

- Standard: completed = no-op; crashed = re-runnable after deleting partial output.
- **Stale render**: if `<thread>.{N}/deck.pdf` is older than `<thread>.{N}/deck.md` (deck source updated since render), re-render and re-evaluate. The PDF is the source of truth for this critic.
- **Stale PNGs**: if PNGs in `slides/` are older than the PDF, re-render.

## Renderer dependencies

- **Marp** (Node binary): `npm install -g @marp-team/marp-cli`. The shipped helper assumes `marp` is on PATH.
- **pdftoppm** (poppler): `brew install poppler` (macOS) / `apt-get install poppler-utils` (Debian). The `anvil.lib.render` helper falls back to `pdf2image` if installed.

## VLM dependencies

- **Anthropic SDK** (default path): `pip install anthropic`. The default model is `claude-opus-4-7-20251022`; pass a different `model=` to override.
- **No SDK required** (callback path): consumers without an API key inject a `callback=` per `anvil/lib/vision.py`. This is the path the slides-vision unit tests use.

## Aggregation behavior

This critic's `_review.json` is discovered by `anvil.lib.critics.discover_critics` exactly like the other slides critics (`.review/`, `.audit/`, `.rehearse/`). The aggregator merges its scorecard into the composite verdict per the existing rules:

- The vision dims (v1–v6) appear in the aggregated scorecard alongside the slides skill's 8 main-rubric dims.
- Per-dim `critical=True` ORs across critics; non-empty `critical_flags` forces `Verdict.BLOCK`.
- The `slides-revise` command (with no code changes) consumes the vision findings via the same discover-glob → aggregate pattern, alongside the `.review/`, `.audit/`, and `.rehearse/` siblings.

See `anvil/lib/README.md` § "Rendered-artifact review (`kind: vision`)" for the worked example.

## Relationship to the slides density dimension

Dimension 4 (slide density / cognitive load) in `rubric.md` is now **jointly owned**: the deterministic source-side checks (`slides-rehearse`'s word/bullet counts, and the `slides-review` pre-flight `slide-content-overflow` lint) catch what is visible in the source, and this critic's `slide_density` + `vertical_overflow` vision dims catch what only shows up after rendering (true overflow from font fallback / theme overrides, density that the source heuristics under-counted). The slides skill has no `slides-design` critic; the density dimension's source-side owner is `slides-rehearse` (mechanical) plus `slides-review` (qualitative), and its rendered-side owner is `slides-vision`. `rubric.md` documents this split.

## Notes for the slides-vision agent

- **Always evaluate the rendered PNGs, not the markdown source.** The whole point of this critic is that visual hierarchy and rendered overflow are invisible in markdown — that is exactly the gap the deterministic lint cannot close.
- **Vision findings often require fixing `figures/src/*.py` or `figures/src/*.mmd`, not `deck.md`.** A vision finding flagging mathtext or palette on a chart label is a matplotlib-script fix under `figures/src/`; a finding flagging illegible axis labels is a DPI/figsize/font-size fix in the same script; a finding flagging an illegible or overflowing mermaid diagram requires editing the `.mmd` source under `figures/src/` and re-running `slides-figures` (the working PDF path is `mmdc → PNG`; inline ```mermaid does not render in the PDF per issue #65). Vertical-overflow on text-heavy slides remains a `deck.md` fix. The `slides-revise` command surfaces this guidance to the reviser explicitly (its D6 reviser-guidance note).
- **Critical flags are sparingly used.** The two shipped types catch information loss (overflow that drops a result or equation) and semantic loss (mathtext that drops a `$`). Other defects surface as findings, not flags.
- **Be specific.** A finding that says "slide 4 chart axis label is cropped" is actionable; "the deck has chart issues" is not.

**Scorecard kind declaration**: This critic's `_meta.json` SHOULD include `"scorecard_kind": "machine-summary"` per `anvil/lib/snippets/scorecard_kind.md`. The canonical payload is `_review.json` per #26 (the prose siblings are not produced — the vision critic ships `_review.json` directly). Note this differs from the slides skill's other critics (`.review/`, `.audit/`, `.rehearse/`), which use the `human-verdict` scorecard kind; the aggregator handles the mixed kinds via the `scorecard_kind` discriminator.
