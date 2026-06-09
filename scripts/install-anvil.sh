#!/usr/bin/env bash
# install-anvil.sh - Install Anvil into a consumer repository
#
# Usage:
#   ./scripts/install-anvil.sh [OPTIONS] <target-repo>
#
# Options:
#   --skills=<a,b,c>  Install only the listed skills (default: all)
#   --force           Overwrite consumer-edited skill files (default: skip with warning)
#   --dry-run         Print planned actions, write nothing
#   --check-deps      Check renderer dependencies (marp/pdftoppm/mmdc/pdfjam) and exit
#   --no-sync         Skip the post-install `uv sync --project .anvil` step
#                     (useful for offline installs or hosts without uv)
#   -y, --yes         Non-interactive (skip confirmation prompts)
#   -h, --help        Show this help and exit
#
# Examples:
#   ./scripts/install-anvil.sh /tmp/test-repo
#   ./scripts/install-anvil.sh --skills=memo /tmp/test-repo
#   ./scripts/install-anvil.sh --dry-run --skills=memo /tmp/test-repo
#   ./scripts/install-anvil.sh --force /tmp/test-repo
#   ./scripts/install-anvil.sh --no-sync /tmp/test-repo
#
# Layout produced in <target-repo> (issue #230 — uv-runnable consumer install):
#   .anvil/anvil/                      Importable Python package mirror.
#                                      `from anvil.lib.render_gate import gate`
#                                      resolves to .anvil/anvil/lib/render_gate.py.
#     anvil/lib/                       Framework Python (was .anvil/lib/ pre-#230).
#     anvil/skills/<name>/lib/         Skill-side Python.
#   .anvil/pyproject.toml              Generated uv project descriptor. Declares
#                                      pydantic + pyyaml as base deps so a
#                                      `uv sync --project .anvil` from the
#                                      consumer root pulls the framework's
#                                      runtime dependencies without referencing
#                                      the anvil source repo.
#   .anvil/roles/                      Generic role definitions (always installed).
#   .anvil/skills/<name>/              Canonical skill bodies (consumer override
#                                      target: SKILL.md, commands/, templates/,
#                                      rubric.md, examples/, etc.). The skill's
#                                      Python `lib/` lives separately under
#                                      .anvil/anvil/skills/<name>/lib/ so the
#                                      import path and the override path are
#                                      explicitly distinct.
#   .anvil/CLAUDE.md                   Full Anvil guide.
#   .anvil/install-metadata.json       Manifest (version, skills, overrides,
#                                      skill_hashes, layout_version).
#   .claude/skills/anvil-<name>/SKILL.md  Thin Claude registration shim
#                                         (depth 1: Claude Code only discovers
#                                         SKILL.md at .claude/skills/<name>/.)
#   .claude/agents/anvil-<skill>-<phase>.md  Per-skill-phase subagent
#                                            registrations (issue #377).
#                                            Mirrors loom-* agent files.
#                                            Pattern-matched copy so the
#                                            installer never disturbs
#                                            non-anvil agents under
#                                            .claude/agents/ (e.g. loom-*).
#   CLAUDE.md                          Updated with additive <!-- BEGIN ANVIL --> block.
#
# Anvil is forge-optional: git is not required in the target.
# Coexists with Loom: CLAUDE.md merges are additive and marker-bounded.
#
# v0 distribution model: installs from a local checkout (this script's parent dir).
# A future "fetch from release" branch can be added when Anvil ships via package
# managers; out of scope for the v0 implementation.
#
# Layout note (issue #230): Prior installs shipped framework Python at
# `.anvil/lib/` and skill Python at `.anvil/skills/<name>/lib/`. That layout
# was NOT importable as `anvil.lib.*` because there was no `anvil/` package
# root and no `pyproject.toml`. From this version the install ships an
# uv-runnable `.anvil/anvil/` package mirror + `.anvil/pyproject.toml`, and
# `uv run --project .anvil python -c "from anvil.lib.render_gate import gate"`
# works from the consumer root with no manual `uv add` or symlink shims.
# The pre-#230 `.anvil/lib/` location is detected on upgrade and a one-line
# migration warning surfaces (we don't auto-delete to avoid surprising
# consumers who hand-edited override files there).

set -euo pipefail

# ----- ANSI colors -----------------------------------------------------------
if [[ -t 1 ]]; then
  RED=$'\033[0;31m'
  GREEN=$'\033[0;32m'
  BLUE=$'\033[0;34m'
  YELLOW=$'\033[1;33m'
  CYAN=$'\033[0;36m'
  NC=$'\033[0m'
else
  RED=""; GREEN=""; BLUE=""; YELLOW=""; CYAN=""; NC=""
fi

error() { echo "${RED}error: $*${NC}" >&2; exit 1; }
info()  { echo "${BLUE}> $*${NC}"; }
ok()    { echo "${GREEN}  ok: $*${NC}"; }
warn()  { echo "${YELLOW}  warn: $*${NC}"; }
note()  { echo "${CYAN}  note: $*${NC}"; }

usage() {
  # The Usage / Options / Examples block lives in the header comment. The
  # range covers through the "Layout produced" header line so --help shows
  # the operator-facing surface (flags + examples + brief layout summary)
  # without dumping the long architectural notes that follow.
  sed -n '2,55p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

# ----- CLAUDE.md marker constants -------------------------------------------
ANVIL_MARK_BEGIN='<!-- BEGIN ANVIL -->'
ANVIL_MARK_END='<!-- END ANVIL -->'
ANVIL_POINTER='This repository uses [Anvil](https://github.com/rjwalters/anvil) for AI-powered artifact creation. See `.anvil/CLAUDE.md` for the full guide (skills, rubric, state machine). To upgrade Anvil, re-run `install-anvil.sh .` from the anvil checkout without `--skills=` to pick up newly-shipped skills; pass `--skills=...` only to install a strict subset.'

# ----- Argument parsing ------------------------------------------------------
SKILLS_FILTER=""
FORCE=false
DRY_RUN=false
CHECK_DEPS_ONLY=false
NON_INTERACTIVE=false
NO_SYNC=false
TARGET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skills=*) SKILLS_FILTER="${1#--skills=}"; [[ -z "$SKILLS_FILTER" ]] && error "--skills requires a comma-separated list"; shift ;;
    --skills)   shift; SKILLS_FILTER="${1:-}"; [[ -z "$SKILLS_FILTER" ]] && error "--skills requires a comma-separated list"; shift ;;
    --force)    FORCE=true; shift ;;
    --dry-run)  DRY_RUN=true; shift ;;
    --check-deps) CHECK_DEPS_ONLY=true; shift ;;
    --no-sync)  NO_SYNC=true; shift ;;
    -y|--yes)   NON_INTERACTIVE=true; shift ;;
    -h|--help)  usage ;;
    --*)        error "unknown option: $1 (run with --help to see usage)" ;;
    *)
      if [[ -n "$TARGET" ]]; then
        error "unexpected extra argument: $1 (target already set to: $TARGET)"
      fi
      TARGET="$1"
      shift
      ;;
  esac
done

