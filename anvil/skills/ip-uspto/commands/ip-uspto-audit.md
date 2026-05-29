---
name: ip-uspto-audit
description: Final fact-check audit pass on a READY application. Verifies citations, dates, inventor names, reference numerals across spec/claims/drawings/abstract. Runs only after convergence (READY_FOR_AUDIT marker present).
---

# ip-uspto-audit — Auditor

**Role**: auditor.
**Reads**: latest `<thread>.{N}/` (entire content) plus `<thread>/BRIEF.md` and `<thread>/inventorship.md` for ground-truth checks.
**Writes**: `<thread>.{N}.audit/` with `_summary.md`, `findings.md`, `_meta.json`, `_progress.json`.

The audit sibling is **read-only once written**. A failed audit blocks `ip-uspto-finalize`.

## When this runs

The audit is a **post-convergence** phase. It runs only when:
1. The current version has `_revise-result.md` recording `READY_FOR_AUDIT`, AND
2. No audit sibling exists yet for this version.

The audit is NOT one of the parallel critics. It runs once per terminal version, after convergence. Its role is fact-checking, not scoring.

## Inputs

- **Thread slug** (positional argument).
- **READY version directory**: highest `N` with `<thread>.{N}/_revise-result.md` recording `READY_FOR_AUDIT`.
- **Ground-truth sources**:
  - `<thread>/BRIEF.md` — for inventor names, field of use, intended invention.
  - `<thread>/inventorship.md` — for the canonical inventor list and roles.
  - `<thread>/prior-art/**` — for verifying any prior-art citations or admissions in the spec.

## Outputs

```
<thread>.{N}.audit/
  _summary.md       Pass/fail boolean + per-check status
  findings.md       Itemized findings (severity, location, rationale, suggested fix)
  _meta.json        { critic: "audit", role: "ip-uspto-audit.md", started, finished, model, schema_version }
  _progress.json    Phase state for the audit
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/_revise-result.md` containing `READY_FOR_AUDIT`. If no such version exists, exit with an error: "no version is READY_FOR_AUDIT; complete the revise cycle first."
2. **Idempotence check**: if `<thread>.{N}.audit/_progress.json.audit.state == done` AND `_summary.md` exists, exit early.
3. **Resume check**: delete partial output from crashed run.
4. **Initialize `_progress.json`**.

5. **Run audit checks** (collect findings; do not short-circuit):

   ### Check 1 — Inventor name consistency
   - Inventors in `spec.tex` front matter MUST match exactly (spelling, ordering, affiliation) the inventors in `<thread>/inventorship.md` frontmatter.
   - Inventors in `inventorship.md` MUST match `<thread>/BRIEF.md` frontmatter.
   - Any mismatch → severity `blocker`.

   ### Check 2 — Title and field-of-use consistency
   - `spec.tex` title must match `BRIEF.md` frontmatter `title` (or be a clearly equivalent restatement).
   - Field of use stated in `spec.tex` FIELD section must match `BRIEF.md` frontmatter `field_of_use`.
   - Mismatch → severity `major`.

   ### Check 3 — Reference numeral coherence (full)
   - For every reference numeral appearing in `spec.tex`, the same numeral must appear in at least one figure (or figure stub description) referring to the same component.
   - For every reference numeral in any drawing or stub, the numeral must appear in `spec.tex`.
   - The component name associated with a numeral must be **consistent** across spec and drawings (e.g., `12` cannot mean "input port" in spec and "housing" in fig-2).
   - Each kind of inconsistency → severity `blocker`.

   ### Check 4 — Date and citation verification
   - For every cited reference (in Background or elsewhere), check that the publication date precedes the inventor's stated priority date (`BRIEF.md` frontmatter `priority_date_target`). A reference cited as prior art with a date *after* priority cannot be prior art — flag as either a date error or an inadvertent admission.
   - For citations to `<thread>/prior-art/` references, verify the citation text matches the reference's stated `title` / `inventors` / `publication_date`.
   - Mismatch → severity `blocker` if it affects patentability analysis, `major` otherwise.

   ### Check 5 — Claim-spec terminology consistency
   - Terms introduced in claims (`the widget`, `the processor configured to`) must appear in the spec with consistent meaning.
   - Terms used in spec that are NOT in any claim are not a finding (the spec may describe more than is claimed).
   - Terms in claims with NO support in the spec → severity `blocker` (overlaps with s112(a), but the audit catches what slipped through).

   ### Check 6 — Abstract correctness
   - The abstract states what the invention IS — verify against the SUMMARY section. The abstract should not introduce new claim scope.
   - Abstract word count ≤150 (overlaps with pre-flight; audit re-checks).
   - Abstract does not contain phrases like "the present invention" (USPTO style preference) or legal conclusions ("novel" / "patentable").
   - Severity `minor` to `major` depending on issue.

   ### Check 7 — Numerical consistency
   - For every numeric value or range in the spec that also appears in claims (e.g., "between 5 GHz and 10 GHz"), verify exact agreement.
   - Spec stating "5 GHz to 10 GHz" while a dependent claim recites "5 GHz to 12 GHz" is a `blocker` finding.

   ### Check 8 — Background admissions audit
   - Re-read the BACKGROUND section. Identify any sentence that could be construed as admitting a particular reference or product is prior art under §103.
   - In US practice, applicant's own admissions in the spec are binding. Flag any unintentional admissions for the reviser/attorney to consider rewording.
   - Severity `major`.

   ### Check 9 — Inventorship matrix currency
   - `<thread>/inventorship.md` frontmatter `generated_against` must reference the current version's `claims.tex` (not an earlier version), OR the matrix must be re-run before finalize.
   - If stale → severity `blocker` (this is a finalize blocker; the audit surfaces it early).
   - If `matrix_locked: false` in frontmatter → severity `blocker` (no attorney signoff yet).

   ### Check 10 — Drawing-stub completeness (v0 specific)
   - In v0, drawings are typically stubs (`drawings/drawing-descriptions.md`). Verify each stub has all four required fields (Type, Components shown, Spatial relationships, Annotations/lead lines).
   - If figures have been rendered (TikZ or external), spot-check that each renders cleanly under the build pipeline.
   - Severity `minor` (informational; figures are typically completed by a human illustrator).

