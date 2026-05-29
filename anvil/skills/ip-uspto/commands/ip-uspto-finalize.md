---
name: ip-uspto-finalize
description: Finalize command for the ip-uspto skill. Assembles the submission package (PDFs, ADS placeholder, fee sheet placeholder, inventorship attestation) from an AUDITED version. Does NOT file with USPTO — that is a human + Patent Center action.
---

# ip-uspto-finalize — Finalizer

**Role**: finalizer.
**Reads**: AUDITED `<thread>.{N}/` + `<thread>/inventorship.md` (must be locked + current).
**Writes**: `<thread>.final/` with assembled submission package + `_manifest.json` + `_progress.json`.

This is the terminal command. After `ip-uspto-finalize` succeeds, the package is ready for human attorney review and submission via USPTO Patent Center.

## Inputs

- **Thread slug** (positional argument).
- **AUDITED version directory**: highest `N` with `<thread>.{N}.audit/_summary.md` recording `passed: true`.
- **Inventorship matrix**: `<thread>/inventorship.md` — frontmatter `matrix_locked: true` AND `generated_against` must reference the current version's `claims.tex`.
- **Optional cover materials**: `<thread>/cover/` for any attorney-provided overrides (custom ADS data, fee classification, small-entity / micro-entity declarations).

## Outputs

```
<thread>.final/
  spec.pdf                       Rendered specification (via pdflatex against anvil-uspto class)
  drawings.pdf                   Assembled drawings PDF (one figure per page, ordered FIG. 1 ... FIG. N)
  abstract.txt                   Copy of abstract.txt (USPTO requires it as a separate part of the application data)
  claims.tex                     Copy of claims (for reference; also embedded in spec.pdf)
  ads-placeholder.txt            Application Data Sheet placeholder — human attorney fills final ADS via Patent Center
  fee-sheet-placeholder.txt      Fee schedule placeholder with claim-count-based fee estimate
  inventorship-attestation.md    Final inventorship matrix snapshot with attestation block ready for human signoff
  README.md                      Submission package contents + Patent Center filing instructions
  _manifest.json                 Machine-readable manifest of all artifacts with hashes
  _progress.json                 Phase state with finalize: done
```

## Procedure

1. **Discover state**:
   - Find the highest `N` with `<thread>.{N}.audit/_summary.md` containing `passed: true`. If none, exit with an error: "no version is AUDITED; run `ip-uspto-audit` first."
   - Check whether `<thread>.final/` already exists. If yes AND `_progress.json.finalize.state == done` AND `_manifest.json` parses, exit early (idempotent).
2. **Resume check**: delete partial `<thread>.final/` output from a crashed run.
3. **Initialize `<thread>.final/_progress.json`**.

### Pre-flight gates (must all pass before producing the package)

4. **Audit gate**: `<thread>.{N}.audit/_summary.md` records `passed: true`. (Verified in step 1.)
5. **Inventorship matrix gate**:
   - `<thread>/inventorship.md` exists.
   - Frontmatter `matrix_locked: true`.
   - Frontmatter `generated_against` references `<thread>.{N}/claims.tex` (the current version).
   - If any gate fails, exit with a `BLOCKED` notice naming the specific gate and the remedial action (e.g., "re-run ip-uspto-inventorship to regenerate against thread.{N}/claims.tex, then have attorney attest").
6. **Pre-flight currency gate**: `<thread>.{N}.preflight/_summary.md` records `passed: true` (or all blockers were waived in an override file).

### Assemble the package

7. **Compile `spec.pdf`** by invoking `pdflatex` on `<thread>.{N}/spec.tex`:
   - Working directory: a temp build directory to avoid polluting the version dir.
   - Command: `pdflatex -interaction=nonstopmode -output-directory=<temp> <thread>.{N}/spec.tex`.
   - If the build fails, capture the LaTeX log, write it to `<thread>.final/spec.build.log`, AND emit a finalize error: "spec.tex did not compile cleanly; see build log. Common causes: missing anvil-uspto.cls in TEXINPUTS, syntax error in spec, undefined macro." Do NOT produce a partial package.
   - On success, copy the resulting `spec.pdf` into `<thread>.final/`.
