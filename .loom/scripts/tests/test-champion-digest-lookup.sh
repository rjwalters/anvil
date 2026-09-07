#!/usr/bin/env bash
# test-champion-digest-lookup.sh — regression tests for
# .loom/scripts/champion-digest-lookup.sh (issue #1304).
#
# Coverage:
#   1. Argument validation: missing/empty title or marker, bad --limit,
#      unknown flag -> usage error (exit 2), no read call attempted.
#   2. Marker-tagged digest issue is resolved when present (the common
#      case, matching the vendored startswith() filter's happy path).
#   3. A pre-marker digest issue (title matches, body has no marker) is
#      resolved via the title-only fallback instead of being orphaned —
#      the concrete #1211-style incident this issue documents.
#   4. When two open issues both match by title and only one carries the
#      marker, the marker-tagged issue always wins, regardless of which
#      one is older/newer (both orderings are exercised).
#   5. No title match at all -> prints nothing, exit 0 (the caller's
#      existing "create a new digest issue" branch is unaffected).
#
# All cases stub the underlying read command via GH_READ_BIN (a tiny local
# script that echoes canned JSON) — hermetic, no live `gh`/network call.
#
# Usage: bash .loom/scripts/tests/test-champion-digest-lookup.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LOOKUP="$REPO_ROOT/.loom/scripts/champion-digest-lookup.sh"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "  ${GREEN}PASS${NC}: $1"
}

fail() {
    TESTS_RUN=$((TESTS_RUN + 1))
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "  ${RED}FAIL${NC}: $1"
    [[ -n "${2:-}" ]] && echo "    $2"
}

if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is required to run these tests" >&2
    exit 1
fi

if [[ ! -f "$LOOKUP" ]]; then
    echo "ERROR: $LOOKUP not found" >&2
    exit 1
fi
if [[ ! -x "$LOOKUP" ]]; then
    echo "ERROR: $LOOKUP is not executable" >&2
    exit 1
fi

TITLE="Champion: Merge-Risk Hold Digest"
MARKER="<!-- champion:merge-risk-hold-digest -->"

# Stub for GH_READ_BIN: echoes $STUB_JSON regardless of arguments, and
# records that it was invoked (so the argument-validation tests below can
# assert the stub was NEVER called for a rejected invocation).
STUB="$(mktemp -d)/stub-gh-read.sh"
STUB_CALLED_FILE="$(mktemp)"
cat >"$STUB" <<EOF
#!/usr/bin/env bash
echo -n > "$STUB_CALLED_FILE"
echo "\${STUB_JSON:-[]}"
EOF
chmod +x "$STUB"

run_lookup() { # <title> <marker> [extra args...]
    rm -f "$STUB_CALLED_FILE"
    GH_READ_BIN="$STUB" bash "$LOOKUP" "$@"
}

# ---------------------------------------------------------------------------
# 1. Argument validation (hermetic — the stub must never be invoked for a
#    rejected invocation)
# ---------------------------------------------------------------------------
echo "=== champion-digest-lookup.sh argument validation ==="

OUT=$(run_lookup 2>&1); RC=$?
if [[ "$RC" -eq 2 ]] && [[ ! -f "$STUB_CALLED_FILE" ]]; then
    pass "no arguments -> usage error (exit 2), stub not invoked"
else
    fail "no arguments -> usage error (exit 2), stub not invoked" \
        "got exit $RC, stub called: $([[ -f "$STUB_CALLED_FILE" ]] && echo yes || echo no), output: $OUT"
fi

OUT=$(run_lookup "$TITLE" 2>&1); RC=$?
if [[ "$RC" -eq 2 ]]; then
    pass "only title, no marker -> usage error (exit 2)"
else
    fail "only title, no marker -> usage error (exit 2)" "got exit $RC, output: $OUT"
fi

OUT=$(run_lookup "" "$MARKER" 2>&1); RC=$?
if [[ "$RC" -eq 2 ]]; then
    pass "empty title -> usage error (exit 2)"
else
    fail "empty title -> usage error (exit 2)" "got exit $RC, output: $OUT"
fi

OUT=$(run_lookup "$TITLE" "" 2>&1); RC=$?
if [[ "$RC" -eq 2 ]]; then
    pass "empty marker -> usage error (exit 2)"
else
    fail "empty marker -> usage error (exit 2)" "got exit $RC, output: $OUT"
fi

OUT=$(run_lookup "$TITLE" "$MARKER" --limit 0 2>&1); RC=$?
if [[ "$RC" -eq 2 ]]; then
    pass "--limit 0 -> usage error (exit 2)"
else
    fail "--limit 0 -> usage error (exit 2)" "got exit $RC, output: $OUT"
fi

