"""Tests for ``anvil/lib/ai_byline.py`` (issue #941).

Covers the pure string-rendering half of the opt-in AI-authorship byline
contract: :func:`render_byline` (default text, custom-text override,
``{model}``/``{date}`` interpolation, deterministic given fixed inputs)
and :func:`render_byline_markdown` (the markdown-wrapping convention
consumers splice into a rendered artifact).

The BRIEF-parsing / resolution half (``AiByline`` / ``resolve_ai_byline``)
is covered separately in ``tests/lib/test_project_brief_ai_byline.py``.
"""

from __future__ import annotations

from anvil.lib.ai_byline import (
    DEFAULT_PLACEMENT,
    DEFAULT_TEXT,
    VALID_PLACEMENTS,
    render_byline,
    render_byline_markdown,
)


# ---------------------------------------------------------------------------
# render_byline — default text
# ---------------------------------------------------------------------------


def test_default_text_used_when_no_override() -> None:
    assert render_byline() == DEFAULT_TEXT


def test_default_text_used_for_none_text() -> None:
    assert render_byline(text=None) == DEFAULT_TEXT


def test_default_text_used_for_empty_string() -> None:
    assert render_byline(text="") == DEFAULT_TEXT


def test_default_text_used_for_whitespace_only_string() -> None:
    assert render_byline(text="   ") == DEFAULT_TEXT


def test_default_text_ignores_model_and_date() -> None:
    # DEFAULT_TEXT has no placeholders — model_name/date are simply unused.
    assert render_byline(model_name="Claude", date="2026-08-11") == DEFAULT_TEXT


# ---------------------------------------------------------------------------
# render_byline — custom text override
# ---------------------------------------------------------------------------


def test_custom_text_used_verbatim_when_no_placeholders() -> None:
    custom = "Written by a human, polished by a machine."
    assert render_byline(text=custom) == custom


def test_custom_text_strips_surrounding_whitespace() -> None:
    assert render_byline(text="  Custom line.  ") == "Custom line."


def test_model_placeholder_substituted() -> None:
    rendered = render_byline(
        text="Drafted with AI assistance ({model}).", model_name="Claude"
    )
    assert rendered == "Drafted with AI assistance (Claude)."


def test_date_placeholder_substituted() -> None:
    rendered = render_byline(
        text="Drafted with AI assistance, last updated {date}.", date="2026-08-11"
    )
    assert rendered == "Drafted with AI assistance, last updated 2026-08-11."


def test_both_placeholders_substituted() -> None:
    rendered = render_byline(
        text="Drafted with {model} on {date}.",
        model_name="Claude",
        date="2026-08-11",
    )
    assert rendered == "Drafted with Claude on 2026-08-11."


def test_unused_placeholder_value_is_harmless() -> None:
    # model_name supplied but {model} not referenced in the template —
    # never raises, output is unaffected.
    rendered = render_byline(text="Drafted with AI assistance.", model_name="Claude")
    assert rendered == "Drafted with AI assistance."


def test_missing_placeholder_value_never_raises() -> None:
    # {model} referenced but no model_name supplied — substitutes empty
    # string and collapses the resulting whitespace run, never raises
    # and never leaves a literal "{model}" in the output.
    rendered = render_byline(text="Drafted with {model} assistance.")
    assert "{model}" not in rendered
    assert rendered == "Drafted with assistance."


def test_deterministic_given_fixed_inputs() -> None:
    kwargs = dict(text="Drafted with {model} on {date}.", model_name="Claude", date="2026-08-11")
    assert render_byline(**kwargs) == render_byline(**kwargs)


# ---------------------------------------------------------------------------
# render_byline_markdown
# ---------------------------------------------------------------------------


def test_render_byline_markdown_wraps_in_italics() -> None:
    assert render_byline_markdown("Drafted with AI assistance.") == (
        "*Drafted with AI assistance.*"
    )


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


def test_default_placement_is_byline() -> None:
    assert DEFAULT_PLACEMENT == "byline"


def test_valid_placements_contains_default() -> None:
    assert DEFAULT_PLACEMENT in VALID_PLACEMENTS


def test_valid_placements_closed_vocabulary() -> None:
    assert set(VALID_PLACEMENTS) == {"byline", "footer", "frontmatter-only"}
