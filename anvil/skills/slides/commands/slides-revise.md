---
name: slides-revise
description: Reviser command for the slides skill. Reads the latest version + all critic siblings (review, audit, rehearse) and produces the next version with a changelog mapping critic notes to revisions.
---

# slides-revise — Reviser

**Role**: reviser.
**Reads**: latest `<thread>.{N}/` (deck.md + notes/* + figures/) AND ALL `<thread>.{N}.*/` critic siblings (`.review/`, `.audit/`, `.rehearse/`, and any others).
**Writes**: `<thread>.{N+1}/` containing the revised deck, notes, figures, `_progress.json`, and a `changelog.md` mapping critic notes to the changes made.

This command is the "N parallel critics, one reviser" pattern from anvil's design principles. It consumes any number of critic siblings at the current version and produces a single revised version that addresses them.

## Inputs

- **Thread slug** (positional argument).
- **Latest version**: highest `N` with `<thread>.{N}/deck.md`.
- **Critic siblings**: ALL `<thread>.{N}.<critic>/` directories at that `N`. At minimum the `.review/` sibling is required (the reviewer's verdict drives the dimension-by-dimension revision plan). The `.audit/` and `.rehearse/` siblings, when present, contribute additional findings — and `wrong` audit verdicts or set density/time flags MUST be addressed (they short-circuit advancement).

## Outputs

```
<thread>.{N+1}/
  deck.md            Revised Marp markdown source
  notes/             Carried-over and updated per-slide notes (preserving filename slugs where slides survive; renumbered if slides are added/removed/split)
  figures/           Carried-over and/or updated figures
  changelog.md       Maps each critic note (by sibling + slide number) to the change made
  _progress.json     Phase state with revise: done
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md` AND at least `<thread>.{N}.review/verdict.md`. If no review exists, exit with an error ("no review to revise against; run `slides-review` first").
2. **Resume check**: if `<thread>.{N+1}/_progress.json.revise.state == done` and `deck.md` + `changelog.md` exist, the revision is complete — exit early with a notice.
3. **Iteration cap check**: read `metadata.max_iterations` from `<thread>.{N}/_progress.json` (or `<thread>/.anvil.json` override; default 4). If `N + 1 > max_iterations`, exit with a `BLOCKED` notice — human review required.
4. **Verdict pre-check**: parse `<thread>.{N}.review/verdict.md`. If `advance == true` and there are no critical flags from any sibling (review, audit, rehearse), exit with a notice: the thread is `READY`, no revision needed. (Operator can force-run by deleting the verdict or bumping the iteration manually, but the default is to refuse to revise an already-passing version.)
5. **Initialize `_progress.json`**: `phases.revise.state = in_progress`, `phases.revise.started = <ISO>`, `metadata.iteration = N+1`, `metadata.max_iterations`, `metadata.revised_from = N`.
6. **Read inputs**:
   - Prior version's `deck.md`, `notes/*.md`, `figures/`.
   - `<thread>.{N}.review/verdict.md` + `scoring.md` + `comments.md`.
   - `<thread>.{N}.audit/verdict.md` + `claims.md` (if present).
   - `<thread>.{N}.rehearse/timing.md` + `density.md` (if present).
   - Any other `<thread>.{N}.<critic>/` sibling discovered on disk.
7. **Build a revision plan**:
   - **Critical flags first.** Every `wrong` audit verdict, every density violation, and the time flag (if set) MUST be addressed. These are non-negotiable.
   - For each rubric dimension that scored below threshold, enumerate the specific changes required to lift the score (cite the reviewer's justification in `scoring.md`).
   - For each `comments.md` entry tagged `blocker` or `major`, plan a concrete change.
   - For each `unsupported` audit claim (does NOT set the flag but reduces Dimension 1), plan either: (a) add a citation, (b) soften the claim to match what's defensible, or (c) remove the claim. The reviser chooses per claim and documents the choice in `changelog.md`.
   - Resolve conflicting feedback between critic siblings explicitly (e.g., reviewer says "more depth on slide 7," rehearse says "slide 7 is over-dense" — synthesis: split slide 7 into two slides, each with more depth than the original combined slide).
8. **Produce `deck.md`** at `<thread>.{N+1}/deck.md`:
   - Address each planned change.
   - Preserve sections that scored well — do not regress on dimensions that already met the standard.
   - Density-flag resolution: split over-dense slides into multiple slides; the resulting slide count increase will affect the time estimate (re-checked on the next `slides-rehearse` pass).
   - Time-flag resolution: cut the lowest-priority beat or sub-points identified in `timing.md`'s "Recommended cuts" section.
   - Audit-flag resolution: correct or remove every `wrong` claim. Where correction requires data the brief doesn't provide, mark the claim as a TODO and surface it in `changelog.md` (the next audit pass will re-verdict).
9. **Update `notes/`**:
   - If a slide is unchanged in position and content, copy its notes file unchanged.
   - If a slide is split, create two notes files (renaming the original to one of them, creating a new one for the other).
   - If a slide is removed, remove its notes file.
   - If a slide is reworked, rewrite its notes file.
   - Renumber notes files to maintain `<NN>-<slug>.md` convention matching the new slide order.
10. **Update `figures/`**:
    - Carry over figures that are still referenced.
    - Generate new figures only if the brief or refs provide source data (or defer to `slides-figures` for the rendering).
    - Remove figures no longer referenced (cleanup; not strictly required).
11. **Write `changelog.md`**: a markdown table mapping each critic note to the change made.

    ```
    | Source                              | Note                                              | Resolution                                                |
    |-------------------------------------|---------------------------------------------------|-----------------------------------------------------------|
    | kdd-2026.1.audit (wrong)            | Slide 12: "FlashAttention reduces this to O(n)"   | Corrected to "O(n^2) FLOPs but O(n) memory"; added citation |
    | kdd-2026.1.audit (unsupported)      | Slide 14: "Most production LLMs use this"         | Softened to "Several production LLMs use this (e.g., X, Y)" with citation |
    | kdd-2026.1.rehearse (density flag)  | Slide 7: 62 words                                 | Split into slides 7a (architecture) and 7b (data flow); each ≤30 words |
    | kdd-2026.1.rehearse (time flag)     | 47 min for 45-min slot                            | Cut sub-point "GPU vs TPU comparison" from beat 3; new estimate 43 min |
    | kdd-2026.1.review (blocker)         | Notes/14-results.md is empty                      | Wrote substantive notes covering results interpretation + Q&A defense |
    | kdd-2026.1.review (major)           | Dim 3 (Narrative arc) scored 3/6                  | Added section divider before beat 2; reworded slide 5 to recap beat 1 explicitly |
    ```

    For deliberate non-resolutions (e.g., critic suggested a change the reviser disagrees with), include them with `Resolution: declined — <one-line reason>`. The next reviewer pass can override or accept the reviser's judgment. **Critical flags cannot be declined** — `wrong` claims must be addressed; density and time violations must be resolved.

12. **Update `_progress.json`**: `phases.revise.state = done`, `phases.revise.completed = <ISO>`.
13. **Report**: print the path to the new version dir and a one-line status (e.g., `Revised kdd-2026-keynote.1 → kdd-2026-keynote.2/ (addressed 11 notes, declined 1, slides 22 → 24)`).

## Idempotence and resumability

- A completed revision (`revise.state == done` AND `deck.md` + `changelog.md` exist) is never re-run.
- A crashed revision is re-runnable after deleting partial output.

## Convergence

After this command produces `<thread>.{N+1}/`, the orchestrator runs all three critics (`slides-review`, `slides-audit`, `slides-rehearse`) against the new version. The cycle continues until:
- `verdict.md` reports `advance: true` (no rubric block, no propagated audit/density/time flag) — thread reaches `READY`. Then `slides-audit` (if not already current) and `slides-rehearse` (if not already current) must complete cleanly for the thread to reach `AUDITED` and `REHEARSED`. Then `slides-handout` may produce the terminal export.
- `N+1 > max_iterations` — thread is `BLOCKED` for human review.

## Notes for the reviser agent

- **Critical flags trump everything.** If any sibling raised a critical flag, the revision MUST address it. Failing to address a `wrong` audit claim is a worse outcome than declining a stylistic suggestion.
- **Do not regress.** If a dimension scored well in the prior review, the next version should keep it at the same level or higher. The `changelog.md` is the audit trail proving you did not lose ground while addressing other dimensions.
- **Density splits affect time.** Splitting an over-dense slide adds to the slide count, which adds to the projected duration. After a density split, double-check that you haven't created a new time-flag violation. The next `slides-rehearse` pass will catch it, but a conscientious reviser anticipates.
- **Notes are not optional.** If you add a slide, write its notes. If you split a slide, split its notes too. A revised deck with empty notes files for new slides is a Dimension 7 failure.
- **Declined notes are a feature, not a bug.** Sometimes the reviewer is wrong. Document the disagreement in `changelog.md` so the next reviewer can re-evaluate with full context. But NEVER decline a critical flag.

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

Note `metadata.revised_from` — the version this revision was produced from. Helpful for the orchestrator's anomaly detection (catches gaps in the version chain).
