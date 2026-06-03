"""Regression tests for the booktabs-class table block in
``anvil/lib/memo/styles.css`` (#238).

The default memo `styles.css` is deliberately minimal (no color, no
logos, no `@font-face`, no decorative rules) — see
``anvil/lib/memo/README.md`` §"Maintainer policy on aesthetic PRs".
The booktabs-class table styling shipped in #238 is the narrow
carve-out from that policy: comparison tables in synthesis / feedback
memos carry rhetorical load, and the LaTeX fallback already emits
booktabs-quality output via ``template.tex``, so the markdown render
path tracks that quality via the `table`-block ruleset.

These tests are grep-the-file shape (mirrors
``tests/skills/memo/test_memo_render_doc.py``) so a later
aesthetic-minimization PR can't silently revert the booktabs rules.
They assert on the LOAD-BEARING selectors and property values, not on
whitespace or comment text — the contract is the rendered output, not
the source formatting.

Per the #58 packaging convention, this filename is distinct from the
neighboring ``test_memo_render_detection.py`` (renderer availability
checks) and ``test_render_gate_memo.py`` (render-gate primitive).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from anvil.lib import render as _render


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def styles_css_text() -> str:
    """Return the shipped ``anvil/lib/memo/styles.css`` text.

    Resolved from the installed package path so the test passes both in
    the dev tree (``anvil/lib/memo/styles.css``) and against an
    installed consumer repo.
    """
    css = Path(_render.__file__).parent / "memo" / "styles.css"
    assert css.exists(), f"missing pinned theme: {css}"
    return css.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Booktabs selectors — the contract
# ---------------------------------------------------------------------------


def test_table_uses_border_collapse(styles_css_text: str):
    """The ``table`` block keeps ``border-collapse: collapse`` so the
    booktabs-class rule weights paint without doubling up on internal
    borders.
    """
    assert re.search(
        r"table\s*\{[^}]*border-collapse:\s*collapse", styles_css_text
    ), "table block must set border-collapse: collapse"


def test_table_spans_full_width(styles_css_text: str):
    """The ``table`` block sets ``width: 100%`` so the booktabs rules
    span the printable text column edge-to-edge — matching the LaTeX
    booktabs convention.
    """
    assert re.search(
        r"table\s*\{[^}]*width:\s*100%", styles_css_text
    ), "table block must set width: 100% for full-width booktabs rules"


def test_thead_th_has_top_rule(styles_css_text: str):
    """The header cells get a ``border-top`` (the booktabs ``\\toprule``
    analog). The exact weight is a tunable; the contract is "there is a
    top rule on the header".
    """
    assert re.search(
        r"thead\s+th\s*\{[^}]*border-top:\s*[^;]+solid", styles_css_text
    ), "thead th must set a solid border-top (booktabs \\toprule analog)"


def test_thead_th_has_bottom_rule(styles_css_text: str):
    """The header cells get a ``border-bottom`` (the booktabs
    ``\\midrule`` analog separating header from body).
    """
    assert re.search(
        r"thead\s+th\s*\{[^}]*border-bottom:\s*[^;]+solid", styles_css_text
    ), "thead th must set a solid border-bottom (booktabs \\midrule analog)"


def test_thead_th_is_bold(styles_css_text: str):
    """Header cells stay bold so the heading row reads as a heading,
    not as data. Booktabs convention.
    """
    assert re.search(
        r"thead\s+th\s*\{[^}]*font-weight:\s*bold", styles_css_text
    ), "thead th must be bold"


def test_tbody_td_has_no_border(styles_css_text: str):
    """The data cells get ``border: none`` — no vertical rules, no
    internal horizontal rules. Booktabs explicitly forbids both.
    """
    assert re.search(
        r"tbody\s+td\s*\{[^}]*border:\s*none", styles_css_text
    ), "tbody td must explicitly clear borders (no vertical rules)"


def test_tbody_td_uses_tabular_nums(styles_css_text: str):
    """Data cells get ``font-variant-numeric: tabular-nums`` so numeric
    columns line up at the digit position. The other half of the
    booktabs "comparison tables read cleanly" effect.
    """
    assert re.search(
        r"tbody\s+td\s*\{[^}]*font-variant-numeric:\s*tabular-nums",
        styles_css_text,
    ), "tbody td must set font-variant-numeric: tabular-nums"


def test_final_row_has_bottom_rule(styles_css_text: str):
    """The last data row gets a ``border-bottom`` (the booktabs
    ``\\bottomrule`` analog closing the table). The selector must
    target ``tbody tr:last-child td`` so it paints under the final row
    regardless of how many rows the table has.
    """
    assert re.search(
        r"tbody\s+tr:last-child\s+td\s*\{[^}]*border-bottom:\s*[^;]+solid",
        styles_css_text,
    ), (
        "tbody tr:last-child td must set a solid border-bottom "
        "(booktabs \\bottomrule analog)"
    )


# ---------------------------------------------------------------------------
# Anti-patterns — what booktabs explicitly forbids
# ---------------------------------------------------------------------------


def test_no_header_background_fill(styles_css_text: str):
    """The header row must NOT have a colored background fill.
    Booktabs convention is rule-weights, not background shading; the
    README's "no color" pin reinforces this.

    We check the ``thead th`` block (and the legacy ``th`` block, if
    re-introduced) for any ``background`` declaration.
    """
    # Search only inside thead th { ... } and th { ... } blocks.
    blocks = re.findall(
        r"(thead\s+th|^\s*th)\s*\{[^}]*\}",
        styles_css_text,
        flags=re.MULTILINE,
    )
    # The findall above returns the selector, not the body. Re-find with
    # a wider pattern that captures the body too.
    body_matches = re.findall(
        r"(?:thead\s+th|^\s*th)\s*\{([^}]*)\}",
        styles_css_text,
        flags=re.MULTILINE,
    )
    for body in body_matches:
        assert "background" not in body, (
            "header cells must not set a background fill — "
            "booktabs convention uses rule weights, not shading"
        )


def test_no_vertical_rules_via_border_left_right_on_data_cells(
    styles_css_text: str,
):
    """The ``tbody td`` block must not introduce vertical rules. We
    check that no ``border-left`` or ``border-right`` declarations live
    inside the data-cell block.
    """
    body_match = re.search(
        r"tbody\s+td\s*\{([^}]*)\}", styles_css_text
    )
    assert body_match is not None, "tbody td block must exist"
    body = body_match.group(1)
    assert "border-left" not in body, (
        "tbody td must not set border-left (no vertical rules)"
    )
    assert "border-right" not in body, (
        "tbody td must not set border-right (no vertical rules)"
    )
