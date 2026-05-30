---
name: deck-revise
description: Reviser command for the deck skill. Discovers all critic siblings at the current version, aggregates per-dimension scores and critical flags, and produces the next version with a revision log.
---

# deck-revise — Reviser

**Role**: reviser. Implements the canonical "N parallel critics, one reviser" pattern.
**Reads**: latest `<thread>.{N}/` and ALL `<thread>.{N}.*/` critic siblings discovered by the glob `<thread>.{N}.*/` minus the bare `<thread>.{N}/`.
**Writes**: `<thread>.{N+1}/` containing the revised `deck.md`, updated `speaker-notes.md` and `figures/`, `_progress.json`, and `_revision-log.md` mapping each critic finding to a change.

This command consumes any number of critic siblings at the current version and produces a single revised version that addresses them.

## Inputs

- **Thread slug** (positional argument).
- **Latest version**: highest `N` with `<thread>.{N}/deck.md`.
- **Critic siblings**: ALL `<thread>.{N}.<critic>/` directories at that `N`. At minimum the `.review/` sibling is required (the general reviewer writes the aggregated `verdict.md` the reviser uses as a starting point). Specialist critics (`.narrative/`, `.market/`, `.design/`) contribute additional dimension scores and findings.
- **Brief**: `<thread>/BRIEF.md` (re-read; numeric/name facts must continue to trace to the brief in the revised version).

## Outputs

```
<thread>.{N+1}/
  deck.md             Revised slide source
  speaker-notes.md    Revised speaker notes
  figures/            Carried over + updated figures (with src/ regenerable)
  _progress.json      Phase state with revise: done
  _revision-log.md    Maps each critic finding to the change made (or "declined" with reason)
  _consistency.md     CONDITIONAL — only present when step 9.5's stale-token sweep
                      finds priced-number tokens (e.g. `$54B+`, `15-25%`) in companion
                      files (figure scripts / speaker-notes) that the revised
                      deck.md no longer asserts. Absent on a clean revision so
                      no noise on threads that touched no numeric anchors.
```

## Discover-glob → aggregate-scorecards → emit-or-loop algorithm

This is the canonical aggregation algorithm for the multi-critic reviser pattern.

### Step 1 — Discover

Glob the critic siblings:

```bash
# Conceptual; reviser implements equivalent file enumeration
critic_dirs = glob("<thread>.{N}.*/") - glob("<thread>.{N}/")
```

Each matched directory is a critic sibling. Read its `_summary.md` (the JSON-in-markdown scorecard) and `findings.md` (the itemized findings list).

### Step 2 — Aggregate scorecards

For each rubric dimension (1–8):
- Collect the per-critic score from every critic that owns the dimension (`_summary.md` non-null entries).
- Compute the aggregated score as the **mean of non-null critic scores**, rounded to one decimal for display, summed as raw values for the total.
- If a dimension is `null` across all critic siblings, mark it as `null` in the aggregated verdict — the deck cannot reach `READY` with any dimension still null (operator must run the missing critic).

For the critical flag:
- `aggregated_critical_flag = OR(critic.critical_flag for each critic in critic_dirs)`.
- Collect all `critical_flag_notes` from contributing critics into the aggregated verdict.

For the decision:
- `aggregated_advance = (aggregated_total >= 35) AND (aggregated_critical_flag == false) AND (no dimension is null)`.

### Step 3 — Emit or loop

