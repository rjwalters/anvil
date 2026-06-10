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

The detector recognizes three pre-migration shapes. **Deck, slides, and
proposal threads are in scope** alongside memo (issue #382 — the parallel
rollout of the #295/#296 model to the other rich-command-set skills):

1. **Pre-#283 classic** — `memo.N/` siblings of the portfolio dir, optional
   per-thread `BRIEF.md`, skill-fixed `memo.md` body. No project-level
   `BRIEF.md`. This shape ALSO covers the **nested-but-flat**
   deck/slides/proposal variant (the studio canary's `series-a-deck`
   shape): a thread-root directory (`<slug>/` carrying the thread-level
   BRIEF + refs + assets and optionally a per-thread `.anvil.json`)
   sitting as a SIBLING of flat `<slug>.N/` version dirs at the project
   root. The migration moves the version dirs (and critic siblings) IN
   under the thread root; the thread-root contents stay where they are
   (the studio hand-fix `2cf3f37` is the reference shape).

   **Bare sub-state (issue #408).** A pre-#283 classic project with NO
   anvil config anywhere — no project BRIEF, no `.anvil.json`, no
   skill-fixed or retained body filenames — is the **bare** shape: a
   hand-rolled workflow that independently converged on the
   `{thread}.{N}/` + `.review`/`.audit` grammar (e.g. `<slug>.N/`
   dirs carrying `paper.tex` bodies, version gaps tolerated). Bare
   projects classify and migrate as PRE_283_CLASSIC, but the project
   BRIEF is **synthesized** from observed state (there is nothing to
   merge from): every inferred or defaulted frontmatter value carries
   a `# TODO(operator)` YAML comment, the BRIEF body carries a
   mirrored operator-confirmation checklist (body prose survives
   future BRIEF rewrites verbatim; YAML comments survive the no-op
   idempotent path), and the dry-run report prints the full proposed
   BRIEF text through the same `render_project_brief` code path the
   apply step writes. Synthesis is automatic when the bare sub-state
   is detected — dry-run-by-default is the safety surface; no extra
   flag.
2. **Post-#283 with `.anvil.json`** — project root with `BRIEF.md` listing
   `documents:`, per-thread directories under
   `<project>/<slug>/<slug>.N/memo.md`, separate per-thread `.anvil.json`
   files carrying `target_length` / `target_length_overrides` /
   `rubric_overrides` (or, on deck threads, the paired `max_iterations` +
   `iteration_cap_rationale` override). Mixed-grammar projects — a
   BRIEF-bearing project where some threads are nested and others still
   sit flat — dispatch per thread: flat threads get the nesting move,
   nested threads get the in-place cleanup.
3. **Fully-migrated** — project root, `BRIEF.md` absorbs all per-doc config,
   no skill-fixed body filename remains. This is the target shape; the
   migration is a no-op on this input (idempotence contract).

**Body filenames per skill.** Memo bodies are renamed to the slug-echo
shape (`memo.md` → `<slug>.md`). Deck/slides (`deck.md`) and proposal
(`proposal.tex`) **retain their skill-fixed body filenames** — the
slug-echo rename is scoped out for those skills because the filenames
are consumed by external tooling (marp CLI, xelatex,
`anvil-proposal.cls`); see the per-skill SKILL.md body-filename notes
(issue #382). The migration for those skills is directory nesting plus
`.anvil.json` → BRIEF merge only.

**Artifact types.** The registered artifact-type enum
(`anvil/lib/project_brief.py::ArtifactType`) carries skill-identity
values `deck`, `slides`, `proposal` (issue #386), and `pub` (issue
#408) alongside the memo subtypes. The migration infers the type from
the retained body filename and writes it into the BRIEF `documents:`
entry: `deck.md` → `deck`, `proposal.tex` → `proposal`. Threads with
no retained body (memo-shaped `.md` bodies) default to
`artifact_type: investment-memo`.
The plan surfaces an inference note on every retained-body thread —
including `.tex`-bodied proposal threads — and the deck note flags the
deck-vs-slides ambiguity: `anvil:slides` threads also use `deck.md`, so
body shape alone cannot distinguish them; edit the BRIEF entry to
`slides` for a talk deck.

On **bare** threads (issue #408) the inference extends to observed
non-`.md` bodies (`*.tex`): a body with
`\documentclass{anvil-proposal}` infers `proposal`; any other
`\documentclass` infers `pub`; markdown-bodied bare threads keep the
`investment-memo` default. Every bare inference — including the
default — is paired with a `# TODO(operator)` confirmation marker;
nothing is guessed silently. Observed body filenames (e.g.
`paper.tex`) are **recorded but never renamed** — the #382 slug-echo
carve-out applies because root-level build artifacts
(`paper.tex`/`paper.pdf`) are direct evidence that external tooling
consumes the fixed name; the plan emits a deferral note instead.
Existing `.review`/`.audit` sidecars rename cleanly with the thread;
hand-rolled unstamped review content stays invisible-but-intact to
`discover_critics` per the #346 additive contract (rebackportable via
`anvil:rubric-rebackport`).

## Commands

| Command                                     | What it does                                                                                  |
|---------------------------------------------|-----------------------------------------------------------------------------------------------|
| `/anvil:project-migrate <project-dir>`      | **Dry-run.** Detect current shape, emit a per-doc migration plan. **No mutations** to disk.   |
| `/anvil:project-migrate <project-dir> --apply` | Execute the plan atomically per doc. Use `git mv` when the project is under git.           |
| `/anvil:project-migrate <project-dir> --report` | Emit a markdown report only (no plan, no mutations). Useful for portfolio surveys.        |
| `/anvil:project-migrate --enroll <file> [...]` | **Single-file enrollment** (issue #406): wrap loose `.md`/`.tex` files into project threads. Dry-run by default; `--apply` executes. Optional `--project <dir>`, `--slug <slug>`, `--artifact-type <type>`. |

See `commands/project-migrate.md` for the operator-facing contract.

## Single-file enrollment (`--enroll`, issue #406)

Adoption-target monorepos hold hundreds of **loose single-file
documents** (flat `.md`/`.tex` files in topical directories, often
date-prefixed or date-suffixed). Enrollment is the path from a bare
file to a thread:

- The file moves to `<project>/<slug>/<slug>.1/<slug>.<ext>` (`git mv`
  in-repo so history follows). `.tex` bodies slug-echo too — new
  enrollments have no external-tooling carve-out; the enclosing move
  already breaks any path-based consumer, so a plan note records the
  rename instead.
- The slug derives from the filename (lowercased, hyphens, ISO date
  prefix/suffix stripped); the stripped date is preserved as a YAML
  comment on the BRIEF entry (`# enrolled-from: <file> (date: ...)`)
  and as a body `## Enrollment log` line (body prose survives future
  BRIEF rewrites; YAML comments do not). `--slug` must already be
  canonical — it is rejected, never silently re-sanitized.
- **Existing BRIEFs are extended by surgical textual append**, never
  re-rendered: the migrate-mode re-render path is lossy (it drops
  top-level `theme:`, per-doc `render_*` / `latex_header_includes`
  keys, every YAML comment, quoting style, and entry order), so the
  enroll path inserts the new entry lines at the end of the
  `documents:` block and leaves every other byte untouched. With no
  enclosing BRIEF, a minimal one is synthesized through the same
  `render_project_brief` path as bare-project migration (#408 TODO
  discipline). Both paths are strict-validated post-write and rolled
  back on failure.
- Artifact types come from `--artifact-type` (two-tier validation per
  #394) or are inferred with a `# TODO(operator)` marker (`.md` →
  `investment-memo`; `.tex` → `proposal`/`pub` from `\documentclass`).
- Batch form: N files enroll into ONE project as N independently
  planned documents. Plan-time errors (slug collisions, non-md/tex,
  already-enrolled inputs, malformed BRIEF) abort pre-mutation;
  apply-time failures isolate per doc with the BRIEF written for the
  succeeded subset. Re-enrolling an enrolled file is a refusal, not a
  duplicate.

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

Fixtures are programmatic builders in `tests/_fixtures.py` (trees are
constructed in tmp dirs rather than baked on disk):

- `build_pre_283_classic` — pre-#283 layout (memo.N siblings, no project
  BRIEF, `memo.md` bodies).
- `build_post_283_anvil_json` — post-#283 with `.anvil.json` (project BRIEF +
  per-thread `.anvil.json`).
- `build_fully_migrated` — target shape (no-op test).
- `build_bessemer_shaped` — sanitized multi-thread snapshot exercising the
  canary case (multiple `memo.N` versions, critic siblings).
- `build_aldus_shaped_deck` — sanitized snapshot of the studio's
  pre-`2cf3f37` deck thread (thread root with BRIEF + refs + assets +
  `.anvil.json` as a sibling of flat version dirs; issue #382).
- `build_mixed_memo_deck_proposal` — the mixed-skill canary case: one
  project root with flat memo + deck + proposal threads (issue #382).
- `build_bare_version_dir_threads` — the bare adoption-target shape
  (issue #408): `.tex` bodies, version gaps {1,3,4,5,6,7}, mixed
  hand-rolled `.review`/`.audit` sidecars, root-level
  `paper.tex`/`paper.pdf` build artifacts, `figures/`.
- `build_loose_file_in_existing_project` — migrated project with a
  tripwire-laden operator BRIEF (`theme:`, `render_*` keys, YAML
  comments, quoting, non-alpha entry order) + a dated loose file
  (issue #406).
- `build_loose_file_no_project` — bare topical dir with date-prefixed
  and date-suffixed loose files (issue #406).
- `build_loose_file_batch` — batch of loose files incl. a `.tex` with
  `\documentclass`, an intra-batch slug-collision pair, and a
  non-md/tex refusal target (issue #406).

Test files:

- `test_project_migrate_detect.py` — shape detection across all fixtures.
- `test_project_migrate_plan.py` — per-shape plan generation.
- `test_project_migrate_apply.py` — apply correctness, atomicity, rollback.
- `test_project_migrate_dry_run.py` — snapshot-and-diff: dry-run
  leaves the input byte-identical.
- `test_project_migrate_idempotent.py` — apply on fully-migrated input is a
  no-op (zero diff).
- `test_project_migrate_verify.py` — post-apply the project rounds-trips
  through `discover_thread_root` + `load_project_brief` (incl. the mixed
  fixture through the promoted `anvil.lib` primitives).
- `test_project_migrate_detect_mixed.py` — nested-but-flat + mixed-skill
  classification and inventory (issue #382).
- `test_project_migrate_plan_mixed.py` — nesting renames, critic-sibling
  moves, retained-body no-rename, iteration-cap pair extraction.
- `test_project_migrate_apply_mixed.py` — nested tree correctness +
  cross-skill discovery smoke through `anvil.lib.project_discovery`.
- `test_project_migrate_idempotent_mixed.py` — re-apply on a migrated
  mixed project is zero diff.
- `test_project_migrate_bare.py` — bare sub-state (issue #408):
  characterization lock (PRE_283_CLASSIC), artifact-type inference +
  TODO markers, dry-run BRIEF preview, apply + post-apply contracts
  (`discover_thread_root`, strict load, verify, `discover_critics`
  excludes unstamped sidecars), byte-identical idempotence.
- `test_project_migrate_enroll_slug.py` — slug derivation + canonical
  `--slug` validation (issue #406).
- `test_project_migrate_enroll_append.py` — surgical-append byte
  preservation against the tripwire BRIEF + strict re-parse + append
  refusal cases (issue #406).
- `test_project_migrate_enroll_apply.py` — enroll end-to-end: existing
  project, no-project synthesis, batch, `.tex` inference, git-mv
  history follow, per-doc failure isolation with succeeded-subset
  BRIEF write (issue #406).
- `test_project_migrate_enroll_errors.py` — plan-time hard errors
  (collisions, refusals, idempotency-as-refusal, malformed BRIEFs,
  flag validation) all pre-mutation (issue #406).
- `test_project_migrate_enroll_dry_run.py` — dry-run default leaves
  the tree digest unchanged; the previewed BRIEF is byte-identical to
  the apply-time write (issue #406).
