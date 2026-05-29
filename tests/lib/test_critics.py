"""Tests for ``anvil.lib.critics``.

Covers:

- Discovery of sibling critic dirs (canonical + legacy + mixed).
- Load precedence: canonical > legacy, with deprecation warnings.
- Loading errors when no recognizable payload exists.
- Aggregation: mean-of-non-null, OR of critical, fix union dedup,
  evidence-span first-wins.
- Aggregation rejection: inconsistent max, mismatched version_dir, empty
  reviews list.
- ``compute_verdict`` boundary cases: at threshold, just below, just
  above, with critical flag (top-level and per-dim).
- Legacy adapter for the memo prose triple.
- Legacy adapter for the ip-uspto hybrid.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from anvil.lib.critics import (
    CANONICAL_REVIEW_FILENAME,
    CriticDiscoveryError,
    aggregate,
    compute_verdict,
    discover_critics,
    load_review,
)
from anvil.lib.review_schema import (
    CriticalFlag,
    Finding,
    Kind,
    Review,
    Score,
    Verdict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_review(
    *,
    version_dir: str = "thread.1",
    critic_id: str = "review",
    scores: list[Score] | None = None,
    findings: list[Finding] | None = None,
    critical_flags: list[CriticalFlag] | None = None,
    threshold: int | None = None,
    kind: Kind = Kind.JUDGMENT,
) -> Review:
    if scores is None:
        scores = [Score(dimension="d", score=3, max=5)]
    return Review(
        version_dir=version_dir,
        critic_id=critic_id,
        scores=scores,
        findings=findings or [],
        critical_flags=critical_flags or [],
        threshold=threshold,
        kind=kind,
    )


def _write_canonical(critic_dir: Path, review: Review) -> None:
    critic_dir.mkdir(parents=True, exist_ok=True)
    (critic_dir / CANONICAL_REVIEW_FILENAME).write_text(
        review.model_dump_json(indent=2)
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_discover_finds_sibling_canonical(tmp_path):
    (tmp_path / "thread.1").mkdir()
    review_dir = tmp_path / "thread.1.review"
    _write_canonical(review_dir, _make_review())

    siblings = discover_critics(tmp_path / "thread.1")
    assert siblings == [review_dir]


def test_discover_finds_multiple_siblings_sorted(tmp_path):
    (tmp_path / "thread.1").mkdir()
    for tag in ["review", "narrative", "market"]:
        _write_canonical(tmp_path / f"thread.1.{tag}", _make_review())

    siblings = discover_critics(tmp_path / "thread.1")
    names = [s.name for s in siblings]
    assert names == sorted(names)
    assert names == ["thread.1.market", "thread.1.narrative", "thread.1.review"]


def test_discover_skips_dirs_without_review(tmp_path):
    (tmp_path / "thread.1").mkdir()
    (tmp_path / "thread.1.empty").mkdir()
    _write_canonical(tmp_path / "thread.1.review", _make_review())

    siblings = discover_critics(tmp_path / "thread.1")
    assert siblings == [tmp_path / "thread.1.review"]


def test_discover_skips_subversion_dirs(tmp_path):
    (tmp_path / "thread.1").mkdir()
    # thread.1.1 is a "sub-version" (looks like a sibling with tag "1");
    # by convention only single-segment tags count, and our naming scheme
    # uses thread.{N} for versions and thread.{N}.<tag> for siblings —
    # so thread.1.2 (a number) is fine as a tag, but a sub-version dir
    # with two trailing segments must be skipped.
    (tmp_path / "thread.1.2.review").mkdir()
    (tmp_path / "thread.1.2.review" / CANONICAL_REVIEW_FILENAME).write_text("{}")

    _write_canonical(tmp_path / "thread.1.review", _make_review())
    siblings = discover_critics(tmp_path / "thread.1")
    # Only thread.1.review counts; thread.1.2.review has two dots after
    # the base name and is skipped.
    assert siblings == [tmp_path / "thread.1.review"]


def test_discover_finds_legacy_memo_triple(tmp_path):
    (tmp_path / "thread.1").mkdir()
    review_dir = tmp_path / "thread.1.review"
    review_dir.mkdir()
    (review_dir / "verdict.md").write_text("Total: 30/40\nDecision: advance: false\n")
    (review_dir / "scoring.md").write_text("| # | Dimension | Weight | Score | Justification |\n")
    (review_dir / "comments.md").write_text("")

    siblings = discover_critics(tmp_path / "thread.1")
    assert siblings == [review_dir]


def test_discover_finds_legacy_ip_uspto_triple(tmp_path):
    (tmp_path / "thread.1").mkdir()
    review_dir = tmp_path / "thread.1.review"
    review_dir.mkdir()
    (review_dir / "_summary.md").write_text("```json\n{\"dimensions\": {}}\n```\n")
    (review_dir / "findings.md").write_text("")
    (review_dir / "_meta.json").write_text(
        json.dumps({"critic": "ip-uspto-review", "schema_version": "1"})
    )
    siblings = discover_critics(tmp_path / "thread.1")
    assert siblings == [review_dir]


def test_discover_empty_when_no_siblings(tmp_path):
    (tmp_path / "thread.1").mkdir()
    assert discover_critics(tmp_path / "thread.1") == []


def test_discover_empty_when_parent_missing(tmp_path):
    # version_dir's parent doesn't exist on disk
    fake = tmp_path / "missing" / "thread.1"
    assert discover_critics(fake) == []


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_load_canonical(tmp_path):
    review_dir = tmp_path / "thread.1.review"
    _write_canonical(review_dir, _make_review(critic_id="memo-review"))
    review = load_review(review_dir)
    assert review.critic_id == "memo-review"
    assert review.scores[0].dimension == "d"


def test_load_canonical_with_stale_legacy_files_warns(tmp_path):
    review_dir = tmp_path / "thread.1.review"
    _write_canonical(review_dir, _make_review())
    (review_dir / "verdict.md").write_text("stale")
    (review_dir / "scoring.md").write_text("stale")
    (review_dir / "comments.md").write_text("stale")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        review = load_review(review_dir)
    assert review.critic_id == "review"
    assert any(
        "stale" in str(w.message) for w in caught if w.category is DeprecationWarning
    )


def test_load_missing_raises(tmp_path):
    review_dir = tmp_path / "thread.1.review"
    review_dir.mkdir()
    with pytest.raises(CriticDiscoveryError):
        load_review(review_dir)


# ---------------------------------------------------------------------------
# Legacy adapter — memo prose triple
# ---------------------------------------------------------------------------


MEMO_VERDICT_MD = """# Verdict

