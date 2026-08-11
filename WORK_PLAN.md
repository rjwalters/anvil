# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-11 (Guide triage pass — the prior building trio (#957/#952/#962) and #964 all shipped via PR #969/#968/#970/#972; only #965 and #958 remain open work, both now `loom:building`. #958 ("wire ip-search into the lifecycle") is the direct follow-on to #957 and was promoted + claimed within this same pass — marked `loom:urgent` as the sole ready candidate, then claimed by a Builder minutes later. Both #965 and #958 briefly carried a stray `loom:issue` alongside `loom:building` (Builder claim step left the prior-approval label in place); cleaned up as label hygiene, no state otherwise changed. #965 has PR #973 open for review (documents the sanctioned resolution for singleton-class overflow, per curator decision D4). Urgent queue: 1/3 filled (#958). No unlabeled issues awaiting Curator; PR #902, a human-authored tool-currency chore, remains open outside the Loom label pipeline)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

- **#958**: "Wire an opt-in ip-search step into the ip-uspto(-provisional) lifecycle before the priorart critic" (`loom:building` + `loom:curated` + `loom:urgent`, `tier:goal-supporting`). Promoted to urgent as the only ready issue this pass; a Builder claimed it (added `loom:building`) shortly after. Left `loom:urgent` in place per policy — work already underway.

## Ready for Work (`loom:issue`)

*Empty.* Nothing carries a bare `loom:issue` right now — the only two issues that recently did (#958, #965) are both `loom:building`.

## In Progress (`loom:building`)

- **#958**: "Wire an opt-in ip-search step into the ip-uspto(-provisional) lifecycle before the priorart critic" (`loom:curated` + `loom:urgent`, `tier:goal-supporting`). Claimed; no PR yet.
- **#965**: "deck-review: auto-shrink detector skips singleton classes, leaving title-slide overflow lint errors uncrosscheckable" (`loom:curated`, `tier:goal-supporting`). PR #973 open (`loom:review-requested`).

## PRs Awaiting Review (`loom:review-requested`)

- **#973**: "docs(deck): name the sanctioned resolution for singleton-class overflow errors" — resolves #965's unified-gate hole (curator Option B: document the sanctioned resolution, not a peerless absolute-margin floor).

## Approved (Awaiting Merge) (`loom:pr`)

*Empty.*

## Curated, Not Yet Claimed (`loom:curated`)

*Empty.* #958 and #965 are both now `loom:building` (see above).

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug — a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.

## Blocked (`loom:blocked`)

*Empty.* #958's prior block (on #957) resolved when #957 merged (PR #969); #958 is now `loom:building`.

## Triage Queue (unlabeled / awaiting Curator)

*Empty.*

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

**Four open issues as of 2026-08-11: #958 and #965 (both `loom:building`; #958 with a PR pending, #965 with PR #973 open for review; neither orphaned per `loom-recover-orphans --recover`), #888 (curated + `loom:operator-only`, awaiting human/Champion design review), and #918 (`loom:operator-only` + `loom:operator-mechanical`, loom-daemon-down watchdog escalation).** One PR is open in the Loom review pipeline (`loom:review-requested`: #973); none yet approved (`loom:pr` empty). One PR is open outside the pipeline (#902, "chore: update Repo Skills 0.7.0 → 0.8.1", unlabeled human-authored tool bump, awaiting a direct human merge decision per `CLAUDE.md`'s small-mechanical-change guidance). `loom-recover-orphans --recover` found no orphaned `loom:building` claims this pass (#965's claim is watched but well under the 4h staleness threshold). All recently merged PRs (#972, #970, #969, #968, plus the earlier batch) correctly closed their linked issues — no orphaned closures found. Two issues (#958, #965) briefly carried a stray `loom:issue` alongside `loom:building` this pass — cleaned up as label hygiene; worth a look if the Builder claim step keeps leaving it behind. Next action: Judge reviews #973, a human or Champion reviews #888's design tradeoffs, #918 awaits a human daemon-recovery run.

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