OUT=$(run_lookup "$TITLE" "$MARKER" --bogus-flag 2>&1); RC=$?
if [[ "$RC" -eq 2 ]]; then
    pass "unknown flag -> usage error (exit 2)"
else
    fail "unknown flag -> usage error (exit 2)" "got exit $RC, output: $OUT"
fi

echo ""

# ---------------------------------------------------------------------------
# 2. Marker-tagged digest issue resolved (happy path, matches the vendored
#    startswith() filter's existing behavior)
# ---------------------------------------------------------------------------
echo "=== marker-tagged issue resolution ==="

STUB_JSON='[{"number":1224,"body":"<!-- champion:merge-risk-hold-digest -->\n# Merge-Risk Hold Digest"}]'
OUT=$(STUB_JSON="$STUB_JSON" run_lookup "$TITLE" "$MARKER")
if [[ "$OUT" == "1224" ]]; then
    pass "single marker-tagged match -> resolved to #1224"
else
    fail "single marker-tagged match -> resolved to #1224" "got: '$OUT'"
fi

echo ""

# ---------------------------------------------------------------------------
# 3. Pre-marker digest issue adopted via title-only fallback — the concrete
#    #1211-style incident (issue #1304)
# ---------------------------------------------------------------------------
echo "=== pre-marker digest issue adopted via fallback (#1304) ==="

STUB_JSON='[{"number":1211,"body":"Auto-maintained by Champion'"'"'s Held-PR Census (#6720, #6851)..."}]'
OUT=$(STUB_JSON="$STUB_JSON" run_lookup "$TITLE" "$MARKER")
if [[ "$OUT" == "1211" ]]; then
    pass "title match with no marker -> adopted via fallback (#1211), not orphaned"
else
    fail "title match with no marker -> adopted via fallback (#1211), not orphaned" "got: '$OUT'"
fi

STUB_JSON='[]'
OUT=$(STUB_JSON="$STUB_JSON" run_lookup "$TITLE" "$MARKER")
if [[ -z "$OUT" ]]; then
    pass "no title match at all -> empty output (caller creates a new digest issue)"
else
    fail "no title match at all -> empty output" "got: '$OUT'"
fi

echo ""

# ---------------------------------------------------------------------------
# 4. Marker match always wins over a title-only match, in EITHER number
#    ordering — this is the exact #1211/#1224 shape (old issue first,
#    marker-tagged issue created later) plus its mirror.
# ---------------------------------------------------------------------------
echo "=== marker match wins regardless of issue-number ordering ==="

STUB_JSON='[{"number":1211,"body":"Auto-maintained by Champion..."},{"number":1224,"body":"<!-- champion:merge-risk-hold-digest -->\n# digest"}]'
OUT=$(STUB_JSON="$STUB_JSON" run_lookup "$TITLE" "$MARKER")
if [[ "$OUT" == "1224" ]]; then
    pass "older no-marker (#1211) + newer marker-tagged (#1224) -> marker wins (#1224)"
else
    fail "older no-marker (#1211) + newer marker-tagged (#1224) -> marker wins (#1224)" "got: '$OUT'"
fi

STUB_JSON='[{"number":900,"body":"<!-- champion:merge-risk-hold-digest -->\n# digest"},{"number":950,"body":"no marker here"}]'
OUT=$(STUB_JSON="$STUB_JSON" run_lookup "$TITLE" "$MARKER")
if [[ "$OUT" == "900" ]]; then
    pass "older marker-tagged (#900) + newer no-marker (#950) -> marker wins (#900)"
else
    fail "older marker-tagged (#900) + newer no-marker (#950) -> marker wins (#900)" "got: '$OUT'"
fi

echo ""

# ---------------------------------------------------------------------------
# 5. Multiple pre-marker title matches, no marker anywhere -> fallback picks
#    the OLDEST (lowest-numbered) — the most plausible original digest.
# ---------------------------------------------------------------------------
echo "=== multiple no-marker title matches -> oldest wins ==="

STUB_JSON='[{"number":1300,"body":"no marker"},{"number":1211,"body":"no marker"},{"number":1250,"body":"no marker"}]'
OUT=$(STUB_JSON="$STUB_JSON" run_lookup "$TITLE" "$MARKER")
if [[ "$OUT" == "1211" ]]; then
    pass "three no-marker title matches, unordered input -> oldest (#1211) wins"
else
    fail "three no-marker title matches, unordered input -> oldest (#1211) wins" "got: '$OUT'"
fi

echo ""

rm -f "$STUB" "$STUB_CALLED_FILE"

# --- Summary ---
echo "Tests run: $TESTS_RUN, Passed: $TESTS_PASSED, Failed: $TESTS_FAILED"

if [[ $TESTS_FAILED -gt 0 ]]; then
    exit 1
fi
exit 0
