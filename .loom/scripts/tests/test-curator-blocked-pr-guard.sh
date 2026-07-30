#!/usr/bin/env bash
# test-curator-blocked-pr-guard.sh - Regression coverage for the curator
# "Blocked-pending-PR re-checks" idempotency guard's REST-backed marker read,
# its fail-closed behavior on read failure (#809), and its normalization of
# a transient `mergeable_state: unknown` reading so it is never mistaken for
# a real state change (#806).
#
# The guard is a documented bash reference script embedded in
# `.loom/roles/curator.md` / `.claude/commands/loom/curator.md` (kept
# byte-identical for this section per the #804 pairing convention). This test
# extracts the *actual* fenced ```bash block from the doc (no hand-copied
# duplicate to drift out of sync), stubs `gh`, and asserts on the resulting
# claim/comment/unclaim mutations across:
#
#   1. Both curator docs stay byte-identical for this section.
#   2. A failed comment read (non-zero exit, e.g. GraphQL/REST exhaustion)
#      skips the pass entirely: no claim, no comment, no unclaim at all -
#      not even the self-healing unclaim_if_dangling exception (#809 AC).
#   3. A genuine confirmed-empty read (successful call, zero matching
#      comments) still bootstraps (claim, comment, unclaim) exactly as
#      before this fix.
#   4. A fresh marker within the cooldown window skips (self-healing
#      unclaim only if a dangling claim label is present).
#   5. A stale marker with an unchanged state is a true no-op (self-healing
#      unclaim only).
#   6. A stale marker with a changed mergeable_state re-bootstraps.
#   7. (#806) A current reading of `unknown` against a stale prior marker
#      never posts a fresh marker (self-healing unclaim only).
#   8. (#806) `unknown` as the very first-ever reading (no prior marker)
#      still bootstraps normally.
#   9. (#806) Two consecutive `unknown` readings against the same
#      unchanged prior marker both skip without posting.
#  10. (#806) An `unknown` reading immediately followed by a genuine
#      `clean` -> `dirty` transition still fires a fresh marker.
#  11. (#806) The full `clean -> unknown -> clean -> unknown` sequence
#      observed live on #746 produces zero fresh marker posts.
#
# Usage:
#   bash .loom/scripts/tests/test-curator-blocked-pr-guard.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DOC_A="$REPO_ROOT/.loom/roles/curator.md"
DOC_B="$REPO_ROOT/.claude/commands/loom/curator.md"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

assert_contains() {
    local haystack="$1" needle="$2" msg="$3"
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "$haystack" == *"$needle"* ]]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo -e "  ${GREEN}PASS${NC}: $msg"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo -e "  ${RED}FAIL${NC}: $msg"
        echo "    Looking for: '$needle'"
        echo "    In:"
        printf '%s\n' "$haystack" | sed 's/^/      /'
    fi
}

assert_not_contains() {
    local haystack="$1" needle="$2" msg="$3"
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "$haystack" != *"$needle"* ]]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo -e "  ${GREEN}PASS${NC}: $msg"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo -e "  ${RED}FAIL${NC}: $msg"
        echo "    Unexpectedly found: '$needle'"
        echo "    In:"
        printf '%s\n' "$haystack" | sed 's/^/      /'
    fi
}

if [[ ! -f "$DOC_A" ]]; then
    echo "ERROR: $DOC_A not found" >&2
    exit 1
fi
if [[ ! -f "$DOC_B" ]]; then
    echo "ERROR: $DOC_B not found" >&2
    exit 1
fi

echo ""
echo "Testing curator blocked-pending-PR guard (#809 fail-closed REST read)..."
echo ""

# ---------------------------------------------------------------------------
# Group 1: the "Blocked-pending-PR re-checks" section stays byte-identical
# across both curator docs (#804 pairing convention).
# ---------------------------------------------------------------------------
echo "Group 1: byte-identical section across both curator docs"

extract_section() {
    # $1 = file. Prints from the guard heading up to (not including) the
    # next top-level "## " heading.
    awk '
      /^### Blocked-pending-PR re-checks/ { f=1 }
      f && /^## / && !/^### Blocked-pending-PR re-checks/ { exit }
      f { print }
    ' "$1"
}

SECTION_A=$(extract_section "$DOC_A")
SECTION_B=$(extract_section "$DOC_B")

