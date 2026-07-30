# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-07-30 (Guide triage pass)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

| Issue | Title | Tier |
|---|---|---|
| #800 | vocab_reminder: shipped-default word list unreachable in installed consumer repos (`DEFAULT_WORD_LIST_PATH` dead path) | `tier:goal-supporting` |

#800 is the only ready, unblocked issue in the backlog — marked urgent to fast-track the only available Builder pickup. #796 (the Curator label-flap bug that previously held the only `loom:urgent`) closed 2026-07-30 via merged PR #798 — see `WORK_LOG.md`.

## In Progress (`loom:building`)

*Empty.*

## Ready for Work (`loom:issue`)

| Issue | Title | Tier |
|---|---|---|
| #800 | vocab_reminder: shipped-default word list unreachable in installed consumer repos (`DEFAULT_WORD_LIST_PATH` dead path) | `tier:goal-supporting` |

Filed by `loom:auditor` from a main-branch audit; already curated with root cause, affected files, and test plan. The other two open `loom:issue` issues also carry `loom:blocked` (see below) — each already has a complete, Judge-approved, mergeable PR awaiting human/Champion merge.

## Blocked (`loom:blocked`) — implementation complete, pending merge

| Issue | Title | Tier | Status |
|---|---|---|---|
| #746 | memo-review: version-drift block — no lifecycle phase can see monotonic densification across revise cycles | `tier:goal-supporting` | PR #761 open, `mergeable_state: clean`; blocked 2026-07-29 to prevent duplicate Builder dispatch |
| #743 | Consumer install omits `skills/*/lib/` — SKILL.md's documented render-phase CLI path does not exist | `tier:goal-supporting` | PR #763 open, `mergeable_state: clean`; blocked 2026-07-29 to prevent duplicate Builder dispatch |

**Action needed is a merge, not a Builder dispatch.** Recommend `./.loom/scripts/merge-pr.sh 761`, `763` (Champion/human).

Each carries a documented unblock condition: PR merges → issue auto-closes; PR closes without merging → remove `loom:blocked`, issue re-enters normal triage.

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

Three open issues total as of 2026-07-30: #800 (ready, `loom:urgent`), plus #746 and #743, both `loom:issue` + `loom:blocked`, each with a complete, Judge-approved, mergeable PR (#761 and #763 respectively) awaiting human/Champion merge. #751 closed 2026-07-30 via merged PR #773; #796 closed 2026-07-30 via merged PR #798. The rate-limiting step for #746/#743 is **merging #761/#763**, not Builder dispatch or triage prioritization. #800 is a fresh `loom:auditor`-filed bug and the only unblocked ready issue, so it now carries the sole `loom:urgent`.

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
