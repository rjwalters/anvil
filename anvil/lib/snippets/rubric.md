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

### Termination resolution order

The full termination decision considers **four** terminators, evaluated
in the following order — the first match wins:

| # | Condition | Verdict | `termination_reason` |
|---|---|---|---|
| 1 | Any critical flag set | `BLOCK` | `CRITICAL_FLAG` |
| 2 | `composite_total >= threshold` | `ADVANCE` | `THRESHOLD_MET` |
| 3 | `iteration >= max_iterations` | `REVISE` | `MAX_ITERATIONS` |
| 4 | Stable: last `lookback` totals within `± window` | `STALLED` | `STALLED` |

If none of the above match, the loop continues and the next revise pass
runs.

### Secondary stop condition: stable-score termination (#27)

Near the threshold the loop can oscillate (e.g., scores 31 → 32 → 31)
without converging, burning the iteration budget on a plateaued thread.
The **secondary** stop condition halts the loop when the score has
stopped changing meaningfully:

- Compare the last `lookback` aggregated totals (default `lookback=2`,
  i.e., the two most recent iterations).
- If all of them are within `± window` of each other (default
  `window=1`), AND the latest total is below threshold, AND no critical
  flag is set, halt with `verdict: STALLED` and
  `termination_reason: "STALLED"`.

The orchestrator (or human) then decides whether to escalate, swap
critics, or accept the below-threshold result.

The `STALLED` verdict is **distinct from** `MAX_ITERATIONS`:

- `STALLED` means "the loop demonstrably plateaued" — the score is no
  longer moving.
- `MAX_ITERATIONS` means "the loop ran out of budget" — the score might
  still have been climbing, but we hit the cap. The verdict stays
  `REVISE` (work did not converge); the `termination_reason` field is
  the signal that distinguishes the two.

The input to the stable check is `metadata.score_history` from
`_progress.json` (see `progress.md`). Defaults for `window` and
`lookback` match the rationale in #27. Skills may override per-thread in
`<thread>/.anvil.json`, alongside `max_iterations`.

The Python implementation is `anvil.lib.convergence.decide_termination`,
which is the source of truth for programmatic use. This snippet is the
source of truth for LLM-side authoring. The two MUST agree.

## Judgment dimensions vs tool-evidence dimensions

Rubric dimensions split along the CRITIC tool-vs-judgment line (see
`audit.md`). A **judgment dimension** is scored from the text alone by a
strong reader; a **tool-evidence dimension** requires an external
verification step (citation resolution, build check, numeric audit,
prior-art search). The split governs *which critic scores the dimension*,
not the dimension definition itself — the same dimension name can be
scored by a `kind: judgment` review critic and (re-)scored by a
`kind: tool_evidence` audit critic at the audit phase. The aggregator
merges contributions via the standard mean-of-non-null rule; it is
indifferent to which critic kind produced the score.

The same dimension can therefore appear on both a review and an audit
critic when the artifact warrants it. For example, a `methodology`
dimension on a `pub-review` (judgment-kind) might score how clearly the
method is *described*, while the same dimension on a `pub-audit`
(tool_evidence-kind) re-scores the same dim against a tool-verified
check that the cited datasets/code actually exist and behave as
described.

### Worked example: `anvil:pub`

| Dimension | Typically scored by | Kind | Why |
|---|---|---|---|
| `clarity` | `pub-review` | `judgment` | A reader can assess prose quality from the text alone. |
| `argument_coherence` | `pub-review` | `judgment` | Argument flow is a subjective-quality check. |
| `methodology` | `pub-review` + (optionally) `pub-audit` | `judgment` + `tool_evidence` | The reviewer scores method *clarity*; the auditor re-scores method *verifiability* (does the cited dataset exist, does the code compile). |
| `citation_recall` | `pub-audit` | `tool_evidence` | Requires resolving every `\cite{}` against `refs.bib` plus an external lookup of the cited source. |
| `citation_precision` | `pub-audit` | `tool_evidence` | Requires reading the cited source to verify claim support — a tool call (or human-in-the-loop on author-supplied PDFs in `<thread>/refs/`). |
| `build_cleanliness` | `pub-audit` | `tool_evidence` | Runs `pdflatex` / `bibtex` and inspects exit codes plus the compile log. |

