# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-12 (Guide triage pass — #978 shipped via PR #981 and is now closed. Two new unlabeled issues arrived (#984, #985, awaiting Curator) and one new curated-not-yet-claimed issue (#983). #982, a new `tier:goal-supporting` issue, was claimed by a Builder (`loom:building`) within this same window — `loom-recover-orphans --verbose` confirms it is not an orphan (label age ~1 minute, well under the 4h staleness threshold). No `loom:issue` work is ready to promote to `loom:urgent` this pass — the backlog carries zero bare `loom:issue` issues. `WORK_LOG.md` is current: no new merged PRs above the #975 high-water mark (excluding this phase's own docs PRs), and every newly-closed issue above the prior issue high-water mark is already captured via an existing `(closes #N)` PR entry, so no WORK_LOG append was needed this pass. All recently-merged PRs correctly closed their linked issues — no orphaned closures found. No `loom:blocked` issues, no open epics, no outstanding Architect/Hermit proposals)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* Nothing ready to promote — the backlog carries no `loom:issue` work this pass.

## Ready for Work (`loom:issue`)

*Empty.*

## In Progress (`loom:building`)

- **#982**: "figurer tikz output crowds/collides labels and self-reports 'clean'; no default pixel-level visual QA on rendered figures" (`tier:goal-supporting`). Claimed by a Builder; not orphaned per `loom-recover-orphans`.

## PRs Awaiting Review (`loom:review-requested`)

*Empty.*

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Curated, Not Yet Claimed (`loom:curated`)

- **#983**: "deck-review: no deterministic gate for bottom-edge caption clipping — add a PDF-text-layer completeness check". Curated, not yet promoted to `loom:issue` or claimed.

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug — a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.

## Blocked (`loom:blocked`)

*Empty.*

## Triage Queue (unlabeled / awaiting Curator)

- **#985**: "generated critic agents: findings.md sidecar writes trip report-file Write heuristics — name manifest files as expected outputs"
- **#984**: "deck-design: imagery-policy gate_should_run resolver misses the thread-level BRIEF frontmatter declaration"

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

**Six open issues as of 2026-08-12: #982 (`loom:building`, claimed by a Builder), #983 (`loom:curated`, not yet claimed), #984 and #985 (both unlabeled, awaiting Curator), and two `loom:operator-only` issues neither eligible for `loom:issue`/`loom:urgent` — #888 (curated, awaiting human/Champion design review of the review-loop lookahead proposal) and #918 (`loom:operator-mechanical`, loom-daemon-down watchdog escalation).** No PRs are open in the Loom review pipeline (`loom:review-requested` and `loom:pr` both empty) — #981 merged this pass, closing #978. One PR is open outside the pipeline (#902, "chore: update Repo Skills 0.7.0 → 0.8.1", unlabeled human-authored tool bump, awaiting a direct human merge decision per `CLAUDE.md`'s small-mechanical-change guidance). `loom-recover-orphans --verbose` confirms #982's `loom:building` claim is live (~1 minute old, well under the 4h staleness threshold) — not an orphan. Recently-merged PRs (including #981, which closed #978) all correctly closed their linked issues — no orphaned closures found. Next action: the Builder on #982 finishes and opens a PR; Curator picks up #984 and #985; Champion or a human promotes #983 once curated work is otherwise clear; a human or Champion reviews #888's design tradeoffs; #918 awaits a human daemon-recovery run; #902 awaits a direct human merge decision. No `loom:issue` work exists for the Guide to prioritize this pass.

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
