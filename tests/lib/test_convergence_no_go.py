"""Tests for the NO-GO terminator in ``anvil.lib.convergence`` (issue #559).

Covers:

- ``decide_termination`` NO-GO branch: fires when ``critical_flags`` contains a
  ``CriticalFlag(type="no_go", ...)`` (or the bare-string ``"no_go"`` sentinel).
- Resolution-order priority: NO-GO beats generic CRITICAL_FLAG, THRESHOLD_MET,
  MAX_ITERATIONS, and STALLED.
- Backwards compatibility: when ``critical_flags`` is None (legacy callers),
  NO-GO is unreachable; all pre-#559 tests continue to pass.
- ``critical_flags`` accepts both ``CriticalFlag`` instances and bare ``str``
  type-tags; the convenience shape matters for fast paths and test fixtures.
"""

from __future__ import annotations

import pytest

from anvil.lib.convergence import (
    NO_GO_FLAG_TYPE,
    TERMINATION_CRITICAL_FLAG,
    TERMINATION_MAX_ITERATIONS,
    TERMINATION_NO_GO,
    TERMINATION_STALLED,
    TERMINATION_THRESHOLD_MET,
    _has_no_go_flag,
    decide_termination,
)
from anvil.lib.review_schema import CriticalFlag, Verdict


# ---------------------------------------------------------------------------
# _has_no_go_flag — helper coverage
# ---------------------------------------------------------------------------


def test_has_no_go_flag_empty_list_is_false():
    assert _has_no_go_flag([]) is False


def test_has_no_go_flag_none_is_false():
    assert _has_no_go_flag(None) is False


def test_has_no_go_flag_with_critical_flag_instance():
    flags = [CriticalFlag(type="no_go", justification="thesis fails")]
    assert _has_no_go_flag(flags) is True


def test_has_no_go_flag_with_bare_string():
    assert _has_no_go_flag(["no_go"]) is True
    assert _has_no_go_flag(["redteam_survives"]) is False


def test_has_no_go_flag_mixed_types_with_no_go_present():
    flags = [
        CriticalFlag(type="redteam_survives", justification="x"),
        "no_go",
    ]
    assert _has_no_go_flag(flags) is True


def test_has_no_go_flag_without_no_go_present():
    flags = [
        CriticalFlag(type="redteam_survives", justification="x"),
        CriticalFlag(type="strongman_load_bearing", justification="y"),
    ]
    assert _has_no_go_flag(flags) is False


def test_no_go_flag_type_constant():
    # Sanity check the canonical constant is the documented vocabulary value.
    assert NO_GO_FLAG_TYPE == "no_go"


# ---------------------------------------------------------------------------
# decide_termination — NO-GO branch
# ---------------------------------------------------------------------------


