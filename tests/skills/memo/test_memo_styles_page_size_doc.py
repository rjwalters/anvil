"""Doc-level regression guard for the memo ``styles.css`` ``@page`` size
(issue #232).

WeasyPrint 68+ on macOS Homebrew silently ignores the named-keyword form
``size: letter;`` and falls back to A4 (595x842 pts), violating the
README's pinned US-Letter contract. The fix is to use the explicit
two-dimension form ``size: 8.5in 11in;`` which is portable across
WeasyPrint versions.

This test reads ``anvil/lib/memo/styles.css``, locates the ``@page``
block, and asserts:

1. The block contains the explicit ``8.5in 11in`` dimension form.
2. The block does NOT contain the bare ``size: letter`` keyword form
   (a future revert to the named-keyword shape is caught at CI time).

The ``xelatex`` fallback path is intentionally untested here — it reads
pandoc's ``--variable=papersize`` chain, not the CSS ``@page`` rule, so
the CSS is the single source of truth for the weasyprint path.

Per-skill test filename convention (#58): this file is named
``test_memo_styles_page_size_doc.py`` so pytest does not collide with
any parallel ``test_styles_*.py`` another skill might pick.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STYLES_CSS = REPO_ROOT / "anvil" / "lib" / "memo" / "styles.css"


def _read_page_block() -> str:
    """Return the body of the first ``@page { ... }`` block in styles.css.

    The block-extraction is brace-counting (not regex-only) so a nested
    ``@bottom-center { ... }`` rule inside the block doesn't terminate
    the outer match early.
    """
    text = STYLES_CSS.read_text(encoding="utf-8")
    start_match = re.search(r"@page\s*\{", text)
    assert start_match is not None, (
        f"styles.css at {STYLES_CSS} has no @page block — has the file "
        f"been restructured? Update this test if so."
    )
    i = start_match.end()
    depth = 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    assert depth == 0, (
        f"styles.css @page block has unbalanced braces at offset "
        f"{start_match.start()} — fix the CSS, then rerun this test."
    )
    return text[start_match.end() : i - 1]


def test_styles_css_page_block_uses_explicit_us_letter_dims() -> None:
    """The ``@page`` block ships the explicit ``8.5in 11in`` dim form."""
    block = _read_page_block()
    assert "8.5in 11in" in block, (
        f"styles.css @page block does not contain the explicit "
        f"'8.5in 11in' US-Letter dimension form. WeasyPrint 68+ ignores "
        f"the named-keyword 'letter' fallback (see issue #232). Restore "
        f"the explicit dims form."
    )


def test_styles_css_page_block_avoids_bare_letter_keyword() -> None:
    """The bare ``size: letter`` keyword form must not return.

    The explicit-dims form makes the named-keyword path unnecessary on
    every WeasyPrint version, and the named-keyword form silently
    breaks on WeasyPrint 68+ (issue #232). Reject the regression.
    """
    block = _read_page_block()
    # Match ``size: letter`` with optional whitespace + terminator, but
    # NOT ``size: letter portrait`` (a CSS shape we'd treat the same).
    # The bare-keyword regression is the specific shape we care about.
    bare_keyword = re.search(
        r"size\s*:\s*letter\s*(?:;|$)",
        block,
        flags=re.MULTILINE,
    )
    assert bare_keyword is None, (
        f"styles.css @page block contains the bare 'size: letter' "
        f"keyword form, which WeasyPrint 68+ silently ignores (issue "
        f"#232). Use the explicit '8.5in 11in' dimension form instead."
    )
