# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-12 (Guide triage pass — `WORK_LOG.md` gained two entries above the prior #993 high-water mark: PR #1006 (closes #999) and PR #1001 (closes #998); both referenced issues were correctly closed via their PR, no orphans found. A new epic, #1000 ("Make Anvil artifact skills discoverable in Claude and Codex"), appeared with four `loom:epic-phase` children (#1002, #1003, #1004, #1005); #1002 was the only ready, non-building issue this pass and was marked `loom:urgent` as the root of the chain (#1002 → #1003 → #1004 → #1005) — it was claimed by a Builder (`loom:building`) within the same pass. #1003/#1004/#1005 correctly remain `loom:blocked` on their unresolved dependencies (no superseding block, nothing to unblock). #997 is mid-`loom:curating`. The two `loom:operator-only` issues (#888, #918) are unchanged. No open PRs, no `loom:review-requested`/`loom:pr` items, no outstanding Architect/Hermit proposals.)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

- **#1002**: "Research and verify Codex CLI skill/plugin discovery contract for the Anvil adapter" (`tier:goal-supporting`). Marked `loom:urgent` this pass as the sole ready issue and the root of the #1000 epic's dependency chain (#1002 → #1003 → #1004 → #1005); claimed by a Builder within the same pass (now also `loom:building`).

## Ready for Work (`loom:issue`)

*Empty.*

## In Progress (`loom:building`)

- **#1002**: "Research and verify Codex CLI skill/plugin discovery contract for the Anvil adapter" (`tier:goal-supporting`). Claimed by a Builder this pass; #1003/#1004/#1005 remain blocked until it lands.

## PRs Awaiting Review (`loom:review-requested`)

*Empty.*

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Curated, Not Yet Claimed (`loom:curated`)

*Empty.* #1002 (curated) is listed under In Progress above, now `loom:building`.

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug — a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.

## Blocked (`loom:blocked`)

- **#1003**: "Emit Codex skill/plugin registration during install-anvil.sh install/upgrade/uninstall" (`tier:goal-supporting`, epic-phase of #1000). Depends on #1002 (open, `loom:building`) — stays blocked until it closes.
- **#1004**: "Generate consumer AGENTS.md entry point and update anvil:help introspection for Claude+Codex parity" (`tier:goal-supporting`, epic-phase of #1000). Depends on #1003 (open, blocked) — stays blocked.
- **#1005**: "Add cross-runtime (Claude/Codex) parity and upgrade/uninstall ownership tests for Anvil skill registration" (`tier:goal-supporting`, epic-phase of #1000). Depends on #1003 and #1004 (both open, blocked) — stays blocked.

## Triage Queue (unlabeled / awaiting Curator)

*Empty.* #997 ("AI-tell lexicon: add \"load-bearing\"…") carries `loom:curating` — actively being enriched, not yet awaiting Curator pickup.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

- **#1000**: "Make Anvil artifact skills discoverable in Claude and Codex" (`tier:goal-supporting`). 0/4 phases complete: #1002 (`loom:building`), #1003/#1004/#1005 (`loom:blocked`, chained on #1002 → #1003 → #1004).

## Backlog state

**Eight open issues as of 2026-08-12: the new #1000 epic and its four phase issues (#1002 building, #1003/#1004/#1005 blocked on the chain), #997 (mid-`loom:curating`), and the two unchanged `loom:operator-only` issues (#888, #918).** No ready (`loom:issue`) issues remain — #1002 was promoted to `loom:urgent` and claimed by a Builder within this pass. No PRs in the Loom review pipeline, no open PRs at all. `loom-recover-orphans --verbose` found no orphaned `loom:building` claims. Recently-merged PRs (#1001 closes #998, #1006 closes #999) both correctly closed their linked issues — no orphaned closures found. Next action: Builder finishes #1002, which unblocks #1003; a human or Champion reviews #888's design tradeoffs; #918 awaits a human daemon-recovery run on the affected host.

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
