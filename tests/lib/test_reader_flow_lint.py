"""Tests for ``anvil/lib/reader_flow_lint.py`` (issue #1401).

Advisory define-before-use / variant-name / roadmap-order lint. The defect
fixture is seeded from the #1396 examples: an ``S18`` caption that precedes
its definition, "edges/unknowns/DOFs" used before they are introduced, and
an introduction whose roadmap puts accuracy before the results section the
body actually opens with.
"""

from __future__ import annotations

import json
from pathlib import Path

from anvil.lib.critics import discover_critics, load_review
from anvil.lib.reader_flow_lint import (
    CHECK_NAME,
    READER_FLOW_SUFFIX,
    RULE_DEFINE_BEFORE_USE,
    RULE_ROADMAP_ORDER,
    RULE_VARIANT_PAIR,
    check_reader_flow,
    find_reader_flow_hits_in_text,
    main,
    write_review_dir,
)
from anvil.lib.review_schema import Kind

_DEFECT_TEX = r"""\documentclass{article}
\newcommand{\dofs}{DOFs}
\begin{document}
\section{Introduction}
We solve for edges, unknowns and DOFs of the mesh.
Section~\ref{sec:accuracy} reports accuracy and Section~\ref{sec:results} the results.
\begin{figure}
\caption{Residual on S18 over the first family of meshes.}
\end{figure}
\section{Results}\label{sec:results}
The second family of meshes is harder; family a is the easy one.
\section{Accuracy}\label{sec:accuracy}
Here S18 denotes the 18-state benchmark and the degrees of freedom (DOFs) are counted.
We call these \emph{edges} the interface set.
The look-up table is large; the lookup table is cached.
\end{document}
"""

_CLEAN_TEX = r"""\documentclass{article}
\begin{document}
\section{Introduction}
Section~\ref{sec:results} reports results and Section~\ref{sec:accuracy} accuracy.
\section{Results}\label{sec:results}
We count the degrees of freedom (DOFs); the DOFs total 40. S18 denotes the 18-state benchmark.
Later S18 is reused. The lookup table is small.
\section{Accuracy}\label{sec:accuracy}
Accuracy is high.
\end{document}
"""


def _make(tmp_path: Path, body: str, name: str = "main.tex") -> Path:
    version = tmp_path / "paper" / "paper.1"
    version.mkdir(parents=True)
    (version / name).write_text(body, encoding="utf-8")
    return version


def _tokens(hits, rule):
    return {h.token for h in hits if h.rule == rule}


def test_define_before_use_positive():
    hits = find_reader_flow_hits_in_text(_DEFECT_TEX, latex=True)
    toks = _tokens(hits, RULE_DEFINE_BEFORE_USE)
    assert (
        "S18" in toks
    )  # caption before definition (caption counted at source position)
    assert "DOF" in toks
    assert "edges" in toks
    s18 = next(h for h in hits if h.token == "S18")
    assert s18.line == 8 and s18.related_line == 13


def test_define_before_use_negative():
    hits = find_reader_flow_hits_in_text(_CLEAN_TEX, latex=True)
    assert hits == []


def test_undefined_token_never_reported():
    text = "\\section{A}\nS18 is used here and S18 again, never defined.\n"
    assert find_reader_flow_hits_in_text(text, latex=True) == []


def test_macro_definition_and_preamble_ignored():
    text = (
        "\\newcommand{\\x}{S18}\n\\begin{document}\n\\section{A}\n"
        "S18 denotes the benchmark.\n\\end{document}\n"
    )
    assert find_reader_flow_hits_in_text(text, latex=True) == []


def test_math_symbol_define_before_use():
    text = (
        "\\section{A}\nFor $\\kappa$ small we win.\nHere $\\kappa$ denotes the gap.\n"
    )
    hits = find_reader_flow_hits_in_text(text, latex=True)
    assert _tokens(hits, RULE_DEFINE_BEFORE_USE) == {"$\\kappa$"}


