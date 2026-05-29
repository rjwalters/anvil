"""Tests for ``anvil.lib.convergence``.

Covers:

- ``check_stable`` — empty / short history, equal / within-window /
  out-of-window pairs, ``None`` in the window, ``lookback=3`` case.
- ``decide_termination`` resolution order — each of the 5 branches gets
  its own focused test.
- ``decide_termination`` priority boundaries — critical wins over
  stable-but-below, threshold wins over stable, max-iterations wins over
  stable.
- ``compute_verdict`` backward compatibility — ``history=None`` is
  identical to the pre-#27 single-iteration semantics; the existing 65-test
  suite in ``test_critics.py`` is unaffected.
- ``compute_verdict`` convergence path — when ``history`` is provided, the
  function returns the same verdict that ``decide_termination`` would.
- Three integration tests against synthetic ``_progress.json`` histories
  documented in the issue body:
    - ``[31, 32, 31]`` -> ``STALLED``
    - ``[28, 30, 32]`` -> ``ADVANCE``
    - ``[28]`` -> ``REVISE`` (continue)
"""

from __future__ import annotations

import pytest

from anvil.lib.convergence import (
    TERMINATION_CRITICAL_FLAG,
    TERMINATION_MAX_ITERATIONS,
    TERMINATION_STALLED,
    TERMINATION_THRESHOLD_MET,
    check_stable,
    decide_termination,
)
from anvil.lib.critics import aggregate, compute_verdict
from anvil.lib.review_schema import (
    CriticalFlag,
    Review,
    Score,
    Verdict,
)


# ---------------------------------------------------------------------------
# check_stable
# ---------------------------------------------------------------------------


def test_check_stable_empty_history_is_false():
    assert check_stable([]) is False


def test_check_stable_single_entry_is_false():
    # Default lookback=2 requires at least two entries.
    assert check_stable([31]) is False


def test_check_stable_two_equal_entries_is_true():
    assert check_stable([31, 31]) is True


def test_check_stable_two_entries_within_window_is_true():
    # Default window=1: 31 and 32 differ by exactly 1 -> stable.
    assert check_stable([31, 32]) is True
    assert check_stable([32, 31]) is True


def test_check_stable_two_entries_outside_window_is_false():
    # 31 vs 33 differ by 2 -> exceeds default window=1.
    assert check_stable([31, 33]) is False


def test_check_stable_none_in_window_is_false():
    # A None in the trailing lookback window prevents a stability decision.
    assert check_stable([31, None]) is False
    assert check_stable([None, 31]) is False
    # Earlier None outside the window does NOT prevent stability.
    assert check_stable([None, 31, 31]) is True


def test_check_stable_lookback_three_all_within_window():
    # Three entries all within ±1 of each other -> stable.
    assert check_stable([30, 31, 30], lookback=3) is True


def test_check_stable_lookback_three_middle_out_of_window():
    # Three entries with the middle one out -> not stable.
    assert check_stable([30, 35, 30], lookback=3) is False


def test_check_stable_lookback_three_only_uses_trailing_three():
    # Earlier wild value doesn't matter; only the last 3 are examined.
    assert check_stable([99, 30, 31, 30], lookback=3) is True


def test_check_stable_custom_window_widens_tolerance():
    # window=3 means spread up to 3 is stable.
    assert check_stable([30, 33], window=3) is True
    assert check_stable([30, 34], window=3) is False


def test_check_stable_lookback_one_is_meaningless():
    # By contract, a 1-entry "stability" check is False (need comparison).
    assert check_stable([31], lookback=1) is False
    assert check_stable([], lookback=1) is False


# ---------------------------------------------------------------------------
# decide_termination — resolution order, branch-by-branch
# ---------------------------------------------------------------------------


