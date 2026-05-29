---
name: deck-review
description: General reviewer command for the deck skill. Scores rubric dimensions 2, 5, 6 (problem clarity, traction/proof, team credibility) and emits the full critic-sibling schema plus a verdict.md.
---

# deck-review — General reviewer

**Role**: general reviewer.
**Reads**: latest `<thread>.{N}/` (specifically `deck.md`, `speaker-notes.md`, and `figures/`).
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, `_summary.md`, `findings.md`, `_meta.json`, `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

## Owned rubric dimensions

The general reviewer owns dimensions:
- **2 — Problem clarity** (weight 5)
- **5 — Traction / proof** (weight 5)
- **6 — Team credibility** (weight 4)

Total ownership: 14/40. Other dimensions are scored by specialist critics (`deck-narrative` for 1+7, `deck-market` for 3+4, `deck-design` for 8) and are left `null` in `_summary.md`.

The general reviewer is also responsible for writing the **aggregated `verdict.md`** — the canonical artifact the orchestrator reads to decide advance/block. The aggregation reads sibling critics if present at the same `<thread>.{N}.<tag>/` and combines per-dimension scores (mean of non-null) and critical flags (logical OR).

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md`.
- **Rubric**: `anvil/skills/deck/rubric.md` (8 dimensions, /40, ≥35 threshold, four critical flags).
- **Optional consumer override**: `.anvil/skills/deck/rubric.overrides.md`.
- **Sibling critics at same `N`** (read but not modified): `<thread>.{N}.narrative/_summary.md`, `<thread>.{N}.market/_summary.md`, `<thread>.{N}.design/_summary.md`. These contribute to the aggregated `verdict.md` if present.

## Outputs

```
<thread>.{N}.review/
  verdict.md         Aggregated decision + total /40 + critical flags + top revision priorities
  scoring.md         Per-dimension score (owned dims only) + 1–3 sentence justification each
  comments.md        Slide-level comments keyed to deck.md slides
  _summary.md        8-dim partial scorecard (owned dims scored; others null) + critical-flag bool
  findings.md        Itemized findings: severity, slide ref, rationale, suggested fix
  _meta.json         { "critic": "review", "role": "deck-review.md", "started": "<ISO>", "finished": "<ISO>", "model": "<id>" }
  _progress.json     Phase state for the review (phase: review)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md`. If `<thread>.{N}.review/_progress.json.review.state == done` AND `verdict.md` + `_summary.md` exist with parseable scores, the review is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed review exists (`review.state == in_progress` without `verdict.md`), delete the partial output and re-review.
3. **Initialize `_progress.json`**: `phases.review.state = in_progress`, `phases.review.started = <ISO>`.
4. **Initialize `_meta.json`** with `critic: "review"`, `role: "deck-review.md"`, `started: <ISO>`, `model: <id>`.
5. **Read inputs**:
   - `<thread>.{N}/deck.md` (slide source) + `speaker-notes.md`.
   - `<thread>/BRIEF.md` (to ground claims — every traction number on a slide should trace to the brief).
   - Optionally `<thread>.{N}/figures/` for sanity-checking diagrams.
   - Sibling critic `_summary.md` files at the same `N` (if they exist), for verdict aggregation.
