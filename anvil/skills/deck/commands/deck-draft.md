---
name: deck-draft
description: Drafter command for the deck skill. Produces a new deck version directory from a BRIEF.md, under a strict no-fabrication contract.
---

# deck-draft — Drafter

**Role**: drafter.
**Reads**: `<thread>/BRIEF.md` (required), `<thread>/refs/**` (optional), `<thread>/assets/**` (optional). For revisions, prefer `deck-revise` (which writes a `_revision-log.md`); the drafter is the entry point for new threads.
**Writes**: `<thread>.{N+1}/` containing `deck.md`, `speaker-notes.md`, `figures/`, and `_progress.json`. For a new thread, `N+1 == 1`.

## Inputs

- **Thread slug** (positional argument).
- **`<thread>/BRIEF.md`** (required): the structured brief produced by `deck-brief` (or hand-written by the operator). The drafter errors out if `BRIEF.md` is missing — there is no "draft from raw refs" path. The brief is the contract.
- **`<thread>/refs/**`** (optional): supporting material the drafter may consult for context (transcripts, prior decks, financial spreadsheets). Refs do NOT extend the no-fabrication contract — a number must appear in `BRIEF.md` to appear on a slide.
- **`<thread>/assets/**`** (optional): consumer-provided imagery. The drafter references assets by relative path; the brief's "Assets available" inventory is the closed set of usable assets.

## Outputs

```
<thread>.{N+1}/
  deck.md            Marp markdown slide source (10-15 slides typical for fundraising)
  speaker-notes.md   Per-slide presenter notes (parallel structure: one section per slide)
  figures/
    src/             Mermaid sources (.mmd), matplotlib scripts (.py), data (.csv) — drafter writes stubs/specs here
    .gitkeep         (Empty figures dir; deck-figures populates rendered PNGs and deck.pdf)
  _progress.json     Phase state with draft: done after successful write
```

For a new thread, `N+1 == 1` → output is `<thread>.1/`.

## Procedure

1. **Discover thread state**: enumerate existing `<thread>.{N}/` dirs. Compute the next `N`.
2. **Brief check**: require `<thread>/BRIEF.md` to exist with all required sections (problem, solution, stage, traction, team, market, competition, why now, ask, prior raises, assets). If missing or incomplete, error out with: `BRIEF.md missing or incomplete — run deck-brief <thread> first, or fill the required sections manually.` List which sections are missing.
3. **Resume check**: if `<thread>.{N+1}/_progress.json` exists with `draft.state == in_progress`, treat as a crashed prior run. Delete any partial `deck.md` and re-draft. If `draft.state == done`, the version is already drafted — exit early with a notice (idempotent; this command does not overwrite a completed draft).
4. **Initialize `_progress.json`**: write `phases.draft.state = in_progress`, `phases.draft.started = <ISO>`, `metadata.iteration = N+1`. Read `<thread>/.anvil.json` (graceful-degradation per `_read_anvil_json`; missing/malformed → `{}`) and apply the **paired-override validation** for the iteration cap (see `SKILL.md` §"State machine" → "Per-thread override contract"):
   - If `.anvil.json` has both `max_iterations` (int `>= 4`) AND a non-empty `iteration_cap_rationale` (string, non-whitespace) → write both into `metadata.max_iterations` and `metadata.iteration_cap_rationale`. The drafter's status line confirms the elevated cap, e.g. `... max_iterations=6 (rationale set)`.
   - If `.anvil.json` has `max_iterations` set without a valid `iteration_cap_rationale` (missing, empty, whitespace-only), OR `max_iterations < 4` → fall back to default: `metadata.max_iterations = 4`, `metadata.iteration_cap_rationale = null`. Emit a one-line warning in the drafter's status output, e.g. `WARNING: <thread>/.anvil.json sets max_iterations=6 but iteration_cap_rationale is missing/empty — falling back to default cap of 4. See SKILL.md §State machine for the override contract.`
   - If `.anvil.json` is absent or has neither key → default `max_iterations = 4`, `iteration_cap_rationale = null`. No warning.
5. **Read inputs**: load `BRIEF.md`. Enumerate `refs/` and `assets/`. Load the slide-archetype reference at `anvil/skills/deck/assets/slide-archetypes.md` for canonical slide patterns.
6. **Plan the slide order**: standard fundraising structure (target 10–15 slides). The order below is the canonical order shipped by `templates/deck.md.j2` and `templates/speaker-notes.md.j2` and is the order the narrative critic (`deck-narrative`) grades against:
   - **Slide 1**: Title — company name, one-line tagline, founder name, date.
   - **Slide 2**: Problem — concrete, specific, evocative.
   - **Slide 3**: Why now — what changed in the world. Establishes the open window before the solution lands.
   - **Slide 4**: Solution — plain language, one paragraph + one diagram/screenshot if asset available. Lands on the why-now setup.
   - **Slide 5**: Competition — 2x2 or table. Establishes the competitive landscape so the product reveal lands as differentiated. No competitor smearing.
   - **Slide 6**: Product — what it actually is. Screenshot from `assets/` if available.
   - **Slide 7**: Market — TAM/SAM/SOM with bottom-up logic. Chart in `figures/src/`.
   - **Slide 8**: Traction — only numbers from the brief. No projections unless explicitly labeled.
   - **Slide 9**: Business model — unit economics if applicable; pricing.
   - **Slide 10**: Team — only people in the brief. No anonymous "advisors".
   - **Slide 11**: Financials — current burn, runway, projections clearly labeled as projections.
   - **Slide 12**: Ask — round size, use of funds, runway-to-milestone.
   - **Slide 13** (optional): Appendix — additional traction detail, technical architecture, FAQ slides.

   Subset / reorder as the brief indicates (e.g., partnership pitches skip traction/financials in favor of integration mock-ups). Document slide-order rationale in `speaker-notes.md`.
