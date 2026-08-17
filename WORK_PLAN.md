# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-17 (Guide triage pass — #1140 (Consolidate DOC/_SKILL_ROOT-closure and remaining `_read(...)` test-helper variants into `anvil/lib/testing.py`) completed its full lifecycle since the prior pass: PR #1142 merged, closing #1140, so it drops out of Urgent/In Progress/PRs Awaiting Review/Proposed below. Otherwise the operator-only backlog is unchanged: the same ten `loom:operator-only` issues (#888, #918, #1069, #1070, #1072, #1073, #1081, #1090, #1103, #1107) remain open, none newly eligible for `loom:urgent`. No open PRs, no `loom:issue`/`loom:building`/`loom:blocked`/`loom:epic` issues. Incumbent `loom:urgent` set stayed empty (zero eligible candidates) — another quiet tick on that front. `WORK_LOG.md` NOT rewritten this pass: only one new merged PR (#1146, closing #1144) since the last write, below the 5-entry `LOOM_WORK_LOG_MIN_ENTRIES` threshold, and only ~4 minutes since WORK_LOG.md was last written (well under the 30-minute debounce) — batched for a later tick. README checked for architectural drift: none found, left untouched. No token-pool pressure signal (`.loom/tokens/.ranking` absent) — proceeded normally.)*

---

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

_None._

## Urgent

Issues flagged as highest priority (`loom:urgent`).

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

- **#888**: review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

_None._

## Backlog Balance

| Tier | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Urgent | 0 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 0 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 1 |
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
