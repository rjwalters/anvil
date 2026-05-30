# Work Plan

Prioritized roadmap generated from current GitHub label state. Maintained by the Guide triage agent.

*Last updated: 2026-05-30*

---

## Urgent (Top Priority)

*No issues currently carry the `loom:urgent` label.*

## In Progress (`loom:building`)

*No issues currently claimed.* The full v0 backlog cleared between 2026-05-28 and 2026-05-30 (see `WORK_LOG.md` for the merge sequence). Builders are idle pending new canary-surfaced friction or maintainer-prioritized follow-ups.

## Ready for Work (`loom:issue`)

*None at the moment.*

## Triage queue (`loom:triage`)

| Issue | Title | Tier | Notes |
|---|---|---|---|
| **#106** | Declare `pydantic` in `pyproject.toml` — `anvil/lib/__init__.py` eagerly imports `cite` which requires it | `tier:maintenance` | Surfaced by #102/#105 builder + judge. Pre-existing on main. Now that `pyproject.toml` exists (post-#105), this is the right time. Two paths: declare `pydantic` in `[project] dependencies` (recommended; `pydantic` is a real lib-level dep for the schema layer) OR make the `cite` import lazy. |

## Proposals Awaiting Human Approval (`loom:architect` / `loom:hermit`)

*None outstanding.*

## Backlog state

The repository moved from "v0 punch list of skill implementations" (2026-05-28) to "shipped 8 skills + lib substrate + figure-theming + render-gate + 2 vision-critic families + extensive install-script hardening" (2026-05-30). The aggressive cycle was canary-driven — 2AM Logic Studio's authoring use against the framework surfaced the prioritized friction in real time, and the framework absorbed it through small bounded PRs (typically 1-4 files modified + 1 new test file).

### Recurring themes the next wave of issues will likely touch

These are not currently open — they're forward-looking signals based on patterns visible across the closed issues:

1. **Per-skill `lib/` extraction → `anvil/lib/`.** Several primitives that started skill-local (deck's `marp_lint`, `auto_shrink_detector`; report's `ack.py` / `audit_flags.py` / `pdf_freshness.py`) are candidates for promotion when a second skill needs them. Trigger is observed duplication, not anticipation.

2. **Per-skill audit-command migrations.** Five skills (`pub`, `report`, `deck`, `slides`, `ip-uspto`) have `*-audit` commands that pre-date #29's `kind: tool_evidence` codification. Migrations to emit typed `_review.json` from those commands are tracked as separate follow-ups when they're filed.

3. **Memo-side render-gate analog.** `anvil:memo` is markdown-first (maintainer decision, #64); a markdown-appropriate length-proxy + clean-output gate could ship as memo's analog of `render_gate` if canary friction emerges.

4. **Render-gate consumer ergonomics.** The five paginated skills have `render_gate` wired (#64); per-thread `.anvil.json` overrides for `page_cap` and similar are part of the contract but the consumer-side ergonomics for setting them haven't been exercised at scale yet.

5. **Cross-skill primitive sharing.** `marp_lint` is duplicated between deck and slides via `importlib` shim (post-#38); a deeper consolidation would be a `lib/` extraction following theme #1.

## How this file is maintained

The Guide triage agent should refresh this file when:

- A new issue enters `loom:triage` (add to triage queue with notes).
- An issue is promoted to `loom:issue` (move to "Ready for Work").
- A builder claims an issue (`loom:issue` → `loom:building`; move to "In Progress").
- A PR merges and the issue closes (remove from this file; add to `WORK_LOG.md`).
- `loom:urgent` is added or removed.
- Stale issues need re-prioritization.

If the file is more than a week stale and the open-issues backlog has changed, regenerate from current label state and timestamp with `*Last updated: YYYY-MM-DD*` at the top.
