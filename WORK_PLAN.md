# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-06 (Guide triage pass — issue #898 curated+approved and issue #899's PR opened to close it; PR #896 merge from the prior pass unchanged)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* #898 is the only `loom:issue`-labeled work, but it already has an open PR (#899) closing it and awaiting Judge review — there is no unclaimed ready work for `loom:urgent` to direct a Builder toward.

## In Progress (`loom:building`)

*Empty.* No open issues carry `loom:building`. Issue #894 (installer contract: version-source + machine-local sidecar gaps) closed 2026-08-06 via PR #896.

## Ready for Work (`loom:issue`)

- **#898**: "feat: deslop skill — iterate arbitrary prose clean of AI tells (anvil:deslop)" (`tier:goal-supporting`, `loom:curated`). Filed from the greentokens consumer repo for a new utility skill that cleans AI-drafted prose living outside any anvil project. Already has an open PR (#899) closing it — see "PRs Awaiting Review" below; no `loom:building` label was ever applied, but the issue is effectively covered.

## PRs Awaiting Review (`loom:review-requested`)

- **#899**: "feat(deslop): add anvil:deslop utility skill for cleaning AI-drafted prose outside any anvil project" — closes #898. Adds `anvil/skills/deslop/` (ingest → iterate → emit loop over `rhetoric_lint.py` + `project_brief.py` voice resolvers + `convergence.py`/`critics.py`), 36 new tests, README/CLAUDE.md skill-count updates.

## Curated, Awaiting Operator Review (`loom:curated` + `loom:operator-only`)

- **#888**: "review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect" (`tier:goal-supporting`). Canary-surfaced structural critique of the review/revise loop across all artifact-class skills, not a single-skill bug: a `wave-one-bandgaps` essay thread took ~23 agent runs to converge, with three distinct failure modes documented (each round's fix creates the next round's defect; inherited text is never systematically re-checked; findings trickle instead of batching). Suggested acceptance criteria include a persistent cross-version claim ledger and findings that carry predicted downstream effects. Flagged `loom:operator-only` — this shapes the core review/revise primitive shared by all 14 artifact-class skills, so it needs human/Champion design judgment before promotion to `loom:issue`, not routine Guide triage.

## Blocked (`loom:blocked`)

*Empty.* The three previously-blocked issues (#800, #746, #743) all closed 2026-07-30 when their pending PRs (#805, #761, #763) merged — see `WORK_LOG.md`.

## Triage queue (`loom:triage` / `loom:curating`)

*Empty.* No issues carry `loom:triage` or `loom:curating`.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Epics (`loom:epic`)

*None open.* The most recent epic, #697 (`anvil:spec` artifact class), closed 2026-07-15 — all four phases (#706–#709) merged; see `WORK_LOG.md` 2026-07-15.

## Backlog state

**Two open issues as of 2026-08-06: #898 (`loom:issue`, already covered by open PR #899 awaiting Judge review) and #888 (curated + `loom:operator-only`, awaiting human/Champion design review); one open PR (#899).** Issue #894 closed via merged PR #896. `loom:urgent` stays empty — #898 has no unclaimed work to direct (a PR already exists), and #888 is not eligible for `loom:urgent` promotion because it isn't `loom:issue` (the Guide never adds `loom:issue`; that's human/Champion approval). Next actions: Judge review of PR #899, and a human/Champion review of #888's design tradeoffs.

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