**Total**: 28 / 40
**Decision**: advance: false

## Critical flags

- **factual_error**: TAM figure cited as $12B but source says $1.4B.
- Risks section omits a known dealbreaker around regulatory exposure.

## Top revision priorities

1. Fix the TAM citation.
2. Add the regulatory risk.
"""

MEMO_SCORING_MD = """# Scoring

| # | Dimension | Weight | Score | Justification |
|---|---|---|---|---|
| 1 | recommendation_clarity | 5 | 4 | Clear recommendation; conditional split across paragraphs. |
| 2 | thesis_coherence | 6 | 5 | Falsifiable thesis. |
| 3 | evidence_quality | 6 | 3 | Two unsourced numbers. |
| 4 | risk_honesty | 6 | 4 | Missing regulatory risk. |
| 5 | market_framing | 4 | 3 | TAM disputed. |
| 6 | financial_reasoning | 5 | 4 | No downside sensitivity. |
| 7 | scope_discipline | 4 | 4 | In scope. |
| 8 | prose_structure | 4 | 3 | Undefined term. |
"""

MEMO_COMMENTS_MD = """# Comments

## evidence_quality

- **major**: TAM figure is unsourced.
- **nit**: Citation style inconsistent in section 3.

## risk_honesty

- **blocker**: Missing regulatory risk on HHS guidance reversal.
"""


def _write_memo_legacy(critic_dir: Path) -> None:
    critic_dir.mkdir(parents=True, exist_ok=True)
    (critic_dir / "verdict.md").write_text(MEMO_VERDICT_MD)
    (critic_dir / "scoring.md").write_text(MEMO_SCORING_MD)
    (critic_dir / "comments.md").write_text(MEMO_COMMENTS_MD)


def test_legacy_memo_adapter(tmp_path):
    review_dir = tmp_path / "acme-seed.3.review"
    _write_memo_legacy(review_dir)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        review = load_review(review_dir)
    deprecations = [
        w for w in caught if issubclass(w.category, DeprecationWarning)
    ]
    assert deprecations, "expected DeprecationWarning from memo adapter"

    assert review.schema_version == "1"
    assert review.kind == Kind.JUDGMENT
    assert review.total == 28
    assert review.threshold == 40
    assert review.verdict == Verdict.BLOCK  # critical flags present
    assert len(review.scores) == 8
    dims = [s.dimension for s in review.scores]
    assert "evidence_quality" in dims
    # Critical flags from the verdict.md bullets
    flag_types = [cf.type for cf in review.critical_flags]
    assert "factual_error" in flag_types
    # Findings from comments.md
    severities = [f.severity for f in review.findings]
    assert "blocker" in severities
    assert "major" in severities


def test_legacy_memo_adapter_canonical_rule_overrides_advance_hint(tmp_path):
    """The adapter prefers the canonical decision rule over the prose hint.

    When both total and threshold can be parsed, the verdict is derived
    from ``total >= threshold`` regardless of the verdict.md's
    ``advance:`` line. This is intentional: the prose hint is a
    pre-canonical-schema notion of the verdict and the canonical rule
    is the source of truth.
    """
    review_dir = tmp_path / "acme.1.review"
    review_dir.mkdir()
    (review_dir / "verdict.md").write_text(
        "**Total**: 35 / 40\n**Decision**: advance: true\n"
    )
    (review_dir / "scoring.md").write_text(
        "| # | Dimension | Weight | Score | Justification |\n"
        "| 1 | dim1 | 5 | 5 | Good. |\n"
    )
    (review_dir / "comments.md").write_text("")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        review = load_review(review_dir)
    # 35 < 40 → REVISE despite the "advance: true" hint.
    assert review.verdict == Verdict.REVISE
    assert review.total == 35
    assert review.threshold == 40


def test_legacy_memo_adapter_advance_hint_used_when_total_missing(tmp_path):
    review_dir = tmp_path / "acme.1.review"
    review_dir.mkdir()
    # No Total line; only the decision prose.
    (review_dir / "verdict.md").write_text("**Decision**: advance: true\n")
    (review_dir / "scoring.md").write_text(
        "| # | Dimension | Weight | Score | Justification |\n"
        "| 1 | dim1 | 5 | 5 | Good. |\n"
    )
    (review_dir / "comments.md").write_text("")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        review = load_review(review_dir)
    assert review.verdict == Verdict.ADVANCE
    assert review.total is None
    assert review.threshold is None


def test_legacy_memo_adapter_null_scores(tmp_path):
    review_dir = tmp_path / "acme.1.review"
    review_dir.mkdir()
    (review_dir / "verdict.md").write_text(
        "**Total**: 0 / 40\n**Decision**: advance: false\n"
    )
    (review_dir / "scoring.md").write_text(
        "| # | Dimension | Weight | Score | Justification |\n"
        "| 1 | dim1 | 5 | null | Not owned. |\n"
        "| 2 | dim2 | 5 | n/a | Not owned. |\n"
        "| 3 | dim3 | 5 | - | Not owned. |\n"
    )
    (review_dir / "comments.md").write_text("")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        review = load_review(review_dir)
    assert all(s.score is None for s in review.scores)


# ---------------------------------------------------------------------------
# Legacy adapter — ip-uspto hybrid
# ---------------------------------------------------------------------------


IP_USPTO_SUMMARY_MD = """# Reviewer summary

