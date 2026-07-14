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
#   -y, --yes         Non-interactive (skip confirmation prompts; also
#                     auto-enabled when stdin is not a TTY, e.g. CI pipelines
#                     or `install-anvil.sh . </dev/null`)
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
#   .anvil/.gitignore                  Self-contained ignore file (issue #674)
#                                      suppressing the Python runtime artifacts
#                                      the .anvil/ footprint generates:
#                                      `__pycache__/`, `*.py[cod]`, and the
#                                      `.venv/` created at Stage 10.5. Written
#                                      once (skip-if-exists); the consumer's
#                                      root .gitignore is left untouched.
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

# Auto-detect non-interactive mode when stdin is not a TTY (agent shells,
# CI pipelines, `install-anvil.sh . </dev/null`). Without this, the
# confirmation prompt below hits EOF on `read`, which under `set -euo
# pipefail` (see line 77 above) silently aborts the script with exit 1 and
# no diagnostic. Mirrors install-loom.sh:285-293. The explicit `--yes` flag
# is still honored on a TTY; the note below only prints when the auto-detect
# is what flipped the flag.
if [[ "$NON_INTERACTIVE" != true ]] && [[ ! -t 0 ]]; then
  NON_INTERACTIVE=true
  note "stdin is not a TTY — proceeding non-interactively (use --yes explicitly to suppress this note)"
fi

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
  # Sort the extracted skill NAMES (bytewise, C locale), not the SKILL.md
  # paths: path-wise sorting compares a name's `-` (0x2D) against the `/`
  # (0x2F) before `SKILL.md`, which mis-orders a skill whose name is a
  # hyphenated extension of a sibling's (`ip-uspto-provisional` would sort
  # before `ip-uspto`). Name-wise C-locale sort matches Python's
  # `sorted()` and keeps the Stage-11.5 drift note deterministic.
  while IFS= read -r -d '' skill_name; do
    ALL_SKILLS+=("$skill_name")
  done < <(
    find "$ANVIL_ROOT/anvil/skills" -mindepth 2 -maxdepth 2 -name 'SKILL.md' -print0 \
      | while IFS= read -r -d '' skill_md; do
          printf '%s\0' "$(basename "$(dirname "$skill_md")")"
        done \
      | LC_ALL=C sort -z
  )
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

# Documented consumer-override targets under the lib tree (issue #490). These
# are the asset files the memo README sanctions editing in place
# (`anvil/lib/<skill>/<asset>`). The Stage 5 override-detection / skip-with-
# warning discipline protects ONLY these files; every other file under
# anvil/lib/ — the importable framework code, __init__.py, schema JSON,
# figures, marp config — always upgrades unconditionally so the `anvil.lib.*`
# mirror is never left stale (the carve-out the curator flagged as critical).
#
# Paths are relative to the lib root (anvil/lib/ in source, .anvil/anvil/lib/
# at the destination). Confirmed against `anvil/lib/*/` asset files at
# implementation time: the memo skill ships consumer-brandable template
# assets, and `figures/mermaid-theme.json` is the shared diagram theme
# consumers patch to match their brand palette (issue #634 — the studio
# patches it locally). Adding a new skill-asset override tier means adding
# its files here.
LIB_OVERRIDE_TARGETS=(
  "memo/styles.css"
  "memo/template.html"
  "memo/template.tex"
  "figures/mermaid-theme.json"
)

