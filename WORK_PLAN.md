# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-11 (Guide triage pass — #947 shipped via PR #953 (mirrored the `deck_imagegen` extra into the generated consumer pyproject); the `deck-imagegen`/figure-conventions cluster advanced: #948 and #951 claimed by Builders, #949 curated and also claimed, #954 opened against #948 and awaiting Judge review; a new issue #952 (deck agent-set generation gap) entered curation; urgent queue is empty — no `loom:issue` work is currently unclaimed; no `loom:blocked`/`loom:epic` issues open; PR #902, a human-authored tool-currency chore, remains open outside the Loom label pipeline)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

- **#961**: "Pre-flight/audit render-gate misattributes overfull-box line numbers across \input boundaries" (`tier:goal-supporting`, `loom:issue`). `render_gate` is shared infrastructure across every paginated LaTeX skill; hit twice on a live `ip-uspto-provisional` filing where a misattributed overfull-box location pointed a scoped reviser at the wrong file (`spec.tex` instead of the `\input`'d `claims.tex`). Routine complexity, clear regression-test shape.
- **#960**: "deck-imagegen: _extract_field_block swallows '**Worked example**:' blocks into preset prompt prefixes" (`tier:goal-supporting`, `loom:issue`). Every consumer using the shipped preset library (`studio-product`, `documentary`, ...) dispatches image-generation prompts polluted with fabricated worked-example content because the block-terminator regex doesn't recognize two-word `**Field**:` markers. Routine complexity.

## Ready for Work (`loom:issue`)

- **#961** and **#960** (above) — both promoted to `loom:urgent` this pass; no additional unclaimed `loom:issue` work beyond the urgent two.

## In Progress (`loom:building`)

- **#957**: "Build anvil:ip-search — a prior-art search skill feeding the positioning critic" (`loom:issue` + `loom:building` + `loom:curated`, `tier:goal-supporting`). Claimed by a Builder; live per the daemon sweep journal.
- **#952**: "generate-anvil-agents: deck agent set missing economics (default critic, dim 10) and vision" (`loom:building` + `loom:curated`, `tier:goal-supporting`). Claimed; no PR yet, label age well under `loom-recover-orphans`' 4h staleness threshold — not orphaned.

## PRs Awaiting Review (`loom:review-requested`)

*Empty.*

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug — a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.

## Blocked (`loom:blocked`)

- **#958**: "Wire an opt-in ip-search step into the ip-uspto(-provisional) lifecycle before the priorart critic" — depends on #957 (still open, currently `loom:building`). Stays blocked until #957 ships an invocable `ip-search` command.

## Triage Queue (unlabeled / awaiting Curator)

- **#962**: "Critic findings.md write blocked by report-file guard; agents forced into heredoc workaround" — filed with no labels yet; a cross-skill harness-adjacent friction report (every critic-writing agent in a real `ip-uspto-provisional` run hit a Write-tool guard false-positive on `findings.md` and fell back to a Bash heredoc). Awaiting Curator triage/tiering; not yet eligible for `loom:issue` or `loom:urgent`.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

**Eight open issues as of 2026-08-11: #961 and #960 (newly promoted to `loom:urgent` this pass, both `tier:goal-supporting`), #957 and #952 (`loom:building`, both live/not orphaned per `loom-recover-orphans`), #958 (`loom:blocked` on #957, dependency still open), #962 (unlabeled, awaiting Curator triage), #888 (curated + `loom:operator-only`, awaiting human/Champion design review), and #918 (`loom:operator-only` + `loom:operator-mechanical`, loom-daemon-down watchdog escalation).** No PRs are currently open in the Loom review pipeline (`loom:review-requested` / `loom:pr` both empty); one PR is open outside the pipeline (#902, "chore: update Repo Skills 0.7.0 → 0.8.1", unlabeled human-authored tool bump, awaiting a direct human merge decision per `CLAUDE.md`'s small-mechanical-change guidance). `loom-recover-orphans --recover` found no orphaned `loom:building` claims this pass. All recently merged PRs (#954, #955, #959, plus the earlier #953/#946/#943/#939/#936 batch) correctly closed their linked issues — no orphaned closures found. Next action: Builders continue #957/#952, a human or Champion reviews #888's design tradeoffs, #918 awaits a human daemon-recovery run, and Curator triages #962.

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