# ----- Renderer dependency check --------------------------------------------
# Renderer binaries the presentation skills (deck/slides) shell out to. The
# install itself only copies files, so a fresh install can report success while
# a core renderer is absent — this check surfaces that up front. `mmdc` is
# REQUIRED for any deck with a diagram (inline ```mermaid does NOT render in the
# canonical `marp --pdf` output; verified, issue #65), so a missing `mmdc` is a
# warning, not a silent omission.
#
# Returns the number of missing dependencies (0 = all present).
check_renderer_deps() {
  local missing=0
  info "Renderer dependency check (presentation skills: deck/slides)"

  if command -v marp >/dev/null 2>&1; then
    ok "marp present ($(command -v marp))"
  else
    warn "marp MISSING (required for deck/slides PDF render). Install: npm install -g @marp-team/marp-cli"
    missing=$((missing + 1))
  fi

  if command -v pdftoppm >/dev/null 2>&1; then
    ok "pdftoppm present ($(command -v pdftoppm))"
  else
    warn "pdftoppm MISSING (poppler; used by the deck-design vision critic). Install: brew install poppler / apt-get install poppler-utils"
    missing=$((missing + 1))
  fi

  if command -v mmdc >/dev/null 2>&1; then
    ok "mmdc present ($(command -v mmdc))"
  else
    warn "mmdc MISSING (REQUIRED for any deck with a diagram — inline mermaid does NOT render in the PDF). Install: npm install -g @mermaid-js/mermaid-cli"
    note "mmdc pulls Puppeteer + a ~300MB+ headless Chromium; in CI/containers pass --puppeteerConfigFile with {\"args\":[\"--no-sandbox\"]}."
    missing=$((missing + 1))
  fi

  # pdfjam is OPTIONAL (not REQUIRED): only `slides-handout --4-up` and
  # `--2-up` need it for the N-up post-process. The default `--notes-below`
  # handout path renders via Marp's native `--pdf-notes` mode and has zero
  # pdfjam dependency. Marp cannot natively express N-up (verified, issue
  # #85: Marp's rendering model is one-section-per-page; no CLI flag or CSS
  # injection combines N sections onto a single rendered page), so a
  # post-process is the only N-up path. Counted in `missing` so the summary
  # line surfaces it.
  if command -v pdfjam >/dev/null 2>&1; then
    ok "pdfjam present ($(command -v pdfjam))"
  else
    warn "pdfjam MISSING (OPTIONAL — only required for \`slides-handout --4-up\` and \`--2-up\` N-up layouts; the default \`--notes-below\` handout does NOT need it). Install: tlmgr install pdfjam / apt-get install texlive-extra-utils / brew install --cask mactex-no-gui"
    note "TeX Live is a multi-GB install; if you only need the notes-below handout layout, this warning can be safely ignored."
    missing=$((missing + 1))
  fi

  if [[ "$missing" -eq 0 ]]; then
    ok "all renderer dependencies present"
  else
    warn "$missing renderer dependenc$([[ "$missing" -eq 1 ]] && echo y || echo ies) missing (see above)"
  fi
  return "$missing"
}

# --check-deps: report renderer dependencies and exit (no install, no target
# required). Independent of #21's install-script surface.
if [[ "$CHECK_DEPS_ONLY" == true ]]; then
  check_renderer_deps || true
  exit 0
fi

[[ -z "$TARGET" ]] && error "target repository path required (run with --help to see usage)"

# ----- Stage 1: resolve ANVIL_ROOT ------------------------------------------
info "Stage 1: resolve ANVIL_ROOT"
ANVIL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -d "$ANVIL_ROOT/anvil" ]] || error "ANVIL_ROOT does not look like an anvil checkout (missing anvil/): $ANVIL_ROOT"
[[ -f "$ANVIL_ROOT/CLAUDE.md" ]] || error "ANVIL_ROOT missing CLAUDE.md: $ANVIL_ROOT"
ok "ANVIL_ROOT=$ANVIL_ROOT"

# Extract version (single source of truth: CLAUDE.md, per scripts/version.sh)
ANVIL_VERSION=$(grep -o 'Anvil Version\*\*: [0-9]*\.[0-9]*\.[0-9]*' "$ANVIL_ROOT/CLAUDE.md" \
  | grep -o '[0-9]*\.[0-9]*\.[0-9]*' || true)
[[ -n "$ANVIL_VERSION" ]] || error "could not extract Anvil version from $ANVIL_ROOT/CLAUDE.md"
ok "ANVIL_VERSION=$ANVIL_VERSION"

INSTALL_DATE="$(date +%Y-%m-%d)"

# ----- Stage 2: resolve and validate TARGET ---------------------------------
info "Stage 2: resolve and validate TARGET"
# Expand tilde
TARGET="${TARGET/#\~/$HOME}"
[[ -d "$TARGET" ]] || error "target directory does not exist: $TARGET"
TARGET="$(cd "$TARGET" && pwd)"
ok "TARGET=$TARGET"

if [[ "$TARGET" == "$ANVIL_ROOT" ]]; then
  error "refusing to install anvil into its own source checkout ($ANVIL_ROOT)"
fi

if [[ ! -d "$TARGET/.git" ]]; then
  note "target is not a git repository (anvil is forge-optional; proceeding)"
fi

# ----- Stage 3: active-install guard (lightweight) --------------------------
info "Stage 3: active-install guard"
if [[ -d "$TARGET/.anvil" ]]; then
  note "existing .anvil/ detected -- treating as upgrade"
  UPGRADE=true
else
  note "fresh install"
  UPGRADE=false
fi

# ----- Stage 4: read source manifest, filter by --skills= -------------------
info "Stage 4: enumerate source skills"
ALL_SKILLS=()
if [[ -d "$ANVIL_ROOT/anvil/skills" ]]; then
  # Each subdir of anvil/skills/ that contains a SKILL.md is a skill.
  while IFS= read -r -d '' skill_md; do
    skill_dir="$(dirname "$skill_md")"
    skill_name="$(basename "$skill_dir")"
    ALL_SKILLS+=("$skill_name")
  done < <(find "$ANVIL_ROOT/anvil/skills" -mindepth 2 -maxdepth 2 -name 'SKILL.md' -print0 | sort -z)
