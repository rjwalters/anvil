---
name: proposal
description: Portfolio orchestrator for proposal threads. Discovers all proposal threads under cwd, reports state-machine position per thread, and recommends the next command.
---

# proposal — Portfolio orchestrator

**Role**: portfolio orchestrator (read-only; reports state, does not mutate).
**Reads**: all `<thread>.*/` directories under the current working directory.
**Writes**: nothing on disk. Returns a status report.

## Purpose

A single command that an operator (or orchestrating agent) runs to see the state of every proposal thread in the portfolio and a recommended next command per thread.

## Inputs

- **CWD**: the portfolio directory containing proposal threads.
- **Discovery rule**: a thread is detected by the presence of any `<slug>.{N}/` directory (with `_progress.json`). The slug is the directory name up to the first `.<digit>`. A bare `<slug>/` directory without any versioned siblings is treated as a brief-only thread in state `EMPTY`.

## Procedure

1. Enumerate all directories under cwd matching the pattern `<slug>` or `<slug>.{N}` or `<slug>.{N}.<critic>` (where `<critic>` ∈ {`review`, `audit`, `critic`, ...}).
2. Group by slug. For each slug, identify:
   - The latest `N` for which `<slug>.{N}/` exists.
   - Which sibling critic dirs exist at that `N` — specifically whether BOTH `<slug>.{N}.review/` AND `<slug>.{N}.audit/` are present (both are required to leave `DRAFTED`).
   - The review verdict (advance/block, total /44, critical flags) from `<slug>.{N}.review/verdict.md` if present, and the audit verdict (pass/fail, critical flags) from `<slug>.{N}.audit/verdict.md` if present.
   - The iteration count and `max_iterations` from `<slug>.{N}/_progress.json` (or from `<slug>/.anvil.json` if the per-thread override is set).
3. Compute the state-machine position per thread using the table in `SKILL.md`. Note the parallel-critic states:
   - `DRAFTED` — neither critic sibling present.
   - `REVIEWED` (transient) — only `.review/` present; not advance-eligible.
   - `AUDITED-PARTIAL` (transient) — only `.audit/` present; not advance-eligible.
   - `REVIEWED+AUDITED` — both present.
   - `READY`/`AUDITED` — both clear (review `advance: true` ≥35, audit `pass: true`, no critical flags).
4. Recommend the next command per thread:

   | State | Recommended next command |
   |---|---|
   | `EMPTY` | `proposal-draft <thread>` |
   | `DRAFTED` | `proposal-review <thread>` **and** `proposal-audit <thread>` (run both, in parallel) |
   | `REVIEWED` (only review done) | `proposal-audit <thread>` (the audit sibling is still required) |
   | `AUDITED-PARTIAL` (only audit done) | `proposal-review <thread>` (the review sibling is still required) |
   | `REVIEWED+AUDITED` (either blocks, under iteration cap) | `proposal-revise <thread>` |
   | `REVIEWED+AUDITED` (either blocks, AT iteration cap) | `BLOCKED — human review required` |
   | `REVIEWED+AUDITED` (both clear, no figures yet) | `proposal-figures <thread>` (optional) |
   | `READY` / `AUDITED` | (terminal) |
   | `READY` + figures missing | `proposal-figures <thread>` |

5. Detect anomalies and surface them:
   - A `<slug>.{N}/_progress.json` with any phase in state `in_progress` AND the version dir is older than 10 minutes — likely a crashed phase; recommend resuming.
   - A critic sibling dir (`<slug>.{N}.<critic>/`) without a matching `<slug>.{N}/` — orphan; report.
   - A gap in version numbers (e.g., `<slug>.1/` and `<slug>.3/` with no `<slug>.2/`) — report.
   - A thread that reached a new version but has only one of the two required critic siblings at the prior version — report (an incomplete critic pass).

## Output format

Print a markdown table to stdout:

```
| Thread       | Latest | State            | Review | Audit | Iter | Next                              |
|--------------|--------|------------------|--------|-------|------|-----------------------------------|
| gossamer-lan | .2     | REVIEWED+AUDITED | 32/44  | pass  | 2/4  | proposal-revise gossamer-lan      |
| solar-rig    | .3     | AUDITED          | 38/44  | pass  | 3/4  | (terminal)                        |
| new-system   | -      | EMPTY            | -      | -     | 0/4  | proposal-draft new-system         |
```

Follow the table with an `## Anomalies` section if any were detected, and an `## Operator notes` section with any threads requiring human review (iteration cap reached, critical flag unresolved across multiple revisions, only one of two required critic siblings present, etc.).

## Notes

- This command does **not** write to disk. It is safe to run repeatedly.
- The portfolio orchestrator is the recommended user-facing entry point. The lifecycle commands (`proposal-draft`, `proposal-review`, `proposal-audit`, `proposal-revise`, `proposal-figures`) can be invoked directly by an orchestrating agent or by a human operator running them in sequence.
- **Both `proposal-review` and `proposal-audit` are required** before a thread can advance. The orchestrator never recommends advancing on a single critic sibling; it surfaces an `AUDITED-PARTIAL` or review-only state and recommends running the missing critic.
