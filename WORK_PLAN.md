# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-16 (Guide triage pass — a Builder claimed #1133 ("Consolidate 10 duplicate `_parse_frontmatter` test helpers into `anvil/lib/testing.py`", `loom:curated`/`tier:maintenance`) since the prior pass, moving it `loom:issue` → `loom:building`; `loom-recover-orphans` confirms it is legitimately in progress (freshly claimed, well under the 4h stale-building threshold), not orphaned. Otherwise the operator-only backlog is unchanged: the same ten `loom:operator-only` issues (#888, #918, #1069, #1070, #1072, #1073, #1081, #1090, #1103, #1107) remain open, none newly eligible for `loom:urgent`. No open PRs. Incumbent `loom:urgent` set stayed empty (zero eligible candidates) — another quiet tick on that front. `WORK_LOG.md` updated this pass: appended entries for two Auditor-filed guard-telemetry issues closed as not-planned duplicates since the prior write — #1132 (duplicate of #1103's read-only-heredoc sub-pattern) and #1131 (duplicate of #1069's mktemp/rm-scope pattern) — both folded their additional telemetry into a comment on the surviving issue rather than staying open as separate escalations; no new merged PR needed recording (PR #1129 was already captured, and PR #1130 is this role's own prior docs-maintenance PR, correctly excluded). README checked for architectural drift: none found, left untouched. No token-pool pressure signal (`.loom/tokens/.ranking` absent) — proceeded normally.)*

---

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

_None._

## Urgent

Issues flagged as highest priority (`loom:urgent`).

- **#1140**: Consolidate DOC/_SKILL_ROOT-closure and remaining _read(...) test-helper variants into anvil/lib/testing.py

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#1140**: Consolidate DOC/_SKILL_ROOT-closure and remaining _read(...) test-helper variants into anvil/lib/testing.py

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#1142**: refactor(lib): consolidate DOC/_SKILL_ROOT-closure _read test helpers

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#1140**: Consolidate DOC/_SKILL_ROOT-closure and remaining _read(...) test-helper variants into anvil/lib/testing.py *(curated)*
- **#888**: review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

_None._

## Backlog Balance

| Tier | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Urgent | 1 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 1 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 0 |
| Curated | 2 |
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