```json
{
  "critic": "ip-uspto-review",
  "critical_flag": true,
  "dimensions": {
    "1_claim_breadth": null,
    "2_s112": null,
    "6_spec_completeness": {"score": 4, "weight": 5, "justification": "Solid coverage."},
    "7_drawing_correspondence": {"score": 3, "weight": 5, "justification": "Two orphan numerals."},
    "8_formal_compliance": {"score": 5, "weight": 5, "justification": "Clean."}
  },
  "critical_flag_notes": [
    {"type": "spec_claim_mismatch", "justification": "Specification omits the key inventive feature.", "slide_ref": "spec.tex:L120"}
  ]
}
```
"""

IP_USPTO_FINDINGS_MD = """# Findings

1. **[blocker]** Specification omits FEATURE-A described in claim 5. Suggested fix: Add a paragraph to DETAILED DESCRIPTION covering FEATURE-A.
2. **[major]** Orphan reference numeral 47 in drawing fig-3. Fix: add to spec or remove from drawing.
3. **[minor]** Inconsistent heading capitalization. Fix: normalize.
4. **[nit]** Trailing whitespace on line 200.
"""

IP_USPTO_META_JSON = {
    "critic": "ip-uspto-review",
    "schema_version": "1",
    "model": "claude-opus-4-7",
    "role": "reviewer",
}


def _write_ip_uspto_legacy(critic_dir: Path) -> None:
    critic_dir.mkdir(parents=True, exist_ok=True)
    (critic_dir / "_summary.md").write_text(IP_USPTO_SUMMARY_MD)
    (critic_dir / "findings.md").write_text(IP_USPTO_FINDINGS_MD)
    (critic_dir / "_meta.json").write_text(json.dumps(IP_USPTO_META_JSON))


def test_legacy_ip_uspto_adapter(tmp_path):
    review_dir = tmp_path / "acme-widget.2.review"
    _write_ip_uspto_legacy(review_dir)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        review = load_review(review_dir)
    deprecations = [
        w for w in caught if issubclass(w.category, DeprecationWarning)
    ]
    assert deprecations, "expected DeprecationWarning from ip-uspto adapter"

    assert review.schema_version == "1"
    assert review.critic_id == "ip-uspto-review"
    assert review.model == "claude-opus-4-7"
    # Dimensions: 5 entries; 2 are null-owned, 3 are scored.
    assert len(review.scores) == 5
    null_dims = [s.dimension for s in review.scores if s.score is None]
    assert "1_claim_breadth" in null_dims
    assert "2_s112" in null_dims
    # Critical flag present.
    assert len(review.critical_flags) == 1
    assert review.critical_flags[0].type == "spec_claim_mismatch"
    # Findings.
    severities = [f.severity for f in review.findings]
    assert "blocker" in severities
    assert "major" in severities
    assert "minor" in severities
    assert "nit" in severities


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _three_critic_reviews() -> list[Review]:
    """Three critics with overlapping ownership.

    Dim layout (8 dims, /40):
      d1 owned by general (4/5) and narrative (5/5) → mean 4.5 → 4 (banker's)
      d2 owned by general (3/6) only → 3
      d3 owned by market (4/4) with critical → 4, critical
      d4 owned by general (5/6) only → 5
      d5 owned by general (4/6) only → 4
      d6 owned by market (3/5) only → 3
      d7 owned by general (3/4) only → 3
      d8 owned by general (3/4) only → 3
      Total: 4+3+4+5+4+3+3+3 = 29
    """
    general = Review(
        version_dir="thread.1",
        critic_id="general",
        rubric="anvil-demo-v1",
        threshold=28,
        scores=[
            Score(dimension="d1", score=4, max=5, fix="tighten recommendation"),
            Score(dimension="d2", score=3, max=6, fix="link claims",
                  evidence_span="thread.1/doc.md:L10-L20"),
            Score(dimension="d3", score=None, max=4,
                  justification="n/a — see market"),
            Score(dimension="d4", score=5, max=6),
            Score(dimension="d5", score=4, max=6),
            Score(dimension="d6", score=None, max=5),
            Score(dimension="d7", score=3, max=4),
            Score(dimension="d8", score=3, max=4, fix="define jargon"),
        ],
        findings=[
            Finding(severity="major", dimension="d2",
                    rationale="thesis chain breaks",
                    suggested_fix="link claims"),
            Finding(severity="minor", dimension="d8",
                    rationale="undefined term",
                    suggested_fix="define jargon"),
        ],
    )
    narrative = Review(
        version_dir="thread.1",
        critic_id="narrative",
        scores=[
            Score(dimension="d1", score=5, max=5),
            Score(dimension="d2", score=None, max=6),
            Score(dimension="d3", score=None, max=4),
            Score(dimension="d4", score=None, max=6),
            Score(dimension="d5", score=None, max=6),
            Score(dimension="d6", score=None, max=5),
            Score(dimension="d7", score=None, max=4),
            Score(dimension="d8", score=None, max=4),
        ],
        findings=[],
    )
    market = Review(
        version_dir="thread.1",
        critic_id="market",
        scores=[
            Score(dimension="d1", score=None, max=5),
            Score(dimension="d2", score=None, max=6),
            Score(dimension="d3", score=4, max=4, critical=True,
                  fix="cite TAM source",
                  evidence_span="thread.1/doc.md:L80-L90"),
            Score(dimension="d4", score=None, max=6),
            Score(dimension="d5", score=None, max=6),
            Score(dimension="d6", score=3, max=5),
            Score(dimension="d7", score=None, max=4),
            Score(dimension="d8", score=None, max=4),
        ],
        critical_flags=[
            CriticalFlag(type="factual_error",
                         justification="TAM figure cited does not match source."),
        ],
    )
    return [general, narrative, market]


def test_aggregate_score_means():
    agg = aggregate(_three_critic_reviews())
    # d1 mean = (4+5)/2 = 4.5
    assert agg.score_means["d1"] == 4.5
    # d3 only has one non-null score (4)
    assert agg.score_means["d3"] == 4.0
    # d6 only has one non-null score (3)
    assert agg.score_means["d6"] == 3.0


def test_aggregate_rounded_scores():
    agg = aggregate(_three_critic_reviews())
    by_dim = {s.dimension: s for s in agg.scores}
    # 4.5 rounds to 4 with banker's rounding (Python round).
    assert by_dim["d1"].score == 4
    assert by_dim["d2"].score == 3
    assert by_dim["d3"].score == 4
    assert by_dim["d4"].score == 5
    assert by_dim["d5"].score == 4
    assert by_dim["d6"].score == 3
    assert by_dim["d7"].score == 3
    assert by_dim["d8"].score == 3


def test_aggregate_total_matches_rounded_sum():
    agg = aggregate(_three_critic_reviews())
    assert agg.total == sum(s.score for s in agg.scores if s.score is not None)


def test_aggregate_critical_flag_propagation():
    agg = aggregate(_three_critic_reviews())
    # The market critic's d3 has critical=True → aggregated d3 must
    # also be critical.
    d3 = next(s for s in agg.scores if s.dimension == "d3")
    assert d3.critical is True
    # Top-level critical flag propagated through dedup.
    assert any(cf.type == "factual_error" for cf in agg.critical_flags)


def test_aggregate_verdict_blocks_on_critical():
    agg = aggregate(_three_critic_reviews())
    assert agg.verdict == Verdict.BLOCK


def test_aggregate_verdict_advances_without_critical():
    reviews = _three_critic_reviews()
    # Strip the critical flag and per-dim critical to test the
    # score-only path.
    reviews[2].critical_flags = []
    for s in reviews[2].scores:
        s.critical = False
    agg = aggregate(reviews)
    # Total 29, threshold 28 → ADVANCE.
    assert agg.total >= agg.threshold
    assert agg.verdict == Verdict.ADVANCE


def test_aggregate_fix_union_dedup():
    # Two critics emit identical fixes for the same dim; aggregated fix
    # should appear once.
    a = _make_review(
        critic_id="a",
        scores=[Score(dimension="d", score=3, max=5, fix="same fix"),
                Score(dimension="e", score=None, max=5)],
    )
    b = _make_review(
        critic_id="b",
        scores=[Score(dimension="d", score=4, max=5, fix="same fix"),
                Score(dimension="e", score=2, max=5, fix="other fix")],
    )
    agg = aggregate([a, b])
    by_dim = {s.dimension: s for s in agg.scores}
    assert by_dim["d"].fix == "same fix"
    assert by_dim["e"].fix == "other fix"


def test_aggregate_fix_union_joins_distinct():
    a = _make_review(
        critic_id="a",
        scores=[Score(dimension="d", score=3, max=5, fix="fix A")],
    )
    b = _make_review(
        critic_id="b",
        scores=[Score(dimension="d", score=4, max=5, fix="fix B")],
    )
    agg = aggregate([a, b])
    assert agg.scores[0].fix == "fix A; fix B"


def test_aggregate_evidence_span_first_wins():
    a = _make_review(
        critic_id="a",
        scores=[Score(dimension="d", score=3, max=5,
                       evidence_span="thread.1/doc.md:L10-L20")],
    )
    b = _make_review(
        critic_id="b",
        scores=[Score(dimension="d", score=4, max=5,
                       evidence_span="thread.1/doc.md:L100-L120")],
    )
    agg = aggregate([a, b])
    assert agg.scores[0].evidence_span == "thread.1/doc.md:L10-L20"


def test_aggregate_findings_dedup():
    f = Finding(severity="major", dimension="d", rationale="x",
                suggested_fix="y")
    a = _make_review(critic_id="a", findings=[f])
    b = _make_review(critic_id="b", findings=[f])
    agg = aggregate([a, b])
    assert len(agg.findings) == 1


def test_aggregate_empty_raises():
    with pytest.raises(ValueError, match="at least one Review"):
        aggregate([])


def test_aggregate_mismatched_version_dir_raises():
    a = _make_review(version_dir="thread.1", critic_id="a")
    b = _make_review(version_dir="thread.2", critic_id="b")
    with pytest.raises(ValueError, match="version_dir"):
        aggregate([a, b])


def test_aggregate_inconsistent_max_raises():
    a = _make_review(
        critic_id="a",
        scores=[Score(dimension="d", score=3, max=5)],
    )
    b = _make_review(
        critic_id="b",
        scores=[Score(dimension="d", score=4, max=6)],
    )
    with pytest.raises(ValueError, match="inconsistent max"):
        aggregate([a, b])


def test_aggregate_picks_first_threshold():
    a = _make_review(critic_id="a", threshold=None)
    b = _make_review(critic_id="b", threshold=32)
    c = _make_review(critic_id="c", threshold=40)
    agg = aggregate([a, b, c])
    assert agg.threshold == 32


def test_aggregate_default_threshold_when_none():
    a = _make_review(
        critic_id="a",
        scores=[Score(dimension="d", score=3, max=5)],
        threshold=None,
    )
    agg = aggregate([a])
    # Defaults to sum of max — score 3, max 5, so threshold=5, total=3
    # → REVISE.
    assert agg.threshold == 5
    assert agg.verdict == Verdict.REVISE


def test_aggregate_all_null_dim_contributes_zero():
    a = _make_review(
        critic_id="a",
        scores=[
            Score(dimension="d1", score=3, max=5),
            Score(dimension="d2", score=None, max=5),
        ],
        threshold=4,
    )
    agg = aggregate([a])
    by_dim = {s.dimension: s for s in agg.scores}
    assert by_dim["d2"].score is None
    assert agg.total == 3


# ---------------------------------------------------------------------------
# Verdict — boundary cases
# ---------------------------------------------------------------------------


def _single_critic_aggregated(total: int, threshold: int, critical: bool):
    """Helper to build an aggregated review with the requested totals."""
    score = Score(dimension="d", score=total, max=max(total, 1),
                   critical=critical)
    review = Review(
        version_dir="thread.1",
        critic_id="x",
        scores=[score],
        threshold=threshold,
    )
    return aggregate([review])


def test_verdict_at_threshold_advances():
    agg = _single_critic_aggregated(total=32, threshold=32, critical=False)
    assert compute_verdict(agg) == Verdict.ADVANCE


def test_verdict_just_below_threshold_revises():
    agg = _single_critic_aggregated(total=31, threshold=32, critical=False)
    assert compute_verdict(agg) == Verdict.REVISE


def test_verdict_above_threshold_advances():
    agg = _single_critic_aggregated(total=35, threshold=32, critical=False)
    assert compute_verdict(agg) == Verdict.ADVANCE


def test_verdict_critical_short_circuits_at_threshold():
    agg = _single_critic_aggregated(total=32, threshold=32, critical=True)
    assert compute_verdict(agg) == Verdict.BLOCK


def test_verdict_critical_short_circuits_above_threshold():
    agg = _single_critic_aggregated(total=40, threshold=32, critical=True)
    assert compute_verdict(agg) == Verdict.BLOCK


def test_verdict_threshold_override():
    agg = _single_critic_aggregated(total=32, threshold=32, critical=False)
    # Override to a higher threshold.
    assert compute_verdict(agg, threshold=33) == Verdict.REVISE


def test_verdict_top_level_critical_flag_blocks():
    review = Review(
        version_dir="thread.1",
        critic_id="x",
        scores=[Score(dimension="d", score=40, max=40)],
        critical_flags=[
            CriticalFlag(type="factual_error", justification="oops"),
        ],
        threshold=32,
    )
    agg = aggregate([review])
    assert compute_verdict(agg) == Verdict.BLOCK


# ---------------------------------------------------------------------------
# End-to-end discovery + load + aggregate
# ---------------------------------------------------------------------------


def test_end_to_end_three_critic_run(tmp_path):
    """Worked example: write three sibling critic dirs, discover, load,
    aggregate, and verify the verdict."""
    (tmp_path / "thread.1").mkdir()
    for review in _three_critic_reviews():
        tag = review.critic_id
        _write_canonical(tmp_path / f"thread.1.{tag}", review)

    siblings = discover_critics(tmp_path / "thread.1")
    assert len(siblings) == 3
    reviews = [load_review(s) for s in siblings]
    agg = aggregate(reviews)
    # Same expectation as the in-memory aggregate test.
    assert agg.verdict == Verdict.BLOCK
    assert agg.total == sum(s.score for s in agg.scores if s.score is not None)