def test_decide_termination_critical_flag_branch():
    # Critical flag wins regardless of history / threshold / iteration.
    verdict, reason = decide_termination(
        history=[40],
        threshold=32,
        any_critical=True,
        iteration=1,
        max_iterations=4,
    )
    assert verdict == Verdict.BLOCK
    assert reason == TERMINATION_CRITICAL_FLAG


def test_decide_termination_threshold_met_branch():
    verdict, reason = decide_termination(
        history=[32],
        threshold=32,
        any_critical=False,
        iteration=1,
        max_iterations=4,
    )
    assert verdict == Verdict.ADVANCE
    assert reason == TERMINATION_THRESHOLD_MET


def test_decide_termination_max_iterations_branch():
    # No critical, below threshold, at cap, not stable -> MAX_ITERATIONS.
    # History of one entry is not enough for stability check anyway.
    verdict, reason = decide_termination(
        history=[28],
        threshold=32,
        any_critical=False,
        iteration=4,
        max_iterations=4,
    )
    assert verdict == Verdict.REVISE
    assert reason == TERMINATION_MAX_ITERATIONS


def test_decide_termination_stalled_branch():
    # No critical, below threshold, not at cap, stable -> STALLED.
    verdict, reason = decide_termination(
        history=[31, 31],
        threshold=32,
        any_critical=False,
        iteration=2,
        max_iterations=4,
    )
    assert verdict == Verdict.STALLED
    assert reason == TERMINATION_STALLED


def test_decide_termination_continue_branch():
    # No critical, below threshold, not at cap, not stable -> REVISE, "".
    verdict, reason = decide_termination(
        history=[28],
        threshold=32,
        any_critical=False,
        iteration=1,
        max_iterations=4,
    )
    assert verdict == Verdict.REVISE
    assert reason == ""


# ---------------------------------------------------------------------------
# decide_termination — priority boundaries
# ---------------------------------------------------------------------------


def test_decide_termination_critical_wins_over_stable():
    # Stable below-threshold history AND critical flag -> CRITICAL_FLAG.
    verdict, reason = decide_termination(
        history=[31, 31],
        threshold=32,
        any_critical=True,
        iteration=2,
        max_iterations=4,
    )
    assert verdict == Verdict.BLOCK
    assert reason == TERMINATION_CRITICAL_FLAG


def test_decide_termination_threshold_wins_over_stable():
    # Stable history AND threshold met -> ADVANCE, not STALLED.
    # Note: at-or-above threshold, the latest entry triggers THRESHOLD_MET.
    verdict, reason = decide_termination(
        history=[32, 32],
        threshold=32,
        any_critical=False,
        iteration=2,
        max_iterations=4,
    )
    assert verdict == Verdict.ADVANCE
    assert reason == TERMINATION_THRESHOLD_MET


def test_decide_termination_max_iterations_wins_over_stable():
    # Stable below-threshold AND at cap -> MAX_ITERATIONS, not STALLED.
    # The cap is the harder signal: the work simply ran out of budget.
    verdict, reason = decide_termination(
        history=[31, 31],
        threshold=32,
        any_critical=False,
        iteration=4,
        max_iterations=4,
    )
    assert verdict == Verdict.REVISE
    assert reason == TERMINATION_MAX_ITERATIONS


def test_decide_termination_critical_wins_over_threshold():
    # Threshold met but critical -> CRITICAL_FLAG (no ADVANCE).
    verdict, reason = decide_termination(
        history=[40],
        threshold=32,
        any_critical=True,
        iteration=1,
        max_iterations=4,
    )
    assert verdict == Verdict.BLOCK
    assert reason == TERMINATION_CRITICAL_FLAG


def test_decide_termination_threshold_wins_over_max_iterations():
    # At cap AND threshold met -> ADVANCE (the work converged just in time).
    verdict, reason = decide_termination(
        history=[28, 30, 32, 33],
        threshold=32,
        any_critical=False,
        iteration=4,
        max_iterations=4,
    )
    assert verdict == Verdict.ADVANCE
    assert reason == TERMINATION_THRESHOLD_MET