### Worked example: `anvil:ip-uspto`

| Dimension | Typically scored by | Kind | Why |
|---|---|---|---|
| `claim_breadth` | `ip-uspto-claims` | `judgment` | A patent attorney scores claim scope vs prior art from the spec alone. |
| `s101_eligibility` | `ip-uspto-s101` | `judgment` | Statutory-subject-matter analysis from the spec; doctrinal, not tool-augmented. |
| `s112_enablement` | `ip-uspto-s112` | `judgment` | Written-description analysis from the spec; doctrinal. |
| `prior_art_coverage` | `ip-uspto-priorart` (judgment today, `tool_evidence` once tool-augmented) | `judgment` → `tool_evidence` | When the prior-art critic searches an external corpus, it becomes a tool-evidence critic; today it ships judgment-only. |
| `inventor_consistency` | `ip-uspto-audit` | `tool_evidence` | Cross-checks `spec.tex` front matter against `inventorship.md` and `BRIEF.md` — a grep/diff tool call per inventor. |
| `reference_numeral_coherence` | `ip-uspto-audit` | `tool_evidence` | Greps every `\ref{}` against the figure source files. |

The takeaway: judgment dimensions tend to live on review-class critics
(`<skill>-review` and doctrinal specialists); tool-evidence dimensions
tend to live on audit-class critics. The same rubric dim can appear on
both classes when the artifact warrants belt-and-suspenders verification.

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

## Advisory rubric overlays

Some skills (currently `anvil:pub`) ship **advisory rubric overlays**
in addition to the generic /40 rubric. These are venue-pinned YAMLs
(e.g. `anvil/skills/pub/rubrics/neurips.yaml`) that produce
supplementary scoring for venue-specific signal — NeurIPS
reproducibility checklist, Nature's broad-significance bar, arXiv's
category-correctness norm — without breaking the framework-wide
/40 invariant.

Key properties of advisory rubrics:

- **They do NOT change the convergence gate.** The generic /40 with
  its declared threshold remains the sole driver of the `advance`
  decision. The venue overlay produces additional findings the
  reviser consumes; it does NOT contribute points to the
  gate-deciding total.
- **They relax the sum-to-total invariant.** A venue overlay may
  declare any sensible total (NeurIPS /16, Nature /15, arXiv /10).
  The framework's "/40 means the same thing across skills" rule
  applies only to the gate rubric (`advisory: false`).
- **Threshold is optional.** Advisory rubrics have no gate, so no
  threshold is required.

The on-disk shape is the same `Rubric` model in `anvil/lib/rubric.py`
(YAML-loaded) — the `advisory: true` flag is the discriminator. The
machine-readable JSON Schema lives at
`anvil/lib/rubric_schema.json`.

Reviewer commands that consume an advisory rubric write its scores
as a second `_review.json`-shaped file in the same `.review/` sibling
directory (canonical name: `_review.venue.json`). Both files use the
existing `Review` schema in `anvil/lib/review_schema.py`; the
reviser's existing N-critics-one-reviser aggregator treats the
venue file as one more critic input and the convergence gate is
computed from the generic file only (filtered by `rubric` id).

See `anvil/skills/pub/SKILL.md` and `anvil/skills/pub/rubric.md` for
the canonical example of an advisory overlay in use.

## See also

- `critics.md` — how multi-critic aggregation produces the composite
  per-dimension score and critical flag.
- `scorecard_kind.md` — how the reviser knows what file shape to read
  from each critic.
- `state_machine.md` — where the convergence check sits in the
  lifecycle.
- `audit.md` — the `.review/` (judgment) vs `.audit/` (tool-evidence)
  distinction with skill-by-skill mapping table.
