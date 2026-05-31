---
name: memo
description: Portfolio orchestrator for memo threads. Discovers all memo threads under cwd, reports state-machine position per thread, and recommends the next command.
---

# memo — Portfolio orchestrator

**Role**: portfolio orchestrator (read-only; reports state, does not mutate).
**Reads**: all `<thread>.*/` directories under the current working directory.
**Writes**: nothing on disk. Returns a status report.

## Purpose

A single command that an operator (or orchestrating agent) runs to see the state of every memo thread in the portfolio and a recommended next command per thread.

## Inputs

- **CWD**: the portfolio directory containing memo threads.
- **Discovery rule**: a thread is detected by the presence of any `<slug>.{N}/` directory (with `_progress.json`). The slug is the directory name up to the first `.<digit>`. A bare `<slug>/` directory without any versioned siblings is treated as a brief-only thread in state `EMPTY`.

## Procedure

1. Enumerate all directories under cwd matching the pattern `<slug>` or `<slug>.{N}` or `<slug>.{N}.<critic>` (where `<critic>` ∈ {`review`, `audit`, `critic`, ...}).
2. Group by slug. For each slug, identify:
   - The latest `N` for which `<slug>.{N}/` exists.
   - Which sibling critic dirs exist at that `N`.
   - The verdict (advance/block, total /40, critical flags) from `<slug>.{N}.review/verdict.md` if present.
   - The iteration count and `max_iterations` from `<slug>.{N}/_progress.json` (or from `<slug>/.anvil.json` if the per-thread override is set).
   - The optional `target_length` from `<slug>/.anvil.json` (informational only — the orchestrator does not enforce; it surfaces the declared target alongside the latest version's word count when both are available, so the operator can see at a glance whether the thread is tracking its target).
3. Compute the state-machine position per thread using the table in `SKILL.md`.
4. Recommend the next command per thread:

   | State | Recommended next command |
   |---|---|
   | `EMPTY` | `memo-draft <thread>` |
   | `DRAFTED` | `memo-review <thread>` |
   | `REVIEWED` (advance=false, under iteration cap) | `memo-revise <thread>` |
   | `REVIEWED` (advance=false, AT iteration cap) | `BLOCKED — human review required` |
   | `REVIEWED` (advance=true, no figures yet) | `memo-figures <thread>` (optional) |
   | `READY` | (terminal) |
   | `READY` + figures missing exhibits | `memo-figures <thread>` |

5. Detect anomalies and surface them:
   - A `<slug>.{N}/_progress.json` with any phase in state `in_progress` AND the version dir is older than 10 minutes — likely a crashed phase; recommend resuming.
   - A critic sibling dir (`<slug>.{N}.<critic>/`) without a matching `<slug>.{N}/` — orphan; report.
   - A gap in version numbers (e.g., `<slug>.1/` and `<slug>.3/` with no `<slug>.2/`) — report.

## Output format

Print a markdown table to stdout:

```
| Thread        | Latest | State    | Score | Iter | Next                       |
|---------------|--------|----------|-------|------|----------------------------|
| acme-seed     | .2     | REVIEWED | 28/40 | 2/4  | memo-revise acme-seed      |
| beta-bridge   | .3     | READY    | 34/40 | 3/4  | (terminal)                 |
| gamma-ic      | -      | EMPTY    | -     | 0/4  | memo-draft gamma-ic        |
```

Follow the table with an `## Anomalies` section if any were detected, and an `## Operator notes` section with any threads requiring human review (iteration cap reached, critical flag unresolved across multiple revisions, etc.).

## Notes

- This command does **not** write to disk. It is safe to run repeatedly.
- The portfolio orchestrator is the recommended user-facing entry point. The four lifecycle commands (`memo-draft`, `memo-review`, `memo-revise`, `memo-figures`) can be invoked directly by an orchestrating agent or by a human operator running them in sequence.
