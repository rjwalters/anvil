---
name: report-audit
description: Auditor command for the report skill. Verifies every cited claim against its source, checks numeric consistency, and cross-checks against prior delivered reports. Writes a read-only audit sibling directory. RUN BY DEFAULT — required to leave DRAFTED state.
---

# report-audit — Auditor

**Role**: auditor.
**Reads**: `<project>/_project.md` (including `prior_reports[]`), latest `<project>/<thread>.{N}/` (specifically `report.md`, `exhibits/`, and any cited source files in `<thread>/refs/`). For prior-report cross-check: also any `prior_reports[].thread` final version dirs referenced in `_project.md`.
**Writes**: `<project>/<thread>.{N}.audit/` with `verdict.md`, `findings.md`, `evidence.md`, and `_progress.json`.

The audit sibling directory is **read-only once written**. Revisions consume it; they never modify it.

This command is one of the two REQUIRED critic siblings for the report skill (the other is `report-review`). Both must complete before a thread can leave the `DRAFTED` state. They run in parallel.

**This command is run by default.** Unlike `anvil:memo` (where the auditor sibling is optional), `report` REQUIRES the auditor pass before promotion. Customer-facing material has higher correctness stakes than internal memos.

## Inputs

- **Project + thread path** (positional argument): `<project>/<thread>`.
- **Project context**: `<project>/_project.md` — REQUIRED. The auditor uses `prior_reports[]` to cross-check the current draft for contradictions with previously-delivered material.
- **Latest version directory**: highest `N` with `<thread>.{N}/report.md` existing.
- **Source references**: `<project>/<thread>/refs/**` — the auditor reads these to verify cited claims.
- **Prior delivered reports**: for each entry in `_project.md`'s `prior_reports[]`, the auditor opens the referenced `<thread>.{final_version}/report.md` and uses it as a cross-check corpus.
- **Rubric** (audit-side critical flags): `anvil/skills/report/rubric.md`.

## Outputs

```
<project>/<thread>.{N}.audit/
  verdict.md       Pass/fail + critical flags + prior-report cross-check summary + top revision priorities
  findings.md      Per-claim audit log (every quantitative claim + citation + audit result)
  evidence.md      Citation traceability map (every cited source → which claims depend on it)
  _meta.json       { critic, scorecard_kind: "human-verdict", started, finished, model, schema_version }
  _progress.json   Phase state for the auditor (phase: audit)
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/report.md`. If `<thread>.{N}.audit/_progress.json.audit.state == done` and `verdict.md` exists, the audit is complete — exit early with a notice (idempotent).
2. **Resume check**: if a prior crashed audit exists (`audit.state == in_progress` without `verdict.md`), delete the partial output and re-audit.
3. **Initialize `_progress.json`** for the audit dir: `phases.audit.state = in_progress`, `phases.audit.started = <ISO>`, `for_version = N` (per `anvil/lib/snippets/progress.md`). Also initialize `_meta.json` with `scorecard_kind: human-verdict` (see `anvil/lib/snippets/scorecard_kind.md`); report-audit ships task-specific `findings.md` and `evidence.md` alongside the scorecard-kind declaration.
4. **Read inputs**: load `<thread>.{N}/report.md`, enumerate `exhibits/`, load `_project.md`, enumerate `refs/`. For each entry in `prior_reports[]`, attempt to load `<thread>.{final_version}/report.md`; if the file is missing, note the gap in `verdict.md` (auditor does not fail solely on missing prior reports, but flags it for operator awareness).
5. **Build the claim inventory**: walk `report.md` and enumerate every quantitative claim, numeric assertion, named-entity attribution, and citation. Record each in `findings.md` with columns:

   ```
   | # | Location | Claim | Cited source | Verified? | Notes |
   |---|----------|-------|--------------|-----------|-------|
   | 1 | §2.1 ¶3  | "47% reduction in latency" | refs/perf-2026-04.csv | yes | Matches cited source within rounding |
   | 2 | Exec §1  | "12 customers affected"     | (none — uncited)       | NO  | CRITICAL: unsupported quantitative claim |
   | 3 | §3.2 fig2| "Top 3 vendors are A, B, C" | refs/vendor-survey.md  | partial | Source lists A, B, D — claim is wrong on third entry |
   ```

   Every row gets a `Verified?` value of `yes`, `no`, `partial`, or `n/a` (for non-quantitative narrative claims that the auditor cannot mechanically verify).
