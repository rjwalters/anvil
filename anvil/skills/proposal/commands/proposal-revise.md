---
name: proposal-revise
description: Reviser command for the proposal skill. Reads the latest version + ALL critic siblings (both .review/ and .audit/ required) and produces the next version with a changelog mapping critic notes to changes.
---

# proposal-revise — Reviser

**Role**: reviser.
**Reads**: latest `<thread>.{N}/` and ALL `<thread>.{N}.*/` critic siblings (`.review/`, `.audit/`, and any optional `.critic/`).
**Writes**: `<thread>.{N+1}/` containing the revised proposal, the class file, figures, `_progress.json`, and a `changelog.md` mapping critic notes to the changes made.

This command is the canonical "N parallel critics, one reviser" pattern from anvil's design principles. It consumes any number of critic siblings at the current version and produces a single revised version that addresses them. For the proposal skill, **both `.review/` and `.audit/` are required** — the reviser refuses to run if either is missing.

## Inputs

- **Thread slug** (positional argument).
- **Latest version**: highest `N` with `<thread>.{N}/proposal.tex`.
- **Critic siblings**: ALL `<thread>.{N}.<critic>/` directories at that `N`. BOTH `<thread>.{N}.review/verdict.md` AND `<thread>.{N}.audit/verdict.md` are REQUIRED (the proposal skill runs both critics by default). Optional siblings (a domain specialist `.critic/`) contribute additional findings.

## Outputs

```
<thread>.{N+1}/
  proposal.tex          Revised proposal body
  anvil-proposal.cls    Carried over so the version dir compiles standalone
  figures/              Carried over and/or updated figures
  changelog.md          Maps each critic note (by sibling + section) to the change made in this revision
  _progress.json        Phase state with revise: done
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/proposal.tex` AND BOTH `<thread>.{N}.review/verdict.md` and `<thread>.{N}.audit/verdict.md`. If either critic sibling is missing, exit with an error ("both review and audit are required before revising; run the missing critic first").
2. **Resume check**: if `<thread>.{N+1}/_progress.json.revise.state == done` and `proposal.tex` + `changelog.md` exist, the revision is complete — exit early with a notice.
3. **Iteration cap check**: read `metadata.max_iterations` from `<thread>.{N}/_progress.json` (or `<thread>/.anvil.json` override; default 4). If `N + 1 > max_iterations`, exit with a `BLOCKED` notice — human review required.
4. **Combined-advance pre-check**: parse both verdicts. If `review.advance == true` (≥35) AND `audit.pass == true` AND there are no critical flags in either sibling, exit with a notice: the thread is `READY`/`AUDITED`, no revision needed. (Operator can force-run by deleting a verdict or bumping the iteration manually, but the default is to refuse to revise an already-passing version.)
5. **Initialize `_progress.json`**: write `phases.revise.state = in_progress`, `phases.revise.started = <ISO>`, `metadata.iteration = N+1`, `metadata.max_iterations`.
6. **Read inputs**:
   - Prior version's `proposal.tex` and `figures/`.
   - `<thread>.{N}.review/verdict.md` + `scoring.md` + `comments.md`.
   - `<thread>.{N}.audit/verdict.md` + `findings.md` + `evidence.md`.
   - Every other `<thread>.{N}.<critic>/` sibling discovered on disk.
7. **Build a revision plan**:
   - For each rubric dimension that scored below threshold (or had a critical flag), enumerate the specific changes required to lift the score.
   - For each `comments.md` entry tagged `blocker` or `major`, plan a concrete change.
   - For each audit finding with `Verified? = no` or a critical flag, plan the specific factual / arithmetic fix (correct the BOM line, fix the subtotal, reconcile the transceiver count with the topology, source the unsourced price, or close the link budget).
   - Resolve conflicting feedback between critic siblings explicitly (e.g., reviewer says "cut the BOM detail to tighten the pitch," auditor says "the cut line was the one with the sourceable basis" — pick a synthesis and note it in the changelog).
