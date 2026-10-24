"""Tests for ``anvil/lib/float_proximity.py`` (issue #1398).

Synthetic aux + per-page PDF-text pairs: near / far / cross-section floats,
multi-ref floats, ``figure*``-style numbering, appendix floats, printed-page
offset, and fail-open when the aux/PDF is missing.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib import float_proximity as fp
from anvil.lib.critics import discover_critics
from anvil.lib.review_schema import Review

_AUX = r"""
\@writefile{toc}{\contentsline {section}{\numberline {1}Intro}{1}{section.1}\protected@file@percent }
\@writefile{toc}{\contentsline {section}{\numberline {2}Method}{3}{section.2}\protected@file@percent }
\@writefile{toc}{\contentsline {section}{\numberline {3}Results}{6}{section.3}\protected@file@percent }
\@writefile{toc}{\contentsline {section}{\numberline {A}Extra}{8}{section.A}\protected@file@percent }
\@writefile{lot}{\contentsline {table}{\numberline {1}{\ignorespaces Costs}}{1}{table.caption.1}\protected@file@percent }
\@writefile{lof}{\contentsline {figure}{\numberline {1}{\ignorespaces Near}}{3}{figure.caption.2}\protected@file@percent }
\@writefile{lof}{\contentsline {figure}{\numberline {2}{\ignorespaces Cross}}{6}{figure.caption.3}\protected@file@percent }
\@writefile{lof}{\contentsline {figure}{\numberline {3}{\ignorespaces App}}{8}{figure.caption.4}\protected@file@percent }
"""

_PAGES = [
    "Intro text.\nTable 1: Costs\n",  # 1: Table 1 caption
    "Filler.\n",  # 2
    "As Figure 1 shows, it is good.\nFigure 1: Near\n",  # 3
    "Method text mentions Table 1 here.\n",  # 4: first ref of Table 1
    "Method text, see Fig. 2 for cross.\n",  # 5
    "Results.\nFigure 2: Cross\n",  # 6
    "More.\n",  # 7
    "Appendix.\nFigure 3: App\nSee Figure 3.\n",  # 8
]


def test_parse_aux():
    floats, sections = fp.parse_aux(_AUX)
    assert [(f.kind, f.number, f.aux_page) for f in floats] == [
        ("table", "1", 1), ("figure", "1", 3), ("figure", "2", 6), ("figure", "3", 8)
    ]
    assert sections == [("1", 1), ("2", 3), ("3", 6), ("A", 8)]


def test_far_near_cross_and_appendix():
    hits, unmatched = fp.analyze(_AUX, _PAGES)
    by = {h.name: h for h in hits}
    assert set(by) == {"Table 1", "Figure 2"}  # Figure 1 near; Figure 3 appendix
    assert by["Table 1"].float_page == 1 and by["Table 1"].ref_page == 4
    assert "3 pages" in by["Table 1"].reasons[0]
    assert any("section 3" in r and "section 2" in r for r in by["Figure 2"].reasons)
    assert unmatched == []


def test_multi_ref_uses_first_reference_only():
    pages = list(_PAGES)
    pages[1] = "Early mention of Table 1 on page two.\n"
    hits, _ = fp.analyze(_AUX, pages)
    assert "Table 1" not in {h.name for h in hits}


def test_caption_line_is_not_a_reference():
    # Float on page 1; only the caption mentions it -> unmatched, not reported.
    pages = list(_PAGES)
    pages[3] = "Nothing here.\n"
    hits, unmatched = fp.analyze(_AUX, pages)
    assert "Table 1" in unmatched and "Table 1" not in {h.name for h in hits}


def test_printed_page_offset_is_absorbed():
    pages = ["Cover page.\n"] + _PAGES  # pdf index = printed + 1
    hits, _ = fp.analyze(_AUX, pages)
    assert {h.name for h in hits} == {"Table 1", "Figure 2"}
    assert {h.name: h.float_page for h in hits}["Table 1"] == 2


def _version(tmp_path: Path) -> Path:
    v = tmp_path / "paper" / "paper.1"
    v.mkdir(parents=True)
    (v / "main.tex").write_text("\\documentclass{article}\n", encoding="utf-8")
    return v


def test_fail_open_without_aux_or_pdf(tmp_path):
    v = _version(tmp_path)
    r = fp.check_float_proximity(v)
    assert r.skipped_reason == fp.REASON_NO_AUX and r.passed()
    (v / "main.aux").write_text(_AUX, encoding="utf-8")
    assert fp.check_float_proximity(v).skipped_reason == fp.REASON_NO_PDF


def test_file_entry_point_and_sidecar(tmp_path, monkeypatch):
    v = _version(tmp_path)
    (v / "main.aux").write_text(_AUX, encoding="utf-8")
    (v / "main.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(fp, "_extract_pdf_text", lambda p: "\f".join(_PAGES) + "\f")
    r = fp.check_float_proximity(v)
    assert {h.name for h in r.hits} == {"Table 1", "Figure 2"}
    out = fp.write_review_dir(v, r)
    assert out == v.parent / f"{v.name}.floats" / "_review.json"
    review = Review.model_validate_json(out.read_text(encoding="utf-8"))
    assert review.critical_flags == [] and review.scores[0].score is None
    assert {f.severity for f in review.findings} == {"minor"}
    assert out.parent in discover_critics(v)


def test_skipped_sidecar_states_note(tmp_path):
    v = _version(tmp_path)
    out = fp.write_review_dir(v, fp.check_float_proximity(v))
    review = Review.model_validate_json(out.read_text(encoding="utf-8"))
    assert review.findings == [] and "skipped" in review.scores[0].justification
    assert fp.main([str(v)]) == 0
