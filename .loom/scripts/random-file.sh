#!/usr/bin/env bash
#
# random-file.sh - Get a random file from the workspace
#
# This script provides standalone random file selection for use without the MCP server.
# It respects .gitignore and supports include/exclude patterns.
#
# Usage:
#   ./random-file.sh                                    # Random file from workspace
#   ./random-file.sh --include "src/**/*.ts"            # Only TypeScript files in src/
#   ./random-file.sh --exclude "**/*.test.ts"           # Exclude test files
#   ./random-file.sh --include "src/**/*.ts" --exclude "**/*.test.ts"
#
# Options:
#   --include PATTERN   Glob pattern to include (can be used multiple times)
#   --exclude PATTERN   Glob pattern to exclude (can be used multiple times)
#   --help              Show this help message
#   --debug             Show debug output
#
# Examples:
#   ./random-file.sh --include "src/**/*.ts" --include "src/**/*.tsx"
#   ./random-file.sh --exclude "**/*.test.ts" --exclude "**/*.spec.ts"
#   ./random-file.sh --include "defaults/roles/*.md"
#

set -eo pipefail

# Get script directory and workspace root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Configuration
DEBUG="${DEBUG:-false}"
INCLUDE_PATTERNS=()
EXCLUDE_PATTERNS=()

# Default exclude patterns (match MCP implementation)
DEFAULT_EXCLUDES=(
    "node_modules"
    ".git"
    "dist"
    "build"
    "target"
    ".loom/worktrees"
    "*.log"
    "package-lock.json"
    "pnpm-lock.yaml"
    "yarn.lock"
    "Cargo.lock"
)

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --include)
                if [[ -z "${2:-}" ]]; then
                    echo "Error: --include requires a pattern argument" >&2
                    exit 1
                fi
                INCLUDE_PATTERNS+=("$2")
                shift 2
                ;;
            --exclude)
                if [[ -z "${2:-}" ]]; then
                    echo "Error: --exclude requires a pattern argument" >&2
                    exit 1
                fi
                EXCLUDE_PATTERNS+=("$2")
                shift 2
                ;;
            --debug)
                DEBUG=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo "Error: Unknown option: $1" >&2
                show_help >&2
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << 'EOF'
random-file.sh - Get a random file from the workspace

Usage:
  ./random-file.sh [OPTIONS]

Options:
  --include PATTERN   Glob pattern to include (can be used multiple times)
  --exclude PATTERN   Glob pattern to exclude (can be used multiple times)
  --debug             Show debug output
  --help              Show this help message

Examples:
  ./random-file.sh                                    # Random file from workspace
  ./random-file.sh --include "src/**/*.ts"            # Only TypeScript files in src/
  ./random-file.sh --exclude "**/*.test.ts"           # Exclude test files
  ./random-file.sh --include "src/**/*.ts" --exclude "**/*.test.ts"

Default exclusions:
  - node_modules/, .git/, dist/, build/, target/
  - .loom/worktrees/
  - *.log, package-lock.json, pnpm-lock.yaml, yarn.lock, Cargo.lock
  - Files matching .gitignore patterns

The script always respects .gitignore if present in the workspace root.
EOF
}

debug() {
    if [[ "$DEBUG" == "true" ]]; then
        echo "[DEBUG] $*" >&2
    fi
}

# Get list of files matching criteria
get_matching_files() {
    cd "$WORKSPACE_ROOT"

    # Use fd if available (faster), otherwise fall back to `git ls-files`
    # (or plain find outside a git repo)
    if command -v fd &>/dev/null; then
        get_files_with_fd
    else
        get_files_with_find
    fi
}