def test_decide_termination_empty_history_no_termination():
    # No history -> can't evaluate threshold or stability; fall through to
    # continue (REVISE, "") unless iteration cap was hit.
    verdict, reason = decide_termination(
        history=[],
        threshold=32,
        any_critical=False,
        iteration=0,
        max_iterations=4,
    )
    assert verdict == Verdict.REVISE
    assert reason == ""


def test_decide_termination_none_latest_does_not_advance():
    # Last entry is None (no scorecard); not enough info to advance.
    # No critical, not at cap, not stable -> continue.
    verdict, reason = decide_termination(
        history=[None],
        threshold=32,
        any_critical=False,
        iteration=1,
        max_iterations=4,
    )
    assert verdict == Verdict.REVISE
    assert reason == ""


def test_decide_termination_configurable_window_and_lookback():
    # Three entries within window=2 across lookback=3 -> STALLED.
    verdict, reason = decide_termination(
        history=[30, 31, 32],
        threshold=40,
        any_critical=False,
        iteration=3,
        max_iterations=10,
        window=2,
        lookback=3,
    )
    assert verdict == Verdict.STALLED
    assert reason == TERMINATION_STALLED


# ---------------------------------------------------------------------------
# compute_verdict — backward compatibility
# ---------------------------------------------------------------------------


def _agg(total: int, threshold: int, critical: bool = False):
    """Build a one-dimension AggregatedReview with the requested totals."""
    score = Score(
        dimension="d", score=total, max=max(total, 1), critical=critical
    )
    review = Review(
        version_dir="thread.1",
        critic_id="x",
        scores=[score],
        threshold=threshold,
    )
    return aggregate([review])


def test_compute_verdict_backward_compat_advance():
    # history=None preserves pre-#27 behavior exactly.
    agg = _agg(total=32, threshold=32, critical=False)
    assert compute_verdict(agg) == Verdict.ADVANCE
    assert compute_verdict(agg, history=None) == Verdict.ADVANCE


def test_compute_verdict_backward_compat_revise():
    agg = _agg(total=31, threshold=32, critical=False)
    assert compute_verdict(agg) == Verdict.REVISE
    assert compute_verdict(agg, history=None) == Verdict.REVISE


def test_compute_verdict_backward_compat_block():
    agg = _agg(total=40, threshold=32, critical=True)
    assert compute_verdict(agg) == Verdict.BLOCK
    assert compute_verdict(agg, history=None) == Verdict.BLOCK


def test_compute_verdict_with_history_advances_on_threshold():
    agg = _agg(total=32, threshold=32, critical=False)
    verdict = compute_verdict(
        agg,
        history=[32],
        iteration=1,
        max_iterations=4,
    )
    assert verdict == Verdict.ADVANCE


def test_compute_verdict_with_history_returns_stalled():
    agg = _agg(total=31, threshold=32, critical=False)
    verdict = compute_verdict(
        agg,
        history=[31, 31],
        iteration=2,
        max_iterations=4,
    )
    assert verdict == Verdict.STALLED


def test_compute_verdict_with_history_max_iterations_keeps_revise():
    agg = _agg(total=28, threshold=32, critical=False)
    verdict = compute_verdict(
        agg,
        history=[28],
        iteration=4,
        max_iterations=4,
    )
    # MAX_ITERATIONS keeps the verdict at REVISE (not STALLED).
    assert verdict == Verdict.REVISE


def test_compute_verdict_with_history_requires_iteration_and_max():
    agg = _agg(total=28, threshold=32, critical=False)
    with pytest.raises(ValueError):
        compute_verdict(agg, history=[28])
    with pytest.raises(ValueError):
        compute_verdict(agg, history=[28], iteration=1)
    with pytest.raises(ValueError):
        compute_verdict(agg, history=[28], max_iterations=4)