6. **Build the evidence map**: in `evidence.md`, invert the above — list every cited source (from `refs/` or external references), and for each one list which findings/recommendations depend on it. This surfaces single-source claims (everything depending on one document) and uncovers orphan sources (cited material not actually load-bearing).
7. **Check internal consistency**: compare numbers in the executive summary against numbers in the body against numbers in exhibits. Any mismatch is a critical flag (internal contradiction).
8. **Cross-check against prior reports** (`_project.md`'s `prior_reports[]`): for each prior report loaded, identify any claim in the current draft that disagrees with a claim in the prior report. Examples: a count that was N then and is N+5 now without explanation; a recommendation that contradicts a recommendation made earlier; an entity characterized differently. Each disagreement is either a critical flag (audit-side: "Contradicts prior report in engagement") OR is reconciled inline in the current draft with an explicit note ("In our Q1 report we stated X; based on additional evidence Y, we now state Z"). If reconciliation is present, the auditor flags it as a `reconciliation_present` note rather than a critical flag.
9. **Identify audit-side critical flags** (see `rubric.md`):
   - Unsupported quantitative claim (any row in `findings.md` with cited source = none AND claim is quantitative)
   - Cited source does not support claim (any row with `Verified? = no` or `partial` where the discrepancy is material)
   - Internal contradiction (from step 7)
   - Contradicts prior report in engagement, without reconciliation (from step 8)
   - Unreachable external citation (`audit_unreachable_external_citation`) — any row in `findings.md` with `Verified? = n/a` where the `Cited source` column matches an external URL (scheme `http://` or `https://`, case-insensitive). An external URL the auditor could not fetch is indistinguishable from a fabricated source and MUST NOT pass the audit. Narrative-claim `n/a` (rows whose cited source is `(none — uncited)`, `(internal)`, or another parenthesized literal) does NOT trigger this flag — uncited quantitative claims are already covered by the separate "Unsupported quantitative claim" flag above, and narrative `n/a` is allowed because you cannot verify what isn't quantitative. An `n/a` against an in-tree `refs/<path>` reference is an auditor-mistake case (the auditor CAN read in-tree refs) and is out of scope here — flag as a follow-up if observed. Each flag entry carries `kind: tool_evidence` per `anvil/lib/snippets/audit.md` and records the failed URL fetch in `tool_calls[]` (e.g., `{tool: "WebFetch", args: {url: "..."}}`); the `fix` / `location` field points at the originating `findings.md` row (e.g., `findings.md row #N`). Multiple offending rows aggregate into a single flag entry that references all originating rows. The flag surfaces via the standard `critical_flags[]` top-level field (no schema change).
10. **Compute pass/fail**: `pass = (no critical flags) AND (all quantitative claims verified or partial-with-acceptable-rationale)`.
11. **Write `verdict.md`** in the format specified in `rubric.md`:
    - Pass: `pass: true` or `pass: false`
    - Findings count: total + breakdown by severity
    - Critical flags (if any) with justification pointing to specific location and evidence
    - Prior-report cross-check: per-prior-report result (one bullet per entry in `prior_reports[]`)
    - Top revision priorities (if `pass: false`)
12. **Update `_progress.json`**: `phases.audit.state = done`, `phases.audit.completed = <ISO>`.
13. **Report**: print the path to the audit dir and a one-line status (e.g., `Audited acme-q2/findings.1 → acme-q2/findings.1.audit/ (pass: false, 2 critical flags, 14 claims audited, 3 prior reports cross-checked)`).

## Idempotence and resumability

- A completed audit (`audit.state == done` AND `verdict.md` exists with a parseable pass/fail) is never re-run. Re-invoking is a no-op with a notice.
- A crashed audit is re-runnable after deleting partial output.

## Parallel-with-review semantics

This command makes NO attempt to coordinate with `report-review`. Both commands read the same `<thread>.{N}/` version dir; they write to disjoint sibling paths; neither reads the other's output. The portfolio orchestrator (and `report-revise`) aggregates both critic outputs.

## Notes for the auditor agent

- **You are not a reviewer.** Stylistic concerns are out of scope; defer them to the review sibling. Your job is to verify that what the report says is **factually true and properly cited**, and that it does not contradict itself or prior delivered material.
- **Walk every cited source.** A citation that exists but does not support the claim is worse than an uncited claim — it is misleading. Both are flagged; the latter is more serious.
- **Quantify your coverage.** Report in `verdict.md` exactly how many quantitative claims you audited (e.g., "audited 18/18 quantitative claims; 14 verified, 2 partial, 2 unsupported"). If the report contains a quantitative claim you could not verify (because the source is not in `refs/` and you cannot access it), flag it explicitly in `findings.md` with `Verified? = n/a — source not accessible to auditor` and recommend the reviser either provide the source or remove the claim. **An `n/a` against an external URL (`http://` / `https://`) is no longer graceful degradation — raise `audit_unreachable_external_citation` (see step 9) and require the reviser to either supply the cited source under `refs/` or remove the claim. Narrative-claim `n/a` remains allowed.**
- **Prior-report cross-check is load-bearing.** This is the value-add of running the audit at all for ongoing engagements. A report that quietly contradicts a prior delivered report damages the engagement's credibility — and the recipient, who paid for both reports, will notice.
- **Do not invent reconciliations.** If you find a contradiction with a prior report and the current draft does NOT explicitly acknowledge it, that is a critical flag. Your job is not to construct the reconciliation; it is to surface the gap so the reviser can address it explicitly.

## `_progress.json` snippet (audit sibling)

```json
{
  "version": 1,
  "thread": "<slug>",
  "project": "<project-slug>",
  "for_version": <N>,
  "phases": {
    "audit": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

Merge rule (shallow): preserve fields not touched by this command.
