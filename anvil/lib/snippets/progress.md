# `_progress.json` read-merge-write snippet

Canonical convention for every command that touches a `_progress.json` file.
This is the single source of truth referenced by SKILL.md and command files
across all anvil skills.

## Schema

Every `_progress.json` carries this minimum shape:

```json
{
  "version": 1,
  "thread": "<slug>",
  "phases": {
    "<phase>": {
      "state": "pending|in_progress|done|failed",
      "started":   "<ISO-8601 UTC>",
      "completed": "<ISO-8601 UTC>"
    }
  },
  "metadata": {
    "iteration": <N>,
    "max_iterations": <N>,
    "score_history": [
      { "iteration": 1, "total": 28, "threshold": 32 },
      { "iteration": 2, "total": 30, "threshold": 32 }
    ]
  },
  "termination_reason": "THRESHOLD_MET | CRITICAL_FLAG | STALLED | MAX_ITERATIONS"
}
```

`metadata.score_history` and the top-level `termination_reason` are
**optional** and added by #27 for stable-score termination. See
"Convergence fields" below.

Critic sibling directories (`<thread>.{N}.<tag>/`) carry an additional
top-level field naming the version they critique:

```json
{ "version": 1, "thread": "<slug>", "for_version": <N>, "phases": { ... } }
```

Skill-specific extensions are allowed (e.g., `project: <slug>` for the
report skill; `metadata.audit_summary` for pub-audit's rich nested
metadata). The merge rule preserves any extension fields the caller does
not touch.

## Phase states

| State | Meaning |
|---|---|
| `pending` | Phase has not started (or was reset after a crash). |
| `in_progress` | Phase is currently running. |
| `done` | Phase completed successfully. |
| `completed` field is set. |
| `failed` | Phase ran but did not produce valid output. Caller decides whether to retry from `pending` or escalate. |

## Convergence fields (added by #27)

Two optional fields participate in the secondary "stable-score termination"
stop condition. Both are additive and the shallow-merge rule (see
"Read-merge-write recipe" below) preserves them: a command that does not
own these fields will read them, leave them untouched, and write them back.

### `metadata.score_history`

An array of per-iteration scorecard summaries, appended one entry per
review iteration:

```json
"score_history": [
  { "iteration": 1, "total": 28, "threshold": 32 },
  { "iteration": 2, "total": 30, "threshold": 32 },
  { "iteration": 3, "total": null, "threshold": 32 }
]
```

- `iteration`: 1-indexed iteration number, matching `metadata.iteration`
  at the time the entry was appended.
- `total`: the per-version aggregated total from
  `anvil.lib.critics.aggregate`. Use `null` (NOT `0`) when no scorecard
  was produced — e.g., a critical-flag short-circuit fired before the
  reviewer wrote a scorecard.
- `threshold`: the advance threshold at that iteration. Captured per-row
  so a mid-loop threshold override remains auditable.

The array is the input to `anvil.lib.convergence.check_stable` and
`anvil.lib.convergence.decide_termination`. The orchestrator extracts the
`total` column in iteration order and passes it as the `history` argument.

The reviser/orchestrator command is responsible for appending the row for
the iteration it just finished. Other commands MUST NOT mutate
`score_history`; they read it as input only.

### `termination_reason` (top-level)

A top-level field set by the review/revise command **only** when it has
just decided to terminate the convergence loop. Absent (or `null`) on
intermediate iterations. Values:

| Value | Meaning |
|---|---|
| `THRESHOLD_MET` | `total >= threshold`, no critical flag — `ADVANCE`. |
| `CRITICAL_FLAG` | A critical flag is set — `BLOCK`. |
| `STALLED` | The last `lookback` totals are within `± window` and below threshold — secondary stop condition. Verdict = `STALLED`. |
| `MAX_ITERATIONS` | Iteration cap exhausted without convergence. Verdict stays `REVISE`; the termination reason distinguishes "ran out of budget" from "demonstrated plateau". |

The resolution order is documented in `rubric.md`'s "Convergence logic"
and implemented in `anvil.lib.convergence.decide_termination`. The two
sources MUST agree; the Python implementation is the source of truth for
programmatic use, the snippet for LLM-side authoring.

### Why this is additive

