# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-15 (Guide triage pass — #1084 and #1086 (both `loom:building` last pass) merged via PR #1088 and PR #1091 respectively and closed; five more maintenance PRs landed since (#1074, #1077, #1079, #1085, #1093, #1097), leaving nothing `loom:building`. A new Hermit proposal, #1098 ("Wire or remove orphaned ack.py: report-promote's executable spec is never invoked"), was filed this pass. #888, #918, #1061, #1069, #1070, #1072, #1073, #1081 are otherwise unchanged — #1061 remains the only `loom:issue` issue and remains `loom:blocked` pending its 2026-08-16 re-check, so nothing was eligible for `loom:urgent` this pass (urgent set is empty; no eligible candidate to fill it). No open PRs. `WORK_LOG.md` updated with PR #1097 this pass (debounce window elapsed, single pending entry written). Merged-PR/closed-issue pairing checked clean, no orphans; `loom-recover-orphans --recover` also reports none.)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* #1061 is the only `loom:issue` issue open, and it is also `loom:blocked` — not eligible for promotion until its time-gated re-check (due 2026-08-16) clears. Nothing else to promote.

## Ready for Work (`loom:issue`, non-building)

*Empty of actionable work.* #1061 carries `loom:issue` but is also `loom:blocked` (its acceptance criteria call for a re-check of guard telemetry on/after 2026-08-16, seven days after the #5754 create-side redirect landed) — see Blocked below.

## In Progress (`loom:building`)

*Empty.* #1084 and #1086 (both claimed as of the previous pass) merged via PR #1088 and PR #1091 respectively and are now closed. Nothing currently claimed.

## PRs Awaiting Review (`loom:review-requested`)

*Empty.*

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Needs Human Disposition (open PR, blocked on a judgment call)

*Empty.* PR #1025 (the duplicate-of-#1019 slides fix) is now CLOSED — resolved without a Guide action.

## Curated, Not Yet Claimed (`loom:curated`)

*Empty.* #1061 also carries `loom:curated` but is already promoted (`loom:issue`, currently `loom:blocked` — see Blocked below), so it is not "awaiting promotion." The only unpromoted `loom:curated` issue is `loom:operator-only` (#888, listed below).

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug — a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure / guard-tuning judgment)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.
- **#1069**: "Guard telemetry: rm-scope-unresolved-var denies self-contained mktemp scratch-dir cleanup" (`loom:auditor`/`loom:operator-decision`). Auditor-filed under the #3898 Guard-Decision Telemetry Review standing policy: 2 independent `deny`/`catastrophic`-tier hits where a `mktemp -d && ... && rm -rf "$tmpdir"` scratch-dir cleanup was denied. Needs a human ruling on whether the guard pattern should recognize a self-contained mktemp-scoped `rm -rf` as safe.
- **#1070**: "Guard telemetry: stash-scope:main-checkout asks on self-contained stash/pull/pop sequence" (`loom:auditor`/`loom:operator-decision`). 1 `ask`-tier hit on a `git stash && git pull --ff-only && git stash pop` sequence run in the main checkout; an unanswered `ask` blocks headless runs the same as a deny. Needs a human ruling on narrowing this ask.
- **#1072**: "Guard telemetry: worktree-write-confinement-unresolved-var denies cross-repo gh-config token write (keep flagged)" (`loom:auditor`/`loom:operator-decision`). 1 `catastrophic`-tier deny on a cross-repo `gh-config/hosts.yml` token write; the issue's own title recommends keeping this one flagged rather than loosening the guard — a human ruling documents/confirms that stance.
- **#1073**: "Guard telemetry: catastrophic:rm pattern fires on heredoc prose mentioning 'rm -rf /' as an example text, not an executed command" (`loom:auditor`/`loom:operator-decision`). A denied heredoc write (a Curator-style draft comment for #1060) was flagged only because its markdown prose *mentions* `rm -rf /` as an example, not because anything executed it. Needs a human ruling on whether the catastrophic-`rm` regex should exempt heredoc/quoted prose content.
- **#1081**: "Guard telemetry: stash-scope:create-redirect denies self-contained stash/lint-check/pop sequence" (`loom:auditor`/`loom:operator-decision`). Sibling of #1061: the same self-contained `git stash && <read-only lint check>; git stash pop` shape, but here it trips the sibling `deny`-tier `stash-scope:create-redirect` branch (raw `git stash` with other managed worktrees active) instead of the `ask`-tier `worktree-collision` branch. Per #1061's own Champion-reviewed correction, the shared cross-worktree `refs/stash` stack means this is not provably safe either — proposed outcome is keep flagged pending upstream review, mirroring #1061's disposition.
- **#1090**: "Guide role's automated PR body template references nonexistent issue #1784" (`loom:operator-mechanical`). Every automated "docs: Guide document maintenance update" PR body carries a dead `See issue #1784 for the feature specification.` line — root-caused to a vendored `.loom/roles/guide.md`/`.claude/commands/loom/guide.md` template that hardcodes an unqualified `#1784` reference resolving only inside `rjwalters/loom`'s own tracker. Cosmetic only (no repo content affected); curated acceptance criteria call for filing the fix upstream in `rjwalters/loom` rather than patching the vendored copy locally (would revert on next resync).

