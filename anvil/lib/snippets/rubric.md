# Rubric scoring shape and convergence logic

Every anvil skill ships a `rubric.md` with 8 weighted dimensions summing
to /40. This snippet documents the SHAPE only — every skill picks its
own dimension names, weights, and thresholds. The lib does not impose a
canonical dimension list (every observed skill has a different one).

## Shape requirements

A skill rubric MUST:

1. Define exactly **8 dimensions** numbered 1–8.
2. Assign each dimension an integer **weight** (in points).
3. Have weights that **sum to 40**.
4. Declare an **advance threshold** (integer, in points out of 40).
5. Declare a **critical-flag** list (one-paragraph definitions of
   "any of these blocks regardless of total").

A skill rubric MAY:

- Document a calibration guide ("a score of N means ...") per
  dimension.
- Override critical-flag definitions per consumer
  (`rubric.overrides.md`).
- Document which critic owns which dimension (for skills with multiple
  specialists; see `critics.md`).

## Observed thresholds across v0 skills

| Skill | Threshold | Critical-flag count |
|---|---|---|
| memo | ≥32/40 | 4 examples + open-ended |
| pub | ≥32/40 | 5 examples + open-ended |
| slides | ≥32/40 | 3 hard rules (audit / density / time) + open-ended |
| deck | ≥35/40 | 4 hard rules (fabricated traction / fabricated team / market-math / absent ask) |
| report | ≥35/40 | 4 hard rules + open-ended |
| ip-uspto | ≥35/40 | §101 + §112 hard rules (each short-circuits) + open-ended |

The recurring pattern: customer-facing or legal-facing artifacts use
≥35; internal or rough-draft-friendly artifacts use ≥32. New skills
should pick from this binary by audience class.

## Convergence logic

A version `<thread>.{N}/` advances out of the convergence loop when:

```
advance = (composite_total >= threshold) AND (no critical flag)
```

Both conditions must hold. Either falsy condition triggers another
revise iteration (within the `max_iterations` cap).

The composite total is computed by the reviser per the aggregation
rules in `critics.md` (per-dimension mean of non-null contributions
across all critic siblings, summed).

## Critical-flag semantics

Critical flags are NOT a sub-score deduction. They are a binary
short-circuit:

- **Critical flag set** → block regardless of total. Even a 38/40
  with one critical flag does not advance.
- **Critical flag NOT set** → fall back to the score-vs-threshold
  check.

This matches the intuition that some defects cannot be averaged away:
a deck with fabricated traction does not become more truthful by being
well-designed; a paper with a citation error does not become more
correct by being well-written.

## Dimension scoring guidance (applies to all skills)

1. **Justify every score.** Each per-dim score in `scoring.md`
   carries 1–3 sentences of justification citing specific evidence
   from the artifact (section heading, slide number, excerpt, exhibit
   reference). A score without justification is not a useful signal
   for the reviser.

2. **Be calibrated, not encouraging.** The rubric exists to surface
   problems early. A reviewer who scores generously to spare the
   drafter's feelings wastes a revision iteration.

3. **Integer scores only.** No half-points. If you cannot decide
   between 4 and 5, that is a 4 with a justification that explains
   what would push it to 5 on the next iteration.

4. **Critical flags are not bonus points.** A flag is "this would
   stop a sophisticated reader cold". Set them when warranted; do
   not set them for stylistic concerns or polish issues (those live
   in comments at severity `minor` or `nit`).

## Citation-quality dimensions (optional, opt-in per skill)

Skills that produce sourced artifacts may name two of their dimensions
using the canonical citation-quality vocabulary:

- **`citation_recall`** — claims-with-citations / total-claims. How
  much of the artifact's load-bearing content is sourced.
- **`citation_precision`** — claims-supported-by-cited-source /
  claims-with-citations. How well the cited sources actually back the
  claims they're attached to.

Both are integer scores on the same /weight scale as any other
rubric dimension. The two-dim shape (rather than one combined
"citation hygiene" dimension) lets each axis move independently —
high recall with low precision is a different failure mode than the
inverse.

This is **opt-in**, not mandatory. Skills that don't produce sourced
artifacts (`anvil:deck`, `anvil:slides`) leave them out entirely.
Skills that do (`anvil:pub`, `anvil:report`, `anvil:memo`,
`anvil:ip-uspto`) may name two of their eight dimensions accordingly.
The lib does not enforce or detect this naming — it documents the
convention so the eventual citation auditor critic can populate
identifiable per-dimension scores per the existing partial-scorecard
rule (see `critics.md`).

### Per-consumer rubric migration

The canonical "8 dimensions summing to /40" shape is preserved by
**splitting** an existing citation-related dimension rather than
adding two new ones outside the /40 envelope. Worked examples:

| Skill | Before | After |
|---|---|---|
| `anvil:pub` | dim 8 "Citation hygiene", weight 5 | `citation_recall` + `citation_precision`, weights 2 + 3 (or any split summing to 5) |
| `anvil:report` | dim 4 "Evidence trail / citation", weight 6 | `citation_recall` + `citation_precision`, weights 3 + 3 |

The migration is per-skill and **not in scope** for the lib PR. Each
consumer skill that opts in does so in its own follow-up PR (rubric.md
edit + the owning critic's command spec).

STORM (stanford-oval/storm) reports 84.83% / 85.18% on these dimensions
in its retrieval-grounded essay generation, useful as calibration
anchors when authoring a new rubric.

## Rubric override mechanism

Every skill ships `rubric.md` in its source-controlled root. Consumers
override via `.anvil/skills/<skill>/rubric.overrides.md` in their own
repo. The override file:

- **Adds** critical-flag examples specific to the consumer's domain.
- **May tune** dimension calibration guidance.
- **Cannot reduce** the base rubric — overrides are additive only.

The reviewer command loads both files (base + override) and applies
both during scoring.

## See also

- `critics.md` — how multi-critic aggregation produces the composite
  per-dimension score and critical flag.
- `scorecard_kind.md` — how the reviser knows what file shape to read
  from each critic.
- `state_machine.md` — where the convergence check sits in the
  lifecycle.
