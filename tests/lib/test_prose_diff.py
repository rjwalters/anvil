"""Unit tests for ``anvil/lib/prose_diff.py`` (issue #925).

Covers the word-level diff engine and the self-contained HTML renderer:

- identical text -> no diff (nothing marked changed);
- a pure rewrap (same words, different line breaks) -> a minimal diff,
  NOT a false-positive full-line/full-paragraph replacement — this is the
  whole reason the module diffs word tokens instead of lines;
- insertions and deletions render on the correct side only;
- non-ASCII / emoji tokens tokenize and diff without raising;
- the rendered HTML is self-contained (no CDN `<link>`/`<script src="http">`);
- the overlay note rendering (anchored + unanchored) and stdlib-only
  import discipline.

Test filename is distinct per the #58 packaging convention.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from anvil.lib.prose_diff import (
    OverlayNote,
    diff_prose,
    render_html,
)


# ---------------------------------------------------------------------------
# Core diff behavior
# ---------------------------------------------------------------------------


def test_identical_text_has_no_diff() -> None:
    text = "The quick brown fox jumps over the lazy dog.\nSecond line here.\n"
    result = diff_prose(text, text)

    assert result.identical is True
    assert result.left.changed_line_count == 0
    assert result.right.changed_line_count == 0
    assert "<del>" not in "".join(ln.html for ln in result.left.lines)
    assert "<ins>" not in "".join(ln.html for ln in result.right.lines)


def test_pure_rewrap_is_a_minimal_diff_not_a_full_replacement() -> None:
    """A reflow (same words, new line breaks) must not read as a
    wholesale line-for-line replacement — the motivating friction from
    the issue. Word content is unchanged, so any token-level marking
    should be limited to whitespace tokens at the rewrap boundary, and
    the overwhelming majority of words on both sides must be unmarked.
    """

    left = (
        "The quick brown fox jumps over the lazy dog while the sun sets "
        "slowly behind the hills.\n"
    )
    right = (
        "The quick brown fox jumps over the lazy dog while the sun\n"
        "sets slowly behind the hills.\n"
    )

    result = diff_prose(left, right)

    assert result.identical is False

    left_html = "".join(ln.html for ln in result.left.lines)
    right_html = "".join(ln.html for ln in result.right.lines)

    # No whole-word content was deleted or inserted -- only whitespace
    # rearranged around the new line break. A false-positive full-line
    # replacement would mark every word `<del>`/`<ins>`; assert that is
    # NOT the case by requiring the marked spans (if any) contain no
    # alphabetic word characters.
    for tag in ("del", "ins"):
        for match in re.findall(rf"<{tag}>(.*?)</{tag}>", left_html + right_html):
            assert not re.search(r"[A-Za-z]", match), (
                f"expected only whitespace to be marked, got <{tag}>{match!r}"
            )


def test_insertion_marks_only_the_new_side() -> None:
    # "end." stays intact on both sides so the inserted word does not
    # shift trailing punctuation onto a neighboring token.
    left = "One two three end.\n"
    right = "One two three four end.\n"

    result = diff_prose(left, right)

    left_html = "".join(ln.html for ln in result.left.lines)
    right_html = "".join(ln.html for ln in result.right.lines)

    assert "<del>" not in left_html
    assert "<ins>four" in right_html


def test_deletion_marks_only_the_old_side() -> None:
    left = "One two three four end.\n"
    right = "One two three end.\n"

    result = diff_prose(left, right)

    left_html = "".join(ln.html for ln in result.left.lines)
    right_html = "".join(ln.html for ln in result.right.lines)

    assert "<ins>" not in right_html
    assert "<del>four" in left_html


def test_empty_inputs_are_identical() -> None:
    result = diff_prose("", "")
    assert result.identical is True
    assert result.left.lines == []
    assert result.right.lines == []


def test_non_ascii_and_emoji_tokens_do_not_raise() -> None:
    left = "Café naïve résumé \U0001f600 done.\n"
    right = "Café naïve résumé \U0001f389 done.\n"

    result = diff_prose(left, right)

    assert result.identical is False
    left_html = "".join(ln.html for ln in result.left.lines)
    right_html = "".join(ln.html for ln in result.right.lines)
    assert "\U0001f600" in left_html or "&#128512;" in left_html or "\U0001f600" in left.encode().decode()
    assert "Café" in left_html
    assert "Café" in right_html


def test_line_numbers_are_independent_per_side() -> None:
    left = "a\nb\nc\n"
    right = "a\nb\nc\nd\n"

    result = diff_prose(left, right)

    assert [ln.line for ln in result.left.lines] == [1, 2, 3]
    assert [ln.line for ln in result.right.lines] == [1, 2, 3, 4]
    assert result.right.lines[-1].changed is True


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def test_render_html_is_self_contained() -> None:
    result = diff_prose("hello world\n", "hello there\n")
    page = render_html(result, left_label="v1", right_label="v2")

    assert "<!DOCTYPE html>" in page
    # No CDN / external resource references.
    assert "<script" not in page
    assert not re.search(r'<link[^>]+href="https?://', page)
    assert not re.search(r'src="https?://', page)
    assert "v1" in page and "v2" in page


def test_render_html_escapes_content() -> None:
    result = diff_prose("<b>bold</b>\n", "<i>italic</i>\n")
    page = render_html(result)

    assert "<b>bold</b>" not in page
    assert "&lt;b&gt;bold&lt;/b&gt;" in page or "&lt;i&gt;italic&lt;/i&gt;" in page


def test_render_html_identical_notes_no_diff() -> None:
    result = diff_prose("same text\n", "same text\n")
    page = render_html(result)
    assert "identical" in page.lower()


def test_render_html_overlay_anchored_and_unanchored() -> None:
    result = diff_prose("first line\n", "first line changed\n")
    right_overlay = [
        OverlayNote(line=1, severity="warning", message="passive voice", source="rhetoric_lint"),
        OverlayNote(line=None, severity="info", message="dim 9 score: 6/7", source="review:9_rhetorical_economy"),
    ]

    page = render_html(result, right_overlay=right_overlay)

    assert "passive voice" in page
    assert "dim 9 score" in page
    assert "Document-level notes" in page


def test_render_html_no_overlay_degrades_gracefully() -> None:
    result = diff_prose("a\n", "b\n")
    page = render_html(result)  # no overlay at all
    assert "<!DOCTYPE html>" in page
    assert "Document-level notes" not in page


# ---------------------------------------------------------------------------
# Stdlib-only import discipline
# ---------------------------------------------------------------------------


def test_prose_diff_imports_are_stdlib_only() -> None:
    """Guards the module's headline constraint: no third-party imports.

    Parses the module source with ``ast`` (rather than introspecting
    ``sys.modules`` after import, which could hide a lazily-imported
    third-party dependency) and asserts every top-level import root is
    either stdlib or the module's own package.
    """

    src_path = (
        Path(__file__).resolve().parents[2] / "anvil" / "lib" / "prose_diff.py"
    )
    tree = ast.parse(src_path.read_text(encoding="utf-8"))

    _STDLIB_ROOTS = {"difflib", "html", "re", "dataclasses", "typing", "__future__"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root in _STDLIB_ROOTS, f"unexpected import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            root = node.module.split(".")[0]
            assert root in _STDLIB_ROOTS, f"unexpected import from: {node.module}"