TESTS_RUN=$((TESTS_RUN + 1))
if [[ -n "$SECTION_A" && "$SECTION_A" == "$SECTION_B" ]]; then
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "  ${GREEN}PASS${NC}: guard section is byte-identical in .loom/roles/curator.md and .claude/commands/loom/curator.md"
else
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "  ${RED}FAIL${NC}: guard section diverges between the two curator docs (or extraction found nothing)"
fi

# ---------------------------------------------------------------------------
# Group 2: the guard's marker read is REST-backed, not GraphQL (`gh issue
# view --json comments` must not appear anywhere in the section).
# ---------------------------------------------------------------------------
echo ""
echo "Group 2: marker read uses REST, not GraphQL"

assert_contains "$SECTION_A" 'gh api "repos/{owner}/{repo}/issues/$ISSUE/comments"' \
    "guard reads comments via 'gh api .../issues/\$ISSUE/comments' (REST)"
assert_not_contains "$SECTION_A" 'gh issue view "$ISSUE" --json comments' \
    "guard no longer reads comments via GraphQL-backed 'gh issue view --json comments'"

# ---------------------------------------------------------------------------
# Extract the actual fenced ```bash reference script and make it runnable
# under a stubbed `gh`. Placeholder assignment lines (ISSUE=<number>, etc.)
# are replaced with concrete test values; the remainder of the extracted
# body is executed verbatim.
# ---------------------------------------------------------------------------
extract_bash_block() {
    # $1 = file. Prints the contents of the first ```bash ... ``` fence
    # found after the guard heading.
    awk '
      /^### Blocked-pending-PR re-checks/ { f=1 }
      f && /^```bash$/ { c++; if (c == 1) { in_block=1; next } }
      in_block && /^```$/ { exit }
      in_block { print }
    ' "$1"
}

RAW_SCRIPT=$(extract_bash_block "$DOC_A")

TESTS_RUN=$((TESTS_RUN + 1))
if [[ -n "$RAW_SCRIPT" ]]; then
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "  ${GREEN}PASS${NC}: extracted the guard's fenced bash reference script ($(printf '%s\n' "$RAW_SCRIPT" | wc -l | tr -d ' ') lines)"
else
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "  ${RED}FAIL${NC}: could not extract a fenced bash block from the guard section"
fi

# Strip the placeholder assignment lines (ISSUE=<number>, PR_NUMBER=<pr-number>,
# STATE=<mergeable_state>) - the remaining body (MARKER=... onward) is tested
# verbatim against concrete values supplied by each scenario below.
SCRIPT_BODY=$(printf '%s\n' "$RAW_SCRIPT" | sed '/^ISSUE=<number>$/d; /^PR_NUMBER=<pr-number>$/d; /^STATE=<mergeable_state>/d')

iso_from_epoch() {
    local epoch="$1"
    date -u -d "@$epoch" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null \
        || date -u -r "$epoch" +"%Y-%m-%dT%H:%M:%SZ"
}

NOW_EPOCH=$(date -u +%s)

make_stub_gh() {
    # $1 = stub bin dir
    mkdir -p "$1"
    cat > "$1/gh" <<'STUBEOF'
#!/usr/bin/env bash
# Stub gh for the curator blocked-pending-PR guard tests.
echo "$*" >> "$CALL_LOG"

if [[ "$1" == "api" ]]; then
    path="$2"
    if [[ "$path" == */comments ]]; then
        if [[ "${GH_API_COMMENTS_FAIL:-0}" == "1" ]]; then
            echo "GraphQL: API rate limit already exceeded for user ID 123" >&2
            exit 1
        fi
        cat "$COMMENTS_FIXTURE"
        exit 0
    else
        # unclaim_if_dangling's label lookup: repos/{owner}/{repo}/issues/<n>
        printf '%s' "${CURRENT_LABELS:-}"
        exit 0
    fi
fi

# gh issue edit / gh issue comment - no-op success, already logged above.
exit 0
STUBEOF
    chmod +x "$1/gh"
}

run_scenario() {
    # $1 = scratch dir, $2 = fixture JSON, $3 = "0"/"1" for comments-read-fail,
    # $4 = current labels string (comma-joined), $5 = ISSUE, $6 = PR_NUMBER,
    # $7 = STATE
    local scratch="$1" fixture_json="$2" fail="$3" labels="$4"
    local issue="$5" pr="$6" state="$7"

    local stub_bin="$scratch/bin"
    make_stub_gh "$stub_bin"

    local fixture_file="$scratch/comments.json"
    printf '%s' "$fixture_json" > "$fixture_file"

    local call_log="$scratch/call_log"
    : > "$call_log"

    ISSUE="$issue" PR_NUMBER="$pr" STATE="$state" \
    CALL_LOG="$call_log" COMMENTS_FIXTURE="$fixture_file" \
    GH_API_COMMENTS_FAIL="$fail" CURRENT_LABELS="$labels" \
    PATH="$stub_bin:$PATH" \
        bash -c "ISSUE=$issue; PR_NUMBER=$pr; STATE=$state; $SCRIPT_BODY" \
        > "$scratch/stdout" 2> "$scratch/stderr"

    cat "$call_log"
}

