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
\@writefile{lot}{\contentsline {table}{\numberline {1}{\ignorespaces Costs}}{1}{table.caption.1}\protected@file@percent }
\@writefile{toc}{\contentsline {section}{\numberline {2}Method}{3}{section.2}\protected@file@percent }
\@writefile{lof}{\contentsline {figure}{\numberline {1}{\ignorespaces Near}}{3}{figure.caption.2}\protected@file@percent }
\@writefile{toc}{\contentsline {section}{\numberline {3}Results}{6}{section.3}\protected@file@percent }
\@writefile{lof}{\contentsline {figure}{\numberline {2}{\ignorespaces Cross}}{6}{figure.caption.3}\protected@file@percent }
\@writefile{toc}{\contentsline {section}{\numberline {A}Extra}{8}{section.A}\protected@file@percent }
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
    assert [f.section for f in floats] == ["1", "2", "3", "A"]


_AUX_NO_HYPERREF = r"""
\@writefile{toc}{\contentsline {section}{\numberline {2}Method}{3}}
\@writefile{lof}{\contentsline {figure}{\numberline {1}{\ignorespaces Near}}{3}}
\@writefile{lot}{\contentsline {table}{\numberline {1}{\ignorespaces Costs}}{iv}}
"""


def test_parse_aux_without_hyperref():
    floats, sections = fp.parse_aux(_AUX_NO_HYPERREF)
    assert [(f.kind, f.number, f.aux_page) for f in floats] == [("figure", "1", 3)]
    assert sections == [("2", 3)]  # roman-page table still dropped


def test_parse_aux_hyperref_page_not_label():
    floats, _ = fp.parse_aux(_AUX.splitlines()[4])  # Figure 1, hyperref shape
    assert [(f.number, f.aux_page) for f in floats] == [("1", 3)]


def test_parse_aux_mixed_shapes():
    floats, sections = fp.parse_aux(_AUX + _AUX_NO_HYPERREF.replace("{1}{", "{9}{"))
    assert {f.aux_page for f in floats if f.number == "9"} == {3}
    assert len(floats) == 5 and len(sections) == 5


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


_AUX_MIDPAGE = r"""
\@writefile{toc}{\contentsline {section}{\numberline {1}Intro}{1}{section.1}}
\@writefile{toc}{\contentsline {section}{\numberline {2}Method}{2}{section.2}}
\@writefile{lot}{\contentsline {table}{\numberline {1}{\ignorespaces Top}}{3}{table.caption.1}}
\@writefile{toc}{\contentsline {section}{\numberline {3}Results}{3}{section.3}}
"""


def test_float_above_midpage_section_heading_keeps_its_section():
    # Table 1 is written in section 2 and renders at the top of page 3, above
    # the heading of section 3 that starts lower on the same page.
    pages = ["Intro.\n", "Method text, see Table 1.\n", "Table 1: Top\n\n3 Results\n", "More.\n"]
    floats, _ = fp.parse_aux(_AUX_MIDPAGE)
    assert floats[0].section == "2"
    hits, _ = fp.analyze(_AUX_MIDPAGE, pages)
    assert [h for h in hits if any("section" in r for r in h.reasons)] == []


def test_float_before_first_section_falls_back_to_page():
    aux = r"\@writefile{lot}{\contentsline {table}{\numberline {1}{\ignorespaces T}}{1}{table.1}}" + _AUX_MIDPAGE
    floats, _ = fp.parse_aux(aux)
    assert floats[0].section is None
    hits, unmatched = fp.analyze(aux, ["Table 1: T\n", "x\n", "Table 1 again\n"])
    assert unmatched == [] and [h.float_section for h in hits] == ["1"]  # page-based fallback


_GLOSSARY_AUX = r"""
\@writefile{toc}{\contentsline {section}{\numberline {1}Intro}{1}{section.1}}
\@writefile{lot}{\contentsline {table}{\numberline {1}{\ignorespaces Names}}{1}{table.caption.1}}
\@writefile{lof}{\contentsline {figure}{\numberline {1}{\ignorespaces Plot}}{3}{figure.caption.2}}
"""


def test_mention_inside_another_float_is_not_first_reference():
    pages = [
        "Intro prose that runs across the full width, as Table 1 lists the names.\n\n"
        "Table 1: Names of the quantities\n\nSymbol\nFig. 1a\nsee Figure 1\n",
        "Filler prose that runs across the full width of the text block here.\n",
        "As Figure 1 shows in this long line of ordinary running prose text.\nFigure 1: Plot\n",
    ]
    hits, unmatched = fp.analyze(_GLOSSARY_AUX, pages)
    assert hits == [] and unmatched == []  # first ref is page 3, not the glossary on page 1


def test_line_initial_wrapped_mention_does_not_move_caption_page():
    aux = r"""
\@writefile{toc}{\contentsline {section}{\numberline {1}Intro}{1}{section.1}}
\@writefile{lot}{\contentsline {table}{\numberline {1}{\ignorespaces One}}{1}{table.caption.1}}
\@writefile{lot}{\contentsline {table}{\numberline {5}{\ignorespaces Five}}{3}{table.caption.5}}
"""
    pages = [
        "Table 1: One\n",
        "The shift is re-fitted in the second stage of the long analysis described in\n"
        "Table 5. The shift is re-fitted per case and reported for every run.\n",
        "Table 5: Five\n",
    ]
    captions, _, offset = fp._resolve_captions(fp.parse_aux(aux)[0], pages)
    assert {f.number: p for f, p in captions.items()} == {"1": 1, "5": 3} and offset == 0
    hits, _ = fp.analyze(aux, pages)
    assert hits == []  # mention on page 2 is next to the caption on page 3


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
