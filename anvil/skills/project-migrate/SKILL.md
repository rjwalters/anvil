---
name: project-migrate
description: Migrate existing studio projects to the post-#295 / post-#296 project-org model (BRIEF.md absorbs all config; `<project>/<slug>/<slug>.<N>/` shape; body filename echoes slug).
domain: anvil
type: skill
user-invocable: true
---

# anvil:project-migrate — Bridge existing projects to the new model

The `project-migrate` skill is a one-shot bridge tool: given a path to a studio
project that pre-dates the issue #295 / #296 contract, it migrates the project
in place to the canonical post-#295 / post-#296 shape:

```
<project>/
  BRIEF.md                  # ONE project brief absorbing all anvil config
  <slug>/
    <slug>.1/
      <slug>.md             # body filename echoes the slug
      _progress.json
      ...
    <slug>.2/
      <slug>.md
      ...
    <slug>.N/
  research/                 # shared evidence pool (untouched)
  refs/                     # shared per-project references (optional, untouched)
```

The migration tool exists because issues #295 and #296 changed the contract that
every existing studio project depended on. Without a bridge, every existing
project becomes silently broken at the first revise after the contract change.

## What this skill does

`project-migrate` is **opinionated, idempotent, and dry-run first**. It:

- **Detects** the current on-disk shape by walking the project tree.
- **Plans** the per-document migration steps (rename + content rewrite).
- **Applies** the plan atomically per document — a failure in doc B does not
  half-migrate doc A.
- **Verifies** by re-running `discover_thread_root` + `load_project_brief` on
  the result.

There are **no back-compat flags**. The skill exists to converge existing
projects onto one shape; it does not preserve the legacy shape under any
option. If a consumer needs to keep the legacy layout, they should not run the
migration.

## Recognized current shapes

The detector recognizes three pre-migration shapes:

1. **Pre-#283 classic** — `memo.N/` siblings of the portfolio dir, optional
   per-thread `BRIEF.md`, skill-fixed `memo.md` body. No project-level
   `BRIEF.md`.
2. **Post-#283 with `.anvil.json`** — project root with `BRIEF.md` listing
   `documents:`, per-thread directories under
   `<project>/<slug>/<slug>.N/memo.md`, separate per-thread `.anvil.json`
   files carrying `target_length` / `target_length_overrides` /
   `rubric_overrides`.
3. **Fully-migrated** — project root, `BRIEF.md` absorbs all per-doc config,
   body filename is `<slug>.md`. This is the target shape; the migration is a
   no-op on this input (idempotence contract).

## Commands

| Command                                     | What it does                                                                                  |
|---------------------------------------------|-----------------------------------------------------------------------------------------------|
| `/anvil:project-migrate <project-dir>`      | **Dry-run.** Detect current shape, emit a per-doc migration plan. **No mutations** to disk.   |
| `/anvil:project-migrate <project-dir> --apply` | Execute the plan atomically per doc. Use `git mv` when the project is under git.           |
| `/anvil:project-migrate <project-dir> --report` | Emit a markdown report only (no plan, no mutations). Useful for portfolio surveys.        |

See `commands/project-migrate.md` for the operator-facing contract.

## Atomicity & rollback

The skill applies its plan one document at a time. Within a single doc, the
sequence is:

1. Compute the new layout (target paths for every file the doc owns).
2. Perform the renames + content rewrites.
3. If any step fails, roll back the doc's changes from a per-doc snapshot
   taken before the apply began (the snapshot lives at `.anvil-migrate-rollback/<slug>/`
   under the project root and is removed on successful apply).

Failures in doc B do not affect already-migrated docs A. A partial apply on
doc B is rolled back before the skill moves on (or surfaces the error and
stops, depending on the failure mode).

## Idempotence

Re-running `--apply` on a project that has already been migrated is **zero
diff**: the detector reports the project as fully-migrated and the planner
emits an empty plan. The verify step then succeeds without writing.

This is the **canonical safety net** for operators who lose track of which
projects they've already migrated.

## Cross-thread reference rewriting

The plan walks every `<slug>.md` body for cross-thread references using the
old `memo.N` shape (e.g., "see `memo.7` §3"). When found, the planner emits a
content-rewrite step that updates the reference to the new `<slug>.N` shape.
This handles the canary case where multiple `memo.N` versions of a single
thread inadvertently cite one another.

## Relationship to `anvil/skills/memo/lib/migrate.py`

The memo-side LaTeX bootstrap helper (`migrate.py`) currently writes a legacy
`.anvil.json` file when ingesting a LaTeX memo source. Per the carve-out from
issue #296's judge review, this skill **runs as a post-step** to that helper:
an operator who runs `memo-migrate` to ingest a LaTeX source produces a
`.anvil.json`-shaped thread; running `project-migrate --apply` on the
resulting portfolio merges the `.anvil.json` into the project `BRIEF.md`.

A future refactor may retarget `memo-migrate` to write `BRIEF.md` directly;
for now the two skills compose cleanly under the post-step model, and
`project-migrate`'s idempotence means re-running it is safe.

## State machine

The skill does not produce a versioned artifact. It runs to completion as a
one-shot. The on-disk evidence is the rewritten project tree itself.

## Tests

Fixtures under `tests/fixtures/`:

- `pre_283_classic/` — pre-#283 layout (memo.N siblings, no project BRIEF,
  `memo.md` bodies).
- `post_283_anvil_json/` — post-#283 with `.anvil.json` (project BRIEF +
  per-thread `.anvil.json`).
- `fully_migrated/` — target shape (no-op test).
- `bessemer_shaped/` — sanitized multi-thread snapshot exercising the canary
  case (multiple `memo.N` versions, critic siblings).

Test files:

- `test_project_migrate_detect.py` — shape detection across all fixtures.
- `test_project_migrate_plan.py` — per-shape plan generation.
- `test_project_migrate_apply.py` — apply correctness, atomicity, rollback.
- `test_project_migrate_dry_run.py` — snapshot-and-diff: dry-run
  leaves the input byte-identical.
- `test_project_migrate_idempotent.py` — apply on fully-migrated input is a
  no-op (zero diff).
- `test_project_migrate_verify.py` — post-apply the project rounds-trips
  through `discover_thread_root` + `load_project_brief`.
