"""Schema/content drift guard for the four canonical mermaid classDefs.

The shipped ``anvil/lib/figures/mermaid-theme.json`` adds a ``themeCSS``
top-level key alongside ``theme`` and ``themeVariables``. mermaid injects
that string verbatim into a ``<style>`` block in the rendered SVG, which lets
the framework ship semantic classes (``anvil-accent``, ``anvil-muted``,
``anvil-warning``, ``anvil-success``) without authors hand-rolling them in
each ``.mmd`` source.

This test asserts:

- The JSON parses (no syntax regression).
- The ``themeCSS`` key exists and is a string.
- All four canonical class names appear in the ``themeCSS`` string.
- The four pinned hexes (navy, muted, warning, success) all appear, sourced
  from ``palette.py``'s constants (drift guard between the JSON literal hexes
  and the Python constants).
- ``!important`` is present so the rules override mermaid's per-source
  ``classDef`` defaults and prevent the white-on-color text contract from
  being silently broken by an author-supplied ``classDef`` that sets fill but
  not color (the heirloom ``consent_flow`` white-on-white regression).

No mermaid binary needed — this is a content-presence check on the shipped
JSON. Visual verification with ``mmdc`` is documented in the issue verification
checklist; this test is the CI-cheap drift guard.
"""

from __future__ import annotations

import json
from pathlib import Path

from anvil.lib.figures import palette


REPO_ROOT = Path(__file__).resolve().parents[2]
MERMAID_PATH = REPO_ROOT / "anvil" / "lib" / "figures" / "mermaid-theme.json"


CANONICAL_CLASSES = ("anvil-accent", "anvil-muted", "anvil-warning", "anvil-success")


def _theme() -> dict:
    return json.loads(MERMAID_PATH.read_text())


def test_theme_json_parses() -> None:
    theme = _theme()
    assert isinstance(theme, dict)


def test_theme_has_themecss_key() -> None:
    theme = _theme()
    assert "themeCSS" in theme, (
        "mermaid-theme.json must declare a top-level themeCSS key (the four "
        "canonical classDefs are shipped via this key, injected into a "
        "<style> block in every rendered SVG)."
    )
    assert isinstance(theme["themeCSS"], str)
    assert theme["themeCSS"].strip(), "themeCSS must not be empty"


def test_themecss_declares_all_four_canonical_classes() -> None:
    css = _theme()["themeCSS"]
    for cls in CANONICAL_CLASSES:
        assert f".{cls}" in css, (
            f"themeCSS missing canonical class selector .{cls} — authors "
            f"applying :::{cls} on a node will get mermaid's default "
            "rendering instead of the shipped semantic palette."
        )


def test_themecss_uses_palette_constants_for_hexes() -> None:
    """Drift guard: JSON literal hexes must match palette.py constants.

    The themeCSS string is hex-literal (mermaid theme JSON can't import
    Python), so this test enforces the sync between the two on the four
    semantic colors. Same contract as the CSS-drift guard for
    ``--anvil-*`` tokens.
    """
    css = _theme()["themeCSS"].lower()
    for name, hex_value in [
        ("navy/accent", palette.ANVIL_NAVY),
        ("muted", palette.ANVIL_MUTED),
        ("warning", palette.ANVIL_WARNING),
        ("success", palette.ANVIL_SUCCESS),
    ]:
        assert hex_value.lower() in css, (
            f"themeCSS missing {name} hex {hex_value} — drift between "
            "mermaid-theme.json literal hex and palette.py constant."
        )


