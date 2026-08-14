#!/usr/bin/env bash
# check-changelog-entry.sh - Deterministic pre-flight: does a changelog-worthy PR
# actually carry a CHANGELOG.md entry? (issue #1037)
#
# Why this exists: at the v0.11.0 cut, `/repo:release`'s merged-work coverage
# check found `[Unreleased]` covered ~28 items while the cycle had merged ~50
# more feat/fix/security PRs with no entry at all — including two whole new
# skills (`anvil:ip-search` #969, `anvil:diff` #931). All were reconstructed by
# hand at release time, which is exactly the expensive archaeology a changelog
# convention exists to prevent. The convention was real but unenforced: nothing
# in the Builder/Judge cycle ever looked.
#
# This is the cheap mechanical gate that runs BEFORE the expensive content
# review (`CLAUDE.md` § "Pattern overview" — "Deterministic pre-flight before
# judgment"). It answers one question and renders no quality verdict.
#
# Contract (`CLAUDE.md` § "Changelog discipline"):
#   - A PR whose title is a `feat`/`fix`/`security` conventional commit is
#     changelog-worthy; every other type (docs, chore, test, refactor, ci,
#     build, style, perf) is exempt.
#   - A changelog-worthy PR must either touch `CHANGELOG.md` or carry an
#     explicit `CHANGELOG: no — <reason>` line in its body.
#   - `CHANGELOG: yes` with no `CHANGELOG.md` in the diff is a contradiction
#     (the false-`yes` case, mirroring a false `TDD: yes`), and is the loudest
#     failure this script reports.
#
# Usage:
#   check-changelog-entry.sh <pr-number> [repo]      # live mode (needs gh)
#   check-changelog-entry.sh --title <t> \
#       --body-file <f> --files-file <f>             # offline mode (tests, hooks)
#
# Exit codes (following .loom/scripts/require-complexity-marker.sh):
#   0 = has an entry, or a valid exemption
#   1 = missing entry (or a contradicted `CHANGELOG: yes` claim)
#   2 = could not evaluate (bad args, no gh, fetch failure)
#
# Advisory by design: this reports, it does not mutate labels or block merges.
set -uo pipefail

usage() {
  cat >&2 <<'EOF'
usage:
  check-changelog-entry.sh <pr-number> [repo]
  check-changelog-entry.sh --title <title> [--body-file <path>] --files-file <path>

exit: 0 = entry present or exempt, 1 = missing/contradicted, 2 = could not evaluate
EOF
}

TITLE=""
BODY=""
FILES=""
PR=""
REPO=""
MODE="live"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)      TITLE="${2:-}"; MODE="offline"; shift 2 || { usage; exit 2; } ;;
    --body-file)  [[ -f "${2:-}" ]] || { echo "no such body file: ${2:-}" >&2; exit 2; }
                  BODY="$(cat "$2")"; MODE="offline"; shift 2 ;;
    --files-file) [[ -f "${2:-}" ]] || { echo "no such files file: ${2:-}" >&2; exit 2; }
                  FILES="$(cat "$2")"; MODE="offline"; shift 2 ;;
    -h|--help)    usage; exit 0 ;;
    -*)           echo "unknown flag: $1" >&2; usage; exit 2 ;;
    *)            if [[ -z "$PR" ]]; then PR="$1"; else REPO="$1"; fi; shift ;;
  esac
done

if [[ "$MODE" == "live" ]]; then
  [[ -n "$PR" ]] || { usage; exit 2; }
  command -v gh >/dev/null 2>&1 || { echo "COULD NOT CHECK: gh not on PATH" >&2; exit 2; }

  # Resolve the repo explicitly. A bare `gh pr view` targets the default remote,
  # which is wrong wherever `origin` is not where the PRs live (a fork checkout,
  # most obviously) — it would report on a same-numbered PR elsewhere.
  REPO="${REPO:-${LOOM_REPO:-}}"
  if [[ -z "$REPO" ]]; then
    REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
  fi
  [[ -n "$REPO" ]] || { echo "COULD NOT CHECK: could not determine repo; pass it explicitly or set LOOM_REPO" >&2; exit 2; }

  # One API call; title and body separated by a sentinel line. `gh -q` is jq, so
  # this adds no standalone jq dependency. `.body // ""` keeps a bodyless PR
  # from stringifying to the literal "null".
  SEP="---anvil-changelog-check-sep---"
  if ! meta="$(gh pr view "$PR" -R "$REPO" --json title,body -q ".title + \"\n${SEP}\n\" + (.body // \"\")" 2>/dev/null)"; then
    echo "COULD NOT CHECK: could not fetch PR $REPO#$PR (API failure or quota exhaustion). Retry; this is not a changelog defect." >&2
    exit 2
  fi
  TITLE="$(printf '%s\n' "$meta" | sed -n "1,/^${SEP}\$/p" | sed "/^${SEP}\$/d")"
  BODY="$(printf '%s\n' "$meta" | sed -n "/^${SEP}\$/,\$p" | sed "/^${SEP}\$/d")"

  if ! FILES="$(gh pr diff "$PR" -R "$REPO" --name-only 2>/dev/null)"; then
    echo "COULD NOT CHECK: could not fetch changed files for $REPO#$PR" >&2
    exit 2
  fi
