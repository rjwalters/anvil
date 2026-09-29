# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-09-29 (Guide triage pass — the backlog is essentially empty: zero open issues other than Champion's auto-maintained `loom:blocked` merge-risk-hold digest (#1224, not a work item, never curated/built/promoted), and the only open PRs are unlabeled Dependabot/Renovate dependency-bump PRs outside the loom review pipeline. `#888` (previously listed here as `loom:curated`) closed 2026-09-15 via PR #1317/#1316, so "Proposed" is now empty. This pass also migrated the section set from the retired `loom:urgent` label to `loom:operator-priority` (#9244) — Guide never applies or removes that label, only reads it; it stayed empty this tick. `WORK_LOG.md` was rewritten this pass after a large gap: the prior committed entry was #1142 (2026-08-17), 18 merged PRs and 165 closed issues had accumulated unrecorded since, well above the 5-entry minimum — written immediately rather than deferred. No token-pool pressure signal (`.loom/tokens/.ranking` absent) — proceeded normally.)*

---

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

_None._

## Operator Priority

Issues the operator starred (`loom:operator-priority`); land these first.

_None._

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

_None._

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

_None._

## Proposed (Architect / Hermit)

_None._

## Epics

_None._

## Backlog Balance

| Tier | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Operator priority | 0 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 0 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 0 |
| Architect / Hermit proposals | 0 |
| Active epics | 0 |
<!-- guide:plan-body:end -->

## How this file is maintained

The Guide triage agent should refresh this file when:

- A new issue enters `loom:triage` (add to triage queue with notes).
- An issue is promoted to `loom:issue` (move to "Ready for Work").
- A builder claims an issue (`loom:issue` → `loom:building`; move to "In Progress").
- A PR merges and the issue closes (remove from this file; add to `WORK_LOG.md`).
- `loom:urgent` is added or removed.
- Stale issues need re-prioritization.

If the file is more than a week stale and the open-issues backlog has changed, regenerate from current label state and timestamp with `*Last updated: YYYY-MM-DD*` at the top.
