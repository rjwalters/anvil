---
name: ip-uspto-provisional-review
description: General reviewer critic for the ip-uspto-provisional skill. Owns rubric dimensions 4 (drawings sufficiency & correspondence), 6 (specification completeness), 7 (formal compliance, provisional posture), 8 (terminology & reference-numeral consistency), and jointly 9 (conversion readiness). Scores against the 9-dimension /45 anvil-ip-provisional-v1 rubric (≥39 advance threshold).
---

# ip-uspto-provisional-review — General reviewer

**Role**: general reviewer critic.
**Reads**: latest `<thread>.{N}/` (all of `spec.tex`, `drawings/`, optional `claims.tex`, `_outline.json`) + `<thread>/BRIEF.md`.
**Writes**: `<thread>.{N}.review/` with `_summary.md`, `findings.md`, `_meta.json`, `_progress.json`.

The review sibling is **read-only once written**. Revisions consume it; they never modify it.

## Rubric dimensions owned (per `rubric.md`)

| # | Dimension | Weight |
|---|---|---|
| 4 | Drawings sufficiency & drawing-text correspondence | 5 |
| 6 | Specification completeness | 5 |
| 7 | Formal compliance (provisional posture) | 3 |
| 8 | Terminology & reference-numeral consistency | 3 |
| 9 | Conversion readiness (joint with `s112`) | 6 |

The reviewer MAY contribute a non-owned score when it has a specific observation (it participates in the mean); otherwise dims 1, 2, 3, 5 stay `null` — the `s112` and `priorart` critics own them.

## Outputs

```
<thread>.{N}.review/
  _summary.md       Critic tag review, rubric block, critical flag, dims 4/6/7/8/9 scores, top revision priorities
  findings.md       Itemized findings (severity, location, rationale, suggested fix)
  _meta.json        { critic, role, started, finished, model, schema_version, scorecard_kind: "machine-summary",
                      rubric_id: "anvil-ip-provisional-v1", rubric_total: 45, advance_threshold: 39 }
  _progress.json    Phase state for the reviewer
```

