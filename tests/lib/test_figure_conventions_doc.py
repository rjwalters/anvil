"""Content-presence drift guard for ``figure-conventions.md``.

The figure-conventions doc is the author-facing prose counterpart to the
``anvil/lib/figures/`` substrate. The figure-theming follow-up to #74 added
two new sections — Unicode-glyph fallback and semantic mermaid classDefs —
whose existence is a contract: the substrate fix is invisible without the
prose, and the substrate test (``test_figures_mermaid_classdefs.py``) only
asserts the JSON, not that authors know the classDefs are shipped.

Cheap grep-style assertions. Markdown structure (headers, code fences) is not
validated — just that the load-bearing tokens, class names, and cross-
references appear in the doc.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "anvil" / "skills" / "deck" / "assets" / "figure-conventions.md"


def _doc() -> str:
    return DOC_PATH.read_text()


def test_doc_exists() -> None:
    assert DOC_PATH.is_file(), f"missing doc: {DOC_PATH}"


def test_doc_mentions_unicode_fallback_section() -> None:
    """The new Unicode-fallback section must exist."""
    text = _doc()
    # Header presence — accept any header level so cosmetic re-leveling
    # doesn't break the test.
    assert "Unicode glyphs" in text or "Unicode-glyph" in text or "per-glyph fallback" in text, (
        "figure-conventions.md must document the Unicode-glyph fallback "
        "behavior (the matplotlib font.family-as-concrete-list gotcha)."
    )


def test_doc_includes_arrow_example() -> None:
    """The motivating glyph ``→`` (U+2192) must appear in the doc."""
    text = _doc()
    assert "→" in text, (
        "figure-conventions.md Unicode-fallback section must include the "
        "→ example (the motivating glyph from the #74 re-render wave)."
    )


def test_doc_warns_against_sans_serif_alias() -> None:
    """The doc must call out the ``sans-serif`` alias as the gotcha."""
    text = _doc()
    assert "sans-serif" in text, (
        "figure-conventions.md must mention the 'sans-serif' alias by name "
        "as the trap to avoid (per-glyph fallback is disabled when "
        "font.family is the alias)."
    )
    # Must also cite DejaVu Sans as the last-resort fallback.
    assert "DejaVu Sans" in text, (
        "figure-conventions.md must cite DejaVu Sans as the last-resort "
        "fallback font (matplotlib-bundled, universal Unicode coverage)."
    )


def test_doc_lists_all_four_canonical_classdefs() -> None:
    """The four canonical mermaid class names must be documented."""
    text = _doc()
    for cls in ("anvil-accent", "anvil-muted", "anvil-warning", "anvil-success"):
        assert cls in text, (
            f"figure-conventions.md missing canonical classDef name {cls} — "
            "authors won't know the shipped vocabulary exists."
        )


def test_doc_shows_classdef_usage_with_triple_colon() -> None:
    """The doc must show the ``:::className`` mermaid syntax."""
    text = _doc()
    # The triple-colon prefix is mermaid's class-application syntax.
    assert ":::anvil-" in text, (
        "figure-conventions.md must show the :::anvil-* usage syntax "
        "(mermaid's class-application form on a node)."
    )


def test_doc_cross_references_mermaid_theme_and_palette() -> None:
    """Cross-references to the substrate files must be present."""
    text = _doc()
    assert "mermaid-theme.json" in text or "themeCSS" in text, (
        "figure-conventions.md must cross-reference mermaid-theme.json / "
        "themeCSS so authors know where the shipped classDefs come from."
    )
    assert "palette.py" in text, (
        "figure-conventions.md must cross-reference palette.py (the "
        "canonical Python token source) — this cross-ref pre-exists; the "
        "test just guards it stays."
    )