Both fields are optional and absent in pre-#27 `_progress.json` files. The
shallow-merge rule (every command preserves top-level + `metadata` fields
it does not own) means existing commands that have not been migrated to
write these fields continue to function unchanged. The only command that
needs to know about them is the review/revise command (which appends to
`score_history`) and the orchestrator's stop-condition check (which reads
both).

## Validation discipline

**Validation is by file existence**, not by flag. The presence of `memo.md`
(or `deck.md`, `spec.tex`, `report.md`, etc.) is the source of truth for
"did this phase produce output". `_progress.json` is a resume hint that
helps a crashed command re-enter the right phase. A `phases.draft.state ==
done` without the artifact file present means the JSON is stale; the
command should treat the phase as crashed and re-run.

## Read-merge-write recipe (pseudocode)

```
def write_phase(path, phase, fields):
    if exists(path):
        progress = json.loads(read(path))
    else:
        progress = {"version": 1, "thread": <slug>, "phases": {}, "metadata": {}}

    # Update only this phase; preserve all other phases and top-level fields.
    progress["phases"][phase] = {
        **progress["phases"].get(phase, {}),
        **fields,  # e.g., {"state": "done", "completed": <ISO>}
    }

    write_atomic(path, json.dumps(progress, indent=2))
```

**Merge rule (shallow)**: the command updates one phase, preserves all
others, and preserves any top-level fields it does not own (`metadata`,
`for_version`, `project`, `termination_reason`, skill-specific
extensions). The merge is shallow: do not attempt deep recursive merges
of `metadata` sub-objects unless the specific snippet says otherwise.

Specifically:

- `termination_reason` (top-level, added by #27) is preserved on every
  shallow merge. Only the review/revise command that decided termination
  writes this field. Other commands MUST NOT clear it.
- `metadata.score_history` (added by #27) is preserved on every shallow
  merge. Only the review/revise command that just finished an iteration
  appends to it. Other commands MUST NOT mutate it.

**Atomicity**: write to a temp file in the same directory, then `rename()`
over the target. This avoids corrupting `_progress.json` if the process
is killed mid-write.

## Crash recovery contract

If a command finds `phases.<phase>.state == in_progress` and the expected
output file is missing or empty, the command MUST:

1. Treat the phase as crashed.
2. Delete any partial output (e.g., an empty or truncated `memo.md`).
3. Re-enter the phase from `pending` (or directly re-write `in_progress`
   with a fresh `started` timestamp).

If `phases.<phase>.state == done` AND the expected output file is present
and parses, the command is a no-op (idempotent).

## Initial-write template (version dir)

A new version directory writes its `_progress.json` for the first time
like this (replace `<phase>` with `draft`, `figures`, etc.):

```json
{
  "version": 1,
  "thread": "<slug>",
  "phases": {
    "<phase>": {
      "state": "in_progress",
      "started": "<ISO-8601 UTC>"
    }
  },
  "metadata": {
    "iteration": <N>,
    "max_iterations": <inherited from <thread>/.anvil.json or 4>
  }
}
```

On successful completion:

```json
{
  "version": 1,
  "thread": "<slug>",
  "phases": {
    "<phase>": {
      "state": "done",
      "started":   "<ISO-8601 UTC>",
      "completed": "<ISO-8601 UTC>"
    }
  },
  "metadata": { ... preserved ... }
}
```

## Initial-write template (critic sibling)

A critic sibling adds the `for_version` field naming the version it
critiques:

```json
{
  "version": 1,
  "thread": "<slug>",
  "for_version": <N>,
  "phases": {
    "<phase>": {
      "state": "done",
      "started":   "<ISO-8601 UTC>",
      "completed": "<ISO-8601 UTC>"
    }
  }
}
```

Note that the phase name in a critic sibling SHOULD match the critic's
own tag (e.g., `review` for `.review/`, `audit` for `.audit/`, `s101` for
`.s101/`). Some early skill implementations used `review` as a generic
phase name across siblings — that is a known inconsistency tracked
separately; new critics should use their own tag.

## See also

- `timestamp.md` — canonical ISO-8601 UTC format.
- `version_layout.md` — directory naming rules.
- `critics.md` — `_meta.json` discovery and aggregation.
- `scorecard_kind.md` — the `human-verdict` vs `machine-summary` discriminator.
