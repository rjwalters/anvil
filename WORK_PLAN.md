# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-13 (Guide triage pass — #1005's dependencies (#1003, #1004) were both already closed at the start of this pass, so #1005 (the #1000 epic's last phase, cross-runtime parity/ownership tests) was the only ready, non-building `loom:issue` in the queue; promoted to `loom:urgent`. Mid-pass, a Builder claimed #1005 for `loom:building` — leave it, work is already happening (`loom:urgent` stays; not removed on building per Guide policy). Three more issues (#1016, #1017, #1018) also moved to `loom:building` during this pass, so "In Progress" now lists four. `loom-recover-orphans --verbose` found no orphaned tasks; the sole flagged claim (#1016, 2 min old) was well inside the 4h staleness threshold. `check-duplicate.sh --include-merged-prs` on #1005 found no real duplicate (only self-match + its own already-closed epic siblings #1002-#1004). Verified all PRs merged since the last pass (#1014, #1010, #1008, #1006, #1001) correctly closed their linked issues — no orphaned closures. `WORK_LOG.md`/`WORK_PLAN.md` watermarks: no new PRs merged above PR #1014 (this pass's own `docs:` PRs excluded); all 48 issues closed above issue #876 are already covered via their closing PR's `(closes #N)` WORK_LOG entry, so `WORK_LOG.md` needed no new entries this pass — only `WORK_PLAN.md` regenerated from current label state below.)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

- **#1005**: "Add cross-runtime (Claude/Codex) parity and upgrade/uninstall ownership tests for Anvil skill registration" (`tier:goal-supporting`, epic-phase of #1000). Promoted this pass — last phase of the #1000 epic, dependencies #1003/#1004 both closed. Now `loom:building` (claimed shortly after promotion); left alone per policy.

## Ready for Work (`loom:issue`, non-building)

*Empty.* #1005 and #1016 (the two open `loom:issue` issues) are both now `loom:building` — see In Progress below.

## In Progress (`loom:building`)

- **#1018**: "evidence_drift: float-precision false positive on manually-recorded snapshots — compare mtimes with tolerance" (`tier:goal-supporting`)
- **#1017**: "No sanctioned binary/bulk asset channel when consumer hooks block Bash writes (figure carry-forward, compile logs, detector sidecars)" (`tier:goal-supporting`)
- **#1016**: "slides-rehearse: timing heuristic saturates on script-style notes — recognize a Cues section, and the 90s base alone fails short slots" (`tier:goal-supporting`)
- **#1005**: "Add cross-runtime (Claude/Codex) parity and upgrade/uninstall ownership tests for Anvil skill registration" (`tier:goal-supporting`, epic-phase of #1000, `loom:urgent`)

## PRs Awaiting Review (`loom:review-requested`)

*Empty.*

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.* No open PRs at all this pass.

## Curated, Not Yet Claimed (`loom:curated`)

*Empty.* All currently-`loom:curated` issues are either `loom:building` (#1005, #1016, #1017, #1018) or `loom:operator-only` (#888, listed below).

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug — a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.

## Blocked (`loom:blocked`)

*Empty.*

## Triage Queue (unlabeled / awaiting Curator)

- **#997**: "AI-tell lexicon: add \"load-bearing\" (structural-importance announcement class) — and sweep it from anvil's own shipped prose" carries `loom:curating` — actively being enriched, not yet awaiting Curator pickup.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

- **#1000**: "Make Anvil artifact skills discoverable in Claude and Codex" (`tier:goal-supporting`). Install-side work complete (#1002 closed via PR #1008, #1003 closed via PR #1010, #1004 closed via PR #1014); the fourth and last phase, #1005 (cross-runtime parity/ownership tests), is now `loom:building` — epic closes once #1005 merges.

## Backlog state

**Eight open issues as of 2026-08-13: the #1000 epic, its four `loom:building` phase/friction issues (#1005, #1016, #1017, #1018), #997 (mid-`loom:curating`), and the two unchanged `loom:operator-only` issues (#888, #918).** No ready (`loom:issue`, non-building) issues remain this pass — everything eligible is already claimed — so no further `loom:urgent` promotions were needed beyond #1005. No PRs in the Loom review pipeline, no open PRs at all. `loom-recover-orphans --verbose` confirmed no orphaned tasks. Next action: Builders land #1005/#1016/#1017/#1018; a human or Champion reviews #888's design tradeoffs; #918 awaits a human daemon-recovery run on the affected host.

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
