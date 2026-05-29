---
name: proposal-review
description: Reviewer command for the proposal skill. Scores the latest proposal version against the 8-dimension /40 rubric and writes a read-only review sibling directory. Runs in parallel with proposal-audit; both are required to advance.
---

# proposal-review — Reviewer

**Role**: reviewer (`kind: judgment`).
**Reads**: latest `<thread>.{N}/` (specifically `proposal.tex` and any `figures/`).
**Writes**: `<thread>.{N}.review/` with `verdict.md`, `scoring.md`, `comments.md`, `_meta.json`, and `_progress.json`.

The review sibling directory is **read-only once written**. Revisions consume it; they never modify it.

This is one of the **two REQUIRED critic siblings** for the proposal skill (the other is `proposal-audit`). Both must complete before a thread can leave the `DRAFTED` state. They run in parallel — this command makes NO attempt to coordinate with `proposal-audit`; both read the same `<thread>.{N}/` and write to disjoint sibling paths.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: enumerated from disk as the highest `N` with `<thread>.{N}/proposal.tex` existing.
- **`customer_kind`**: read from the brief frontmatter (or `<thread>/.anvil.json`); default `external`. Reframes how dimension 7 is read (see below).
- **Rubric**: `anvil/skills/proposal/rubric.md` (8 dimensions, /40, ≥32 threshold, critical flags).
- **Optional consumer override**: `.anvil/skills/proposal/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).

## Outputs

```
<thread>.{N}.review/
  verdict.md       Top-level decision + total /40 + critical flags + top revision priorities
  scoring.md       Per-dimension score (0–weight) + 1–3 sentence justification each
  comments.md      Line-level comments keyed to proposal.tex sections or excerpts
  _meta.json       { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json   Phase state for the reviewer (phase: review)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/proposal.tex`. If `<thread>.{N}.review/_progress.json.review.state == done` and `verdict.md` exists, the review is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed review exists (`review.state == in_progress` without `verdict.md`), delete the partial output and re-review.
3. **Initialize `_progress.json`** for the review dir: `phases.review.state = in_progress`, `phases.review.started = <ISO>`, `for_version = N` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`).
4. **Read inputs**: load `<thread>.{N}/proposal.tex`, enumerate `figures/`, read `customer_kind`, load `rubric.md` and any consumer override.
5. **Score each dimension** (1–8 per rubric):
   - Assign an integer between 0 and the dimension's weight.
   - Write a 1–3 sentence justification citing specific evidence (section heading, excerpt, figure) from the proposal.
   - Record per-dimension result in `scoring.md` as a markdown table with columns `# | Dimension | Weight | Score | Justification`.
   - **Dimension 7 (persuasiveness / value proposition) is read through `customer_kind`**: for `external`, score "does this give the client a reason to commit money?"; for `internal`, score "does this justify the budget allocation against the alternative?" Same weight (4), reframed prompt. Note the framing you used in the justification.
6. **Identify critical flags**: review the proposal against the rubric's four named flags AND the open-ended "any issue that means the proposal cannot proceed as specified" instruction. The reviewer **owns flag 1** (*misses a stated hard constraint*) and shares flag 3 (*not deliverable as resourced*) with the auditor; flags 2 (*cost not credible/sourceable*) and 4 (*internal inconsistency*) are primarily audit-owned but flag them here too if obvious from the text alone. For each flag set, write a one-paragraph justification in `verdict.md`.
7. **Compute total**: sum all dimension scores. `advance = (total >= 32) AND (no critical flags)`.
8. **Write line-level comments**: in `comments.md`, list specific feedback keyed to proposal sections — heading reference + short excerpt + comment. Group by severity (`blocker` / `major` / `minor` / `nit`).
9. **Write `verdict.md`** in the format specified in `rubric.md`:
   - Total: `XX / 40`
   - Decision: `advance: true` or `advance: false`
   - Critical flags (if any)
   - Dimension summary table (per-dim scores; full justifications in `scoring.md`)
   - Top 3 revision priorities (if `advance: false`)
10. **Update `_progress.json`**: `phases.review.state = done`, `phases.review.completed = <ISO>`.
11. **Report**: print the path to the review dir and a one-line status (e.g., `Reviewed gossamer-lan.1 → gossamer-lan.1.review/ (30/40, advance: false, 0 critical flags)`).

## Idempotence and resumability

- A completed review (`review.state == done` AND `verdict.md` exists with a parseable score) is never re-run. Re-invoking is a no-op with a notice.
- A crashed review is re-runnable after deleting partial output. Validation is by file existence (does `verdict.md` exist and parse?), not solely by flag.

## Notes for the reviewer agent

- **You are the judgment critic, not the auditor.** Your job is subjective quality a strong reader can score from the text alone — is the design sound, does it meet the stated hard constraints, is the scope complete, can it plausibly be delivered, is the pitch persuasive? The *arithmetic* of the BOM and the *spec consistency* (does the link budget close? does Qty × Unit = Total?) belong to `proposal-audit` — do not duplicate that work, but DO flag an obvious contradiction if you see one.
- **Constraint satisfaction is the proposal's spine.** A proposal that does not visibly thread each stated hard constraint through the design has not earned dimension 3. If the brief said "invisible, no conduit, 10 Gbps" and the design quietly proposes surface raceway, that is critical flag 1 — not a minor note.
- **Distinguish description from design.** A proposal that *describes* an architecture but never gives the topology, the part choices, or the install method has not resolved dimension 2. This is the most common reason for a low design-correctness score.
- **Deliverability is real, not aspirational.** The "we'll figure out staffing" answer scores low on dimension 5. The proposal must show a concrete path to the tools/skills/staff — the Gossamer "fiber workshop" is the model: own the splicer and the practice spool, not a contractor's phone number.
- **Comments should be actionable.** "Make the cost section stronger" is not useful. "The BOM lists 16 transceivers but the topology has 7 spokes — state the 14 + 2 uplink derivation so the count is checkable" is useful.

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

And the companion `_meta.json` declaring the scorecard kind (see `anvil/lib/snippets/scorecard_kind.md`):

```json
{
  "critic": "review",
  "role": "proposal-review.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict"
}
```

Merge rule (shallow): preserve fields not touched by this command. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
