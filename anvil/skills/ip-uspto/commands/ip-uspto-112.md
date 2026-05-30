---
name: ip-uspto-112
description: §112 critic. Checks (a) written description / enablement, (b) definiteness, including means-plus-function structure support. Critical-flag eligible. Owns rubric dimensions 2 and 3.
---

# ip-uspto-112 — §112 critic

**Role**: §112 critic.
**Reads**: latest `<thread>.{N}/spec.tex` + `<thread>.{N}/claims.tex`.
**Writes**: `<thread>.{N}.s112/` with `_summary.md`, `findings.md`, `_meta.json`, `_progress.json`.

The s112 sibling is **read-only once written**. Critical flags short-circuit convergence.

## Rubric dimensions owned

| # | Dimension | Weight |
|---|---|---|
| 2 | §112(a) written description & enablement | 5 |
| 3 | §112(b) definiteness | 5 |

Dimension 3 is jointly owned with `claims` — both critics may score it; the reviser aggregates by mean.

## Background — 35 U.S.C. § 112

- **§112(a) written description**: the specification must describe the invention in such full, clear, concise, and exact terms as to enable a person of ordinary skill in the art (PHOSITA) to make and use it, AND must demonstrate that the inventor was in possession of the full scope of the claimed invention at the time of filing.
- **§112(b) definiteness**: each claim must particularly point out and distinctly claim the subject matter. Ambiguity, missing antecedent basis, undefined relative terms ("about", "substantially") without spec-defined bounds, and means-plus-function claims without corresponding structure in the spec are §112(b) failures.
- **§112(f) means-plus-function**: a claim element written as "means for [function]" without structure is construed under §112(f) to cover the structure described in the spec for that function plus equivalents. If the spec discloses NO structure for the function, the claim is indefinite under §112(b).

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/claims.tex`.
- **Rubric**: `anvil/skills/ip-uspto/rubric.md`.

## Outputs

```
<thread>.{N}.s112/
  _summary.md       Critic tag s112, critical flag, dim 2 + dim 3 scores, top revision priorities
  findings.md       Per-claim and per-spec-section §112 findings
  _meta.json        { critic, role, started, finished, model, schema_version, scorecard_kind: "machine-summary" }
  _progress.json    Phase state for the s112 critic
```

## Procedure

1. **Discover state, resume, init `_progress.json`** (standard).
2. **Read inputs**: `spec.tex` and `claims.tex` in full.

### Evaluate §112(a) — written description & enablement (Dimension 2, score 0–5)

3. **Build a claim-element index**: for every claim, enumerate every limitation introduced (`a widget`, `a processor configured to`, `said widget further comprising`).
4. **For each claim limitation, search the spec for support**:
   - The limitation must be described in the spec at sufficient detail that a PHOSITA can practice it.
   - For each independent claim, verify the spec teaches the full scope. If claim 1 says "the wireless transmitter operates between 5 GHz and 80 GHz" but the spec only describes operation at 5 GHz, the claim scope exceeds written description → §112(a) failure.
5. **Enablement check**: identify any claim feature that, while described, would require undue experimentation by a PHOSITA to practice. This is rarer than written-description failures in well-drafted specs.
6. **Best mode check** (de-emphasized post-AIA but still required by §112(a) literally): the spec should describe at least one mode the inventor contemplates as preferred. Look for explicit "preferably" or "in a particularly preferred embodiment" language.
7. **Score Dimension 2**:
   - All claim limitations fully supported, spec teaches full scope, best mode disclosed: **5**.
   - All limitations supported with one or two specific weaknesses (e.g., a range edge is only described at the midpoint): **4**.
   - Some claim limitations weakly supported; partial scope coverage: **3**.
   - One or more independent claim limitations have NO spec support: **0–2** (critical flag).

### Evaluate §112(b) — definiteness (Dimension 3, score 0–5)

8. **Antecedent basis sweep**: for every "the X" or "said X" in the claims, find the prior "a X" or "an X" in the same claim chain. Missing antecedents are §112(b) failures.
9. **Means-plus-function check**: identify any claim recitation matching the pattern `means for <function>` or its functional equivalents (`module configured to`, `unit for`). For each, verify the spec describes a specific structure performing that function. If not, §112(b) indefinite (this is a **critical flag**).
10. **Relative term check**: identify uses of "about", "substantially", "approximately", "near". For each, the spec should bound the relativity (e.g., "about 100 °C" is fine if the spec says "within ±5 °C of 100 °C"; unbounded uses are §112(b) risk).
11. **Dependent claim scope check**: every dependent claim must narrow its parent. A dependent that broadens (or fails to narrow) is a §112 drafting error and often a §112(b) issue.
12. **Score Dimension 3**:
   - All antecedents clean, no MPF without structure, relative terms bounded, dependents properly narrow: **5**.
   - One or two minor antecedent issues or one unbounded relative term: **4**.
   - Multiple antecedent issues OR one MPF-without-structure (critical): **0–3**.

### Identify critical flags

13. Set `flagged: true` if any of:
    - An independent claim has a limitation with NO §112(a) written-description support.
    - A claim uses means-plus-function language with NO corresponding structure disclosed in the spec.
    - A dependent claim is broader than (or fails to narrow) its parent — this is a structural drafting failure.
    - Antecedent basis is so degraded that the claim is ambiguous as to its referents.

### Write outputs

14. **Write `_summary.md`** with full 8-row scorecard. Only dimensions 2 and 3 carry scores (others `null`). Optionally contribute to Dim 1 (claim breadth) if an obvious breadth pathology is noticed, but defer to the `claims` critic.
15. **Write `findings.md`** organized by section: §112(a) findings first, §112(b) findings second. Each finding has severity, location (with claim number and spec paragraph reference), rationale, suggested fix.
16. **Write `_meta.json`** and finalize `_progress.json`.
17. **Report**: e.g., `s112: acme-widget.2.s112/ → D2=4, D3=3, FLAGGED (claim 4 MPF without structure)`.

## Idempotence and resumability

Standard.

## Notes for the s112 agent

- **§112(a) is the most common rejection.** Examiners are aggressive about scope-support mismatches. Score conservatively when the spec only describes a narrow range and the claim spans a broad range.
- **MPF without structure is a hard kill.** A claim invalidated under §112(b) for MPF-without-structure cannot be saved by amendment in many cases (Williamson v. Citrix). Critical flag every time.
- **Dependent claim direction matters.** A dependent that "further comprises" narrows. A dependent that "wherein A may be either X or Y" can effectively broaden the parent and is a drafting trap.
- **Best mode is de-emphasized post-AIA** but still nominally required. Score minor for absence, critical only in egregious cases.
- **Defer to the claims critic on Dim 1.** s112 contributes to Dim 3 (definiteness) explicitly. Dim 1 (breadth) is the claims critic's primary.

## `_progress.json` snippet

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": {
    "s112": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```


## Scorecard kind

This critic emits the `machine-summary` scorecard kind per `anvil/lib/snippets/scorecard_kind.md`. The `_meta.json` MUST include `"scorecard_kind": "machine-summary"` so the `ip-uspto-revise` aggregator can correctly discriminate this sibling from any `human-verdict` siblings (e.g., consumer-added narrative critics).
