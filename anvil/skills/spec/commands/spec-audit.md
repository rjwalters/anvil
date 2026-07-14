---
name: spec-audit
description: Auditor for the spec skill. Verifies factual/internal-logic correctness and, when code_ref is active, sweeps the spec's normative claims against the resolved implementation. Phase 1 records a suspected code/spec mismatch as a major finding; the full three-way verdict (spec-wrong / code-wrong / intentional-gap) + implementation-status register land in Phase 2 (#707). Degrades gracefully when code_ref is absent or unresolvable. Runs parallel with spec-review. DRAFTED/REVISED → AUDITED transition.
---

# spec-audit — Auditor

**Role**: auditor (factual + spec↔implementation consistency critic; runs parallel with `spec-review` per the `report`/`primer` two-critic shape).
**Reads**: latest `<thread>.{N}/<thread>.tex` (+ `sections/*.tex`), `<thread>.{N}/_progress.json` (`metadata.figure_plan` — the diagram sources to audit alongside the prose; `metadata.code_ref_resolved`), the diagram source (mermaid `.mmd` under `<thread>/refs/` or the drafter's recorded inline specs), project `BRIEF.md` (+ the resolved `code_ref` implementation when declared), `<thread>/refs/` + shared `research/`, `rubric.md`.
**Writes**: `<thread>.{N}.audit/` with `verdict.md`, `findings.md`, `comments.md`, `_summary.md`, `_meta.json`, `_progress.json`.

The audit sibling is **read-only once written**. Revisions consume it; they never modify it.

## Scope boundary: Phase 1 vs. Phase 2 (#707)

**This command doc ships the audit's SHAPE and dispatch in Phase 1; the three-way verdict LOGIC lands in Phase 2 (#707).** Read this boundary before implementing:

- **Phase 1 (this doc, now)**: describes the `code_ref` consistency sweep at the skeleton level. When the sweep detects a spec claim that appears to contradict the implementation, the auditor records a **`major` finding** (quoting the spec claim AND the implementation location) and surfaces the *ambiguous fix direction* to the operator in the verdict prose. Phase 1 **does NOT adjudicate direction** and **NEVER auto-rewrites the spec to match the code**.
- **Phase 2 (#707, deferred)**: the full three-way verdict — (a) **spec wrong** → revise the spec; (b) **code wrong** → operator escalation (file an issue; never silently rewrite the spec to canonize a vestigial code path); (c) **intentional target-state gap** → record in a first-class **implementation-status register** section (live vs. target per component). Phase 2 also introduces the "Implementation contradicts normative claim" *critical flag* (rubric flag 3) as a fully-adjudicated verdict rather than the Phase-1 `major` finding. **Extension point**: the step-5 sweep below is where Phase 2 slots the three-way adjudication; leave it structured so Phase 2 extends rather than rewrites.

The motivating incident (SKILL.md §Audit verdict) is why direction is never presumed: the botho near-miss almost rewrote the spec to canonize a vestigial code path contradicting an accepted ADR. The audit must **never** presume the code is right.

## Outputs

```
<thread>.{N}.audit/
  verdict.md       Audit verdict + critical/major audit-flag paragraphs (factual + spec↔implementation)
  findings.md      Per-claim table: Claim | Kind (factual/implementation-consistency) | Verified? | Evidence / cited source
  comments.md      Line-level audit comments keyed to the body
  _summary.md      Machine-readable audit blocks: code_ref resolution, findings counts
  _meta.json       { critic, role, started, finished, model, schema_version, scorecard_kind: "human-verdict",
                     rubric_id: "anvil-spec-v1", rubric_total: 44, advance_threshold: 39 }
  _progress.json   Phase state for the auditor
```

**Atomicity** (issues #350, #376): written atomically via `anvil/lib/sidecar.py` — files staged under `.<thread>.{N}.audit.tmp/`, atomically renamed on clean completion; stale staging from a prior interrupt of THIS critic removed by `cleanup_one_staging(<thread>.{N}.audit)` at entry.

## Procedure

1. **Discover state, sweep, open sidecar**: find the highest `N` with `<thread>.{N}/<thread>.tex`; run `cleanup_one_staging(<thread>.{N}.audit)`; if `<thread>.{N}.audit/` exists, exit early (idempotent). Otherwise open `staged_sidecar(final_dir=<thread>.{N}.audit, required_files=["verdict.md", "findings.md", "comments.md", "_summary.md", "_meta.json", "_progress.json"])` and write everything inside the staging dir. Initialize `_progress.json` and `_meta.json` with `scorecard_kind: "human-verdict"`, **`rubric_id: "anvil-spec-v1"`, `rubric_total: 44`, `advance_threshold: 39`** (per-review version stamping, issue #346).

   **Non-Python-driver ordering (fail-open, manual fallback)** — as in `spec-review` step 1, a driver-less session uses the CLI shim (`python -m anvil.lib.sidecar stage/commit/cleanup <thread>.{N}.audit --required verdict.md,findings.md,comments.md,_summary.md,_meta.json,_progress.json`) or, as a last resort, the manual `mv`-based staging (write every required file into `.<thread>.{N}.audit.tmp/`, `_progress.json` last, then `mv` as the last step; stamp `_meta.json` with `"atomicity_fallback": "manual-mv"`). Never write straight into the final `<thread>.{N}.audit/` name. (If your agent harness pattern-matches and rejects the `findings.md` filename on a `Write`, a Bash-heredoc write into the staging dir is an accepted fallback — see `anvil/lib/snippets/critics.md` §"Orchestrator output-file guard collisions".)

2. **Read inputs**: the body, the matching BRIEF `documents:` entry, `<thread>.{N}/_progress.json` (the drafter's self-check + `metadata.code_ref_resolved`), `<thread>/refs/` + shared `research/`.
3. **Resolve the code_ref (conditional — the consistency oracle)**: invoke `anvil/lib/project_brief.py::resolve_code_ref(<project_dir>, <slug>)` per SKILL.md §Code-ref contract.
   - **When active** (declared and resolves): read (or index) the resolved implementation. It is the **consistency oracle** for the sweep at step 5. Record the resolved implementation path(s) for the `_summary.md.code_ref` block. Cache it for step 5.
   - **When inactive** (no `code_ref` declared): record a **`major` finding recommending the operator declare `code_ref`** — without a declared implementation the consistency sweep cannot run and the class's defining constraint is unenforceable (a defect to surface, not a crash). The spec↔implementation sweep does not run. Do NOT invent an implementation contract.
   - **Declared-but-missing implementation (bad path / empty glob)**: the tier ACTIVATES; `resolve_code_ref` returns `missing: true` (never raises). Surface the broken declaration as a **`major` finding** directing the operator to fix the path; the consistency sweep does not run (graceful degradation — the `report` customer-context / `primer` spec-ref posture). **No false critical flag, no raised exception.**
4. **Factual / internal-logic audit (always runs)**: walk every load-bearing claim, formula, and predicate in the spec. For each, record a `findings.md` row (`Claim | Kind: factual | Verified? | Evidence`). A claim that is *internally* wrong (a dimensionally-unsound formula, an unsatisfiable predicate, a misused cited primitive) is a factual finding scored under rubric dim 5; a claim that is code-mismatched is the step-5 consistency sweep. **Diagram content is in scope**: a state-machine or message-flow diagram whose steps contradict the normative prose it illustrates is a factual finding (quote the diagram step and the prose it fights). The auditor reads the diagram *source* — it does not need the rendered PNG.
5. **Spec↔implementation consistency sweep (conditional — active `code_ref` only)** — **the Phase-2 extension point**: for each normative claim that touches something the implementation defines (a constant, a struct/field layout, a formula, a validity predicate), cross-check against the resolved implementation. Record each on a `findings.md` row (`Claim | Kind: implementation-consistency | Verified?: matches/contradicts/unverified | Evidence: <impl file:line>`).
   - **A claim that MATCHES the implementation** → verified; note it.
   - **A claim that appears to CONTRADICT the implementation** → **Phase-1 posture: a `major` finding**, NOT an adjudicated critical flag. Quote BOTH the spec claim AND the contradicting implementation location in `verdict.md`, and **surface the ambiguous fix direction to the operator** ("this may be a spec-wrong, code-wrong, or intentional-target-state case — the direction is a human decision; see Phase 2 / #707"). **Never** conclude the code is authoritative and **never** recommend rewriting the spec to match it. This is exactly the near-miss the class exists to prevent.
   - When the tier is inactive or unresolvable (step 3), skip this sweep entirely — the finding cannot fire.
   - **Phase 2 (#707) replaces this bullet's `major`-finding posture** with the three-way verdict (spec-wrong / code-wrong / intentional-gap), the implementation-status register cross-check (a claim marked target-state in the register is NOT a contradiction), and the promotion of an unadjudicated-and-unregistered contradiction to the "Implementation contradicts normative claim" critical flag. Structure the sweep so Phase 2 extends this step rather than rewriting it.
6. **Identify audit-side flags** — each with a one-paragraph justification in `verdict.md`:
   - **Suspected implementation/spec mismatch** (Phase 1 → `major` finding, per step 5; Phase 2 → three-way verdict + critical flag): a spec claim appears to disagree with the resolved implementation. Cannot fire when `code_ref` is undeclared or unresolvable.
   - (Factual internal-logic problems are dim-5 findings, not flags, unless they rise to a spec that describes a non-functional system — an auditor may note a suspected showstopper as a `major` finding for the reviser.)

   If none: "Critical flags: none. Major findings: <count>."
7. **Verdict** into `verdict.md`: audit-flag counts, `audit_clean: true` iff zero unresolved audit **critical** flags (Phase 1 has none of its own — a suspected mismatch is a `major` finding, so a Phase-1 audit with only `major` findings is `audit_clean: true` but carries revision priorities). (The auditor does not score the /44 rubric — that is `spec-review`; the auditor's output is the factual + consistency verdict the reviser combines with the review verdict.) List the top audit priorities: any suspected mismatch first (with its ambiguous-direction note), then other `major` findings (missing/unresolvable `code_ref`, internal-logic problems).
8. **Write `_summary.md`** (inside the staging dir): the audit block `{ "critic": "audit", "rubric_id": "anvil-spec-v1", "audit_clean": <bool>, "factual_findings": <count>, "implementation_mismatch_findings": <count>, "phase": 1 }`, and — **only when the code_ref tier is active** — the `code_ref` block `{ran: true, resolved: <path(s)>, missing: <bool>, mismatch_findings: <count>}` (+ `missing: [...]` when the declared implementation was absent). When the tier is inactive the `code_ref` block is NOT emitted (the recommendation lives in the `major` finding).
9. **Finalize `_meta.json` + `_progress.json`** inside the staging dir (`_progress.json` LAST), then exit the `staged_sidecar` block — manifest verified, staging dir atomically renamed to `<thread>.{N}.audit/`.
10. **Report**: e.g., `Audited botho-consensus.1 → audit clean (no critical flags), code_ref active, 2 suspected spec/impl mismatches surfaced as major findings pending the Phase-2 three-way verdict. Next: spec-revise botho-consensus (after spec-review)`.

## What spec-audit does NOT do

- **Never edits the body.** Read-only against `<thread>.{N}/`.
- **Never auto-rewrites the spec to match the implementation.** A suspected mismatch is surfaced with its ambiguous fix direction for the operator; direction is a human decision (Phase 2 / #707). This is the load-bearing safety property of the class.
- **Never scores the /44 rubric** — that is `spec-review`. The auditor produces the factual + consistency verdict only.
- **Never crashes on a missing/unresolvable `code_ref`** — `resolve_code_ref` never raises; the broken declaration is a `major` finding and the consistency sweep is skipped (graceful degradation).
- **Never fires a consistency finding when `code_ref` is undeclared or unresolvable** — no false finding.
- **Does NOT implement the three-way verdict or the implementation-status register** — that is Phase 2 (#707). Phase 1 records suspected mismatches as `major` findings only.

## Scorecard kind

This critic emits the `human-verdict` scorecard kind per `anvil/lib/snippets/scorecard_kind.md`. `_meta.json` MUST include `"scorecard_kind": "human-verdict"` plus the three rubric-stamping fields (`"rubric_id": "anvil-spec-v1"`, `"rubric_total": 44`, `"advance_threshold": 39`).

## Git sync (opt-in, off by default)

Per `anvil/lib/snippets/git_sync.md`: if `.anvil/config.json` exists and `git.commit_per_phase` is `true`, end this phase: stage only the dirs this phase wrote, commit as `anvil(<skill>/<phase>): <thread>.{N} [<state>]`, push if `git.push` is `true`. Git failures warn and continue. Default off.

This phase's specifics:

- **Ordering**: after the staged-sidecar atomic rename (issue #350) lands the final-named `<thread>.{N}.audit/`.
- **Staging target**: ONLY this command's own `<thread>.{N}.audit/`.
- **Commit**: `anvil(spec/audit): <thread>.{N} [AUDITED]`.
