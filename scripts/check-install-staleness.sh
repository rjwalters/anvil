#!/usr/bin/env bash
# check-install-staleness.sh - "Is this consumer's .anvil/ tree actually at the
# version its manifest claims?" (issue #1320)
#
# Why this exists: `install-anvil.sh` records the INSTALLER-RUN version in
# `.anvil/install-metadata.json`'s top-level `anvil_version`, and correctly
# declines to overwrite consumer-modified skill bodies (the documented `--force`
# skip). Those two facts together mean a single unqualified read of
# `anvil_version` can report a tree as current when most of its skill bodies are
# several releases behind — which is exactly what #1320 hit upgrading a consumer
# from 0.10.1 to 0.11.6 (467 files differed while the manifest read `0.11.6`).
#
# The correct per-skill data already exists: `skill_versions.<name>` (#633/#635)
# records the version of the run that last ACTUALLY installed each skill's body,
# and `skipped_overrides` names the skills a run declined to overwrite. Nothing
# consumed it at the two places a human or tool asks "am I current" — the
# end-of-install summary (fixed in `install-anvil.sh` Stage 11) and
# `/repo:update-tools`. This script is the read side for the second one.
#
# Deliberately zero-dependency: no jq, no python. The manifest parse reuses the
# same `tr`/`grep`/`sed` idiom as `install-anvil.sh`'s `read_recorded_version`,
# so this script works anywhere the installer itself does.
#
# STRICTLY READ-ONLY: it opens the manifest and writes nothing, anywhere.
#
# Usage:
#   check-install-staleness.sh [<target-repo>] [--json] [--quiet]
#
#   <target-repo>   repo root containing .anvil/ (default: cwd)
#   --json          machine-readable output instead of the human report
#   --quiet         suppress the report; use the exit code only
#
# Exit codes (mirroring check-changelog-entry.sh / check-surface-version-bump.sh):
#   0 = uniformly current: every installed skill's body is at `anvil_version`
#   1 = partial: one or more skills are frozen behind `anvil_version`
#   2 = could not evaluate (no manifest, unreadable, not an anvil install)
#
# Advisory by design: it reports, it never installs, forces, or mutates.
set -uo pipefail

usage() {
  cat >&2 <<'EOF'
usage: check-install-staleness.sh [<target-repo>] [--json] [--quiet]

exit: 0 = uniformly current, 1 = N skill(s) frozen behind, 2 = could not evaluate
EOF
}

TARGET="."
JSON=false
QUIET=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)     JSON=true; shift ;;
    --quiet|-q) QUIET=true; shift ;;
    -h|--help)  usage; exit 0 ;;
    -*)         echo "unknown option: $1" >&2; usage; exit 2 ;;
    *)          TARGET="$1"; shift ;;
  esac
done

MANIFEST="$TARGET/.anvil/install-metadata.json"
if [[ ! -f "$MANIFEST" ]]; then
  $QUIET || echo "could not evaluate: no anvil install manifest at $MANIFEST" >&2
  exit 2
fi

# Flatten newlines so every parse below is independent of one-line vs.
# pretty-printed JSON (a consumer or a tool may have reformatted the manifest).
FLAT="$(tr '\n' ' ' < "$MANIFEST")" || { echo "could not read $MANIFEST" >&2; exit 2; }

# Read a top-level string scalar (`anvil_version`, `commit`). Empty when absent.
read_scalar() {
  local key="$1"
  printf '%s' "$FLAT" \
    | grep -oE "\"$key\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
    | head -n1 \
    | sed -E "s/.*\"$key\"[[:space:]]*:[[:space:]]*\"([^\"]*)\".*/\1/" \
    || true
}

