---
name: memo-review
description: Reviewer command for the memo skill. Scores the latest memo version against the 8-dimension /40 rubric and writes a read-only review sibling directory.
---

# memo-review — Reviewer

**Role**: reviewer.
**Reads**: latest `<thread>.{N}/` (specifically `memo.md` and any `exhibits/`).
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, and `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/memo.md` existing.
- **Rubric**: `anvil/skills/memo/rubric.md` (8 dimensions, /40, ≥32 threshold, critical flags).
- **Optional consumer override**: `.anvil/skills/memo/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).

## Outputs

```
<thread>.{N}.review/
  verdict.md       Top-level decision + total /40 + critical flags + top revision priorities
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Line-level comments keyed to memo.md headings or excerpts
  _meta.json       { critic, role, scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json   Phase state for the reviewer (phase: review)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/memo.md`. If `<thread>.{N}.review/_progress.json.review.state == done` and `verdict.md` exists, the review is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed review exists (`review.state == in_progress` without `verdict.md`), delete the partial output and re-review.
3. **Initialize `_progress.json`** for the review dir: `phases.review.state = in_progress`, `phases.review.started = <ISO>` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`).
4. **Read inputs**: load `<thread>.{N}/memo.md`, enumerate `exhibits/`, load `rubric.md` and any consumer override.
5. **Score each dimension** (1–8 per rubric):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (heading, excerpt, exhibit) from the memo.
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.
6. **Identify critical flags**: review the memo against the 4 example flags in `rubric.md` AND the open-ended "any deal-breaker a sophisticated reader would catch" instruction. For each flag set, write a one-paragraph justification in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 32) AND (no critical flags)`.
8. **Write line-level comments**: in `comments.md`, list specific feedback keyed to memo sections — heading reference + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`).
9. **Write `verdict.md`** in the format specified in `rubric.md`:
   - Total: `XX / 40`
   - Decision: `advance: true` or `advance: false`
   - Critical flags (if any)
   - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
   - Top 3 revision priorities (if `advance: false`)
10. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>`.
11. **Report**: print the path to the review dir and a one-line status (e.g., `Reviewed acme-seed.1 → acme-seed.1.review/ (28/40, advance: false, 0 critical flags)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` exists with a parseable score) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review is re-runnable after deleting partial output. Validation is by file existence (does `verdict.md` exist and parse?), not solely by flag.

## Notes for the reviewer agent

- **Be honest**, not encouraging. The skill is not "polish the memo." It is "would I stake my professional reputation on this recommendation?" If the answer is no, score accordingly.
- **Distinguish assertion from research.** A claim without a source is a hypothesis. Most early-draft memos contain too many hypotheses dressed as facts; this is the most common reason for low Evidence Quality scores.
- **Critical flags are not bonus points.** They are statements that the memo has a defect serious enough that a sophisticated reader would stop reading. Use sparingly but use them when warranted.
- **Comments should be actionable.** "Tighten this section" is not useful. "Replace the unsourced TAM figure with a citation or remove the claim" is useful.

## `_progress.json` and `_meta.json` snippets (review sibling)

This command writes the critic-sibling shape documented in `anvil/lib/snippets/progress.md` (with `for_version` naming the version reviewed). Specifically:

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

> Note: using `review` as the phase name here is the documented v0 status quo; new critics should use their own tag per `anvil/lib/snippets/progress.md` (phase-name normalization across skills is deferred under #21 item 11).

And the companion `_meta.json` declaring the scorecard kind (see `anvil/lib/snippets/scorecard_kind.md`):

```json
{
  "critic": "review",
  "role": "memo-review.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict"
}
```

Merge rule (shallow): preserve fields not touched by this command. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
