# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-07-29*

---

## Urgent (Top Priority)

*No issues currently carry the `loom:urgent` label.* The three open `loom:issue` issues (below) each already have a complete, Judge-approved, mergeable PR awaiting human/Champion merge — there is no unbuilt work to prioritize among them. Urgent labeling would misrepresent the queue; see "Backlog state" below.

## In Progress (`loom:building`)

- **#779** — `test(memo): stale weasyprint-detection test fails when binary is not on PATH`. Small, mechanical bug fix (a stale test never updated for #308/#311's two-stage `check_weasyprint_available()`). Curated `tier:maintenance`, promoted, and claimed by a Builder on 2026-07-29 shortly after this plan was drafted.

## Ready for Work (`loom:issue`) — implementation complete, pending merge

| Issue | Title | Tier | Status |
|---|---|---|---|
| #746 | memo-review: version-drift block — no lifecycle phase can see monotonic densification across revise cycles | `tier:goal-supporting` | PR #761 open, `loom:pr` (Judge-approved, mergeable) |
| #743 | Consumer install omits `skills/*/lib/` — SKILL.md's documented render-phase CLI path does not exist | `tier:goal-supporting`, `loom:curated` | PR #763 open, `loom:pr` (Judge-approved, mergeable) |
| #751 | evidence grades leak into reader prose — preservation contract needs a rendering rule | `tier:goal-supporting`, `loom:blocked` (dependency: PR #773 unmerged) | PR #773 open, `loom:pr` (Judge-approved, mergeable) |

**Action needed is a merge, not a Builder dispatch.** Recommend `./.loom/scripts/merge-pr.sh 761`, `763`, `773` (Champion/human).

## Blocked (`loom:blocked`)

- **#764** — Tracker: retire local `.claude/commands/loom/sweep.md --claim-owned` patch once Loom is upgraded. The 2026-07-29 Loom v0.16.0 upgrade (PR — commit `bf47bcb`) landed the trigger condition; Curator verified ACs 1–2 (patch superseded, upstream `sweep.md` natively handles `--claim-owned`). AC 3 (one daemon-dispatched sweep completing end-to-end post-upgrade) is still unobserved as of PR #777/#778 — `sweeps.json` is empty. Stays blocked pending that observation; not a dependency-resolution unblock.
- **#751** — see table above; blocked on PR #773 merging (self-referential — the fix is already built).

## Triage queue (`loom:triage` / `loom:curating`)

*Empty.* #779 completed curation and was claimed while this plan was in review — see "In Progress" above.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

Five open issues total as of 2026-07-29 (down from a much larger in-flight set worked through the 2026-07-03 → 2026-07-29 window — see `WORK_LOG.md` for the ~85-PR merge record since the last Work Plan refresh). The backlog is effectively **drained of unbuilt ready work**: every `loom:issue` issue already has a complete, Judge-approved PR; the only blocked issue with real dependency content (#751) is blocked on its own already-built PR merging; #764 is a self-tracking migration-verification issue waiting on one live daemon sweep cycle, not on other issues. The rate-limiting step across the board is **merging open PRs #761 / #763 / #773**, not Builder dispatch.

### Recurring themes the next wave of issues will likely touch

Forward-looking signals from `ROADMAP.md` "Near-Term Themes" (dormant until canary friction or a second consumer surfaces):

1. **Per-skill `lib/` extraction → `anvil/lib/`** — trigger is observed duplication, not anticipation.
2. **Per-skill audit-command migrations** to typed `_review.json` (`kind: tool_evidence`).
3. **Memo-side render-gate analog** (markdown-appropriate length proxy + clean-output gate).
4. **Render-gate consumer ergonomics** (per-thread overrides at scale).
5. **Cross-skill lint sharing** (deck/slides `marp_lint` consolidation).

## How this file is maintained

The Guide triage agent should refresh this file when:

- A new issue enters `loom:triage` (add to triage queue with notes).
- An issue is promoted to `loom:issue` (move to "Ready for Work").
- A builder claims an issue (`loom:issue` → `loom:building`; move to "In Progress").
- A PR merges and the issue closes (remove from this file; add to `WORK_LOG.md`).
- `loom:urgent` is added or removed.
- Stale issues need re-prioritization.

If the file is more than a week stale and the open-issues backlog has changed, regenerate from current label state and timestamp with `*Last updated: YYYY-MM-DD*` at the top.