# ---------------------------------------------------------------------------
# Group 3: failed read skips the pass entirely - no claim, no comment, no
# unclaim (not even the self-healing exception).
# ---------------------------------------------------------------------------
echo ""
echo "Group 3: failed comment read is fail-closed (#809)"

SCRATCH3=$(mktemp -d /tmp/loom-curator-guard-3.XXXXXX)
trap 'rm -rf "$SCRATCH3"' EXIT
CALLS3=$(run_scenario "$SCRATCH3" "" "1" "loom:curating" "42" "763" "clean")
rm -rf "$SCRATCH3"
trap - EXIT

assert_not_contains "$CALLS3" "issue edit" \
    "failed read: no 'gh issue edit' call of any kind (no claim, no unclaim)"
assert_not_contains "$CALLS3" "issue comment" \
    "failed read: no 'gh issue comment' call"
assert_contains "$CALLS3" "api repos/{owner}/{repo}/issues/42/comments" \
    "failed read: the REST comments read was attempted"

# ---------------------------------------------------------------------------
# Group 4: a genuine confirmed-empty read (successful call, zero comments)
# still bootstraps exactly as today.
# ---------------------------------------------------------------------------
echo ""
echo "Group 4: confirmed-empty read still bootstraps"

SCRATCH4=$(mktemp -d /tmp/loom-curator-guard-4.XXXXXX)
trap 'rm -rf "$SCRATCH4"' EXIT
CALLS4=$(run_scenario "$SCRATCH4" "[]" "0" "" "42" "763" "clean")
rm -rf "$SCRATCH4"
trap - EXIT

assert_contains "$CALLS4" "issue edit 42 --add-label loom:curating" \
    "confirmed-empty: claims loom:curating"
assert_contains "$CALLS4" "issue comment 42 --body" \
    "confirmed-empty: posts a fresh marker comment"
assert_contains "$CALLS4" "issue edit 42 --remove-label loom:curating" \
    "confirmed-empty: unclaims loom:curating after posting"

# ---------------------------------------------------------------------------
# Group 5: fresh marker within the cooldown window skips (self-healing
# unclaim only when a dangling claim label is present).
# ---------------------------------------------------------------------------
echo ""
echo "Group 5: fresh marker within cooldown skips (debounce)"

FRESH_AT=$(iso_from_epoch $((NOW_EPOCH - 10)))
FRESH_FIXTURE=$(cat <<EOF
[{"body": "<!-- curator:blocked-pending-pr-notice -->\n<!-- pr:763 -->\n<!-- mergeable_state:clean -->", "created_at": "$FRESH_AT"}]
EOF
)

SCRATCH5=$(mktemp -d /tmp/loom-curator-guard-5.XXXXXX)
trap 'rm -rf "$SCRATCH5"' EXIT
CALLS5=$(run_scenario "$SCRATCH5" "$FRESH_FIXTURE" "0" "loom:curating" "42" "763" "clean")
rm -rf "$SCRATCH5"
trap - EXIT

assert_not_contains "$CALLS5" "issue comment" \
    "fresh marker (cooldown): no fresh comment posted"
assert_not_contains "$CALLS5" "--add-label loom:curating" \
    "fresh marker (cooldown): no fresh claim"
assert_contains "$CALLS5" "issue edit 42 --remove-label loom:curating" \
    "fresh marker (cooldown): self-healing unclaim runs since loom:curating was dangling"

# ---------------------------------------------------------------------------
# Group 6: stale marker, unchanged state -> true no-op (self-healing unclaim
# only, no comment/claim).
# ---------------------------------------------------------------------------
echo ""
echo "Group 6: stale marker, unchanged state is a true no-op"

STALE_AT=$(iso_from_epoch $((NOW_EPOCH - 500)))
STALE_SAME_FIXTURE=$(cat <<EOF
[{"body": "<!-- curator:blocked-pending-pr-notice -->\n<!-- pr:763 -->\n<!-- mergeable_state:clean -->", "created_at": "$STALE_AT"}]
EOF
)

