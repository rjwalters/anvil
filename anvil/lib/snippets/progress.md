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
    "max_iterations": <N>
  }
}
```

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
`for_version`, `project`, skill-specific extensions). The merge is shallow:
do not attempt deep recursive merges of `metadata` sub-objects unless the
specific snippet says otherwise.

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
