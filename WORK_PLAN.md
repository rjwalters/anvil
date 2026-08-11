# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-11 (Guide triage pass — #961 and #960 shipped via PR #967 (render-gate `\input`-scope attribution) and PR #966 (imagegen field-block terminator); the prior urgent pair is now closed and off the board. The `957`/`952`/`962` building trio each has a PR open for review (#969, #968, #970); a new issue #964 (deck-figures legibility gate) entered building, and #965 (deck-review auto-shrink singleton-class gap) entered curation, unclaimed. Urgent queue is empty — nothing currently rises above the building/blocked/operator-only work already in flight; no unlabeled issues awaiting Curator; PR #902, a human-authored tool-currency chore, remains open outside the Loom label pipeline)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No `loom:issue` work is currently unclaimed and ready to promote — everything approved is already `loom:building`.

## Ready for Work (`loom:issue`)

*Empty* (beyond the `loom:building` issue below, which already carries `loom:issue` from its prior approval).

## In Progress (`loom:building`)

- **#957**: "Build anvil:ip-search — a prior-art search skill feeding the positioning critic" (`loom:issue` + `loom:building` + `loom:curated`, `tier:goal-supporting`). PR #969 open (`loom:reviewing` + `loom:review-requested`).
- **#964**: "deck-figures: legibility gate heuristic ignores render scale and actual font sizes — false errors in both directions" (`loom:building` + `loom:curated`, `tier:goal-supporting`). Claimed; no PR yet.
- **#962**: "Critic findings.md write blocked by report-file guard; agents forced into heredoc workaround" (`loom:building` + `loom:curated`, `tier:goal-supporting`). PR #970 open (`loom:review-requested`).
- **#952**: "generate-anvil-agents: deck agent set missing economics (default critic, dim 10) and vision" (`loom:building` + `loom:curated`, `tier:goal-supporting`). PR #968 open (`loom:review-requested`).

## PRs Awaiting Review (`loom:review-requested`)

- **#970**: "docs(critics): propagate orchestrator guard-collision breadcrumb to 31 commands" — closes #962.
- **#969**: "feat(ip-search): add prior-art search skill feeding the positioning critic" — closes #957; also carries `loom:reviewing`.
- **#968**: "feat(agents): add deck-economics and deck-vision specialist agents" — closes #952.

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Curated, Not Yet Claimed (`loom:curated`)

- **#965**: "deck-review: auto-shrink detector skips singleton classes, leaving title-slide overflow lint errors uncrosscheckable" — curated but no tier label and no `loom:issue` yet; awaiting tier assignment / Champion promotion.

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug — a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.

## Blocked (`loom:blocked`)

- **#958**: "Wire an opt-in ip-search step into the ip-uspto(-provisional) lifecycle before the priorart critic" — depends on #957 (still open, currently `loom:building`, PR #969 open). Stays blocked until #957 ships an invocable `ip-search` command.

## Triage Queue (unlabeled / awaiting Curator)

*Empty.*

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

**Eight open issues as of 2026-08-11: #964, #962, #957, and #952 (all `loom:building`, each with a PR open except #964; none orphaned per `loom-recover-orphans --recover`), #965 (`loom:curated`, unclaimed, no tier label yet), #958 (`loom:blocked` on #957, dependency still open), #888 (curated + `loom:operator-only`, awaiting human/Champion design review), and #918 (`loom:operator-only` + `loom:operator-mechanical`, loom-daemon-down watchdog escalation).** Three PRs are open in the Loom review pipeline (`loom:review-requested`: #970, #969, #968); none yet approved (`loom:pr` empty). One PR is open outside the pipeline (#902, "chore: update Repo Skills 0.7.0 → 0.8.1", unlabeled human-authored tool bump, awaiting a direct human merge decision per `CLAUDE.md`'s small-mechanical-change guidance). `loom-recover-orphans --recover` found no orphaned `loom:building` claims this pass (two claims — #962, #952 — are watched but well under the 4h staleness threshold). All recently merged PRs (#967, #966, plus the earlier #959/#955/#954/#953/#946 batch) correctly closed their linked issues — no orphaned closures found. Next action: Judge reviews #970/#969/#968, a human or Champion reviews #888's design tradeoffs and #965's tiering, #918 awaits a human daemon-recovery run.

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