# Use fd for fast file finding (if available). fd honors .gitignore
# natively when --no-ignore-vcs is NOT passed, so no manual gitignore
# post-filtering is needed here.
get_files_with_fd() {
    local fd_args=("--type" "f" "--hidden")

    # Add include patterns
    if [[ ${#INCLUDE_PATTERNS[@]} -gt 0 ]]; then
        # For fd, we need to use -e for extensions or -g for globs
        for pattern in "${INCLUDE_PATTERNS[@]}"; do
            fd_args+=("-g" "$pattern")
        done
    fi

    # Add exclude patterns
    for pattern in "${DEFAULT_EXCLUDES[@]}"; do
        fd_args+=("-E" "$pattern")
    done

    for pattern in "${EXCLUDE_PATTERNS[@]}"; do
        fd_args+=("-E" "$pattern")
    done

    debug "Running: fd ${fd_args[*]}"

    fd "${fd_args[@]}" . 2>/dev/null
}

# Fallback file listing when fd is unavailable.
#
# Uses `git ls-files --cached --others --exclude-standard`, which respects
# .gitignore, .git/info/exclude, and core.excludesFile natively (git's own
# ignore-matching, not a hand-rolled gitignore-pattern-to-regex conversion),
# when the workspace is a git repo; falls back to plain `find` otherwise.
# DEFAULT_EXCLUDES / --exclude / --include are then applied with bash's
# native glob matching (see path_excluded() / filter_by_include()) -- no
# regex conversion, no eval.
get_files_with_find() {
    local files

    if git -C "$WORKSPACE_ROOT" rev-parse --is-inside-work-tree &>/dev/null; then
        debug "Listing files via: git ls-files --cached --others --exclude-standard"
        files=$(git -C "$WORKSPACE_ROOT" ls-files --cached --others --exclude-standard -- . 2>/dev/null)
    else
        debug "Not a git repo; listing files via: find . -type f"
        files=$(find . -type f 2>/dev/null | sed 's|^\./||')
    fi

    if [[ ${#INCLUDE_PATTERNS[@]} -gt 0 ]]; then
        files=$(printf '%s\n' "$files" | filter_by_include)
    fi

    printf '%s\n' "$files" | apply_exclusions
}

# Keep only lines matching at least one --include pattern. Uses bash's
# native `[[ path == pattern ]]` glob matching, where "*" matches any run
# of characters including "/" (so "**" behaves the same as a single "*").
filter_by_include() {
    local path pattern matched
    while IFS= read -r path; do
        [[ -z "$path" ]] && continue
        matched=false
        for pattern in "${INCLUDE_PATTERNS[@]}"; do
            # shellcheck disable=SC2053
            if [[ "$path" == $pattern ]]; then
                matched=true
                break
            fi
        done
        [[ "$matched" == true ]] && printf '%s\n' "$path"
    done
    # Always succeed: under `set -eo pipefail`, letting this function's exit
    # status depend on whether the LAST input line happened to match would
    # abort the enclosing subshell (the left side of `get_matching_files |
    # pick_random` in main()) whenever the last candidate path didn't match,
    # silently truncating output before apply_exclusions ever runs.
    return 0
}

# Drop lines matching any DEFAULT_EXCLUDES or --exclude pattern.
apply_exclusions() {
    local path
    while IFS= read -r path; do
        [[ -z "$path" ]] && continue
        path_excluded "$path" || printf '%s\n' "$path"
    done
    # See the comment in filter_by_include() above -- same reasoning applies.
    return 0
}

# True (exit 0) if $1 matches any exclude pattern (DEFAULT_EXCLUDES plus
# --exclude), false (exit 1) otherwise.
#
# A pattern matches a path if the path equals the pattern, ends with
# "/<pattern>", starts with "<pattern>/", or contains "/<pattern>/" (all as
# bash glob comparisons, so wildcards in the pattern still work). This one
# set of checks handles "extension/filename" patterns (e.g. "*.log",
# "package-lock.json", matched as a suffix anywhere) and "directory name"
# patterns (e.g. "node_modules", ".git", ".loom/worktrees", matched as a
# path segment anywhere) uniformly -- there is no separate branch keyed on
# whether the pattern contains a literal "." (the root cause of the
# previous bug, which misrouted dotted directory patterns like ".git" and
# ".loom/worktrees" into the wrong branch).
path_excluded() {
    local path="$1" pattern
    for pattern in "${DEFAULT_EXCLUDES[@]}" "${EXCLUDE_PATTERNS[@]}"; do
        # shellcheck disable=SC2053
        if [[ "$path" == $pattern || "$path" == */$pattern || "$path" == $pattern/* || "$path" == */$pattern/* ]]; then
            return 0
        fi
    done
    return 1
}

# Pick a random file from the list
pick_random() {
    local files=()
    while IFS= read -r line; do
        [[ -n "$line" ]] && files+=("$line")
    done

    if [[ ${#files[@]} -eq 0 ]]; then
        echo "No files found matching the criteria" >&2
        exit 1
    fi

    debug "Found ${#files[@]} matching files"

    # Pick random index
    local index=$((RANDOM % ${#files[@]}))
    local selected="${files[$index]}"

    # Return absolute path
    echo "$WORKSPACE_ROOT/$selected"
}

# Main
main() {
    parse_args "$@"

    debug "Workspace: $WORKSPACE_ROOT"
    debug "Include patterns: ${INCLUDE_PATTERNS[*]:-<all>}"
    debug "Exclude patterns: ${EXCLUDE_PATTERNS[*]:-<none>}"

    get_matching_files | pick_random
}

main "$@"
