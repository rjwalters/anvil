---
name: ip-uspto-inventorship
description: Inventorship interview generator. Produces a per-independent-claim attribution matrix the human attorney countersigns. Run before first draft AND re-run before finalize once claims are stable.
---

# ip-uspto-inventorship — Inventorship interviewer

**Role**: inventorship interviewer.
**Reads**: `<thread>/BRIEF.md`. If a latest `<thread>.{N}/claims.tex` exists, also read it for per-claim attribution.
**Writes**: `<thread>/inventorship.md` — the inventorship matrix, with one row per independent claim and a column per named inventor.

**Why this matters**: 37 CFR 1.63 (the inventor's oath/declaration) requires correct inventorship. Mis-attributed inventorship is grounds for **unenforceability** of the issued patent — the issue can be raised during litigation and the patent invalidated. This is one of the highest-stakes correctness questions in the entire filing.

## Inputs

- **Thread slug** (positional argument).
- **`<thread>/BRIEF.md`**: required. Provides the named inventors and the inventive features.
- **`<thread>.{N}/claims.tex`** (optional): if a draft exists, the inventorship matrix attributes each independent claim's inventive concept(s) to named inventors. Without claims, the matrix attributes the inventive features from `BRIEF.md` §3.

## Outputs

```
<thread>/
  inventorship.md   Inventorship interview prompts + attribution matrix + attestation block
```

The file has the following structure:

```markdown
---
thread: <slug>
inventors:
  - name: <Full Name>
    role: <e.g., "principal investigator", "lead engineer">
generated_against: BRIEF.md  # or "thread.3/claims.tex" once claims exist
generated_at: <ISO>
matrix_locked: false           # set to true once human attorney countersigns
---

# Inventorship matrix — <thread>

## Source basis

This matrix attributes inventive contribution either to:
- (A) **Inventive features** as enumerated in `BRIEF.md` §3 (used when no claims exist yet), OR
- (B) **Independent claims** as drafted in `<thread>.{N}/claims.tex` (used once claims are stable).

Current basis: <A or B with version reference>.

## Interview prompts (give these to each named inventor)

For each <feature | claim>, ask:

1. **Who conceived this <feature | claim limitation>?** (Conception = the formation in the mind of a definite and permanent idea of the complete and operative invention. The conceiver is an inventor.)
2. **Was this conceived in collaboration?** If yes, name every collaborator and describe each person's contribution to the conception.
3. **When was this first conceived?** (Date, even approximate.)
4. **Was conception communicated to anyone (orally, in writing, code commits) before reduction to practice?** Reduction to practice (a working implementation or constructive reduction via filing) is distinct from conception.
5. **Has anyone NOT named here contributed to the conception?** (Reduction to practice alone is NOT inventorship. Lab assistants who built but did not conceive are NOT inventors.)

## Matrix

| #  | Feature or claim                                                       | Inventor 1 | Inventor 2 | Inventor 3 | Notes |
|----|------------------------------------------------------------------------|------------|------------|------------|-------|
| F1 | <feature 1 from BRIEF §3, or claim 1 from claims.tex>                  | ●          |            |            |       |
| F2 | <feature 2, or claim N>                                                | ●          | ●          |            | Joint conception over a 2-week period |
| ...|                                                                        |            |            |            |       |

Mark `●` for each inventor who conceived (in whole or part) the feature or claim limitation.

## Attribution rules

- An inventor must conceive at least one limitation of at least one issued claim to qualify. If after the matrix is filled, a named inventor has no `●` against any claim, they should be **removed** from the inventor list. Conversely, if anyone is `●` who is NOT in the named inventor list, they must be **added** (37 CFR 1.48 covers correction post-filing, but the cleaner path is to fix before filing).
- Lab assistants, technicians, and engineers who built a working implementation without conceiving are NOT inventors. Include them in the spec acknowledgments if appropriate.
- A supervisor or PI who funded or directed the work but did not conceive is NOT an inventor.
- Joint conception requires actual collaboration on the inventive concept. Two people who independently arrived at the same idea are not joint inventors of that idea; only one can be the inventor of that limitation (the earlier in time, generally).

## Attestation block (for human attorney countersignature)

I have reviewed the matrix above and the underlying interviews. I confirm:

- [ ] All conceiving inventors are named.
- [ ] No non-conceiving contributors are named.
- [ ] The matrix is consistent with the current claim set (or, if drafted pre-claims, the inventive features in `BRIEF.md` §3).
- [ ] Each named inventor has separately agreed to sign the 37 CFR 1.63 declaration.

Attorney signature: ___________________________  Date: ___________
```

## Procedure

1. **Discover state**: check whether `<thread>/inventorship.md` already exists.
   - If yes AND `matrix_locked: true` in frontmatter AND it was generated against the same basis (BRIEF.md or the same `claims.tex` version), exit early with a notice (idempotent).
   - If yes AND it was generated against an OLDER basis (claims have advanced since), back it up to `inventorship.{N-1}.md` and proceed with a fresh generation.
   - If yes AND `matrix_locked: false` and the basis is current, exit with a notice: "matrix exists and is current basis; attorney signature pending."
2. **Read inputs**:
   - `<thread>/BRIEF.md` — extract named inventors from the frontmatter and inventive features from §3.
   - Latest `<thread>.{N}/claims.tex` — if present, extract independent claims (parse `\begin{claim}...\end{claim}` blocks numbered 1, M, ... that are not dependent on a prior claim).
3. **Pick basis**:
   - If `claims.tex` exists at any version, use **basis B (claims-based)** with the highest-N version.
   - If no claims yet, use **basis A (feature-based)** from `BRIEF.md` §3.
4. **Generate the matrix**:
   - Frontmatter: thread slug, named inventors (from BRIEF), basis identifier, `generated_at` timestamp, `matrix_locked: false`.
   - Interview prompts: the 5-question list above (copy verbatim — these are legally derived).
   - Matrix: one row per feature (basis A) or per independent claim (basis B). Pre-fill `●` entries based on:
     - (basis A) The inventor most likely associated with each feature based on `BRIEF.md` context. **If uncertain, leave the cell blank and add a note "ATTRIBUTION TBD — pending inventor interview".** Never guess at attribution.
     - (basis B) The features-to-claims mapping should be evident from the spec's reference numerals and the claim language. Again, only pre-fill where the attribution is unambiguous from the source material.
   - Attribution rules: copy verbatim (these are 37 CFR 1.45 and case law derived).
   - Attestation block: copy verbatim, leave all checkboxes unchecked and attorney signature blank.
5. **Report**: print the path written and a one-line summary (e.g., `Inventorship matrix generated: acme-widget/inventorship.md (basis: thread.3/claims.tex, 3 independent claims, 2 named inventors, 4 attribution cells pre-filled, 5 marked TBD)`).

## Re-validation pre-finalize

After the claim set stabilizes (during AUDITED → FINALIZED transition), re-run this command to regenerate the matrix against the final `claims.tex`. The previous matrix is backed up. The human attorney must re-attest against the final matrix before `ip-uspto-finalize` will proceed.

## Idempotence

- A locked (`matrix_locked: true`) matrix generated against the current basis is never overwritten.
- An unlocked matrix against the current basis is preserved (a no-op with a notice).
- An out-of-date matrix is backed up before being replaced.
- The operator can force regeneration by deleting `inventorship.md`.

## Notes for the inventorship agent

- **Pre-fill conservatively.** It is far less harmful to leave a cell blank and let the human attorney fill it after interviews than to pre-fill incorrectly and have the attorney accept the bad attribution by inattention.
- **Never invent inventors.** Only the inventors named in `BRIEF.md` frontmatter may appear in the matrix.
- **Conception ≠ reduction to practice.** This distinction is the source of most inventorship errors. The matrix attribution rules document it; the matrix itself enforces it by only listing the conceiving step.
- **Re-validation is mandatory pre-finalize.** Claims often change during revision (a claim limitation gets added, removed, or shifted between independents and dependents). The matrix MUST track the final claims, not just the first-draft features.


**Snippet references**: See `anvil/lib/snippets/progress.md` for the `_progress.json` read-merge-write recipe and `anvil/lib/snippets/timestamp.md` for the ISO-8601 UTC timestamp convention. The merge is shallow: preserve fields and phases not touched by this command.