8. **Produce `proposal.tex`** at `<thread>.{N+1}/proposal.tex`:
   - Address each planned change.
   - Preserve sections that scored well — do not regress on dimensions that already met the standard.
   - Carry over `figures/` and the `anvil-proposal.cls` from the prior version; update or add figures as the revision plan requires.
   - **Critical flags MUST be addressed**: a *missed hard constraint* flag (1) requires the design to actually satisfy the constraint (no surface raceway if invisibility was required); a *cost not sourceable* flag (2) requires a basis for every price; a *not deliverable* flag (3) requires a concrete delivery-capability story the BOM/labor actually fund; an *internal inconsistency* flag (4) requires the arithmetic, counts, and link budgets to be made to agree.
9. **Write `changelog.md`**: a markdown table mapping each critic note to the change made.

   ```
   | Source                          | Note                                          | Resolution                                  |
   |---------------------------------|-----------------------------------------------|---------------------------------------------|
   | gossamer-lan.1.audit (critical) | Materials subtotal off by $200 (sum mismatch) | Recomputed the subtotal; was a missing line |
   | gossamer-lan.1.audit (major)    | Transceiver qty 14 but topology has 7 spokes  | Corrected to 16 (14 spoke + 2 uplink); added the derivation inline |
   | gossamer-lan.1.review (blocker) | Design proposes surface raceway — violates "no conduit" | Reworked routing to ceiling adhesion; restored constraint satisfaction |
   | gossamer-lan.1.review (major)   | Deliverability story is a contractor phone number | Added the fiber-workshop subsection (tools + practice spool) |
   ```

   For deliberate non-resolutions (e.g., a critic suggested a change the reviser disagrees with), include them with `Resolution: declined — <one-line reason>`. The next critic pass can override or accept the reviser's judgment.
10. **Update `_progress.json`**: `phases.revise.state = done`, `phases.revise.completed = <ISO>`.
11. **Report**: print the path to the new version dir and a one-line status (e.g., `Revised gossamer-lan.1 → gossamer-lan.2/ (addressed 7 notes incl. 1 audit-critical, declined 1)`).

## Idempotence and resumability

- A completed revision (`revise.state == done` AND `proposal.tex` + `changelog.md` exist) is never re-run.
- A crashed revision is re-runnable after deleting partial output.

## Convergence

After this command produces `<thread>.{N+1}/`, the orchestrator should run BOTH `proposal-review <thread>` AND `proposal-audit <thread>` on the new version (in parallel). The cycle continues until:
- BOTH `verdict.md`s clear (`review.advance: true` ≥35 AND `audit.pass: true`, no critical flags) — thread reaches `READY`/`AUDITED`, OR
- `N+1 > max_iterations` (thread is `BLOCKED` for human review).

## Notes for the reviser agent

- **Do not regress.** If a section scored 5/6 in the prior review, the next version should keep it at ≥5/6. The `changelog.md` is the audit trail proving you did not lose ground while addressing other dimensions.
- **Audit-critical flags trump everything.** A failed BOM subtotal or a link budget that does not close is a worse outcome than declining a stylistic suggestion. Fix the math first.
- **Reconcile the two critics, don't average them.** The reviewer and auditor own different defect classes; a note from one is not softened by a good score from the other. Address both.
- **Declined notes are a feature, not a bug.** Sometimes a critic is wrong. Document the disagreement in `changelog.md` so the next pass can re-evaluate with full context.

## `_progress.json` snippet (revised version dir)

This command writes the version-dir shape documented in `anvil/lib/snippets/progress.md`. The reviser adds a `metadata.revised_from` field naming the parent version (preserved by the shallow-merge rule on subsequent writes):

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

`metadata.revised_from` helps the orchestrator's anomaly detection catch gaps in the version chain. Use ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.
