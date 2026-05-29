---
name: ip-uspto-claims
description: Claim breadth and dependency-tree critic. Evaluates the claim ladder — independent claim scope, dependent claim coverage of fallback positions. Owns rubric dimension 1, contributes to dimension 3.
---

# ip-uspto-claims — Claims critic

**Role**: claims critic.
**Reads**: latest `<thread>.{N}/claims.tex` + `<thread>.{N}/spec.tex` + (if present) `<thread>/BRIEF.md` for inventive feature ground truth.
**Writes**: `<thread>.{N}.claims/` with `_summary.md`, `findings.md`, `_meta.json`, `_progress.json`.

The claims sibling is **read-only once written**. Critical flags short-circuit convergence.

## Rubric dimensions

| # | Dimension | Weight | Ownership |
|---|---|---|---|
| 1 | Claim breadth & dependency structure | 5 | **Primary** |
| 3 | §112(b) definiteness | 5 | Joint with `s112` |

The claims critic focuses on the *strategic* side of claim drafting (scope, ladder, fallback positions) and the *structural* side (dependency tree, claim count). §101 statutory issues are the s101 critic's job; §112 statutory issues are the s112 critic's job. The claims critic's job is "are these the right claims to file?"

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/claims.tex`.
- **Brief** (`<thread>/BRIEF.md`): the inventor's enumeration of inventive features. The claims critic uses this to check whether the claim ladder picks up the major fallback positions described in the brief.

## Outputs

```
<thread>.{N}.claims/
  _summary.md       Critic tag claims, critical flag, dim 1 (and dim 3 contribution) scores
  findings.md       Per-claim and per-ladder findings
  _meta.json        { critic, role, started, finished, model, schema_version }
  _progress.json    Phase state for the claims critic
```

## Procedure

1. **Discover state, resume, init `_progress.json`** (standard).
2. **Read inputs**: `claims.tex`, `spec.tex`, optionally `BRIEF.md`.

### Parse the claim tree

3. Extract every claim. For each, capture:
   - Claim number.
   - Independent or dependent. If dependent, what claim(s) it depends on (single or multiple).
   - Preamble (e.g., "A widget", "A method for X").
   - Transitional phrase (`comprising` | `consisting of` | `consisting essentially of`).
   - Body limitations.
4. Build a tree: independents at the roots, dependents as children of their parents.

### Evaluate Dimension 1 — Claim breadth & dependency structure (score 0–5)

5. **Independent claim breadth check** (per independent claim):
   - Is the claim too narrow (reciting a specific embodiment rather than the inventive concept)? Too-narrow independent claims sacrifice scope unnecessarily.
   - Is the claim too broad (reciting only the inventive concept abstractly without a tangible embodiment)? Too-broad claims invite §101 and §112(a) rejections.
   - Does the independent claim cover the principal inventive feature(s) from `BRIEF.md` §3?
6. **Claim type diversity**: a well-drafted application usually has 2–3 independent claims covering different aspects (e.g., apparatus + method + system; or apparatus + method + computer-readable medium for software inventions). One independent claim is a missed opportunity unless the invention truly has one face.
7. **Dependent ladder coverage**: for each independent claim, the dependents should narrow toward fallback positions that:
   - Pick up specific embodiments from `BRIEF.md` §4.
   - Pick up alternative materials/ranges/configurations from `BRIEF.md` §5.
   - Provide intermediate scope between the independent and the narrowest known practical embodiment.
   - Each dependent should add a meaningfully different limitation; redundant dependents waste claim count budget.
8. **Multiple-dependent rule** (37 CFR 1.75(c)): no multiple-dependent claim may depend on another multiple-dependent claim. Catches missed by pre-flight should be flagged here as well.
9. **Claim count budget**:
   - ≤20 total claims and ≤3 independent claims is "free" (no excess fees).
   - 21+ total or 4+ independents incurs USPTO fees. NOT a quality issue but worth noting.
   - >30 total or >5 independents is excessive without strong justification.
10. **Score Dimension 1**:
    - Independents are well-scoped (broad enough to matter, narrow enough to grant); diverse claim types; dependent ladder picks up all major brief features and provides intermediate scope; within fee-budget: **5**.
    - All independents scoped well, dependent ladder strong, one specific gap (e.g., missing a dependent that narrows to a specific embodiment): **4**.
    - Independent claim scope is defensible but the ladder is sparse, missing several brief features: **3**.
    - One independent is clearly too narrow (sacrificing scope) OR too broad (inviting rejection); ladder structure is haphazard: **2**.
    - Independent claim scope is fundamentally wrong (doesn't cover the inventive concept, or is anticipated on its face): **0–1** (critical flag).

### Contribute to Dimension 3 — Definiteness (score 0–5, optional)

11. The claims critic notices definiteness issues even though s112 is the primary owner:
    - Confused dependency phrasing.
    - Inconsistent claim-internal terminology (uses "widget" in body, "device" in preamble).
    - Score Dim 3 if observations are substantive; leave `null` to defer to s112.

### Identify critical flags

12. Set `flagged: true` if any of:
    - An independent claim is **clearly anticipated** by a reference in `<thread>/prior-art/` (a single reference discloses every limitation). NOTE: this overlaps with the prior-art critic; flag whichever critic notices it first.
    - An independent claim is so broad that it fails Alice/Mayo on its face (notify s101 critic via finding; do not double-flag).
    - An independent claim does NOT cover the principal inventive feature from `BRIEF.md` §3 — the application would issue (if at all) without protecting the actual invention.
    - The dependent ladder is missing the obvious narrowing fallback to the only described working embodiment (a §112-adjacent failure: the granted scope cannot retreat to a safe harbor under amendment).

### Write outputs

13. **Write `_summary.md`** with 8-row scorecard (only Dim 1 and optionally Dim 3 scored).
14. **Write `findings.md`** with itemized findings, organized by claim then by ladder.
15. **Write `_meta.json`** and finalize `_progress.json`.
16. **Report**: e.g., `claims: acme-widget.2.claims/ → D1=4 (1 ladder gap on claim 1 family); D3 deferred to s112`.

## Idempotence and resumability

Standard.

## Notes for the claims critic agent

- **The independent claim is the patent.** Spend most of your attention there. A great spec with a 4/5 dependent ladder around a 2/5 independent is a worse patent than a 5/5 independent with a thin ladder.
- **Don't grade on prose.** Claim language is intentionally formal and stilted. Score on scope and structure, not readability.
- **Claim differentiation matters.** Each claim should add something — either narrower scope (dependents) or a different mode of claiming (independents). Pure restatement of the same scope across claims is wasteful.
- **Multiple-dependent claims are powerful but expensive.** They count as N claims for fee purposes (where N is the number of antecedents). Use them when the dependent applies to several parents; avoid when only one parent.
- **Score Dim 3 only when adding signal.** If s112 will obviously catch the antecedent issue, leave Dim 3 null. Contribute only when noticing something s112 might miss (e.g., subtle inter-claim inconsistency).

## `_progress.json` snippet

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