7. **Write `deck.md`** at `<thread>.{N+1}/deck.md` using the Marp source format. Use `templates/deck.md.j2` as a scaffold. Marp slide separator is `---` on its own line; per-slide CSS via inline directives. Example:
   ```markdown
   ---
   marp: true
   theme: anvil-deck
   paginate: true
   ---

   # Acme Robotics
   Industrial automation for mid-market manufacturers

   _Series Seed · 2026-Q3 · Founder Name_

   ---

   ## The problem

   Mid-market manufacturers run 70% of US industrial output but cannot afford the $2M+ automation systems Fortune 500s deploy.

   - 250,000 US plants in the $10M–$500M revenue band
   - Industry-standard PLC programming requires $200k/yr engineers
   - Average automation ROI break-even: 4.5 years (vs 18 months for F500)
   ```

   Each content slide: ≤6 bullets, ≤30 words total. Walls of text trigger a design-critic finding. Use figures (referenced by relative path: `![Solution architecture](figures/architecture.png)`) for anything visual; the drafter writes the source files into `figures/src/` and `deck-figures` renders them.
8. **No-fabrication contract** (enforced by the drafter; verified by audit):
   - **Numbers**: only numbers that appear verbatim in `BRIEF.md` may appear on slides.
   - **Names**: only people, customers, competitors, investors named in `BRIEF.md` may be named on slides.
   - **Logos / assets**: only files in `<thread>/assets/` (and listed in the brief's "Assets available" inventory) may be referenced.
   - **Projections**: any forward-looking number must be labeled (e.g., "Projection — assumes 15% MoM growth"). Hockey-stick projections without a current data point on the curve are forbidden.

   If a planned slide requires a number / name / asset not in the brief, the drafter has two options:
   - **Mark a stub**: leave the slide with a `[TODO: traction number from brief — currently TBD]` marker. The narrative critic will flag this.
   - **Drop the slide**: if the brief gap is fundamental (e.g., no traction at all for a "traction" slide), drop the slide and document the decision in `speaker-notes.md`.

   The drafter MUST NOT invent numbers, names, or assets.
9. **Write `speaker-notes.md`** at `<thread>.{N+1}/speaker-notes.md`. Parallel structure to `deck.md`: one section per slide, with the slide heading as the section heading. Each section includes:
   - **Talk track** (2–4 sentences): what the founder would say live.
   - **Anticipated questions**: 1–3 likely investor questions on this slide.
   - **Backing data**: where the numbers on this slide came from in the brief (citation).
   - **Drafter notes** (optional): rationale for slide order, asset choices, or omissions.
10. **Populate `figures/src/`**:
    - For each diagram/architecture/flowchart slide, write a Mermaid source file: `figures/src/<name>.mmd`.
    - For each data chart slide, write a matplotlib script: `figures/src/<name>.py` and source data: `figures/src/<name>.csv`. If the brief contains the data inline, extract it to CSV first.
    - The drafter does NOT run renders — `deck-figures` handles rendering. The drafter is responsible for producing source files that `deck-figures` can render unambiguously.
    - See `assets/figure-conventions.md` for matplotlib `$`-escaping, DPI, palette, transparency, and output-path conventions when writing `figures/src/*.py`.
11. **Update `_progress.json`**: `phases.draft.state = done`, `phases.draft.completed = <ISO>`.
12. **Report**: print the path and a one-line status (e.g., `Drafted acme-seed.1/ (deck.md: 12 slides, speaker-notes.md: 12 sections, 4 figures specified)`).

## Voice and style overrides

If `.anvil/skills/deck/voice.md` exists in the consumer repo, load it and apply during drafting. This is how a fund or founder customizes voice without forking the skill.

## Idempotence and resumability

- A completed draft (`draft.state == done` AND `deck.md` exists non-empty) is never overwritten. Re-running on a `DRAFTED` thread is a no-op with a notice.
- A crashed draft (`draft.state == in_progress` with no complete `deck.md`) is re-runnable after deleting any partial output.
- Validation is by file existence (does `deck.md` exist? is it non-empty? does `speaker-notes.md` exist?), not solely by the progress flag.

## `_progress.json` snippet

```json
{
  "version": 1,
  "thread": "<slug>",
  "phases": {
    "draft": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  },
  "metadata": {
    "iteration": <N>,
    "max_iterations": 4,
    "iteration_cap_rationale": null
  }
}
```

When the per-thread override (`<thread>/.anvil.json`) is valid (paired `max_iterations` + non-empty `iteration_cap_rationale`), both fields are carried into `metadata`. When the override is absent or malformed (fell back to default), `iteration_cap_rationale` is `null`.

Merge rule: read existing `_progress.json`, update only `phases.draft` and `metadata`, preserve all other fields.

## Notes for the drafter agent

- **The brief is the contract.** When in doubt, refuse to fill. A `TBD` slide is a feature; a fabricated number is a critical flag.
- **Slide order is the argument.** Don't shuffle for variety. Don't lead with traction unless traction is the strongest card. The standard order works for a reason; deviate with justification in `speaker-notes.md`.
- **Density discipline.** Slides are seen, not read. Aim for one idea per slide, supported by one chart or image. Walls of text are a design-critic finding.
- **Speaker notes are the safety net.** Detail that doesn't fit on the slide goes in the notes. The deck should still work without notes (PDF send-aheads, async review), but the live pitch is richer with them.


**Snippet references**: See `anvil/lib/snippets/progress.md` for the `_progress.json` read-merge-write recipe and `anvil/lib/snippets/timestamp.md` for the ISO-8601 UTC timestamp convention. The merge is shallow: preserve fields and phases not touched by this command.
