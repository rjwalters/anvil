---
name: memoir
description: Per-chapter-thread status orchestrator for the memoir skill. Discovers memoir threads under cwd, reports state-machine position per thread (including corpus/voice tier declaration status), and recommends the next command. Read-only. Does NOT rebuild anvil:project-book's portfolio view — use /anvil:project-book for the all-chapters table.
---

# memoir — Per-chapter-thread status orchestrator

**Role**: per-thread status orchestrator (read-only; reports state, does
not mutate).
**Reads**: all `<thread>.*/` directories under the current working
directory (ONE chapter thread's directory tree, or several when invoked
at a project root — see §Scope note).
**Writes**: nothing on disk. Returns a status report.

## Scope note — this is NOT `anvil:project-book`

This command follows the `primer.md`/`spec.md`/`report.md` precedent: a
**per-thread** status report, not a project-wide portfolio view. The
"show me all six chapters, their states, their scores" table is
`anvil:project-book`'s job (`BOOK_REPORT.md`) — composing that view a
second time here would duplicate #596 rather than reuse it. Assemble the
book with `/anvil:project-book <project-dir>`; do not look for a
portfolio command here.

## Inputs

- **CWD**: a chapter thread directory (or the project root, in which case
  every chapter thread found is reported individually — still one row per
  thread, never a cross-thread aggregate).
- **Discovery rule**: a thread is detected by the presence of any
  `<slug>.{N}/` directory (with `_progress.json`). The slug is the
  directory name up to the first `.<digit>`. A bare `<slug>/` directory
  without versioned siblings is a brief-only thread in state `EMPTY`.

## Procedure

1. Enumerate all directories matching `<slug>`, `<slug>.{N}`, or
   `<slug>.{N}.<critic>` (where `<critic>` ∈ {`review`, `audit`,
   `corpus-audit`}).
2. Group by slug. For each slug, identify:
   - The latest `N` for which `<slug>.{N}/` exists.
   - Which sibling critic dirs exist at that `N` (`.review/`, `.audit/`,
     `.corpus-audit/`).
   - The verdict (advance/block, total /44, critical flags) from
     `<slug>.{N}.review/verdict.md`, the general audit verdict from
     `<slug>.{N}.audit/verdict.md`, and — when present — the corpus-audit
     verdict from `<slug>.{N}.corpus-audit/verdict.md`.
   - The iteration count and `max_iterations` from
     `<slug>.{N}/_progress.json` (default 4; project-BRIEF paired
     override per SKILL.md).
   - Whether the project BRIEF declares a top-level `corpus:` and a
     `voice:` block (with `subjects:`) — informational, surfaced so the
     operator sees at a glance which tiers are active for this project
     (the tiers are project-level, not per-chapter — SKILL.md §Dual-corpus
     provenance / §Dual voice tiers).
3. Compute the state-machine position per thread using the table in
   `SKILL.md` §State machine.
4. Recommend the next command per thread:

   | State | Recommended next command |
   |---|---|
   | `EMPTY` | `memoir-draft <thread>` |
   | `DRAFTED` (figure references present, exhibits not yet rendered) | `memoir-figures <thread>` first, then `memoir-review <thread>` + `memoir-audit <thread>` (parallel) |
   | `DRAFTED` (no figure references / exhibits current) | `memoir-review <thread>` + `memoir-audit <thread>` (parallel) |
   | `REVIEWED-PARTIAL` | `memoir-audit <thread>` (run the missing critic) |
   | `AUDITED-PARTIAL` | `memoir-review <thread>` (run the missing critic) |
   | `REVIEWED+AUDITED` (any critic blocks, under iteration cap) | `memoir-revise <thread>` |
   | `REVIEWED+AUDITED` (any critic blocks, AT iteration cap) | `BLOCKED — human review required` |
   | `AUDITED` (all clear) | `memoir-figures <thread>` (refresh/produce PDF+exhibits if not current), then `/anvil:project-book <project-dir>` to assemble the book |

5. Detect anomalies and surface them:
   - A `<slug>.{N}/_progress.json` with any phase `in_progress` AND the
     version dir older than 10 minutes — likely a crashed phase; the next
     invocation's `cleanup_one_staging` sweep handles stale critic
     staging.
   - A critic sibling dir without a matching `<slug>.{N}/` — orphan;
     report.
   - A gap in version numbers — report.
   - A project declaring `corpus:` with no `<slug>.{N}.corpus-audit/`
     sibling at the latest reviewed/audited `N` — the exhaustive
     provenance sweep has not run; recommend `memoir-audit <thread>`.
   - An `AUDITED` thread whose critic siblings carry a stale rubric stamp
     (`_meta.json.rubric_id` != `anvil-memoir-v1`) — informational;
     recommend `anvil:rubric-rebackport`.

## Output format

Print a markdown table to stdout:

```
| Thread          | Latest | State            | Review | Audit | Corpus-audit | Iter | Next                              |
|-----------------|--------|------------------|--------|-------|--------------|------|------------------------------------|
| 00-introduction | .2     | AUDITED          | 41/44  | clean | clean        | 2/4  | memoir-figures 00-introduction     |
| 01-childhood    | .1     | REVIEWED+AUDITED | 35/44  | flag  | clean        | 1/4  | memoir-revise 01-childhood         |
| appendix        | -      | EMPTY            | -      | -     | -            | 0/4  | memoir-draft appendix              |
```

Follow the table with an `## Anomalies` section if any were detected, and
an `## Operator notes` section for threads requiring human review
(iteration cap reached, an unresolved fabrication-class critical flag
across multiple revisions, an undeclared `corpus:`/`voice:` tier
surfaced repeatedly, etc.).

## Notes

- This command does **not** write to disk. Safe to run repeatedly. As a
  read-only command it is exempt from the per-phase git-sync hook by
  definition (SKILL.md §"Git sync hook").
- The orchestrator is the recommended per-thread entry point; the
  lifecycle commands (`memoir-draft`, `memoir-review`, `memoir-audit`,
  `memoir-revise`, `memoir-figures`) can be invoked directly in sequence.
- For the cross-chapter assembled-book view, use `/anvil:project-book
  <project-dir>` — never reimplement it here (§Scope note above).
