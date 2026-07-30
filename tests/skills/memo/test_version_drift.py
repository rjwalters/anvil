"""Tests for ``anvil/skills/memo/lib/version_drift.py`` (issue #746).

Per-skill test filename convention (#58): this file is named
``test_version_drift.py`` and lives under ``tests/skills/memo/``; the
``tests/skills/memo/__init__.py`` chain prevents collision with any
sibling skill that ships a same-named detector test in the future.

The fixture suite locks in the module's two load-bearing contracts:

1. **Graceful-skip** — first version (N=1), missing prior version dir, or
   missing/unreadable body file all resolve to ``ran=False`` with zero
   findings (byte-identical to "no drift check ran" for any thread that
   predates this contract).
2. **Two-transition monotonic finding rule** — a densification metric
   (bold-word share, hedge-marker count, meta-commentary count) only
   fires a finding when it increased across BOTH of the last two version
   transitions. A single-transition increase, or a metric outside the
   three densification metrics, must never fire.

The synthetic 3-version "bold ratchet" fixture mirrors the issue body's
canary evidence table (studio, sentinel thread, 2026-07-27).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.skills.memo.lib.version_drift import (
    ALL_METRICS,
    DENSIFICATION_METRICS,
    FINDING_SCOPE,
    FINDING_SEVERITY,
    VersionDriftResult,
    VersionMetrics,
    compute_drift,
    compute_metrics,
)


def _write_version(
    portfolio: Path,
    slug: str,
    n: int,
    *,
    bold_words: int = 0,
    hedge_hits: int = 0,
    meta_hits: int = 0,
    extra_words: int = 20,
    exhibits: int = 0,
) -> Path:
    """Write a synthetic ``<slug>.<n>/<slug>.md`` version dir."""
    version_dir = portfolio / f"{slug}.{n}"
    version_dir.mkdir(parents=True, exist_ok=True)
    filler = " ".join(f"word{i}" for i in range(extra_words))
    bold = " ".join(f"**boldword{i}**" for i in range(bold_words))
    hedges = " ".join(["roughly"] * hedge_hits)
    metas = " ".join(["As noted above, the thesis holds."] * meta_hits)
    body = (
        f"# {slug}\n\n"
        f"## Thesis\n\n"
        f"{filler}. {bold} {hedges} {metas}\n"
    )
    (version_dir / f"{slug}.md").write_text(body, encoding="utf-8")
    if exhibits:
        ex_dir = version_dir / "exhibits"
        ex_dir.mkdir()
        for i in range(exhibits):
            (ex_dir / f"fig{i}.png").write_text("fake-png", encoding="utf-8")
    return version_dir


# ---------------------------------------------------------------------------
# Module surface guards
# ---------------------------------------------------------------------------


def test_densification_metrics_are_the_three_documented_metrics():
    assert set(DENSIFICATION_METRICS) == {
        "bold_word_share",
        "hedge_marker_count",
        "meta_commentary_count",
    }


def test_all_metrics_is_a_superset_of_densification_metrics():
    assert set(DENSIFICATION_METRICS) <= set(ALL_METRICS)
    assert set(ALL_METRICS) == {
        "word_count",
        "bold_span_count",
        "bold_word_share",
        "hedge_marker_count",
        "meta_commentary_count",
        "mean_sentence_length",
        "exhibit_count",
    }


def test_finding_severity_and_scope_are_fixed():
    """Every finding is major/reduce — the issue's explicit contract."""
    assert FINDING_SEVERITY == "major"
    assert FINDING_SCOPE == "reduce"


# ---------------------------------------------------------------------------
# compute_metrics — per-version mechanical metrics
# ---------------------------------------------------------------------------


def test_compute_metrics_returns_none_for_missing_body(tmp_path: Path):
    version_dir = tmp_path / "acme.1"
    version_dir.mkdir()
    assert compute_metrics(version_dir) is None


def test_compute_metrics_counts_bold_spans_and_share(tmp_path: Path):
    version_dir = _write_version(
        tmp_path, "acme", 1, bold_words=2, extra_words=8
    )
    metrics = compute_metrics(version_dir)
    assert isinstance(metrics, VersionMetrics)
    assert metrics.bold_span_count == 2
    assert metrics.bold_word_count == 2
    assert metrics.bold_word_share > 0
    assert metrics.word_count >= 10


def test_compute_metrics_hedge_lexicon_hits(tmp_path: Path):
    version_dir = _write_version(tmp_path, "acme", 1, hedge_hits=3)
    metrics = compute_metrics(version_dir)
    assert metrics.hedge_marker_count == 3


def test_compute_metrics_hedge_parenthetical_caveat(tmp_path: Path):
    version_dir = tmp_path / "acme.1"
    version_dir.mkdir()
    body = "# acme\n\nThe figure is $40M (unconfirmed) per the deck.\n"
    (version_dir / "acme.md").write_text(body, encoding="utf-8")
    metrics = compute_metrics(version_dir)
    assert metrics.hedge_marker_count == 1