**Atomicity** (issues #350, #376): written atomically via `anvil/lib/sidecar.py` — files staged under `.<thread>.{N}.review.tmp/`, atomically renamed on clean completion; stale staging from a prior interrupt of THIS critic removed by `cleanup_one_staging(<thread>.{N}.review)` at entry; sibling critics' staging dirs never touched.

## Procedure

1. **Discover state, sweep, open sidecar**: find the highest `N` with `<thread>.{N}/spec.tex`; run `cleanup_one_staging(<thread>.{N}.review)`; if `<thread>.{N}.review/` exists, exit early (idempotent). Otherwise open `staged_sidecar(final_dir=<thread>.{N}.review, required_files=["_summary.md", "findings.md", "_meta.json", "_progress.json"])` and write everything inside the staging dir. Initialize `_progress.json` and `_meta.json` with `scorecard_kind: "machine-summary"`, **`rubric_id: "anvil-ip-provisional-v1"`, `rubric_total: 45`, `advance_threshold: 39`** (per-review version stamping, issue #346). Load `<thread>.{N-1}.review/_meta.json` when present and cache `prior_rubric_id` for the `_summary.md` rubric block (omit on first iteration).
2. **Read inputs**: all of `<thread>.{N}/`, `BRIEF.md`, `rubric.md`, plus any consumer `.anvil/skills/ip-uspto-provisional/rubric.overrides.md` (additive only). Consult `_outline.json` as the structural ground truth (figure list, feature subsection plan, optional `claim-seed` tree) — a reading aid, not a scored artifact.
3. **Dimension 4 — drawings sufficiency & correspondence (0–5)**:
   - Does every feature whose understanding requires a figure have one (rendered or stub in `drawing-descriptions.md`)?
   - Every `\refnum{N}` in spec appears in a drawing/stub; every numeral in drawings/stubs appears in spec; brief-description-of-drawings lists every figure; captions consistent.
4. **Dimension 6 — specification completeness (0–5)**: Field, Background, Summary, Brief Description of Drawings, Detailed Description present and proportionate; every `BRIEF.md` §3 feature reaches the detailed description; §6 edge cases acknowledged. Completeness ≠ length.
5. **Dimension 7 — formal compliance, provisional posture (0–3)**: title and inventor names present (cover-sheet inputs); spec compiles legibly under `anvil-uspto.cls` (class copied alongside); paragraph numbering used consistently IF used at all. **Do NOT apply non-provisional rules** — no abstract word cap, no claim numbering/count rules, no 37 CFR 1.77(b) section-order enforcement; their absence is not a deduction.
6. **Dimension 8 — terminology & reference-numeral consistency (0–3)**: one name per component used consistently across spec and drawings (a component that is "the controller" in ¶[0012] and "the processing unit" in ¶[0031] is a deduction); numerals stable and non-colliding. This is antecedent-basis groundwork for the conversion's claims.
7. **Dimension 9 — conversion readiness, drafting half (0–6, joint with `s112`)**: is each inventive feature articulated sharply enough to draft claims from — load-bearing elements individually named, narrower fallbacks visible? **Claims-optional posture**: absence of `claims.tex` is never a finding or deduction — score from the spec's articulation alone. When a claim-seed is present, well-supported seeds raise the ceiling; seed-internal drafting defects cap at `major`.
8. **Reviewer-level critical flags** (rare): spec so disorganized or internally contradictory it cannot serve as a §119(e) priority document for the invention in the brief; drawings contradicting the spec in a way that undermines the disclosure.
9. **Write `_summary.md`**: full 9-row scorecard (4/6/7/8/9 scored, others `null` with `n/a — see <owning critic>`), top-level rubric block:

   ```json
   {
     "critic": "review",
     "for_version": <N>,
     "rubric": { "id": "anvil-ip-provisional-v1", "total": 45, "advance_threshold": 39, "dimensions": 9 },
     "dimensions": { /* 9-dim partial scorecard */ },
     "critical_flag": false
   }
   ```

   Include `prior_rubric_id` in the rubric block when a prior review sibling exists (this skill ships post-#346, so the steady state is the same id; the field exists for future rubric migrations). The block is observational — it does not affect the verdict.
10. **Write `findings.md`** grouped by dimension; terse and actionable (long-form justification lives in `_summary.md`).
11. **Finalize `_meta.json` + `_progress.json`** inside the staging dir (`_progress.json` LAST), then exit the `staged_sidecar` block — manifest verified, staging dir atomically renamed to `<thread>.{N}.review/`.
12. **Report**: e.g., `Reviewed acme-widget-prov.1 → acme-widget-prov.1.review/ (D4=4/5, D6=4/5, D7=3/3, D8=2/3, D9=4/6; no critical flag)`.

**Score-history note** (issue #346): this critic does NOT write `score_history` — the reviser appends one row per completed critic pass (it is the component that computes the cross-critic aggregate), shape `{ "iteration": <N>, "total": <aggregate>, "threshold": 39, "rubric_id": "anvil-ip-provisional-v1" }` per `anvil/lib/snippets/progress.md` §"Convergence fields". See `ip-uspto-provisional-revise.md` step 6.

## Idempotence and resumability

Standard: completed review never re-run; crashed review re-runnable (the entry sweep removes the stale staging dir); validation by file existence.

## Notes for the reviewer agent

- **Drawing correspondence is mechanical but high-leverage** — orphan numerals on either side are the most common first-draft issue.
- **Hold the provisional posture firmly.** Reflexively applying non-provisional formality rules (abstract caps, claim numbering) produces noise findings the reviser must waste an iteration declining.
- **Terminology drift is cheap to fix now and expensive at conversion.** Flag every synonym pair.

## `_progress.json` snippet

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": { "review": { "state": "done", "started": "<ISO>", "completed": "<ISO>" } }
}
```

## Scorecard kind

This critic emits the `machine-summary` scorecard kind per `anvil/lib/snippets/scorecard_kind.md`. `_meta.json` MUST include `"scorecard_kind": "machine-summary"` plus the three rubric-stamping fields (`"rubric_id": "anvil-ip-provisional-v1"`, `"rubric_total": 45`, `"advance_threshold": 39`).
