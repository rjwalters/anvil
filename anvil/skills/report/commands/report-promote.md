---
name: report-promote
description: Promoter command — transitions an AUDITED report to CUSTOMER-READY. Requires explicit human acknowledgment. Refuses to run from any state other than AUDITED.
---

# report-promote — Promoter (AUDITED → CUSTOMER-READY)

**Role**: promoter.
**Reads**: `<project>/_project.md`, latest `<project>/<thread>.{N}/` (must be in state `AUDITED`), `<thread>.{N}.review/verdict.md`, `<thread>.{N}.audit/verdict.md`, `<thread>.{N}/report.pdf`.
**Writes**: `<project>/<thread>.{N}.promote/receipt.md`, `<project>/<thread>.{N}.promote/_progress.json`, and updates `<project>/<thread>.{N}/_progress.json` with `phases.promote = done`.

**This command is the customer-facing release gate.** It is the only command in the report skill that requires an explicit human acknowledgment token — the equivalent of Loom's `loom:curated → loom:issue` promotion. It refuses to run from any state other than `AUDITED`.

## Why this command exists

The standard anvil state machine ends at `AUDITED`. For internal artifacts (like `anvil:memo`) that is sufficient — "the rubric cleared" and "the artifact is usable" are the same event. For customer-facing artifacts they are not:

- **`AUDITED`** is a machine-checkable state: rubric ≥35, audit pass, no critical flags. The skill can determine this from on-disk evidence with no human input.
- **`CUSTOMER-READY`** is an act of judgment: a human (or explicitly-authorized approver) accepts liability for releasing this specific PDF, with this specific content, to this specific recipient. The skill cannot determine this without an external acknowledgment.

Conflating them removes a useful kill-switch. A report can pass the rubric and still be inappropriate to deliver (recipient relationship changed, embargo period, follow-up question from the recipient that should be addressed before delivery, schedule slipped past delivery window). `report-promote` is where that judgment lands.

## Inputs

