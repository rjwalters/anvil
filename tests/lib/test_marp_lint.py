"""Regression armor for the ``anvil.lib.marp_lint`` promotion (issue #318).

Two narrow guards:

1. **Import smoke**: ``from anvil.lib.marp_lint import …`` exposes the full
   public surface. Mirrors ``tests/lib/test_lib_imports.py``'s pattern.
   Catches a future regression where the module gets accidentally removed,
   re-located, or has a public name dropped.

2. **Thin re-export identity**: the deck-side and slides-side modules
   (``anvil/skills/deck/lib/marp_lint.py`` and
   ``anvil/skills/slides/lib/marp_lint.py``) must expose the SAME function
   objects as ``anvil.lib.marp_lint`` — identity (``is``), not equality.
   This pins the "thin re-export" contract: any future drift where a skill
   re-exports a wrapped/subclassed version would fail this test.

The 18 deck-side and 11 slides-side fixture-driven test cases are NOT
duplicated here — they're already covered exhaustively under
``anvil/skills/{deck,slides}/tests/`` and the wider rule semantics are the
same regardless of import route.
"""

from __future__ import annotations


def test_anvil_lib_marp_lint_imports() -> None:
    """``from anvil.lib.marp_lint import …`` succeeds for the full surface."""
    from anvil.lib.marp_lint import (  # noqa: F401
        Finding,
        Geometry,
        LintResult,
        PORTED_RULES,
        UPSTREAM_SHA,
        lint_deck,
        lint_source,
    )

    # Public surface sanity: the constants advertise the expected rule set.
    assert "slide-content-overflow" in PORTED_RULES
    assert "figure-italic-supporting-line-too-long" in PORTED_RULES
    assert "inline-display-style-dropped" in PORTED_RULES
    assert isinstance(UPSTREAM_SHA, str) and len(UPSTREAM_SHA) >= 7


def test_deck_skill_reexport_is_thin() -> None:
    """``anvil.skills.deck.lib.marp_lint`` re-exports identity-equal symbols.

    The deck-side module must be a thin re-export of ``anvil.lib.marp_lint``
    — not a wrapped or subclassed variant. Identity (``is``) catches any
    future drift where a skill ships a fork.
    """
    from anvil.lib import marp_lint as canonical
    from anvil.skills.deck.lib import marp_lint as deck_side

    assert deck_side.lint_deck is canonical.lint_deck
    assert deck_side.lint_source is canonical.lint_source
    assert deck_side.Finding is canonical.Finding
    assert deck_side.Geometry is canonical.Geometry
    assert deck_side.LintResult is canonical.LintResult
    assert deck_side.PORTED_RULES is canonical.PORTED_RULES
    assert deck_side.UPSTREAM_SHA is canonical.UPSTREAM_SHA


def test_slides_skill_reexport_is_thin() -> None:
    """``anvil.skills.slides.lib.marp_lint`` re-exports identity-equal symbols.

    Same contract as the deck-side re-export. Pre-#318 the slides side was a
    ~90-line ``importlib.util.spec_from_file_location`` shim that broke if
    deck was not co-installed; post-#318 it imports ``anvil.lib.marp_lint``
    directly.
    """
    from anvil.lib import marp_lint as canonical
    from anvil.skills.slides.lib import marp_lint as slides_side

    assert slides_side.lint_deck is canonical.lint_deck
    assert slides_side.lint_source is canonical.lint_source
    assert slides_side.Finding is canonical.Finding
    assert slides_side.Geometry is canonical.Geometry
    assert slides_side.LintResult is canonical.LintResult
    assert slides_side.PORTED_RULES is canonical.PORTED_RULES
    assert slides_side.UPSTREAM_SHA is canonical.UPSTREAM_SHA
