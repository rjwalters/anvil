# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-07-30 (Guide triage pass)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*No issues currently carry the `loom:urgent` label.* The three open `loom:issue` issues (below) each already have a complete, Judge-approved, mergeable PR awaiting human/Champion merge — there is no unbuilt work to prioritize among them. Urgent labeling would misrepresent the queue; see "Backlog state" below.

## In Progress (`loom:building`)

*Empty.* #788 (the size-limit idempotency-guard follow-up) closed via PR #791 — no issue currently carries `loom:building`.

## Ready for Work (`loom:issue`)

*Empty.* All three open `loom:issue` issues still also carry `loom:blocked` (see below) — each already has a complete, Judge-approved, mergeable PR awaiting human/Champion merge, so there is no unbuilt ready work to dispatch a Builder onto.

## Blocked (`loom:blocked`) — implementation complete, pending merge

| Issue | Title | Tier | Status |
|---|---|---|---|
| #746 | memo-review: version-drift block — no lifecycle phase can see monotonic densification across revise cycles | `tier:goal-supporting` | PR #761 open, `mergeable_state: clean`; blocked 2026-07-29 to prevent duplicate Builder dispatch |
| #743 | Consumer install omits `skills/*/lib/` — SKILL.md's documented render-phase CLI path does not exist | `tier:goal-supporting` | PR #763 open, `mergeable_state: clean`; blocked 2026-07-29 to prevent duplicate Builder dispatch. Also still carries `loom:curating` (Curator re-check pass) |
| #751 | evidence grades leak into reader prose — preservation contract needs a rendering rule | `tier:goal-supporting` | PR #773 open, `mergeable_state: dirty` — needs a rebase before merge |

**Action needed is a merge, not a Builder dispatch.** Recommend `./.loom/scripts/merge-pr.sh 761`, `763`, `773` (Champion/human); #773 needs a rebase first.

Each of the three carries a documented unblock condition: PR merges → issue auto-closes; PR closes without merging → remove `loom:blocked`, issue re-enters normal triage.

**#764** (Tracker: retire local `.claude/commands/loom/sweep.md --claim-owned` patch) has since **closed** (2026-07-29, manual closure — the tracked Loom v0.16.0 upgrade landed the trigger condition) and is no longer part of the open backlog; see `WORK_LOG.md`.

## Triage queue (`loom:triage` / `loom:curating`)

*No new issues in `loom:triage`.* #743 (listed above under Blocked) still carries a `loom:curating` claim from Curator's standing re-check pass on the #763 blocked-pending-PR condition — not new triage work.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

Three open `loom:issue` issues total as of 2026-07-30, all blocked (#746, #743, #751), each with a complete, Judge-approved, mergeable PR — #761, #763, #773 respectively — awaiting human/Champion merge. #788 (the prior "In Progress" entry) closed 2026-07-30 via PR #791. The rate-limiting step for the blocked trio is **merging those three PRs**, not Builder dispatch or triage prioritization. PR #773 (closes #751) still shows a `dirty` mergeable_state (merge conflict with `main`) — it will need a rebase before it can merge, unlike #761/#763 which are clean. With zero unblocked *ready* issues, the `loom:urgent` queue is correctly empty.

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
