"""Per-glyph Unicode fallback regression test for ``anvil.lib.figures``.

Background: matplotlib 3.6+ does per-glyph fallback ONLY when ``font.family``
is itself a concrete list of family names — NOT when it is the ``sans-serif``
alias with ``font.sans-serif`` carrying the list. The alias form silently
disables fallback (first-available-family-wins), which means a glyph the
primary font lacks (e.g. ``→`` U+2192 on Helvetica Neue, which has no arrows)
renders as the missing-glyph box and matplotlib emits a ``Glyph N missing
from font`` ``UserWarning`` per offending glyph.

This was the root cause of the studio canary re-render wave's recurring
``→``-rendered-as-square defect. The fix lives in ``anvil/lib/figures/
anvil.mplstyle``: ``font.family`` is a concrete chain ending in DejaVu Sans
(the matplotlib-bundled universal backstop).

This test asserts the fix by capturing matplotlib warnings around a render
that includes ``→`` and confirming no ``Glyph * missing`` warning is emitted.
matplotlib is gated via ``importorskip`` so the suite stays green without it.
"""

from __future__ import annotations

import io
import warnings

import pytest


mpl = pytest.importorskip("matplotlib", reason="matplotlib not installed")


def test_arrow_glyph_renders_without_missing_glyph_warning() -> None:
    """``→`` (U+2192) renders cleanly after ``apply()`` — no glyph-missing warning.

    The shipped ``anvil.mplstyle`` declares ``font.family`` as a concrete
    family list ending in ``DejaVu Sans``, which triggers matplotlib's
    per-glyph fallback. The Unicode right-arrow is absent from Helvetica
    Neue/Helvetica/Arial on macOS but present in DejaVu Sans, so the chain
    must resolve it cleanly.

    Failure mode without the fix: matplotlib emits ``UserWarning: Glyph 8594
    (\\N{RIGHTWARDS ARROW}) missing from font(s) Helvetica Neue.`` and the
    glyph renders as the missing-glyph box.
    """
    import matplotlib as _mpl
    import matplotlib.pyplot as plt

    from anvil.lib.figures import palette

    with _mpl.rc_context():
        palette.apply()

        # The arrow MUST appear in a text element that actually rasterizes,
        # which means rendering the figure to a buffer. Title is the easiest.
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        ax.set_title("draft → review → ship")
        ax.set_xlabel("phase → next")

        buf = io.BytesIO()
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            fig.savefig(buf, format="png")
        plt.close(fig)

        glyph_missing = [
            w for w in captured
            if "missing from font" in str(w.message).lower()
            or "glyph" in str(w.message).lower() and "missing" in str(w.message).lower()
        ]
        assert not glyph_missing, (
            "matplotlib emitted glyph-missing warnings; per-glyph Unicode "
            "fallback is not working. font.family in anvil.mplstyle must be a "
            "concrete family list (not the 'sans-serif' alias) so DejaVu Sans "
            "can serve as the fallback for glyphs Helvetica Neue lacks. "
            f"Warnings: {[str(w.message) for w in glyph_missing]}"
        )


def test_font_family_is_concrete_list_not_alias() -> None:
    """``font.family`` after ``apply()`` must be a concrete family chain.

    matplotlib's per-glyph fallback is gated on this — ``['sans-serif']`` (the
    alias) silently disables it; a list of concrete family names (``['Helvetica
    Neue', ..., 'DejaVu Sans']``) enables it. This test fails if a future edit
    to ``anvil.mplstyle`` reverts to the alias form.
    """
    import matplotlib as _mpl

    from anvil.lib.figures import palette

    with _mpl.rc_context():
        palette.apply()
        family = _mpl.rcParams["font.family"]
        # rcParams normalizes this to a list-of-strings.
        assert isinstance(family, list)
        # Must NOT be the alias — that disables per-glyph fallback.
        assert family != ["sans-serif"], (
            "font.family is the 'sans-serif' alias; per-glyph Unicode "
            "fallback is disabled. Use a concrete family list."
        )
        # Must end in DejaVu Sans (the matplotlib-bundled universal fallback).
        # Case-insensitive substring match keeps the test robust to whitespace.
        assert any("dejavu" in fam.lower() for fam in family), (
            "font.family must include DejaVu Sans as a fallback for glyphs "
            "the primary fonts lack (arrows, em dash, Unicode minus). "
            f"Current chain: {family}"
        )