def test_compute_verdict_with_history_critical_still_blocks():
    agg = _agg(total=20, threshold=32, critical=True)
    verdict = compute_verdict(
        agg,
        history=[20, 20],
        iteration=2,
        max_iterations=4,
    )
    assert verdict == Verdict.BLOCK


# ---------------------------------------------------------------------------
# Integration: synthetic _progress.json score_history fixtures
# ---------------------------------------------------------------------------


def _extract_totals(score_history):
    """Pull totals out in iteration order, as an orchestrator would."""
    return [entry["total"] for entry in score_history]


def test_integration_oscillation_history_returns_stalled():
    """The oscillation case from the issue problem statement.

    score_history = [
      {iteration: 1, total: 31, threshold: 32},
      {iteration: 2, total: 32, threshold: 32},
      {iteration: 3, total: 31, threshold: 32},
    ]

    Note: iteration 2 with total 32 met the threshold at that step, but
    iteration 3 fell back to 31. The latest total (31) is below threshold,
    and the last 2 entries are 32 and 31 (within ±1) -> STALLED.
    """
    score_history = [
        {"iteration": 1, "total": 31, "threshold": 32},
        {"iteration": 2, "total": 32, "threshold": 32},
        {"iteration": 3, "total": 31, "threshold": 32},
    ]
    totals = _extract_totals(score_history)
    verdict, reason = decide_termination(
        history=totals,
        threshold=32,
        any_critical=False,
        iteration=3,
        max_iterations=4,
    )
    assert verdict == Verdict.STALLED
    assert reason == TERMINATION_STALLED


def test_integration_convergence_history_advances():
    """The convergence case: scores climbing monotonically to threshold.

    score_history = [
      {iteration: 1, total: 28, threshold: 32},
      {iteration: 2, total: 30, threshold: 32},
      {iteration: 3, total: 32, threshold: 32},
    ]

    The latest total met the threshold -> ADVANCE (threshold check wins
    before stable check).
    """
    score_history = [
        {"iteration": 1, "total": 28, "threshold": 32},
        {"iteration": 2, "total": 30, "threshold": 32},
        {"iteration": 3, "total": 32, "threshold": 32},
    ]
    totals = _extract_totals(score_history)
    verdict, reason = decide_termination(
        history=totals,
        threshold=32,
        any_critical=False,
        iteration=3,
        max_iterations=4,
    )
    assert verdict == Verdict.ADVANCE
    assert reason == TERMINATION_THRESHOLD_MET


def test_integration_early_iteration_continues():
    """The early-iteration case: only one round, plenty of budget left.

    score_history = [{iteration: 1, total: 28, threshold: 32}]

    Not enough history to decide stability, not at cap, no critical flag,
    below threshold -> continue (REVISE, "").
    """
    score_history = [
        {"iteration": 1, "total": 28, "threshold": 32},
    ]
    totals = _extract_totals(score_history)
    verdict, reason = decide_termination(
        history=totals,
        threshold=32,
        any_critical=False,
        iteration=1,
        max_iterations=4,
    )
    assert verdict == Verdict.REVISE
    assert reason == ""


def test_integration_history_with_null_scorecard():
    """An iteration with no scorecard (e.g., critical-flag short-circuit
    before scoring) is recorded as None and prevents stability decisions
    in its window. The orchestrator should continue rather than stall.

    score_history = [
      {iteration: 1, total: 30, threshold: 32},
      {iteration: 2, total: None, threshold: 32},
    ]
    """
    score_history = [
        {"iteration": 1, "total": 30, "threshold": 32},
        {"iteration": 2, "total": None, "threshold": 32},
    ]
    totals = _extract_totals(score_history)
    verdict, reason = decide_termination(
        history=totals,
        threshold=32,
        any_critical=False,
        iteration=2,
        max_iterations=4,
    )
    # Latest entry None -> threshold check skipped. Last 2 entries include
    # a None -> stability check returns False. Not at cap -> continue.
    assert verdict == Verdict.REVISE
    assert reason == ""
