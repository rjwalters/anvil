"""Tests for ``anvil/lib/numeral_multiset.py`` (issue #1400)."""

from __future__ import annotations

from collections import Counter

from anvil.lib.numeral_multiset import diff_multisets, main, numeral_multiset

OLD = "We ran 12 trials.\n\nAccuracy was 87.3\\% on 1,000 samples.\n"


def test_reorder_is_identical():
    new = "Accuracy was 87.3\\% on 1000 samples.\n\nWe ran 12 trials.\n"
    d = diff_multisets(OLD, new)
    assert d.passed()
    assert d.to_markdown().startswith("numeral multiset: identical")


def test_removed_numeral():
    d = diff_multisets(OLD, "We ran 12 trials.\n\nAccuracy was 87.3\\%.\n")
    assert d.removed == {"1000": 1}
    assert d.added == {}
    assert not d.passed()


def test_added_numeral_and_count_change():
    d = diff_multisets(OLD, OLD + "We ran 12 more.\n")
    assert d.added == {"12": 1}
    assert d.removed == {}


def test_decimal_not_split():
    assert numeral_multiset("p = 0.05") == Counter({"0.05": 1})


def test_comments_and_ref_args_ignored():
    text = "See Table~\\ref{tab:2} \\cite{li2020} \\label{sec:3} % 99 draft\nCount 5.\n"
    assert numeral_multiset(text) == Counter({"5": 1})


def test_math_counted_by_default_and_strippable():
    text = "Bound $x < 0.5$ and 7 runs."
    assert numeral_multiset(text) == Counter({"0.5": 1, "7": 1})
    assert numeral_multiset(text, strip_math=True) == Counter({"7": 1})


def test_equation_env_strippable():
    text = "A.\n\\begin{equation}\ny = 3x\n\\end{equation}\nB 4."
    assert numeral_multiset(text, strip_math=True) == Counter({"4": 1})


def test_empty_inputs_clean():
    assert diff_multisets("", "").passed()


def test_cli_exit_codes(tmp_path, capsys):
    a = tmp_path / "a.tex"
    b = tmp_path / "b.tex"
    a.write_text("1 2 3", encoding="utf-8")
    b.write_text("3 2 1", encoding="utf-8")
    assert main([str(a), str(b)]) == 0
    b.write_text("3 2", encoding="utf-8")
    assert main([str(a), str(b)]) == 1
    assert "removed: `1`" in capsys.readouterr().out
    assert main([str(a), str(tmp_path / "missing.tex")]) == 2