## Blocked (`loom:blocked`)

- **#1061**: "Guard telemetry: stash-scope:worktree-collision blocks self-contained stash/pop pairs inside a worktree" (`loom:issue`, `loom:curated`, `tier:maintenance`). Champion reviewed the issue's original narrowing proposal and found it technically unsound (the shared `refs/stash` stack across worktrees means a same-worktree, same-chain `stash && check && stash pop` is not actually race-free). Revised outcome: do not narrow the guard; re-check `stash-scope` telemetry on/after 2026-08-16 (7+ days after the #5754 create-side redirect landed) and only file an upstream `rjwalters/loom` issue if hits persist. No action for Guide until that date.

## Triage Queue (unlabeled / awaiting Curator)

*Empty.* #1027 (the deck/rubric.md follow-up gap) landed via PR #1030 and is now closed.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

- **#1098**: "Wire or remove orphaned ack.py: report-promote's executable spec is never invoked" (`loom:hermit`, `tier:maintenance`). `anvil/skills/report/lib/ack.py` (258 lines) is a complete, tested implementation of `report-promote.md` step 6's eight ack-file failure modes, but nothing outside its own test file ever calls it — the command's step 6 instead re-describes the identical algorithm in prose for an agent to hand-implement inline each run, so the tested code path sits inert while the prose path is what's actually load-bearing on this customer-facing release gate. Lays out both remediation options (wire in vs. delete) without prescribing one; awaiting human/Champion evaluation before promotion to `loom:issue`.

## Epics (`loom:epic`)

*Empty.* The #1000 epic ("Make Anvil artifact skills discoverable in Claude and Codex") closed 2026-08-13T01:17:01Z — all four phases complete (#1002 via PR #1008, #1003 via PR #1010, #1004 via PR #1014, #1005 via PR #1023).

## Backlog state

**Ten open issues as of 2026-08-15, none `loom:urgent`-eligible: #888 (curated, operator-only, awaiting human design judgment), #918 (operator-only infrastructure escalation), #1061 (approved but `loom:blocked` until its 2026-08-16 re-check), six Auditor/Curator operator-mechanical or operator-decision escalations (#1069, #1070, #1072, #1073, #1081, #1090, all `loom:operator-only` — see Operator Escalations above), and one fresh Hermit proposal (#1098, not yet `loom:issue`).** No open PRs, nothing `loom:building`. Nothing was eligible for `loom:urgent` this cycle — the sole `loom:issue` issue (#1061) is blocked, and it is the only `loom:issue` candidate in the backlog, so the urgent set stays empty rather than being filled with an ineligible/blocked holder. Merged-PR/closed-issue pairing checked clean this pass, no orphans found (`loom-recover-orphans --recover` also reports none). Next action: a human reviews the six operator escalations, #888's design tradeoffs, and #1098's wire-in-vs-delete judgment call; #918 still awaits a human daemon-recovery run on the affected host; #1061 waits on its own time-gated re-check due 2026-08-16.

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
