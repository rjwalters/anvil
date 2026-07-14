# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-07-03*

---

## Urgent (Top Priority)

*No issues currently carry the `loom:urgent` label.*

## In Progress (`loom:building`)

*No issues currently claimed.*

## Ready for Work (`loom:issue`)

*None at the moment.*

## Triage queue (`loom:triage`)

*Empty.* The 2026-07-01/02 sweep waves cleared the entire backlog: the `nitas-mama` memoir enablement wave (#596–#599 → PRs #603–#606) and the blog-parity batch (#600–#602 → PRs #607–#609). See `WORK_LOG.md` for the merge record.

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Backlog state

Zero open issues as of 2026-07-03. A **v0.7.0 release cut is pending** — `CHANGELOG.md` `[Unreleased]` carries the full post-0.6.0 batch (deck business-model wave, memoir enablement wave, blog-parity batch, memo/ip/install hardening).

### Known follow-ons (documented in curation comments, filed as issues as needed)

These were deliberately deferred from the 2026-07-02 sweep to keep PRs small; the lib contracts shipped without skill-level consumers:

1. **Corpus claim-provenance skill adoption** (from #597's curation): `paper-audit` corpus verification step (`kind: tool_evidence`, five-way classification, fabrication-class critical flags), `paper-review` back-check (5–10 spot samples), `essay-draft` provenance.md writing + `essay-review` back-check. Until one lands, a corpus-declaring project cannot actually run a corpus audit.
2. **Subject voice tier adoption beyond essay** (from #598's curation): paper and report drafter/reviewer wiring per the same pattern (their voice-grounding steps already exist); audit hooks.
3. **Deferred from #598**: rhetoric-lint integration for subject-dialogue lines; `vocab_reminder`-style subject-cadence tool.

### Recurring themes the next wave of issues will likely touch

Forward-looking signals from `ROADMAP.md` "Near-Term Themes" (dormant until canary friction or a second consumer surfaces):

1. **Per-skill `lib/` extraction → `anvil/lib/`** — trigger is observed duplication, not anticipation.
2. **Per-skill audit-command migrations** to typed `_review.json` (`kind: tool_evidence`).
3. **Memo-side render-gate analog** (markdown-appropriate length proxy + clean-output gate).
4. **Render-gate consumer ergonomics** (per-thread overrides at scale).
5. **Cross-skill lint sharing** (deck/slides `marp_lint` consolidation).

## How this file is maintained

The Guide triage agent should refresh this file when:

- A new issue enters `loom:triage` (add to triage queue with notes).
- An issue is promoted to `loom:issue` (move to "Ready for Work").
- A builder claims an issue (`loom:issue` → `loom:building`; move to "In Progress").
- A PR merges and the issue closes (remove from this file; add to `WORK_LOG.md`).
- `loom:urgent` is added or removed.
- Stale issues need re-prioritization.

If the file is more than a week stale and the open-issues backlog has changed, regenerate from current label state and timestamp with `*Last updated: YYYY-MM-DD*` at the top.
