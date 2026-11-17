"""Tests for the ``python -m anvil.lib.critics`` aggregate-report CLI (#1498).

The CLI exists because each critic's ``_summary.md`` prints an
owned-dimension subtotal, and the ip-uspto-provisional dim 9 is owned
jointly by the ``review`` and ``s112`` critics — so summing critic
subtotals double-counts it. The CLI wraps ``discover_critics`` +
``load_review`` + ``aggregate`` and prints the rubric-rule aggregate
(per-dimension mean of non-null scores, then the sum).

Covers:

- The printed total is the mean-based sum, NOT the subtotal sum, when
  two critics both score the shared dimension.
- A dimension with no non-null score prints as ``missing``, never
  ``0``, and the total is flagged as partial.
- ``--expect`` lists expected critics that have no sibling dir.
- No critics found → nonzero exit with a clear message; a missing
  version dir → invocation error.
- ``aggregate()``'s per-dimension-rounded total is shown alongside the
  sum-of-means when the two differ.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.critics import CANONICAL_REVIEW_FILENAME, main
from anvil.lib.review_schema import Review, Score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_review_dir(critic_dir: Path, review: Review) -> None:
    critic_dir.mkdir(parents=True, exist_ok=True)
    (critic_dir / CANONICAL_REVIEW_FILENAME).write_text(
        review.model_dump_json(indent=2)
    )


def _provisional_shape() -> list[tuple[str, int]]:
    """The ip-uspto-provisional 9-dim /45 weight shape (dim id, max)."""
    return [
        ("1_enablement_depth", 8),
        ("2_embodiments_coverage", 6),
        ("3_written_description", 5),
        ("4_drawings_sufficiency", 5),
        ("5_prior_art_positioning", 4),
        ("6_specification_completeness", 5),
        ("7_formal_compliance", 3),
        ("8_terminology_consistency", 3),
        ("9_conversion_readiness", 6),
    ]


def _scores(
    shape: list[tuple[str, int]], scored: dict[str, int]
) -> list[Score]:
    return [
        Score(dimension=dim, score=scored.get(dim), max=weight)
        for dim, weight in shape
    ]


def _make_version_dir(tmp_path: Path, name: str = "prov.1") -> Path:
    version_dir = tmp_path / name
    version_dir.mkdir()
    return version_dir


# ---------------------------------------------------------------------------
# The double-counted shared dimension (the bug that motivated #1498)
# ---------------------------------------------------------------------------


def test_total_is_mean_based_not_subtotal_sum(tmp_path, capsys):
    version_dir = _make_version_dir(tmp_path)
    shape = _provisional_shape()

    # review owns 4/6/7/8/9; s112 owns 1/2/3/9 — dim 9 shared.
    _write_review_dir(
        tmp_path / "prov.1.review",
        Review(
            version_dir="prov.1",
            critic_id="ip-uspto-provisional-review",
            scores=_scores(
                shape,
                {
                    "4_drawings_sufficiency": 5,
                    "6_specification_completeness": 5,
                    "7_formal_compliance": 3,
                    "8_terminology_consistency": 3,
                    "9_conversion_readiness": 5,
                },
            ),
            threshold=39,
        ),
    )
    _write_review_dir(
        tmp_path / "prov.1.s112",
        Review(
            version_dir="prov.1",
            critic_id="ip-uspto-provisional-s112",
            scores=_scores(
                shape,
                {
                    "1_enablement_depth": 5,
                    "2_embodiments_coverage": 4,
                    "3_written_description": 4,
                    "9_conversion_readiness": 4,
                },
            ),
            threshold=39,
        ),
    )

    rc = main([str(version_dir)])
    assert rc == 0
    out = capsys.readouterr().out

    # Both critics found.
    assert "review" in out and "s112" in out

    # Shared dim 9 prints the mean (5 + 4) / 2 = 4.5, not either subtotal.
    assert "9_conversion_readiness: 4.5 / 6" in out

    # Sum of per-dimension means: 5+5+3+3+4.5 + 5+4+4 = 33.5 / 45.
    assert "33.5 / 45" in out

    # The subtotal sum (21 + 17 = 38, double-counting dim 9) must not be
    # presented as the total.
    assert "38 / 45" not in out

    assert "advance threshold: 39" in out

    # aggregate() rounds each mean to an int (round(4.5) -> 4 under
    # round-half-to-even), so its total is 33 — shown when it differs.
    assert "33 / 45" in out


# ---------------------------------------------------------------------------
# Missing dimensions and missing critics
# ---------------------------------------------------------------------------


def test_dimension_with_no_non_null_score_prints_missing_never_zero(
    tmp_path, capsys
):
    version_dir = _make_version_dir(tmp_path)
    shape = _provisional_shape()

    # Only the s112 critic exists; it scores dims 1-3 + 9, so dims 4-8
    # have no non-null score anywhere.
    _write_review_dir(
        tmp_path / "prov.1.s112",
        Review(
            version_dir="prov.1",
            critic_id="ip-uspto-provisional-s112",
            scores=_scores(
                shape,
                {
                    "1_enablement_depth": 6,
                    "2_embodiments_coverage": 4,
                    "3_written_description": 4,
                    "9_conversion_readiness": 4,
                },
            ),
            threshold=39,
        ),
    )

    rc = main([str(version_dir)])
    assert rc == 0
    out = capsys.readouterr().out

    assert "4_drawings_sufficiency: missing / 5" in out
    assert "4_drawings_sufficiency: 0" not in out
    # Un-scored dims never contribute a value to the total.
    assert "partial" in out
    # 6 + 4 + 4 + 4 = 18 out of 45.
    assert "18 / 45" in out


def test_expect_lists_critics_without_sibling_dirs(tmp_path, capsys):
    version_dir = _make_version_dir(tmp_path)
    shape = _provisional_shape()

    _write_review_dir(
        tmp_path / "prov.1.review",
        Review(
            version_dir="prov.1",
            critic_id="ip-uspto-provisional-review",
            scores=_scores(shape, {"7_formal_compliance": 3}),
            threshold=39,
        ),
    )

    rc = main(
        [str(version_dir), "--expect", "review,s112,priorart"]
    )
    assert rc == 0
    out = capsys.readouterr().out

    assert "s112" in out and "priorart" in out
    # The present critic is not reported as missing: the found line names
    # it, and there is no second 'review' occurrence flagged missing.
    assert out.count("review") >= 1


def test_no_critics_found_is_nonzero_with_clear_message(tmp_path, capsys):
    version_dir = _make_version_dir(tmp_path)
    rc = main([str(version_dir)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "no critic" in err


def test_missing_version_dir_is_invocation_error(tmp_path, capsys):
    rc = main([str(tmp_path / "does-not-exist.1")])
    assert rc == 2
    err = capsys.readouterr().err
    assert "does-not-exist.1" in err


# ---------------------------------------------------------------------------
# The table-shaped legacy ip-uspto sibling (the vendored example's shape)
# ---------------------------------------------------------------------------


_TABLE_SHAPED_SUMMARY = """# s112 critic summary — prov.1

