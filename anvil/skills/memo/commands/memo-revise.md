---
name: memo-revise
description: Reviser command for the memo skill. Reads the latest version + all critic siblings and produces the next version with a changelog mapping critic notes to revisions.
---

# memo-revise — Reviser

**Role**: reviser.
**Reads**: latest `<thread>.{N}/` and ALL `<thread>.{N}.*/` critic siblings (`.review/`, `.audit/`, `.critic/`, ...).
**Writes**: `<thread>.{N+1}/` containing the revised memo, exhibits, `_progress.json`, and a `changelog.md` mapping critic notes to the changes made.

This command is the canonical "N parallel critics, one reviser" pattern from anvil's design principles. It consumes any number of critic siblings at the current version and produces a single revised version that addresses them.

## Inputs

- **Thread slug** (positional argument).
- **Latest version**: highest `N` with `<thread>.{N}/memo.md`.
- **Critic siblings**: ALL `<thread>.{N}.<critic>/` directories at that `N`. At minimum the `.review/` sibling is required (the reviewer's verdict drives the dimension-by-dimension revision plan). Optional siblings (`.audit/`, `.critic/`, etc.) contribute additional findings.

## Outputs

```
<thread>.{N+1}/
  memo.md            Revised memo body
  exhibits/          Carried over and/or updated exhibits
  changelog.md       Maps each critic note (by sibling + section) to the change made in this revision
  _progress.json     Phase state with revise: done
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/memo.md` AND at least `<thread>.{N}.review/verdict.md`. If no review exists, exit with an error ("no review to revise against; run `memo-review` first").
2. **Resume check**: if `<thread>.{N+1}/_progress.json.revise.state == done` and `memo.md` + `changelog.md` exist, the revision is complete — exit early with a notice.
3. **Iteration cap check**: read `metadata.max_iterations` from `<thread>.{N}/_progress.json` (or `<thread>/.anvil.json` override; default 4). If `N + 1 > max_iterations`, exit with a `BLOCKED` notice — human review required.
4. **Verdict pre-check**: parse `<thread>.{N}.review/verdict.md`. If `advance == true` and there are no critical flags, exit with a notice: the thread is `READY`, no revision needed. (Operator can force-run by deleting the verdict or bumping the iteration manually, but the default is to refuse to revise an already-passing version.)
5. **Initialize `_progress.json`**: write `phases.revise.state = in_progress`, `phases.revise.started = <ISO>`, `metadata.iteration = N+1`, `metadata.max_iterations`.
6. **Read inputs**:
   - Prior version's `memo.md` and `exhibits/`.
   - `<thread>.{N}.review/verdict.md` + `scoring.md` + `comments.md`.
   - Every other `<thread>.{N}.<critic>/` sibling discovered on disk (auditor, secondary critic, etc.).
7. **Build a revision plan**:
   - For each rubric dimension that scored below threshold (or had a critical flag), enumerate the specific changes required to lift the score.
   - For each `comments.md` entry tagged `blocker` or `major`, plan a concrete change.
   - Resolve conflicting feedback between critic siblings explicitly (e.g., reviewer says "more risks," critic says "fewer risks but deeper" — pick a synthesis and note it in the changelog).
8. **Produce `memo.md`** at `<thread>.{N+1}/memo.md`:
   - Address each planned change.
   - Preserve sections that scored well — do not regress on dimensions that already met the standard.
   - Carry over `exhibits/` from the prior version; update or add exhibits as the revision plan requires.
9. **Write `changelog.md`**: a markdown table mapping each critic note to the change made.

   ```
   | Source                       | Note                                | Resolution                          |
   |------------------------------|-------------------------------------|-------------------------------------|
   | acme-seed.1.review (blocker) | TAM figure $40B unsourced           | Cited Gartner 2025 report; verified figure is $38B (corrected) |
   | acme-seed.1.review (major)   | Risk #2 lacks mitigation            | Added 1-paragraph mitigation referencing escrow structure        |
   | acme-seed.1.audit            | Cash burn rate disagrees with deck  | Recomputed from primary deck; updated body and exhibit          |
   ```

   For deliberate non-resolutions (e.g., critic suggested a change the reviser disagrees with), include them with `Resolution: declined — <one-line reason>`. The next reviewer pass can override or accept the reviser's judgment.
10. **Update `_progress.json`**: `phases.revise.state = done`, `phases.revise.completed = <ISO>`.
11. **Report**: print the path to the new version dir and a one-line status (e.g., `Revised acme-seed.1 → acme-seed.2/ (addressed 7 notes, declined 1)`).

## Idempotence and resumability

- A completed revision (`revise.state == done` AND `memo.md` + `changelog.md` exist) is never re-run.
- A crashed revision is re-runnable after deleting partial output.

## Convergence

After this command produces `<thread>.{N+1}/`, the orchestrator should run `memo-review <thread>` on the new version. The cycle continues until:
- `verdict.md` reports `advance: true` (thread reaches `READY`), OR
- `N+1 > max_iterations` (thread is `BLOCKED` for human review).

## Notes for the reviser agent

- **Do not regress.** If a section scored 5/6 in the prior review, the next version should keep it at ≥5/6. The `changelog.md` is the audit trail proving you did not lose ground while addressing other dimensions.
- **Critical flags trump everything.** If any critic sibling raised a critical flag, the revision MUST address it — failing to do so is a worse outcome than declining a stylistic suggestion.
- **Declined notes are a feature, not a bug.** Sometimes the reviewer is wrong. Document the disagreement in `changelog.md` so the next reviewer can re-evaluate with full context.

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