def test_compute_metrics_meta_commentary_lexicon_hits(tmp_path: Path):
    version_dir = _write_version(tmp_path, "acme", 1, meta_hits=2)
    metrics = compute_metrics(version_dir)
    assert metrics.meta_commentary_count == 2


def test_compute_metrics_exhibit_count(tmp_path: Path):
    version_dir = _write_version(tmp_path, "acme", 1, exhibits=3)
    metrics = compute_metrics(version_dir)
    assert metrics.exhibit_count == 3


def test_compute_metrics_zero_exhibits_when_dir_absent(tmp_path: Path):
    version_dir = _write_version(tmp_path, "acme", 1)
    metrics = compute_metrics(version_dir)
    assert metrics.exhibit_count == 0


def test_compute_metrics_ignores_bold_and_hedge_words_inside_code_fences(
    tmp_path: Path,
):
    version_dir = tmp_path / "acme.1"
    version_dir.mkdir()
    body = (
        "# acme\n\n"
        "Some prose here with no markers.\n\n"
        "```python\n"
        "# roughly speaking, **kwargs are bold-looking but not markdown\n"
        "def f(**kwargs):\n"
        "    pass\n"
        "```\n"
    )
    (version_dir / "acme.md").write_text(body, encoding="utf-8")
    metrics = compute_metrics(version_dir)
    assert metrics.bold_span_count == 0
    assert metrics.hedge_marker_count == 0


def test_compute_metrics_mean_sentence_length_excludes_headings(tmp_path: Path):
    version_dir = tmp_path / "acme.1"
    version_dir.mkdir()
    body = "# A Long Heading That Should Not Count As A Sentence\n\nOne two three four.\n"
    (version_dir / "acme.md").write_text(body, encoding="utf-8")
    metrics = compute_metrics(version_dir)
    # Exactly one 4-word sentence; the heading must not be folded in.
    assert metrics.mean_sentence_length == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# compute_drift — graceful-skip paths
# ---------------------------------------------------------------------------


def test_compute_drift_skips_first_version(tmp_path: Path):
    version_dir = _write_version(tmp_path, "acme", 1)
    result = compute_drift(version_dir)
    assert isinstance(result, VersionDriftResult)
    assert result.ran is False
    assert "N=1" in result.reason or "first version" in result.reason
    assert result.findings == []


def test_compute_drift_skips_when_prior_version_missing(tmp_path: Path):
    # acme.2 exists but acme.1 does not.
    version_dir = _write_version(tmp_path, "acme", 2)
    result = compute_drift(version_dir)
    assert result.ran is False
    assert "acme.1" in result.reason
    assert result.findings == []


def test_compute_drift_skips_when_current_body_missing(tmp_path: Path):
    _write_version(tmp_path, "acme", 1)
    version_dir = tmp_path / "acme.2"
    version_dir.mkdir()
    result = compute_drift(version_dir)
    assert result.ran is False
    assert result.findings == []


def test_compute_drift_skips_on_malformed_version_dir_name(tmp_path: Path):
    version_dir = tmp_path / "not-a-version-dir"
    version_dir.mkdir()
    result = compute_drift(version_dir)
    assert result.ran is False
    assert "naming convention" in result.reason


def test_compute_drift_runs_with_only_one_prior_transition(tmp_path: Path):
    """N-2 absent: the check runs, reports one transition, emits no findings."""
    _write_version(tmp_path, "acme", 1, bold_words=1)
    version_dir = _write_version(tmp_path, "acme", 2, bold_words=5)
    result = compute_drift(version_dir)
    assert result.ran is True
    assert result.earliest_version is None
    assert "earliest_to_prior" not in result.transitions
    assert "prior_to_current" in result.transitions
    # A single-transition increase is observational only — no finding.
    assert result.findings == []


# ---------------------------------------------------------------------------
# compute_drift — the two-transition monotonic finding rule
# ---------------------------------------------------------------------------


def test_compute_drift_fires_on_two_transition_bold_ratchet(tmp_path: Path):
    """Mirrors the issue body's canary evidence: monotonic bold-share ratchet."""
    _write_version(tmp_path, "acme", 1, bold_words=2, extra_words=40)
    _write_version(tmp_path, "acme", 2, bold_words=5, extra_words=40)
    version_dir = _write_version(tmp_path, "acme", 3, bold_words=9, extra_words=40)

    result = compute_drift(version_dir)
    assert result.ran is True
    assert result.current_version == 3
    assert result.prior_version == 2
    assert result.earliest_version == 1

    metrics_by_metric = {f.metric for f in result.findings}
    assert "bold_word_share" in metrics_by_metric
    finding = next(f for f in result.findings if f.metric == "bold_word_share")
    assert finding.severity == "major"
    assert finding.scope == "reduce"
    assert finding.versions == [1, 2, 3]
    assert "→" in finding.trajectory


