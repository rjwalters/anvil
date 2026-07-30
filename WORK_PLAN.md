# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-07-30 (Guide triage pass, #809 added — new urgent GraphQL-fallback fix)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

| Issue | Title | Tier |
|---|---|---|
| #809 | curator: blocked-pending-PR guard's marker read is GraphQL-backed — silently bootstrap-reposts when GraphQL quota is exhausted | `tier:maintenance` |
| #800 | vocab_reminder: shipped-default word list unreachable in installed consumer repos (`DEFAULT_WORD_LIST_PATH` dead path) | `tier:goal-supporting` |

#809 is a fresh, curated, dependency-free bug fix: the curator's blocked-pending-PR idempotency guard reads its dedup marker via a GraphQL-backed `gh` call, and when the GraphQL bucket is exhausted (a real, observed condition in this repo — confirmed live during this triage pass, `core: 4999 remaining` vs `graphql: 0`), the failed read is silently treated as "no prior marker," reproducing the exact claim/comment/unclaim churn #785/#796/#798/#802/#804 were built to eliminate. Small, well-scoped REST-fallback fix with a clear acceptance checklist — top priority. #800 carries `loom:urgent` from a prior triage pass and is claimed and building (PR #805 open, Judge-approved, `mergeable_state: clean`) — no triage action needed; work is already in progress. Urgent count: 2/3.

## In Progress (`loom:building`)

| Issue | Title | Tier | Status |
|---|---|---|---|
| #800 | vocab_reminder: shipped-default word list unreachable in installed consumer repos (`DEFAULT_WORD_LIST_PATH` dead path) | `tier:goal-supporting` | PR #805 open (`Closes #800`), Judge-approved (`loom:pr`), `mergeable_state: clean` — awaiting human/Champion merge |
| #806 | curator: unknown `mergeable_state` causes false-positive churn in blocked-pending-PR guard | `tier:maintenance` | Claimed by a Builder; no PR yet as of this pass |

Both checked this pass — claim ages ~1h48m (#800) and ~1h29m (#806), both under the 2h/4h staleness thresholds, so neither is orphaned.

## Ready for Work (`loom:issue`)

| Issue | Title | Tier | Status |
|---|---|---|---|
| #809 | curator: blocked-pending-PR guard's marker read is GraphQL-backed — silently bootstrap-reposts when GraphQL quota is exhausted | `tier:maintenance` | `loom:urgent`, not yet claimed — top pick for next Builder dispatch |

The two remaining open `loom:issue` issues (#746, #743) also carry `loom:blocked` (see below) — each already has a complete, Judge-approved, mergeable PR awaiting human/Champion merge.

## Blocked (`loom:blocked`) — implementation complete, pending merge

| Issue | Title | Tier | Status |
|---|---|---|---|
| #746 | memo-review: version-drift block — no lifecycle phase can see monotonic densification across revise cycles | `tier:goal-supporting` | PR #761 open, `mergeable_state: clean`; blocked 2026-07-29 to prevent duplicate Builder dispatch |
| #743 | Consumer install omits `skills/*/lib/` — SKILL.md's documented render-phase CLI path does not exist | `tier:goal-supporting` | PR #763 open, `mergeable_state: clean`; blocked 2026-07-29 to prevent duplicate Builder dispatch |

**Action needed is a merge, not a Builder dispatch.** Recommend `./.loom/scripts/merge-pr.sh 761`, `763` (Champion/human).

Each carries a documented unblock condition: PR merges → issue auto-closes; PR closes without merging → remove `loom:blocked`, issue re-enters normal triage.

**#802** (blocked-pending-PR guard concurrent-dispatch race) **closed** 2026-07-30 via merged PR #804 — no longer part of the open backlog; see `WORK_LOG.md`.

**#751** (evidence grades leak into reader prose) **closed** 2026-07-30 via merged PR #773 — no longer part of the open backlog; see `WORK_LOG.md`.

**#796** (Curator label-flap bug on #743's blocked-pending-PR re-checks) **closed** 2026-07-30 via merged PR #798 — no longer part of the open backlog; see `WORK_LOG.md`.

**#764** (Tracker: retire local `.claude/commands/loom/sweep.md --claim-owned` patch) has since **closed** (2026-07-29, manual closure — the tracked Loom v0.16.0 upgrade landed the trigger condition) and is no longer part of the open backlog; see `WORK_LOG.md`.

## Triage queue (`loom:triage` / `loom:curating`)

*Empty.* No issues carry `loom:triage` or `loom:curating`.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

Five open issues total as of 2026-07-30: #809 (new, `loom:issue` + `loom:urgent`, unclaimed — top pick for next Builder dispatch); #800 and #806, both `loom:building` and confirmed not orphaned (claim ages ~1h48m and ~1h29m); plus #746 and #743, both `loom:issue` + `loom:blocked`, each with a complete, Judge-approved, mergeable PR (#761 and #763 respectively) awaiting human/Champion merge. #802 closed 2026-07-30 via merged PR #804; #751 closed 2026-07-30 via merged PR #773; #796 closed 2026-07-30 via merged PR #798. Two concurrent needs this pass: **merge open PRs** (#761, #763, #805) to clear the blocked/building backlog, and **dispatch a Builder to #809** (small, well-scoped, dependency-free).

### Recurring themes the next wave of issues will likely touch

Forward-looking signals from `ROADMAP.md` "Near-Term Themes" (dormant until canary friction or a second consumer surfaces):

1. **Per-skill `lib/` extraction → `anvil/lib/`** — trigger is observed duplication, not anticipation.
2. **Per-skill audit-command migrations** to typed `_review.json` (`kind: tool_evidence`).
3. **Memo-side render-gate analog** (markdown-appropriate length proxy + clean-output gate).
4. **Render-gate consumer ergonomics** (per-thread overrides at scale).
5. **Cross-skill lint sharing** (deck/slides `marp_lint` consolidation).
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
