# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-10-27*

---

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

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

- **#1449**: project_brief: rubric_overrides rejects dim_10 keys (MAX_DIM = 9) and the lenient loader swallows the error, so deck dim 10 waivers silently never apply
- **#1450**: deck-review: no sanctioned re-run path once <thread>.{N}.review/ exists — docs say re-aggregating after sibling critics is appropriate, but step 1 exits early and sidecar stage/replace both refuse

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#1451**: fix(sidecar): add supersede path so deck-review can re-run after sibling critics

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#1396**: paper-review: add a reader-flow lens (define-before-use, one name per concept, body order vs intro roadmap, figure proximity) *(curated)*
- **#1449**: project_brief: rubric_overrides rejects dim_10 keys (MAX_DIM = 9) and the lenient loader swallows the error, so deck dim 10 waivers silently never apply *(curated)*
- **#1450**: deck-review: no sanctioned re-run path once <thread>.{N}.review/ exists — docs say re-aggregating after sibling critics is appropriate, but step 1 exits early and sidecar stage/replace both refuse *(curated)*

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
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 0 |
| Curated | 3 |
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
