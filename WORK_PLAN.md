# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-13 (Guide triage pass — the #1005/#997 `loom:building` pair from the previous pass both landed and closed: #1005 via PR #1023 (which also closed out the #1000 epic — all four phases complete), #997 via PR #1026 (which also filed a follow-up gap, #1027, now in the triage queue). No `loom:issue`, `loom:building`, `loom:blocked`, or `loom:epic` issues remain open. #888 and #918 are unchanged `loom:operator-only` items. One open PR, #1025, is a Judge-flagged duplicate of already-merged PR #1019 awaiting a human/Champion close decision — not eligible for any Guide label action. `WORK_LOG.md` gained three new entries this pass (PRs #1026, #1023, and a standalone closed-issue entry for the #1000 epic, #1000). Merged-PR/closed-issue pairing checked clean, no orphans.)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No `loom:issue` issues are open this pass, so there is nothing eligible to promote — see Ready for Work below.

## Ready for Work (`loom:issue`, non-building)

*Empty.* No open issues currently carry `loom:issue`.

## In Progress (`loom:building`)

*Empty.* #1005 and #997 (both `loom:building` last pass) landed via PR #1023 and PR #1026 respectively and are now closed.

## PRs Awaiting Review (`loom:review-requested`)

*Empty.*

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Needs Human Disposition (open PR, blocked on a judgment call)

- **PR #1025**: "feat(slides): recognize a Cues section for rehearse timing + saturation caveat" — duplicate of already-merged **PR #1019**, which closed the same issue (#1016) with equivalent content just ~14 minutes before #1025 opened. Judge flagged this as `loom:changes-requested` + `loom:merge-conflict` with real (non-mechanical) content conflicts in `CHANGELOG.md`, `slides/SKILL.md`, and `slides-rehearse.md`, and recommended closing #1025 as superseded rather than reconciling two independently-drafted versions of the same prose. Doctor's `loom:treating` claim stood down without reclaiming (already at the recommended terminal state). Awaiting a human or Champion decision to close.

## Curated, Not Yet Claimed (`loom:curated`)

*Empty.* The only currently-`loom:curated` issue is `loom:operator-only` (#888, listed below).

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug — a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.

## Blocked (`loom:blocked`)

*Empty.*

## Triage Queue (unlabeled / awaiting Curator)

- **#1027**: "AI-tell lexicon: 'load-bearing' boilerplate also present in deck/rubric.md dim 9 (missed by #997's file enumeration)" (`loom:triage`, marked `<!-- loom:complexity=trivial -->` by the filer). Follow-up gap found during review of PR #1026: `deck/rubric.md` uses a different 10-dim /49 rubric shape and was not in #997's curated Affected Files list, so its dim-9 "Are slides 18+ load-bearing?" boilerplate wasn't swept. Awaiting Curator enhancement.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*Empty.* The #1000 epic ("Make Anvil artifact skills discoverable in Claude and Codex") closed 2026-08-13T01:17:01Z — all four phases complete (#1002 via PR #1008, #1003 via PR #1010, #1004 via PR #1014, #1005 via PR #1023).

## Backlog state

**Three open issues as of 2026-08-13: #1027 (fresh, awaiting Curator), #888 (curated, operator-only, awaiting human design judgment), and #918 (operator-only infrastructure escalation).** The #1000 epic and its last two phases (#1005, #997) all closed this pass. No `loom:issue` issues are open, so nothing was eligible for `loom:urgent` this cycle. One open PR (#1025) is a judgment-call duplicate awaiting human/Champion closure — see "Needs Human Disposition" above. Merged-PR/closed-issue pairing checked clean this pass, no orphans found. Next action: Curator enriches #1027; a human or Champion reviews #888's design tradeoffs and decides on closing #1025 as superseded; #918 awaits a human daemon-recovery run on the affected host.

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