def test_appendix_only_definition_noted():
    text = (
        "\\section{A}\nWe study the degrees of freedom here, tracked as DOFs.\n"
        "\\appendix\n\\section{B}\nThe degrees of freedom (DOFs) are listed.\n"
    )
    hits = find_reader_flow_hits_in_text(text, latex=True)
    assert len(hits) == 1 and "appendix" in hits[0].detail


def test_appendix_pointer_exempts_use():
    text = (
        "\\section{A}\nDOFs (see Appendix~B) matter.\n"
        "\\appendix\n\\section{B}\nThe degrees of freedom (DOFs) are listed.\n"
    )
    assert find_reader_flow_hits_in_text(text, latex=True) == []


def test_variant_pairs():
    hits = find_reader_flow_hits_in_text(_DEFECT_TEX, latex=True)
    toks = " | ".join(_tokens(hits, RULE_VARIANT_PAIR))
    assert "first family" in toks and "family a" in toks
    assert "look-up" in toks
    assert not _tokens(
        find_reader_flow_hits_in_text("A family a lot of times.", latex=True),
        RULE_VARIANT_PAIR,
    )


def test_roadmap_inversion_and_consistent_order():
    hits = find_reader_flow_hits_in_text(_DEFECT_TEX, latex=True)
    road = [h for h in hits if h.rule == RULE_ROADMAP_ORDER]
    assert len(road) == 1 and "Accuracy" in road[0].detail and road[0].line == 6
    assert not [
        h
        for h in find_reader_flow_hits_in_text(_CLEAN_TEX, latex=True)
        if h.rule == RULE_ROADMAP_ORDER
    ]


def test_roadmap_numeric_markdown():
    md = "# Title\n\n## Introduction\nSection 3 covers B and Section 2 covers A.\n\n## A\nx\n\n## B\ny\n"
    hits = find_reader_flow_hits_in_text(md, latex=False, path="p.md")
    assert [h.rule for h in hits] == [RULE_ROADMAP_ORDER]


def test_suppression_records_nit():
    text = _DEFECT_TEX.replace(
        "\\caption{Residual",
        "% anvil-lint-disable: reader_flow_lint\n\\caption{Residual",
    )
    hits = find_reader_flow_hits_in_text(text, latex=True)
    s18 = next(h for h in hits if h.token == "S18")
    assert s18.suppressed and s18.severity == "nit"


def test_input_children_in_document_order(tmp_path):
    version = _make(
        tmp_path, "\\begin{document}\n\\input{a}\n\\input{b}\n\\end{document}\n"
    )
    (version / "a.tex").write_text("\\section{A}\nWe use S18 here.\n")
    (version / "b.tex").write_text("\\section{B}\nS18 denotes the benchmark.\n")
    result = check_reader_flow(version)
    assert [h.token for h in result.hits] == ["S18"]
    assert result.hits[0].path == "a.tex" and result.hits[0].related_path == "b.tex"


def test_sidecar_schema_and_discovery(tmp_path):
    version = _make(tmp_path, _DEFECT_TEX)
    result = check_reader_flow(version)
    out = write_review_dir(version, result)
    assert out.parent.name == f"paper.1.{READER_FLOW_SUFFIX}"
    review = load_review(out.parent)
    assert review.kind == Kind.TOOL_EVIDENCE
    assert review.critical_flags == [] and review.scores[0].score is None
    assert review.scores[0].dimension == CHECK_NAME
    assert all(f.severity == "minor" for f in review.findings)
    assert discover_critics(version)  # picked up with no aggregator change


def test_cli_exit_codes(tmp_path, capsys):
    dirty = _make(tmp_path, _DEFECT_TEX)
    assert main([str(dirty), "--write-review"]) == 1
    assert json.loads(capsys.readouterr().out)["passed"] is False
    clean_root = tmp_path / "c"
    clean_root.mkdir()
    assert main([str(_make(clean_root, _CLEAN_TEX))]) == 0
    assert main([str(tmp_path / "missing")]) == 2
