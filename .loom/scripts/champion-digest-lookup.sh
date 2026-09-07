#!/usr/bin/env bash
# champion-digest-lookup.sh <title> <marker> [--limit N] — resolve Champion's
# pinned "durable digest" tracking issue (e.g. the "Champion: Merge-Risk Hold
# Digest" issue, #6851/#7020) by title, preferring a marker-tagged body, with
# a title-only fallback that ADOPTS a pre-marker digest issue instead of
# orphaning it (issue #1304).
#
# Problem this closes
# --------------------
# `.claude/commands/loom/champion-pr-merge.md`'s Step 0 locates the digest
# issue with:
#
#   DIGEST_ISSUE=$("$GH_READ" issue list --search "\"$DIGEST_TITLE\" in:title" \
#     --state open --json number,body --limit 10 \
#     --jq "[.[] | select(.body | startswith(\"$DIGEST_MARKER\"))] | first | .number // empty")
#
# That `startswith($DIGEST_MARKER)` filter has no fallback: a digest issue
# created BEFORE the marker convention shipped (#6851/PR #6870) never
# starts with the marker and never will, so the lookup permanently misses
# it. Champion then creates a fresh digest issue instead of updating the
# existing one, and the original quietly stops being maintained — observed
# live in this repo: rjwalters/anvil#1211 (created 2026-08-24, pre-marker
# body) stopped updating on 2026-08-28, the same day rjwalters/anvil#1224
# (marker-prefixed body) was created as an unwanted duplicate. #1211 was
# closed as an orphaned duplicate in the curation pass that filed #1304.
#
# Constraint: `champion-pr-merge.md` is a VENDORED copy of an upstream Loom
# default, refreshed wholesale by `.loom/scripts/resync-installed.sh` — a
# direct edit to its Step 0 jq filter would not survive the next resync.
# The real fix belongs upstream (tracked at the issue named in
# CLAUDE.md's "Champion digest-issue lookup" section); this script is the
# same shape as `gh-since.sh` (#1060) and `check-changelog-entry.sh`
# (#1037): an anvil-owned script that moves the actual fix out of the
# vendored file, paired with a CLAUDE.md-owned instruction that redirects
# Champion's Step 0 to call it instead of running the inline jq filter
# itself.
#
# Resolution order:
#   1. Among OPEN issues whose title matches <title> exactly (forge
#      full-text search, same as the vendored snippet), prefer the one
#      whose body starts with <marker> (the current convention). If more
#      than one open issue matches the title and exactly one carries the
#      marker, the marker-tagged issue always wins — never the newest or
#      oldest by number.
#   2. If no title match carries the marker, fall back to the OLDEST
#      (lowest-numbered) open title match. This "adopts" a pre-marker
#      digest issue rather than orphaning it: Champion's very next write
#      (`gh issue edit --body "$DIGEST_BODY"`, champion-pr-merge.md Step 2)
#      always writes a marker-prefixed body, so the adopted issue is
#      migrated in place on the same pass that finds it — no separate
#      migration step is needed here.
#   3. No title match at all -> prints nothing (empty), exit 0 — the
#      caller's existing "create a new digest issue" branch already handles
#      this case unchanged.
#
# Usage:
#   .loom/scripts/champion-digest-lookup.sh "<digest title>" "<marker>" [--limit N]
#
#   <title>   Required. Exact digest issue title, e.g.
#             "Champion: Merge-Risk Hold Digest".
#   <marker>  Required. Leading-HTML-comment marker the current convention
#             stamps at the start of the digest body, e.g.
#             "<!-- champion:merge-risk-hold-digest -->".
#   --limit N Optional. Page size passed to the underlying `issue list`
#             search (default: 10, matching the vendored snippet).
#
# Environment:
#   GH_READ_BIN   Override the `gh`-compatible binary invoked for the issue
#                 list query (default: the sibling `gh-cached` in this
#                 directory). Tests use this to stub a canned response
#                 without a live forge call.
#
# Exit codes: 0 = query ran (possibly with no match, i.e. empty stdout);
# 2 = usage error; 1 = the underlying read command itself failed.
#
# Safety: read-only. This script never mutates an issue — it only prints
# the resolved issue number (or nothing) to stdout for the caller to act on,
# exactly like the inline jq filter it replaces.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GH_READ="${GH_READ_BIN:-$SCRIPT_DIR/gh-cached}"

RED='\033[0;31m'
NC='\033[0m'
print_error() { printf "${RED}ERROR: %s${NC}\n" "$1" >&2; }

show_help() {
    cat <<'EOF'
champion-digest-lookup.sh — resolve Champion's pinned digest issue by title,
preferring a marker-tagged body, with a title-only fallback that adopts a
pre-marker digest issue instead of orphaning it (issue #1304).

Usage:
  .loom/scripts/champion-digest-lookup.sh "<title>" "<marker>" [--limit N]

Prints the resolved issue number to stdout (empty if no title match at all).
See the header comment in this file for the full rationale (issue #1304).
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    show_help
    exit 0
fi

LIMIT=10
POSITIONAL=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --limit)
            LIMIT="${2:-}"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        --*)
            print_error "unknown option: $1"
            show_help >&2
            exit 2
            ;;
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac
done

if [[ ${#POSITIONAL[@]} -ne 2 ]]; then
    print_error "expected exactly 2 positional arguments (<title> <marker>), got ${#POSITIONAL[@]}"
    show_help >&2
    exit 2
fi

TITLE="${POSITIONAL[0]}"
MARKER="${POSITIONAL[1]}"

if [[ -z "$TITLE" ]]; then
    print_error "<title> must not be empty"
    exit 2
fi
if [[ -z "$MARKER" ]]; then
    print_error "<marker> must not be empty"
    exit 2
fi
if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || [[ "$LIMIT" -eq 0 ]]; then
    print_error "--limit must be a positive integer, got: '${LIMIT}'"
    exit 2
fi

if [[ ! -x "$GH_READ" ]]; then
    print_error "read binary not found or not executable at: $GH_READ"
    exit 1
fi

RAW=$("$GH_READ" issue list --search "\"$TITLE\" in:title" \
    --state open --json number,body --limit "$LIMIT" 2>/dev/null) || RAW="[]"

if [[ "$RAW" != \[*\] ]]; then
    RAW="[]"
fi

# All matching/sorting happens HERE via jq --arg (never shell interpolation
# of the title/marker into a second command string), mirroring gh-since.sh's
# "consolidate the comparison inside the script file" contract (#1060).
MARKER_MATCH=$(jq -r --arg m "$MARKER" \
    '[.[] | select((.body // "") | startswith($m))] | sort_by(.number) | (.[0].number // empty)' \
    <<<"$RAW")

if [[ -n "$MARKER_MATCH" ]]; then
    echo "$MARKER_MATCH"
    exit 0
fi

# No open title match carries the marker. Adopt the oldest (lowest-numbered)
# title match instead of orphaning it — the caller's own next write always
# stamps the marker on this issue's body (champion-pr-merge.md Step 2),
# which is the migration.
TITLE_MATCH=$(jq -r '[.[]] | sort_by(.number) | (.[0].number // empty)' <<<"$RAW")
echo "$TITLE_MATCH"
exit 0
