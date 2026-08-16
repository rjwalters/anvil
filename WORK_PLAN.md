# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-16 (Guide triage pass — #1110 (the Hermit proposal to consolidate `_body_path()`/`_record_body_path()` helpers, listed under Proposals last pass) closed via merged PR #1114. A new Hermit proposal, #1121 ("Split anvil/lib/project_brief.py into a package"), ran the full pipeline within this tick's window — filed, promoted to `loom:issue`, and claimed by a Builder 25 seconds later — so it lands directly in "In Progress" rather than Proposals; it is the only open issue with no `loom:operator-only` label. No `loom:issue` candidates remain in the backlog (zero eligible, so `loom:urgent` stays empty rather than being filled with an ineligible holder — the incumbent set was already empty and stayed empty). #888, #918, #1069, #1070, #1072, #1073, #1081, #1090, #1103, #1107 are otherwise unchanged. No open PRs. `WORK_LOG.md` update deferred this pass: only 2 pending entries (PRs #1120, #1118, both already covered by their own "(closes #N)" text for issues #1119/#1116 once written — below the 5-entry batch threshold) and only ~20 minutes since the last write (below the 30-minute debounce window). Merged-PR/closed-issue pairing checked clean this pass — every recently-merged PR's closing reference resolved to a CLOSED issue, no orphans found (`loom-recover-orphans --recover` also reports none). README checked for architectural drift: none found, left untouched. No token-pool pressure signal (`.loom/tokens/.ranking` absent) — proceeded normally.)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No `loom:issue` issues are open at all — #1061 (the only one) closed this pass via PR #1109. Nothing to promote.

## Ready for Work (`loom:issue`, non-building)

*Empty.* No open issues currently carry `loom:issue`.

## In Progress (`loom:building`)

- **#1121**: "Split anvil/lib/project_brief.py into a package: 5816 lines, 9 clearly-bounded sections" (`tier:maintenance`). Reorganization proposal (not a removal) for the largest source file in the repo — the shared `BRIEF.md` schema + parser + resolver consumed by all 14 artifact-class skills. Proposed as a pure re-export split (`project_brief.py` → `project_brief/` package with modules along existing section boundaries) so no call-site churn. Filed and claimed by a Builder within the same window this pass — no Guide action needed.

## PRs Awaiting Review (`loom:review-requested`)

*Empty.*

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Needs Human Disposition (open PR, blocked on a judgment call)

*Empty.* PR #1025 (the duplicate-of-#1019 slides fix) is now CLOSED — resolved without a Guide action.

## Curated, Not Yet Claimed (`loom:curated`)

*Empty.* The only `loom:curated` issue open is `loom:operator-only` (#888, listed below).

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
- **#1103**: "Guard telemetry: worktree-write-confinement denies read-only multi-line heredoc scripts (gh-since.sh pattern persists, plus non-gh heredocs)" (`loom:auditor`/`loom:operator-decision`). `worktree-write-confinement` is the single most frequent guard trigger in the log (11 of 27 entries, 2026-08-06..2026-08-15) — two read-only shapes still deny at the catastrophic tier: the exact `GH_READ`+`jq` anti-pattern `CLAUDE.md`'s `gh-since.sh` section already documents a fix for, plus non-`gh` heredocs. Needs a human ruling distinct from #1072's cross-repo-token case.
- **#1107**: "Guard telemetry: worktree-write-confinement-unresolved-var denies backgrounded pytest run redirecting to /tmp scratch log" (`loom:auditor`/`loom:operator-decision`). Now Curator-triaged (was in the Triage Queue last pass). One instance distinct in shape from #1072 (cross-repo token write): a backgrounded `pytest` run inside a worktree redirecting to a locally-assigned `/tmp` scratch path, denied at the catastrophic tier. Needs a human ruling.

## Blocked (`loom:blocked`)

*Empty.* #1061 (the only blocked issue) resolved its own re-check and closed this pass via PR #1109.

## Triage Queue (unlabeled / awaiting Curator)

*Empty.* #1107 (previously here) has been Curator-triaged to `loom:operator-only`/`loom:operator-decision` — see Operator Escalations above.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*Empty.* #1110 (the `_body_path()`/`_record_body_path()` consolidation) closed via PR #1114 this pass. #1121 (new this pass) skipped this state entirely — promoted and claimed within the same window — see "In Progress" above.

## Epics (`loom:epic`)

*Empty.* The #1000 epic ("Make Anvil artifact skills discoverable in Claude and Codex") closed 2026-08-13T01:17:01Z — all four phases complete (#1002 via PR #1008, #1003 via PR #1010, #1004 via PR #1014, #1005 via PR #1023).

## Backlog state

**Eleven open issues as of 2026-08-16, none `loom:urgent`-eligible: #888 (curated, operator-only, awaiting human design judgment), #918 (operator-only infrastructure escalation), eight Auditor/Curator operator-mechanical or operator-decision escalations (#1069, #1070, #1072, #1073, #1081, #1090, #1103, #1107, all `loom:operator-only` — see Operator Escalations above), and #1121 (a Hermit proposal already claimed by a Builder, see In Progress above).** No open PRs, zero `loom:issue` issues open at all — the backlog's one live candidate this pass (#1121) was promoted and claimed within the same window before Guide's tick, so there was nothing to promote to `loom:urgent`; the empty incumbent urgent set stayed empty. Merged-PR/closed-issue pairing checked clean this pass, no orphans found (`loom-recover-orphans --recover` also reports none). `WORK_LOG.md` write deferred (batching a 2-entry delta below the 5-entry/30-minute threshold). Next action: a human reviews the eight operator escalations and #888's design tradeoffs; #918 still awaits a human daemon-recovery run on the affected host.

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