- If `aggregated_advance == true`: the thread is `READY` after this revise pass. Reviser still runs to address minor findings (the deck is good but the reviser cleans up `[minor]` and `[nit]` items en route to terminal). Output `<thread>.{N+1}/` with `_revision-log.md` documenting which (if any) minor improvements were made. Update `_progress.json` with `revise: done` and emit a notice.
- If `aggregated_advance == false`: produce the revised version addressing all `[blocker]` and `[major]` findings + the critical-flag-driving issue (if any). Run the lifecycle again: orchestrator should re-run the critics on `<thread>.{N+1}/` and re-aggregate.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md` AND at least `<thread>.{N}.review/verdict.md`. If no review exists, exit: `no review to revise against; run deck-review first`.
2. **Resume check**: if `<thread>.{N+1}/_progress.json.revise.state == done` AND `deck.md` + `_revision-log.md` exist, exit (idempotent).
3. **Iteration cap check**: read `metadata.max_iterations` from `<thread>.{N}/_progress.json` (or `<thread>/.anvil.json` override; default 4). If `N + 1 > max_iterations`, exit with `BLOCKED` notice — human review required.
4. **Aggregate verdict pre-check**: parse `<thread>.{N}.review/verdict.md`. If `advance == true` AND no critical flags AND no `[blocker]`/`[major]` findings remain across any critic sibling → thread is already `READY`, exit with notice. (Operator can force-run by deleting the verdict or bumping iteration manually.)
5. **Initialize `_progress.json`** for `<thread>.{N+1}/`: `phases.revise.state = in_progress`, `phases.revise.started = <ISO>`, `metadata.iteration = N+1`, `metadata.max_iterations`, `metadata.revised_from = N`.
6. **Run discover-glob → aggregate**:
   - Enumerate `<thread>.{N}.*/` directories.
   - Parse each `_summary.md` and `findings.md`.
   - Compute aggregated dimension scores, aggregated critical flag, aggregated decision.
   - Note any missing critic (`design` skipped, `market` not yet run, etc.) — they appear in `_revision-log.md` as gaps for the next iteration.
7. **Build a revision plan**:
   - For each critical-flag entry: plan a specific change that resolves the flag. Critical flags trump everything — the revision must address them or the thread cannot advance.
   - For each `[blocker]` finding (any critic): plan a concrete change.
   - For each `[major]` finding (any critic): plan a change OR document the deliberate decline with one-line reason.
   - For each dimension scoring <50% of weight after aggregation: list the specific changes needed to lift the score (drawn from the relevant critic's findings).
   - **Conflict resolution**: when critics disagree (e.g., reviewer says "more risks", narrative says "fewer slides"), explicitly pick a synthesis. Document the conflict and the resolution in `_revision-log.md`.
   - **Preserve high-scoring sections**: any dimension scoring ≥75% of weight in the prior iteration must remain at ≥75% in the revised iteration. Track regressions in `_revision-log.md`.
8. **Produce revised `deck.md`** at `<thread>.{N+1}/deck.md`:
   - Address each planned change.
   - **Preserve the no-fabrication contract**: every number / name / asset on a slide must continue to trace to `<thread>/BRIEF.md`. The reviser is allowed to drop content but not invent.
   - If a critic's finding implicitly asks the reviser to invent a number ("add ARR retention number to Slide 8"), the reviser MUST either pull the number from the brief OR decline the finding with `Resolution: declined — number not in brief; founder to provide before next iteration`.
9. **Produce revised `speaker-notes.md`** at `<thread>.{N+1}/speaker-notes.md`: parallel revision; update notes for any slide whose content changed.
9.5. **Sweep for stale priced-number tokens** — call `anvil.lib.revise_consistency.sweep` on the deck.md and speaker-notes.md deltas to catch the silent-staleness pattern from #113 (numbers that moved on the slide but were left untouched in companion files):
    - **Deck-vs-companions sweep.** Compute removed-token delta between `<thread>.{N}/deck.md` and `<thread>.{N+1}/deck.md`. Scan companions: the **old** version's `<thread>.{N}/figures/src/*.{py,csv,mmd}` (deliberately operating on the v(N) figure-sources *before* the carry-over in step 10 — findings then drive the per-file updates in step 10) plus the just-written `<thread>.{N+1}/speaker-notes.md`.
    - **Speaker-notes-vs-figures sweep** (optional second pass). When speaker-notes carried a different numeric framing than deck.md and was rewritten in step 9 above, also run a sweep with old_source=`<thread>.{N}/speaker-notes.md`, new_source=`<thread>.{N+1}/speaker-notes.md`, companions=`<thread>.{N}/figures/src/*.{py,csv,mmd}`. Catches sub-case (b) from the issue body (draftwell canary: deck slide 7 SAM framing changed, speaker-notes carried v2 framing).
    - **Two safety rules make false positives rare without an allowlist**: (1) only tokens *removed* across the v(N) → v(N+1) delta are candidates (a number still asserted by the new deck is not flagged); (2) tokens that *survive* anywhere in the new source are filtered (the number may have moved between slides but is still in the deck). Operator may extend with `ignore_tokens` per-thread if a specific token (e.g. a quoted historical figure in a footnote) keeps tripping the sweep.
    - **Output handling — conditional, no noise on clean revisions**:
      - If `sweep(...).passed()` → **no `_consistency.md` is written; no `_revision-log.md` subsection is added.** This is the common case on revisions that don't touch numbers.
      - If findings present → write `<thread>.{N+1}/_consistency.md` with one structured row per finding (companion file, line, stale token, suggested fix) and proceed to step 10 below.
    - **Reviser behaviour on findings** — the operator-facing outcome: each stale-token finding is one of two things:
      - **Real staleness (preferred resolution: update the companion in step 10).** The reviser changes the companion file as part of the figure carry-over to match the new deck token. Record the update in `_revision-log.md`'s "Stale token findings" subsection (see step 11 template).
      - **Legitimate divergence (resolution: decline with rationale).** The companion's token references a deliberately distinct concept (e.g., historical comparison, footnote context). Record the decline in `_revision-log.md`'s "Stale token findings" subsection with a one-line reason; the next iteration's sweep will keep re-flagging until the operator either updates the file or adds the token to the per-thread `ignore_tokens` allowlist.
10. **Carry over and update `figures/`**:
    - Copy `figures/src/` from prior version. Update specific source files for any chart / diagram that needed regeneration per critic findings.
    - Do not copy rendered PNGs / PDFs — those are produced by `deck-figures` after revise completes.
11. **Write `_revision-log.md`** at `<thread>.{N+1}/_revision-log.md`:
    ```markdown
    # Revision log — acme-seed.1 → acme-seed.2

    Aggregated verdict from .1 critics: 32.5/40, advance=false, 1 critical flag (market-math error).

    ## Critical flags addressed

    | Source | Flag | Resolution |
    |---|---|---|
    | acme-seed.1.market | Market-math error: Slide 7 TAM cited as $50B; recomputation from inputs yields $5B | Slide 7 rewritten with correct $5B TAM, recomputation shown in speaker notes, source data committed to figures/src/tam-inputs.csv |

    ## Major findings addressed

    | Source | Finding | Resolution |
    |---|---|---|
    | acme-seed.1.review | Slide 8 ARR discrepancy ($420k slide vs $380k brief) | Slide 8 updated to $380k matching brief. Discrepancy was a drafter typo. |
    | acme-seed.1.review | Slide 11 hockey-stick projection lacks intermediate milestones | Replaced single projection with month-by-month build to $1.5M ARR over 12 months. Beyond-12-month projections moved to appendix with explicit "Projection — see assumptions" labeling. |
    | acme-seed.1.narrative | Slide 12 (Ask): no use-of-funds breakdown | Added use-of-funds bullet: 45% eng / 30% GTM / 15% hires / 10% reserve. Runway-to-milestone framing: "$3M → $1.5M ARR over 18 months at current CAC." |

    ## Minor findings addressed

    | Source | Finding | Resolution |
    |---|---|---|
    | acme-seed.1.market | SAM multiplier (25%) unsourced | Cited NAM 2024 industry survey for budget-bearing plant subset (28%, used in new calc). |
    | acme-seed.1.design | Slide 4 has 11 bullets (limit 6) | Condensed to 5 bullets; moved detail to speaker notes. |

    ## Declined findings

    | Source | Finding | Reason for decline |
    |---|---|---|
    | acme-seed.1.review | Add advisors slide | Brief lists 2 advisors but neither has agreed to be public yet — would violate the assets-available contract. Will revisit when founder confirms. |
    | acme-seed.1.design | Use brand color on every slide | Brand color used on title and section breaks (purposeful, not decorative). Reviser disagrees that brand color should appear on every slide — would flatten visual hierarchy. |

    ## Dimensions preserved (no regression)

    | # | Dimension | Prior score | This iteration target |
    |---|---|---|---|
    | 1 | Narrative arc | 5/6 | ≥5 maintained (slide reorder addresses minor finding without changing core arc) |
    | 7 | Ask specificity | 4/5 | Targeted at 5/5 with use-of-funds + runway-to-milestone |

    ## Gaps / followups

    - `deck-design` critic was not run on this iteration (figures/ updated, deck.pdf needs re-render). Operator should run `deck-figures` then `deck-design` on .2 before next aggregate.
    - Founder follow-up needed: advisor public-listing permission for Slide 10.

    ## Stale token findings

    Detected by `anvil/lib/revise_consistency.sweep` in step 9.5. See
    `_consistency.md` for the full machine-readable table. ONLY present
    when step 9.5 wrote `_consistency.md` (no subsection on a clean
    revision).

    | Companion | Line | Stale token | Resolution |
    |---|---|---|---|
    | figures/src/market-convergence.py | 142 | $54B+ | Updated to $25.9B; replaced chart caption to match Slide 7 revision. |
    | speaker-notes.md | 87 | $2-4B/mo | Updated to $0.8-1.5B/yr matching Slide 7 SAM reframing. |
    | figures/src/footnote-chart.py | 23 | $54B+ | Declined — token is the 2024 historical-compare reference (deliberate divergence from the 2026 figure on Slide 7). Will revisit if sweep keeps re-flagging. |
    ```
12. **Update `_progress.json`**: `phases.revise.state = done`, `phases.revise.completed = <ISO>`.
13. **Report**: one-line status (e.g., `Revised acme-seed.1 → acme-seed.2/ (addressed 1 critical flag + 3 major + 2 minor findings; declined 2; 1 founder follow-up)`).

## Convergence

After this command produces `<thread>.{N+1}/`, the orchestrator should:
1. Run `deck-figures <thread>` to re-render the PDF and any updated figures.
2. Run `deck-review`, `deck-narrative`, `deck-market`, `deck-design` in parallel on the new version.
3. Re-run `deck-revise <thread>` or — if the aggregated verdict says advance — let the thread settle in `READY` state.

The cycle continues until:
- Aggregated `verdict.md` reports `advance: true` (thread reaches `READY`), OR
- `N+1 > max_iterations` (thread is `BLOCKED` for human review).

## Idempotence and resumability

- A completed revision (`revise.state == done` AND `deck.md` + `_revision-log.md` exist) is never re-run.
- A crashed revision is re-runnable after deleting partial output.

## Notes for the reviser agent

- **Do not regress.** If a dimension scored ≥75% in the prior aggregated verdict, it should score ≥75% after revise. The `_revision-log.md` table is the audit trail proving you didn't lose ground.
- **Critical flags trump everything.** A revision that addresses 5 major findings but ignores a critical flag is a failed revision.
- **Declined findings are a feature.** Sometimes critics are wrong (or the resolution would violate the no-fabrication contract). Document the disagreement in `_revision-log.md` so the next critic pass can re-evaluate with full context.
- **Conflict resolution must be explicit.** When critics disagree, pick one and document why. A silent synthesis is harder to audit than an explicit one.
- **The reviser may not invent.** If a finding asks for a number / name / asset not in the brief, the reviser declines with `Resolution: declined — not in brief; founder follow-up needed`. The reviser is never the source of factual content.
- **Vision findings often require fixes in `figures/src/*.py` or mermaid blocks, not in `deck.md` itself.** Findings from the `deck-vision` critic (per `deck-vision.md`) flag rendered-only defects: italic-mathtext artifacts (#23 family) and palette-adherence issues are matplotlib-script fixes under `figures/src/`; axis-legibility and label-cropping findings may require DPI/figsize/font-size changes in the same scripts; mermaid diagram findings (illegible labels, layout overflow) require edits to the inline ```mermaid block in `deck.md`. Vertical-overflow findings on text-heavy slides remain `deck.md` fixes. The default assumption "the reviser edits `deck.md`" silently underserves vision findings — surface the figure-source path explicitly in the `_revision-log.md` resolution column.

## `_progress.json` snippet (revised version dir)

```json
{
  "version": 1,
  "thread": "<slug>",
  "phases": {
    "revise": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  },
  "metadata": {
    "iteration": <N+1>,
    "max_iterations": 4,
    "revised_from": <N>
  }
}
```


**Snippet references**: See `anvil/lib/snippets/progress.md` for the `_progress.json` read-merge-write recipe and `anvil/lib/snippets/timestamp.md` for the ISO-8601 UTC timestamp convention. The merge is shallow: preserve fields and phases not touched by this command.