def test_themecss_uses_important_so_per_source_classdefs_lose() -> None:
    """``!important`` must be present on the shipped rules.

    Without ``!important``, an author-supplied ``classDef foo fill:#xxx`` in
    a ``.mmd`` source would override the shipped semantic palette — and an
    author who sets only ``fill:`` (no ``color:``) would re-trigger the
    white-on-white regression on a dark fill. ``!important`` on fill+stroke+
    color guarantees the contract holds end-to-end.
    """
    css = _theme()["themeCSS"]
    # Cheap presence check — the exact count is implementation detail; the
    # contract is "important is used on the rules".
    assert "!important" in css, (
        "themeCSS rules must use !important so they override per-source "
        "classDef declarations and preserve the white-on-color contract."
    )
    # Specifically the white text rule (color:#ffffff) must be !important —
    # this is the load-bearing one for the white-on-white fix.
    css_compact = css.replace(" ", "")
    assert "color:#ffffff!important" in css_compact.lower(), (
        "themeCSS must set white text (color:#ffffff !important) on the "
        "classDef'd nodes — this is the fix for the white-on-white "
        "sub-symptom from heirloom consent_flow."
    )


def test_themecss_declares_edgelabel_overrides() -> None:
    """Edge-label CSS must be present (mermaid v11 white-on-white fix, #619).

    mermaid v11's ``base`` theme emits ``.label { color: <primaryTextColor> }``
    and edge labels inherit ``.label``; with ``primaryTextColor: #ffffff`` the
    edge-label text renders white on the near-white ``#f5f5f5`` label
    background — invisible. ``themeVariables.labelTextColor`` /
    ``edgeLabelBackground`` do NOT fix it, so a ``themeCSS`` ``.edgeLabel``
    override is the only working path. This asserts the override ships and
    can't silently regress.
    """
    css = _theme()["themeCSS"]
    assert ".edgeLabel" in css, (
        "themeCSS missing .edgeLabel override — mermaid v11 edge labels will "
        "render white-on-white (invisible) because they inherit .label with "
        "primaryTextColor #ffffff. See issue #619."
    )
    css_compact = css.replace(" ", "").lower()
    # Dark text (matches themeVariables.textColor #1a1a1a) on the edge label.
    assert "color:#1a1a1a!important" in css_compact, (
        "themeCSS .edgeLabel rule must force dark text (color:#1a1a1a "
        "!important, matching textColor) so edge labels are legible."
    )
    # White label background (matches themeVariables.background #ffffff).
    assert "background-color:#ffffff!important" in css_compact, (
        "themeCSS .edgeLabel rule must force a white label background "
        "(background-color:#ffffff !important, matching background)."
    )


def test_edgelabel_provenance_comment_is_present() -> None:
    """The `_edgeLabel_comment` key documents the v11 root cause and dead ends.

    JSON has no comments, so the provenance note lives in a top-level key
    (mermaid ignores unknown keys). Mirrors the `_comment` /
    `_themeCSS_comment` discipline. It must name the mermaid v11 `.label`
    inheritance root cause and the themeVariables dead ends so a future editor
    doesn't "simplify" the fix back into the broken themeVariables approach.
    """
    theme = _theme()
    assert "_edgeLabel_comment" in theme, (
        "mermaid-theme.json must document the edge-label fix in an "
        "_edgeLabel_comment key (mirrors _comment / _themeCSS_comment)."
    )
    note = theme["_edgeLabel_comment"]
    assert ".label" in note, "provenance note must name the .label inheritance root cause"
    assert "labelTextColor" in note or "edgeLabelBackground" in note, (
        "provenance note must document the themeVariables dead ends that do "
        "NOT fix the regression"
    )


def test_themecss_sync_comment_is_present() -> None:
    """JSON has no comments, so the sync note lives in a `_themeCSS_comment` key.

    Mirrors the existing `_comment` discipline for `themeVariables`; this is
    the author/maintainer-facing pointer that the themeCSS classDefs are
    documented in ``figure-conventions.md`` and synced via the drift tests.
    """
    theme = _theme()
    assert "_themeCSS_comment" in theme, (
        "themeCSS shipping a sync note in _themeCSS_comment mirrors the "
        "_comment discipline already used for themeVariables."
    )
    note = theme["_themeCSS_comment"]
    assert "palette.py" in note
    assert "figure-conventions.md" in note or "test_figures_mermaid_classdefs" in note