SCRATCH6=$(mktemp -d /tmp/loom-curator-guard-6.XXXXXX)
trap 'rm -rf "$SCRATCH6"' EXIT
CALLS6=$(run_scenario "$SCRATCH6" "$STALE_SAME_FIXTURE" "0" "" "42" "763" "clean")
rm -rf "$SCRATCH6"
trap - EXIT

assert_not_contains "$CALLS6" "issue comment" \
    "stale + same state: no comment posted (true no-op)"
assert_not_contains "$CALLS6" "--add-label loom:curating" \
    "stale + same state: no fresh claim"

# ---------------------------------------------------------------------------
# Group 7: stale marker, changed mergeable_state -> re-bootstraps.
# ---------------------------------------------------------------------------
echo ""
echo "Group 7: stale marker, changed state re-bootstraps"

STALE_DIFF_FIXTURE=$(cat <<EOF
[{"body": "<!-- curator:blocked-pending-pr-notice -->\n<!-- pr:763 -->\n<!-- mergeable_state:dirty -->", "created_at": "$STALE_AT"}]
EOF
)

SCRATCH7=$(mktemp -d /tmp/loom-curator-guard-7.XXXXXX)
trap 'rm -rf "$SCRATCH7"' EXIT
CALLS7=$(run_scenario "$SCRATCH7" "$STALE_DIFF_FIXTURE" "0" "" "42" "763" "clean")
rm -rf "$SCRATCH7"
trap - EXIT

assert_contains "$CALLS7" "issue edit 42 --add-label loom:curating" \
    "stale + changed state: claims loom:curating"
assert_contains "$CALLS7" "issue comment 42 --body" \
    "stale + changed state: posts a fresh marker comment"
assert_contains "$CALLS7" "issue edit 42 --remove-label loom:curating" \
    "stale + changed state: unclaims after posting"

# ---------------------------------------------------------------------------
# Group 8 (#806): current reading of 'unknown' against a stale prior marker
# (state clean) never posts a fresh marker - self-healing unclaim only.
# ---------------------------------------------------------------------------
echo ""
echo "Group 8: current 'unknown' reading against stale prior marker skips (#806)"

SCRATCH8=$(mktemp -d /tmp/loom-curator-guard-8.XXXXXX)
trap 'rm -rf "$SCRATCH8"' EXIT
CALLS8=$(run_scenario "$SCRATCH8" "$STALE_SAME_FIXTURE" "0" "loom:curating" "42" "763" "unknown")
rm -rf "$SCRATCH8"
trap - EXIT

assert_not_contains "$CALLS8" "issue comment" \
    "unknown reading: no fresh comment posted"
assert_not_contains "$CALLS8" "--add-label loom:curating" \
    "unknown reading: no fresh claim"
assert_contains "$CALLS8" "issue edit 42 --remove-label loom:curating" \
    "unknown reading: self-healing unclaim runs since loom:curating was dangling"

# ---------------------------------------------------------------------------
# Group 9 (#806): 'unknown' as the very first-ever reading (no prior marker)
# still bootstraps normally - nothing yet to preserve.
# ---------------------------------------------------------------------------
echo ""
echo "Group 9: 'unknown' with no prior marker still bootstraps (#806 edge case a)"

SCRATCH9=$(mktemp -d /tmp/loom-curator-guard-9.XXXXXX)
trap 'rm -rf "$SCRATCH9"' EXIT
CALLS9=$(run_scenario "$SCRATCH9" "[]" "0" "" "42" "763" "unknown")
rm -rf "$SCRATCH9"
trap - EXIT

assert_contains "$CALLS9" "issue edit 42 --add-label loom:curating" \
    "unknown + no prior marker: claims loom:curating"
assert_contains "$CALLS9" "issue comment 42 --body" \
    "unknown + no prior marker: posts a fresh marker comment"
assert_contains "$CALLS9" "issue edit 42 --remove-label loom:curating" \
    "unknown + no prior marker: unclaims after posting"

# ---------------------------------------------------------------------------
# Group 10 (#806): two consecutive 'unknown' readings against the same
# unchanged prior marker both skip without posting.
# ---------------------------------------------------------------------------
echo ""
echo "Group 10: two consecutive 'unknown' readings both skip (#806 edge case b)"

SCRATCH10A=$(mktemp -d /tmp/loom-curator-guard-10a.XXXXXX)
trap 'rm -rf "$SCRATCH10A"' EXIT
CALLS10A=$(run_scenario "$SCRATCH10A" "$STALE_SAME_FIXTURE" "0" "" "42" "763" "unknown")
rm -rf "$SCRATCH10A"
trap - EXIT

