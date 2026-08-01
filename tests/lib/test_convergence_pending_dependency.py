"""Tests for the pending-dependency non-blocking terminator (issue #842).

Covers:

- ``_has_pending_dependency_flag`` / ``_has_blocking_critical_flag`` —
  helper coverage mirroring ``test_convergence_no_go.py``'s
  ``_has_no_go_flag`` coverage.
- ``decide_termination``: a ``critical_flags`` list containing ONLY
  ``pending_dependency`` (and/or ``no_go``) entries never routes to
  ``BLOCK`` on its own; an ordinary critical flag co-occurring with a
  ``pending_dependency`` flag still routes to ``BLOCK``.
- Resolution-order independence from NO-GO, THRESHOLD_MET,
  MAX_ITERATIONS, STALLED (a pending_dependency flag never suppresses any
  of those).
- Backwards compatibility: the legacy ``any_critical`` bool path and a
  ``critical_flags`` list with no pending_dependency entries are
  byte-identical to pre-#842 behavior.
- Integration via ``anvil.lib.critics.aggregate`` / ``compute_verdict``.
"""

from __future__ import annotations

import pytest

from anvil.lib.convergence import (
    NO_GO_FLAG_TYPE,
    PENDING_DEPENDENCY_FLAG_TYPE,
    TERMINATION_CRITICAL_FLAG,
    TERMINATION_MAX_ITERATIONS,
    TERMINATION_NO_GO,
    TERMINATION_STALLED,
    TERMINATION_THRESHOLD_MET,
    _has_blocking_critical_flag,
    _has_no_go_flag,
    _has_pending_dependency_flag,
    decide_termination,
)
from anvil.lib.review_schema import CriticalFlag, Verdict


# ---------------------------------------------------------------------------
# _has_pending_dependency_flag — helper coverage
# ---------------------------------------------------------------------------


def test_has_pending_dependency_flag_empty_list_is_false():
    assert _has_pending_dependency_flag([]) is False


def test_has_pending_dependency_flag_none_is_false():
    assert _has_pending_dependency_flag(None) is False


def test_has_pending_dependency_flag_with_critical_flag_instance():
    flags = [CriticalFlag(type="pending_dependency", justification="x")]
    assert _has_pending_dependency_flag(flags) is True


def test_has_pending_dependency_flag_with_bare_string():
    assert _has_pending_dependency_flag(["pending_dependency"]) is True
    assert _has_pending_dependency_flag(["factual_error"]) is False


def test_has_pending_dependency_flag_mixed_types():
    flags = [
        CriticalFlag(type="factual_error", justification="x"),
        "pending_dependency",
    ]
    assert _has_pending_dependency_flag(flags) is True


def test_pending_dependency_flag_type_constant():
    assert PENDING_DEPENDENCY_FLAG_TYPE == "pending_dependency"


# ---------------------------------------------------------------------------
# _has_blocking_critical_flag — the generic non-blocking-type exclusion
# ---------------------------------------------------------------------------


def test_has_blocking_critical_flag_empty_is_false():
    assert _has_blocking_critical_flag([]) is False
    assert _has_blocking_critical_flag(None) is False


def test_has_blocking_critical_flag_pending_only_is_false():
    flags = [CriticalFlag(type="pending_dependency", justification="x")]
    assert _has_blocking_critical_flag(flags) is False


def test_has_blocking_critical_flag_no_go_only_is_false():
    # no_go is resolved by its own higher-priority branch; excluding it
    # here has no observable effect (that branch always returns first),
    # but the set membership is exercised directly.
    flags = [CriticalFlag(type="no_go", justification="x")]
    assert _has_blocking_critical_flag(flags) is False


def test_has_blocking_critical_flag_pending_and_no_go_only_is_false():
    flags = [
        CriticalFlag(type="pending_dependency", justification="x"),
        CriticalFlag(type="no_go", justification="y"),
    ]
    assert _has_blocking_critical_flag(flags) is False


def test_has_blocking_critical_flag_ordinary_flag_is_true():
    flags = [CriticalFlag(type="factual_error", justification="x")]
    assert _has_blocking_critical_flag(flags) is True


def test_has_blocking_critical_flag_pending_plus_ordinary_is_true():
    flags = [
        CriticalFlag(type="pending_dependency", justification="x"),
        CriticalFlag(type="factual_error", justification="y"),
    ]
    assert _has_blocking_critical_flag(flags) is True


# ---------------------------------------------------------------------------
# decide_termination — pending_dependency-only never blocks
# ---------------------------------------------------------------------------


