# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-11 (Guide triage pass — #934 moved from curating to `loom:building` and its PR #936 opened with `loom:review-requested`; no `loom:issue`/`loom:blocked`/`loom:epic` issues open; PR #902, a human-authored tool-currency chore, is open outside the Loom label pipeline)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No open issues carry `loom:issue` — there is no unclaimed ready work for `loom:urgent` to direct a Builder toward. #888 and #918 are `loom:operator-only` and not eligible for `loom:urgent` (see below).

## In Progress (`loom:building`)

*Empty.* Both issues that were in progress as of the previous pass shipped: #933 merged via PR #939 ("fix(memoir): let the final revision under max_iterations get a critic pass") and #934 merged via PR #936 ("fix(provenance-anchor): parse every claim table, not just the first") — both closed 2026-08-11; see `WORK_LOG.md`.

## Ready for Work (`loom:issue`)

*Empty.* No open issues carry `loom:issue`.

## PRs Awaiting Review (`loom:review-requested`)

*Empty.* PR #936 (closes #934) merged 2026-08-11.

One PR is open outside the Loom label pipeline: **#902** "chore: update Repo Skills 0.7.0 → 0.8.1" — opened directly by the repo owner (no labels), a tool-currency bump not routed through Curator/Builder. Per `CLAUDE.md`'s guidance on small mechanical changes, this class of PR doesn't require the full Loom review cycle; it awaits a direct human merge decision, not Judge/Champion action.

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug: a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.

## Blocked (`loom:blocked`)

*Empty.* The three previously-blocked issues (#800, #746, #743) all closed 2026-07-30 when their pending PRs (#805, #761, #763) merged — see `WORK_LOG.md`.

## Triage queue (`loom:triage` / `loom:curating`)

*Empty.*

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

**Two open issues as of 2026-08-11: #888 (curated + `loom:operator-only`, awaiting human/Champion design review) and #918 (`loom:operator-only` + `loom:operator-mechanical`, loom-daemon-down watchdog escalation).** The two issues that were in progress last pass (#933, #934) both shipped this pass via PR #939 and PR #936 respectively. One open PR outside the Loom pipeline: #902 (unlabeled, human-authored tool bump), awaiting a direct human merge decision. No orphaned `loom:building` issues (`loom-recover-orphans --verbose` reports none), no stale `loom:blocked` issues, no open epics. `loom:urgent` stays empty — no open issue carries `loom:issue`, and the Guide never adds `loom:issue` (that's human/Champion approval, not triage). Next action: a human runs the daemon-recovery command for #918, and a human or Champion reviews #888's design tradeoffs; the backlog otherwise has no queued work for a Builder to pick up.

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
