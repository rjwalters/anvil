# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-07-31 (Guide triage pass — #824 closed when PR #825 merged; the backlog is now fully empty: no open issues in any state)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No open issues exist to prioritize.

## In Progress (`loom:building`)

*Empty.* #824's fix merged as PR #825 — closed 2026-07-31; see `WORK_LOG.md`.

## Ready for Work (`loom:issue`)

*Empty.* No open issues carry `loom:issue`.

## Blocked (`loom:blocked`)

*Empty.* The three previously-blocked issues (#800, #746, #743) all closed 2026-07-30 when their pending PRs (#805, #761, #763) merged — see `WORK_LOG.md`.

## Triage queue (`loom:triage` / `loom:curating`)

*Empty.* No issues carry `loom:triage` or `loom:curating`.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

**Zero open issues, zero open PRs (excluding this docs PR), as of 2026-07-31.** Issue #824 (`gitignore gap: .loom/.daemon.flags and .loom/runtimes/ cause false-positive dirty-main-worktree detection`) was fixed by PR #825, which merged 2026-07-31 and closed #824. Nothing is ready, building, blocked, or in active triage, and `loom:urgent` stays empty since there is no open work to rank. Next action is whatever the Auditor, a human, or an Architect/Hermit proposal surfaces next — there is no pending Guide triage work.

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
