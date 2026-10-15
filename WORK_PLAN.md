# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-10-15*

---

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

_None._

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#1368**: slides: no import path for a deck authored outside anvil (PDF / Keynote / code-built)
- **#1369**: slides-revise: port memo's operator-directed paths (`--polish` / `--reject`) and record operator overrides so critics stop re-flagging them
- **#1370**: Critics over-apply disclosure and hedging; slides rubric assumes a technical lecture
- **#1371**: Time-budget realism (D8) is scored inconsistently without a rehearsal, and rehearse can't time script-style notes
- **#1372**: Vision critic without an API key: agent-as-VLM works but drifts, and palette_adherence assumes the anvil theme
- **#1373**: slides: BRIEF editorial_overrides so critics report operator-overridden findings as info instead of re-flagging

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#1379**: feat(slides): add slides-import for externally-authored PDF decks

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#1374**: fix(slides): separate on-slide disclosure from provenance and add talk_genre
- **#1375**: feat(slides): add --polish/--reject paths to slides-revise
- **#1376**: fix(vision): add score anchors, palette consistency fallback, agent-as-VLM mode
- **#1377**: feat(slides): add rehearse script mode and cap D8 without timing evidence
- **#1378**: feat(slides): honor BRIEF editorial_overrides in review and vision critics

## Proposed

Issues carrying `loom:curated`.

- **#1368**: slides: no import path for a deck authored outside anvil (PDF / Keynote / code-built) *(curated)*
- **#1369**: slides-revise: port memo's operator-directed paths (`--polish` / `--reject`) and record operator overrides so critics stop re-flagging them *(curated)*
- **#1370**: Critics over-apply disclosure and hedging; slides rubric assumes a technical lecture *(curated)*
- **#1371**: Time-budget realism (D8) is scored inconsistently without a rehearsal, and rehearse can't time script-style notes *(curated)*
- **#1372**: Vision critic without an API key: agent-as-VLM works but drifts, and palette_adherence assumes the anvil theme *(curated)*
- **#1373**: slides: BRIEF editorial_overrides so critics report operator-overridden findings as info instead of re-flagging *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 0 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 6 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 5 |
| Curated | 6 |
| Architect / Hermit proposals | 0 |
| Active epics | 0 |
<!-- guide:plan-body:end -->

## How this file is maintained

The Guide triage agent should refresh this file when:

- A new issue enters `loom:triage` (add to triage queue with notes).
- An issue is promoted to `loom:issue` (move to "Ready for Work").
- A builder claims an issue (`loom:issue` → `loom:building`; move to "In Progress").
- A PR merges and the issue closes (remove from this file; add to `WORK_LOG.md`).
- The operator adds or removes `loom:operator-priority` (Guide only reads it).
- Stale issues need re-prioritization.

If the file is more than a week stale and the open-issues backlog has changed, regenerate from current label state and timestamp with `*Last updated: YYYY-MM-DD*` at the top.
