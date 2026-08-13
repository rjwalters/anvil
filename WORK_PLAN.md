# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-13 (Guide triage pass — no new PRs or standalone issue closures since the prior pass: `WORK_LOG.md`'s watermark (PR #1010, issue #876) already covers everything except the self-referential docs PR #1011, and all 47 issues closed since #876 are already logged via their closing PR's `(closes #N)` entry, so `WORK_LOG.md` is unchanged this pass. #1004 moved since the last update: after being unblocked and re-curated, it was reviewed and approved (`loom:issue` restored at 00:13 UTC by Champion/human) and immediately claimed by a Builder (`loom:building` at 00:13, worktree `issue-1004` confirmed live) — moved from "Triage Queue" to "In Progress" below. #1005 stays `loom:blocked`: its dependency #1004 is open (building, not yet closed). No ready/non-building `loom:issue` work exists this pass, so the `loom:urgent` queue stays empty. #997 remains mid-`loom:curating`. The `loom:curated`+`loom:operator-only` issue (#888) and the `loom:operator-only` infra escalation (#918) are unchanged. `loom-recover-orphans` not needed — the one `loom:building` issue (#1004) has a live worktree, not orphaned. No open PRs at all.)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No ready, non-building issue exists this pass to promote — see Backlog state below.

## Ready for Work (`loom:issue`)

*Empty.*

## In Progress (`loom:building`)

- **#1004**: "Generate consumer AGENTS.md entry point and update anvil:help introspection for Claude+Codex parity" (`tier:goal-supporting`, epic-phase of #1000). Unblocked this pass's predecessor round (dependency #1003 closed via PR #1010), re-curated, approved (`loom:issue`), and claimed by a Builder — live worktree at `.loom/worktrees/issue-1004`.

## PRs Awaiting Review (`loom:review-requested`)

*Empty.*

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Curated, Not Yet Claimed (`loom:curated`)

*Empty.* #888 (curated) is listed under the operator-review section below.

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug — a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.

## Blocked (`loom:blocked`)

- **#1005**: "Add cross-runtime (Claude/Codex) parity and upgrade/uninstall ownership tests for Anvil skill registration" (`tier:goal-supporting`, epic-phase of #1000). Depends on #1003 (closed) and #1004 (open, `loom:building`) — stays blocked until #1004 closes.

## Triage Queue (unlabeled / awaiting Curator)

- **#997**: "AI-tell lexicon: add \"load-bearing\"…" carries `loom:curating` — actively being enriched, not yet awaiting Curator pickup.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

- **#1000**: "Make Anvil artifact skills discoverable in Claude and Codex" (`tier:goal-supporting`). 2/4 phases complete: #1002 closed (PR #1008), #1003 closed (PR #1010), #1004 in progress (`loom:building`), #1005 `loom:blocked` (chained on #1004).

## Backlog state

**Six open issues as of 2026-08-13: the #1000 epic and its two still-open phase issues (#1004 now `loom:building`, #1005 blocked on it), #997 (mid-`loom:curating`), and the two unchanged `loom:operator-only` issues (#888, #918).** No ready (`loom:issue`, non-building) issues remain, so no `loom:urgent` promotions this pass. No PRs in the Loom review pipeline, no open PRs at all. The one `loom:building` issue (#1004) has a confirmed live worktree — not orphaned, no `loom-recover-orphans` action needed. No new merged PRs or standalone issue closures since the prior watermark (PR #1010 / issue #876) beyond the phase's own self-referential docs PRs; cross-checked all 47 issues closed since #876 against `WORK_LOG.md` and confirmed every one is already logged via its closing PR's `(closes #N)` entry. Next action: Builder finishes #1004, which unblocks #1005 for the sweep/approval flow; a human or Champion reviews #888's design tradeoffs; #918 awaits a human daemon-recovery run on the affected host.

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
