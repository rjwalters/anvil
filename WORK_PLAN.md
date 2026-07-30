# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-07-30 (Guide triage pass — shifted `loom:urgent` from #800 to #743: oldest open issue, broadest blast radius (every installed skill's render-phase CLI path), and its PR #763 is the smallest/lowest-risk of the three stalled PRs)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

| Issue | Title | Tier |
|---|---|---|
| #743 | Consumer install omits `skills/*/lib/` — SKILL.md's documented render-phase CLI path does not exist | `tier:goal-supporting` |

Urgent count: 1/3. All three open issues remain equally blocked-pending-merge (implementation complete, awaiting a human/Champion merge decision); #743 is flagged as the merge-priority signal for humans reviewing the stalled-PR queue — oldest issue, broadest impact (affects every installed skill, not one), and lowest-risk fix (278 lines).

## In Progress (`loom:building`)

*Empty.* No issue is currently claimed by a Builder.

## Ready for Work (`loom:issue`)

*Empty.* No unclaimed `loom:issue` work is available this pass — all three open `loom:issue` issues (#800, #746, #743) also carry `loom:blocked` (see below).

## Blocked (`loom:blocked`) — implementation complete, pending merge

| Issue | Title | Tier | Status |
|---|---|---|---|
| #800 | vocab_reminder: shipped-default word list unreachable in installed consumer repos (`DEFAULT_WORD_LIST_PATH` dead path) | `tier:goal-supporting` | PR #805 open, `mergeable_state: clean`, 316 lines (over the 200-line auto-merge limit; size-notice marker posted) |
| #746 | memo-review: version-drift block — no lifecycle phase can see monotonic densification across revise cycles | `tier:goal-supporting` | PR #761 open, `mergeable_state: clean`, 1268 lines (over the 200-line auto-merge limit; size-notice marker posted) |
| #743 | Consumer install omits `skills/*/lib/` — SKILL.md's documented render-phase CLI path does not exist | `tier:goal-supporting` | PR #763 open, `mergeable_state: clean`, 287 lines (over the 200-line auto-merge limit; size-notice marker posted) |

**Action needed is a human merge decision, not a Builder dispatch.** All three PRs are Judge-approved (`loom:pr`) and clean, but each exceeds Champion's 200-line auto-merge limit with no `loom:auto-merge-ok` override yet. Recommend a human either adds `loom:auto-merge-ok` to #805/#761/#763, or splits them.

Each carries a documented unblock condition: PR merges → issue auto-closes; PR closes without merging → remove `loom:blocked`, issue re-enters normal triage.

**#806** (curator unknown-`mergeable_state` churn) **closed** 2026-07-30 via merged PR #814 — no longer part of the open backlog; see `WORK_LOG.md`.

**#809** (curator blocked-pending-PR guard's GraphQL-backed marker read) **closed** 2026-07-30 via merged PR #812 — no longer part of the open backlog; see `WORK_LOG.md`.

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

Three open issues total as of 2026-07-30: #800, #746, and #743 are all `loom:issue` + `loom:blocked`, each with a complete, Judge-approved, mergeable PR (#805, #761, #763 respectively) stalled above Champion's 200-line auto-merge limit and awaiting a human merge decision. #806 closed 2026-07-30 via merged PR #814; #809 closed via merged PR #812; #802 closed via merged PR #804; #751 closed via merged PR #773; #796 closed via merged PR #798. No unclaimed ready work remains and nothing is currently `loom:building`. The one concurrent need this pass: **a human adds `loom:auto-merge-ok` (or splits) PRs #805/#761/#763** to clear the entire open backlog.

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
