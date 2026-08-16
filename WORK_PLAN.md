# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-16 (Guide triage pass — a Builder claimed #1133 ("Consolidate 10 duplicate `_parse_frontmatter` test helpers into `anvil/lib/testing.py`", `loom:curated`/`tier:maintenance`) since the prior pass, moving it `loom:issue` → `loom:building`; `loom-recover-orphans` confirms it is legitimately in progress (freshly claimed, well under the 4h stale-building threshold), not orphaned. Otherwise the operator-only backlog is unchanged: the same ten `loom:operator-only` issues (#888, #918, #1069, #1070, #1072, #1073, #1081, #1090, #1103, #1107) remain open, none newly eligible for `loom:urgent`. No open PRs. Incumbent `loom:urgent` set stayed empty (zero eligible candidates) — another quiet tick on that front. `WORK_LOG.md` updated this pass: appended entries for two Auditor-filed guard-telemetry issues closed as not-planned duplicates since the prior write — #1132 (duplicate of #1103's read-only-heredoc sub-pattern) and #1131 (duplicate of #1069's mktemp/rm-scope pattern) — both folded their additional telemetry into a comment on the surviving issue rather than staying open as separate escalations; no new merged PR needed recording (PR #1129 was already captured, and PR #1130 is this role's own prior docs-maintenance PR, correctly excluded). README checked for architectural drift: none found, left untouched. No token-pool pressure signal (`.loom/tokens/.ranking` absent) — proceeded normally.)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No `loom:issue` issues are open at all. Nothing to promote.

## Ready for Work (`loom:issue`, non-building)

*Empty.* No open issues currently carry `loom:issue`.

## In Progress (`loom:building`)

- **#1133**: "Consolidate 10 duplicate `_parse_frontmatter` test helpers into `anvil/lib/testing.py`" (`tier:maintenance`). Claimed by a Builder this pass (`loom:issue` → `loom:building`). Mirrors the same-shaped consolidations already merged this cycle (#1085's `frontmatter.py` extraction, #1126's `_tree_hash`/`_tree_digest` cleanup). Confirmed not orphaned via `loom-recover-orphans` (freshly claimed, well under the 4h stale-building threshold).

## PRs Awaiting Review (`loom:review-requested`)

*Empty.*

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Needs Human Disposition (open PR, blocked on a judgment call)

*Empty.* PR #1025 (the duplicate-of-#1019 slides fix) is now CLOSED — resolved without a Guide action.

## Curated, Not Yet Claimed (`loom:curated`)

*Empty.* Two `loom:curated` issues are open: #1133 is already claimed (`loom:building`, see In Progress above) and #888 is `loom:operator-only` (listed below).

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

*Empty.* No open Architect/Hermit proposals this pass.

## Epics (`loom:epic`)

*Empty.* The #1000 epic ("Make Anvil artifact skills discoverable in Claude and Codex") closed 2026-08-13T01:17:01Z — all four phases complete (#1002 via PR #1008, #1003 via PR #1010, #1004 via PR #1014, #1005 via PR #1023).

## Backlog state

**Eleven open issues as of 2026-08-16: #1133 (`loom:building`, a Builder actively working the `_parse_frontmatter` consolidation) plus the same ten `loom:operator-only` issues as the prior pass — #888 (curated, operator-only, awaiting human design judgment), #918 (operator-only infrastructure escalation), eight Auditor/Curator operator-mechanical or operator-decision escalations (#1069, #1070, #1072, #1073, #1081, #1090, #1103, #1107 — see Operator Escalations above).** No open PRs; the empty incumbent urgent set stayed empty (nothing `loom:issue`-eligible exists to promote). Two Auditor-filed guard-telemetry issues closed as not-planned duplicates this pass (#1132 → #1103, #1131 → #1069) — their contributions were folded into comments on the surviving issues rather than left as separate open escalations, so the Operator Escalations list itself is unchanged. `WORK_LOG.md` updated this pass with those two closures. Next action: a human reviews the eight operator escalations and #888's design tradeoffs; #918 still awaits a human daemon-recovery run on the affected host; #1133 needs no Guide action while a Builder has it claimed.

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
