#!/usr/bin/env bash
# version.sh - Manage version across all Anvil files
#
# Usage:
#   ./scripts/version.sh                    # Show current version
#   ./scripts/version.sh list               # List version-bearing files (one per line)
#   ./scripts/version.sh check              # Verify all files are in sync
#   ./scripts/version.sh set 0.1.0          # Set explicit version
#   ./scripts/version.sh set 0.1.0 --tag    # Set version, commit, and tag
#   ./scripts/version.sh bump patch         # Bump patch (0.1.0 -> 0.1.1)
#   ./scripts/version.sh bump minor --tag   # Bump minor + commit + tag
#   ./scripts/version.sh bump major --tag   # Bump major + commit + tag
#
# Currently covers CLAUDE.md and pyproject.toml. To extend when a new
# version-bearing file lands, add it to VERSION_FILES below and add matching
# case-arms to both get_version_from_file() and set_version().
#
# The list / check / bump <level> --tag interface conforms to the upstream
# Loom v0.10.4 release.md scripts/version.sh contract (#590).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

VERSION_FILES=(
  "CLAUDE.md"
  "pyproject.toml"
)

get_version() {
  get_version_from_file "CLAUDE.md"
}

get_version_from_file() {
  local file="$1"
  case "$file" in
    CLAUDE.md)
      grep -o 'Anvil Version\*\*: [0-9]*\.[0-9]*\.[0-9]*' "$REPO_ROOT/$file" \
        | grep -o '[0-9]*\.[0-9]*\.[0-9]*'
      ;;
    pyproject.toml)
      # Anchored on ^...$ so only the top-level [project] version line matches;
      # immune to a future nested-table `version = "..."` string elsewhere in
      # the file (e.g. a `[tool.foo]` block).
      grep -E '^version = "[0-9]+\.[0-9]+\.[0-9]+"$' "$REPO_ROOT/$file" \
        | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
      ;;
    *)
      echo "unknown file: $file" >&2
      return 1
      ;;
  esac
}

check_versions() {
  local expected
  expected=$(get_version)
  local all_match=true
  for file in "${VERSION_FILES[@]}"; do
    local actual
    actual=$(get_version_from_file "$file")
    if [[ "$actual" == "$expected" ]]; then
      printf "  %-40s %s\n" "$file" "$actual"
    else
      printf "  %-40s %s (expected %s)\n" "$file" "$actual" "$expected" >&2
      all_match=false
    fi
  done
  if [[ "$all_match" == "true" ]]; then
    echo "All version files in sync at $expected"
  else
    echo "Version drift detected" >&2
    exit 1
  fi
}

set_version() {
  local new="$1"
  if [[ ! "$new" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "error: version must be X.Y.Z, got '$new'" >&2
    exit 2
  fi
  for file in "${VERSION_FILES[@]}"; do
    case "$file" in
      CLAUDE.md)
        sed -i.bak "s/Anvil Version\*\*: [0-9]*\.[0-9]*\.[0-9]*/Anvil Version**: $new/" "$REPO_ROOT/$file"
        rm "$REPO_ROOT/$file.bak"
        ;;
      pyproject.toml)
        # Anchored on ^...$ — only the top-level [project] version line
        # gets rewritten; any future nested-table `version = "..."` is left
        # alone. Mirrors the regex in get_version_from_file() above.
        sed -i.bak -E 's/^version = "[0-9]+\.[0-9]+\.[0-9]+"$/version = "'"$new"'"/' "$REPO_ROOT/$file"
        rm "$REPO_ROOT/$file.bak"
        ;;
    esac
  done
  echo "Set version to $new"
}

bump_version() {
  local level="$1"
  case "$level" in
    patch|minor|major) ;;
    *)
      echo "error: bump level must be patch, minor, or major (got '$level')" >&2
      exit 2
      ;;
  esac
  local current maj min pat
  current=$(get_version)
  IFS=. read -r maj min pat <<<"$current"
  case "$level" in
    patch) pat=$((pat + 1)) ;;
    minor) min=$((min + 1)); pat=0 ;;
    major) maj=$((maj + 1)); min=0; pat=0 ;;
  esac
  echo "${maj}.${min}.${pat}"
}

usage() {
  sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

case "${1:-show}" in
  show|"")
    get_version
    ;;
  list)
    printf '%s\n' "${VERSION_FILES[@]}"
    ;;
  check)
    check_versions
    ;;
  set)
    new="${2:?usage: set X.Y.Z [--tag]}"
    set_version "$new"
    if [[ "${3:-}" == "--tag" ]]; then
      cd "$REPO_ROOT"
      git add "${VERSION_FILES[@]}"
      git commit -m "chore: bump version to $new"
      git tag "v$new"
      echo "Committed and tagged v$new"
    fi
    ;;
  bump)
    level="${2:?usage: bump <patch|minor|major> [--tag]}"
    new=$(bump_version "$level")
    set_version "$new"
    if [[ "${3:-}" == "--tag" ]]; then
      cd "$REPO_ROOT"
      git add "${VERSION_FILES[@]}"
      git commit -m "chore: release v$new"
      git tag "v$new"
      echo "Committed and tagged v$new"
    fi
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "unknown command: $1" >&2
    usage
    ;;
esac
