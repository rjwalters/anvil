# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-11 (Guide triage pass — #958 and #965, the last two issues carrying `loom:building`, both shipped: #958 via PR #975 (opt-in `ip-search` pre-search wiring), #965 via PR #973 (sanctioned resolution for singleton-class overflow errors). Both issues are now closed and both PRs merged. The backlog is now fully quiescent: zero issues carry `loom:issue` / `loom:urgent` / `loom:building` / `loom:blocked`, zero PRs carry `loom:review-requested` / `loom:pr`, no open epics, no outstanding Architect/Hermit proposals, and no unlabeled issues awaiting Curator. The only two open issues are both `loom:operator-only` (#888, #918), neither eligible for `loom:issue`/`loom:urgent`. `loom-recover-orphans --recover` found no orphaned `loom:building` claims. All 10 most-recently-merged PRs correctly closed their linked issues — no orphaned closures found)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* Nothing ready to promote — the backlog carries no `loom:issue` work this pass.

## Ready for Work (`loom:issue`)

*Empty.*

## In Progress (`loom:building`)

*Empty.* #958 and #965, the prior pair, both shipped this pass (PR #975, PR #973) and are closed.

## PRs Awaiting Review (`loom:review-requested`)

*Empty.*

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Curated, Not Yet Claimed (`loom:curated`)

*Empty.* (#888 carries `loom:curated` but is also `loom:operator-only` — see below.)

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

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

**Two open issues as of 2026-08-11, both `loom:operator-only` and neither eligible for `loom:issue`/`loom:urgent`: #888 (curated, awaiting human/Champion design review of the review-loop lookahead proposal) and #918 (`loom:operator-mechanical`, loom-daemon-down watchdog escalation).** No PRs are open in the Loom review pipeline (`loom:review-requested` and `loom:pr` both empty) — #975 and #973, the two PRs open at the start of this pass, both merged. One PR is open outside the pipeline (#902, "chore: update Repo Skills 0.7.0 → 0.8.1", unlabeled human-authored tool bump, awaiting a direct human merge decision per `CLAUDE.md`'s small-mechanical-change guidance). `loom-recover-orphans --recover` found no orphaned `loom:building` claims this pass (none carry the label at all). The 10 most-recently-merged PRs (#975, #974, #973, #972, #971, #970, #969, #968, #967, #966) all correctly closed their linked issues — no orphaned closures found. Next action: a human or Champion reviews #888's design tradeoffs; #918 awaits a human daemon-recovery run. No ready work exists for Curator, Builder, or Judge to pick up until a new issue is filed or #888/#918 are resolved.

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