- **Project + thread path** (positional argument): `<project>/<thread>`.
- **Acknowledgment token** (REQUIRED): one of:
  - `--confirm-customer-ready` flag PLUS an interactive prompt where the operator must type the EXACT report title (read from `report.md`'s H1 heading) to confirm. Substring matches and lowercase-fuzzy matches are rejected.
  - Or, in non-interactive automation contexts, a `--ack-file <path>` argument pointing to a signed acknowledgment file the operator created out of band (the skill validates that the file exists, was modified within the last 24 hours, and contains the exact report title + recipient identity from `_project.md`).
  - The skill REFUSES to run without one of these. There is no `--yes` shortcut.
- **State precondition**: thread must be in state `AUDITED`. The skill verifies this by checking BOTH `<thread>.{N}.review/verdict.md` (advance: true, no flags) AND `<thread>.{N}.audit/verdict.md` (pass: true, no flags). Verifies `<thread>.{N}/report.pdf` exists and is newer than `report.md`.

## Outputs

```
<project>/<thread>.{N}.promote/
  receipt.md         Human-acknowledgment record + deliverable hash + supersession info
  _progress.json     { phases.promote.state == done }
```

And updates `<project>/<thread>.{N}/_progress.json` with `phases.promote.state = done` (so the version dir self-reports its CUSTOMER-READY status).

### `receipt.md` schema

```markdown
# CUSTOMER-READY receipt — <thread> v<N>

**Project**: <project-slug>
**Recipient**: <recipient from _project.md>
**Engagement ID**: <engagement_id from _project.md>
**Report title**: <H1 from report.md>
**Version**: <N>
**Deliverable**: <thread>.{N}/report.pdf
**Deliverable SHA256**: <sha256 of report.pdf at promotion time>
**Source SHA256**: <sha256 of report.md at promotion time>

## Acknowledgment

**Acknowledged by**: <operator identity — git user.name from env, or value from --ack-file>
**Acknowledged at**: <ISO timestamp>
**Method**: <"interactive prompt" | "ack-file: <path>">

## Rubric clearance

- Review verdict: <total>/40, advance: true, 0 critical flags
- Audit verdict: pass: true, 0 critical flags, <findings_count> claims audited
- Prior-report cross-check: <pass | with-reconciliation | n/a — no prior reports>

## Supersession

<If this is a later CUSTOMER-READY version on the same thread:>
**Supersedes**: <thread>.{prior_N}/ (delivered <prior_delivered_at>)
**Cause**: <brief operator-provided rationale, prompted at promotion time>
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/report.md`. Verify:
   - `<thread>.{N}.review/verdict.md` exists, parses, has `advance: true` and no critical flags.
   - `<thread>.{N}.audit/verdict.md` exists, parses, has `pass: true` and no critical flags.
   - `<thread>.{N}/report.pdf` exists and is newer than `report.md`.

   If any precondition fails, exit with a specific error explaining which one. Do NOT run the promotion.
2. **Idempotence check**: if `<thread>.{N}.promote/receipt.md` already exists, exit early with the message "thread already CUSTOMER-READY at version <N>, promoted at <timestamp>." (Re-promotion is not supported; supersession works by promoting a later version.)
3. **Load project context**: read `<project>/_project.md`. Extract `recipient` and `engagement_id` (both REQUIRED fields). The acknowledgment will be checked against `recipient` to ensure the operator knows who they are releasing to.
4. **Extract report title**: parse the first H1 heading from `report.md`. This is the canonical title used in the acknowledgment prompt.
5. **Verify rendering match**: compute SHA256 of both `report.md` and `report.pdf`. Re-render the PDF if `report.md` modtime is newer than `report.pdf` modtime — a stale PDF cannot be promoted. (If re-render is needed and `report-figures` has not been invoked since the last `report.md` change, fail with "report.pdf is stale; run report-figures first" rather than re-rendering implicitly — promotion should be a no-op check, not a side-effect cascade.)
6. **Acknowledgment** (REQUIRED — no shortcut path):
   - **Interactive path** (`--confirm-customer-ready`): print the report title, recipient, engagement_id, and SHA256 of the PDF to the operator. Prompt: "Type the exact report title to confirm CUSTOMER-READY promotion." Read input. Reject if it does not match the H1 character-for-character (whitespace-trimmed comparison; case-sensitive). On three rejected attempts, exit with no promotion.
   - **Non-interactive path** (`--ack-file <path>`): validate that the ack file exists, was modified within the last 24 hours, and contains (anywhere in its text body) BOTH the exact report title AND the exact recipient string from `_project.md`. If either substring is missing or the file is older than 24 hours, exit with no promotion.
7. **Detect supersession**: enumerate other `<thread>.{prior_N}.promote/` siblings under the project for the same thread slug. If any exist, the new promotion supersedes them. Prompt the operator for a one-line `Cause:` (or read from the ack file). Record both the prior version reference and the cause in `receipt.md`. (The skill does NOT modify prior `.promote/` siblings; they remain as audit trail. The newest `.promote/` is canonical for delivery.)
8. **Initialize `_progress.json`** (in the promote sibling dir): `phases.promote.state = in_progress`, `phases.promote.started = <ISO>`, `for_version = N`.
9. **Write `receipt.md`** per the schema above, including the verified SHA256 of `report.pdf` and `report.md`, the operator identity, acknowledgment method, and rubric clearance summary.
10. **Update `_progress.json`** (in the promote sibling): `phases.promote.state = done`, `phases.promote.completed = <ISO>`.
11. **Update `<thread>.{N}/_progress.json`** (in the version dir): merge `phases.promote.state = done`, `phases.promote.receipt_path = <thread>.{N}.promote/receipt.md`.
12. **Report**: print a one-line status (e.g., `Promoted acme-q2/findings.3 to CUSTOMER-READY (recipient: Acme Corp, deliverable SHA256 c7e3...)`). If this promotion superseded a prior version, also print the supersession note.

## Idempotence and safety

- A completed promotion (`<thread>.{N}.promote/receipt.md` exists) is never re-run. Re-invoking is a no-op with a notice. To supersede, draft a new version and promote that.
- The command has no `--force` or `--yes` flag. The acknowledgment requirement is the safety mechanism; bypassing it would defeat the purpose of the two-stage gate.
- A promotion failure (acknowledgment rejected, precondition not met) leaves no on-disk state. The thread remains in `AUDITED` and can be re-promoted later with a successful acknowledgment.

## Demotion (or rather, the absence of it)

A `CUSTOMER-READY` thread cannot be demoted. To correct a delivered report, draft a new version (`<thread>.{N+2}/`) and put it through a fresh `draft → review+audit → revise → figures → promote` cycle. The new `.promote/` sibling will supersede the old one (recorded in its `receipt.md`).

Rationale: a delivered report is a fact in the recipient's hands. Removing the on-disk record of that fact would create false confidence in the audit trail. Supersession is the right model — it acknowledges both the original delivery and the correction.

## Framework extraction note (per #10)

This command is the inline implementation of a two-stage promotion gate that the report skill needs but the standard anvil state machine does not provide. When `anvil/lib/state_machine.py` lands, the recommendation is to expose a **terminal-state extension hook** that allows skills to register additional post-`AUDITED` states with declared entry guards (acknowledgment requirements, precondition checks, custom receipt schemas). Likely consumers of the same pattern: `anvil:pub` (post-`AUDITED` → `SUBMITTED`), `anvil:ip-uspto` (post-`AUDITED` → `FILED`).

Wait until ≥2 skills need the pattern before extracting it. For now, this command is the reference implementation; future skills can copy it and adapt the receipt schema.

## `_progress.json` snippet (promote sibling)

```json
{
  "version": 1,
  "thread": "<slug>",
  "project": "<project-slug>",
  "for_version": <N>,
  "phases": {
    "promote": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

The version dir's `_progress.json` is updated additively with the same `phases.promote` block plus a `receipt_path` pointer.

## Notes for the promoter agent

- **You are not a critic.** You do not score, audit, or revise. Your one job is to enforce the acknowledgment gate and produce an auditable receipt of the human decision.
- **Refuse silently-broken preconditions.** If `report.pdf` is missing or stale, do not regenerate it as a side effect — fail loudly. The operator should see exactly what is wrong before they acknowledge release.
- **Acknowledgment is mandatory, not aspirational.** There is no automation path that skips it. If an orchestrating agent invokes this command without `--confirm-customer-ready` or `--ack-file`, the agent must escalate to a human — the skill will not promote.
- **The receipt is the audit trail.** Capture enough information that a future auditor can reconstruct, weeks later, what was delivered, to whom, when, and on whose say-so. SHA256 of the PDF is the load-bearing field — it is the cryptographic fact that ties the receipt to the artifact.
