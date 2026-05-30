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
#   -y, --yes         Non-interactive (skip confirmation prompts)
#   -h, --help        Show this help and exit
#
# Examples:
#   ./scripts/install-anvil.sh /tmp/test-repo
#   ./scripts/install-anvil.sh --skills=memo /tmp/test-repo
#   ./scripts/install-anvil.sh --dry-run --skills=memo /tmp/test-repo
#   ./scripts/install-anvil.sh --force /tmp/test-repo
#
# Layout produced in <target-repo>:
#   .anvil/lib/                        Framework code (always installed)
#   .anvil/roles/                      Generic role definitions (always installed)
#   .anvil/skills/<name>/              Canonical skill bodies (consumer override target)
#   .anvil/CLAUDE.md                   Full Anvil guide
#   .anvil/install-metadata.json       Manifest (version, skills, overrides)
#   .claude/skills/anvil/<name>/SKILL.md  Thin Claude registration shim
#   CLAUDE.md                          Updated with additive <!-- BEGIN ANVIL --> block
#
# Anvil is forge-optional: git is not required in the target.
# Coexists with Loom: CLAUDE.md merges are additive and marker-bounded.
#
# v0 distribution model: installs from a local checkout (this script's parent dir).
# A future "fetch from release" branch can be added when Anvil ships via package
# managers; out of scope for the v0 implementation.

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
  sed -n '2,35p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

# ----- CLAUDE.md marker constants -------------------------------------------
ANVIL_MARK_BEGIN='<!-- BEGIN ANVIL -->'
ANVIL_MARK_END='<!-- END ANVIL -->'
ANVIL_POINTER='This repository uses [Anvil](https://github.com/rjwalters/anvil) for AI-powered artifact creation. See `.anvil/CLAUDE.md` for the full guide (skills, rubric, state machine).'

# ----- Argument parsing ------------------------------------------------------
SKILLS_FILTER=""
FORCE=false
DRY_RUN=false
CHECK_DEPS_ONLY=false
NON_INTERACTIVE=false
TARGET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skills=*) SKILLS_FILTER="${1#--skills=}"; shift ;;
    --skills)   shift; SKILLS_FILTER="${1:-}"; [[ -z "$SKILLS_FILTER" ]] && error "--skills requires a comma-separated list"; shift ;;
    --force)    FORCE=true; shift ;;
    --dry-run)  DRY_RUN=true; shift ;;
    --check-deps) CHECK_DEPS_ONLY=true; shift ;;
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
write_manifest() {
  local target_dir="$1" manifest_path="$2"
  local anvil_version="$3" anvil_source="$4" install_date="$5"
  local installed_json="$6" skipped_json="$7"
  mkdir -p "$target_dir/.anvil"
  cat > "$manifest_path" <<MANIFEST_EOF
{
  "anvil_version": "$anvil_version",
  "anvil_source": "$anvil_source",
  "install_date": "$install_date",
  "installed_skills": $installed_json,
  "skipped_overrides": $skipped_json
}
MANIFEST_EOF
}

# Track override decisions for the manifest.
SKIPPED_OVERRIDES=()
INSTALLED_SKILLS=()

# ----- Stage 5: copy framework code (lib) -----------------------------------
info "Stage 5: copy framework code (anvil/lib -> .anvil/lib)"
SRC_LIB="$ANVIL_ROOT/anvil/lib"
DST_LIB="$TARGET/.anvil/lib"
if [[ -d "$SRC_LIB" ]]; then
  # Copy contents (cp -R src/. dest preserves contents, not the wrapper dir).
  do_action "install $DST_LIB from $SRC_LIB" copy_tree "$SRC_LIB" "$DST_LIB"
  # Suppress post-action confirmation under --dry-run; the [dry-run] line above
  # is the truthful record (issue #81). Stage 1-4/10 diagnostic ok: lines stay.
  [[ "$DRY_RUN" == true ]] || ok "framework lib installed"
else
  warn "source lib not found: $SRC_LIB (skipping)"
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
info "Stage 7: copy selected skills"
for skill in "${SELECTED_SKILLS[@]}"; do
  src_skill="$ANVIL_ROOT/anvil/skills/$skill"
  dst_skill="$TARGET/.anvil/skills/$skill"
  shim_dir="$TARGET/.claude/skills/anvil/$skill"
  shim_file="$shim_dir/SKILL.md"

  # Override detection: if destination exists and differs from source by any
  # byte, treat as consumer-modified. Skip unless --force.
  if [[ -d "$dst_skill" ]]; then
    if dirs_identical "$src_skill" "$dst_skill"; then
      note "skill '$skill' already installed and unchanged (refreshing safely)"
    else
      if [[ "$FORCE" == true ]]; then
        warn "overwriting consumer-modified file(s) in .anvil/skills/$skill (--force)"
      else
        warn "skipped: consumer-modified .anvil/skills/$skill (re-run with --force to overwrite)"
        SKIPPED_OVERRIDES+=("$skill")
        # Still ensure the Claude shim exists and points at the canonical path,
        # since that file is a pointer and safe to regenerate.
        do_action "regenerate Claude registration shim at .claude/skills/anvil/$skill/SKILL.md" \
          write_shim "$skill" "$shim_dir" "$shim_file"
        continue
      fi
    fi
  fi

  # Copy (or recopy): wipe destination and replace with source contents.
  do_action "install .anvil/skills/$skill from source" \
    replace_tree "$src_skill" "$dst_skill"

  # Always regenerate the thin Claude registration shim.
  do_action "write Claude registration shim at .claude/skills/anvil/$skill/SKILL.md" \
    write_shim "$skill" "$shim_dir" "$shim_file"

  INSTALLED_SKILLS+=("$skill")
  # Suppress post-action confirmation under --dry-run (issue #81). The
  # INSTALLED_SKILLS array is still populated so the Stage 11 summary can
  # accurately report what a real run WOULD install (relabel branch below).
  [[ "$DRY_RUN" == true ]] || ok "skill '$skill' installed"
done

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

# ----- Stage 9: install manifest --------------------------------------------
info "Stage 9: write install manifest"
MANIFEST="$TARGET/.anvil/install-metadata.json"

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

INSTALLED_JSON="$(json_array_from_list ${INSTALLED_SKILLS[@]+"${INSTALLED_SKILLS[@]}"})"
SKIPPED_JSON="$(json_array_from_list ${SKIPPED_OVERRIDES[@]+"${SKIPPED_OVERRIDES[@]}"})"

do_action "write $MANIFEST" \
  write_manifest "$TARGET" "$MANIFEST" "$ANVIL_VERSION" "$ANVIL_ROOT" "$INSTALL_DATE" \
                 "$INSTALLED_JSON" "$SKIPPED_JSON"

# ----- Stage 10: renderer dependency check ----------------------------------
# Report which renderer binaries are present so a fresh install does not claim
# unqualified success while a core renderer (esp. mmdc) is absent. Scope: this
# is the dependency-CHECK addition owned by #65; the path-injection/dry-run
# items are #21's surface and are untouched here.
info "Stage 10: renderer dependency check"
DEPS_MISSING=0
check_renderer_deps || DEPS_MISSING=$?

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
if [[ "$DRY_RUN" == true ]]; then
  warn "DRY-RUN: no files were written"
else
  ok "Anvil v$ANVIL_VERSION installed into $TARGET"
  if [[ "$DEPS_MISSING" -gt 0 ]]; then
    warn "install complete, but $DEPS_MISSING renderer dependenc$([[ "$DEPS_MISSING" -eq 1 ]] && echo y || echo ies) missing (see above) -- deck/slides rendering will be impaired until installed"
  fi
fi