6. **Determine pass/fail**:
   - Pass iff no finding has severity `blocker`.
   - `major` findings do not block but should be addressed where feasible.
7. **Write `_summary.md`**:

   ```markdown
   ---
   critic: audit
   for_version: <N>
   passed: <true|false>
   ---

   # Audit summary — <thread>.<N>

   | Check | Result | Findings |
   |---|---|---|
   | 1. Inventor name consistency | pass | - |
   | 2. Title / field-of-use consistency | pass | - |
   | 3. Reference numeral coherence (full) | fail | 2 (orphans on reference 22 and 34) |
   | 4. Date / citation verification | pass | - |
   | 5. Claim-spec terminology | pass | - |
   | 6. Abstract correctness | pass | - |
   | 7. Numerical consistency | pass | - |
   | 8. Background admissions | major | 1 (Background ¶[0008] could be construed as admitting Smith-2019 as prior art) |
   | 9. Inventorship matrix currency | fail | 1 (matrix generated against thread.2/claims.tex; current is thread.3) |
   | 10. Drawing-stub completeness | pass | - |

   **Overall**: <PASS | FAIL — 3 blockers>

   See `findings.md` for details.
   ```

8. **Write `findings.md`** in the standard format.
9. **Write `_meta.json`** and finalize `_progress.json`.
10. **Report**: e.g., `Audit: acme-widget.3.audit/ → FAIL (3 blockers: ref-numeral orphans, inventorship matrix stale). Next: address blockers via ip-uspto-revise or ip-uspto-inventorship.`

## Failure handling

A failed audit (any `blocker` finding) blocks `ip-uspto-finalize`. The operator should:
- Address blockers via `ip-uspto-revise <thread>` (this creates a new version; the cycle re-runs critics + pre-flight + re-audit). The aggregate score check still applies — addressing audit blockers doesn't bypass the rubric.
- For the inventorship-matrix-stale finding specifically, run `ip-uspto-inventorship <thread>` to regenerate the matrix against the current claims, then have the human attorney re-attest.

## Idempotence and resumability

- Completed audit on a version is never re-run (it's tied to a specific version that's immutable).
- A new version requires a new audit cycle.
- Crashed audit is re-runnable after deleting partial output.

## Notes for the auditor agent

- **The audit catches what the critics let through.** Critics evaluate against the rubric; the audit catches mechanical and factual issues that don't fit the rubric (inventor name typos, date errors).
- **Spec admissions are binding.** Background section re-read is high-leverage. An inadvertent admission can lose a patent at litigation.
- **Inventorship matrix currency is mandatory.** This is the most common audit finding when revisions change the claim set. Always check.
- **Severity discipline.** Blocker = patent could be invalid or unenforceable. Major = should be fixed but won't tank the application. Minor = quality of life.

## `_progress.json` snippet (audit sibling)

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
