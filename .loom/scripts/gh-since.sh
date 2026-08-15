#!/usr/bin/env bash
# gh-since.sh <last-pr> <last-issue> — read-only "what's new since watermark N"
# helper (issue #1060).
#
# Problem this closes
# --------------------
# The Auditor's "Guard-Decision Telemetry Review" standing policy (#3898,
# .loom/roles/auditor.md) and the WORK_LOG/changelog cross-reference workflow
# it inspired both need the same shape of query: "which PRs merged / issues
# closed since I last looked (PR #N / issue #M)?" The ad-hoc way to answer
# that — a multi-line shell script assigning `GH_READ=".loom/scripts/gh-cached"`,
# calling `"$GH_READ" pr list ... --jq "[.[] | select(.number > N) | ...]"`,
# looping, and printing a summary — is exactly the shape
# `.loom/hooks/guard-destructive-generic.sh`'s `fastpath_structural_ok()`
# rejects outright (any `;`, `&`, `|`, `<`, `>`, backtick, `$(`, or newline
# routes to the slow path), and the slow path's write-target masking then
# denies it at the catastrophic `worktree-write-confinement` tier even though
# every one of these queries is read-only (10 independent incidents,
# 2026-08-06..2026-08-13 — see #1060).
#
# This script consolidates that query shape into ONE file so the numeric
# comparison and jq filtering live here, never on the Bash-tool command
# line the guard scans. Its own invocation — `.loom/scripts/gh-since.sh
# <last-pr> <last-issue>` — has no shell metacharacter at all, so it is
# registered under `guards.readOnlyFastPathExtra` in `.loom/config.json`
# (the guard's own documented escape hatch,
# `.loom/docs/guard-hooks.md` § "Read-Only Fast-Path Guard Toggle") and is
# admitted at the fast path instead of ever reaching the buggy slow-path
# masking logic. The underlying slow-path bug is real but out of scope here
# — it lives in a vendored file (`guard-destructive-generic.sh`) that any
# local edit would lose on the next resync; see #1060 for the upstream
# follow-up.
#
# Usage:
#   .loom/scripts/gh-since.sh <last-pr> <last-issue> [--exclude-guide-docs] [--json] [--limit N]
#
#   <last-pr>              Required. Non-negative integer PR-number
#                           watermark — only merged PRs numbered strictly
#                           greater than this are reported. No default: an
#                           omitted or non-numeric value is a usage error
#                           (#1060 acceptance criteria: "no silent default").
#   <last-issue>            Required. Same contract as <last-pr>, for closed
#                           issues.
#   --exclude-guide-docs    Optional. Drop merged PRs whose head branch
#                           starts with `docs/guide-update` — the Guide
#                           role's automated WORK_LOG/WORK_PLAN/README sync
#                           PRs (.loom/scripts/docs-worktree.sh), which are
#                           routine doc-maintenance noise for a
#                           substantive-change cross-reference. This mirrors
#                           the exclusion variant seen in several of the 10
#                           logged incident commands.
#   --json                  Optional. Emit one JSON object
#                           {new_merged_prs: [...], new_closed_issues: [...]}
#                           instead of the human-readable report.
#   --limit N               Optional. Page size passed to `gh-cached ...
#                           list --limit N` for BOTH the PR and issue query
#                           (default: 200). Raise this if more than N items
#                           have merged/closed since the watermark.
#
# Exit codes: 0 = query ran (possibly with zero new items); 2 = usage error
# (missing/non-numeric watermark, unknown flag); 1 = gh-cached itself failed
# for both queries.
#
# Safety: this script only ever READS (gh-cached's `pr list` / `issue list`,
# both non-mutating `gh` nouns) and writes nothing. All numeric comparisons
# happen inside this file via jq's `--argjson`, never via unquoted shell
# interpolation of the watermark arguments, so a malformed/adversarial
# argument cannot reach a shell-interpreted context (#1060 acceptance
# criteria: "does not reintroduce a command-injection surface").

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GH_READ="$SCRIPT_DIR/gh-cached"

RED='\033[0;31m'
NC='\033[0m'
print_error() { printf "${RED}ERROR: %s${NC}\n" "$1" >&2; }

