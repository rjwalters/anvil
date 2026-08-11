# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-11 (Guide triage pass — issue #978 filed since the prior pass: a `tier:maintenance` hardening suggestion (backport #977's code-enforced `prior_art_step.py` behind #975's shipped `ip-search` pre-search knob), curated on arrival and not `loom:operator-only`. The backlog otherwise remains fully quiescent: zero issues carry `loom:issue` / `loom:urgent` / `loom:building` / `loom:blocked`, zero PRs carry `loom:review-requested` / `loom:pr`, no open epics, no outstanding Architect/Hermit proposals, and no unlabeled issues awaiting Curator. `WORK_LOG.md` is current — every closed issue above the prior high-water mark was closed via an already-recorded merged PR (#977, which looked issue-shaped, is actually a closed-unmerged PR, not a genuine issue). `loom-recover-orphans` found no orphaned `loom:building` claims (none carry the label). All recently-merged PRs correctly closed their linked issues — no orphaned closures found)*

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

- **#978**: "Backport #977's code-enforced `prior_art_step.py` behind #975's shipped ip-search pre-search knob" (`tier:maintenance`, complexity: routine). #958 shipped a doc-only, prose-enforced opt-in `ip-search` pre-search knob via PR #975; a concurrent duplicate PR (#977, closed unmerged) took a more rigorous approach with a real Python module and 26 behavioral tests structurally proving the four safety properties (off by default, no network call when unset, never clobbers operator art, fail-safe config parsing). This issue suggests backporting that module as the tested implementation behind the already-shipped knob, reconciling two incompatible `.anvil.json` `prior_art_search` config shapes in the process. Explicitly not urgent — the shipped behavior is already functionally correct per its own tests; a Curator/Builder may close this if the doc-only contract is judged sufficient. Not eligible for `loom:urgent` (no `loom:issue` — awaiting approval).

(#888 also carries `loom:curated` but is `loom:operator-only` — see below, not here.)

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

**Three open issues as of 2026-08-11: #978 (`loom:curated`, `tier:maintenance`, freshly filed backport suggestion, not operator-only) and two `loom:operator-only` issues neither eligible for `loom:issue`/`loom:urgent` — #888 (curated, awaiting human/Champion design review of the review-loop lookahead proposal) and #918 (`loom:operator-mechanical`, loom-daemon-down watchdog escalation).** No PRs are open in the Loom review pipeline (`loom:review-requested` and `loom:pr` both empty). One PR is open outside the pipeline (#902, "chore: update Repo Skills 0.7.0 → 0.8.1", unlabeled human-authored tool bump, awaiting a direct human merge decision per `CLAUDE.md`'s small-mechanical-change guidance). `loom-recover-orphans` found no orphaned `loom:building` claims this pass (none carry the label at all). Recently-merged PRs all correctly closed their linked issues — no orphaned closures found. Next action: a Curator/Builder may triage or close #978 per its own suggestion; a human or Champion reviews #888's design tradeoffs; #918 awaits a human daemon-recovery run. No ready work exists for Builder or Judge to pick up until #978 is promoted, or #888/#918 are resolved.

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
