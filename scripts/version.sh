#!/usr/bin/env bash
# version.sh - Manage version across all Anvil files
#
# Usage:
#   ./scripts/version.sh                    # Show current version
#   ./scripts/version.sh check              # Verify all files are in sync
#   ./scripts/version.sh set 0.1.0          # Set explicit version
#   ./scripts/version.sh set 0.1.0 --tag    # Set version, commit, and tag
#
# As the project grows beyond CLAUDE.md (e.g. pyproject.toml when lib/ lands),
# add the new files to VERSION_FILES below and extend get_version_from_file().
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

VERSION_FILES=(
  "CLAUDE.md"
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
    esac
  done
  echo "Set version to $new"
}

usage() {
  sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

case "${1:-show}" in
  show|"")
    get_version
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
  -h|--help|help)
    usage
    ;;
  *)
    echo "unknown command: $1" >&2
    usage
    ;;
esac
