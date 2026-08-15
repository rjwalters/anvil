#!/usr/bin/env bash
# test-gh-since.sh — regression tests for gh-since.sh and its registration as
# a guards.readOnlyFastPathExtra entry (issue #1060).
#
# Coverage:
#   1. gh-since.sh's own argument validation: no silent default watermark,
#      rejects non-numeric/negative/missing arguments, and a malformed
#      argument never reaches a shell-interpreted context (all hermetic —
#      validation happens before any gh-cached invocation, so these never
#      touch the network).
#   2. .loom/config.json registers gh-since.sh's exact path under
#      guards.readOnlyFastPathExtra.
#   3. Direct hook replay against .loom/hooks/guard-destructive-generic.sh
#      (VENDORED — this test only ever pipes JSON to it and reads its
#      decision output; it never edits it):
#        (a) the script's typical single-word invocation is fast-path
#            admitted — the guard's decision is "allow" (silent, no deny/ask
#            JSON), never a catastrophic worktree-write-confinement deny.
#        (b) a deliberately dangerous chained variant (the same invocation
#            with `; rm -rf /` appended) still denies at the catastrophic
#            tier — the fast-path registration is scoped to the exact
#            registered command word, not a general bypass.
#        (c) other metacharacter-chained variants (`&&`, `|`, `$(...)`) also
#            still deny/fall through, confirming fastpath_structural_ok()'s
#            structural gate is not defeated by the extra-admits entry.
#      The hook is only ever fed a JSON payload on stdin and its decision
#      output inspected — the guard never executes the command itself, so
#      this whole suite is hermetic (no live `gh`/network calls).
#
# Usage: bash .loom/scripts/tests/test-gh-since.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
GH_SINCE="$REPO_ROOT/.loom/scripts/gh-since.sh"
GUARD_DESTRUCTIVE_GENERIC="$REPO_ROOT/.loom/hooks/guard-destructive-generic.sh"
CONFIG_JSON="$REPO_ROOT/.loom/config.json"

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

if [[ ! -f "$GH_SINCE" ]]; then
    echo "ERROR: $GH_SINCE not found" >&2
    exit 1
fi
if [[ ! -x "$GH_SINCE" ]]; then
    echo "ERROR: $GH_SINCE is not executable" >&2
    exit 1
fi
if [[ ! -f "$GUARD_DESTRUCTIVE_GENERIC" ]]; then
    echo "ERROR: $GUARD_DESTRUCTIVE_GENERIC not found" >&2
    exit 1
fi
if [[ ! -f "$CONFIG_JSON" ]]; then
    echo "ERROR: $CONFIG_JSON not found" >&2
    exit 1
fi

# Feed a PreToolUse-shaped JSON payload to guard-destructive-generic.sh and
# print its raw decision output. The hook always exits 0 (it communicates
# allow/deny via the JSON contract, never via exit code) — so callers must
# inspect the printed output, not $?, exactly per #1060's acceptance
# criteria.
replay_guard() { # <command> <cwd>
    local cmd="$1" cwd="$2" input
    input=$(jq -n --arg cmd "$cmd" --arg cwd "$cwd" \
        '{tool_input: {command: $cmd}, cwd: $cwd}')
    printf '%s' "$input" | bash "$GUARD_DESTRUCTIVE_GENERIC" 2>/dev/null
}

# ---------------------------------------------------------------------------
# 1. gh-since.sh argument validation (hermetic — no gh-cached invocation on
#    any of these paths, validation fails before GH_READ is ever touched)
# ---------------------------------------------------------------------------
echo "=== gh-since.sh argument validation ==="

OUT=$(bash "$GH_SINCE" 2>&1); RC=$?
if [[ "$RC" -eq 2 ]]; then
    pass "no arguments -> usage error (exit 2), no silent default watermark"
else
    fail "no arguments -> usage error (exit 2), no silent default watermark" \
        "got exit $RC, output: $OUT"
fi

OUT=$(bash "$GH_SINCE" 100 2>&1); RC=$?
if [[ "$RC" -eq 2 ]]; then
    pass "only one watermark -> usage error (exit 2)"
else
    fail "only one watermark -> usage error (exit 2)" "got exit $RC, output: $OUT"
fi

OUT=$(bash "$GH_SINCE" abc 100 2>&1); RC=$?
if [[ "$RC" -eq 2 ]]; then
    pass "non-numeric <last-pr> -> usage error (exit 2)"
else
    fail "non-numeric <last-pr> -> usage error (exit 2)" "got exit $RC, output: $OUT"
fi

OUT=$(bash "$GH_SINCE" 100 abc 2>&1); RC=$?
if [[ "$RC" -eq 2 ]]; then
    pass "non-numeric <last-issue> -> usage error (exit 2)"
else
    fail "non-numeric <last-issue> -> usage error (exit 2)" "got exit $RC, output: $OUT"
fi

OUT=$(bash "$GH_SINCE" -5 100 2>&1); RC=$?
if [[ "$RC" -eq 2 ]]; then
    pass "negative <last-pr> -> usage error (exit 2, not treated as a flag)"
else
    fail "negative <last-pr> -> usage error (exit 2)" "got exit $RC, output: $OUT"
fi