def test_decide_termination_pending_only_advances_on_score():
    flags = [CriticalFlag(type="pending_dependency", justification="x")]
    verdict, reason = decide_termination(
        history=[40],
        threshold=35,
        iteration=2,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.ADVANCE
    assert reason == TERMINATION_THRESHOLD_MET


def test_decide_termination_pending_only_below_threshold_revises():
    flags = [CriticalFlag(type="pending_dependency", justification="x")]
    verdict, reason = decide_termination(
        history=[20],
        threshold=35,
        iteration=2,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.REVISE
    assert reason == ""


def test_decide_termination_pending_only_reaches_stalled():
    flags = [CriticalFlag(type="pending_dependency", justification="x")]
    verdict, reason = decide_termination(
        history=[28, 28],
        threshold=35,
        iteration=2,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.STALLED
    assert reason == TERMINATION_STALLED


def test_decide_termination_pending_only_reaches_max_iterations():
    flags = [CriticalFlag(type="pending_dependency", justification="x")]
    verdict, reason = decide_termination(
        history=[20],
        threshold=35,
        iteration=4,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.REVISE
    assert reason == TERMINATION_MAX_ITERATIONS


def test_decide_termination_pending_coexisting_with_ordinary_flag_blocks():
    flags = [
        CriticalFlag(type="pending_dependency", justification="x"),
        CriticalFlag(type="factual_error", justification="y"),
    ]
    verdict, reason = decide_termination(
        history=[40],
        threshold=35,
        iteration=2,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.BLOCK
    assert reason == TERMINATION_CRITICAL_FLAG


def test_decide_termination_pending_does_not_suppress_no_go():
    flags = [
        CriticalFlag(type="pending_dependency", justification="x"),
        CriticalFlag(type="no_go", justification="thesis fails"),
    ]
    verdict, reason = decide_termination(
        history=[40],
        threshold=35,
        iteration=2,
        max_iterations=4,
        critical_flags=flags,
    )
    assert verdict == Verdict.NO_GO
    assert reason == TERMINATION_NO_GO


def test_decide_termination_pending_flag_bare_string_shape():
    verdict, reason = decide_termination(
        history=[40],
        threshold=35,
        iteration=2,
        max_iterations=4,
        critical_flags=["pending_dependency"],
    )
    assert verdict == Verdict.ADVANCE
    assert reason == TERMINATION_THRESHOLD_MET


# ---------------------------------------------------------------------------
# Backwards compatibility
# ---------------------------------------------------------------------------


def test_decide_termination_legacy_any_critical_unaffected():
    verdict, reason = decide_termination(
        history=[28],
        threshold=35,
        any_critical=True,
        iteration=3,
        max_iterations=4,
    )
    assert verdict == Verdict.BLOCK
    assert reason == TERMINATION_CRITICAL_FLAG


def test_decide_termination_ordinary_flags_unaffected():
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


# ---------------------------------------------------------------------------
# Integration via critics.aggregate / compute_verdict
# ---------------------------------------------------------------------------


def test_aggregate_pending_only_advances():
    from anvil.lib.critics import aggregate
    from anvil.lib.review_schema import Review, Score

    review = Review(
        version_dir="thread.1",
        critic_id="pending",
        scores=[Score(dimension="d", score=40, max=44)],
        critical_flags=[
            CriticalFlag(type="pending_dependency", justification="x")
        ],
        threshold=35,
    )
    agg = aggregate([review])
    assert agg.verdict == Verdict.ADVANCE
    # Flag stays visible for a terminal-state check to query.
    assert any(cf.type == "pending_dependency" for cf in agg.critical_flags)


def test_aggregate_pending_plus_ordinary_flag_blocks():
    from anvil.lib.critics import aggregate
    from anvil.lib.review_schema import Review, Score

    review_pending = Review(
        version_dir="thread.1",
        critic_id="pending",
        scores=[Score(dimension="d", score=None, max=44)],
        critical_flags=[
            CriticalFlag(type="pending_dependency", justification="x")
        ],
    )
    review_review = Review(
        version_dir="thread.1",
        critic_id="review",
        scores=[Score(dimension="d", score=40, max=44)],
        critical_flags=[
            CriticalFlag(type="factual_error", justification="y")
        ],
        threshold=35,
    )
    agg = aggregate([review_pending, review_review])
    assert agg.verdict == Verdict.BLOCK


def test_compute_verdict_with_history_pending_only_advances():
    from anvil.lib.critics import aggregate, compute_verdict
    from anvil.lib.review_schema import Review, Score

    review = Review(
        version_dir="thread.1",
        critic_id="pending",
        scores=[Score(dimension="d", score=40, max=44)],
        critical_flags=[
            CriticalFlag(type="pending_dependency", justification="x")
        ],
        threshold=35,
    )
    agg = aggregate([review])
    verdict = compute_verdict(agg, history=[40], iteration=2, max_iterations=4)
    assert verdict == Verdict.ADVANCE