5b. **Run pre-flight overflow lint**:
   - Invoke `anvil/skills/deck/lib/marp_lint.py`'s `lint_deck(<thread>.{N}/deck.md)`. This is a Python-stdlib heuristic port of marp-vscode's `slide-content-overflow` diagnostic (see the module docstring for the upstream SHA pin and the per-slide `<!-- anvil-lint-disable: slide-content-overflow -->` escape hatch).
   - The call returns a `LintResult` with `errors: list[Finding]`, `warnings: list[Finding]`, and `infos: list[Finding]`. Each `Finding` has `slide` (1-based slide number), `line` (1-based source line), `rule`, `severity`, and `message`.
   - The lint is **review-phase only** — drafter, auditor, figurer, and the specialist critics (`deck-narrative`, `deck-market`, `deck-design`) do not invoke it. The drafter is intentionally allowed to produce an overflowing slide so the reviser sees the failure mode (issue #31, AC6).
   - Cache the `LintResult` for the `_summary.md` and `findings.md` writes below; cache `lint.errors > 0` as `lint_critical_flag` for the verdict logic.
6. **Score owned dimensions**:
   - **Dim 2 — Problem clarity** (0–5): Does the problem slide convey what hurts, for whom, how much, in <30 seconds? Cite specific slide language. Vague problems, self-evident problems, or problems explained only via solution score low.
   - **Dim 5 — Traction / proof** (0–5): Does the traction slide show real evidence at the stage's level? Are projections clearly labeled as projections? Cross-check every number against `BRIEF.md` — any number on the slide not in the brief is a `Fabricated traction` critical flag.
   - **Dim 6 — Team credibility** (0–4): Are bios specific (named prior roles, named outcomes)? Is founder–market fit explicit? Cross-check every bio against `BRIEF.md` — any bio claim not in the brief is a `Fabricated team credentials` critical flag.
7. **Identify critical flags**:
   - `Fabricated traction`: any traction number or customer logo on a slide not attested in `BRIEF.md`.
   - `Fabricated team credentials`: any bio claim not attested in `BRIEF.md`.
   - Open-ended: "any other issue a sophisticated investor would catch and disqualify on." Raise as the fourth-category flag with a one-paragraph justification.
8. **Write `scoring.md`** as a markdown table for owned dimensions (others omitted or shown as N/A):
   ```
   | # | Dimension          | Weight | Score | Justification |
   |---|--------------------|--------|-------|---------------|
   | 2 | Problem clarity    | 5      | 4     | Slide 2 clearly identifies mid-market manufacturers and quantifies (250k plants, $200k/yr engineer cost). One gap: doesn't quantify how much profit is left on the table. |
   | 5 | Traction / proof   | 5      | 3     | Slide 8 lists 8 paying customers and 3 LOIs (all verified in brief). Missing: retention/cohort data and revenue cadence. |
   | 6 | Team credibility   | 4      | 3     | Founder bios are specific (prior roles named). Gap: no advisors slide; brief lists 2 advisors. |
   ```
9. **Write `_summary.md`** as a JSON-in-markdown scorecard. The `lint` block is populated from the cached `LintResult` returned by step 5b:
   ```markdown
   # Review summary

   ```json
   {
     "critic": "review",
     "for_version": <N>,
     "dimensions": {
       "1_narrative_arc":            null,
       "2_problem_clarity":          { "score": 4, "weight": 5 },
       "3_market_size_credibility":  null,
       "4_solution_differentiation": null,
       "5_traction_proof":           { "score": 3, "weight": 5 },
       "6_team_credibility":         { "score": 3, "weight": 4 },
       "7_ask_specificity":          null,
       "8_design_polish":            null
     },
     "lint": {
       "ran": true,
       "errors": 2,
       "warnings": 3,
       "errors_by_slide": [
         { "slide": 4, "line": 27, "rule": "slide-content-overflow", "severity": "error", "message": "Slide exceeds estimated vertical capacity by ~2.0 line-units..." },
         { "slide": 7, "line": 51, "rule": "slide-content-overflow", "severity": "error", "message": "..." }
       ],
       "warnings_by_slide": [
         { "slide": 5, "line": 36, "rule": "slide-content-overflow", "severity": "warning", "message": "..." }
       ]
     },
     "critical_flag": false,
     "critical_flag_notes": []
   }
   ```
   ```
   - When `lint.errors > 0`, set `critical_flag: true` and append an entry of the form `{ "type": "slide_overflow_lint", "slide_refs": ["Slide 4", "Slide 7"], "justification": "Pre-flight overflow lint flagged N slides..." }` to `critical_flag_notes` — the lint is treated as a fourth-category critical flag.
   - If a non-lint critical flag is also raised, populate `critical_flag_notes` with one object per flag: `{ "type": "fabricated_traction", "slide_ref": "Slide 8", "justification": "..." }`.
10. **Write slide-level `comments.md`**: list specific feedback keyed to slide number + heading. Group by severity (`blocker` / `major` / `minor` / `nit`). Example:
    ```
    ## Slide 8 — Traction

    - **major**: ARR figure ($420k) appears here but brief lists $380k ARR. Discrepancy must be resolved before send.
    - **minor**: Add MoM growth rate — investor will ask.

    ## Slide 11 — Financials

    - **blocker**: "Projected $5M ARR by end of year" — current ARR is $380k, no current data point on the curve. Either provide intermediate milestones or drop the projection.
    ```
11. **Write `findings.md`** as itemized findings (deck-specific format the reviser uses for aggregation):
    ```
    ## Findings

    1. **[major]** Slide 8: ARR discrepancy ($420k on slide vs $380k in brief). Suggested fix: use $380k or explain the delta in speaker notes with citation.
    2. **[blocker]** Slide 11: Hockey-stick projection with no intermediate milestones. Suggested fix: replace with month-by-month build to a $5M ARR target, or scope projection to next 12 months only.
    ...

    ## Lint findings

    Each entry comes from the pre-flight `slide-content-overflow` lint (step 5b). Errors block advance; warnings are recorded for the reviser but do not block.

    1. **[error]** Slide 4 (line 27): Slide exceeds estimated vertical capacity by ~2.0 line-units (estimated 15.6u vs. capacity 13.0u). Top costs: image=7.0u, h2=2.0u, bullet=1.1u. Suggested fix: collapse the trailing 4 bullets into a single italic supporting line under the figure, or move the figure to a two-column block.
    2. **[error]** Slide 7 (line 51): Slide exceeds estimated vertical capacity by ~2.7 line-units. Top costs: h1=3.2u, h1+h2-anti-pattern=1.5u. Suggested fix: drop the H2 slide tag — the `_class: ask` dark background already signals "the ask"; use a single H2 headline.
    3. **[warning]** Slide 5 (line 36): Slide borderline (estimated 14.0u vs. capacity 13.0u). Suggested fix (non-blocking): consider trimming one bullet.
    ```
    Each finding: severity, slide reference (with source line), rationale (1–2 sentences), suggested fix (1 sentence). The "Lint findings" section is present even if empty (write `_No lint findings._`).
12. **Aggregate verdict** (this reviewer is the canonical verdict author):
    - Glob `<thread>.{N}.*/_summary.md` (siblings + self). Parse each.
    - For each rubric dimension, compute the aggregate score as the mean of non-null critic scores. Round to one decimal for display; sum for total.
    - For critical flag, take logical OR of all critic flags **including the pre-flight lint**. If this `_summary.md`'s own `lint.errors > 0`, the aggregated critical flag is true regardless of any other critic.
    - Decision: `advance = (total >= 35) AND (no critical flag)`. When `lint.errors > 0`, `advance` is forced `false` and the verdict lists `Slide overflow (lint)` under critical flags — the rubric total is reported honestly but does not save the verdict.
13. **Write `verdict.md`**:
    ```markdown
    # Verdict — <thread> v<N>

    **Total**: 32.5 / 40
    **Decision**: `advance: false`
    **Critical flags**: 1 (from deck-market)

    ## Dimension summary

    | # | Dimension | Weight | Score | Critics contributing |
    |---|-----------|--------|-------|---------------------|
    | 1 | Narrative arc            | 6 | 5.0 | narrative |
    | 2 | Problem clarity          | 5 | 4.0 | review |
    | 3 | Market size credibility  | 5 | 3.0 | market |
    | 4 | Solution differentiation | 5 | 4.0 | market |
    | 5 | Traction / proof         | 5 | 3.0 | review |
    | 6 | Team credibility         | 4 | 3.0 | review |
    | 7 | Ask specificity          | 5 | 5.0 | narrative |
    | 8 | Design polish            | 5 | 5.5 | design |

    ## Critical flags

    - **Market-math error** (raised by deck-market): TAM calculation on Slide 6 multiplies units wrong — claimed $50B but inputs yield $5B. Reviser must recompute.
    - **Slide overflow (lint)** (raised by deck-review pre-flight, 2 errors): Slides 4 and 7 exceed estimated vertical capacity per the `slide-content-overflow` heuristic. See `findings.md` § Lint findings for the per-slide breakdown and suggested fixes.

    ## Top revision priorities

    1. Fix Slide 6 TAM calculation (critical flag).
    2. Resolve the 2 overflow-lint errors on slides 4 and 7 (critical flag — blocks advance).
    3. Slide 11 projection — replace hockey stick with month-by-month build.
    4. Slide 8 ARR discrepancy ($420k vs brief $380k).
    ```
14. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>`.
15. **Update `_meta.json`**: `finished: <ISO>`.
16. **Report**: print one-line status (e.g., `Reviewed acme-seed.1 → acme-seed.1.review/ (review owns 14/40; aggregated total 32.5/40, advance: false, 1 critical flag)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` + `_summary.md` exist and parse) is never re-run.
- A crashed review is re-runnable after deleting partial output.
- If sibling critics produce updated `_summary.md` files **after** this reviewer ran, re-running the reviewer is appropriate — the aggregation in `verdict.md` will pick up the new scores. (The orchestrator should re-run `deck-review` last in any parallel critic batch.)

## Notes for the reviewer agent

- **Be honest, not encouraging.** The skill is not "polish the deck." It is "would I take a meeting based on this?" If the answer is no, score accordingly.
- **Cross-check against the brief.** Every traction number on a slide must trace to the brief. Every bio must trace to the brief. This is the single highest-value check the reviewer performs.
- **Critical flags are not bonus points.** Use sparingly but use them when warranted. A fabrication critical flag in a fundraising deck is a deal-killer.
- **Slide-level comments are actionable.** "Tighten this slide" is not useful. "Slide 8 ARR figure conflicts with brief — use $380k or document the delta in speaker notes" is useful.

## `_progress.json` snippet (review sibling)

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": {
    "review": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

Merge rule: shallow merge; preserve fields not touched by this command.


**Scorecard kind declaration**: This critic's `_meta.json` SHOULD include `"scorecard_kind": "human-verdict"` per `anvil/lib/snippets/scorecard_kind.md`. This is the deck aggregator critic, which emits BOTH the `human-verdict` shape (verdict.md, scoring.md, comments.md) and the `machine-summary` shape (_summary.md, findings.md); the primary kind is `human-verdict` because the aggregated `verdict.md` is the primary deliverable for the orchestrator.
