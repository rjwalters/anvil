r"""Tests for ``anvil/lib/tex_includes.py`` (issue #643).

Covers the acceptance criteria + test plan from the issue:

- ``.tex`` extension defaulting: ``\input{x}`` → ``x.tex``;
  ``\input{x.tex}`` stays ``x.tex`` (no ``.tex.tex`` doubling).
- Nested ``\input`` is walked recursively (a child that itself
  ``\input``s further files).
- LaTeX-comment-masked ``\input`` (after an unescaped ``%``) is NOT
  resolved; an escaped ``\%`` does not start a comment.
- Missing-file target is surfaced in ``ResolvedTex.missing`` without
  crashing.
- Cyclic ``\input`` pair does not infinite-loop.
- ``\include`` (braced) is recognized alongside ``\input``.
- Brace-less ``\input path`` (TeX form) is recognized.
- Fixture-based integration: a three-file tree (``main.tex`` →
  ``intro.tex`` + ``method.tex`` → ``method-details.tex``) resolves the
  concatenated body from all three children.
- Regression: a single-file thread (no ``\input``/``\include``) resolves
  to just ``main.tex`` — the body degrades to the master alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.lib.tex_includes import ResolvedTex, resolve_tex_inputs


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# .tex extension defaulting
# ---------------------------------------------------------------------------


def test_extension_defaulting_no_suffix(tmp_path):
    r"""``\input{sections/intro}`` resolves to ``sections/intro.tex``."""
    _write(tmp_path / "sections" / "intro.tex", "Intro body.\n")
    master = _write(tmp_path / "main.tex", r"\input{sections/intro}" + "\n")
    result = resolve_tex_inputs(master)
    names = [f.name for f in result.files]
    assert names == ["main.tex", "intro.tex"]
    assert "Intro body." in result.body
    assert not result.has_missing


def test_extension_defaulting_explicit_suffix_not_doubled(tmp_path):
    r"""``\input{sections/intro.tex}`` must NOT become ``intro.tex.tex``."""
    _write(tmp_path / "sections" / "intro.tex", "Intro body.\n")
    master = _write(tmp_path / "main.tex", r"\input{sections/intro.tex}" + "\n")
    result = resolve_tex_inputs(master)
    assert [f.name for f in result.files] == ["main.tex", "intro.tex"]
    assert "Intro body." in result.body
    assert not result.has_missing
    # The pathological doubled path must never appear as a resolved file.
    assert not (tmp_path / "sections" / "intro.tex.tex").exists()


# ---------------------------------------------------------------------------
# Nested \input
# ---------------------------------------------------------------------------


def test_nested_input_walked_recursively(tmp_path):
    r"""A child that itself ``\input``s further files is walked."""
    _write(
        tmp_path / "sections" / "method-details.tex",
        "Hyperparameters: lr=0.01.\n",
    )
    _write(
        tmp_path / "sections" / "method.tex",
        "Method overview.\n" + r"\input{sections/method-details}" + "\n",
    )
    master = _write(tmp_path / "main.tex", r"\input{sections/method}" + "\n")
    result = resolve_tex_inputs(master)
    assert [f.name for f in result.files] == [
        "main.tex",
        "method.tex",
        "method-details.tex",
    ]
    assert "Method overview." in result.body
    assert "Hyperparameters: lr=0.01." in result.body


# ---------------------------------------------------------------------------
# LaTeX-comment masking
# ---------------------------------------------------------------------------


def test_commented_input_not_resolved(tmp_path):
    r"""``% \input{...}`` after an unescaped ``%`` is NOT resolved."""
    _write(tmp_path / "sections" / "intro.tex", "Real intro.\n")
    _write(tmp_path / "sections" / "dead.tex", "Dead section.\n")
    master = _write(
        tmp_path / "main.tex",
        r"\input{sections/intro}" + "\n"
        + r"% \input{sections/dead}" + "\n",
    )
    result = resolve_tex_inputs(master)
    names = [f.name for f in result.files]
    assert "intro.tex" in names
    assert "dead.tex" not in names, "commented-out \\input must not resolve"
    assert "Dead section." not in result.body
    assert not result.has_missing


def test_inline_trailing_comment_masks_input(tmp_path):
    r"""An ``\input`` after a mid-line ``%`` comment is masked."""
    _write(tmp_path / "sections" / "intro.tex", "Real intro.\n")
    _write(tmp_path / "sections" / "dead.tex", "Dead section.\n")
    master = _write(
        tmp_path / "main.tex",
        r"\input{sections/intro} % then \input{sections/dead}" + "\n",
    )
    result = resolve_tex_inputs(master)
    names = [f.name for f in result.files]
    assert names == ["main.tex", "intro.tex"]
    assert "Dead section." not in result.body


def test_escaped_percent_does_not_start_comment(tmp_path):
    r"""``\%`` is a literal percent — a following ``\input`` still resolves."""
    _write(tmp_path / "sections" / "intro.tex", "Real intro.\n")
    master = _write(
        tmp_path / "main.tex",
        r"A 50\% gain. \input{sections/intro}" + "\n",
    )
    result = resolve_tex_inputs(master)
    assert [f.name for f in result.files] == ["main.tex", "intro.tex"]
    assert "Real intro." in result.body


# ---------------------------------------------------------------------------
# Missing-file target
# ---------------------------------------------------------------------------


def test_missing_target_surfaced_not_crashing(tmp_path):
    r"""A dangling ``\input`` is surfaced in ``missing``, never raised."""
    master = _write(tmp_path / "main.tex", r"\input{sections/nope}" + "\n")
    result = resolve_tex_inputs(master)  # must not raise
    assert [f.name for f in result.files] == ["main.tex"]
    assert result.has_missing
    assert len(result.missing) == 1
    target, including = result.missing[0]
    assert target == "sections/nope"
    assert including.endswith("main.tex")


def test_partial_tree_resolves_present_children(tmp_path):
    r"""A present child resolves even when a sibling ``\input`` dangles."""
    _write(tmp_path / "sections" / "intro.tex", "Real intro.\n")
    master = _write(
        tmp_path / "main.tex",
        r"\input{sections/intro}" + "\n" + r"\input{sections/gone}" + "\n",
    )
    result = resolve_tex_inputs(master)
    assert [f.name for f in result.files] == ["main.tex", "intro.tex"]
    assert result.has_missing
    assert result.missing[0][0] == "sections/gone"


# ---------------------------------------------------------------------------
# Cycle guard
# ---------------------------------------------------------------------------


def test_cyclic_input_does_not_infinite_loop(tmp_path):
    r"""Two files ``\input``-ing each other are each walked once."""
    _write(tmp_path / "a.tex", r"A body. \input{b}" + "\n")
    _write(tmp_path / "b.tex", r"B body. \input{a}" + "\n")
    master = _write(tmp_path / "main.tex", r"\input{a}" + "\n")
    result = resolve_tex_inputs(master)  # must terminate
    names = [f.name for f in result.files]
    # Each file appears exactly once despite the cycle.
    assert names == ["main.tex", "a.tex", "b.tex"]
    assert names.count("a.tex") == 1
    assert names.count("b.tex") == 1
    assert "A body." in result.body
    assert "B body." in result.body


def test_repeated_include_deduplicated(tmp_path):
    r"""A file ``\input``-ed twice appears once, at first-seen position."""
    _write(tmp_path / "shared.tex", "Shared macros.\n")
    master = _write(
        tmp_path / "main.tex",
        r"\input{shared}" + "\n" + r"\input{shared}" + "\n",
    )
    result = resolve_tex_inputs(master)
    assert [f.name for f in result.files] == ["main.tex", "shared.tex"]


# ---------------------------------------------------------------------------
# \include and brace-less \input
# ---------------------------------------------------------------------------


def test_include_recognized(tmp_path):
    r"""``\include{path}`` is recognized alongside ``\input``."""
    _write(tmp_path / "chapter1.tex", "Chapter one.\n")
    master = _write(tmp_path / "main.tex", r"\include{chapter1}" + "\n")
    result = resolve_tex_inputs(master)
    assert [f.name for f in result.files] == ["main.tex", "chapter1.tex"]
    assert "Chapter one." in result.body


def test_braceless_input_recognized(tmp_path):
    r"""The TeX brace-less ``\input path`` form is recognized."""
    _write(tmp_path / "intro.tex", "Braceless intro.\n")
    master = _write(tmp_path / "main.tex", r"\input intro" + "\n")
    result = resolve_tex_inputs(master)
    assert [f.name for f in result.files] == ["main.tex", "intro.tex"]
    assert "Braceless intro." in result.body


# ---------------------------------------------------------------------------
# Fixture-based integration (test-plan §2)
# ---------------------------------------------------------------------------


def test_full_tree_body_concatenation(tmp_path):
    r"""main.tex \input-ing intro + method, method \input-ing details:
    the resolved body includes content from all three children."""
    _write(tmp_path / "sections" / "intro.tex", "INTRO_MARKER contribution.\n")
    _write(
        tmp_path / "sections" / "method-details.tex",
        "DETAILS_MARKER seed=42.\n",
    )
    _write(
        tmp_path / "sections" / "method.tex",
        "METHOD_MARKER pipeline.\n"
        + r"\input{sections/method-details}" + "\n",
    )
    master = _write(
        tmp_path / "main.tex",
        r"\documentclass{article}\begin{document}" + "\n"
        + r"\input{sections/intro}" + "\n"
        + r"\input{sections/method}" + "\n"
        + r"\end{document}" + "\n",
    )
    result = resolve_tex_inputs(master)
    assert len(result.files) == 4
    for marker in ("INTRO_MARKER", "METHOD_MARKER", "DETAILS_MARKER"):
        assert marker in result.body, f"{marker} missing from resolved body"
    # Document order: master, intro, method, method-details.
    assert [f.name for f in result.files] == [
        "main.tex",
        "intro.tex",
        "method.tex",
        "method-details.tex",
    ]


# ---------------------------------------------------------------------------
# Regression: single-file thread degrades to main.tex alone
# ---------------------------------------------------------------------------


def test_single_file_thread_no_children(tmp_path):
    r"""A thread with no ``\input``/``\include`` resolves to just main.tex."""
    master = _write(
        tmp_path / "main.tex",
        r"\documentclass{article}\begin{document}Body only.\end{document}"
        + "\n",
    )
    result = resolve_tex_inputs(master)
    assert isinstance(result, ResolvedTex)
    assert [f.name for f in result.files] == ["main.tex"]
    assert "Body only." in result.body
    assert not result.has_missing


# ---------------------------------------------------------------------------
# Error handling: missing master
# ---------------------------------------------------------------------------


def test_missing_master_raises(tmp_path):
    r"""A missing MASTER file raises (distinct from a missing child)."""
    with pytest.raises(FileNotFoundError):
        resolve_tex_inputs(tmp_path / "does-not-exist.tex")
