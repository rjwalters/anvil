---
name: ip-uspto-review
description: General reviewer critic for the ip-uspto skill. Owns rubric dimensions 6 (specification completeness), 7 (drawing-text correspondence), and 8 (formal compliance). Writes a sibling .review/ directory with the uniform critic output schema.
---

# ip-uspto-review — General reviewer

**Role**: general reviewer critic.
**Reads**: latest `<thread>.{N}/` (all of `spec.tex`, `claims.tex`, `abstract.txt`, `drawings/`).
**Writes**: `<thread>.{N}.review/` with `_summary.md`, `findings.md`, `_meta.json`, `_progress.json`.

The reviewer sibling directory is **read-only once written**. Revisions consume it; they never modify it.

## Rubric dimensions owned

Per `rubric.md` ownership map:

| # | Dimension | Weight |
|---|---|---|
| 6 | Specification completeness | 5 |
| 7 | Drawing-text correspondence | 5 |
| 8 | Formal compliance (37 CFR 1.71–1.84) | 5 |

The reviewer MAY also contribute scores to dimensions it does not primarily own (e.g., it may notice a §112(b) antecedent-basis issue and score Dimension 3 — but the s112 critic is the primary owner). When the reviewer contributes a non-owned score, that score participates in the mean aggregation alongside the primary critic's score.

For dimensions 1–5 (claim breadth, §112, §101, novelty), the reviewer leaves the score as `null` unless it has a specific observation.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/spec.tex`.
- **Rubric**: `anvil/skills/ip-uspto/rubric.md`.
- **Optional consumer override**: `.anvil/skills/ip-uspto/rubric.overrides.md` (additional critical-flag examples; never reduces the base rubric).

## Outputs

```
<thread>.{N}.review/
  _summary.md       Critic tag, critical flag, per-dimension scorecard (owns 6, 7, 8), top revision priorities
  findings.md       Itemized findings (severity, location, rationale, suggested fix)
  _meta.json        { critic, role, started, finished, model, schema_version, scorecard_kind: "machine-summary" }
  _progress.json    Phase state for the reviewer
```

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/spec.tex`. If `<thread>.{N}.review/_progress.json.review.state == done` and `_summary.md` exists, exit early (idempotent).
2. **Resume check**: if a prior crashed review exists, delete partial output and re-review.
3. **Initialize `_progress.json`** for the review dir.
4. **Read inputs**: load all of `<thread>.{N}/` and `rubric.md` + any consumer override.
   - **Consult `_outline.json`** as the structural ground truth for coherence checks. The outline records the section render plan (ids, order, `claim_tree`, per-feature `subsections`, figure list, `drawn_from` pointers from claims into the detailed description). Use it to:
     - confirm every claim in `claim_tree` traces to a detailed-description subsection via `drawn_from`;
     - confirm the abstract's coverage aligns with the `summary` section's `key_points`;
     - confirm the figures enumerated in `brief-description-of-drawings.figures` correspond to entries in `drawings/drawing-descriptions.md`.
   - The reviewer is NOT required to score `_outline.json` itself or enforce its presence — the drafter and reviser own that contract. The outline is a *reading aid* for coherence checks; light-touch adoption only at this stage.
5. **Evaluate Dimension 6 — Specification completeness** (score 0–5):
   - Are FIELD, BACKGROUND, SUMMARY, BRIEF DESCRIPTION, DETAILED DESCRIPTION present and proportionate?
   - Does the detailed description cover every inventive feature claimed in CLAIMS?
   - Are embodiments, alternatives, and ranges present where the brief specified them?
   - Score per the calibration guide in `rubric.md`.
   - Justification: cite specific spec section(s).
6. **Evaluate Dimension 7 — Drawing-text correspondence** (score 0–5):
   - For each reference numeral in `spec.tex`, does it appear in at least one drawing (or drawing stub description)?
   - For each reference numeral in drawings, does it appear in `spec.tex`?
   - Does `BRIEF DESCRIPTION OF DRAWINGS` list every figure in `drawings/`?
   - Are figure captions consistent between brief description and the drawing files themselves?
   - In v0, drawings are typically stubs; the check is against `drawing-descriptions.md` entries until figures are rendered.
   - Score per calibration.
7. **Evaluate Dimension 8 — Formal compliance** (score 0–5):
   - This dimension partially overlaps with `ip-uspto-pre-flight`. Pre-flight catches the deterministic violations; the reviewer adds judgment on:
     - Section heading prose quality (not just presence).
     - Paragraph-level structure within `DETAILED DESCRIPTION` (well-organized? logical flow?).
     - Claim drafting conventions (preamble style, transitional phrase: `comprising`/`consisting of`/`consisting essentially of`).
   - Note: if pre-flight has been run on this version (look for `<thread>.{N}.preflight/_summary.md`), incorporate its findings into the rationale rather than re-running deterministic checks.
   - Score per calibration.
8. **Identify reviewer-level critical flags** (rare): the reviewer may set a critical flag for issues like:
   - Specification is so disorganized that examination would be impossible.
   - Drawings contradict the spec in a way that introduces indefiniteness.
   - The application as drafted does not appear to describe the invention claimed in the brief (severe spec-claim mismatch).
9. **Write `_summary.md`** in the rubric's specified format. Per-dimension scorecard has all 8 rows but only 6, 7, 8 carry scores (others are `null` with justification `n/a — see <other critic>`).
10. **Write `findings.md`** with itemized findings (severity, location, rationale, suggested fix). Findings group by dimension.
11. **Write `_meta.json`** and finalize `_progress.json` to `done`.
12. **Report**: print the path and a one-line status (e.g., `Reviewed acme-widget.2 → acme-widget.2.review/ (D6=4, D7=3, D8=5; no critical flag)`).

## Idempotence and resumability

- Completed review is never re-run.
- Crashed review is re-runnable after deleting partial output.
- Validation is by file existence (does `_summary.md` exist and parse?), not solely by flag.

## Notes for the reviewer agent

- **Specification completeness ≠ length.** A 60-page spec that fails to describe an inventive feature scores worse than a 20-page spec that covers everything.
- **Drawing correspondence is mechanical but high-leverage.** Orphan reference numerals on either side are the single most common issue in first drafts. Be thorough.
- **Defer to pre-flight on the mechanical Dim 8 stuff.** Read its findings (if present) and incorporate by reference, then add judgment on the things pre-flight can't measure (prose quality, claim-drafting voice).
- **Be terse in findings.** The reviser is reading every critic's findings. Long-form justification belongs in `_summary.md` per-score rationale; findings should be short and actionable.

## `_progress.json` snippet (review sibling)

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": {
    "review": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```


## Scorecard kind

This critic emits the `machine-summary` scorecard kind per `anvil/lib/snippets/scorecard_kind.md`. The `_meta.json` MUST include `"scorecard_kind": "machine-summary"` so the `ip-uspto-revise` aggregator can correctly discriminate this sibling from any `human-verdict` siblings (e.g., consumer-added narrative critics).
