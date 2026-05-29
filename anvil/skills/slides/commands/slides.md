---
name: slides
description: Portfolio orchestrator for slides threads. Discovers all slides threads under cwd, reports state-machine position per thread, and recommends the next command.
---

# slides — Portfolio orchestrator

**Role**: portfolio orchestrator (read-only; reports state, does not mutate).
**Reads**: all `<thread>.*/` directories under the current working directory.
**Writes**: nothing on disk. Returns a status report.

## Purpose

A single command that an operator (or orchestrating agent) runs to see the state of every slides thread in the portfolio and a recommended next command per thread.

## Inputs

- **CWD**: the portfolio directory containing slides threads.
- **Discovery rule**: a thread is detected by the presence of any `<slug>.{N}/` directory (with `_progress.json`) OR a `<slug>.0.outline/` directory. The slug is the directory name up to the first `.<digit>`. A bare `<slug>/` directory without any versioned or outline siblings is treated as a brief-only thread in state `EMPTY`.

## Procedure

1. Enumerate all directories under cwd matching the patterns `<slug>`, `<slug>.{N}`, or `<slug>.{N}.<phase>` (where `<phase>` ∈ {`outline`, `review`, `audit`, `rehearse`, `handout`, ...} and `N` is a non-negative integer).
2. Group by slug. For each slug, identify:
   - Whether `<slug>.0.outline/outline.md` exists.
   - The latest `N > 0` for which `<slug>.{N}/` exists.
   - Which sibling critic / phase dirs exist at that `N` (`review`, `audit`, `rehearse`, `handout`).
   - The verdict (advance/block, total /40, critical flags) from `<slug>.{N}.review/verdict.md` if present.
   - The audit flag from `<slug>.{N}.audit/verdict.md` if present.
   - The density and time flags from `<slug>.{N}.rehearse/timing.md` and `density.md` if present.
   - The iteration count and `max_iterations` from `<slug>.{N}/_progress.json` (or from `<slug>/.anvil.json` if the per-thread override is set).
3. Compute the state-machine position per thread using the table in `SKILL.md`.
4. Recommend the next command per thread:

   | State | Recommended next command |
   |---|---|
   | `EMPTY` (no outline yet) | `slides-outline <thread>` (or `slides-draft <thread>` if the brief contains a `## Outline` heading) |
   | `OUTLINED` | `slides-draft <thread>` |
   | `DRAFTED` | `slides-review <thread>` AND `slides-audit <thread>` AND `slides-rehearse <thread>` (run all three; they are independent critics) |
   | `REVIEWED` (advance=false, under iteration cap) | `slides-revise <thread>` |
   | `REVIEWED` (advance=false, AT iteration cap) | `BLOCKED — human review required` |
   | `REVIEWED` (advance=true, no audit yet) | `slides-audit <thread>` (audit is MANDATORY before READY) |
   | `REVIEWED` (advance=true) + `AUDITED` (no rehearse yet) | `slides-rehearse <thread>` |
   | `READY` + `AUDITED` + `REHEARSED` (no handout yet) | `slides-handout <thread>` (optional terminal export) |
   | `HANDOUT_GENERATED` | (terminal) |
   | Any state, figures referenced but missing | `slides-figures <thread>` |

5. Detect anomalies and surface them:
   - A `<slug>.{N}/_progress.json` with any phase in state `in_progress` AND the version dir is older than 10 minutes — likely a crashed phase; recommend resuming.
   - A critic sibling dir (`<slug>.{N}.<critic>/`) without a matching `<slug>.{N}/` — orphan; report.
   - A gap in version numbers (e.g., `<slug>.1/` and `<slug>.3/` with no `<slug>.2/`) — report.
   - A `<slug>.{N}.audit/verdict.md` recording a `wrong` claim that has not been addressed in any `<slug>.{M>N}/changelog.md` — report (audit flag carried forward unresolved).
   - A `<slug>.{N}.rehearse/timing.md` recording a time flag where projected duration is significantly over the slot — report (with the current overrun percentage).

## Output format

Print a markdown table to stdout:

```
| Thread                | Latest | State              | Score | Flags          | Iter | Next                                |
|-----------------------|--------|--------------------|-------|----------------|------|-------------------------------------|
| kdd-2026-keynote      | .2     | REVIEWED           | 28/40 | density        | 2/4  | slides-revise kdd-2026-keynote      |
| intro-to-anvil        | .3     | READY+AUDITED      | 34/40 | -              | 3/4  | slides-rehearse intro-to-anvil      |
| q3-arch-review        | .0.outline | OUTLINED       | -     | -              | 0/4  | slides-draft q3-arch-review         |
| internals-deep-dive   | -      | EMPTY              | -     | -              | 0/4  | slides-outline internals-deep-dive  |
```

Follow the table with an `## Anomalies` section if any were detected, and an `## Operator notes` section with any threads requiring human review (iteration cap reached, critical flag unresolved across multiple revisions, etc.).

## Notes

- This command does **not** write to disk. It is safe to run repeatedly.
- The portfolio orchestrator is the recommended user-facing entry point. The eight lifecycle commands (`slides-outline`, `slides-draft`, `slides-review`, `slides-audit`, `slides-revise`, `slides-figures`, `slides-rehearse`, `slides-handout`) can be invoked directly by an orchestrating agent or by a human operator running them in sequence.
- The `DRAFTED → READY` loop runs three critics in parallel (`review`, `audit`, `rehearse`) and one reviser. The reviser consumes all three sibling outputs. The orchestrator is responsible for running all three critics before invoking the reviser — `slides-revise` reads whichever critic dirs exist at the current `N`.
