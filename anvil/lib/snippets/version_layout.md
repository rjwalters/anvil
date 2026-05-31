# Version and critic sibling directory layout

Canonical naming convention for anvil artifact directories. Every skill
follows this layout; the discovery logic in `thread_state.md` and
`critics.md` depends on it.

## Directory taxonomy

Given a thread slug `<thread>` (e.g., `acme-seed`, `q3-method`,
`kdd-2026-keynote`, `acme-widget`), a portfolio contains these
directory kinds:

| Kind | Pattern | Purpose | Mutability |
|---|---|---|---|
| **Thread root** | `<thread>/` | Brief, refs, per-thread overrides | Mutable (human-edited) |
| **Version** | `<thread>.{N}/` | One drafted version of the artifact | Immutable once `_progress.json` records `done` |
| **Critic sibling** | `<thread>.{N}.<tag>/` | Output of one critic on version N | Immutable once written |
| **Pre-draft sibling** | `<thread>.0.<tag>/` | Pre-draft phase output (e.g., outline, litsearch) | Immutable once written |
| **Project root** | `<project>/` | Per-project shared context (report skill) | Mutable (`_project.md`) |
| **Terminal sibling** | `<thread>.{N}.<tag>/` (e.g., `.handout/`, `.promote/`) | Terminal-state export or acknowledgment | Immutable once written |

## Naming rules

1. **Version numbering**: integer, starting at `1` for the first drafted
   version. No zero-pad (`acme-seed.1/`, not `acme-seed.01/`). Versions
   are dense — there are no gaps in a normal lifecycle.
2. **Critic tag**: a single short token, no nested dots, no spaces. Use
   `review`, `audit`, `s101`, `narrative`, `market`, `design`,
   `preflight`, `litsearch`, `outline`, `rehearse`, `handout`, `promote`.
3. **Pre-draft phase tag**: special case — a sibling at `<thread>.0.<tag>/`
   may exist before any `<thread>.1/`. Reserved for outputs that feed
   the first drafter (outline for slides, litsearch for pub, brief intake
   for deck).
