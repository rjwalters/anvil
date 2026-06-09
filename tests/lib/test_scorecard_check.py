"""Tests for anvil/lib/scorecard_check.py (issue #392).

Covers the pure-function checks (all finding codes + the clean case +
the stamp-absent fallback + the overlay-adjusted pool) and the
filesystem convenience ``check_review_dir`` against memo prose-triple
fixtures, including the studio canary shape (a 9-dimension table whose
weights sum to 48 under a declared 44/44 ``advance: true`` verdict).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.lib.review_schema import (
    CriticalFlag,
    Review,
    Score,
    Verdict,
)
from anvil.lib.scorecard_check import (
    ADVANCE_INCONSISTENT,
    PARSE_ERROR,
    POOL_UNSTAMPED,
    SCORE_OUT_OF_BOUNDS,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    TOTAL_MISMATCH,
    WEIGHTS_SUM_MISMATCH,
    ScorecardFinding,
    check_review_dir,
    check_scorecard,
)


# The canonical /44 memo rubric weights (anvil-memo-v2, 9 dims).
MEMO_WEIGHTS = [5, 6, 6, 6, 4, 5, 4, 4, 4]
assert sum(MEMO_WEIGHTS) == 44

DIM_NAMES = [f"dim_{i}" for i in range(1, 10)]


def _make_review(
    weights=None,
    scores=None,
    total=None,
    verdict=None,
    critical_flags=(),
):
    weights = weights if weights is not None else MEMO_WEIGHTS
    if scores is None:
        scores = list(weights)  # full marks
    score_objs = [
        Score(dimension=d, score=s, max=w)
        for d, s, w in zip(DIM_NAMES, scores, weights)
    ]
    return Review(
        schema_version="1",
        version_dir="memo.5",
        critic_id="review",
        scores=score_objs,
        critical_flags=list(critical_flags),
        total=total,
        verdict=verdict,
    )


def _codes(findings):
    return [f.code for f in findings]


# ---------------------------------------------------------------------------
# Pure function: clean case
# ---------------------------------------------------------------------------


def test_clean_scorecard_zero_findings():
    review = _make_review(
        scores=[4, 6, 5, 5, 4, 5, 4, 4, 4], total=41, verdict=Verdict.ADVANCE
    )
    findings = check_scorecard(
        review, rubric_total=44, advance_threshold=35
    )
    assert findings == []


def test_clean_scorecard_advance_false_below_threshold():
    review = _make_review(
        scores=[2, 3, 4, 3, 2, 3, 2, 1, 2], total=22, verdict=Verdict.REVISE
    )
    findings = check_scorecard(
        review, rubric_total=44, advance_threshold=35
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Pure function: weights_sum_mismatch (the canary case)
# ---------------------------------------------------------------------------


def test_weights_sum_mismatch_canary_48_vs_44():
    """The studio canary: a 48-weight table under a 44/44 verdict."""
    inflated = [5, 6, 8, 6, 4, 5, 4, 4, 6]  # sums to 48
    review = _make_review(
        weights=inflated,
        scores=list(inflated),  # perfect marks against the inflated weights
        total=44,  # declared total: arithmetically impossible
        verdict=Verdict.ADVANCE,
    )
    findings = check_scorecard(
        review, rubric_total=44, advance_threshold=35
    )
    codes = _codes(findings)
    assert WEIGHTS_SUM_MISMATCH in codes
    mismatch = next(f for f in findings if f.code == WEIGHTS_SUM_MISMATCH)
    assert mismatch.severity == SEVERITY_ERROR
    assert mismatch.detail == "48 != 44"
    assert mismatch.compact == "weights_sum_mismatch: 48 != 44"
    # The declared 44 also disagrees with the computed 48.
    assert TOTAL_MISMATCH in codes


# ---------------------------------------------------------------------------
# Pure function: overlay-adjusted pool
# ---------------------------------------------------------------------------


def test_overlay_adjusted_pool_validates_against_38_not_44():
    """vision-document overlay: deltas sum to -6, effective pool 38."""
    adjustments = {
        "dim_1": -3,
        "dim_3": 2,
        "dim_4": -3,
        "dim_6": -4,
        "dim_9": 2,
    }
    adjusted = [
        w + adjustments.get(d, 0) for d, w in zip(DIM_NAMES, MEMO_WEIGHTS)
    ]
    assert sum(adjusted) == 38
    review = _make_review(
        weights=adjusted, scores=list(adjusted), total=38, verdict=None
    )
    findings = check_scorecard(
        review,
        rubric_total=44,
        advance_threshold=35,
        weight_adjustments=adjustments,
    )
    assert findings == []


def test_overlay_adjusted_pool_flags_base_44_table():
    """A 44-weight table under a vision-document (pool 38) stamp is wrong."""
    adjustments = {"dim_1": -3, "dim_3": 2, "dim_4": -3, "dim_6": -4, "dim_9": 2}
    review = _make_review(total=44, verdict=None)  # base /44 table
    findings = check_scorecard(
        review,
        rubric_total=44,
        advance_threshold=35,
        weight_adjustments=adjustments,
    )
    mismatch = next(f for f in findings if f.code == WEIGHTS_SUM_MISMATCH)
    assert mismatch.detail == "44 != 38"


def test_identity_overlay_validates_against_base_44():
    """investment-memo identity overlay: all-zero deltas keep the pool 44."""
    identity = {f"dim_{i}": 0 for i in range(1, 10)}
    review = _make_review(
        scores=[4, 6, 5, 5, 4, 5, 4, 4, 4], total=41, verdict=Verdict.ADVANCE
    )
    findings = check_scorecard(
        review,
        rubric_total=44,
        advance_threshold=35,
        weight_adjustments=identity,
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Pure function: score_out_of_bounds
# ---------------------------------------------------------------------------


def test_score_out_of_bounds_via_model_construct():
    """A score above its weight is flagged (raw re-check, no pydantic)."""
    good = [
        Score(dimension=d, score=w, max=w)
        for d, w in zip(DIM_NAMES[:-1], MEMO_WEIGHTS[:-1])
    ]
    bad = Score.model_construct(
        dimension="dim_9", score=7, max=4, critical=False
    )
    review = Review.model_construct(
        schema_version="1",
        version_dir="memo.5",
        critic_id="review",
        scores=good + [bad],
        critical_flags=[],
        findings=[],
        total=None,
        verdict=None,
    )
    findings = check_scorecard(
        review, rubric_total=44, advance_threshold=35
    )
    oob = [f for f in findings if f.code == SCORE_OUT_OF_BOUNDS]
    assert len(oob) == 1
    assert "dim_9" in oob[0].detail
    assert oob[0].severity == SEVERITY_ERROR


def test_negative_score_out_of_bounds():
    bad = Score.model_construct(
        dimension="dim_1", score=-1, max=5, critical=False
    )
    rest = [
        Score(dimension=d, score=w, max=w)
        for d, w in zip(DIM_NAMES[1:], MEMO_WEIGHTS[1:])
    ]
    review = Review.model_construct(
        schema_version="1",
        version_dir="memo.5",
        critic_id="review",
        scores=[bad] + rest,
        critical_flags=[],
        findings=[],
        total=None,
        verdict=None,
    )
    findings = check_scorecard(
        review, rubric_total=44, advance_threshold=35
    )
    assert SCORE_OUT_OF_BOUNDS in _codes(findings)


def test_null_scores_are_legal():
    """None scores (unowned dims) do not trip the bounds check."""
    scores = [
        Score(dimension=d, score=None, max=w)
        for d, w in zip(DIM_NAMES, MEMO_WEIGHTS)
    ]
    review = Review(
        schema_version="1",
        version_dir="memo.5",
        critic_id="review",
        scores=scores,
    )
    findings = check_scorecard(
        review, rubric_total=44, advance_threshold=35
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Pure function: total_mismatch
# ---------------------------------------------------------------------------


def test_total_mismatch():
    review = _make_review(
        scores=[4, 6, 5, 5, 4, 5, 4, 4, 4],  # sums to 41
        total=43,  # declared total disagrees
        verdict=Verdict.ADVANCE,
    )
    findings = check_scorecard(
        review, rubric_total=44, advance_threshold=35
    )
    mismatch = next(f for f in findings if f.code == TOTAL_MISMATCH)
    assert mismatch.detail == "declared 43 != computed 41"


def test_no_declared_total_skips_total_check():
    review = _make_review(scores=[4, 6, 5, 5, 4, 5, 4, 4, 4], total=None)
    findings = check_scorecard(
        review, rubric_total=44, advance_threshold=35
    )
    assert TOTAL_MISMATCH not in _codes(findings)


# ---------------------------------------------------------------------------
# Pure function: advance_inconsistent
# ---------------------------------------------------------------------------


def test_advance_true_below_threshold():
    review = _make_review(
        scores=[4, 5, 6, 5, 3, 4, 3, 1, 3],  # sums to 34
        total=34,
        verdict=Verdict.ADVANCE,
    )
    findings = check_scorecard(
        review, rubric_total=44, advance_threshold=35
    )
    inconsistent = [f for f in findings if f.code == ADVANCE_INCONSISTENT]
    assert len(inconsistent) == 1
    assert "34 < threshold 35" in inconsistent[0].detail


def test_advance_true_with_critical_flag():
    review = _make_review(
        scores=[5, 6, 6, 6, 4, 5, 4, 4, 4],
        total=44,
        verdict=None,
        critical_flags=[
            CriticalFlag(type="factual_error", justification="contradicted")
        ],
    )
    findings = check_scorecard(
        review,
        rubric_total=44,
        advance_threshold=35,
        advance=True,  # prose decision cross-checked against the flags
    )
    inconsistent = [f for f in findings if f.code == ADVANCE_INCONSISTENT]
    assert len(inconsistent) == 1
    assert "critical flag" in inconsistent[0].detail


def test_advance_explicit_kwarg_overrides_verdict():
    """Prose advance=False suppresses the check even when verdict says ADVANCE."""
    review = _make_review(
        scores=[4, 5, 6, 5, 3, 4, 3, 1, 3],
        total=34,
        verdict=Verdict.ADVANCE,
    )
    findings = check_scorecard(
        review,
        rubric_total=44,
        advance_threshold=35,
        advance=False,
    )
    assert ADVANCE_INCONSISTENT not in _codes(findings)


def test_advance_check_uses_declared_total_when_present():
    """Declared 36 >= 35 passes the threshold leg even though the computed
    34 disagrees — the total_mismatch finding carries that disagreement."""
    review = _make_review(
        scores=[4, 5, 6, 5, 3, 4, 3, 1, 3],  # sums to 34
        total=36,
        verdict=Verdict.ADVANCE,
    )
    findings = check_scorecard(
        review, rubric_total=44, advance_threshold=35
    )
    assert TOTAL_MISMATCH in _codes(findings)
    assert ADVANCE_INCONSISTENT not in _codes(findings)


# ---------------------------------------------------------------------------
# Pure function: pool_unstamped (legacy pre-#346)
# ---------------------------------------------------------------------------


def test_pool_unstamped_info_when_stamps_absent():
    review = _make_review(
        scores=[4, 6, 5, 5, 4, 5, 4, 4, 4], total=41, verdict=Verdict.ADVANCE
    )
    findings = check_scorecard(
        review, rubric_total=None, advance_threshold=None
    )
    assert _codes(findings) == [POOL_UNSTAMPED]
    assert findings[0].severity == SEVERITY_INFO


def test_internal_checks_still_run_when_unstamped():
    """Checks 2-4 are internal to the scorecard and run without stamps."""
    review = _make_review(
        scores=[4, 6, 5, 5, 4, 5, 4, 4, 4],  # sums to 41
        total=43,
        verdict=None,
        critical_flags=[
            CriticalFlag(type="factual_error", justification="contradicted")
        ],
    )
    findings = check_scorecard(
        review, rubric_total=None, advance_threshold=None, advance=True
    )
    codes = _codes(findings)
    assert POOL_UNSTAMPED in codes
    assert TOTAL_MISMATCH in codes
    assert ADVANCE_INCONSISTENT in codes  # critical-flag leg needs no stamp


# ---------------------------------------------------------------------------
# check_review_dir: memo prose-triple fixtures
# ---------------------------------------------------------------------------


SCORING_HEADER = (
    "| # | Dimension | Weight | Score | Justification |\n"
    "|---|-----------|--------|-------|---------------|\n"
)


def _write_review_dir(
    tmp_path: Path,
    *,
    weights,
    scores,
    total,
    denominator,
    advance,
    meta=None,
    summary=None,
    critical_flags_section="",
) -> Path:
    critic_dir = tmp_path / "memo.5.review"
    critic_dir.mkdir()
    rows = "".join(
        f"| {i} | Dimension {i} | {w} | {s} | fine |\n"
        for i, (w, s) in enumerate(zip(weights, scores), start=1)
    )
    (critic_dir / "scoring.md").write_text(SCORING_HEADER + rows)
    (critic_dir / "verdict.md").write_text(
        f"# Verdict\n\n"
        f"**Total**: {total}/{denominator}\n"
        f"**Decision**: `advance: {'true' if advance else 'false'}`\n"
        f"{critical_flags_section}"
    )
    (critic_dir / "comments.md").write_text("# Comments\n\nNone.\n")
    if meta is not None:
        (critic_dir / "_meta.json").write_text(json.dumps(meta))
    if summary is not None:
        (critic_dir / "_summary.md").write_text(
            "# Review summary\n\n```json\n"
            + json.dumps(summary, indent=2)
            + "\n```\n"
        )
    return critic_dir


STAMPED_META = {
    "critic": "review",
    "scorecard_kind": "human-verdict",
    "rubric_id": "anvil-memo-v2",
    "rubric_total": 44,
    "advance_threshold": 35,
}


def test_dir_canary_48_weight_table_under_44_verdict(tmp_path):
    """End-to-end studio canary: 48-weight table, declared 44/44, advance: true."""
    inflated = [5, 6, 8, 6, 4, 5, 4, 4, 6]  # sums to 48
    critic_dir = _write_review_dir(
        tmp_path,
        weights=inflated,
        scores=inflated,
        total=44,
        denominator=44,
        advance=True,
        meta=STAMPED_META,
    )
    findings = check_review_dir(critic_dir)
    codes = _codes(findings)
    assert WEIGHTS_SUM_MISMATCH in codes
    mismatch = next(f for f in findings if f.code == WEIGHTS_SUM_MISMATCH)
    assert mismatch.compact == "weights_sum_mismatch: 48 != 44"
    assert TOTAL_MISMATCH in codes  # declared 44 vs computed 48


def test_dir_well_formed_review_zero_findings(tmp_path):
    critic_dir = _write_review_dir(
        tmp_path,
        weights=MEMO_WEIGHTS,
        scores=[4, 6, 5, 5, 4, 5, 4, 4, 4],
        total=41,
        denominator=44,
        advance=True,
        meta=STAMPED_META,
    )
    assert check_review_dir(critic_dir) == []


def test_dir_score_above_weight_yields_finding_not_exception(tmp_path):
    """AC3: per-dim score > weight produces a finding, not a ValidationError."""
    scores = list(MEMO_WEIGHTS)
    scores[2] = MEMO_WEIGHTS[2] + 1  # 9 > weight 8
    critic_dir = _write_review_dir(
        tmp_path,
        weights=MEMO_WEIGHTS,
        scores=scores,
        total=45,
        denominator=44,
        advance=True,
        meta=STAMPED_META,
    )
    findings = check_review_dir(critic_dir)
    assert findings, "malformed scorecard must produce findings"
    assert SCORE_OUT_OF_BOUNDS in _codes(findings)


def test_dir_legacy_unstamped_yields_pool_unstamped_info(tmp_path):
    """AC5: pre-#346 sidecar (no stamps) -> info-level pool_unstamped;
    the internal checks still run."""
    critic_dir = _write_review_dir(
        tmp_path,
        weights=MEMO_WEIGHTS,
        scores=[4, 6, 5, 5, 4, 5, 4, 4, 4],  # sums to 41
        total=43,  # declared disagrees -> total_mismatch still fires
        denominator=44,
        advance=True,
        meta=None,  # no _meta.json at all
    )
    findings = check_review_dir(critic_dir)
    codes = _codes(findings)
    assert POOL_UNSTAMPED in codes
    unstamped = next(f for f in findings if f.code == POOL_UNSTAMPED)
    assert unstamped.severity == SEVERITY_INFO
    assert TOTAL_MISMATCH in codes


def test_dir_legacy_rubric_kwarg_supplies_pool(tmp_path):
    """rubric-rebackport --legacy-rubric path: caller supplies the pool."""
    legacy_weights = [5, 5, 8, 5, 4, 5, 4, 4]  # /40-legacy 8-dim shape
    assert sum(legacy_weights) == 40
    critic_dir = _write_review_dir(
        tmp_path,
        weights=legacy_weights,
        scores=[4, 4, 7, 4, 3, 4, 3, 4],
        total=33,
        denominator=40,
        advance=True,
        meta=None,
    )
    findings = check_review_dir(
        critic_dir, rubric_total=40, advance_threshold=32
    )
    assert findings == []


def test_dir_overlay_adjusted_pool_from_summary(tmp_path):
    """AC2: vision-document overlay recorded in _summary.md adjusts the pool."""
    adjustments = {
        "dim_1": -3,
        "dim_2": 0,
        "dim_3": 2,
        "dim_4": -3,
        "dim_5": 0,
        "dim_6": -4,
        "dim_7": 0,
        "dim_8": 0,
        "dim_9": 2,
    }
    adjusted = [
        w + adjustments[d] for d, w in zip(DIM_NAMES, MEMO_WEIGHTS)
    ]
    assert sum(adjusted) == 38
    critic_dir = _write_review_dir(
        tmp_path,
        weights=adjusted,
        scores=adjusted,
        total=38,
        denominator=38,
        advance=True,
        meta=STAMPED_META,
        summary={
            "critic": "review",
            "rubric_overlay": {
                "ran": True,
                "artifact_type": "vision-document",
                "weight_adjustments": adjustments,
            },
        },
    )
    assert check_review_dir(critic_dir) == []


def test_dir_advance_true_with_critical_flag_section(tmp_path):
    critic_dir = _write_review_dir(
        tmp_path,
        weights=MEMO_WEIGHTS,
        scores=[5, 6, 6, 6, 4, 5, 4, 4, 4],
        total=44,
        denominator=44,
        advance=True,
        meta=STAMPED_META,
        critical_flags_section=(
            "\n## Critical flags\n\n"
            "- **factual_error**: contradicted by refs/cv.pdf\n"
        ),
    )
    findings = check_review_dir(critic_dir)
    inconsistent = [f for f in findings if f.code == ADVANCE_INCONSISTENT]
    assert len(inconsistent) == 1
    assert "critical flag" in inconsistent[0].detail


def test_dir_explicit_kwargs_override_stamps(tmp_path):
    """Explicit rubric_total kwarg wins over the on-disk stamp."""
    critic_dir = _write_review_dir(
        tmp_path,
        weights=MEMO_WEIGHTS,  # sums to 44
        scores=[4, 6, 5, 5, 4, 5, 4, 4, 4],
        total=41,
        denominator=44,
        advance=True,
        meta=STAMPED_META,  # stamps 44
    )
    findings = check_review_dir(critic_dir, rubric_total=40)
    mismatch = next(f for f in findings if f.code == WEIGHTS_SUM_MISMATCH)
    assert mismatch.detail == "44 != 40"


def test_finding_is_frozen_dataclass():
    f = ScorecardFinding(
        code=PARSE_ERROR, severity=SEVERITY_ERROR, detail="x", message="y"
    )
    with pytest.raises(Exception):
        f.code = "other"  # type: ignore[misc]
