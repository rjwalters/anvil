# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-13 (Guide triage pass — PR #1014 merged mid-pass, closing #1004 ("Generate consumer AGENTS.md entry point and update anvil:help introspection for Claude+Codex parity"); this completes the #1000 epic's install-side work (#1002, #1003, #1004 all closed). That resolved #1005's last open dependency, so #1005 was unblocked: `has_superseding_block` found no linked PR, and `was_previously_approved` found `loom:issue` never in its label history (it was Curator-blocked pre-approval), so per the label-gate policy `loom:blocked` was removed WITHOUT restoring `loom:issue` — #1005 re-enters the curation/approval flow and moves from "Blocked" to "Triage Queue" below. `WORK_LOG.md` gets one new entry (PR #1014); its watermark (PR #1010, issue #876) otherwise still covers everything else, including all issues closed since #876 via their closing PR's `(closes #N)` entry. No ready/non-building `loom:issue` work exists this pass, so the `loom:urgent` queue stays empty. #997 remains mid-`loom:curating`. The `loom:curated`+`loom:operator-only` issue (#888) and the `loom:operator-only` infra escalation (#918) are unchanged. `loom-recover-orphans` reported no orphaned tasks (`loom:building` queue was empty by the time this ran). No open PRs remain.)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No ready, non-building issue exists this pass to promote — see Backlog state below.

## Ready for Work (`loom:issue`)

*Empty.*

## In Progress (`loom:building`)

*Empty.* #1004 closed this pass (PR #1014, merged 2026-08-13T00:36:15Z).

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

*Empty.* #1005 unblocked this pass (see Triage Queue below).

## Triage Queue (unlabeled / awaiting Curator)

- **#1005**: "Add cross-runtime (Claude/Codex) parity and upgrade/uninstall ownership tests for Anvil skill registration" (`loom:triage`, `tier:goal-supporting`, epic-phase of #1000). Unblocked this pass — both dependencies (#1003, #1004) are now closed. Never carried `loom:issue` before being blocked, so it re-enters at the curation stage rather than being restored straight to `loom:issue`; awaiting Curator pickup.
- **#997**: "AI-tell lexicon: add \"load-bearing\"…" carries `loom:curating` — actively being enriched, not yet awaiting Curator pickup.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

- **#1000**: "Make Anvil artifact skills discoverable in Claude and Codex" (`tier:goal-supporting`). 3/4 phases complete: #1002 closed (PR #1008), #1003 closed (PR #1010), #1004 closed (PR #1014), #1005 unblocked and awaiting curation (last phase).

## Backlog state

**Five open issues as of 2026-08-13: the #1000 epic and its one remaining open phase issue (#1005, unblocked and back at `loom:triage`), #997 (mid-`loom:curating`), and the two unchanged `loom:operator-only` issues (#888, #918).** No ready (`loom:issue`, non-building) issues remain, so no `loom:urgent` promotions this pass. No PRs in the Loom review pipeline, no open PRs at all (PR #1014 merged mid-pass). `loom-recover-orphans --verbose` confirmed no orphaned tasks. Next action: Curator picks up #1005 (the epic's last phase); a human or Champion reviews #888's design tradeoffs; #918 awaits a human daemon-recovery run on the affected host.

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
