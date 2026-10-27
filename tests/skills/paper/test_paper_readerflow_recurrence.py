"""Unit tests for the reader-flow recurrence measure (issue #1419)."""

from __future__ import annotations

from anvil.skills.paper.lib.readerflow_recurrence import recurrence


def f(span, severity="minor", dim="7"):
    return {"severity": severity, "dimension": dim, "evidence_span": span}


def test_exact_match():
    r = recurrence([f("cites design A (Section 5) before Section 5")],
                   [f("cites design A (Section 5) before Section 5")])
    assert r == {"prior_total": 1, "recurring": 1, "share": 1.0}


def test_near_match_whitespace_and_case():
    r = recurrence([f("the intro says five words")],
                   [f("The intro  says\nFive words.")])
    assert r["recurring"] == 1


def test_no_match():
    r = recurrence([f("abstract 2.70/4.11")], [f("Fig 3 placement far from text")])
    assert r == {"prior_total": 1, "recurring": 0, "share": 0.0}


def test_containment_requires_same_dimension():
    prior = [f("Table 6", dim="7")]
    cur_same = [f("Table 6 lists six rows but intro says five", dim="7")]
    cur_other = [f("Table 6 lists six rows but intro says five", dim="3")]
    assert recurrence(prior, cur_same)["recurring"] == 1
    assert recurrence(prior, cur_other)["recurring"] == 0


def test_nit_excluded_from_prior_total():
    r = recurrence([f("a b c", "nit"), f("x y z", "major")], [f("x y z")])
    assert r == {"prior_total": 1, "recurring": 1, "share": 1.0}


def test_empty_or_all_nit_prior_returns_none():
    assert recurrence([], [f("a")]) is None
    assert recurrence([f("a", "nit")], [f("a")]) is None


def test_one_to_one_matching():
    prior = [f("same span here"), f("same span here")]
    r = recurrence(prior, [f("same span here")])
    assert r["prior_total"] == 2 and r["recurring"] == 1 and r["share"] == 0.5


def test_span_reordering_in_lists():
    prior = [f("alpha beta gamma"), f("delta epsilon zeta")]
    cur = [f("delta epsilon zeta"), f("unrelated"), f("alpha beta gamma")]
    assert recurrence(prior, cur)["recurring"] == 2


def test_missing_span_never_matches():
    assert recurrence([f(None)], [f(None)])["recurring"] == 0


def test_accepts_finding_models():
    from anvil.lib.review_schema import Finding

    mk = lambda s: Finding(severity="minor", dimension="7", evidence_span=s,
                           rationale="r", suggested_fix="x")
    assert recurrence([mk("abc def")], [mk("abc def")])["share"] == 1.0