def test_decide_termination_no_go_branch_with_critical_flag_instance():
    flags = [CriticalFlag(type="no_go", justification="thesis fails")]
    verdict, reason = decide_termination(
        history=[28],
        threshold=35,
        iteration=3,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.NO_GO
    assert reason == TERMINATION_NO_GO


def test_decide_termination_no_go_branch_with_bare_string():
    verdict, reason = decide_termination(
        history=[28],
        threshold=35,
        iteration=3,
        max_iterations=4,
        critical_flags=["no_go"],
    )
    assert verdict == Verdict.NO_GO
    assert reason == TERMINATION_NO_GO


def test_decide_termination_no_go_branch_unreachable_via_any_critical_bool():
    # The legacy any_critical=True path NEVER fires NO-GO — backwards-compat.
    verdict, reason = decide_termination(
        history=[28],
        threshold=35,
        any_critical=True,
        iteration=3,
        max_iterations=4,
    )
    assert verdict == Verdict.BLOCK
    assert reason == TERMINATION_CRITICAL_FLAG


# ---------------------------------------------------------------------------
# Resolution order — NO-GO beats every other terminator
# ---------------------------------------------------------------------------


def test_decide_termination_no_go_wins_over_critical_flag():
    # Both a no_go flag AND a regular critical flag → NO-GO wins.
    flags = [
        CriticalFlag(type="redteam_survives", justification="x"),
        CriticalFlag(type="no_go", justification="thesis fails"),
    ]
    verdict, reason = decide_termination(
        history=[28],
        threshold=35,
        iteration=3,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.NO_GO
    assert reason == TERMINATION_NO_GO


def test_decide_termination_no_go_wins_over_threshold_met():
    # Even with total >= threshold, a no_go flag → NO-GO.
    flags = [CriticalFlag(type="no_go", justification="thesis fails")]
    verdict, reason = decide_termination(
        history=[40],
        threshold=35,
        iteration=2,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.NO_GO
    assert reason == TERMINATION_NO_GO


def test_decide_termination_no_go_wins_over_max_iterations():
    flags = [CriticalFlag(type="no_go", justification="thesis fails")]
    verdict, reason = decide_termination(
        history=[28],
        threshold=35,
        iteration=4,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.NO_GO
    assert reason == TERMINATION_NO_GO


def test_decide_termination_no_go_wins_over_stalled():
    flags = [CriticalFlag(type="no_go", justification="thesis fails")]
    verdict, reason = decide_termination(
        history=[28, 28],
        threshold=35,
        iteration=2,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.NO_GO
    assert reason == TERMINATION_NO_GO


# ---------------------------------------------------------------------------
# Distinction from STALLED, CRITICAL_FLAG, MAX_ITERATIONS, THRESHOLD_MET
# ---------------------------------------------------------------------------


def test_decide_termination_redteam_survives_alone_routes_to_block():
    # A redteam_survives flag WITHOUT a no_go flag → BLOCK (pre-#559 behavior).
    # This is the gap the curator named: a load-bearing SURVIVES today is
    # indistinguishable from a fixable typo at this layer; the memo-review
    # promotion step decides whether to escalate to no_go.
    flags = [CriticalFlag(type="redteam_survives", justification="x")]
    verdict, reason = decide_termination(
        history=[28],
        threshold=35,
        iteration=3,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.BLOCK
    assert reason == TERMINATION_CRITICAL_FLAG


def test_decide_termination_strongman_alone_routes_to_block():
    flags = [
        CriticalFlag(type="strongman_load_bearing", justification="x")
    ]
    verdict, reason = decide_termination(
        history=[28],
        threshold=35,
        iteration=3,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.BLOCK
    assert reason == TERMINATION_CRITICAL_FLAG


def test_decide_termination_stalled_distinct_from_no_go():
    # STALLED: score plateau, no critical flag, below threshold. Distinct from
    # NO-GO (thesis-failure terminal).
    verdict, reason = decide_termination(
        history=[31, 31],
        threshold=35,
        iteration=2,
        max_iterations=4,
        critical_flags=[],
    )
    assert verdict == Verdict.STALLED
    assert reason == TERMINATION_STALLED


def test_decide_termination_threshold_met_with_empty_critical_flags():
    # Empty critical_flags list (truthy-ish but len 0) → not no_go, not block.
    verdict, reason = decide_termination(
        history=[36],
        threshold=35,
        iteration=2,
        max_iterations=4,
        critical_flags=[],
    )
    assert verdict == Verdict.ADVANCE
    assert reason == TERMINATION_THRESHOLD_MET


def test_decide_termination_max_iterations_with_no_critical_flags():
    verdict, reason = decide_termination(
        history=[28],
        threshold=35,
        iteration=4,
        max_iterations=4,
        critical_flags=[],
    )
    assert verdict == Verdict.REVISE
    assert reason == TERMINATION_MAX_ITERATIONS


# ---------------------------------------------------------------------------
# Backwards compatibility — pre-#559 callers use the any_critical bool path
# ---------------------------------------------------------------------------


def test_decide_termination_legacy_any_critical_path_unchanged():
    # Legacy callers pass any_critical=True without critical_flags. They get
    # the pre-#559 behavior (BLOCK with CRITICAL_FLAG reason).
    verdict, reason = decide_termination(
        history=[28],
        threshold=35,
        any_critical=True,
        iteration=3,
        max_iterations=4,
    )
    assert verdict == Verdict.BLOCK
    assert reason == TERMINATION_CRITICAL_FLAG


def test_decide_termination_legacy_any_critical_false_path_unchanged():
    # No critical flag, no critical_flags list → existing resolution order.
    verdict, reason = decide_termination(
        history=[36],
        threshold=35,
        any_critical=False,
        iteration=2,
        max_iterations=4,
    )
    assert verdict == Verdict.ADVANCE
    assert reason == TERMINATION_THRESHOLD_MET


def test_decide_termination_critical_flags_overrides_any_critical_kwarg():
    # When both shapes are passed, the typed list's derivation wins.
    # any_critical=False but critical_flags=[no_go] → NO-GO.
    flags = [CriticalFlag(type="no_go", justification="x")]
    verdict, reason = decide_termination(
        history=[28],
        threshold=35,
        any_critical=False,
        iteration=3,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.NO_GO
    assert reason == TERMINATION_NO_GO


# ---------------------------------------------------------------------------
# Integration via critics.compute_verdict — the consumer-facing surface
# ---------------------------------------------------------------------------


def test_compute_verdict_with_history_returns_no_go():
    """When the aggregated review carries a no_go flag, compute_verdict
    routes through decide_termination and returns NO_GO."""
    from anvil.lib.critics import aggregate, compute_verdict
    from anvil.lib.review_schema import Review, Score

    review = Review(
        version_dir="thread.1",
        critic_id="memo-review",
        scores=[Score(dimension="d", score=28, max=44)],
        critical_flags=[
            CriticalFlag(type="no_go", justification="thesis fails")
        ],
        threshold=35,
    )
    agg = aggregate([review])
    verdict = compute_verdict(
        agg,
        history=[28],
        iteration=3,
        max_iterations=4,
    )
    assert verdict == Verdict.NO_GO


def test_compute_verdict_without_history_returns_no_go():
    """Single-iteration path: no_go flag → NO_GO even with no history."""
    from anvil.lib.critics import aggregate, compute_verdict
    from anvil.lib.review_schema import Review, Score

    review = Review(
        version_dir="thread.1",
        critic_id="memo-review",
        scores=[Score(dimension="d", score=28, max=44)],
        critical_flags=[
            CriticalFlag(type="no_go", justification="thesis fails")
        ],
        threshold=35,
    )
    agg = aggregate([review])
    verdict = compute_verdict(agg)
    assert verdict == Verdict.NO_GO


def test_aggregate_emits_no_go_when_any_critic_emits_no_go_flag():
    """The aggregator unions critical flags across critics; one critic's
    no_go propagates to the aggregated verdict."""
    from anvil.lib.critics import aggregate
    from anvil.lib.review_schema import Review, Score

    review_review = Review(
        version_dir="thread.1",
        critic_id="memo-review",
        scores=[Score(dimension="d", score=28, max=44)],
        critical_flags=[
            CriticalFlag(type="no_go", justification="thesis fails")
        ],
        threshold=35,
    )
    review_redteam = Review(
        version_dir="thread.1",
        critic_id="memo-redteam",
        scores=[Score(dimension="d", score=None, max=44)],
        critical_flags=[
            CriticalFlag(type="redteam_survives", justification="x")
        ],
    )
    agg = aggregate([review_review, review_redteam])
    assert agg.verdict == Verdict.NO_GO
    # Both flags survive in the aggregated list (deduplication is by exact
    # (type, justification) key).
    types = {cf.type for cf in agg.critical_flags}
    assert "no_go" in types
    assert "redteam_survives" in types
