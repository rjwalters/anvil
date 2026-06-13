---
name: datasheet-audit
description: Auditor command for the datasheet skill. Back-checks every numeric claim against the refs/ spec bundle, runs the pin-map and bus-width integrity checks, enforces the revision-history READY-gate, and verifies shared-die SKU coherence across sibling threads. Writes a read-only audit sibling. RUN BY DEFAULT — required to leave DRAFTED state.
---

# datasheet-audit — Auditor

**Role**: auditor (`kind: tool_evidence`).
**Reads**: latest `<thread>/<thread>.{N}/` (specifically `datasheet.tex` and its spec tables), `<thread>/refs/**` (the spec bundle), the prior version `<thread>.{N-1}/datasheet.tex` when present (revision-history gate), and sibling SKU threads' latest versions under the same project root (SKU-coherence step).
**Writes**: `<thread>/<thread>.{N}.audit/` with `verdict.md`, `findings.md`, `evidence.md`, `_meta.json`, and `_progress.json`. Bare `<thread>.{N}/` references below are shorthand for these nested paths.

The audit sibling directory is **read-only once written**. Revisions consume it; they never modify it.

This is one of the **two REQUIRED critic siblings** (the other is `datasheet-review`). Both must complete before a thread can leave `DRAFTED`; they run in parallel.

