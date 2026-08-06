# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-08-06 (Guide triage cycle — issue #894's Builder opened PR #896, now `loom:review-requested`; no other label-state changes)*

---

<!-- guide:plan-body:start -->
## Urgent (Top Priority)

*Empty.* No open issues exist to prioritize.

## In Progress (`loom:building`)

- **#894**: "Installer contract: version is scraped from CLAUDE.md prose, and machine-local fields are committed" (`tier:goal-supporting`). Two live correctness gaps in the installer contract shared across the Loom/Anvil/Repo Skills/squad tool family: (C8) `scripts/install-anvil.sh` regex-scrapes the version out of `CLAUDE.md` prose and fails hard on any rewording, while the root `VERSION` file exists but is empty; (C6) `.anvil/install-metadata.json` commits machine-local fields (`anvil_source` absolute path, `install_date`) instead of a gitignored sidecar, following the precedent set by Loom's `.loom/loom-source-path` and Repo Skills' `.claude/skills/repo/.install-local.json`. Opened, curated, approved, and claimed same-day (2026-08-06); PR **#896** now open and `loom:review-requested` (`Closes #894`) — see "PRs Awaiting Review" below.

## Ready for Work (`loom:issue`)

*Empty.* No open issues carry `loom:issue`.

## PRs Awaiting Review (`loom:review-requested`)

- **#896**: "fix(installer): read version from a root VERSION file, split machine-local install fields into a gitignored sidecar" — closes #894 (C8 version-source fix, C6 machine-local sidecar, C1 root `install.sh` entry shim, C7 consumer-side `resync-installed.sh`). Awaiting Judge review.

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

**Two open issues as of 2026-08-06: #894 (`loom:building`, PR #896 open for review) and #888 (curated + `loom:operator-only`, awaiting human/Champion design review); one open PR, #896.** `loom-recover-orphans` confirms #894 is not orphaned (live via the sweep journal). `loom:urgent` stays empty — the only unclaimed issue, #888, is not eligible for `loom:urgent` promotion because it isn't `loom:issue`, and the Guide never adds `loom:issue` (that's human/Champion approval, not triage). Next actions: Judge review of PR #896; separately, a human or Champion review of #888's design tradeoffs.

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