8. **Compile `drawings.pdf`**:
   - For each rendered figure in `<thread>.{N}/drawings/*.pdf`, concatenate (via `pdfunite` or equivalent) in figure order.
   - For stub-only figures (no rendered PDF), include a placeholder page noting "FIG. N — pending illustrator. See drawing-descriptions.md."
   - If ALL figures are stubs (no PDFs at all), emit a WARNING in the package README: "All drawings are stubs pending illustrator. Submission incomplete without illustrator output." This is a warning, NOT a blocker — finalize still produces the package, and the operator decides whether to wait.
9. **Copy `abstract.txt` and `claims.tex`** verbatim.
10. **Generate `ads-placeholder.txt`**:

    ```
    APPLICATION DATA SHEET (PLACEHOLDER) — USPTO 37 CFR 1.76

    This placeholder is NOT a filable ADS. The human attorney must produce the final ADS via USPTO Patent Center (https://patentcenter.uspto.gov) using the following data:

    Inventor information (from <thread>/inventorship.md):
      Inventor 1: <name from inventorship.md>
        Residence: [ATTORNEY TO COMPLETE]
        Mailing address: [ATTORNEY TO COMPLETE]
        Citizenship: [ATTORNEY TO COMPLETE]
      Inventor 2: <name>
        ...

    Application information:
      Title: <title from spec.tex>
      Filing type: Non-provisional utility, AIA (post-March 2013)
      Total claims: <N>
      Independent claims: <M>
      Drawings: <count>

    Correspondence address: [ATTORNEY TO COMPLETE]
    Application data:
      Domestic priority: [ATTORNEY TO COMPLETE if claiming benefit]
      Foreign priority: [ATTORNEY TO COMPLETE if applicable]
      Government interest statement: [ATTORNEY TO COMPLETE if applicable]

    Assignee: [ATTORNEY TO COMPLETE]

    Notes:
      - All [ATTORNEY TO COMPLETE] fields must be filled before submission.
      - Inventor declarations (37 CFR 1.63) are filed separately; this skill does not generate them.
      - Small-entity / micro-entity status must be elected on the ADS.
    ```

11. **Generate `fee-sheet-placeholder.txt`** with a claim-count-based fee estimate:

    ```
    USPTO FEE SCHEDULE PLACEHOLDER

    This placeholder reflects the claim count and gives a rough fee estimate at standard (large entity) rates. Actual fees depend on entity status and current USPTO fee schedule (https://www.uspto.gov/learning-and-resources/fees-and-payment).

    Claim count: <N> total, <M> independent.

    Estimated fees (large entity, USD, as of last-known schedule — verify current rates):
      Basic filing fee (utility, non-provisional): $XXX
      Search fee: $XXX
      Examination fee: $XXX
      Excess claims fee (claims beyond 20): max(0, N - 20) × $XXX = $YYY
      Excess independent claims fee (independents beyond 3): max(0, M - 3) × $XXX = $YYY
      Multiple-dependent claim fee (if any): $XXX × <count> = $YYY

      Estimated total (large entity): $TTTT

    Adjustments:
      Small entity: ~50% reduction (verify eligibility under 37 CFR 1.27).
      Micro entity: ~75% reduction (verify eligibility under 37 CFR 1.29).

    [ATTORNEY TO FINALIZE based on current fee schedule + entity status.]
    ```