# A malformed/adversarial argument must be rejected by the numeric regex
# check, never reach a shell-interpreted context. If this ever executed the
# embedded command, the marker file below would appear.
MARKER="/tmp/gh-since-test-injection-marker-$$"
rm -f "$MARKER"
OUT=$(bash "$GH_SINCE" "1; touch $MARKER" 100 2>&1); RC=$?
if [[ "$RC" -eq 2 ]] && [[ ! -f "$MARKER" ]]; then
    pass "injection-shaped <last-pr> argument -> rejected, not executed"
else
    fail "injection-shaped <last-pr> argument -> rejected, not executed" \
        "got exit $RC, marker present: $([[ -f "$MARKER" ]] && echo yes || echo no), output: $OUT"
fi
rm -f "$MARKER"

OUT=$(bash "$GH_SINCE" --bogus-flag 100 200 2>&1); RC=$?
if [[ "$RC" -eq 2 ]]; then
    pass "unknown flag -> usage error (exit 2)"
else
    fail "unknown flag -> usage error (exit 2)" "got exit $RC, output: $OUT"
fi

echo ""

# ---------------------------------------------------------------------------
# 2. .loom/config.json registers gh-since.sh under readOnlyFastPathExtra
# ---------------------------------------------------------------------------
echo "=== .loom/config.json registration ==="

REGISTERED=$(jq -r '.guards.readOnlyFastPathExtra // [] | index(".loom/scripts/gh-since.sh")' "$CONFIG_JSON" 2>/dev/null)
if [[ "$REGISTERED" != "null" && -n "$REGISTERED" ]]; then
    pass "guards.readOnlyFastPathExtra contains \".loom/scripts/gh-since.sh\""
else
    fail "guards.readOnlyFastPathExtra contains \".loom/scripts/gh-since.sh\"" \
        "jq index() returned: $REGISTERED"
fi

echo ""

# ---------------------------------------------------------------------------
# 3(a). Direct hook replay: typical invocation is fast-path admitted (allow)
# ---------------------------------------------------------------------------
echo "=== guard replay: typical gh-since.sh invocation -> allow ==="

TYPICAL_CMD=".loom/scripts/gh-since.sh 1008 876"
OUT=$(replay_guard "$TYPICAL_CMD" "$REPO_ROOT")
if [[ -z "$OUT" ]]; then
    pass "typical invocation ('$TYPICAL_CMD') -> silent allow, no deny/ask JSON"
else
    fail "typical invocation ('$TYPICAL_CMD') -> silent allow, no deny/ask JSON" \
        "guard emitted: $OUT"
fi

TYPICAL_CMD_FLAGS=".loom/scripts/gh-since.sh 1008 876 --exclude-guide-docs --json"
OUT=$(replay_guard "$TYPICAL_CMD_FLAGS" "$REPO_ROOT")
if [[ -z "$OUT" ]]; then
    pass "typical invocation with flags -> silent allow"
else
    fail "typical invocation with flags -> silent allow" "guard emitted: $OUT"
fi

echo ""

# ---------------------------------------------------------------------------
# 3(b). Direct hook replay: dangerous chained variant still denies
# ---------------------------------------------------------------------------
echo "=== guard replay: dangerous chained variant -> still denies ==="

DANGEROUS_CMD=".loom/scripts/gh-since.sh 1008 876; rm -rf /"
OUT=$(replay_guard "$DANGEROUS_CMD" "$REPO_ROOT")
DECISION=$(jq -r '.hookSpecificOutput.permissionDecision // empty' <<<"$OUT" 2>/dev/null)
if [[ "$DECISION" == "deny" ]]; then
    pass "'; rm -rf /' chained onto the registered command -> deny"
else
    fail "'; rm -rf /' chained onto the registered command -> deny" \
        "decision='$DECISION', full output: $OUT"
fi

echo ""

# ---------------------------------------------------------------------------
# 3(c). Other metacharacter-chained variants: the extra-admit entry is
# scoped to the exact literal command word, not a general bypass — every
# shape fastpath_structural_ok() rejects still falls through to the full
# path (which may allow OR deny depending on content, but must never take
# the silent fast-path shortcut for a compound command).
# ---------------------------------------------------------------------------
echo "=== guard replay: compound forms fall through (not silently fast-pathed) ==="

AND_CMD=".loom/scripts/gh-since.sh 1008 876 && rm -rf /"
OUT=$(replay_guard "$AND_CMD" "$REPO_ROOT")
DECISION=$(jq -r '.hookSpecificOutput.permissionDecision // empty' <<<"$OUT" 2>/dev/null)
if [[ "$DECISION" == "deny" ]]; then
    pass "'&& rm -rf /' chained form -> deny"
else
    fail "'&& rm -rf /' chained form -> deny" "decision='$DECISION', full output: $OUT"
fi

SUBST_CMD='.loom/scripts/gh-since.sh $(rm -rf /) 876'
OUT=$(replay_guard "$SUBST_CMD" "$REPO_ROOT")
DECISION=$(jq -r '.hookSpecificOutput.permissionDecision // empty' <<<"$OUT" 2>/dev/null)
if [[ "$DECISION" == "deny" ]]; then
    pass "command-substitution form '\$(rm -rf /)' as an argument -> deny"
else
    fail "command-substitution form '\$(rm -rf /)' as an argument -> deny" \
        "decision='$DECISION', full output: $OUT"
fi

echo ""

# --- Summary ---
echo "Tests run: $TESTS_RUN, Passed: $TESTS_PASSED, Failed: $TESTS_FAILED"

if [[ $TESTS_FAILED -gt 0 ]]; then
    exit 1
fi
exit 0