**This command is run by default.** A datasheet's numbers are commitments a customer designs against — exactly the `kind: tool_evidence` class the audit phase exists for (per `anvil/lib/snippets/audit.md`). The canary's hand audit caught four wrong numbers that read fine in isolation (die area, ISP resize, inference input size, an unrepresentable bus range); this command is that audit, made systematic. Four of the rubric's five critical flags are audit-owned.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/datasheet.tex`.
- **Spec bundle**: `<thread>/refs/**` — model/quant/RTL exports, foundry quotes, package drawings, characterization data. Text-readable files (`.md`/`.txt`/`.json`) are read as authoritative; PDFs/images are presence-only (back-check against a `.md` companion or BRIEF-surfaced content; PDF extraction deferred per issue #167). A datasheet without a spec bundle is auditable on internal consistency + pin-map/bus-width alone; the verdict prose MUST flag the sheet as un-back-checkable.
- **Prior version**: `<thread>.{N-1}/datasheet.tex` when `N > 1` — the revision-history gate input.
- **Sibling threads**: datasheet threads named in the project-level `BRIEF.md` `documents:` list sharing this thread's `family` — the SKU-coherence input. Resolve each sibling's latest version via `anvil/lib/latest_resolution.py`'s tolerant helper (walk-to-highest-`N` fallback when the operator maintains no convenience symlink; see also `anvil/lib/cross_thread_refs.py`).
- **Rubric** (audit-side flags): `anvil/skills/datasheet/rubric.md` (flags 1, 2, 3, 5 are audit-owned).

## Outputs

```
<thread>.{N}.audit/
  verdict.md       Pass/fail + critical flags + coverage summary + top revision priorities
  findings.md      Per-claim audit log (spec back-checks, pin-map, bus-width, rev-history gate, SKU coherence)
  evidence.md      Source → dependent-claims traceability map
  _meta.json       { critic: "audit", scorecard_kind: "human-verdict", rubric_id: "anvil-datasheet-v1",
                     rubric_total: 44, advance_threshold: 39, ... }
  _progress.json   Phase state for the auditor (phase: audit, for_version: N)
```

**Atomicity**: written atomically via `anvil/lib/sidecar.py::staged_sidecar` with required files `["verdict.md", "findings.md", "evidence.md", "_meta.json", "_progress.json"]`, staged under `.<thread>.{N}.audit.tmp/` and renamed on clean completion. The proposal skill's `findings.md` alias contract (`claim-log.md` / `audit-findings.md` for harness-blocked contexts) applies here identically; pass the alias in the manifest when used and prepend the one-line header note.

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/datasheet.tex`. Sweep a stale staging dir via `cleanup_one_staging(<thread>.{N}.audit)` (per-critic, parallel-safe — sibling critics' staging dirs are NOT touched). If `<thread>.{N}.audit/` exists, exit early with a notice (idempotent).
2. **Open the staged sidecar** (`staged_sidecar(final_dir=<thread>.{N}.audit, required_files=[...])` as above). Inside the staging dir, initialize `_progress.json` (`phases.audit.state = in_progress`, `for_version = N`) and `_meta.json` with `scorecard_kind: "human-verdict"` plus the v0.4.0 stamping fields: `rubric_id: "anvil-datasheet-v1"`, `rubric_total: 44`, `advance_threshold: 39`.
3. **Read inputs**: load `datasheet.tex`; parse the spec tables (abs-max, recommended operating, DC/electrical, performance), the pinout block, the family/ordering table, and the revision-history table; enumerate `refs/` and partition spec-bundle materials from generic reference material per SKILL.md §"Source-of-truth materials".
4. **Build the claim inventory**: enumerate every **numeric claim** in the sheet — every spec-table value, every dimension, every count, every rate — with its location and its drafter-cited basis (`% source: refs/<file>` comments, Notes-column entries). Claims with no cited basis still enter the inventory (basis: none).
5. **Spec source-of-truth cross-check** — the central check (critical flag 1 territory). For each claim whose subject a spec-bundle document covers, resolve the claim against the source and record a four-valued verdict per `rubric.md` §"Refs back-check (dim 1)":
   - **`VERIFIED`** — claim matches the source.
   - **`UNVERIFIED`** — an on-topic source exists but does not contain the supporting value (1-point dim 1 deduction).
   - **`CONTRADICTED`** — the source directly contradicts the claim (2-point dim 1 deduction AND **critical flag 1**). The canary's catches are the calibration set: die area 3.08 vs the model's 3.33 mm²; ISP resize 300×300 vs the model's 320×320; inference input 32×96 vs 48×192.
   - **`NOT-IN-REFS`** — no source covers the claim's subject (informational; counted in coverage).
   Record each in `findings.md`:
   ```
   | # | Location | Claim | Basis | Verdict | Notes |
   |---|----------|-------|-------|---------|-------|
   | 1 | §2 family table | "die area 3.08 mm²" | refs/model-export.json | CONTRADICTED | source says 3.33 mm² — critical flag 1 |
   | 2 | §4 ISP | "resize to 320×320" | refs/quant-config.json | VERIFIED | matches input_size |
   ```
   Additionally flag any spec **lacking a cited source** (basis: none, verdict NOT-IN-REFS) in a dedicated findings subsection — "where did this come from" visibility for the reviser.
6. **Pin-map + bus-width integrity** — the mechanical checks (critical flag 2 territory). Run `anvil/skills/datasheet/lib/pinmap_check.py::check_pinmap(<tex source>)` and `anvil/skills/datasheet/lib/buswidth_check.py::check_buswidths(<tex source>)`. Record each violation as a findings row (location = the pinout block / the bus marker line) and raise **critical flag 2** per violation class. Independently of the markers, cross-check the pinout against any package drawing companion in `refs/` (ballout names, pin counts) and re-derive bus capacities for any N-bit field the prose claims a range for that lacks a marker (a missing marker does not exempt the claim from judgment — it only exempts it from the mechanical check).
7. **Internal-consistency cross-check** (dim 2, flag-2-adjacent): any quantity stated in more than one section must agree — product-brief header vs family table vs package/mechanical section; performance header vs typical-application text; ordering-info package vs pinout package. Every disagreement is a findings row; a disagreement on a customer-load-bearing value (package, pinout, abs-max) is a critical-flag candidate under the open-ended rule.
8. **Revision-history READY-gate** (critical flag 3 territory). When `N > 1`:
   - Diff the spec-bearing content between `<thread>.{N-1}/datasheet.tex` and `<thread>.{N}/datasheet.tex`: spec-table values, pinout rows, ordering info, package data. (Judgment over a real diff in v1 — run a textual diff and classify changed lines as spec-bearing vs prose-only.)
   - If spec-bearing content changed AND (the revision-history table has no new row relative to `N-1` OR the `rev` value did not change), raise **critical flag 3 (spec change without revision-history entry)** with the changed values enumerated in the justification.
   - Prose-only changes do not trigger the gate. Record the gate outcome (ran / not-applicable / passed / flagged) in `findings.md` and the coverage summary.
9. **Shared-die SKU coherence** (critical flag 5 territory). When sibling SKU threads exist in the project (same `family`):
   - Read each sibling's latest `datasheet.tex` (highest-`N` version dir, per the Inputs note above).
   - Compare the **shared-die spec blocks**: process node, die dimensions, package(s), absolute maximum ratings, DC characteristics, and any block `refs/sibling-shared-specs.md` explicitly names as shared.
   - A divergence on a shared spec is **critical flag 5** (one of the sheets is wrong — name both values and both threads in the justification). Per-SKU specs (network, performance, ordering codes) must be *differentiated*, not identical — an identical performance table across SKUs with different networks is itself a findings row (likely copy-paste residue).
   - Single-SKU project: record the step as inactive in the coverage summary. (Automated byte-diff of marked shared blocks is a Phase-3 follow-up; v1 is documented audit judgment.)
10. **Provenance spot-check** (flag 4, shared with review): for `status: preliminary`, walk the electrical/performance tables for bare values no provenance label or notice covers; raise **critical flag 4** for any pre-silicon value presented as measured/final.
11. **Build the evidence map** in `evidence.md`: invert the claim inventory — list every source (each spec-bundle file, each inline derivation) and, for each, the claims that depend on it. This surfaces unsourced specs (a claim depending on nothing) and single-source risk.
12. **Compute pass/fail**: `pass = (no critical flags) AND (no CONTRADICTED claims) AND (rev-history gate holds) AND (mechanical checks pass or are inactive-with-rationale)`.
13. **Write `verdict.md`** per `rubric.md` §"Verdict format": pass/fail; coverage (claims back-checked + VERIFIED/UNVERIFIED/CONTRADICTED/NOT-IN-REFS split, pin-map/bus-width results, rev-history gate outcome, SKU-coherence siblings compared); critical flags with location + evidence; top revision priorities if failing.
14. **Update `_progress.json`**: `phases.audit.state = done`, `phases.audit.completed = <ISO>` — the LAST write before the context manager exits; exit the `staged_sidecar` block (manifest verify + atomic rename).
15. **Report**: print the path and a one-line status (e.g., `Audited ax101-objdet.1 → ax101-objdet.1.audit/ (pass: false, 2 critical flags [spec CONTRADICTED ×1, pinmap ×1]; 41 claims: 33 VERIFIED, 3 UNVERIFIED, 1 CONTRADICTED, 4 NOT-IN-REFS)`).

## Idempotence and resumability

- A completed audit (`<thread>.{N}.audit/` exists) is never re-run. Re-invoking is a no-op with a notice.
- A crashed audit leaves only a `.tmp` staging dir, removed by the step 1 sweep.

## Parallel-with-review semantics

This command makes NO attempt to coordinate with `datasheet-review`. Both read the same `<thread>.{N}/`; they write to disjoint sibling paths; neither reads the other's output. The pin-map/bus-width checkers run in both deliberately — they are cheap, deterministic, and the two siblings reach `BLOCK` independently. The split is principled per `anvil/lib/snippets/audit.md`: the reviewer owns subjective quality (`kind: judgment`); the auditor owns externally-verifiable correctness (`kind: tool_evidence`).

## Notes for the auditor agent

- **You are not a reviewer.** Layout, prose economy, and application-guidance quality are out of scope; defer them to the review sibling. Your job is that the numbers are **traceable, internally consistent, mechanically valid, and honestly labeled**.
- **A claim that reads fine in isolation is exactly the target.** All four canary catches were plausible numbers. Never accept a value because it "looks reasonable" — resolve it against the source or record NOT-IN-REFS.
- **Re-derive, don't trust.** Bus capacities (2^W), pin counts vs package, table totals, repeated quantities across sections — derive them independently and flag mismatches.
- **The rev-history gate is not bureaucracy.** A customer diffs revisions to find what changed. A corrected number with no history row is a silent spec change — flag it even when the correction itself is right.
- **Quantify your coverage** in `verdict.md`: exactly how many claims were inventoried, back-checked, and in which verdict bucket; which siblings the coherence step compared; whether the gate ran.

## `_progress.json` / `_meta.json` snippets (audit sibling)

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": {
    "audit": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

```json
{
  "critic": "audit",
  "role": "datasheet-audit.md",
  "started":  "<ISO>",
  "finished": "<ISO>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict",
  "rubric_id": "anvil-datasheet-v1",
  "rubric_total": 44,
  "advance_threshold": 39
}
```

Merge rule (shallow): preserve fields not touched by this command. ISO-8601 UTC timestamps per `anvil/lib/snippets/timestamp.md`.

## Git sync (opt-in, off by default)

Per `anvil/lib/snippets/git_sync.md` (`.anvil/lib/snippets/git_sync.md` in an installed consumer repo): if `.anvil/config.json` exists and `git.commit_per_phase` is `true`, end this phase: stage only the dirs this phase wrote, commit as `anvil(<skill>/<phase>): <thread>.{N} [<state>]`, push if `git.push` is `true`. Git failures warn and continue — never fail the phase. When the config or knob is absent, skip this step entirely (default off).

This phase's specifics:

- **Ordering**: after the staged-sidecar atomic rename (issue #350) lands the final-named `<thread>.{N}.audit/` — so only complete sidecars are ever committed.
- **Staging target**: ONLY this command's own `<thread>.{N}.audit/` sidecar (never sibling critics' dirs — the narrow scope keeps the hook safe under parallel critic fan-out).
- **Commit**: `anvil(datasheet/audit): <thread>.{N} [<state>]` (the bracket carries the thread's derived state per SKILL.md §State machine after the audit lands — `AUDITED` when the audit sits alongside a `READY` version).
