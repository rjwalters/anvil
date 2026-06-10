---
name: project-migrate
description: Migrate an existing studio project to the post-#295 / post-#296 canonical model (BRIEF.md absorbs all config, `<slug>.md` body filename, `<project>/<slug>/<slug>.<N>/` shape).
---

# `/anvil:project-migrate`

Bridge tool. Migrates an existing studio project in place to the canonical
post-#295 / post-#296 model.

## Usage

```
/anvil:project-migrate <project-dir>             # dry-run (no mutations)
/anvil:project-migrate <project-dir> --apply     # execute the plan
/anvil:project-migrate <project-dir> --report    # markdown report only

/anvil:project-migrate --enroll <file> [<file> ...]    # dry-run enrollment
    [--project <dir>] [--slug <slug>] [--artifact-type <type>] [--apply]
```

`<project-dir>` is the project root: the directory that holds (or will hold)
the project-level `BRIEF.md` and the per-thread `<slug>/` directories.

## Procedure

### 0. Mode dispatch

If neither `--apply` nor `--report` is passed, the command runs in **dry-run
mode**: it detects, plans, and prints, but writes nothing to disk.

`--apply` and `--report` are mutually exclusive. Passing both is rejected.

`--enroll <file> [...]` selects **single-file enrollment mode** (issue
#406): instead of migrating a whole project, it wraps one or more loose
`.md` / `.tex` files into project threads. Enrollment runs through
`orchestrate.run_enroll(...)` (dry-run by default, like every mode in
this skill) — see §6 below.

### 1. Detect current shape

Call `detect.detect_shape(project_dir)`. This returns a `Shape` enum:

- `Shape.FULLY_MIGRATED` — project root with `BRIEF.md` absorbing all config,
  `<slug>/<slug>.N/<slug>.md`.
- `Shape.POST_283_ANVIL_JSON` — project root with `BRIEF.md` listing
  `documents:`, per-thread directories under `<project>/<slug>/`, but with
  separate `.anvil.json` files and possibly `memo.md` bodies.
- `Shape.PRE_283_CLASSIC` — no project-level `BRIEF.md`; `memo.N/` siblings
  directly under the project root; skill-fixed `memo.md` bodies. The
  **bare sub-state** (issue #408 — version-dir families with no anvil
  config anywhere, e.g. `paper.tex` bodies; `ProjectInventory.is_bare`)
  also classifies here: the BRIEF is then SYNTHESIZED from observed
  state with `# TODO(operator)` confirmation markers on every inferred
  value, and the report header reads
  `pre_283_classic (bare — BRIEF will be synthesized)`.
- `Shape.UNKNOWN` — not recognizable; emit a diagnostic and exit non-zero.

### 2. Plan

Call `plan.build_plan(project_dir, shape)`. Returns a `Plan` object listing
per-document `DocumentPlan` entries. Each entry carries:

- `slug` — final slug name.
- `source_dir` — current on-disk directory (may equal target).
- `target_dir` — where the doc should live post-migration
  (`<project>/<slug>/`).
- `renames` — list of `(source_path, target_path)` pairs for filesystem moves.
- `content_rewrites` — list of `(file_path, old_string, new_string)` tuples
  for in-file content edits (cross-thread refs, body filename refs).
- `brief_merge` — optional `BriefMergeOp` recording the `documents:` entry
  to add/update in the project-level `BRIEF.md`.
- `anvil_json_source` — optional path to a `.anvil.json` that will be merged
  into the BRIEF entry.
- `notes` — operator-facing notes (e.g., "cross-thread references rewritten:
  3 occurrences").

### 3. Report (dry-run / `--report`)

Print the plan as a markdown report:

- Header naming the project, detected shape, and plan summary.
- One section per document with its planned renames, content rewrites, and
  BRIEF merge.
- The **full proposed `BRIEF.md` text** (issue #408) whenever the plan
  carries BRIEF merges — rendered through the same
  `apply.render_project_brief` code path the apply step writes, so the
  preview is byte-identical to the eventual write.
- Footer with the verify-step preview ("after apply, the project would
  round-trip through `discover_thread_root` + `load_project_brief`").

In dry-run mode, the command exits 0 after printing. In `--report` mode it
also exits 0.

In `--apply` mode, the report is printed first (so the operator can see what
is about to happen), then the apply step runs.

### 4. Apply (`--apply` only)

For each `DocumentPlan` in the plan:

1. Take a per-doc snapshot at
   `<project>/.anvil-migrate-rollback/<slug>/` (copy the source dir).
2. Run the renames + content rewrites.
3. If the project is under git (`.git/` exists at or above `project_dir`),
   prefer `git mv` over plain `shutil.move`. Plain renames still work
   correctly; `git mv` is preferred so history follows.
4. If any step in the doc fails, roll back this doc only:
   restore from the snapshot and surface the error. Already-migrated docs are
   not affected.
5. On success, remove the per-doc snapshot.

After all per-doc applies, write the project-level `BRIEF.md` with the merged
`documents:` list. (BRIEF write is the LAST step — until it succeeds, the
existing `BRIEF.md`, if any, is unchanged on disk.) Use a temp-file + rename
to make the BRIEF write atomic.

### 5. Verify (`--apply` only)

Call `verify.verify_migration(project_dir)`:

1. `discover_thread_root(<project>/<slug>/<slug>.N/<slug>.md)` returns a
   `DiscoveryResult` for every slug.
2. `load_project_brief(project_dir)` parses cleanly and lists every slug.
3. No `.anvil.json` files remain anywhere under `project_dir`.
4. No `memo.md` files remain (they should all be `<slug>.md`).
5. No `memo.N/` directories remain at the project root (they should all be
   `<slug>.N/` under their `<slug>/` parent).

Report each verify result. If any fail, exit non-zero with the failures.

### 6. Enrollment mode (`--enroll`, issue #406)

Wraps loose single-file documents (flat `.md` / `.tex` files in topical
directories) into project threads:

```
/anvil:project-migrate --enroll corporate/memos/2026-05-19-board-update.md
/anvil:project-migrate --enroll ip/*.md --project ip --apply
```

Call `orchestrate.run_enroll(files, project=..., slug=...,
artifact_type=..., apply=...)`. The flow:

1. **Project resolution**: `--project` if given (must exist; BRIEF
   optional — created if absent); else walk up from the file looking
   for an existing project BRIEF (bounded by the git repo root); else
   propose the file's parent as a new project root.
2. **Slug derivation**: from `--slug` (must already be canonical —
   `^[a-z0-9][a-z0-9-]*$`; rejected, never re-sanitized), else from the
   filename: leading/trailing ISO date token stripped (and preserved as
   a YAML comment on the BRIEF entry plus a body enrollment-log line),
   lowercased, non-alphanumeric runs collapsed to `-`.
3. **Mechanics**: move the file to `<project>/<slug>/<slug>.1/<slug>.<ext>`
   (`git mv` in-repo so history follows; plain move otherwise). `.tex`
   bodies slug-echo too — new enrollments have no external-tooling
   carve-out (the enclosing move already breaks any path-based
   consumer); a plan note records the rename and that references to the
   old path are NOT rewritten.
4. **BRIEF write**: with an existing BRIEF, the new `documents:`
   entries are added by **surgical textual append** at the end of the
   `documents:` block — every pre-existing byte (YAML comments, top-level
   `theme:`, per-doc `render_*` keys, quoting, entry order) is preserved
   byte-identically, and the body gains an `## Enrollment log` line.
   With no BRIEF, a minimal one is synthesized via
   `render_project_brief` with the #408 TODO-marker discipline. The
   write is strict-validated (`load_project_brief_strict`,
   `validate_dirs=True`) and rolled back on any parse failure.
5. **Artifact type**: `--artifact-type` validated against the two-tier
   registry (#394: registered + consumer-declared); else inferred WITH a
   `# TODO(operator)` marker (`.md` → `investment-memo`;
   `.tex` with `\documentclass{anvil-proposal}` → `proposal`; other
   `\documentclass` → `pub`).
6. **Batch semantics**: N files → N independently-planned
   `DocumentPlan`s in ONE project. Plan-time errors (slug collisions —
   existing or intra-batch, non-md/tex inputs, already-enrolled inputs,
   malformed BRIEF) abort the whole batch BEFORE any mutation.
   Apply-time failures isolate per document (snapshot rollback); the
   BRIEF is written for the **succeeded subset**.

Hard errors (plan-time, pre-mutation):

- Slug collision with a BRIEF entry, an on-disk path, or another batch
  member — the error names the conflict; suggest `--slug`.
- Non-`.md`/`.tex` input; `BRIEF.md` / `README.md` inputs.
- Already-enrolled input (inside a version dir, or
  `discover_thread_root` resolves it) — re-enrolling is a refusal, not
  a duplicate (idempotency).
- Existing BRIEF that fails strict parsing — never modify a BRIEF we
  can't parse.
- A BRIEF-less project root containing other thread-shaped dirs — run
  plain `project-migrate` on it first.
- Empty derived slug (date-only or symbol-only stems) — pass `--slug`.

## Output

In all modes, the command prints a markdown report to stdout. In `--apply`
mode it also writes filesystem changes.

The report follows this shape:

```markdown
# Project migration: <project-name>

**Project root**: <abs path>
**Detected shape**: <Shape>
**Documents**: <N>

## Plan

### <slug-1>
- Rename: `<source>/memo.3/` → `<slug-1>/<slug-1>.3/`
- Rename: `<slug-1>.3/memo.md` → `<slug-1>.3/<slug-1>.md`
- Content rewrite: `<slug-1>.3/<slug-1>.md`:
  - `memo.2` → `<slug-1>.2` (1 occurrence)
- BRIEF merge: add `<slug-1>` to `documents:` with target_length, rubric_overrides
  from `.anvil.json`.

### <slug-2>
- ...

## Verification preview

After apply, the project would round-trip through `discover_thread_root` +
`load_project_brief` cleanly.
```

## Errors

- Source directory does not exist or is not a directory: hard-fail.
- `--apply` and `--report` both passed: hard-fail.
- Detection returns `Shape.UNKNOWN`: hard-fail with a diagnostic.
- Apply step fails for a doc: per-doc rollback, then report the failure and
  exit non-zero. Already-migrated docs are not rolled back.
- Verify fails after apply: report the failures and exit non-zero. The
  filesystem state is left in place (the operator needs to inspect).

## Idempotence

Re-running `--apply` on a fully-migrated project produces a `Shape.FULLY_MIGRATED`
detection, an empty plan, and a clean verify. Zero diff on disk.

## Relationship to `anvil:memo-migrate`

The memo-side LaTeX bootstrap (`anvil:memo-migrate`) produces a thread in the
post-#283 with `.anvil.json` shape. Running `/anvil:project-migrate <project>
--apply` on the resulting portfolio is the documented post-step that
consolidates the `.anvil.json` into the project `BRIEF.md`. The composition
works without flags or special-casing — `project-migrate` recognizes the
post-#283 shape and migrates it the same way it would migrate any other
post-#283 project.
