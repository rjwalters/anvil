# `scorecard_kind` discriminator

The load-bearing primitive that lets `anvil/lib/` describe the critic
landscape without forcing every skill to converge on identical files.

## The problem

Across the six v0 skills (memo, pub, slides, deck, report, ip-uspto),
critic siblings emit different files:

- **memo, pub, slides, report reviewers** emit `verdict.md` +
  `scoring.md` + `comments.md`. These are narrative documents a human
  reads end-to-end to understand the critique.
- **ip-uspto critics + deck specialists** emit `_summary.md` +
  `findings.md` (plus `_meta.json`). These are partial scorecards an
  aggregator merges programmatically; each critic owns only some
  rubric dimensions and leaves the rest `null`.
- **deck-review** emits BOTH layered together — the union of the two
  patterns above.
- **pub-audit, slides-audit, report-audit** add task-specific files
  (citation logs, compile logs, claim tables) alongside one of the
  above scorecard shapes.

The lib does NOT force a single shape. It introduces a discriminator
field in `_meta.json` so consumers can detect what shape to expect
without inspecting filenames.

## The discriminator

Every critic sibling's `_meta.json` MUST include:

```json
{
  "critic": "<tag>",
  "role": "<skill>-<tag>.md",
  "started":  "<ISO-8601 UTC>",
  "finished": "<ISO-8601 UTC>",
  "model": "<model-id>",
  "schema_version": 1,
  "scorecard_kind": "human-verdict" | "machine-summary"
}
```

The `scorecard_kind` field takes one of two values:

### `human-verdict`

The critic's output is meant to be read end-to-end by a human (or by
the reviser as a narrative). Files emitted:

```
<thread>.{N}.<tag>/
  verdict.md       Top-level decision + total /40 + critical flags
  scoring.md       Per-dimension scorecard with justifications (markdown table)
  comments.md      Line-keyed or location-keyed feedback grouped by severity
  _meta.json       { ..., "scorecard_kind": "human-verdict" }
  _progress.json
```

Used by: memo-review, pub-review, slides-review, report-review,
pub-audit, slides-audit, report-audit.

The reviser consumes these by reading the markdown narratives; no
programmatic aggregation is required because each critic produces a
complete (all-8-dimensions) scorecard.

### `machine-summary`

The critic's output is meant to be aggregated programmatically. Each
critic owns only a subset of rubric dimensions; un-owned dimensions
appear as `null`. Files emitted:

```
<thread>.{N}.<tag>/
  _summary.md      Partial 8-dim scorecard (owned dims scored; others null) + critical-flag bool
  findings.md      Itemized findings (severity, location, rationale, suggested fix)
  _meta.json       { ..., "scorecard_kind": "machine-summary" }
  _progress.json
```

Used by: ip-uspto-review, ip-uspto-101, ip-uspto-112, ip-uspto-claims,
ip-uspto-prior-art, ip-uspto-audit, ip-uspto-pre-flight, deck-narrative,
deck-market, deck-design.

The reviser aggregates these by per-dimension mean of non-null scores,
and ORs all critical-flag booleans.

## Aggregation rules

```
def aggregate_scores(critic_dirs):
    per_dim_scores = {dim: [] for dim in 1..8}
    critical_flag = False

    for critic_dir in critic_dirs:
        meta = load_json(critic_dir/"_meta.json")
        kind = meta.get("scorecard_kind", "human-verdict")  # default backward-compatible

        if kind == "human-verdict":
            # Read scoring.md or verdict.md; extract per-dim scores from markdown table.
            scores = parse_scoring_markdown(critic_dir/"scoring.md")
            flag   = parse_verdict_flag(critic_dir/"verdict.md")
        elif kind == "machine-summary":
            # Read _summary.md; extract per-dim partial scorecard.
            scores = parse_summary_markdown(critic_dir/"_summary.md")  # nulls for unowned dims
            flag   = parse_summary_flag(critic_dir/"_summary.md")
        else:
            raise ValueError(f"unknown scorecard_kind: {kind}")

        for dim, score in scores.items():
            if score is not None:
                per_dim_scores[dim].append(score)
        critical_flag = critical_flag or flag

    # Mean of non-null scores per dimension.
    final = {dim: mean(per_dim_scores[dim]) if per_dim_scores[dim] else None
             for dim in 1..8}
    return final, critical_flag
```

LLM-side: an agent doing aggregation reads each critic sibling's
`_meta.json` to detect the kind, then parses the appropriate file shape.

## Backward compatibility

A critic that does NOT ship `_meta.json` (or ships one without
`scorecard_kind`) is treated as `human-verdict` for backward
compatibility. This keeps memo/pub/slides/report reviewers working
without any required changes — their existing `verdict.md` +
`scoring.md` + `comments.md` is already the `human-verdict` shape.

The minimum change required to formally declare a critic's kind is:
add a `_meta.json` with at least:

```json
{ "critic": "<tag>", "scorecard_kind": "machine-summary" }
```

(The other `_meta.json` fields are recommended but not required for
discrimination.)

## Aggregator critics (both kinds)

Some critics (deck-review, future cross-critic synthesizers) emit BOTH
file shapes — `verdict.md` + `scoring.md` + `comments.md` AND
`_summary.md` + `findings.md`. These are aggregator critics: their job
is to assemble a complete picture from the work of other specialists
while also producing a human-readable narrative.

For an aggregator critic, the `_meta.json` SHOULD record either kind
(typically `human-verdict`, since the aggregated `verdict.md` is the
primary deliverable). The presence of both shapes is the signal to
downstream consumers; the discriminator carries the primary intent.

## Audit / fact-check critics

Audit critics (pub-audit, slides-audit, report-audit, ip-uspto-audit)
may add task-specific files alongside whichever scorecard kind they
ship:

- pub-audit: `citation-audit.md`, `numerical-audit.md`, `compile-log.txt`
- slides-audit: `claims.md`
- report-audit: `findings.md`, `evidence.md`
- ip-uspto-audit: `findings.md` (machine-summary kind)

These additive files do NOT affect the discriminator; they are
documented in the respective audit command file.

## See also

- `critics.md` — discovery glob + aggregation invocation.
- `progress.md` — `_progress.json` schema (sits next to `_meta.json`).
- `rubric.md` — the 8-dimension /40 shape that scorecards conform to.