def test_compute_drift_fires_on_hedge_marker_ratchet(tmp_path: Path):
    _write_version(tmp_path, "acme", 1, hedge_hits=1)
    _write_version(tmp_path, "acme", 2, hedge_hits=2)
    version_dir = _write_version(tmp_path, "acme", 3, hedge_hits=3)
    result = compute_drift(version_dir)
    assert any(f.metric == "hedge_marker_count" for f in result.findings)


def test_compute_drift_fires_on_meta_commentary_ratchet(tmp_path: Path):
    _write_version(tmp_path, "acme", 1, meta_hits=0)
    _write_version(tmp_path, "acme", 2, meta_hits=1)
    version_dir = _write_version(tmp_path, "acme", 3, meta_hits=2)
    result = compute_drift(version_dir)
    assert any(f.metric == "meta_commentary_count" for f in result.findings)


def test_compute_drift_does_not_fire_on_single_transition_increase(tmp_path: Path):
    """A dip-then-rise (only the LAST transition increases) is observational only."""
    _write_version(tmp_path, "acme", 1, bold_words=8, extra_words=40)
    _write_version(tmp_path, "acme", 2, bold_words=2, extra_words=40)  # dips
    version_dir = _write_version(
        tmp_path, "acme", 3, bold_words=5, extra_words=40
    )  # rises, but only one transition increased

    result = compute_drift(version_dir)
    assert result.ran is True
    assert result.earliest_version == 1
    # earliest->prior decreased; prior->current increased: not monotonic.
    assert result.transitions["earliest_to_prior"]["bold_word_share"]["increased"] is False
    assert result.transitions["prior_to_current"]["bold_word_share"]["increased"] is True
    assert all(f.metric != "bold_word_share" for f in result.findings)


def test_compute_drift_does_not_fire_on_non_densification_metrics(tmp_path: Path):
    """word_count / bold_span_count / mean_sentence_length / exhibit_count
    never participate in the finding rule, even when monotonically
    increasing across both transitions."""
    _write_version(tmp_path, "acme", 1, extra_words=10, exhibits=1)
    _write_version(tmp_path, "acme", 2, extra_words=40, exhibits=2)
    version_dir = _write_version(tmp_path, "acme", 3, extra_words=80, exhibits=3)

    result = compute_drift(version_dir)
    assert result.transitions["earliest_to_prior"]["word_count"]["increased"] is True
    assert result.transitions["prior_to_current"]["word_count"]["increased"] is True
    assert result.transitions["earliest_to_prior"]["exhibit_count"]["increased"] is True
    assert result.transitions["prior_to_current"]["exhibit_count"]["increased"] is True
    fired_metrics = {f.metric for f in result.findings}
    assert "word_count" not in fired_metrics
    assert "exhibit_count" not in fired_metrics
    assert "bold_span_count" not in fired_metrics
    assert "mean_sentence_length" not in fired_metrics


def test_compute_drift_stable_metrics_produce_no_findings(tmp_path: Path):
    """A thread with genuinely stable style across versions is silent."""
    _write_version(tmp_path, "acme", 1, bold_words=3, hedge_hits=1, meta_hits=0)
    _write_version(tmp_path, "acme", 2, bold_words=3, hedge_hits=1, meta_hits=0)
    version_dir = _write_version(
        tmp_path, "acme", 3, bold_words=3, hedge_hits=1, meta_hits=0
    )
    result = compute_drift(version_dir)
    assert result.ran is True
    assert result.findings == []


# ---------------------------------------------------------------------------
# to_dict() serialization
# ---------------------------------------------------------------------------


def test_to_dict_shape_when_not_ran(tmp_path: Path):
    version_dir = _write_version(tmp_path, "acme", 1)
    result = compute_drift(version_dir)
    d = result.to_dict()
    assert d == {"ran": False, "reason": result.reason}


def test_to_dict_shape_when_ran_with_findings(tmp_path: Path):
    _write_version(tmp_path, "acme", 1, bold_words=2, extra_words=40)
    _write_version(tmp_path, "acme", 2, bold_words=5, extra_words=40)
    version_dir = _write_version(tmp_path, "acme", 3, bold_words=9, extra_words=40)
    result = compute_drift(version_dir)
    d = result.to_dict()
    assert d["ran"] is True
    assert d["current_version"] == 3
    assert d["prior_version"] == 2
    assert d["earliest_version"] == 1
    assert set(d["metrics"].keys()) == {"1", "2", "3"}
    assert "prior_to_current" in d["transitions"]
    assert "earliest_to_prior" in d["transitions"]
    assert d["findings_count"] == len(d["findings"])
    assert d["findings_count"] >= 1
    for finding in d["findings"]:
        assert finding["severity"] == "major"
        assert finding["scope"] == "reduce"
