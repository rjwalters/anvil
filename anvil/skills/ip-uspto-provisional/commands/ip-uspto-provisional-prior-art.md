---
name: ip-uspto-provisional-prior-art
description: Prior-art positioning critic for the ip-uspto-provisional skill. Evaluates the disclosure (not claims — there may be none) against operator-supplied prior art. Does NOT do its own patent search. Owns rubric dimension 5. Stamps anvil-ip-provisional-v1 (/45, ≥39).
---

# ip-uspto-provisional-prior-art — Prior-art critic

**Role**: prior-art positioning critic.
**Reads**: latest `<thread>.{N}/spec.tex` (+ optional `claims.tex`) + `<thread>/prior-art/**` (operator-supplied).
**Writes**: `<thread>.{N}.priorart/` with `_summary.md`, `findings.md`, `_meta.json`, `_progress.json`.

The priorart sibling is **read-only once written**.

## Scope and important non-scope

This critic evaluates the disclosure against prior art the **operator supplied** in `<thread>/prior-art/`. It does **not** perform its own patent search (same non-scope as `anvil:ip-uspto`'s prior-art critic). If `<thread>/prior-art/` is empty or absent, it writes a `_summary.md` noting that, leaves Dimension 5 `null`, and finishes `done` — a legitimate state, not an error.

**No anticipation verdicts.** With claims optional (and unexamined either way), there is no §102/§103 claim-by-claim adjudication to run. The provisional question is different: does the *disclosure* position the invention against the known art so the eventual conversion can be drafted around it, and does the spec avoid poisoning that conversion?

## Rubric dimension owned (per `rubric.md`)

| # | Dimension | Weight |
|---|---|---|
| 5 | Prior-art positioning | 4 |

## Outputs

```
<thread>.{N}.priorart/
  _summary.md       Critic tag priorart, rubric block, critical flag, dim 5 score, per-reference positioning table
  findings.md       Per-reference analysis (severity, location, rationale, suggested fix)
  _meta.json        { critic, role, started, finished, model, schema_version, scorecard_kind: "machine-summary",
                      rubric_id: "anvil-ip-provisional-v1", rubric_total: 45, advance_threshold: 39 }
  _progress.json    Phase state for the priorart critic
```

**Atomicity** (issues #350, #376): written atomically via `anvil/lib/sidecar.py` — staged under `.<thread>.{N}.priorart.tmp/`, atomic rename on completion; entry sweep via `cleanup_one_staging(<thread>.{N}.priorart)`; sibling staging dirs untouched.

## Procedure

1. **Discover state, sweep, open sidecar**: highest `N` with `<thread>.{N}/spec.tex`; `cleanup_one_staging(<thread>.{N}.priorart)`; if `<thread>.{N}.priorart/` exists, exit early. Otherwise open `staged_sidecar(final_dir=<thread>.{N}.priorart, required_files=["_summary.md", "findings.md", "_meta.json", "_progress.json"])`; all writes inside the staging dir. Initialize `_progress.json` and `_meta.json` with `scorecard_kind: "machine-summary"`, **`rubric_id: "anvil-ip-provisional-v1"`, `rubric_total: 45`, `advance_threshold: 39`** (issue #346 stamping).
2. **Check prior-art supply**: enumerate `<thread>/prior-art/**` (markdown summaries preferred — frontmatter `title`/`inventors`/`publication_date`/`kind`/`summary`; PDFs excerpt-and-summarize; per-reference subdirs accepted). If empty: write `_summary.md` with Dim 5 `null` and the "no prior art supplied — operator may add references and re-run" note, plus `findings.md` / `_meta.json` / `_progress.json`, and exit the sidecar context (`done`).
3. **Read the disclosure**: spec in full, with the Background section read twice — once for content, once for **admissions**.

### Evaluate Dimension 5 — prior-art positioning (score 0–4)

4. **Distinguishing disclosure check**: for each supplied reference, does the spec *describe* (not merely assert) what the inventive features do differently — at enough depth that a conversion drafter could recite the distinction as a limitation? "Unlike prior approaches, the present system is better" is assertion; a described mechanism difference is positioning.
5. **Admission scan**: identify any Background language characterizing a supplied reference (or its approach) as prior art. Admissions bind the entire application family, including the conversion. Flag any admission that covers an inventive feature.
6. **Swallowed-disclosure check**: does any single supplied reference describe substantially the same mechanism as a named inventive feature? With no claims to anticipate this is not a §102 verdict — but a feature the art already shows is a feature whose conversion claims will fail, and the inventors should know now. Severity scales with how central the feature is.
7. **Calibration**:
   - All inventive features positioned with described mechanism differences; no admissions; nothing swallowed: **4**.
   - Positioning present but thin for one or two references: **3**.
   - A central feature's distinction asserted but never described: **2**.
   - A supplied reference substantially shows a named inventive feature, or an admission covers one: **0–1** (critical flag when the headline feature is the one covered).

### Critical flags

8. Set `flagged: true` if:
   - The Background **admits a supplied reference as prior art** that fully discloses the headline inventive feature.
   - A single supplied reference substantially discloses the headline inventive feature and the spec offers no described distinction (filing would create a false sense of protection).

### Write outputs

9. **Write `_summary.md`**: 9-row scorecard (only Dim 5 scored, or `null` when no art supplied; others `n/a — see <owning critic>`), the rubric block `{ "id": "anvil-ip-provisional-v1", "total": 45, "advance_threshold": 39, "dimensions": 9 }`, and a per-reference positioning table:

   ```markdown
   ## Positioning matrix

   | Reference   | Closest feature | Distinction described? | Admission risk | Note |
   |-------------|-----------------|------------------------|----------------|------|
   | smith-2019  | BRIEF#3.1       | yes (¶[0018]–[0021])   | none           | clean |
   | jones-2021  | BRIEF#3.2       | asserted only          | Background ¶3  | strengthen mechanism contrast |
   ```

10. **Write `findings.md`**: one section per (reference × relevant feature) pair; each finding carries the spec location and the concrete language fix (and, where the right fix is new disclosure, the question for the inventors).
11. **Finalize `_meta.json` + `_progress.json`** inside the staging dir (`_progress.json` LAST), exit the `staged_sidecar` block (manifest verified, atomic rename to `<thread>.{N}.priorart/`).
12. **Report**: e.g., `priorart: acme-widget-prov.1.priorart/ → D5=3/4, no flag (jones-2021 distinction asserted-only — see findings)`.

## Idempotence and resumability

Standard. Re-running after the operator adds references is expected — but since the sibling at `N` is immutable once written, added art is evaluated on the NEXT version's pass (or the operator removes the sibling before re-running on an un-reviewed version).

## Notes for the priorart agent

- **No prior art supplied is a legitimate state.** Score `null`, note it, return `done`. Do not invent references.
- **Admissions are the provisional-specific trap.** A careless Background sentence costs nothing today and binds the conversion forever.
- **You are positioning a disclosure, not adjudicating claims.** Keep the §102/§103 vocabulary out of the verdict; it returns at conversion time in `anvil:ip-uspto`.

## `_progress.json` snippet

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": { "priorart": { "state": "done", "started": "<ISO>", "completed": "<ISO>" } }
}
```

## Scorecard kind

This critic emits the `machine-summary` scorecard kind per `anvil/lib/snippets/scorecard_kind.md`. `_meta.json` MUST include `"scorecard_kind": "machine-summary"` plus the three rubric-stamping fields (`"rubric_id": "anvil-ip-provisional-v1"`, `"rubric_total": 45`, `"advance_threshold": 39`).
