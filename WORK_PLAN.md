# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-12 (Guide triage pass — #983 and #985 both shipped (PR #988, PR #989) and closed since the prior pass; no issues carry `loom:urgent` this pass because the ready backlog is empty — the only two open issues besides the operator-only pair are already `loom:building`. A new issue, #991 (follow-up filed by PR #989's author, propagating the orchestrator guard-collision cross-reference to the two remaining docs), appeared already `loom:building` — claimed without ever carrying `loom:issue`, likely direct daemon dispatch rather than the human-approval path; not a Guide action item. #984 still carries both `loom:issue` and `loom:building` simultaneously (unchanged dual-label state, still a live claim per `loom-recover-orphans --verbose`, not orphaned) and now has an open PR, #992, addressing it. `WORK_LOG.md` gained two entries (PR #988 closes #983, PR #989 closes #985); every other newly-closed issue above the prior high-water mark was already captured via an existing `(closes #N)` PR entry. All recently-merged PRs correctly closed their linked issues — no orphaned closures found. No `loom:blocked` issues, no open epics, no outstanding Architect/Hermit proposals)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No ready, non-building issue exists this pass to promote — see Backlog state below.

## Ready for Work (`loom:issue`)

*Empty.* #984 below also carries `loom:issue` but is listed under In Progress (it is simultaneously `loom:building`), not duplicated here.

## In Progress (`loom:building`)

- **#991**: "propagate orchestrator guard-collision cross-reference to remaining review/audit docs (datasheet-audit.md, memoir-review.md)" (`tier:maintenance`). Follow-up filed by PR #989; claimed directly as `loom:building` without ever carrying `loom:issue`. Not orphaned per `loom-recover-orphans`.
- **#984**: "deck-design: imagery-policy gate_should_run resolver misses the thread-level BRIEF frontmatter declaration" (`tier:goal-supporting`). Claimed by a Builder; not orphaned per `loom-recover-orphans`. Still carries `loom:issue` alongside `loom:building` — an unchanged dual-label state, left untouched since the claim is live. Now has an open PR, #992 (`loom:review-requested`), addressing it.

## PRs Awaiting Review (`loom:review-requested`)

- **#992**: "fix(deck): resolve imagery_policy against the thread BRIEF, not the ambiguous project-level one" — addresses #984.

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Curated, Not Yet Claimed (`loom:curated`)

*Empty.* #991 and #984 (both curated) have already been claimed and are listed under In Progress.

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

**Four open issues as of 2026-08-12: #991 and #984 (both `loom:building`, claimed by Builders), and two `loom:operator-only` issues neither eligible for `loom:issue`/`loom:urgent` — #888 (curated, awaiting human/Champion design review of the review-loop lookahead proposal) and #918 (`loom:operator-mechanical`, loom-daemon-down watchdog escalation).** No ready, non-building issue exists to mark `loom:urgent` this pass. One PR is open in the Loom review pipeline (#992, `loom:review-requested`, addressing #984) — #988 and #989 both merged this pass, closing #983 and #985 respectively. One PR is open outside the pipeline (#902, "chore: update Repo Skills 0.7.0 → 0.8.1", unlabeled human-authored tool bump, awaiting a direct human merge decision per `CLAUDE.md`'s small-mechanical-change guidance). `loom-recover-orphans --verbose` confirms both #991's and #984's `loom:building` claims are live (well under the 4h staleness threshold) — neither is orphaned. Recently-merged PRs all correctly closed their linked issues — no orphaned closures found. Next action: Builders on #991/#984 finish; Judge reviews #992; a human or Champion reviews #888's design tradeoffs; #918 awaits a human daemon-recovery run; #902 awaits a direct human merge decision.

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
