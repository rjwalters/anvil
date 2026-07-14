---
name: spec-revise
description: Reviser for the spec skill. Consumes BOTH critic siblings (review + audit) for the latest version and produces a single revised version, preserving flagged-as-working normative statements. Never rewrites the spec to match a vestigial code path — a suspected implementation mismatch is an operator decision (Phase 2 / #707). REVIEWED+AUDITED → REVISED transition (loops until ≥39/44 with zero critical flags and a clean audit, or the iteration cap).
---

# spec-revise — Reviser

**Role**: reviser (one reviser consumes N critic siblings — here the review + audit pair, the `report`/`primer` shape).
**Reads**: latest `<thread>.{N}/<thread>.tex` (+ `sections/*.tex`) + `_progress.json`, BOTH `<thread>.{N}.review/` and `<thread>.{N}.audit/` (all files), the resolved `code_ref` implementation (when active), `<thread>/refs/` + shared `research/`, project `BRIEF.md`.
**Writes**: `<thread>.{N+1}/` with `<thread>.tex` (+ `sections/*.tex`), `changelog.md`, `_progress.json` — or reports `AUDITED` without writing when the combined verdict pre-check passes.

## CLI flags

### `--polish "<reason>"` (optional)

Operator-directed revision entry point — the sanctioned, audit-trailed path for spending one additional revision pass when the combined verdict pre-check (step 2) would otherwise force a terminal exit. Full contract: `anvil/lib/snippets/directed_revision.md` (`.anvil/anvil/lib/snippets/directed_revision.md` in an installed consumer repo). Summary:

- **Bypasses step 2 ONLY.** When passed, the combined verdict pre-check is skipped, so the reviser runs against an `AUDITED`-terminal version (which the default path correctly refuses) and polishes sub-threshold per-dimension justifications in `scoring.md`, `nit`-tagged or untagged `comments.md` notes, and audit-side line-level findings.
- **The critic-completeness check (step 1) still applies.** `--polish` bypasses the pre-check *verdict*, never the *existence* of the critics — BOTH a completed `<thread>.{N}.review/` AND a completed `<thread>.{N}.audit/` are still required.
- **The iteration-cap check (step 3) still applies.** `--polish` against a thread at `max_iterations` still hits the `BLOCKED` notice.
- **The reason argument is required.** `--polish` with no value, `--polish ""`, and `--polish "   "` (whitespace-only) are all rejected with a clear error; the thread is left untouched (no version dir written, no `_progress.json` mutation).
- **No inherited credit.** The polish-pass output is a normal `<thread>.{N+1}/` version dir. The next `spec-review` + `spec-audit` pass scores it on its own rubric merits — a fresh critic pair MUST land for the thread to re-reach `AUDITED`. The critics do NOT read the audit-trail fields and do NOT special-case the polish pass.
- **Audit-trail fields** (step 9): `metadata.revision_mode = "polish"` + `metadata.revise_force_reason = "<verbatim reason>"`, both audit-trail-only (NOT scored, NOT gating, NO state-machine impact).

See SKILL.md §"Operator-initiated polish passes" for the user-facing shape.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/<thread>.tex`. Require BOTH a completed `<thread>.{N}.review/` AND a completed `<thread>.{N}.audit/` (else exit pointing at the missing critic — `REVIEWED-PARTIAL`/`AUDITED-PARTIAL` are not advance-eligible per SKILL.md). Require `<thread>.{N+1}/` to not exist (immutability — never revise in place).
2. **Combined verdict pre-check**: read `<thread>.{N}.review/verdict.md` and `<thread>.{N}.audit/verdict.md`. When the review records `advance: true` (total ≥39/44, zero unresolved review critical flags) AND the audit records `audit_clean: true` (zero unresolved audit critical flags), the thread is **`AUDITED` — terminal**: report the publish-handoff summary (resolved body path, review total /44, clean audit, the handoff guarantees per SKILL.md §Publish handoff contract; note that `spec-figures` may optionally produce the PDF) and exit WITHOUT writing a new version.

   **Note (Phase 1)**: an audit carrying only `major` findings (e.g. a suspected implementation mismatch surfaced pending the Phase-2 three-way verdict) is `audit_clean: true` but the operator should weigh whether to resolve those findings before terminal exit; a `major` finding is not a hard block but is a revision priority the reviser addresses when it can (spec-side) or surfaces to the operator when direction is ambiguous (see step 6).

   **`--polish` bypass** (`anvil/lib/snippets/directed_revision.md`): when `spec-revise <thread> --polish "<reason>"` is invoked, this step is skipped entirely — proceed to step 4 regardless of `advance: true` + clean audit. Pre-check the reason argument before bypassing: an absent / empty / whitespace-only reason is rejected with a clear error and the thread is left untouched. `--polish` bypasses ONLY this step — step 1's dual-critic-required check and step 3's iteration cap still apply. See §"CLI flags" for the full required-reason + no-inherited-credit contract.
3. **Iteration-cap check**: default `max_iterations: 4` (worst-case terminal version `<thread>.5/`); project-BRIEF paired override (`max_iterations` + `iteration_cap_rationale`) per the #349 memo contract — the BLOCKED notice surfaces the rationale verbatim when an elevated cap is hit. At cap → report `BLOCKED — human review required` and exit.
4. **Read all critic input**: from the review — `verdict.md` (top revision priorities first), `scoring.md` (per-dim deductions; dim 1 normative-correctness gaps lead), `comments.md` (severity + `scope` tags), and the "What's working" list. From the audit — `verdict.md` (critical flags first, then `major` findings), `findings.md` (per-claim factual + implementation-consistency findings), `comments.md`. The two verdicts combine: a critical flag from *either* critic blocks.
5. **Handle the code_ref contract (conditional)**: when the BRIEF declares an active `code_ref`, re-resolve it (`anvil/lib/project_brief.py::resolve_code_ref(<project_dir>, <slug>)`) and read the implementation alongside the critic feedback so the revision stays consistent with it. When either critic carried the missing/unresolvable-`code_ref` `major` finding, surface it in the report (the fix is operator-side BRIEF authoring or path correction, not body editing).
6. **Build the revision plan**, ordered: (1) critical flags — every flag from EITHER critic MUST be addressed:
   - **Self-contradiction** (review-side) → reconcile the two incompatible statements to one normative value (choosing the correct one against `code_ref` when active, or escalating to the operator when the correct value is itself ambiguous).
   - **Undefined normative term** (review-side) → add the missing definition (in a definitions/notation section), not by deleting the normative use.
   - **Suspected implementation mismatch** (audit-side `major` finding — Phase 1): **this is NOT a mechanical fix.** The reviser may correct the spec ONLY when the review/audit evidence makes the direction unambiguous (the spec is plainly wrong and the implementation is the ratified truth). When the direction is ambiguous — the implementation may be a vestigial code path contradicting an accepted ADR — the reviser **does NOT rewrite the spec to match the code**; it records the mismatch as an unresolved operator decision in `changelog.md` and the report, exactly the near-miss the class exists to prevent. The full three-way verdict (spec-wrong / code-wrong / intentional-gap) + implementation-status register that mechanize this land in Phase 2 (#707).
   (2) `blocker`/`major` comments; (3) the lowest-scoring dims' deductions; (4) `minor`/`nit` only when they don't conflict with (1)–(3). Never touch the "What's working" list — the normative statements the reviewer flagged as load-bearing.
7. **Write `<thread>.{N+1}/<thread>.tex`** (+ `sections/*.tex`, slug-echo per #295) applying the plan. Re-run the drafter's self-disciplines on the result (internal-consistency sweep, code_ref-correspondence check) — the revision must not introduce a fresh instance of the failure mode it just fixed.
   - **Preserve/update the figure plan (draft-time figure-reference contract)**: carry forward the drafter's figure references and the `metadata.figure_plan` record. When the revision reorders sections or a critic flagged a figure's caption/placement, update the references AND the plan together so the two stay in sync. Adding a newly-needed diagram means placing a new reference + plan entry as the drafter's step 5 prescribes; removing a section that owned a figure removes both. `spec-figures` re-renders to whatever paths the revised body now references. Zero-figure threads carry an empty/absent plan forward unchanged (silent-off).
8. **Write `changelog.md`** mapping each consumed critic note to the change made (or to an explicit `declined — <reason>` entry; scoring deductions may be argued against, critical flags may not). **A suspected implementation mismatch the reviser did NOT reconcile (ambiguous direction) is recorded as an explicit `escalated — operator decision required` entry**, never as a silent spec rewrite. On a `--polish` pass, prepend a blockquote header note quoting the operator's `--polish` reason verbatim, and map each polish edit to its source (a sub-threshold dimension deduction, a `nit`/untagged comment, or an audit finding) or to the operator directive. The prior review's "What's working" list still binds.
9. **Initialize `_progress.json`** for the new version: `phases.revise.state = done` (LAST write), carry forward `metadata.code_ref_resolved` (when active) and `metadata.figure_plan` (updated per step 7), and **append the `score_history` row** for the completed review iteration per `anvil/lib/snippets/progress.md` §Convergence fields: `{ "iteration": <N>, "total": <reviewed-total>, "threshold": 39, "rubric_id": "anvil-spec-v1" }`. Stable-score termination (`STALLED`) follows `anvil/lib/snippets/rubric.md` §"Termination resolution order" over this history.

   **Polish-pass audit trail** (`anvil/lib/snippets/directed_revision.md` §"Audit-trail fields"): on a `--polish` pass, additionally write `metadata.revision_mode = "polish"` and `metadata.revise_force_reason = "<verbatim operator-supplied reason>"` (stored verbatim). Both fields are audit-trail-only: NOT scored, NOT gating, NO state-machine impact. On the default (no-`--polish`) path, `revision_mode` defaults to `"normal"` (or is omitted) and `revise_force_reason` is `null` (or omitted).
10. **Report**: e.g., `Revised botho-consensus.1 → botho-consensus.2 (addressed 1 self-contradiction + 2 major comments; 1 suspected impl mismatch escalated to operator, not rewritten). Next: spec-review + spec-audit botho-consensus`.

## What spec-revise does NOT do

- **Never edits `<thread>.{N}/` or any critic sibling in place** — immutability is the audit trail.
- **Never rewrites the spec to match a vestigial code path.** An ambiguous-direction implementation mismatch is escalated to the operator, never silently reconciled toward the code. This is the load-bearing safety property of the class (Phase 2 / #707 mechanizes it as the three-way verdict).
- **Never advances state itself** — the next `spec-review` + `spec-audit` pass scores `<thread>.{N+1}/` on its own merits.
- **Never bypasses critical flags** — a changelog `declined` entry is legitimate for scoring deductions, never for a critical flag from either critic.

## Git sync (opt-in, off by default)

Per `anvil/lib/snippets/git_sync.md`: if `.anvil/config.json` exists and `git.commit_per_phase` is `true`, end this phase: stage only the dirs this phase wrote, commit as `anvil(<skill>/<phase>): <thread>.{N} [<state>]`, push if `git.push` is `true`. Git failures warn and continue. Default off.

This phase's specifics:

- **Ordering**: after the `_progress.json` `done` write lands. On the no-write paths (AUDITED / BLOCKED at step 2–3) there is nothing to commit and the hook is a silent no-op.
- **Staging target**: ONLY this command's own `<thread>.{N+1}/` version dir.
- **Commit**: `anvil(spec/revise): <thread>.{N+1} [REVISED]`.
