# Critic discovery and aggregation

Anvil's "N parallel critics, one reviser" pattern is implemented entirely
through filesystem conventions plus the `scorecard_kind` discriminator.
There is no shared runtime; each skill's reviser performs discovery and
aggregation using the rules here.

## Discovery

Given a thread and a version `N`, critic siblings are the directories
matching the glob:

```
<thread>.{N}.*/
```

minus the bare versioned directory `<thread>.{N}/`. The glob captures
every sibling of every kind (review, audit, narrative, market, design,
s101, s112, preflight, ...) regardless of which skill defined the tag.

### Skill-side default critic set

Each skill defines a default set of critics that MUST run before a
version can leave `REVIEWED`. The reviser refuses to advance if any
configured critic is missing or unfinished.

| Skill | Default critic set | Optional siblings |
|---|---|---|
| memo | `review` | `audit`, `critic` (consumer-added) |
| pub | `review`, `audit` | `litsearch` (pre-draft or re-run) |
| slides | `review`, `audit` (mandatory) | `outline` (pre-draft), `rehearse`, `handout` (terminal) |
| deck | `review`, `narrative`, `market`, `design` | `audit` |
| report | `review`, `audit` (both mandatory) | `promote` (terminal) |
| ip-uspto | `review`, `s101`, `s112`, `claims`, `priorart` | `preflight` (mid-loop), `audit` (post-READY) |

Operators can subset the default set per-thread by writing
`{ "critics": ["..."] }` to `<thread>/.anvil.json`.

## Per-critic discovery

For each discovered sibling at `<thread>.{N}.<tag>/`, the reviser:

1. Loads `_meta.json` if present — extract `scorecard_kind` (default
   `human-verdict` if missing).
2. Verifies `_progress.json` records the relevant phase as `done`.
   If `in_progress` or `failed`, treat as missing for aggregation
   purposes (and warn the operator that a critic crashed).
3. Loads the appropriate scorecard files per the discriminator (see
   `scorecard_kind.md` for the file map).

## Aggregation

The reviser produces a single composite scorecard from all critic
outputs:

```
def aggregate(thread, N, skill_config):
    siblings = glob(f"{thread}.{N}.*/") - {f"{thread}.{N}"}
    required = set(skill_config["critics"])
    found    = {parse_tag(s) for s in siblings}

    missing = required - found
    if missing:
        return ERROR(f"missing required critics: {missing}")

    per_dim = {dim: [] for dim in 1..8}
    critical_flag = False

    for sibling in siblings:
        meta = load_json(sibling/"_meta.json")  # or {} if not present
        kind = meta.get("scorecard_kind", "human-verdict")

        scores, flag = read_scorecard(sibling, kind)
        for dim, score in scores.items():
            if score is not None:
                per_dim[dim].append(score)
        critical_flag = critical_flag or flag

    composite = {dim: round(mean(per_dim[dim])) if per_dim[dim] else None
                 for dim in 1..8}
    total = sum(v for v in composite.values() if v is not None)
    return composite, total, critical_flag
```

### Aggregation rule details

1. **Per-dimension mean of non-null scores.** A dimension is null if NO
   critic owned it (rare; usually the general reviewer covers all
   dimensions). Otherwise the mean of non-null contributions.
2. **Integer rounding.** Final composite per-dimension scores round to
   the nearest integer (the rubric is integer-valued).
3. **Critical-flag OR.** Any critic with `critical_flag: true` (in its
   verdict.md or _summary.md frontmatter) sets the composite flag.
4. **Threshold comparison happens after aggregation.** The reviser
   checks `total >= skill_threshold AND NOT critical_flag` to decide
   if the thread advances.

## Parallelism

Critics are independent. Two parallel critics on the same `<thread>.{N}/`
read the same input and write to disjoint output paths
(`<thread>.{N}.review/` vs `<thread>.{N}.audit/`). There is no shared
mutable state.

**v0 implementations should default to serial execution** (for
debuggability). The sibling-directory convention permits parallel
spawn, and the orchestrator MAY parallelize when an operator opts in;
nothing in the file layout breaks.

## Adding a new critic

To add a new critic to an existing skill:

1. Create a new command file: `commands/<skill>-<tag>.md`.
2. Have it write to `<thread>.{N}.<tag>/` with the appropriate
   `scorecard_kind` per the discriminator.
3. Append the new tag to the skill's default critic set (in the
   skill's SKILL.md, the `Default critic set` row of the table above).
4. No reviser changes required — the glob discovery picks it up.

## Examples by skill

### memo (human-verdict only)

```
acme-seed.1/                  # the artifact
acme-seed.1.review/           # human-verdict
  verdict.md
  scoring.md
  comments.md
  _meta.json   { "scorecard_kind": "human-verdict" }
  _progress.json
```

The reviser reads `scoring.md`'s markdown table to extract all 8
dimension scores; no aggregation across critics (single critic).

### ip-uspto (machine-summary, multiple specialists)

```
acme-widget.2/
acme-widget.2.review/         # machine-summary (owns dims 6, 7, 8)
acme-widget.2.s101/           # machine-summary (owns dim 4)
acme-widget.2.s112/           # machine-summary (owns dims 2, 3)
acme-widget.2.claims/         # machine-summary (owns dim 1)
acme-widget.2.priorart/       # machine-summary (owns dim 5)
```

The reviser aggregates per-dimension means across the 5 specialists,
each contributing scores only for their owned dimensions. Critical
flags from any specialist (especially s101, s112) short-circuit the
advance.

### deck (mixed: aggregator + specialists)

```
acme-seed.1/
acme-seed.1.review/           # AGGREGATOR — emits both kinds; primary kind: human-verdict
  verdict.md                  # synthesized narrative
  scoring.md                  # complete 8-dim table (mean of specialists + own observations)
  comments.md
  _summary.md                 # machine-summary shape (for machine consumers)
  findings.md
  _meta.json   { "scorecard_kind": "human-verdict" }   # primary intent
acme-seed.1.narrative/        # SPECIALIST — machine-summary (owns dims 1, 7)
acme-seed.1.market/           # SPECIALIST — machine-summary (owns dims 3, 4)
acme-seed.1.design/           # SPECIALIST — machine-summary (owns dim 8)
```

Deck's aggregator critic (`deck-review`) emits both shapes layered:
the human-verdict narrative is the primary deliverable; the
machine-summary layer lets future cross-skill machinery aggregate it
alongside other machine-summary critics if needed.

### pub (human-verdict reviewer + human-verdict auditor with task-specific files)

```
q3-method.2/
q3-method.2.review/           # human-verdict
q3-method.2.audit/            # human-verdict + task-specific files
  verdict.md                  (synthesized: aggregates the per-claim audits)
  scoring.md                  (audit-specific scoring; treated as a critic vote in aggregation)
  citation-audit.md           # additive task-specific
  numerical-audit.md          # additive task-specific
  compile-log.txt             # additive task-specific
  flags.md                    # additive task-specific
  _meta.json   { "scorecard_kind": "human-verdict" }
```

Note: pub-audit currently emits `flags.md` rather than `verdict.md` +
`scoring.md`. This is an audit-critic convention; the aggregator
treats `flags.md` as critical-flag input and consults `_meta.json` to
determine the scorecard kind. The migration in the PR introducing
this lib adds the `_meta.json` annotation without changing the
existing files.

## See also

- `scorecard_kind.md` — the discriminator and per-kind file maps.
- `version_layout.md` — sibling directory naming rules.
- `state_machine.md` — when critics run in the lifecycle.
- `progress.md` — `_progress.json` schema for the sibling directory.