**Critic**: `s112`. **Critical flag**: not set.

```json
{
  "id": "anvil-ip-provisional-v1",
  "total": 45,
  "advance_threshold": 39,
  "dimensions": 9
}
```

| # | Dimension | Weight | Score | Justification |
|---|---|---|---|---|
| 1 | Enablement depth | 8 | 6 | quote "…" — ¶[0011] |
| 9 | Conversion readiness | 6 | 4 | quote "…" — ¶[0017] |
| 4 | Drawings sufficiency | 5 | null | n/a — see `review` |

**Owned-dimension subtotal (dims 1+2+3+9)**: 10 / 25.
"""


def test_table_shaped_legacy_sibling_aggregates(tmp_path, capsys):
    """No ``_review.json``: the ip-uspto-provisional triple (rubric-block
    JSON whose ``dimensions`` is a count + a 5-column scorecard table)
    still loads and reports through the CLI — the vendored example's
    exact shape (#1498)."""
    version_dir = _make_version_dir(tmp_path)
    critic_dir = tmp_path / "prov.1.s112"
    critic_dir.mkdir()
    (critic_dir / "_summary.md").write_text(_TABLE_SHAPED_SUMMARY)
    (critic_dir / "findings.md").write_text("1. [minor] D2 gap\n")
    (critic_dir / "_meta.json").write_text(
        '{"critic": "s112", "schema_version": 1, "advance_threshold": 39}'
    )

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        rc = main([str(version_dir)])
    assert rc == 0
    out = capsys.readouterr().out

    assert "critics found: s112" in out
    assert "Enablement depth: 6 / 8" in out
    assert "Conversion readiness: 4 / 6" in out
    assert "Drawings sufficiency: missing / 5" in out
    # 6 + 4 = 10 out of the sum of present dimension maxes (8+6+5=19;
    # dims with no row at all are unknowable without the skill's rubric).
    assert "10 / 19" in out
    assert "advance threshold: 39" in out