# Read a top-level JSON array of strings as whitespace-separated words. Empty
# when the key is absent (a pre-#152 manifest) or the array is `[]`.
read_string_array() {
  local key="$1" block
  block="$(printf '%s' "$FLAT" \
    | grep -oE "\"$key\"[[:space:]]*:[[:space:]]*\[[^]]*\]" \
    | head -n1)" || true
  [[ -n "$block" ]] || return 0
  printf '%s' "$block" \
    | tr ',' '\n' \
    | grep -oE '"[^"]+"' \
    | sed -E 's/^"(.*)"$/\1/' \
    | grep -v -x -e "$key" \
    || true
}

# Read `skill_versions.<skill>`. Empty for a pre-#633 manifest, or for a skill
# with no recorded entry — callers render that as "unknown", never as a guess.
read_skill_version() {
  local skill="$1" block
  block="$(printf '%s' "$FLAT" \
    | grep -oE '"skill_versions"[[:space:]]*:[[:space:]]*\{[^}]*\}' \
    | head -n1)" || true
  [[ -n "$block" ]] || return 0
  printf '%s' "$block" \
    | tr ',' '\n' \
    | grep -E "\"$skill\"[[:space:]]*:[[:space:]]*\"[0-9][^\"]*\"" \
    | head -n1 \
    | sed -E "s/.*\"$skill\"[[:space:]]*:[[:space:]]*\"([0-9][^\"]*)\".*/\1/" \
    || true
}

ANVIL_VERSION="$(read_scalar anvil_version)"
COMMIT="$(read_scalar commit)"
if [[ -z "$ANVIL_VERSION" ]]; then
  $QUIET || echo "could not evaluate: $MANIFEST has no anvil_version field" >&2
  exit 2
fi

SKIPPED=()
while IFS= read -r line; do
  [[ -n "$line" ]] && SKIPPED+=("$line")
done < <(read_string_array skipped_overrides)

INSTALLED=()
while IFS= read -r line; do
  [[ -n "$line" ]] && INSTALLED+=("$line")
done < <(read_string_array installed_skills)

SKIPPED_N=${#SKIPPED[@]}
TOTAL_N=$((${#INSTALLED[@]} + SKIPPED_N))

if $JSON; then
  printf '{\n'
  printf '  "manifest": "%s",\n' "$MANIFEST"
  printf '  "anvil_version": "%s",\n' "$ANVIL_VERSION"
  printf '  "commit": "%s",\n' "$COMMIT"
  printf '  "skill_count": %s,\n' "$TOTAL_N"
  printf '  "frozen_count": %s,\n' "$SKIPPED_N"
  printf '  "uniformly_current": %s,\n' "$([[ $SKIPPED_N -eq 0 ]] && echo true || echo false)"
  printf '  "frozen_skills": ['
  first=true
  for skill in ${SKIPPED[@]+"${SKIPPED[@]}"}; do
    $first && first=false || printf ','
    ver="$(read_skill_version "$skill")"
    printf '\n    {"skill": "%s", "frozen_at": "%s"}' "$skill" "${ver:-unknown}"
  done
  [[ $SKIPPED_N -gt 0 ]] && printf '\n  '
  printf ']\n}\n'
elif ! $QUIET; then
  if [[ $SKIPPED_N -eq 0 ]]; then
    echo "anvil $ANVIL_VERSION (commit ${COMMIT:-unknown}) — all $TOTAL_N installed skill(s) at $ANVIL_VERSION"
  else
    echo "anvil $ANVIL_VERSION (commit ${COMMIT:-unknown}) — NOT uniformly current:"
    echo "  $SKIPPED_N of $TOTAL_N installed skill(s) are frozen behind the recorded anvil_version."
    for skill in ${SKIPPED[@]+"${SKIPPED[@]}"}; do
      ver="$(read_skill_version "$skill")"
      printf '    %-24s frozen at %s\n' "$skill" "${ver:-unknown}"
    done
    echo "  Those bodies were preserved because they are consumer-modified (the documented"
    echo "  install-anvil.sh skip). Re-run the installer with --force to overwrite them."
  fi
fi

[[ $SKIPPED_N -eq 0 ]] && exit 0
exit 1