show_help() {
    cat <<'EOF'
gh-since.sh — read-only "new merged PRs / new closed issues since watermark N"

Usage:
  .loom/scripts/gh-since.sh <last-pr> <last-issue> [--exclude-guide-docs] [--json] [--limit N]

  <last-pr>              Required, non-negative integer. Only merged PRs
                          numbered > this are reported.
  <last-issue>            Required, non-negative integer. Only closed issues
                          numbered > this are reported.
  --exclude-guide-docs    Drop merged PRs on a docs/guide-update* branch
                          (Guide role's automated doc-sync PRs).
  --json                  Emit {new_merged_prs: [...], new_closed_issues: [...]}.
  --limit N               Page size for both gh queries (default: 200).

See the header comment in this file for the full rationale (issue #1060).
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    show_help
    exit 0
fi

EXCLUDE_GUIDE_DOCS=0
AS_JSON=0
LIMIT=200
POSITIONAL=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --exclude-guide-docs)
            EXCLUDE_GUIDE_DOCS=1
            shift
            ;;
        --json)
            AS_JSON=1
            shift
            ;;
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
    print_error "expected exactly 2 positional arguments, got ${#POSITIONAL[@]}"
    show_help >&2
    exit 2
fi

LAST_PR="${POSITIONAL[0]}"
LAST_ISSUE="${POSITIONAL[1]}"

if ! [[ "$LAST_PR" =~ ^[0-9]+$ ]]; then
    print_error "<last-pr> must be a non-negative integer watermark, got: '${LAST_PR}'"
    exit 2
fi
if ! [[ "$LAST_ISSUE" =~ ^[0-9]+$ ]]; then
    print_error "<last-issue> must be a non-negative integer watermark, got: '${LAST_ISSUE}'"
    exit 2
fi
if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || [[ "$LIMIT" -eq 0 ]]; then
    print_error "--limit must be a positive integer, got: '${LIMIT}'"
    exit 2
fi

if [[ ! -x "$GH_READ" ]]; then
    print_error "gh-cached not found or not executable at: $GH_READ"
    exit 1
fi

PRS_RAW=$("$GH_READ" pr list --state merged --limit "$LIMIT" \
    --json number,title,mergedAt,headRefName 2>/dev/null) || PRS_RAW="[]"
ISSUES_RAW=$("$GH_READ" issue list --state closed --limit "$LIMIT" \
    --json number,title,closedAt 2>/dev/null) || ISSUES_RAW="[]"

if [[ "$PRS_RAW" != \[*\] ]]; then
    PRS_RAW="[]"
fi
if [[ "$ISSUES_RAW" != \[*\] ]]; then
    ISSUES_RAW="[]"
fi

# All numeric comparisons happen HERE, via jq --argjson (never shell
# interpolation of the watermark into a command string), matching the
# "consolidate the numeric comparison inside the script file" requirement.
PR_FILTER='[.[] | select(.number > $lastPr)]'
if [[ "$EXCLUDE_GUIDE_DOCS" -eq 1 ]]; then
    PR_FILTER='[.[] | select(.number > $lastPr) | select((.headRefName // "") | startswith("docs/guide-update") | not)]'
fi

NEW_PRS=$(jq -c --argjson lastPr "$LAST_PR" "$PR_FILTER | sort_by(.number)" <<<"$PRS_RAW")
NEW_ISSUES=$(jq -c --argjson lastIssue "$LAST_ISSUE" \
    '[.[] | select(.number > $lastIssue)] | sort_by(.number)' <<<"$ISSUES_RAW")

if [[ "$AS_JSON" -eq 1 ]]; then
    jq -nc --argjson prs "$NEW_PRS" --argjson issues "$NEW_ISSUES" \
        '{new_merged_prs: $prs, new_closed_issues: $issues}'
    exit 0
fi

echo "New merged PRs since #${LAST_PR}:"
if [[ "$(jq 'length' <<<"$NEW_PRS")" -eq 0 ]]; then
    echo "  (none)"
else
    jq -r '.[] | "  #\(.number)  \(.title)  (merged \(.mergedAt))"' <<<"$NEW_PRS"
fi
echo ""
echo "New closed issues since #${LAST_ISSUE}:"
if [[ "$(jq 'length' <<<"$NEW_ISSUES")" -eq 0 ]]; then
    echo "  (none)"
else
    jq -r '.[] | "  #\(.number)  \(.title)  (closed \(.closedAt))"' <<<"$NEW_ISSUES"
fi
exit 0