4. **Final-package suffix**: `<thread>.final/` is reserved for skills
   that produce a separate assembled submission package (e.g.,
   ip-uspto's filing bundle). This is NOT a critic sibling; it does not
   carry a numeric version suffix.

## Discovery globs

A reviser or orchestrator discovers what exists for a thread by globbing:

```
<thread>.{N}/              All versioned dirs (sort by N to find latest).
<thread>.{N}.*/            All critic siblings for version N.
<thread>.0.*/              All pre-draft siblings.
<thread>.final/            Optional terminal submission package.
```

To find the latest version:

```
latest_N = max(N for N in versions_dirs(<thread>))
```

To find all critic siblings for the latest version:

```
glob("<thread>.{latest_N}.*/")  minus the bare "<thread>.{latest_N}/"
```

## N+1 allocation

When a reviser produces the next version after consuming all `<thread>.{N}.*/`
critic siblings, the next version is `<thread>.{N+1}/`. The reviser MUST:

1. Verify `<thread>.{N+1}/` does not already exist (a partially-failed
   revise should be cleaned up via the crash recovery contract).
2. Carry forward `metadata.iteration` as `N+1` and preserve
   `metadata.max_iterations` from the prior version's `_progress.json`
   (or inherit from `<thread>/.anvil.json`).

## `<thread>.0.<tag>/` rationale

Why `0` for pre-draft siblings? It places them in the orchestrator's
enumeration alongside other siblings (which use `<N>.<tag>/` shapes),
preserving the "glob `<thread>.*` and parse" discovery pattern. Three
skills currently use this:

- `slides.0.outline/` — narrative outline before draft.
- `pub.0.litsearch/` — pre-draft literature search.
- `deck.0/` (no tag) — brief-intake output (special case: bare `.0/`
  carries `BRIEF.md` itself).

When an orchestrator detects a gap (e.g., `<thread>.0.outline/` exists
but no `<thread>.1/`), the state is `OUTLINED` (or `BRIEF_DONE`, etc.,
per the skill's state machine), not an anomaly.

## Convenience `.latest` symlinks (optional consumer convention)

Consumers MAY add convenience symlinks per project that alias the
highest-N version of a thread:

```
<thread>.latest        -> <thread>.{max_N}/
<thread>.latest.review -> <thread>.{max_N}.review/
<thread>.latest.<tag>  -> <thread>.{max_N}.<tag>/      e.g., .latest.design, .latest.audit
```

These are **optional and consumer-maintained**. Anvil-shipped commands
do not write, require, or read them in v0 — they exist purely to give
human operators and downstream tooling a stable path that always
resolves to the current version (no N-parsing required).

### Discovery-glob guarantee

The discovery enumeration documented in `thread_state.md` (lines 33–53)
matches only directories whose suffix is a digit-N, optionally followed
by an alphanumeric critic tag:

| Pattern enumerated | Regex |
|---|---|
| `<thread>.{N}/`        | `^<slug>\.(\d+)$` |
| `<thread>.{N}.<tag>/`  | `^<slug>\.(\d+)\.([a-zA-Z0-9-]+)$` |

A `.latest` (or `.latest.review`, `.latest.design`, …) suffix is **not**
a digit and is therefore **invisible** to the version and sibling
enumerators — even when the symlink resolves to a real directory. The
`enumerate_versions` / `enumerate_siblings` functions in
`thread_state.md` return the same list whether or not `.latest`
symlinks are present in the portfolio directory.

This is the load-bearing guarantee for the convention: a consumer who
adds `<thread>.latest -> <thread>.{max_N}` does not perturb anvil's
state-machine derivation. The symlinks are inert from the framework's
perspective.

### Typical usage

After a reviser writes `<thread>.{N+1}/`, the consumer's wrapper script
re-points the symlink in a single atomic step:

```
ln -sfn <thread>.{N+1} <thread>.latest
ln -sfn <thread>.{N+1}.review <thread>.latest.review   # if/when the review lands
```

Downstream tools (figure scripts cross-referencing another thread,
share scripts pointing at "the current PDF", `pdfinfo` checks in CI)
can then hardcode `<thread>.latest/...` and never go stale. Figure
scripts in particular can reference other-skill artifacts via stable
paths like `refs/<thread>.latest/...` rather than hardcoding
`refs/<thread>.8/...`, which silently goes stale on the next revision.

The studio canary consumer (2026-05-30) ships an ~80-line bash refresh
script (`output/refresh-latest-symlinks.sh`, idempotent, dry-run-able)
that sweeps every project dir and `ln -sfn`s the `.latest` aliases for
every thread it finds. Anvil does **not** bundle this script — it is a
~one-page idiom each consumer codifies to taste (in bash, Python, or
their make/just/task runner).

### Edge cases worth noting

- **Git tracks symlink targets as text.** Updating
  `memo.latest -> memo.7` to `memo.latest -> memo.8` is a one-line
  semantic diff, which makes version bumps self-documenting in commit
  history.
- **`git status` shows symlinks as modified when the target changes.**
  This is the desired behavior — the version bump is visible.
- **Some web servers don't follow symlinks** (Apache MultiViews,
  restrictive S3 configs). Edge case for consumers who publish
  artifact trees over HTTP without an explicit copy step.
- **Cross-platform**: macOS Finder and GNU/Linux `ls` follow symlinks
  natively; Windows shells handle them via WSL or `mklink /D`.

### When to promote to a `lib/` primitive

Not in v0. Per the "wait for the second consumer before generalizing"
rule (CLAUDE.md), the `.latest` refresh logic stays consumer-side
until a second consumer requests upstream automation. If/when that
happens, the natural shape is
`anvil.lib.latest_symlinks.refresh(project_dir)` called from
`memo-revise` / `deck-revise` / similar at the end of a successful
write — but only after the convention has been observed in the wild.

## Immutability contract

A directory becomes immutable once its `_progress.json` records the
relevant phase as `done`. After that point:

- The reviser, orchestrator, and any other agent treats the directory
  as read-only.
- Files are never edited in place. To "fix" something, produce a new
  version (`<thread>.{N+1}/`) with a `changelog.md` explaining what
  changed.
- The exception is the thread root (`<thread>/`), which is mutable
  because the brief and refs are author-editable inputs, not
  artifact outputs.

## See also

- `thread_state.md` — derive state-machine position from on-disk layout.
- `critics.md` — discover and aggregate critic siblings.
- `progress.md` — `_progress.json` schema and merge rules.
