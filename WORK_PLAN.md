# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-13 (Guide triage pass — three issues from the previous pass's "In Progress" list landed and closed during this pass: #1018 via PR #1021, #1016 via PR #1019, #1017 via PR #1022 (all three logged in `WORK_LOG.md` this pass). #1005 (the #1000 epic's last phase) remains `loom:building` + `loom:urgent` from the prior promotion — left alone per policy — and now has an open PR (#1023, `loom:reviewing`) awaiting Judge. #997 is also `loom:building` (previously mis-recorded here as `loom:curating`; corrected). No ready (`loom:issue`, non-building) issues exist, so no new `loom:urgent` promotions were needed or made — #1005 remains the sole urgent issue. `loom-recover-orphans --verbose` found no orphaned tasks. No `loom:blocked` issues to check for unblocking. Epic #1000 is one merged PR away from closing (#1023 pending Judge review). `WORK_LOG.md` gained three new entries (PRs #1022, #1021, #1019); watermark PRs below #1014 remain unchanged from the prior pass.)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

- **#1005**: "Add cross-runtime (Claude/Codex) parity and upgrade/uninstall ownership tests for Anvil skill registration" (`tier:goal-supporting`, epic-phase of #1000). Promoted this pass — last phase of the #1000 epic, dependencies #1003/#1004 both closed. Now `loom:building` (claimed shortly after promotion); left alone per policy.

## Ready for Work (`loom:issue`, non-building)

*Empty.* #1005 (the only open `loom:issue` issue) is `loom:building` — see In Progress below.

## In Progress (`loom:building`)

- **#1005**: "Add cross-runtime (Claude/Codex) parity and upgrade/uninstall ownership tests for Anvil skill registration" (`tier:goal-supporting`, epic-phase of #1000, `loom:urgent`) — PR #1023 open and under Judge review
- **#997**: "AI-tell lexicon: add \"load-bearing\" (structural-importance announcement class) — and sweep it from anvil's own shipped prose" (`tier:goal-supporting`)

## PRs Awaiting Review (`loom:review-requested`)

- **#1023**: "test(install): add cross-runtime (Claude/Codex) parity and upgrade/uninstall ownership coverage" — implements #1005; `loom:reviewing` (Judge actively reviewing)

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.* No open PRs at all this pass.

## Curated, Not Yet Claimed (`loom:curated`)

*Empty.* All currently-`loom:curated` issues are either `loom:building` (#1005, #997) or `loom:operator-only` (#888, listed below).

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug — a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.

## Blocked (`loom:blocked`)

*Empty.*

## Triage Queue (unlabeled / awaiting Curator)

*Empty.*

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

- **#1000**: "Make Anvil artifact skills discoverable in Claude and Codex" (`tier:goal-supporting`). Install-side work complete (#1002 closed via PR #1008, #1003 closed via PR #1010, #1004 closed via PR #1014); the fourth and last phase, #1005 (cross-runtime parity/ownership tests), is `loom:building` with PR #1023 open under Judge review — epic closes once #1023 merges.

## Backlog state

**Five open issues as of 2026-08-13: the #1000 epic, its two `loom:building` issues (#1005, #997), and the two unchanged `loom:operator-only` issues (#888, #918).** Three friction issues from the prior pass (#1016, #1017, #1018) landed and closed during this pass. No ready (`loom:issue`, non-building) issues remain, so no further `loom:urgent` promotions were needed or made beyond the standing #1005. One PR (#1023) is in the Judge review pipeline. `loom-recover-orphans --verbose` confirmed no orphaned tasks. Next action: Judge reviews #1023 (closing out the #1000 epic on merge); a Builder lands #997; a human or Champion reviews #888's design tradeoffs; #918 awaits a human daemon-recovery run on the affected host.

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