# Compute a stable content hash over ONLY the lib override-target files
# (LIB_OVERRIDE_TARGETS) that exist under the given lib root. Mirrors
# `dir_hash`'s two-pass shasum pipeline but restricts the file set to the
# documented override surface, so the recorded baseline doesn't churn when
# unrelated framework code (or a newly-added schema file) moves upstream.
# Emits "" when the lib root is absent or none of the targets exist.
lib_override_hash() {
  local root="$1" t existing=()
  [[ -d "$root" ]] || { echo ""; return; }
  for t in "${LIB_OVERRIDE_TARGETS[@]}"; do
    [[ -f "$root/$t" ]] && existing+=("$t")
  done
  [[ ${#existing[@]} -gt 0 ]] || { echo ""; return; }
  ( cd "$root" && printf '%s\0' "${existing[@]}" | LC_ALL=C sort -z \
    | xargs -0 shasum -a 256 ) \
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

# Read the recorded top-level `lib_hash` scalar from an existing manifest.
# Returns the empty string if the manifest or the `lib_hash` field is absent
# (the "legacy install, no recorded lib hash" case the Stage 5 decision matrix
# falls back to skip-with-warning for). Issue #490 — extends the #152
# hash-tracked upgrade discipline to the Stage 5 lib override-target tier.
#
# Pure-bash grep/sed (no jq dependency), mirroring `read_recorded_hash`. The
# schema is hand-emitted by `write_manifest` as a single top-level field:
#   "lib_hash": "abc123..."
# We flatten newlines first so the parse is independent of one-line vs.
# pretty-printed JSON. `|| true` guards the no-match branch so a legacy
# manifest (no `lib_hash` key) returns "" rather than tripping `pipefail`.
read_recorded_lib_hash() {
  local manifest="$1"
  [[ -f "$manifest" ]] || { echo ""; return; }
  tr '\n' ' ' < "$manifest" \
    | grep -oE '"lib_hash"[[:space:]]*:[[:space:]]*"[a-f0-9]+"' \
    | head -n1 \
    | sed -E 's/.*"lib_hash"[[:space:]]*:[[:space:]]*"([a-f0-9]+)".*/\1/' \
    || true
}

# Read a recorded per-skill install version from an existing manifest. Returns
# the empty string if the manifest, the `skill_versions` block, or the
# requested skill entry is absent (the "legacy manifest, no recorded version"
# case — a pre-#633 install, or a skill installed before this field existed).
# Callers display "unknown" for the empty result. Issue #633.
#
# Mirrors `read_recorded_hash` exactly, but reads the `skill_versions` block
# instead of `skill_hashes` and matches a dotted SemVer value (`0.7.0`) rather
# than a hex digest. Pure-bash grep/sed (no jq dependency); `|| true` guards
# both no-match branches so a missing block/entry returns "" instead of
# tripping `set -euo pipefail`.
#
#   "skill_versions": {"memo": "0.8.0", "deck": "0.4.0"}
read_recorded_version() {
  local manifest="$1" skill="$2"
  [[ -f "$manifest" ]] || { echo ""; return; }
  local block
  block="$(tr '\n' ' ' < "$manifest" \
    | grep -oE '"skill_versions"[[:space:]]*:[[:space:]]*\{[^}]*\}' \
    | head -n1)" || true
  [[ -n "$block" ]] || { echo ""; return; }
  # `|| true` guards the no-match branch: a `skill_versions` block present but
  # missing an entry for the queried skill (partial/legacy manifest) must
  # return "" rather than propagate grep's exit 1 under pipefail — the same
  # guard read_recorded_hash uses for the identical scenario.
  printf '%s' "$block" \
    | tr ',' '\n' \
    | grep -E "\"$skill\"[[:space:]]*:[[:space:]]*\"[0-9][^\"]*\"" \
    | head -n1 \
    | sed -E "s/.*\"$skill\"[[:space:]]*:[[:space:]]*\"([0-9][^\"]*)\".*/\1/" \
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

# Append a single pattern to a .gitignore file idempotently (issue #577).
#
# Used by the private voice-grounding scaffold (Stage 7.9) to protect a
# gitignored grounding doc (e.g. VALUES.local.md) from accidental commit. This
# is the first installer-side .gitignore *writer* (project-share only ever
# *suggests*); kept as a reusable helper so sibling #578 can consume it.
#
# Contract:
#   * Idempotent: scans existing non-comment lines; if one already covers the
#     pattern (exact match after trimming, or a broader pattern equal to it),
#     it appends nothing and returns. Never duplicates an entry.
#   * Never rewrites or reorders existing lines — it only appends.
#   * Creates the .gitignore if absent, with a leading section comment.
#   * Ensures the file ends with a newline before appending (no line-joining).
#
# Args: $1 = path to .gitignore, $2 = pattern to ensure present.
gitignore_covers() {
  # Mirror project-share/lib/apply.py::_gitignore_covers minus the dir-only
  # candidates: here the pattern is matched verbatim against trimmed lines.
  local line="$1" pat="$2"
  [[ "$line" == "$pat" ]]
}

append_to_gitignore_idempotent() {
  local gitignore="$1" pattern="$2"
  if [[ -f "$gitignore" ]]; then
    # Already covered? Scan non-comment, non-blank lines for an exact match.
    local raw line
    while IFS= read -r raw || [[ -n "$raw" ]]; do
      line="${raw#"${raw%%[![:space:]]*}"}"   # ltrim
      line="${line%"${line##*[![:space:]]}"}"  # rtrim
      [[ -z "$line" || "$line" == \#* ]] && continue
      if gitignore_covers "$line" "$pattern"; then
        return 0  # already ignored — no-op
      fi
    done < "$gitignore"
    # Ensure a trailing newline so we never join onto an existing line.
    [[ -n "$(tail -c1 "$gitignore" 2>/dev/null)" ]] && printf '\n' >> "$gitignore"
    printf '%s\n' "$pattern" >> "$gitignore"
  else
    {
      printf '# Anvil private voice-grounding docs (issue #577) — kept local.\n'
      printf '%s\n' "$pattern"
    } > "$gitignore"
    chmod 0644 "$gitignore"
  fi
}

# Copy the lib tree from source, then restore (preserve) the consumer-modified
# override-target files from the destination (issue #490). Used by the Stage 5
# skip path: framework code under the lib tree must still upgrade (so the
# importable `anvil.lib.*` mirror never goes stale — the carve-out), but the
# documented override assets the consumer hand-edited (LIB_OVERRIDE_TARGETS)
# are preserved across the upgrade. We snapshot the dst override files to a
# temp dir BEFORE clobbering, recopy the whole tree from source, then restore
# the snapshots over the freshly-copied source assets.
copy_lib_preserving_overrides() {
  local src="$1" dst="$2" t stash
  stash="$(mktemp -d)"
  # Snapshot any existing dst override files (some may not exist yet).
  for t in "${LIB_OVERRIDE_TARGETS[@]}"; do
    if [[ -f "$dst/$t" ]]; then
      mkdir -p "$stash/$(dirname "$t")"
      cp "$dst/$t" "$stash/$t"
    fi
  done
  # Upgrade the whole tree from source (framework code always advances).
  mkdir -p "$dst" && cp -R "$src/." "$dst/"
  # Restore the consumer's override assets over the source defaults.
  for t in "${LIB_OVERRIDE_TARGETS[@]}"; do
    if [[ -f "$stash/$t" ]]; then
      mkdir -p "$dst/$(dirname "$t")"
      cp "$stash/$t" "$dst/$t"
    fi
  done
  rm -rf "$stash"
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
# The `skill_versions` block records, per skill, the `anvil_version` of the run
# that last ACTUALLY installed that skill's body (parallel to `skill_hashes`).
# On a skip run the prior value is carried forward, so the top-level
# `anvil_version` overwrite does not erase a frozen skill's install provenance.
# This lets the next upgrade report "last installed: vX, current: vY" for every
# skipped-override skill instead of a bare skip list. See issue #633.
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
#
# `lib_hash` (issue #490) records the as-installed hash of the Stage 5 lib
# *override-target* files (the documented consumer-override assets under
# `anvil/lib/<skill>/` — styles.css / template.html / template.tex). It is a
# single scalar (parallel to `skill_hashes` but not per-skill) because the
# protected surface is a small, fixed glob, not a per-skill tree. On
# re-install, Stage 5 compares the current override-target hash against this
# baseline to tell apart "consumer hand-edited an override asset" (preserve,
# skip-with-warning unless --force) from "source moved forward" (auto-upgrade).
# The rest of the lib tree (importable framework code + __init__.py) always
# upgrades regardless of this hash — the carve-out that keeps `anvil.lib.*`
# from ever going stale.
write_manifest() {
  local target_dir="$1" manifest_path="$2"
  local anvil_version="$3" anvil_source="$4" install_date="$5"
  local installed_json="$6" skipped_json="$7" hashes_json="$8"
  local versions_json="$9"
  local layout_version="${10:-2}" lib_hash="${11:-}"
  mkdir -p "$target_dir/.anvil"
  cat > "$manifest_path" <<MANIFEST_EOF
{
  "anvil_version": "$anvil_version",
  "anvil_source": "$anvil_source",
  "install_date": "$install_date",
  "layout_version": $layout_version,
  "installed_skills": $installed_json,
  "skipped_overrides": $skipped_json,
  "skill_hashes": $hashes_json,
  "skill_versions": $versions_json,
  "lib_hash": "$lib_hash"
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
# Issue #490: as-installed hash of the lib override-target files, recorded
# under the manifest's top-level `lib_hash`. Set by Stage 5. Empty until Stage
# 5 runs; Stage 9 writes whatever value Stage 5 computed (fresh/auto-upgrade/
# overwrite all record the new source hash; a consumer-modified skip carries
# the prior recorded hash forward so the next install can still detect drift).
LIB_HASH=""
# Whether Stage 5 preserved consumer-modified lib override assets (skip path).
# Surfaced in the Stage 11 summary, mirroring SKIPPED_OVERRIDES for skills.
SKIPPED_LIB=false
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

# Per-skill "as-installed" Anvil version. Keys are skill names, values are the
# `ANVIL_VERSION` string of the installer run that last ACTUALLY installed that
# skill's body. Recorded under `skill_versions` in the manifest (parallel to
# `skill_hashes`) so a subsequent re-install that SKIPS a consumer-modified
# skill can report how many releases behind the frozen copy is — the top-level
# `anvil_version` scalar is overwritten every run and cannot answer this for a
# skill that was last installed several releases earlier (issue #633).
#
# Same Bash-3.x parallel-array shape as SKILL_HASH_KEYS/VALUES (no associative
# arrays on the macOS default shell).
SKILL_VERSION_KEYS=()
SKILL_VERSION_VALUES=()

# Append a (skill, version) entry to the parallel-array version table.
# Overwrites an existing entry for `skill` if present (the recorded version
# should reflect the most recent successful install for that skill).
set_skill_version() {
  local skill="$1" version="$2" i
  for ((i = 0; i < ${#SKILL_VERSION_KEYS[@]}; i++)); do
    if [[ "${SKILL_VERSION_KEYS[$i]}" == "$skill" ]]; then
      SKILL_VERSION_VALUES[$i]="$version"
      return
    fi
  done
  SKILL_VERSION_KEYS+=("$skill")
  SKILL_VERSION_VALUES+=("$version")
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
#
# Override-detection decision matrix (issue #490) — applies ONLY to the
# documented lib override-target assets (LIB_OVERRIDE_TARGETS, e.g.
# memo/styles.css). Mirrors the Stage 7 skill-body matrix but on a small fixed
# glob, recorded as a single top-level `lib_hash` scalar in the manifest:
#
#   Destination state                          Action
#   ────────────────────────────────────────── ───────────────────────────────
#   DST_LIB does not exist                     Fresh install. Copy tree.
#                                              Record lib_hash.
#   Override assets identical to source        Recopy idempotently. Record
#                                              lib_hash.
#   --force passed                             Overwrite unconditionally
#                                              (warn). Record lib_hash.
#   Override assets differ, recorded lib_hash
#     matches current override hash            Auto-upgrade (consumer hasn't
#                                              modified). Copy tree. Record
#                                              new lib_hash.
#   Override assets differ, NO recorded
#     lib_hash (legacy manifest)               Skip-with-warning: upgrade
#                                              framework code, PRESERVE the
#                                              override assets. Require --force
#                                              to overwrite. One-time cost.
#   Override assets differ, recorded lib_hash
#     present and != current                   Consumer-modified. Upgrade
#                                              framework code, PRESERVE the
#                                              override assets. Require --force.
#
# CARVE-OUT (critical, issue #490): in EVERY branch above — including the two
# skip branches — the rest of the lib tree (importable framework code, the
# schema JSON, figures, marp config) and `anvil/__init__.py` are upgraded
# unconditionally. Only the LIB_OVERRIDE_TARGETS files are ever preserved. A
# consumer can never pin stale framework code by editing an override asset:
# the importable `anvil.lib.*` mirror always advances.
info "Stage 5: copy framework code (anvil/lib -> .anvil/anvil/lib)"
SRC_LIB="$ANVIL_ROOT/anvil/lib"
DST_ANVIL_PKG="$TARGET/.anvil/anvil"
DST_LIB="$DST_ANVIL_PKG/lib"
SRC_ANVIL_INIT="$ANVIL_ROOT/anvil/__init__.py"
if [[ -d "$SRC_LIB" ]]; then
  # Decide the lib override verdict. We compute hashes even under --dry-run
  # because the comparison is read-only; the verdict is woven into the action
  # label so the dry-run preview is honest (issue #81).
  lib_verdict="install fresh"
  lib_copy_fn=copy_tree
  if [[ ! -d "$DST_LIB" ]]; then
    lib_verdict="install fresh"
  elif dirs_identical "$SRC_LIB" "$DST_LIB"; then
    note "framework lib already installed and unchanged (refreshing safely)"
    lib_verdict="recopy (identical to source)"
  elif [[ "$FORCE" == true ]]; then
    warn "overwriting consumer-modified lib override file(s) in .anvil/anvil/lib (--force)"
    lib_verdict="overwrite (--force)"
  else
    recorded_lib_hash="$(read_recorded_lib_hash "$MANIFEST")"
    current_lib_override_hash="$(lib_override_hash "$DST_LIB")"
    src_lib_override_hash="$(lib_override_hash "$SRC_LIB")"
    if [[ "$current_lib_override_hash" == "$src_lib_override_hash" ]]; then
      # The override assets themselves are untouched relative to source — the
      # tree differs only in framework code. Plain upgrade, record new hash.
      note "framework lib override assets unchanged vs source; upgrading framework code"
      lib_verdict="auto-upgrade (override assets match source)"
    elif [[ -n "$recorded_lib_hash" && "$recorded_lib_hash" == "$current_lib_override_hash" ]]; then
      # Override assets differ from source, but match the as-installed
      # baseline → consumer never touched them; source moved forward. Safe.
      note "framework lib is unmodified-since-install (recorded lib_hash matches); auto-upgrading from source"
      lib_verdict="auto-upgrade (unmodified-since-install)"
    elif [[ -z "$recorded_lib_hash" ]]; then
      # Legacy manifest (no lib_hash). Fall back to conservative skip: upgrade
      # framework code but preserve the override assets. One-time --force cost.
      warn "skipped: consumer-modified .anvil/anvil/lib override asset(s) (legacy install, no recorded lib_hash; re-run with --force to overwrite — framework code still upgrades, override assets preserved)"
      lib_verdict="skip override assets (legacy install, no recorded hash)"
      lib_copy_fn=copy_lib_preserving_overrides
      SKIPPED_LIB=true
    else
      # Recorded hash exists and differs → consumer modified an override asset.
      warn "skipped: consumer-modified .anvil/anvil/lib override asset(s) (re-run with --force to overwrite — framework code still upgrades, override assets preserved)"
      lib_verdict="skip override assets (consumer-modified)"
      lib_copy_fn=copy_lib_preserving_overrides
      SKIPPED_LIB=true
    fi
  fi

  # Copy contents (cp -R src/. dest preserves contents, not the wrapper dir).
  # The copy fn is either copy_tree (framework + assets advance) or
  # copy_lib_preserving_overrides (framework advances, override assets kept).
  do_action "install $DST_LIB from $SRC_LIB [$lib_verdict]" "$lib_copy_fn" "$SRC_LIB" "$DST_LIB"

  # Record the lib_hash for the manifest. On a skip we carry the prior recorded
  # hash forward (so a future install still detects the modification); when
  # there is no prior hash (legacy/fresh skip) we fall back to the now-
  # preserved dst override hash so the entry is non-empty. On every non-skip
  # branch we record the source override hash (== the now-installed dst).
  if [[ "$SKIPPED_LIB" == true ]]; then
    prior_lib_hash="$(read_recorded_lib_hash "$MANIFEST")"
    if [[ -n "$prior_lib_hash" ]]; then
      LIB_HASH="$prior_lib_hash"
    else
      LIB_HASH="$(lib_override_hash "$DST_LIB")"
    fi
  else
    LIB_HASH="$(lib_override_hash "$SRC_LIB")"
  fi

  # Copy the anvil package's top-level __init__.py so `import anvil` resolves.
  # ALWAYS unconditional (the namespace anchor must never go stale — carve-out).
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
  echo "         The post-#230 layout resolves ALL framework code and assets"
  echo "         under .anvil/anvil/lib/ (now installed). Every 'anvil/lib/*'"
  echo "         path in the command specs — snippets/, marp/config.yml,"
  echo "         figures/, and the 'python -m anvil.lib.*' invocations — maps to"
  echo "         .anvil/anvil/lib/ in this repo, NOT the legacy .anvil/lib/."
  echo "         The legacy dir is no longer on any import path; leaving it in"
  echo "         place makes agents/critics rediscover the indirection (issue #624)."
  echo "         If you hand-edited files in .anvil/lib/ (e.g. memo styles.css),"
  echo "         port them to the matching path under .anvil/anvil/lib/ and then"
  echo "         remove .anvil/lib/ to remove the ambiguity."
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
        prior_version="$(read_recorded_version "$MANIFEST" "$skill")"
        warn "skipped: consumer-modified .anvil/skills/$skill (last installed: ${prior_version:-unknown}, current: v$ANVIL_VERSION; legacy install, no recorded hash; re-run with --force to overwrite — future installs will auto-detect)"
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
        prior_version="$(read_recorded_version "$MANIFEST" "$skill")"
        warn "skipped: consumer-modified .anvil/skills/$skill (last installed: ${prior_version:-unknown}, current: v$ANVIL_VERSION; re-run with --force to overwrite)"
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
  # Record the Anvil version this skill was actually installed under, parallel
  # to the hash. On a later skip run this is what read_recorded_version reads
  # back to report staleness ("last installed: vX") — issue #633.
  set_skill_version "$skill" "$ANVIL_VERSION"
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
# Copy mode: per-file copy from source, scoped to SELECTED_SKILLS. Agents are
# NOT consumer-override targets (the canonical body lives in the source command
# file the agent points at; the agent shim only declares registry metadata).
# The `--force` flag is therefore not needed for the agents/ copy — every
# install refreshes the selected agent set. Skills, by contrast, ARE override
# targets (consumers can patch templates/, rubric.md, etc.), which is why
# Stage 7 carries the override-detection decision matrix.
#
# Filter behavior (issue #662): the agents/ copy IS scoped by --skills=. Agent
# filenames follow anvil-<skill>-<phase>.md, and each <skill> matches a
# directory under anvil/skills/ (the same ALL_SKILLS enumeration Stage 4
# builds). A --skills=pub install therefore installs only the 5 anvil-pub-*.md
# shims, not the full 54-file registry — matching the strict-subset framing of
# the flag itself. (A prior comment here claimed the copy was NOT scoped by
# --skills=, on the rationale that a skill-pinned install might spawn agents for
# non-installed skills. The tractatus canary contradicted that: --skills=pub is
# a real fan-out pattern, and the agent-picker noise from 49 unusable shims is
# real friction — not a "documentation / dev path.")
#
# Longest-prefix-match hazard: `ip-uspto` and `ip-uspto-provisional` share a
# filename prefix, so a naive substring/glob filter would leak
# anvil-ip-uspto-provisional-*.md into an `ip-uspto`-only install. The resolver
# below strips the `anvil-` prefix and `.md` suffix, then finds the LONGEST
# skill name in ALL_SKILLS that is a `-`-delimited prefix of what remains
# (rest == skill || rest starts with "$skill-"). Exact-equality on the
# `-`-delimited segment — never a substring test. (Stage 4's own comment flags
# this same sibling-prefix hazard for sort ordering.)
#
# Shared/unprefixed agents: any agent file whose name does not resolve to a
# known skill prefix is copied UNCONDITIONALLY (with a note), so a future
# shared/framework agent doesn't silently regress into this same filtering bug.
# No such file exists today (all 54 map to one of the 11 artifact-class skills).
#
# Narrowing prune (issue #685): re-running the installer with a *narrower*
# --skills= set after a wider install DOES now prune previously-installed,
# now-out-of-scope agent files under .claude/agents/. The prune pass (below,
# after the copy loop) removes exactly those `anvil-<skill>-*.md` files that
# resolve (via agent_skill_for) to a known skill NOT in the current
# SELECTED_SKILLS. This is safe to do automatically because every such file is
# an installer-owned artifact: every byte originates from anvil/agents/ in the
# source repo and is recopied verbatim on each install — there is no
# consumer-authored content to lose (unlike consumer git state, cf. #684, which
# stays hint-only). Non-anvil files (e.g. a sibling Loom install's loom-*.md
# shims) and shared/unprefixed anvil agents (agent_skill_for -> "") are never
# touched; the prune is per-file, never a directory blow-away. The pass is a
# no-op on a full/unscoped install (SELECTED_SKILLS == ALL_SKILLS) and honors
# --dry-run.
info "Stage 7.5: copy Anvil subagent definitions (anvil/agents -> .claude/agents)"
SRC_AGENTS="$ANVIL_ROOT/anvil/agents"
DST_AGENTS="$TARGET/.claude/agents"
INSTALLED_AGENTS_COUNT=0

# Resolve an agent filename to the skill it belongs to, using longest-prefix,
# `-`-delimited matching against ALL_SKILLS. Echoes the resolved skill name, or
# nothing if the file maps to no known skill (a shared/unprefixed agent).
agent_skill_for() {
  local base="$1"          # e.g. anvil-ip-uspto-provisional-drafter.md
  local rest="${base#anvil-}"
  rest="${rest%.md}"       # e.g. ip-uspto-provisional-drafter
  local best="" avail
  for avail in "${ALL_SKILLS[@]}"; do
    if [[ "$rest" == "$avail" || "$rest" == "$avail-"* ]]; then
      # Prefer the longest matching skill name so `ip-uspto-provisional-*`
      # resolves to `ip-uspto-provisional`, not the shorter `ip-uspto`.
      if [[ ${#avail} -gt ${#best} ]]; then
        best="$avail"
      fi
    fi
  done
  printf '%s' "$best"
}

# Return 0 if $1 is in SELECTED_SKILLS, 1 otherwise.
skill_selected() {
  local needle="$1" s
  for s in "${SELECTED_SKILLS[@]}"; do
    [[ "$s" == "$needle" ]] && return 0
  done
  return 1
}

if [[ -d "$SRC_AGENTS" ]]; then
  # Build the filtered file list up front so the action count is honest under
  # --dry-run (issue #81) — computed from the SELECTED_SKILLS-scoped set, not
  # the full glob.
  AGENTS_TO_INSTALL=()
  while IFS= read -r -d '' agent_file; do
    base="$(basename "$agent_file")"
    skill="$(agent_skill_for "$base")"
    if [[ -z "$skill" ]]; then
      # Shared/unprefixed agent: no known skill owns it. Copy unconditionally
      # so a future shared agent doesn't get filtered out. No such file exists
      # today; the note makes the defensive branch observable if one is added.
      note "agent '$base' maps to no known skill; installing unconditionally (shared/framework agent)"
      AGENTS_TO_INSTALL+=("$agent_file")
    elif skill_selected "$skill"; then
      AGENTS_TO_INSTALL+=("$agent_file")
    fi
  done < <(find "$SRC_AGENTS" -maxdepth 1 -name 'anvil-*.md' -type f -print0 | LC_ALL=C sort -z)

  AGENT_COUNT="${#AGENTS_TO_INSTALL[@]}"
  if [[ "$AGENT_COUNT" -gt 0 ]]; then
    if [[ "$DRY_RUN" == true ]]; then
      # Dry-run: no side effects on disk. Only the planned action line is
      # surfaced so the operator sees what a real run would copy.
      echo "  [dry-run] copy $AGENT_COUNT agent files from $SRC_AGENTS to $DST_AGENTS"
    else
      # Per-file copy (not replace_tree) so we don't blow away any non-anvil
      # agents the consumer has added under .claude/agents/ (e.g., loom-*
      # agents from a sibling Loom install), or anvil agents for skills the
      # consumer selected in a previous (wider) install (see out-of-scope note
      # above).
      mkdir -p "$DST_AGENTS"
      for agent_file in "${AGENTS_TO_INSTALL[@]}"; do
        cp "$agent_file" "$DST_AGENTS/"
        INSTALLED_AGENTS_COUNT=$((INSTALLED_AGENTS_COUNT + 1))
      done
      ok "$INSTALLED_AGENTS_COUNT subagent registration(s) installed at $DST_AGENTS"
    fi
  else
    note "no anvil-*.md files matched the selected skills under $SRC_AGENTS (skipping)"
  fi
else
  note "source agents dir not found: $SRC_AGENTS (skipping; pre-#377 source checkout?)"
fi

# Prune stale agent files (issue #685): remove anything under $DST_AGENTS
# matching anvil-*.md that resolves (via agent_skill_for) to a KNOWN skill NOT
# in SELECTED_SKILLS — leftovers from a prior, wider install. Skip entirely on a
# full/unscoped install (SELECTED_SKILLS == ALL_SKILLS): there is no "unselected
# skill" concept then, so the pass is a no-op in the common case. The guard
# mirrors the Stage 9 drift-detection guard (only matters on a narrower-than-full
# selection). Non-anvil files and shared/unprefixed anvil agents
# (agent_skill_for -> "") are never touched; removal is per-file, never a
# directory blow-away.
if [[ -d "$DST_AGENTS" && ${#SELECTED_SKILLS[@]} -lt ${#ALL_SKILLS[@]} ]]; then
  STALE_AGENTS=()
  while IFS= read -r -d '' existing_file; do
    ebase="$(basename "$existing_file")"
    eskill="$(agent_skill_for "$ebase")"
    if [[ -n "$eskill" ]] && ! skill_selected "$eskill"; then
      STALE_AGENTS+=("$existing_file")
    fi
  done < <(find "$DST_AGENTS" -maxdepth 1 -name 'anvil-*.md' -type f -print0 | LC_ALL=C sort -z)

  if [[ ${#STALE_AGENTS[@]} -gt 0 ]]; then
    if [[ "$DRY_RUN" == true ]]; then
      echo "  [dry-run] would remove ${#STALE_AGENTS[@]} stale agent file(s) for unselected skills"
    else
      for stale in "${STALE_AGENTS[@]}"; do
        rm -f "$stale"
      done
      note "removed ${#STALE_AGENTS[@]} stale agent file(s) from a prior wider install (skills not in current selection)"
    fi
  fi
fi

# ----- Stage 7.8: scaffold starter theme (issue #471) ------------------------
# The framework memo CSS is deliberately minimal by maintainer policy, so a
# fresh consumer's first rendered memo looks unstyled ("did the render
# break?"). Seed a consumer-owned starter theme at <target>/.anvil/themes/
# starter/ — the theme tier is the only consumer-owned path the installer
# never touches on upgrade, so the scaffold survives every re-install
# (including --force), unlike the Stage 5 lib copy which is overwritten
# unconditionally.
#
# Contract:
#   * Gated on `memo` being in SELECTED_SKILLS (the scaffold is memo-side).
#   * Skip-if-exists: if .anvil/themes/starter/ already exists (in any
#     state), the installer leaves it alone — NEVER overwrite anything
#     under .anvil/themes/. Sibling themes are untouched by construction
#     (we only ever write the starter/ subdir, and only when absent).
#   * Scaffolding alone is inert: the theme tier activates only when a
#     project BRIEF declares `theme: starter`. The Stage 11 summary prints
#     the enable step so the operator (or agent) sees the one-liner.
#   * --dry-run reports the would-scaffold action and writes nothing
#     (issue #81 honesty discipline).
info "Stage 7.8: scaffold starter theme (anvil/templates/themes/starter -> .anvil/themes/starter)"
SRC_STARTER_THEME="$ANVIL_ROOT/anvil/templates/themes/starter"
DST_STARTER_THEME="$TARGET/.anvil/themes/starter"
MEMO_SELECTED=false
for s in "${SELECTED_SKILLS[@]}"; do
  if [[ "$s" == "memo" ]]; then MEMO_SELECTED=true; break; fi
done
if [[ "$MEMO_SELECTED" != true ]]; then
  note "memo not in selected skills; skipping starter theme scaffold"
elif [[ ! -d "$SRC_STARTER_THEME" ]]; then
  note "source starter theme not found: $SRC_STARTER_THEME (skipping)"
elif [[ -e "$DST_STARTER_THEME" ]]; then
  note "existing .anvil/themes/starter detected — preserving (the installer never overwrites files under .anvil/themes/)"
else
  do_action "scaffold starter theme at .anvil/themes/starter (consumer-owned; never overwritten on upgrade)" \
    copy_tree "$SRC_STARTER_THEME" "$DST_STARTER_THEME"
  # Suppress post-action confirmation under --dry-run (issue #81).
  [[ "$DRY_RUN" == true ]] || ok "starter theme scaffolded (enable per project with 'theme: starter' in BRIEF.md)"
fi

# ----- Stage 7.9: scaffold starter voice-grounding docs (issue #576) ---------
# Anvil documents the voice-grounding contract (issue #461;
# anvil/lib/snippets/voice_grounding.md) but a consumer adopting it faced a
# blank page — anvil shipped zero starter grounding documents. Stage 7.9 drops
# the two ship-now, de-personalized templates
# (anvil/templates/voice/STYLE_GUIDE.template.md and VOCABULARY.template.md)
# under .anvil/voice/ as .anvil/voice/STYLE_GUIDE.md / .anvil/voice/VOCABULARY.md
# (stripping the `.template` infix). Issue #617 relocated the scaffold
# destination from the CONSUMER ROOT to the `.anvil/voice/` hierarchy so the
# voice docs stop cluttering the repo root (a root-level STYLE_GUIDE.md reads
# as *code* style guidance to a contributor who does not know Anvil) and live
# alongside every other Anvil-owned file (.anvil/themes/, .anvil/skills/,
# .anvil/CLAUDE.md). resolve_voice_docs is fully path-agnostic — its
# consumer-root fallback resolves a declared `.anvil/voice/STYLE_GUIDE.md`
# exactly as it resolved the old root path — so only the installer default and
# the docs change; no library or skill-command edits are required.
#
# Contract (mirrors Stage 7.8; the idempotent skip-if-exists model):
#   * Gated on a voice-consuming skill (`essay` or `memo`) being in
#     SELECTED_SKILLS — the docs are only useful to a skill that grounds in
#     them.
#   * Per-file skip-if-exists checks BOTH the new .anvil/voice/ location AND
#     the pre-#617 root location: if .anvil/voice/STYLE_GUIDE.md (or an old
#     root STYLE_GUIDE.md left by a pre-#617 install) already exists, it is
#     PRESERVED untouched and the stage notes the skip — per file, not
#     all-or-nothing. The dual check keeps an upgrade from scaffolding a
#     confusing duplicate beside a user-edited root doc. A hand-authored
#     STYLE_GUIDE.md does not block VOCABULARY.md from scaffolding.
#   * NEVER overwrites an existing grounding doc (warn-and-skip). The
#     scaffold is inert until a project BRIEF declares the `voice:` block;
#     the stage prints the exact YAML to paste rather than auto-editing a
#     hand-authored BRIEF.
#   * --dry-run reports the would-scaffold action and writes nothing
#     (issue #81 honesty discipline).
#
# Reuses the existing `voice:` grammar (anvil/lib/project_brief.py::VoiceDocs /
# resolve_voice_docs) — no new declaration mechanism.
#
# Private voice-grounding protection (issue #577): the personal layer of voice
# grounding (VALUES.md-class stances) is the half a consumer often will NOT want
# committed. Anvil makes private grounding a designed posture — the documented
# convention is the `*.local.md` suffix (default) or a `.voice/` locus
# (alternative). resolve_voice_docs resolves a gitignored declared doc
# identically to a committed one (it never consults git status), so the only
# work is to PROTECT the private path from accidental commit. This stage appends
# those patterns to the consumer's .gitignore idempotently
# (append_to_gitignore_idempotent above) so a private VALUES.local.md never gets
# committed by mistake. VALUES.md's own template/schema is #578, a downstream
# consumer of this already-shipped private path.
info "Stage 7.9: scaffold starter voice-grounding docs (anvil/templates/voice -> .anvil/voice/)"
SRC_VOICE_DIR="$ANVIL_ROOT/anvil/templates/voice"
VOICE_SKILL_SELECTED=false
for s in "${SELECTED_SKILLS[@]}"; do
  if [[ "$s" == "essay" || "$s" == "memo" ]]; then VOICE_SKILL_SELECTED=true; break; fi
done
VOICE_SCAFFOLDED_ANY=false
if [[ "$VOICE_SKILL_SELECTED" != true ]]; then
  note "no voice-consuming skill (essay/memo) selected; skipping voice-grounding scaffold"
elif [[ ! -d "$SRC_VOICE_DIR" ]]; then
  note "source voice templates dir not found: $SRC_VOICE_DIR (skipping)"
else
  # Map each shipped template to its de-infixed destination filename.
  # VALUES is PRIVATE BY DEFAULT (issue #578): it scaffolds to a
  # VALUES.local.md (NOT a committed VALUES.md) so the `*.local.md` gitignore
  # line appended below keeps the first-person stances/anti-stances/standing
  # out of commits. resolve_voice_docs resolves a gitignored declared doc
  # identically to a committed one — privacy is where the file lives in git,
  # not how anvil reads it.
  # The vocab.words.txt:VOCABULARY.words.txt pair (issue #602) seeds the
  # sibling word list that anvil/lib/vocab_reminder.py::resolve_word_list()
  # picks up automatically: it resolves a `<stem>.words.txt` next to the
  # declared voice.vocabulary doc (VOCABULARY.words.txt beside VOCABULARY.md),
  # falling back to the shipped package default only when no sibling exists.
  # Scaffolding it here means the consumer owns and grows the list with zero
  # BRIEF changes. Unlike VALUES.local.md this is COMMITTED by design — a word
  # list carries no first-person stances, so it matches VOCABULARY.md's
  # committed posture and needs no gitignore pattern below. The source ships
  # without a `.template.` infix (it is a real starter list, not a fill-in
  # scaffold), so the pair is `vocab.words.txt:VOCABULARY.words.txt`.
  for voice_pair in "STYLE_GUIDE.template.md:STYLE_GUIDE.md" "VOCABULARY.template.md:VOCABULARY.md" "VALUES.template.md:VALUES.local.md" "vocab.words.txt:VOCABULARY.words.txt"; do
    voice_src_name="${voice_pair%%:*}"
    voice_dst_name="${voice_pair##*:}"
    voice_src="$SRC_VOICE_DIR/$voice_src_name"
    # Canonical post-#617 destination lives under .anvil/voice/. The relative
    # form (voice_dst_rel) is what the operator sees in action lines / skip
    # notes / the pasteable BRIEF snippet, so it matches what they declare.
    voice_dst_rel=".anvil/voice/$voice_dst_name"
    voice_dst="$TARGET/$voice_dst_rel"
    # Pre-#617 installs scaffolded to the consumer root. A root-level doc there
    # may be user-edited — the migration guard preserves it and suppresses the
    # new-location scaffold so an upgrade never drops a confusing duplicate.
    voice_dst_old="$TARGET/$voice_dst_name"
    if [[ ! -f "$voice_src" ]]; then
      note "source voice template not found: $voice_src (skipping)"
    elif [[ -e "$voice_dst" ]]; then
      note "existing $voice_dst_rel detected — preserving (the installer never overwrites a grounding doc)"
    elif [[ -e "$voice_dst_old" ]]; then
      note "existing root-level $voice_dst_name detected (pre-#617 install) — preserving at root, not re-scaffolding to $voice_dst_rel"
    else
      do_action "scaffold voice-grounding doc at $voice_dst_rel (consumer-owned; tune the <!-- replace me --> placeholders)" \
        copy_file_with_parents "$voice_src" "$voice_dst"
      [[ "$DRY_RUN" == true ]] || { ok "$voice_dst_rel scaffolded"; VOICE_SCAFFOLDED_ANY=true; }
    fi
  done

  # Protect the private voice-grounding paths (issue #577). The documented
  # convention is `*.local.md` (default) and a `.voice/` locus (alternative);
  # we gitignore BOTH patterns so a consumer adopting EITHER is covered, and a
  # private VALUES.local.md (or .voice/VALUES.md) is never committed by
  # accident. Idempotent (re-install never duplicates) and never rewrites
  # unrelated lines (append_to_gitignore_idempotent). This is a DISTINCT
  # do_action from the file copy so --dry-run output and skip-notes read
  # clearly. The append covers both new and pre-existing .gitignore files.
  VOICE_GITIGNORE="$TARGET/.gitignore"
  for voice_pattern in "*.local.md" "/.voice/"; do
    # Determine whether the pattern is already covered, so the note reads
    # honestly under both --dry-run and a real re-run.
    voice_pat_covered=false
    if [[ -f "$VOICE_GITIGNORE" ]]; then
      while IFS= read -r voice_raw || [[ -n "$voice_raw" ]]; do
        voice_line="${voice_raw#"${voice_raw%%[![:space:]]*}"}"
        voice_line="${voice_line%"${voice_line##*[![:space:]]}"}"
        [[ -z "$voice_line" || "$voice_line" == \#* ]] && continue
        if [[ "$voice_line" == "$voice_pattern" ]]; then voice_pat_covered=true; break; fi
      done < "$VOICE_GITIGNORE"
    fi
    if [[ "$voice_pat_covered" == true ]]; then
      note ".gitignore already ignores '$voice_pattern' (private voice grounding) — skipping append"
    else
      do_action "append '$voice_pattern' to .gitignore (protect private voice-grounding docs from commit)" \
        append_to_gitignore_idempotent "$VOICE_GITIGNORE" "$voice_pattern"
      [[ "$DRY_RUN" == true ]] || ok "'$voice_pattern' added to .gitignore (private voice grounding stays local)"
    fi
  done
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

# ----- Stage 8.6: write .anvil/.gitignore (issue #674) ----------------------
# The installer owns a Python mirror under .anvil/anvil/ and (absent --no-sync)
# a venv at .anvil/.venv/. Any consumer command that runs `uv run --project
# .anvil ...` (every critic importing anvil.lib.*) leaves `__pycache__/*.pyc`
# bytecode caches under .anvil/anvil/**, dirtying `git status` in every
# worktree, every time. Ship a self-contained .anvil/.gitignore so those
# runtime artifacts are suppressed.
#
# Contract:
#   * Self-contained under .anvil/ — NOT an append to the consumer's root
#     .gitignore. The patterns cover the installer's own .anvil/ Python
#     footprint (bytecode caches + the venv), which has nothing to do with the
#     consumer's project layout; they are closer in spirit to Stage 8.5's
#     .anvil/pyproject.toml than to the voice-grounding root-.gitignore append.
#     Relative patterns inside a tracked nested .gitignore resolve against its
#     own directory, so `__pycache__/` and `.venv/` here suppress
#     .anvil/anvil/**/__pycache__/*.pyc and .anvil/.venv/* without touching the
#     consumer's root .gitignore at all.
#   * Unconditional — fires on every install regardless of --skills= selection
#     (unlike the skill-gated Stage 7.9 voice patterns), since every install
#     creates the .anvil/anvil/ mirror and (absent --no-sync) the .anvil/.venv/.
#   * Skip-if-exists — matching the Stage 7.8 starter-theme convention: an
#     installer-owned generated file is written once and left alone if the
#     consumer has since hand-edited it. This deliberately does NOT reuse
#     append_to_gitignore_idempotent() (that helper is for appending into a
#     consumer-owned root file, not for an installer-owned generated file).
#   * --dry-run reports the would-write action and writes nothing (issue #81).
info "Stage 8.6: write .anvil/.gitignore (suppress __pycache__ + .venv runtime artifacts)"
ANVIL_GITIGNORE="$TARGET/.anvil/.gitignore"

write_anvil_gitignore() {
  local dst="$1"
  mkdir -p "$(dirname "$dst")"
  cat > "$dst" <<'EOF'
# Anvil-owned .gitignore — suppresses the Python runtime artifacts the anvil
# installer's own .anvil/ footprint generates (bytecode caches under the
# .anvil/anvil/ mirror + the uv venv at .anvil/.venv/). Patterns are relative
# to this directory. The installer writes this file once (skip-if-exists), so
# any local additions you make here survive re-install.
__pycache__/
*.py[cod]
.venv/
EOF
}

if [[ -e "$ANVIL_GITIGNORE" ]]; then
  note "existing .anvil/.gitignore detected — preserving (the installer writes it once, never clobbers a hand-edit)"
else
  do_action "write .anvil/.gitignore (ignore __pycache__/ and .venv/ runtime artifacts)" \
    write_anvil_gitignore "$ANVIL_GITIGNORE"
  [[ "$DRY_RUN" == true ]] || ok ".anvil/.gitignore written (runtime bytecode + venv stay out of git status)"
fi

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
  # Carry forward the prior install version too (issue #633). A skipped skill
  # was NOT re-installed this run, so its version must stay pinned to the run
  # that last actually installed it — otherwise the next upgrade loses the
  # staleness baseline and reports "last installed: unknown".
  prior_ver="$(read_recorded_version "$MANIFEST" "$skipped")"
  if [[ -n "$prior_ver" ]]; then
    set_skill_version "$skipped" "$prior_ver"
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

# Build the `skill_versions` JSON object from the parallel-array version table.
# Mirrors json_object_from_skill_hashes; empty table emits `{}`. Issue #633.
json_object_from_skill_versions() {
  local first=true i
  printf '{'
  for ((i = 0; i < ${#SKILL_VERSION_KEYS[@]}; i++)); do
    if $first; then first=false; else printf ', '; fi
    printf '"%s": "%s"' "${SKILL_VERSION_KEYS[$i]}" "${SKILL_VERSION_VALUES[$i]}"
  done
  printf '}'
}

INSTALLED_JSON="$(json_array_from_list ${INSTALLED_SKILLS[@]+"${INSTALLED_SKILLS[@]}"})"
SKIPPED_JSON="$(json_array_from_list ${SKIPPED_OVERRIDES[@]+"${SKIPPED_OVERRIDES[@]}"})"
HASHES_JSON="$(json_object_from_skill_hashes)"
VERSIONS_JSON="$(json_object_from_skill_versions)"

do_action "write $MANIFEST" \
  write_manifest "$TARGET" "$MANIFEST" "$ANVIL_VERSION" "$ANVIL_ROOT" "$INSTALL_DATE" \
                 "$INSTALLED_JSON" "$SKIPPED_JSON" "$HASHES_JSON" "$VERSIONS_JSON" "2" "$LIB_HASH"

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
  echo "  would skip lib:      $([[ "$SKIPPED_LIB" == true ]] && echo "override assets preserved (framework code upgrades)" || echo "(none)")"
  echo "  would target:        $TARGET/.anvil"
else
  echo "  installed skills:    ${INSTALLED_SKILLS[*]:-(none -- all were consumer-modified)}"
  echo "  skipped overrides:   ${SKIPPED_OVERRIDES[*]:-(none)}"
  echo "  skipped lib:         $([[ "$SKIPPED_LIB" == true ]] && echo "override assets preserved (framework code upgrades)" || echo "(none)")"
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
  # Memo styling hint (issue #471): the framework default CSS is deliberately
  # minimal (black-on-white, no accents) — first-time consumers read that as
  # "the styling failed." Print the correct post-#230 override paths and the
  # one-line theme enable step so the operator (or an agent with no aesthetic
  # intuition) knows where styling lives. Paths per
  # anvil/skills/memo/lib/theme_resolver.py::resolve_memo_asset.
  if [[ "$MEMO_SELECTED" == true ]]; then
    echo ""
    note "memo styling: the framework default CSS is deliberately minimal."
    echo "         A starter theme is scaffolded at .anvil/themes/starter/ (consumer-"
    echo "         owned; the installer never overwrites files under .anvil/themes/)."
    echo "         Enable it per project in the project BRIEF.md frontmatter:"
    echo "             theme: starter"
    echo "         Override paths (resolution order):"
    echo "           durable (theme tier):  .anvil/themes/<theme>/memo/styles.css"
    echo "           in-place (lib copy):   .anvil/anvil/lib/memo/styles.css"
    echo "             CAUTION: the in-place copy is overwritten on every re-install/"
    echo "             upgrade — prefer the theme tier for durable overrides."
  fi
  # Voice-grounding hint (issue #576): the scaffolded voice docs are inert
  # until a project BRIEF declares the `voice:` block. We deliberately do NOT
  # auto-edit the consumer's BRIEF — print the exact YAML snippet to paste so
  # the wiring stays explicit. Paths use the .anvil/voice/ prefix (issue #617).
  if [[ "$VOICE_SKILL_SELECTED" == true ]]; then
    echo ""
    note "voice grounding: starter STYLE_GUIDE.md / VOCABULARY.md / VALUES.local.md scaffolded under .anvil/voice/."
    echo "         They ship as templates — fill in the <!-- replace me --> placeholders with"
    echo "         examples (and your own first-person stances, for VALUES) before relying on"
    echo "         them, then activate per project by adding this to the project BRIEF.md"
    echo "         frontmatter:"
    echo "             voice:"
    echo "               style_guide: .anvil/voice/STYLE_GUIDE.md"
    echo "               vocabulary: .anvil/voice/VOCABULARY.md"
    echo "               values: .anvil/voice/VALUES.local.md   # private — resolves, never committed"
    echo "         An existing .anvil/voice/STYLE_GUIDE.md / VOCABULARY.md / VALUES.local.md is"
    echo "         never overwritten (per-file skip; a pre-#617 root-level doc is likewise"
    echo "         preserved and suppresses the new scaffold). See"
    echo "         anvil/templates/voice/README.md for the four-doc taxonomy."
    echo ""
    echo "         Starter word list scaffolded at .anvil/voice/VOCABULARY.words.txt (sibling"
    echo "         of .anvil/voice/VOCABULARY.md). 'python -m anvil.lib.vocab_reminder' resolves"
    echo "         it automatically; grow or replace the list with your own precision words."
    echo ""
    echo "         Private grounding (issues #577, #578): VALUES carries first-person stances"
    echo "         most authors do NOT want committed, so it scaffolds PRIVATE BY DEFAULT to a"
    echo "         gitignored VALUES.local.md (NOT a committed VALUES.md). The '*.local.md'"
    echo "         and '.voice/' patterns were added to your .gitignore, and anvil's git-sync"
    echo "         hook never commits them. A gitignored doc resolves identically to a"
    echo "         committed one."
    echo "         NOTE: this is not encryption and does not stop 'git add -f' — it keeps"
    echo "         the private source out of anvil's own commits, not out of every tool."
  fi
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