fi
[[ ${#ALL_SKILLS[@]} -gt 0 ]] || error "no skills found under $ANVIL_ROOT/anvil/skills/*/SKILL.md"
note "available skills: ${ALL_SKILLS[*]}"

SELECTED_SKILLS=()
if [[ -n "$SKILLS_FILTER" ]]; then
  # Reject lib/roles as skill names (they are framework prerequisites).
  IFS=',' read -r -a REQUESTED <<< "$SKILLS_FILTER"
  for s in "${REQUESTED[@]}"; do
    s="$(echo "$s" | tr -d '[:space:]')"
    [[ -z "$s" ]] && continue
    case "$s" in
      lib|roles)
        error "lib and roles are always installed; use skill names like: ${ALL_SKILLS[*]}"
        ;;
    esac
    # Validate against ALL_SKILLS
    found=false
    for avail in "${ALL_SKILLS[@]}"; do
      [[ "$avail" == "$s" ]] && { found=true; break; }
    done
    $found || error "unknown skill: $s; available: ${ALL_SKILLS[*]}"
    SELECTED_SKILLS+=("$s")
  done
  [[ ${#SELECTED_SKILLS[@]} -gt 0 ]] || error "--skills= was empty after filtering"
else
  SELECTED_SKILLS=("${ALL_SKILLS[@]}")
  note "no --skills= flag; installing all (${#SELECTED_SKILLS[@]} skills). Use --skills= to install a subset."
fi
ok "selected: ${SELECTED_SKILLS[*]}"

# ----- Confirmation prompt --------------------------------------------------
if [[ "$NON_INTERACTIVE" != true ]] && [[ "$DRY_RUN" != true ]]; then
  echo ""
  echo "About to install Anvil v$ANVIL_VERSION into: $TARGET"
  echo "Skills: ${SELECTED_SKILLS[*]}"
  echo "Mode: $($UPGRADE && echo upgrade || echo fresh)"
  echo ""
  read -r -p "Proceed? [y/N] " -n 1 reply
  echo ""
  [[ "$reply" =~ ^[Yy]$ ]] || { info "cancelled"; exit 0; }
fi

# ----- Helpers --------------------------------------------------------------
# Run a write action, or print it under --dry-run.
do_action() {
  local desc="$1"; shift
  if [[ "$DRY_RUN" == true ]]; then
    echo "  [dry-run] $desc"
  else
    "$@"
  fi
}

# Compare two directory trees byte-by-byte. Returns 0 if identical, 1 if any
# file differs (or files exist on one side but not the other).
dirs_identical() {
  local a="$1" b="$2"
  # diff -r exit codes: 0 = identical, 1 = differs, 2 = trouble
  diff -r -q "$a" "$b" >/dev/null 2>&1
}

# Compute a stable content hash for a directory tree. Used to record the
# "as-installed" snapshot at install time and to compare against the current
# destination on re-install, so the installer can tell apart:
#   - consumer never touched the install (dst hash == recorded hash) → safe
#     to auto-upgrade even when the dst now differs from source (source moved
#     forward in a later release)
#   - consumer modified the install (dst hash != recorded hash) → preserve
#     the modifications by skipping unless --force
#
# Implementation: sorted list of relative file paths, each fed through
# `shasum -a 256`, then the concatenated digests fed through one more
# `shasum -a 256`. `shasum -a 256` is present on macOS and Linux by default;
# no new dependencies (subprocess-only philosophy per pyproject.toml).
dir_hash() {
  local d="$1"
  [[ -d "$d" ]] || { echo ""; return; }
  ( cd "$d" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 ) \
    | shasum -a 256 \
    | awk '{print $1}'
}

# Read a recorded skill hash from an existing manifest. Returns the empty
# string if the manifest, the `skill_hashes` block, or the requested skill
# entry is absent (which is the "legacy install, no recorded hash" case the
# Stage 7 decision matrix falls back to today's byte-diff behavior for).
#
# Uses pure-bash grep/sed so we don't introduce a jq dependency for a
# single-field read. The schema is hand-emitted by `write_manifest`, so the
# parse target is well-known:
#   "skill_hashes": {
#     "memo": "abc123...",
#     "deck": "def456..."
#   }
#
# We restrict the match to the `skill_hashes` block so that, e.g., a future
# `"memo": "..."` field somewhere else in the manifest can't be misread as
# the skill's hash. Done with awk to keep the parse robust against single-
# line schemas.
read_recorded_hash() {
  local manifest="$1" skill="$2"
  [[ -f "$manifest" ]] || { echo ""; return; }
  # Two-pass extract, pure-bash + tr + grep + sed (no jq dependency):
  #   1. Isolate the `skill_hashes` object body. The schema emitted by
  #      `write_manifest` puts the whole block on one line in the form
  #      `"skill_hashes": {"a": "...", "b": "..."}`; we match the literal
  #      `"skill_hashes": {` opener and grep up to the matching `}`.
  #   2. Inside that body, match `"<skill>": "<hash>"` and emit the hash.
  #
  # Using `tr ',' '\n'` to split entries onto separate lines before grepping
  # keeps the parse independent of whether the JSON is one-line or pretty-
  # printed.
  local block
  block="$(tr '\n' ' ' < "$manifest" \
    | grep -oE '"skill_hashes"[[:space:]]*:[[:space:]]*\{[^}]*\}' \
    | head -n1)" || true
  [[ -n "$block" ]] || { echo ""; return; }
  # `|| true` guards the no-match branch: if the manifest has a
  # `skill_hashes` block but no entry for the queried skill (realistic
  # partial-install scenario — e.g. memo was installed in a prior run, the
  # current invocation queries for deck), `grep -E` returns 1, and under
  # `set -euo pipefail` pipefail propagates it, killing the installer
  # silently mid-Stage-7. The first pipeline above is already protected the
  # same way; this one must mirror it.
  printf '%s' "$block" \
    | tr ',' '\n' \
    | grep -E "\"$skill\"[[:space:]]*:[[:space:]]*\"[a-f0-9]+\"" \
    | head -n1 \
    | sed -E "s/.*\"$skill\"[[:space:]]*:[[:space:]]*\"([a-f0-9]+)\".*/\1/" \
    || true
}

# Copy a directory tree's CONTENTS (not the wrapper dir) into dest, creating
# dest if needed. `cp -R src/. dest` copies contents while preserving the dest
# directory itself. All paths are passed as bash positional args (no shell
# re-parse), so paths containing shell metacharacters like ' are safe.
copy_tree() {
  local src="$1" dst="$2"
  mkdir -p "$dst" && cp -R "$src/." "$dst/"
}

# Wipe and replace a directory tree's contents from source. Used for skill
# install/recopy where we want a clean slate on the destination.
replace_tree() {
  local src="$1" dst="$2"
  rm -rf "$dst" && mkdir -p "$dst" && cp -R "$src/." "$dst/"
}

# Copy a single file to a destination path, creating intermediate dirs.
# Portable equivalent of `install -D -m 0644 src dst` (the BSD/macOS
# install(1) doesn't support -D, so we open-code the mkdir + cp + chmod
# steps). Used to ship per-package __init__.py files into the importable
# mirror (anvil/__init__.py, anvil/skills/__init__.py, etc.).
copy_file_with_parents() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  chmod 0644 "$dst"
}

# Write the thin Claude registration shim for a skill. Called from both the
# happy-path (Stage 7 normal install) and the override-skip branch (Stage 7
# consumer-modified skip) -- single helper, two callers.
#
# All substitution happens inside the bash heredoc, so paths containing shell
# metacharacters are safe (no child-shell re-parse).
write_shim() {
  local skill="$1" shim_dir="$2" shim_file="$3"
  mkdir -p "$shim_dir"
  cat > "$shim_file" <<SHIMEOF
---
name: anvil-$skill
description: Anvil skill registration for '$skill' (canonical body at .anvil/skills/$skill/SKILL.md)
---

See \`.anvil/skills/$skill/SKILL.md\` for the canonical skill body.

This file is a thin Claude registration shim generated by install-anvil.sh.
The canonical skill body and any consumer overrides live at .anvil/skills/$skill/.
SHIMEOF
}

# Write the full Anvil guide to <target>/.anvil/CLAUDE.md, prefixed with a
# generated-by header. Uses bash heredoc + plain `cat` (no child-shell re-parse).
write_guide() {
  local target_dir="$1" anvil_version="$2" install_date="$3" anvil_src_claude_md="$4" guide_dst="$5"
  mkdir -p "$target_dir/.anvil"
  {
    echo '<!-- Generated by install-anvil.sh -->'
    echo "<!-- Anvil Version: $anvil_version -->"
    echo "<!-- Install Date: $install_date -->"
    echo ''
    cat "$anvil_src_claude_md"
  } > "$guide_dst"
}

# Write the install manifest JSON. Substitutions happen in the bash heredoc,
# so paths containing shell metacharacters in $anvil_source are safe.
#
# The `skill_hashes` block records the per-skill directory hash at install
# time (the "as-installed" snapshot). Subsequent re-installs compare the
# current destination against this baseline to distinguish "consumer never
# touched the install" (auto-upgrade safe) from "consumer modified the
# install" (preserve modifications unless --force). See issue #152.
#
# `layout_version` records which on-disk shape the installer wrote (issue
# #230): 1 = pre-#230 (.anvil/lib + .anvil/skills/<name>/lib),
# 2 = post-#230 (.anvil/anvil/ importable mirror + .anvil/pyproject.toml).
# Consumers reading the manifest can branch on this to pin invocation
# paths; the installer is forward-only (always writes the highest layout
# it knows), so any consumer-side branch should treat the absence of
# `layout_version` as "1" (legacy).
#
# `anvil_source` is preserved as install-provenance metadata (it records
# which source checkout produced the install — useful for debugging an
# upgrade). Post-#230, it is NOT load-bearing for runtime invocation: the
# importable `anvil/` package lives under .anvil/anvil/ regardless of
# whether `anvil_source` still exists on disk. This closes the canary
# failure mode where a fresh consumer machine couldn't run anvil because
# the install-time `anvil_source` path was machine-specific.
write_manifest() {
  local target_dir="$1" manifest_path="$2"
  local anvil_version="$3" anvil_source="$4" install_date="$5"
  local installed_json="$6" skipped_json="$7" hashes_json="$8"
  local layout_version="${9:-2}"
  mkdir -p "$target_dir/.anvil"
  cat > "$manifest_path" <<MANIFEST_EOF
{
  "anvil_version": "$anvil_version",
  "anvil_source": "$anvil_source",
  "install_date": "$install_date",
  "layout_version": $layout_version,
  "installed_skills": $installed_json,
  "skipped_overrides": $skipped_json,
  "skill_hashes": $hashes_json
}
MANIFEST_EOF
}

# Write the consumer-side pyproject.toml that turns <target>/.anvil/ into
# a uv-runnable Python project. Issue #230 — the file declares the same
# base deps as the source repo (pydantic + pyyaml) and points
# setuptools.packages.find at the in-tree `anvil/` directory (the
# importable mirror written by Stage 5 + Stage 7).
#
# The optional-extras mirror is intentionally narrower than the source
# repo's: only `auto_shrink` is forwarded (the one extra that's currently
# wired through `anvil/lib/render.py::check_auto_shrink_deps_available`).
# `dev` is omitted — consumers running `uv sync --project .anvil` don't
# need pytest to invoke the framework. New extras added to the source
# `pyproject.toml` are auto-mirrored here only when this function is
# updated — by design, since each extra needs a deliberate "yes, the
# consumer needs this at runtime" decision.
#
# Path layout assumption: the consumer's anvil package lives at
# <target>/.anvil/anvil/ (written by Stage 5). The setuptools include
# pattern `anvil*` matches that, with `where = ["."]` rooted at
# <target>/.anvil/ (the directory holding pyproject.toml).
write_consumer_pyproject() {
  local pyproject_path="$1" anvil_version="$2"
  mkdir -p "$(dirname "$pyproject_path")"
  cat > "$pyproject_path" <<PYPROJECT_EOF
# Generated by scripts/install-anvil.sh (issue #230 — uv-runnable consumer
# install). Edit the source repo's pyproject.toml and re-run the installer
# rather than hand-editing this file: the installer overwrites it on every
# run.
#
# Layout: this file lives at <consumer>/.anvil/pyproject.toml and treats
# <consumer>/.anvil/anvil/ as the importable package root. From the
# consumer repo root:
#
#     uv sync --project .anvil
#     uv run --project .anvil python -c "from anvil.lib.render_gate import gate"
#
# pulls the runtime deps + makes \`anvil.*\` importable. No need to clone
# the anvil source repo on the consumer machine.

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "anvil"
version = "$anvil_version"
description = "AI-orchestrated artifact creation using the filesystem as the coordination layer (consumer-side install)."
requires-python = ">=3.10"
license = { text = "MIT" }

# Base deps: load-bearing for \`anvil/lib/__init__.py\`'s import chain.
# Mirrors the source repo's \`[project] dependencies\` so a consumer-side
# \`uv sync --project .anvil\` produces a working framework runtime without
# manual \`uv add\` steps.
#   - \`pydantic\` is consumed by \`anvil/lib/review_schema.py\` and the
#     downstream modules (\`critics\`, \`rubric\`, \`cite\`, \`vision\`,
#     \`convergence\`) that build on it.
#   - \`pyyaml\` is consumed by \`anvil/lib/rubric.py\` (top-level
#     \`import yaml\`; the rubric loader uses \`yaml.safe_load\`). Both are
#     transitively required by \`from anvil.lib import ...\` — see issue
#     #231 for the canary reproducer.
dependencies = [
    "pydantic>=2.0",
    "pyyaml>=6.0",
]

# Opt-in extras mirrored from the source repo. Each one corresponds to a
# single advanced check that needs a third-party Python library; the
# preflights in \`anvil/lib/render.py\` graceful-skip when the extra is
# missing.
[project.optional-dependencies]
# \`anvil:deck\` silent-Marp-auto-shrink lint (issue #102 / #100b).
auto_shrink = [
    "Pillow>=10.0",
    "numpy>=1.24",
]

[tool.uv]

[tool.setuptools.packages.find]
where = ["."]
include = ["anvil*"]
exclude = ["tests*", "*.tests", "*.tests.*", "tests.*"]
PYPROJECT_EOF
}

# Track override decisions for the manifest.
SKIPPED_OVERRIDES=()
INSTALLED_SKILLS=()
# Per-skill "as-installed" content hashes. Keys are skill names, values are
# hex digests from `dir_hash`. Recorded under `skill_hashes` in the manifest
# so a subsequent re-install can tell apart "consumer modified the install"
# from "source moved forward in a later release."
#
# Bash 3.x (the macOS default) does not have associative arrays, so we use
# two parallel indexed arrays. The pair is emitted in order at manifest-
# write time.
SKILL_HASH_KEYS=()
SKILL_HASH_VALUES=()

# Append a (skill, hash) entry to the parallel-array hash table. Overwrites
# an existing entry for `skill` if present (the recorded hash should always
# reflect the most recent successful install for that skill).
set_skill_hash() {
  local skill="$1" hash="$2" i
  for ((i = 0; i < ${#SKILL_HASH_KEYS[@]}; i++)); do
    if [[ "${SKILL_HASH_KEYS[$i]}" == "$skill" ]]; then
      SKILL_HASH_VALUES[$i]="$hash"
      return
    fi
  done
  SKILL_HASH_KEYS+=("$skill")
  SKILL_HASH_VALUES+=("$hash")
}

# Manifest path is also referenced by Stage 7 (for the recorded-hash lookup)
# and Stage 9 (for the write). Defined here so both stages share it.
MANIFEST="$TARGET/.anvil/install-metadata.json"

# ----- Stage 5: copy framework code (lib) -----------------------------------
# Pre-#230 layout: framework Python shipped at <target>/.anvil/lib/ — NOT
# importable as `anvil.lib.*` because there was no `anvil/` package root
# and no consumer-side pyproject.toml (issue #230 canary reproducer).
#
# Post-#230 layout: framework Python ships at <target>/.anvil/anvil/lib/.
# Paired with the generated <target>/.anvil/pyproject.toml (Stage 8.5
# below), `uv run --project .anvil python -c "from anvil.lib.render_gate
# import gate"` works from the consumer root with no manual `uv add` or
# symlink shims.
#
# The `anvil/__init__.py` source file is copied through as part of the
# tree (it's the namespace anchor that makes `import anvil` succeed).
info "Stage 5: copy framework code (anvil/lib -> .anvil/anvil/lib)"
SRC_LIB="$ANVIL_ROOT/anvil/lib"
DST_ANVIL_PKG="$TARGET/.anvil/anvil"
DST_LIB="$DST_ANVIL_PKG/lib"
SRC_ANVIL_INIT="$ANVIL_ROOT/anvil/__init__.py"
if [[ -d "$SRC_LIB" ]]; then
  # Copy contents (cp -R src/. dest preserves contents, not the wrapper dir).
  do_action "install $DST_LIB from $SRC_LIB" copy_tree "$SRC_LIB" "$DST_LIB"
  # Copy the anvil package's top-level __init__.py so `import anvil` resolves.
  # The skills/ subpackage __init__.py is written in Stage 7 alongside the
  # per-skill lib copies (avoids creating empty skills/ until at least one
  # skill is installed; the source `anvil/skills/__init__.py` is the file
  # being copied through).
  if [[ -f "$SRC_ANVIL_INIT" ]]; then
    do_action "install $DST_ANVIL_PKG/__init__.py from $SRC_ANVIL_INIT" \
      copy_file_with_parents "$SRC_ANVIL_INIT" "$DST_ANVIL_PKG/__init__.py"
  fi
  # Suppress post-action confirmation under --dry-run; the [dry-run] line above
  # is the truthful record (issue #81). Stage 1-4/10 diagnostic ok: lines stay.
  [[ "$DRY_RUN" == true ]] || ok "framework lib installed (importable as anvil.lib.*)"
else
  warn "source lib not found: $SRC_LIB (skipping)"
fi

# Migration warning: pre-#230 installs left .anvil/lib/ on disk (the
# non-importable framework layout). On upgrade, surface its presence so the
# operator can clean it up — we don't auto-delete because consumers may have
# hand-edited override files there (memo styles.css, template.html, etc.).
# The post-#230 runtime resolves these via .anvil/anvil/lib/, so the legacy
# directory is no longer load-bearing for any imported code path.
if [[ -d "$TARGET/.anvil/lib" ]]; then
  warn "legacy framework dir detected: $TARGET/.anvil/lib (pre-#230 install layout)"
  echo "         The post-#230 import path is .anvil/anvil/lib/ (now installed)."
  echo "         If you hand-edited files in .anvil/lib/ (e.g. memo styles.css),"
  echo "         port them to the matching path under .anvil/anvil/lib/ and"
  echo "         remove .anvil/lib/ to avoid confusion."
fi

# ----- Stage 6: copy roles --------------------------------------------------
info "Stage 6: copy roles (anvil/roles -> .anvil/roles)"
SRC_ROLES="$ANVIL_ROOT/anvil/roles"
DST_ROLES="$TARGET/.anvil/roles"
if [[ -d "$SRC_ROLES" ]]; then
  do_action "install $DST_ROLES from $SRC_ROLES" copy_tree "$SRC_ROLES" "$DST_ROLES"
  # Suppress post-action confirmation under --dry-run (issue #81).
  [[ "$DRY_RUN" == true ]] || ok "roles installed"
else
  warn "source roles not found: $SRC_ROLES (skipping)"
fi

# ----- Stage 7: copy each selected skill ------------------------------------
# Per skill (issue #230 split layout):
#   * Skill body (SKILL.md, commands/, templates/, rubric.md, examples/,
#     tests/, assets/, README.md, ...) -> .anvil/skills/<name>/
#       The consumer-override target. Override-detection / hash-tracking
#       (issue #152) operates on this directory.
#   * Skill Python `lib/` subdir (when present) -> .anvil/anvil/skills/<name>/lib/
#       The importable-from-anvil location. Mirrors
#       `from anvil.skills.<name>.lib import ...` in the source repo.
#       Auxiliary `__init__.py` files for the skill package and its lib
#       subpackage are sourced from the source tree (when present) so
#       `anvil.skills.<name>.lib.foo` resolves cleanly.
#
# Override detection decision matrix (issue #152) — applies to the skill-
# body destination (.anvil/skills/<name>/):
#
#   Destination state                          Action
#   ────────────────────────────────────────── ───────────────────────────────
#   Does not exist                             Fresh install. Record hash.
#   Exists, byte-identical to source           Recopy idempotently. Record
#                                              hash (overwrites stale entry).
#   Exists, differs from source, dst hash
#     matches recorded "as-installed" hash     Auto-upgrade (consumer hasn't
#                                              modified). Record new hash.
#   Exists, differs from source, dst hash
#     does NOT match recorded hash             Consumer-modified. Skip with
#                                              warning unless --force.
#   Exists, differs from source, NO recorded
#     hash in manifest (legacy install)        Fall back to today's
#                                              behavior: skip with warning
#                                              unless --force. Documented as
#                                              one-time migration cost.
#   --force passed                             Overwrite unconditionally.
#                                              Record new hash.
#
# The skill Python `lib/` -> .anvil/anvil/skills/<name>/lib/ copy is
# unconditional (it's importable code, not a consumer-override target);
# consumers extending skill behavior do so via siblings under
# .anvil/skills/<name>/, not by editing .anvil/anvil/skills/<name>/lib/
# in place. This mirrors the framework-lib treatment in Stage 5.
info "Stage 7: copy selected skills"
SRC_SKILLS_INIT="$ANVIL_ROOT/anvil/skills/__init__.py"
DST_PKG_SKILLS="$DST_ANVIL_PKG/skills"
# Write the anvil.skills sub-package __init__.py (single shot — it's the
# same file for every skill iteration, so the source-to-destination copy
# can happen once before the loop).
if [[ -f "$SRC_SKILLS_INIT" ]]; then
  do_action "install $DST_PKG_SKILLS/__init__.py from $SRC_SKILLS_INIT" \
    copy_file_with_parents "$SRC_SKILLS_INIT" "$DST_PKG_SKILLS/__init__.py"
fi

# Helper: split the skill-body copy (consumer override target, hash-tracked)
# from the skill-lib copy (importable Python, unconditional). The body
# excludes `lib/` so the override-detection hash is stable against the
# importable-mirror change (i.e., bumping a skill's lib/foo.py doesn't
# flip its body's override hash).
#
# We can't use `cp -R src/. dst/` with an exclusion natively; instead use
# `find ... | cpio` is overkill. The simpler approach: copy the whole tree
# then remove the lib subdir from the destination. Under --dry-run we just
# print the planned actions and skip both side effects.
copy_skill_body_excluding_lib() {
  local src="$1" dst="$2"
  rm -rf "$dst" && mkdir -p "$dst" && cp -R "$src/." "$dst/" && rm -rf "$dst/lib"
}

# Mirror of `dir_hash` that EXCLUDES the lib/ subdir from the digest. Used
# for both `dirs_identical` and the recorded-hash comparison so override-
# detection operates on the body-only view (consumers don't override the
# importable Python under the skill's lib/).
dir_hash_body_only() {
  local d="$1"
  [[ -d "$d" ]] || { echo ""; return; }
  ( cd "$d" && find . -type f -not -path "./lib/*" -not -path "./lib" -print0 \
    | LC_ALL=C sort -z | xargs -0 shasum -a 256 ) \
    | shasum -a 256 \
    | awk '{print $1}'
}

# Mirror of `dirs_identical` that treats the lib/ subdir as out-of-scope
# for the consumer-modification check (issue #230 — lib/ moves to the
# importable mirror but the body's override semantics shouldn't churn).
dirs_identical_body_only() {
  local a="$1" b="$2"
  diff -r -q --exclude=lib "$a" "$b" >/dev/null 2>&1
}

for skill in "${SELECTED_SKILLS[@]}"; do
  src_skill="$ANVIL_ROOT/anvil/skills/$skill"
  dst_skill="$TARGET/.anvil/skills/$skill"
  src_skill_lib="$src_skill/lib"
  dst_skill_pylib="$DST_PKG_SKILLS/$skill/lib"
  src_skill_init="$src_skill/__init__.py"
  dst_skill_pyinit="$DST_PKG_SKILLS/$skill/__init__.py"
  # Flatten namespace into the directory name (depth 1). Claude Code's skill
  # discovery only finds SKILL.md at .claude/skills/<name>/SKILL.md; the prior
  # depth-2 path .claude/skills/anvil/<skill>/SKILL.md was silently skipped,
  # leaving slash-command users unable to invoke /anvil-*:* commands (#135).
  shim_dir="$TARGET/.claude/skills/anvil-$skill"
  shim_file="$shim_dir/SKILL.md"

  # Override detection: if the destination exists, decide between safe
  # auto-upgrade and consumer-modified-skip using the per-skill hash baseline
  # recorded in the manifest at the time of the previous install. The
  # `verdict` string is woven into the dry-run action label so operators can
  # tell apart each per-skill decision in the preview.
  #
  # All comparisons here operate on the body-only view (lib/ excluded) so
  # the importable-mirror split (issue #230) doesn't flip every consumer's
  # override status on the first post-#230 upgrade.
  verdict="install fresh"
  if [[ -d "$dst_skill" ]]; then
    if dirs_identical_body_only "$src_skill" "$dst_skill"; then
      note "skill '$skill' already installed and unchanged (refreshing safely)"
      verdict="recopy (identical to source)"
    elif [[ "$FORCE" == true ]]; then
      warn "overwriting consumer-modified file(s) in .anvil/skills/$skill (--force)"
      verdict="overwrite (--force)"
    else
      # Compute the destination's current dir hash and compare against the
      # recorded "as-installed" hash for this skill. We compute the dst hash
      # even under --dry-run because the comparison is read-only.
      recorded_hash="$(read_recorded_hash "$MANIFEST" "$skill")"
      current_dst_hash="$(dir_hash_body_only "$dst_skill")"
      if [[ -n "$recorded_hash" && "$recorded_hash" == "$current_dst_hash" ]]; then
        # Consumer hasn't touched the install since the last install/upgrade.
        # The dst differs from source only because source moved forward in a
        # later release. Safe to auto-upgrade.
        note "skill '$skill' is unmodified-since-install (recorded hash matches); auto-upgrading from source"
        verdict="auto-upgrade (unmodified-since-install)"
      elif [[ -z "$recorded_hash" ]]; then
        # Legacy install (manifest pre-dates the hash-tracking change, or the
        # manifest is missing entirely). Fall back to today's conservative
        # behavior: assume consumer-modified and require --force.
        warn "skipped: consumer-modified .anvil/skills/$skill (legacy install, no recorded hash; re-run with --force to overwrite — future installs will auto-detect)"
        SKIPPED_OVERRIDES+=("$skill")
        # Importable lib mirror is always installed even when the body
        # is skipped — it's unconditional code, not an override target.
        if [[ -d "$src_skill_lib" ]]; then
          do_action "install $dst_skill_pylib from $src_skill_lib (importable mirror)" \
            replace_tree "$src_skill_lib" "$dst_skill_pylib"
        fi
        if [[ -f "$src_skill_init" ]]; then
          do_action "install $dst_skill_pyinit from $src_skill_init" \
            copy_file_with_parents "$src_skill_init" "$dst_skill_pyinit"
        fi
        do_action "regenerate Claude registration shim at .claude/skills/anvil-$skill/SKILL.md" \
          write_shim "$skill" "$shim_dir" "$shim_file"
        continue
      else
        # Recorded hash exists and differs from the current dst hash → the
        # consumer actually modified the install. Preserve their work.
        warn "skipped: consumer-modified .anvil/skills/$skill (re-run with --force to overwrite)"
        SKIPPED_OVERRIDES+=("$skill")
        if [[ -d "$src_skill_lib" ]]; then
          do_action "install $dst_skill_pylib from $src_skill_lib (importable mirror)" \
            replace_tree "$src_skill_lib" "$dst_skill_pylib"
        fi
        if [[ -f "$src_skill_init" ]]; then
          do_action "install $dst_skill_pyinit from $src_skill_init" \
            copy_file_with_parents "$src_skill_init" "$dst_skill_pyinit"
        fi
        do_action "regenerate Claude registration shim at .claude/skills/anvil-$skill/SKILL.md" \
          write_shim "$skill" "$shim_dir" "$shim_file"
        continue
      fi
    fi
  fi

  # Copy the skill body (everything except lib/) into the consumer-override
  # location. Under --dry-run this is a no-op described by the action label.
  do_action "install .anvil/skills/$skill from source (body only, lib mirrored separately) [$verdict]" \
    copy_skill_body_excluding_lib "$src_skill" "$dst_skill"

  # Copy the skill's Python lib subdir into the importable mirror (always —
  # unconditional code, not a consumer-override target).
  if [[ -d "$src_skill_lib" ]]; then
    do_action "install $dst_skill_pylib from $src_skill_lib (importable mirror)" \
      replace_tree "$src_skill_lib" "$dst_skill_pylib"
  fi

  # Copy the skill's package __init__.py into the importable mirror so
  # `import anvil.skills.<name>` resolves.
  if [[ -f "$src_skill_init" ]]; then
    do_action "install $dst_skill_pyinit from $src_skill_init" \
      copy_file_with_parents "$src_skill_init" "$dst_skill_pyinit"
  fi

  # Always regenerate the thin Claude registration shim.
  do_action "write Claude registration shim at .claude/skills/anvil-$skill/SKILL.md" \
    write_shim "$skill" "$shim_dir" "$shim_file"

  INSTALLED_SKILLS+=("$skill")
  # Record the "as-installed" body hash so the next re-install can distinguish
  # consumer-modified from unmodified. Body-only digest (lib/ excluded) so
  # the importable-mirror churn doesn't flip override status. Under --dry-run
  # no copy happens so we hash the source tree (which is what a real run
  # WOULD install); this keeps the dry-run-honesty contract intact (the
  # manifest is not written in dry-run mode either; see Stage 9 do_action
  # wrapper).
  set_skill_hash "$skill" "$(dir_hash_body_only "$src_skill")"
  # Suppress post-action confirmation under --dry-run (issue #81). The
  # INSTALLED_SKILLS array is still populated so the Stage 11 summary can
  # accurately report what a real run WOULD install (relabel branch below).
  [[ "$DRY_RUN" == true ]] || ok "skill '$skill' installed"
done

# ----- Stage 7.5: copy Anvil subagent definitions (issue #377) -------------
# Per-skill-phase subagent registrations (anvil-<skill>-<phase>.md) shipped
# under anvil/agents/ in the source repo. Each file mirrors Loom's
# .claude/agents/loom-<role>.md pattern: thin frontmatter (name, description,
# tools) + a short system-prompt body delegating to the canonical command
# under .anvil/skills/<skill>/commands/<command>.md.
#
# Copy mode: blanket replace_tree from source. Agents are NOT consumer-
# override targets (the canonical body lives in the source command file the
# agent points at; the agent shim only declares registry metadata). The
# `--force` flag is therefore not needed for the agents/ copy — every install
# refreshes the full agent set. Skills, by contrast, ARE override targets
# (consumers can patch templates/, rubric.md, etc.), which is why Stage 7
# carries the override-detection decision matrix.
#
# Filter behavior: the agents/ copy is NOT scoped by --skills=. The full
# agent registry ships even when the operator pins a strict skill subset
# (e.g., --skills=memo). Rationale: a skill-pinned install can still spawn
# agents for non-installed skills if the consumer is running the source
# checkout side-by-side; the agent shims are cheap and parsing failures (no
# command body to follow) would surface immediately when dispatched. The
# canary's actual fan-out pattern always installs the full skill set, so the
# narrowed-install case is purely a documentation / dev path.
info "Stage 7.5: copy Anvil subagent definitions (anvil/agents -> .claude/agents)"
SRC_AGENTS="$ANVIL_ROOT/anvil/agents"
DST_AGENTS="$TARGET/.claude/agents"
INSTALLED_AGENTS_COUNT=0
if [[ -d "$SRC_AGENTS" ]]; then
  # Count source agents up front so the action label is honest under --dry-run.
  AGENT_COUNT="$(find "$SRC_AGENTS" -maxdepth 1 -name 'anvil-*.md' -type f 2>/dev/null | wc -l | tr -d '[:space:]')"
  if [[ "$AGENT_COUNT" -gt 0 ]]; then
    if [[ "$DRY_RUN" == true ]]; then
      # Dry-run: no side effects on disk. Only the planned action line is
      # surfaced so the operator sees what a real run would copy.
      echo "  [dry-run] copy $AGENT_COUNT agent files from $SRC_AGENTS to $DST_AGENTS"
    else
      # Per-file copy (not replace_tree) so we don't blow away any non-anvil
      # agents the consumer has added under .claude/agents/ (e.g., loom-*
      # agents from a sibling Loom install). Pattern-match on `anvil-*.md`
      # restricts the install footprint to the Anvil-owned namespace.
      mkdir -p "$DST_AGENTS"
      while IFS= read -r -d '' agent_file; do
        cp "$agent_file" "$DST_AGENTS/"
        INSTALLED_AGENTS_COUNT=$((INSTALLED_AGENTS_COUNT + 1))
      done < <(find "$SRC_AGENTS" -maxdepth 1 -name 'anvil-*.md' -type f -print0)
      ok "$INSTALLED_AGENTS_COUNT subagent registration(s) installed at $DST_AGENTS"
    fi
  else
    note "no anvil-*.md files found under $SRC_AGENTS (skipping)"
  fi
else
  note "source agents dir not found: $SRC_AGENTS (skipping; pre-#377 source checkout?)"
fi

# ----- Stage 8: CLAUDE.md additive merge ------------------------------------
info "Stage 8: CLAUDE.md additive merge"
CLAUDE_MD="$TARGET/CLAUDE.md"
NEW_BLOCK="$ANVIL_MARK_BEGIN
$ANVIL_POINTER
$ANVIL_MARK_END"

merge_claude_md() {
  if [[ ! -f "$CLAUDE_MD" ]]; then
    # Case 1: no existing CLAUDE.md -- create it with just the marker block.
    printf '%s\n' "$NEW_BLOCK" > "$CLAUDE_MD"
    return
  fi

  if grep -qF "$ANVIL_MARK_BEGIN" "$CLAUDE_MD"; then
    # Case 2: existing Anvil marker -- replace block in place.
    # Pure-bash line-by-line replacement is more portable than awk -v block=<multiline>
    # (BSD awk rejects newlines inside -v values). Preserves everything outside
    # the markers, including any Loom block.
    local tmp in_block=0
    tmp="$(mktemp)"
    local replaced=0
    while IFS= read -r line || [[ -n "$line" ]]; do
      if [[ "$in_block" -eq 0 ]]; then
        if [[ "$line" == *"$ANVIL_MARK_BEGIN"* ]]; then
          printf '%s\n' "$NEW_BLOCK" >> "$tmp"
          in_block=1
          replaced=1
        else
          printf '%s\n' "$line" >> "$tmp"
        fi
      else
        if [[ "$line" == *"$ANVIL_MARK_END"* ]]; then
          in_block=0
        fi
        # discard lines inside the old block
      fi
    done < "$CLAUDE_MD"
    if [[ "$replaced" -eq 0 ]]; then
      rm -f "$tmp"
      return 1
    fi
    mv "$tmp" "$CLAUDE_MD"
    return
  fi

  # Case 3: existing CLAUDE.md, no Anvil markers -- append at end, separated by blank line.
  # Trim trailing newlines from the existing file, then append "\n\n<block>\n".
  local existing
  existing="$(cat "$CLAUDE_MD")"
  # Remove trailing whitespace/newlines, then add exactly one blank line before block.
  printf '%s\n\n%s\n' "${existing%$'\n'}" "$NEW_BLOCK" > "$CLAUDE_MD"
}

if [[ "$DRY_RUN" == true ]]; then
  if [[ ! -f "$CLAUDE_MD" ]]; then
    echo "  [dry-run] create CLAUDE.md with Anvil marker block"
  elif grep -qF "$ANVIL_MARK_BEGIN" "$CLAUDE_MD"; then
    echo "  [dry-run] replace existing Anvil block in CLAUDE.md (in place)"
  else
    echo "  [dry-run] append Anvil marker block to CLAUDE.md (preserves all existing content)"
  fi
else
  merge_claude_md
  ok "CLAUDE.md updated"
fi

# Write the full Anvil guide to <target>/.anvil/CLAUDE.md (with version + date
# substituted). The source CLAUDE.md already carries the canonical version line;
# write_guide just adds an install-date metadata header on top.
ANVIL_GUIDE_DST="$TARGET/.anvil/CLAUDE.md"
do_action "write Anvil guide to .anvil/CLAUDE.md" \
  write_guide "$TARGET" "$ANVIL_VERSION" "$INSTALL_DATE" "$ANVIL_ROOT/CLAUDE.md" "$ANVIL_GUIDE_DST"

# ----- Stage 8.5: write consumer-side pyproject.toml -----------------------
# Issue #230 — generate <target>/.anvil/pyproject.toml so the install is
# uv-runnable from the consumer root without the anvil source repo present.
# This is unconditional: the file is rewritten on every install so it
# tracks any base-dep churn in the source pyproject.toml (consumers should
# not hand-edit it — the installer overwrites in-place).
info "Stage 8.5: write consumer-side pyproject.toml"
CONSUMER_PYPROJECT="$TARGET/.anvil/pyproject.toml"
do_action "write $CONSUMER_PYPROJECT (declares pydantic + pyyaml; anvil/ package)" \
  write_consumer_pyproject "$CONSUMER_PYPROJECT" "$ANVIL_VERSION"

# ----- Stage 9: install manifest --------------------------------------------
info "Stage 9: write install manifest"
# MANIFEST is defined earlier (above Stage 5) because Stage 7 also reads it
# for the recorded-hash lookup.

# Build JSON arrays for installed skills and skipped overrides.
json_array_from_list() {
  local first=true
  printf '['
  for item in "$@"; do
    if $first; then first=false; else printf ', '; fi
    printf '"%s"' "$item"
  done
  printf ']'
}

# Build the `skill_hashes` JSON object from the parallel-array hash table.
# Order matches the order skills were processed in Stage 7. Empty hash table
# emits `{}`.
#
# Preservation rule (issue #152): the hash table at this point contains only
# the entries set by Stage 7 — newly-installed skills. Skills that were
# skipped (consumer-modified) need their PREVIOUSLY-RECORDED hash carried
# forward into the new manifest, or the next re-install would see "no
# recorded hash" and fall back to the legacy-install warning indefinitely.
# That carry-forward happens here so the merge is reflected in the final
# JSON.
for skipped in ${SKIPPED_OVERRIDES[@]+"${SKIPPED_OVERRIDES[@]}"}; do
  prior="$(read_recorded_hash "$MANIFEST" "$skipped")"
  if [[ -n "$prior" ]]; then
    set_skill_hash "$skipped" "$prior"
  fi
done

json_object_from_skill_hashes() {
  local first=true i
  printf '{'
  for ((i = 0; i < ${#SKILL_HASH_KEYS[@]}; i++)); do
    if $first; then first=false; else printf ', '; fi
    printf '"%s": "%s"' "${SKILL_HASH_KEYS[$i]}" "${SKILL_HASH_VALUES[$i]}"
  done
  printf '}'
}

INSTALLED_JSON="$(json_array_from_list ${INSTALLED_SKILLS[@]+"${INSTALLED_SKILLS[@]}"})"
SKIPPED_JSON="$(json_array_from_list ${SKIPPED_OVERRIDES[@]+"${SKIPPED_OVERRIDES[@]}"})"
HASHES_JSON="$(json_object_from_skill_hashes)"

do_action "write $MANIFEST" \
  write_manifest "$TARGET" "$MANIFEST" "$ANVIL_VERSION" "$ANVIL_ROOT" "$INSTALL_DATE" \
                 "$INSTALLED_JSON" "$SKIPPED_JSON" "$HASHES_JSON" "2"

# ----- Stage 10: renderer dependency check ----------------------------------
# Report which renderer binaries are present so a fresh install does not claim
# unqualified success while a core renderer (esp. mmdc) is absent. Scope: this
# is the dependency-CHECK addition owned by #65; the path-injection/dry-run
# items are #21's surface and are untouched here.
info "Stage 10: renderer dependency check"
DEPS_MISSING=0
check_renderer_deps || DEPS_MISSING=$?

# ----- Stage 10.5: uv sync (issue #230) -------------------------------------
# Pull the framework's runtime Python deps into a venv rooted at
# <target>/.anvil/. The pyproject.toml written in Stage 8.5 declares
# pydantic + pyyaml as base deps; `uv sync --project .anvil` materializes
# them so `uv run --project .anvil python -c "from anvil.lib.render_gate
# import gate"` works from the consumer root with no follow-up `uv add`.
#
# Skipped under:
#   * --no-sync — offline installs, hosts without uv, or callers that
#     manage their own venv lifecycle.
#   * --dry-run — by definition no writes; the planned command is printed
#     instead so the operator sees what a real run would do.
# If uv is absent the stage falls back to printing the install hint
# rather than aborting (the install itself succeeded; the sync is a
# convenience, not a requirement).
info "Stage 10.5: uv sync (consumer venv)"
if [[ "$NO_SYNC" == true ]]; then
  note "skipping uv sync (--no-sync requested)"
  note "to materialize the consumer venv later:  uv sync --project $TARGET/.anvil"
elif [[ "$DRY_RUN" == true ]]; then
  echo "  [dry-run] uv sync --project $TARGET/.anvil"
elif ! command -v uv >/dev/null 2>&1; then
  warn "uv not on PATH — skipping post-install sync"
  echo "         Install uv (https://docs.astral.sh/uv/) and run:"
  echo "             uv sync --project $TARGET/.anvil"
  echo "         to materialize the consumer-side venv."
else
  info "running uv sync --project $TARGET/.anvil"
  if uv sync --project "$TARGET/.anvil"; then
    ok "consumer venv synced ($TARGET/.anvil/.venv)"
  else
    warn "uv sync exited non-zero — consumer venv may be incomplete"
    echo "         Re-run manually to see the full error output:"
    echo "             uv sync --project $TARGET/.anvil"
  fi
fi

# ----- Stage 11: summary ----------------------------------------------------
info "Stage 11: summary"
echo ""
if [[ "$DRY_RUN" == true ]]; then
  # Under --dry-run, relabel the summary so the operator sees WHAT a real run
  # would install (load-bearing info — the point of --dry-run) without the
  # lying "installed skills:" framing (issue #81).
  echo "  would install:       ${INSTALLED_SKILLS[*]:-(none -- all were consumer-modified)}"
  echo "  would skip:          ${SKIPPED_OVERRIDES[*]:-(none)}"
  echo "  would target:        $TARGET/.anvil"
else
  echo "  installed skills:    ${INSTALLED_SKILLS[*]:-(none -- all were consumer-modified)}"
  echo "  skipped overrides:   ${SKIPPED_OVERRIDES[*]:-(none)}"
  echo "  target:              $TARGET/.anvil"
fi
echo "  renderer deps:       $([[ "$DEPS_MISSING" -eq 0 ]] && echo "all present" || echo "$DEPS_MISSING missing -- re-run with --check-deps for detail")"
echo ""

# ----- Drift-detection note (issue #239) ------------------------------------
# When SELECTED_SKILLS is a strict subset of ALL_SKILLS the installer has just
# been steered toward installing fewer than the available source-side skills.
# Surface the gap so the operator can tell apart "I deliberately pinned a
# subset" from "I'm copy-pasting an old --skills= from my docs and missing
# upstream additions." The signal is computed against the active selection
# (SELECTED_SKILLS) vs the source enumeration (ALL_SKILLS), NOT against the
# manifest's installed_skills (which exhibits the same staleness as the docs).
# Fires under both real-install and --dry-run paths -- the drift signal is
# part of the operator UX even on dry-run pre-flight.
if [[ ${#SELECTED_SKILLS[@]} -lt ${#ALL_SKILLS[@]} ]]; then
  MISSING_SKILLS=()
  for avail in "${ALL_SKILLS[@]}"; do
    selected=false
    for sel in "${SELECTED_SKILLS[@]}"; do
      if [[ "$sel" == "$avail" ]]; then selected=true; break; fi
    done
    $selected || MISSING_SKILLS+=("$avail")
  done
  if [[ ${#MISSING_SKILLS[@]} -gt 0 ]]; then
    # ALL_SKILLS is already alpha-sorted via Stage 4's `sort -z`, and we
    # iterate it in order to build MISSING_SKILLS -- so the listing here is
    # deterministically alpha-ordered without an extra sort pass.
    note "${#MISSING_SKILLS[@]} anvil skills available beyond your selection:"
    note "      ${MISSING_SKILLS[*]}"
    note "to install all available skills, re-run without --skills= (recommended for upgrades)."
    echo ""
  fi
fi

if [[ "$DRY_RUN" == true ]]; then
  warn "DRY-RUN: no files were written"
else
  ok "Anvil v$ANVIL_VERSION installed into $TARGET"
  if [[ "$DEPS_MISSING" -gt 0 ]]; then
    warn "install complete, but $DEPS_MISSING renderer dependenc$([[ "$DEPS_MISSING" -eq 1 ]] && echo y || echo ies) missing (see above) -- deck/slides rendering will be impaired until installed"
  fi
  # Migration note (#135): pre-fix installs wrote shims to depth-2
  # .claude/skills/anvil/<skill>/SKILL.md, which Claude Code's depth-1
  # discovery contract silently skipped. The depth-1 shims at
  # .claude/skills/anvil-<skill>/ are now the canonical install target.
  # If the stale directory is present, recommend manual removal -- we
  # don't auto-delete to avoid surprising consumers who may have hand-
  # edited files in there.
  if [[ -d "$TARGET/.claude/skills/anvil" ]]; then
    warn "legacy shim directory detected: $TARGET/.claude/skills/anvil/"
    echo "         These depth-2 shims are not discoverable by Claude Code (#135)."
    echo "         Anvil now installs depth-1 shims at .claude/skills/anvil-<skill>/."
    echo "         To clean up:  rm -rf $TARGET/.claude/skills/anvil"
  fi
fi