12. **Generate `inventorship-attestation.md`**: copy `<thread>/inventorship.md` content verbatim with a final note appended: "This snapshot is the inventorship matrix as of finalize. Any post-finalize change to claims may require re-attestation and an amended ADS / corrected declarations under 37 CFR 1.48."
13. **Generate `README.md`** for the package:

    ```markdown
    # Submission package — <thread>

    Generated <ISO timestamp> from <thread>.{N}/ (AUDITED).

    ## Contents

    | File | Purpose |
    |---|---|
    | spec.pdf | Specification, ready for filing |
    | drawings.pdf | Assembled drawings |
    | abstract.txt | Abstract (≤150 words) |
    | claims.tex | Claims source (for attorney reference) |
    | ads-placeholder.txt | Application Data Sheet placeholder — finalize via Patent Center |
    | fee-sheet-placeholder.txt | Fee estimate based on claim count |
    | inventorship-attestation.md | Inventorship matrix + attestation block |
    | _manifest.json | Machine-readable manifest with file hashes |

    ## Filing instructions

    1. Human attorney reviews all contents.
    2. Attorney fills `[ATTORNEY TO COMPLETE]` fields in ads-placeholder.txt.
    3. Attorney verifies current USPTO fee schedule and entity status; updates fee-sheet-placeholder.txt accordingly.
    4. Each inventor signs the 37 CFR 1.63 declaration (NOT generated by this skill — use Patent Center forms).
    5. Attorney submits via USPTO Patent Center: spec.pdf + drawings.pdf + final ADS + declarations + fee payment.
    6. Patent Center issues an Application Number and Filing Receipt; save these in the thread root.

    ## Warnings

    - <conditional> All drawings are stubs pending illustrator. Do NOT file without rendered drawings unless explicitly intended.
    - <conditional> Audit had N major findings (non-blocker) that were not addressed; review the findings.md before filing.
    - This package is a drafting aid. Final responsibility for filing decisions rests with the licensed human attorney.
    ```

14. **Generate `_manifest.json`** with SHA-256 hashes of every artifact:

    ```json
    {
      "thread": "<slug>",
      "from_version": <N>,
      "generated_at": "<ISO>",
      "artifacts": [
        { "path": "spec.pdf", "sha256": "...", "bytes": 123456 },
        { "path": "drawings.pdf", "sha256": "...", "bytes": 78901 },
        { "path": "abstract.txt", "sha256": "...", "bytes": 1234 },
        { "path": "claims.tex", "sha256": "...", "bytes": 5678 },
        { "path": "ads-placeholder.txt", "sha256": "...", "bytes": 2345 },
        { "path": "fee-sheet-placeholder.txt", "sha256": "...", "bytes": 1234 },
        { "path": "inventorship-attestation.md", "sha256": "...", "bytes": 3456 },
        { "path": "README.md", "sha256": "...", "bytes": 2345 }
      ],
      "warnings": [],
      "stub_drawings_count": 0,
      "audit_passed": true,
      "preflight_passed": true,
      "inventorship_locked": true
    }
    ```

15. **Update `_progress.json`**: `phases.finalize.state = done`, `phases.finalize.completed = <ISO>`.
16. **Report**: e.g., `Finalized acme-widget.final/ from acme-widget.3/. 7 artifacts written, 0 warnings. Next: human attorney review + Patent Center submission.`

## Failure handling

- **Gate failures** (audit not done, inventorship stale or unlocked, pre-flight failed) — exit with a `BLOCKED` notice + remedial action. No partial package.
- **LaTeX build failure** — exit with build log written but no PDFs. No partial package.
- **Stub drawings present** — emit warning, produce package with placeholder drawings pages. Operator decides whether to file as-is or wait for illustrator.

## Idempotence

- A finalized package (`_progress.json.finalize.state == done` AND `_manifest.json` exists and parses) is never re-built.
- To re-finalize (e.g., after a small post-audit fix), delete `<thread>.final/` first.
- For a major fix that requires re-revision, return through the revise → review → revise → audit → finalize cycle; do NOT edit `<thread>.final/` directly.

## Notes for the finalizer agent

- **This is the last automated step. After this, humans run the show.** The package's job is to make the human attorney's review as fast and as low-risk as possible.
- **Never silently degrade.** A failed LaTeX build, a stub-only drawing set, a stale inventorship matrix — these are all surfaced as errors or warnings. The operator decides.
- **The manifest is the integrity record.** SHA-256 every artifact. If a downstream step or human edit changes a file, the manifest is the way to detect it.
- **The ADS and fee sheet are placeholders by design.** USPTO Patent Center has dedicated forms; this skill does not duplicate them. The placeholders give the attorney the data they need to fill the Patent Center forms quickly.
- **Filing is a human action.** Period.

## `_progress.json` snippet (final dir)

```json
{
  "version": 1,
  "thread": "<slug>",
  "from_version": <N>,
  "phases": {
    "finalize": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```
