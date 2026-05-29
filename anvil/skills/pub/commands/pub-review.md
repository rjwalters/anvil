---
name: pub-review
description: Reviewer command for the pub skill. Scores the latest paper version against the 8-dimension /40 rubric and writes a read-only review sibling directory.
---

# pub-review — Reviewer

**Role**: reviewer.
**Reads**: latest `<thread>.{N}/` (specifically `main.tex`, `refs.bib`, and any `figures/`).
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, and `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/main.tex` existing.
- **Rubric**: `anvil/skills/pub/rubric.md` (8 dimensions, /40, ≥32 threshold, critical flags).
- **Optional consumer override**: `.anvil/skills/pub/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).

## Outputs

```
<thread>.{N}.review/
  verdict.md       Top-level decision + total /40 + critical flags + top revision priorities
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Line-level comments keyed to main.tex section headings or excerpts
  _meta.json       { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json   Phase state for the reviewer (phase: review)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/main.tex`. If `<thread>.{N}.review/_progress.json.review.state == done` and `verdict.md` exists, the review is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed review exists (`review.state == in_progress` without `verdict.md`), delete the partial output and re-review.
3. **Initialize `_progress.json`** for the review dir: `phases.review.state = in_progress`, `phases.review.started = <ISO>` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`).
4. **Read inputs**: load `<thread>.{N}/main.tex`, `<thread>.{N}/refs.bib`, enumerate `figures/`, load `rubric.md` and any consumer override.
5. **Score each dimension** (1–8 per rubric):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (section heading, excerpt, figure, table) from the paper.
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.

   Notes specific to paper review (in addition to the general guidance in `rubric.md`):
   - **Rigor (D1)** and **Evidence (D2)** are scored independently. A paper with a sound method but only one experiment scores high on D1 and low on D2.
   - **Clarity of contribution (D3)** is scored from the abstract and introduction. If the contribution is not extractable in one sentence per item from those two sections, score below full weight.
   - **Related-work positioning (D4)** requires the reviewer to read `\section{Related Work}` against `refs.bib`. If the closest prior work (per the reviewer's domain knowledge) is missing from `refs.bib`, set a critical flag (close prior work ignored) AND score D4 low.
   - **Reproducibility (D5)**: check for explicit code/data/seed references and a methods section detailed enough to replicate. Pseudo-code without hyperparameters scores low.
   - **Figure & table quality (D6)**: the reviewer reads captions standalone. A caption that does not communicate the figure's point without the body text loses points.
   - **Citation hygiene (D8)**: at this stage the reviewer only checks (a) every `\cite{}` resolves to an entry in `refs.bib` (catches build failure early) and (b) bibliography entries have the standard fields. Whether cited papers actually support claims is `pub-audit`'s job.
6. **Identify critical flags**: review the paper against the example flags in `rubric.md` (citation error, plagiarism risk, missing experiment for a claim, numerical inconsistency, close prior work ignored, build/compile failure) AND the open-ended "any dealbreaker a sophisticated reader would catch" instruction. For each flag set, write a one-paragraph justification in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 32) AND (no critical flags)`.
8. **Write line-level comments**: in `comments.md`, list specific feedback keyed to paper sections — section heading + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`). For related-work concerns, tag with `related-work` so a re-run of `pub-litsearch` can pick them up specifically.
9. **Write `verdict.md`** in the format specified in `rubric.md`:
   - Total: `XX / 40`
   - Decision: `advance: true` or `advance: false`
   - Critical flags (if any)
   - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
   - Top 3 revision priorities (if `advance: false`)
10. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>`.
11. **Report**: print the path to the review dir and a one-line status (e.g., `Reviewed q3-method.1 → q3-method.1.review/ (28/40, advance: false, 1 critical flag)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` exists with a parseable score) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review is re-runnable after deleting partial output. Validation is by file existence (does `verdict.md` exist and parse?), not solely by flag.

## Notes for the reviewer agent

- **Be honest, not encouraging.** The skill is not "polish the paper." It is "would a sophisticated program committee member at the target venue recommend acceptance?" If the answer is no, score accordingly.
- **Distinguish assertion from evidence.** A claim without an experiment, proof, or citation is a hypothesis. This is the most common reason for low Evidence Sufficiency scores.
- **Critical flags are not bonus points.** Use them when the paper has a defect serious enough that a sophisticated reader would stop reading. The audit phase (`pub-audit`) will catch many fact/citation issues — the reviewer should still flag what's visible at review time.
- **Comments should be actionable.** "Tighten this section" is not useful. "Replace the unsourced 87% accuracy claim in the abstract with a citation to Table 2, or remove the claim" is useful.
- **Defer fact-check to the auditor.** This phase scores citation hygiene (do entries exist and are they well-formed) but does not verify cited papers actually support claims. Save the per-citation claim-support pass for `pub-audit`.

## `_progress.json` and `_meta.json` snippets (review sibling)

This command writes the critic-sibling shape documented in `anvil/lib/snippets/progress.md` (with `for_version` naming the version reviewed), and a `_meta.json` declaring the scorecard kind per `anvil/lib/snippets/scorecard_kind.md`:

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

```json
{
  "critic": "review",
  "role": "pub-review.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict"
}
```

Merge rule (shallow): preserve fields not touched by this command. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
