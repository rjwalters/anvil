# scripts/

Operational scripts for anvil maintenance and installation.

## Scripts

| Script | Status | Purpose |
|---|---|---|
| `version.sh` | working | Show / check / set the anvil version across all version-bearing files |
| `install-anvil.sh` | working | Install anvil into a consumer repo (`./install-anvil.sh /path/to/repo`) |
| `new-skill.sh` | planned | Scaffold a new skill from `anvil/templates/` |

## Install design

`install-anvil.sh [OPTIONS] <target-repo>` performs an additive, idempotent install
that coexists with Loom in the same consumer repo.

### Flags

| Flag | Purpose |
|---|---|
| `--skills=<a,b,c>` | Install only the listed skills (default: all). Validates names before writing. |
| `--force` | Overwrite consumer-edited skill files (default: skip with warning). |
| `--dry-run` | Print planned actions, write nothing. |
| `-y`, `--yes` | Non-interactive (skip confirmation prompts). |
| `-h`, `--help` | Show help and exit. |

### Stages

1. Resolve `ANVIL_ROOT` from the script's parent directory and extract `ANVIL_VERSION` from `CLAUDE.md`.
2. Resolve and validate `TARGET` (expand `~`, `cd && pwd`); git is **not** required (anvil is forge-optional).
3. Active-install guard: existing `.anvil/` triggers upgrade mode; otherwise fresh install.
4. Read source skill manifest from `anvil/skills/*/SKILL.md`; filter by `--skills=`; validate fast.
5. Copy `anvil/lib/` -> `.anvil/lib/` (always-overwrite framework code).
6. Copy `anvil/roles/` -> `.anvil/roles/` (always-overwrite framework code).
7. For each selected skill: byte-diff against source; skip if consumer-modified (unless `--force`);
   otherwise install canonical body at `.anvil/skills/<name>/` and regenerate the thin Claude
   registration shim at `.claude/skills/anvil-<name>/SKILL.md` (depth 1 — required by Claude
   Code's skill-discovery contract).
8. CLAUDE.md additive merge using `<!-- BEGIN ANVIL --> / <!-- END ANVIL -->` markers (mirrors
   Loom's `<!-- BEGIN LOOM ORCHESTRATION -->` pattern so the two installers coexist).
9. Write `.anvil/install-metadata.json` (version, install date, installed skills, skipped overrides).
10. Print summary.

### Install layout convention (resolved per issue #1)

Anvil-shipped skills land at `.anvil/skills/<name>/` (canonical bodies) with thin registration
at `.claude/skills/anvil-<name>/SKILL.md` (depth 1, namespace flattened into the directory
name — Claude Code only discovers `SKILL.md` at `.claude/skills/<name>/SKILL.md`). This mirrors
Loom's `.loom/` separation between framework code and Claude registration, and preserves
consumer-override semantics: edits to `.anvil/skills/<name>/` are detected on re-install and
preserved by default.

### CLAUDE.md merge semantics

| Existing target state | Installer behavior |
|---|---|
| No `CLAUDE.md` | Create with just the marker block. |
| Has Anvil markers | Replace block in place (preserves all other content, including any Loom block). |
| Has other content, no Anvil markers | Append marker block at end, separated by a blank line. |

Running the installer twice produces a byte-identical `CLAUDE.md`.

### Override semantics

Consumer edits to `.anvil/skills/<name>/` are detected by byte-diff against the source
`anvil/skills/<name>/`. By default the installer skips modified skills with a warning and
records them in `install-metadata.json` under `skipped_overrides`. Re-run with `--force` to
overwrite.

Claude resolves `anvil-<name>` via the registration shim at `.claude/skills/anvil-<name>/`,
which points at the canonical `.anvil/skills/<name>/` path. The single location is both the
install target and the override target -- there is no separate "shipped vs. override" path.
Slash commands surface as `/anvil-<name>:<command>` (e.g. `/anvil-memo:memo-draft`); the
`anvil-` directory-name prefix matches the frontmatter `name:` field that `write_shim`
emits, and the depth-1 placement satisfies Claude Code's discovery contract.

### v0 distribution model

The installer copies from a local checkout (the script's parent directory). A future "fetch
from release" branch can be added when anvil ships via package managers; out of scope for v0.
