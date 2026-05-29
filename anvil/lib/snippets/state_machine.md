# State machine and extension-point pattern

Every anvil skill walks a state machine from `EMPTY` to a terminal state.
The shape is shared; the specific states differ per skill. This snippet
documents the canonical base machine, the standard extension points, and
how skills hook into them without forking.

## Base state machine

```
EMPTY → DRAFTED → REVIEWED → REVISED → … → READY
                                          ↘ AUDITED (optional, auditor sibling)
```

| State | Evidence (on-disk) |
|---|---|
| `EMPTY` | No `<thread>.{N}/` directories exist. |
| `DRAFTED` | Latest `<thread>.{N}/` has the artifact file + `_progress.json.draft == done`; no sibling review at the same `N`. |
| `REVIEWED` | `<thread>.{N}.review/verdict.md` (or `_summary.md`) exists for the latest `N`. |
| `REVISED` | A `<thread>.{N+1}/` exists after a prior `<thread>.{N}.review/`. |
| `READY` | Latest review records `advance: true` AND no unresolved critical flag. |
| `AUDITED` | `<thread>.{N}.audit/` exists alongside a `READY` version (when supported). |

`READY` is terminal for skills that ship without a mandatory audit phase
(memo, deck). `AUDITED` is terminal for skills where audit is mandatory
(pub, slides). Some skills add further terminal states past `AUDITED`
(report → `CUSTOMER-READY`; ip-uspto → `FINALIZED`); see Extension Points
below.

## Convergence and iteration cap

Each loop iteration is one revise pass. The default iteration cap is
`max_iterations: 4` (terminal version is `<thread>.5/`). Exceeding the
cap marks the thread `BLOCKED` and requires human review.

The cap is configurable per-thread by writing
`{ "max_iterations": <N> }` to `<thread>/.anvil.json` in the thread root.

## Critical-flag short-circuit

Any critical flag set by any sibling critic short-circuits regardless of
score. A `READY` transition requires:

1. `total_score >= threshold` (32 for memo/pub/slides, 35 for deck/report/ip-uspto).
2. `no unresolved critical flag` from any sibling critic.

Both conditions must hold. Either falsy condition keeps the thread in
the convergence loop (or `BLOCKED` if the cap is exceeded).

## Extension points

Skills extend the base machine in three well-defined ways. Use these
patterns rather than inventing parallel structures.

### 1. Pre-draft phases

Add a state before `DRAFTED` for setup work the drafter consumes. The
sibling lives at `<thread>.0.<tag>/`. Examples:

| Skill | Pre-draft state | Sibling |
|---|---|---|
| slides | `OUTLINED` | `<thread>.0.outline/` |
| pub | (no named state — litsearch is informational) | `<thread>.0.litsearch/` |
| deck | `BRIEF_DONE` | `<thread>/BRIEF.md` (not a sibling — lives in thread root) |
| ip-uspto | `INTAKE_DONE` → `INVENTORSHIP_DONE` | `<thread>/BRIEF.md` + `<thread>/inventorship.md` |

The state-derivation predicate (see `thread_state.md`) checks for the
expected pre-draft evidence; if present and no `<thread>.1/` exists yet,
report the pre-draft state.

### 2. Mid-loop phases

Add a state inside the convergence loop. Used when a check must run
before each review iteration. Example:

| Skill | Mid-loop state | When |
|---|---|---|
| ip-uspto | `PRE_FLIGHT_PASSED` | After revise, before next review |

The orchestrator's "next command" recommendation includes the mid-loop
phase as a prerequisite for the next iteration.

### 3. Post-AUDITED terminal phases

Add a state after `AUDITED` for human-acknowledgment gates or assembly
of submission packages. Example:

| Skill | Terminal state | Trigger |
|---|---|---|
| report | `CUSTOMER-READY` | `report-promote` writes `<thread>.{N}.promote/receipt.md` |
| ip-uspto | `FINALIZED` | `ip-uspto-finalize` writes `<thread>.final/_manifest.json` |
| slides | `REHEARSED → HANDOUT_GENERATED` | rehearse sibling, then handout export |

The post-AUDITED transition typically requires explicit human
acknowledgment (a "kill-switch" gate before delivering customer-facing
material). The state-derivation predicate checks for the relevant
sibling's existence.

## Runtime hook (deferred)

The two-stage `AUDITED → CUSTOMER-READY` pattern (and ip-uspto's
`AUDITED → FINALIZED`) is currently implemented inline in each skill.
A first-class "post-audit human-ack gate" runtime hook is deferred until
a third skill needs the pattern — at that point the canonical hook
shape will be added here and the existing skills migrated. Until then,
new skills wanting a post-AUDITED terminal MUST follow the inline
pattern documented in the existing skills (write a critic-shaped
sibling at `<thread>.{N}.<tag>/` containing a `receipt.md` or
`_manifest.json` keyed to the version's content hash).

## State-transition table (composite, across skills)

```
EMPTY
  └→ (skill-specific pre-draft phases, optional)
       └→ DRAFTED
            └→ REVIEWED  ⇄  REVISED (loop until convergence)
                 ↘
                  └→ READY
                       └→ AUDITED (optional or mandatory per skill)
                            └→ (skill-specific terminal, optional: CUSTOMER-READY, FINALIZED, HANDOUT_GENERATED, ...)
       └→ BLOCKED (if iteration cap exceeded)
```

## See also

- `thread_state.md` — derive state from on-disk evidence (the runtime
  side of this table).
- `version_layout.md` — directory naming for sibling phases.
- `progress.md` — `_progress.json` records phase state for each step.
- `critics.md` — how the review/revise loop discovers and aggregates
  critic outputs.
