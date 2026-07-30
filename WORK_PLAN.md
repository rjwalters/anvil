# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-07-30 (Guide triage pass — the three previously-blocked PRs (#805/#763/#761) all merged, closing #800/#743/#746; the open backlog is now empty)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No open issues exist to prioritize.

## In Progress (`loom:building`)

*Empty.* No issue is currently claimed by a Builder.

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

**Zero open issues and zero open PRs as of 2026-07-30.** The last three blocked-pending-merge issues (#800, #746, #743) closed when their Judge-approved PRs (#805, #761, #763) merged, clearing the size-limit-stalled queue that had persisted for most of 2026-07-30. Nothing is ready, building, blocked, or in triage. The backlog is fully drained — next action is filing new issues (via `anvil:project-scout`, canary friction reports, or direct proposals), not triaging existing ones.

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
