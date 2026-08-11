# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-11 (Guide triage pass — #947 shipped via PR #953 (mirrored the `deck_imagegen` extra into the generated consumer pyproject); the `deck-imagegen`/figure-conventions cluster advanced: #948 and #951 claimed by Builders, #949 curated and also claimed, #954 opened against #948 and awaiting Judge review; a new issue #952 (deck agent-set generation gap) entered curation; urgent queue is empty — no `loom:issue` work is currently unclaimed; no `loom:blocked`/`loom:epic` issues open; PR #902, a human-authored tool-currency chore, remains open outside the Loom label pipeline)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No `loom:issue` items are currently unclaimed — everything ready this pass has already been picked up by a Builder (see In Progress).

## In Progress (`loom:building`)

- **#951**: "figure-conventions §3: _find_anvil_root snippet contradicts its own docstring (flat vs nested palette path); mmdc first-run browser failure undocumented" (`tier:goal-supporting`). Claimed by a Builder; live per `loom-recover-orphans` (label age well under the 4h staleness threshold).
- **#949**: "deck-imagegen: speaker-notes prompt extraction leaks human slot-notes into the dispatched prompt" (`tier:goal-supporting`). Claimed by a Builder; live per `loom-recover-orphans`.
- **#948**: "deck-imagegen: _latest_version_dir misses post-#382 nested thread layout" (`tier:goal-supporting`). Claimed by a Builder; PR #954 already open against it, awaiting Judge review (see below).

#947 shipped this pass via PR #953 ("fix: mirror the deck_imagegen extra into the generated consumer pyproject"), closed 2026-08-11; see `WORK_LOG.md`.

## Ready for Work (`loom:issue`)

*Empty.* All `loom:issue` work this pass has already been claimed by a Builder (see In Progress).

## PRs Awaiting Review (`loom:review-requested`)

- **#954**: "fix(deck): resolve nested thread layout in deck-imagegen's version lookup" — closes #948, currently `loom:reviewing` (Judge picked it up).

One PR is open outside the Loom label pipeline: **#902** "chore: update Repo Skills 0.7.0 → 0.8.1" — opened directly by the repo owner (no labels), a tool-currency bump not routed through Curator/Builder. Per `CLAUDE.md`'s guidance on small mechanical changes, this class of PR doesn't require the full Loom review cycle; it awaits a direct human merge decision, not Judge/Champion action.

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug: a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Operator Escalations (`loom:operator-only`, infrastructure)

- **#918**: "loom-daemon is DOWN on ip-172-31-74-176 and watchdog recovery is exhausted" (`loom:operator-mechanical`). Automated watchdog escalation of last resort, filed 2026-08-08: the systemd unit is loaded but not running, and the bounded auto-recovery circuit breaker tripped after 5 attempts. Requires a human to run `.loom/scripts/cli/loom-daemon-start.sh` on the affected host and inspect `loom-daemon status`; the watchdog resumes automatic recovery once a tick observes a healthy daemon. Host/credential access, not judgment work — not eligible for `loom:issue` or `loom:urgent`.

## Blocked (`loom:blocked`)

*Empty.*

## Triage queue (`loom:triage` / `loom:curating`)

- **#952**: "generate-anvil-agents: deck agent set missing economics (default critic, dim 10) and vision" — `loom:curating`, Curator actively enhancing. Filed 2026-08-11.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

**Five open issues as of 2026-08-11: #951, #949, and #948 (all `loom:building`, the `deck-imagegen`/figure-conventions friction cluster, all claimed and live), #952 (`loom:curating`, a fresh deck agent-set generation gap), #888 (curated + `loom:operator-only`, awaiting human/Champion design review), and #918 (`loom:operator-only` + `loom:operator-mechanical`, loom-daemon-down watchdog escalation).** #947, last pass's sole `loom:urgent` item, shipped via PR #953. One PR is in Judge review (#954, closes #948) and one is open outside the Loom pipeline (#902, unlabeled, human-authored tool bump, awaiting a direct human merge decision). No orphaned `loom:building` issues (`loom-recover-orphans --verbose` reports none — #949/#948 are simply young claims, well inside the 4h staleness threshold), no `loom:blocked` issues, no open epics, and no unclaimed `loom:issue` work — the urgent queue is empty by construction. Next action: Judge reviews #954, Builders continue #949/#951, Curator finishes #952, and a human or Champion reviews #888's design tradeoffs; #918 awaits a human daemon-recovery run.

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