SCRATCH10B=$(mktemp -d /tmp/loom-curator-guard-10b.XXXXXX)
trap 'rm -rf "$SCRATCH10B"' EXIT
# Second reading sees the *same* fixture, since the first unknown reading
# never wrote a fresh marker - this is the load-bearing assertion of #806.
CALLS10B=$(run_scenario "$SCRATCH10B" "$STALE_SAME_FIXTURE" "0" "" "42" "763" "unknown")
rm -rf "$SCRATCH10B"
trap - EXIT

assert_not_contains "$CALLS10A" "issue comment" \
    "first consecutive unknown reading: no comment posted"
assert_not_contains "$CALLS10B" "issue comment" \
    "second consecutive unknown reading: no comment posted"

# ---------------------------------------------------------------------------
# Group 11 (#806): an 'unknown' reading immediately followed by a genuine
# clean -> dirty transition still fires a fresh marker - the unknown
# normalization must not mask a real transition.
# ---------------------------------------------------------------------------
echo ""
echo "Group 11: unknown then genuine clean->dirty transition still fires (#806 edge case c)"

SCRATCH11A=$(mktemp -d /tmp/loom-curator-guard-11a.XXXXXX)
trap 'rm -rf "$SCRATCH11A"' EXIT
CALLS11A=$(run_scenario "$SCRATCH11A" "$STALE_SAME_FIXTURE" "0" "" "42" "763" "unknown")
rm -rf "$SCRATCH11A"
trap - EXIT

SCRATCH11B=$(mktemp -d /tmp/loom-curator-guard-11b.XXXXXX)
trap 'rm -rf "$SCRATCH11B"' EXIT
# The marker is still recording the last *real* state (clean) since the
# unknown reading above never overwrote it - this is what lets the genuine
# transition below still compare correctly against "clean", not "unknown".
CALLS11B=$(run_scenario "$SCRATCH11B" "$STALE_SAME_FIXTURE" "0" "" "42" "763" "dirty")
rm -rf "$SCRATCH11B"
trap - EXIT

assert_not_contains "$CALLS11A" "issue comment" \
    "unknown pass: no comment posted"
assert_contains "$CALLS11B" "issue edit 42 --add-label loom:curating" \
    "genuine clean->dirty transition: claims loom:curating"
assert_contains "$CALLS11B" "issue comment 42 --body" \
    "genuine clean->dirty transition: posts a fresh marker comment"
assert_contains "$CALLS11B" "mergeable_state:dirty" \
    "genuine clean->dirty transition: fresh marker records the new state"

# ---------------------------------------------------------------------------
# Group 12 (#806): replay the exact #746 oscillation sequence
# (clean -> unknown -> clean -> unknown) and assert zero fresh marker posts
# across the whole sequence, since the underlying PR state never actually
# changed - the transient 'unknown' blips must not each trigger a re-post.
# ---------------------------------------------------------------------------
echo ""
echo "Group 12: full #746 clean/unknown oscillation sequence produces zero posts (#806)"

TOTAL_COMMENT_POSTS=0
for STEP_STATE in clean unknown clean unknown; do
    SCRATCH12=$(mktemp -d /tmp/loom-curator-guard-12.XXXXXX)
    trap 'rm -rf "$SCRATCH12"' EXIT
    CALLS12=$(run_scenario "$SCRATCH12" "$STALE_SAME_FIXTURE" "0" "" "42" "763" "$STEP_STATE")
    rm -rf "$SCRATCH12"
    trap - EXIT
    if [[ "$CALLS12" == *"issue comment"* ]]; then
        TOTAL_COMMENT_POSTS=$((TOTAL_COMMENT_POSTS + 1))
    fi
done

TESTS_RUN=$((TESTS_RUN + 1))
if [[ "$TOTAL_COMMENT_POSTS" -eq 0 ]]; then
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "  ${GREEN}PASS${NC}: clean/unknown oscillation sequence produced $TOTAL_COMMENT_POSTS fresh marker posts (expected 0)"
else
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "  ${RED}FAIL${NC}: clean/unknown oscillation sequence produced $TOTAL_COMMENT_POSTS fresh marker posts (expected 0)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "Test summary: $TESTS_PASSED/$TESTS_RUN passed ($TESTS_FAILED failed)"
echo "============================================================"

if [[ "$TESTS_FAILED" -gt 0 ]]; then
    exit 1
fi
exit 0