fi

[[ -n "$TITLE" ]] || { echo "COULD NOT CHECK: empty PR title" >&2; exit 2; }

# --- 1. Is this PR changelog-worthy? -----------------------------------------
# Conventional-commit type at the head of the title, with an optional scope and
# an optional `!` breaking marker: `feat(skills)!: ...`. Only feat/fix/security
# are changelog-worthy; every other type is exempt by contract.
worthy_re='^(feat|fix|security)(\([^)]*\))?!?:'
conventional_re='^[a-z]+(\([^)]*\))?!?:'
if [[ ! "$TITLE" =~ $worthy_re ]]; then
  if [[ ! "$TITLE" =~ $conventional_re ]]; then
    # Declining to guess is not the same as passing. A title with no declared
    # type can't be classified, and guessing "exempt" is how a real feature
    # slips through (PR #1033, "corpus-provenance: flag claims …", is the live
    # example). The conventional-commit title format is separately required by
    # `builder-pr.md` § "PR Titles"; this just refuses to launder a violation
    # of it into a clean pass.
    echo "COULD NOT CLASSIFY: '$TITLE' is not a conventional-commit title, so changelog-worthiness can't be determined mechanically. Classify by hand (and fix the title)." >&2
    exit 2
  fi
  ctype="$(printf '%s' "$TITLE" | sed -nE 's/^([a-z]+)(\([^)]*\))?!?:.*/\1/p')"
  echo "EXEMPT: '$ctype' title is not feat/fix/security — no CHANGELOG entry required."
  exit 0
fi

# --- 2. Does the diff touch CHANGELOG.md? ------------------------------------
touches_changelog=0
if printf '%s\n' "$FILES" | grep -qE '(^|/)CHANGELOG\.md$'; then
  touches_changelog=1
fi

# --- 3. What does the PR body claim? -----------------------------------------
# Match the line anywhere in the body, tolerating list-marker and bold prefixes
# (`- CHANGELOG: yes`, `**CHANGELOG:** yes`) the way PR bodies actually get
# written. Take the LAST match so a body that quotes the convention in prose
# before stating its own claim resolves to the real claim.
claim_line="$(printf '%s\n' "$BODY" \
  | grep -iE '^[[:space:]]*[-*]?[[:space:]]*\**CHANGELOG:?\**[[:space:]]*:?[[:space:]]*(yes|no)([^a-zA-Z]|$)' \
  | tail -1)"
claim=""
if [[ -n "$claim_line" ]]; then
  # Safe to take the first yes/no on the line: "changelog" contains neither.
  claim="$(printf '%s' "$claim_line" | tr '[:upper:]' '[:lower:]' | grep -oE 'yes|no' | head -1)"
fi

# --- 4. Verdict ---------------------------------------------------------------
if [[ "$claim" == "yes" && "$touches_changelog" -eq 0 ]]; then
  # The contradiction case: claimed but not corroborated by the diff. Same shape
  # (and same severity tier) as a false `TDD: yes`.
  echo "MISSING: PR body claims 'CHANGELOG: yes' but the diff touches no CHANGELOG.md." >&2
  echo "         Add the entry under '## [Unreleased]', or correct the claim to 'CHANGELOG: no — <reason>'." >&2
  exit 1
fi

if [[ "$touches_changelog" -eq 1 ]]; then
  echo "OK: changelog-worthy PR touches CHANGELOG.md (confirm the entry landed under '## [Unreleased]')."
  exit 0
fi

if [[ "$claim" == "no" ]]; then
  echo "OK: no CHANGELOG.md in the diff, but the body carries an explicit 'CHANGELOG: no' with a stated reason (advisory — a human/Judge still weighs the reason)."
  exit 0
fi

echo "MISSING: '$TITLE' is changelog-worthy (feat/fix/security) but the diff touches no CHANGELOG.md and the body carries no 'CHANGELOG:' line." >&2
echo "         Add an entry under '## [Unreleased]' in CHANGELOG.md (create the heading if the last release consumed it), or state 'CHANGELOG: no — <reason>' in the PR body." >&2
exit 1
