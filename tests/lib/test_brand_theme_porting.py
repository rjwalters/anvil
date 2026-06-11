"""Doc-coverage + starter-theme tests for the brand-theme porting path (#431).

Issue #431 ships the consumer brand-theme porting path (LaTeX beamer
``.sty`` → Marp CSS): a porting guide at
``anvil/lib/snippets/brand-theme-porting.md`` and a starter theme at
``anvil/lib/marp/brand-theme-starter.css``. Both ``anvil:deck`` and
``anvil:slides`` consume the guide, so the deliverables are lib-level and
the tests live in ``tests/lib/`` (vs. the per-skill test dirs).

Coverage, per the #431 acceptance criteria:

- The guide exists and its concept-mapping table covers the six required
  beamer concepts (title frame, section divider, callout/block, color
  macros, footer/confidentiality strip, logo).
- The guide documents the registration path (overlay CSS + frontmatter
  ``theme:`` + ``--theme-set`` merge) and the validation workflow
  (mechanical render gate, then vision critic with the v4 palette
  caveat).
- The guide explicitly scopes OUT: beamer as a first-class renderer,
  TikZ/overlay porting, and vision-palette de-hardcoding.
- The starter CSS ships the ``@theme`` marker, ``@import "default"``, a
  ``:root`` brand-token block, and all four ``SLOT:``-commented slots.
- Both skills' SKILL.md and marp-renderer.md cross-reference the guide.
- The optional BRIEF ``theme:`` key is documented in ``deck-brief.md``
  and honored by both draft commands.
- **Conditional** — when ``marp`` is on PATH, a four-slot fixture deck
  renders to a non-empty PDF under ``marp --theme-set`` with a renamed
  copy of the starter theme (skipped gracefully when marp is absent, per
  the ``test_marp_smoke.py`` precedent).

Doc-coverage style follows
``anvil/skills/deck/tests/test_imagery_style_presets_doc.py``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

GUIDE = _REPO_ROOT / "anvil" / "lib" / "snippets" / "brand-theme-porting.md"
STARTER = _REPO_ROOT / "anvil" / "lib" / "marp" / "brand-theme-starter.css"
MARP_CONFIG = _REPO_ROOT / "anvil" / "lib" / "marp" / "config.yml"

DECK_SKILL = _REPO_ROOT / "anvil" / "skills" / "deck"
SLIDES_SKILL = _REPO_ROOT / "anvil" / "skills" / "slides"

# The four named slots the starter theme must ship, each marked with a
# ``SLOT:`` comment so this test (and the doc-coverage contract) can
# assert presence without parsing CSS.
REQUIRED_SLOTS = [
    "SLOT: title slide",
    "SLOT: section divider",
    "SLOT: callout box",
    "SLOT: footer / confidentiality strip",
]

# One representative token per required concept-mapping-table row. The
# guide must mention each beamer-side concept by its LaTeX spelling so a
# consumer can grep their own .sty against the table.
REQUIRED_MAPPING_TOKENS = {
    "title frame": r"\titlepage",
    "section divider": r"\AtBeginSection",
    "callout/block": "tcolorbox",
    "color macros": r"\setbeamercolor",
    "footer/confidentiality strip": "footline",
    "logo": r"\logo",
}


@pytest.fixture(scope="module")
def guide_text() -> str:
    assert GUIDE.exists(), f"porting guide missing at {GUIDE}"
    return GUIDE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def starter_text() -> str:
    assert STARTER.exists(), f"starter theme missing at {STARTER}"
    return STARTER.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Guide: existence + concept-mapping table
# ---------------------------------------------------------------------------


def test_guide_exists_and_nonempty(guide_text: str) -> None:
    assert guide_text.strip(), "porting guide is empty"


@pytest.mark.parametrize(
    "concept,token",
    sorted(REQUIRED_MAPPING_TOKENS.items()),
    ids=sorted(REQUIRED_MAPPING_TOKENS),
)
def test_mapping_table_covers_concept(
    concept: str, token: str, guide_text: str
) -> None:
    """Each of the six required beamer concepts appears in the guide."""
    assert token in guide_text, (
        f"porting guide is missing the {concept!r} mapping row — expected "
        f"the beamer-side token {token!r} to appear in "
        f"{GUIDE.relative_to(_REPO_ROOT)}"
    )


def test_mapping_targets_marp_side(guide_text: str) -> None:
    """The Marp side of the table references the load-bearing targets."""
    for marp_token in (
        "_class: title",
        "_class: section",
        ":root",
        "footer:",
        "section::after",
    ):
        assert marp_token in guide_text, (
            f"porting guide mapping table missing Marp-side target "
            f"{marp_token!r}"
        )


def test_guide_documents_what_does_not_port(guide_text: str) -> None:
    """TikZ overlays / incremental builds are authoring-model differences."""
    assert "TikZ" in guide_text
    for token in (r"\only", r"\pause"):
        assert token in guide_text, (
            f"'What does NOT port' must name beamer overlay token {token!r}"
        )
    # Live .tex bodies route to foreign-grammar migration, not theming.
    assert "#432" in guide_text


# ---------------------------------------------------------------------------
# Guide: registration + validation workflow
# ---------------------------------------------------------------------------


def test_guide_documents_registration_path(guide_text: str) -> None:
    """Overlay CSS path + frontmatter theme: + --theme-set merge."""
    assert ".anvil/skills/deck/templates/" in guide_text
    assert ".anvil/skills/slides/templates/" in guide_text
    assert "--theme-set" in guide_text
    assert "theme: acme-brand" in guide_text or "theme: <" in guide_text, (
        "registration recipe must show the frontmatter `theme:` line"
    )
    # The pinned themeSet lists shipped themes only; the guide must say
    # NOT to edit it.
    assert "themeSet" in guide_text


def test_guide_documents_validation_workflow(guide_text: str) -> None:
    """Mechanical render gate first, vision critic second."""
    assert "marp" in guide_text
    assert "deck-vision" in guide_text and "slides-vision" in guide_text
    # The v4 palette caveat: hardcoded shipped palettes mean the brand
    # palette must be stated in BRIEF.md for the critic to score against.
    assert "palette_adherence" in guide_text
    assert "BRIEF.md" in guide_text


def test_guide_scopes_out_followups(guide_text: str) -> None:
    """Out of scope: beamer first-class, TikZ porting, v4 de-hardcoding."""
    lower = guide_text.lower()
    assert "out of scope" in lower
    assert "first-class" in lower, (
        "guide must state beamer-as-first-class-renderer is out of scope"
    )
    assert "de-hardcod" in lower, (
        "guide must note vision v4 palette de-hardcoding as a follow-up, "
        "not part of this porting path"
    )


# ---------------------------------------------------------------------------
# Starter theme CSS
# ---------------------------------------------------------------------------


def test_starter_has_theme_marker(starter_text: str) -> None:
    assert "/* @theme REPLACE-ME */" in starter_text, (
        "starter theme must ship the `/* @theme REPLACE-ME */` marker the "
        "porting guide's smoke test renames"
    )


def test_starter_imports_default_theme(starter_text: str) -> None:
    assert '@import "default";' in starter_text


def test_starter_has_brand_token_root_block(starter_text: str) -> None:
    """:root block mirrors the anvil-deck.css token pattern (--brand-*)."""
    assert ":root" in starter_text
    for token in (
        "--brand-text",
        "--brand-muted",
        "--brand-accent",
        "--brand-bg",
    ):
        assert token in starter_text, (
            f"starter theme :root block missing brand token {token!r}"
        )


@pytest.mark.parametrize("slot", REQUIRED_SLOTS)
def test_starter_has_slot(slot: str, starter_text: str) -> None:
    """All four named slots are present and SLOT:-commented."""
    assert slot in starter_text, (
        f"starter theme missing slot marker {slot!r} — the four slots "
        "(title slide, section divider, callout box, footer/confidentiality "
        "strip) are the #431 contract"
    )


def test_starter_serves_both_skills_divider_conventions(
    starter_text: str,
) -> None:
    """One starter serves both skills: deck's section.section AND slides'
    section.divider class are wired for the divider slot."""
    assert "section.section" in starter_text
    assert "section.divider" in starter_text


def test_starter_not_in_pinned_themeset() -> None:
    """The pinned config.yml themeSet lists shipped themes only — the
    starter is a copy-template and must NOT be registered there."""
    config_text = MARP_CONFIG.read_text(encoding="utf-8")
    assert "brand-theme-starter" not in config_text, (
        "brand-theme-starter.css must not be added to the pinned themeSet "
        "(curator decision on #431: that list names shipped themes only)"
    )


# ---------------------------------------------------------------------------
# Cross-references from the consuming skills
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "doc",
    [
        DECK_SKILL / "SKILL.md",
        SLIDES_SKILL / "SKILL.md",
        DECK_SKILL / "assets" / "marp-renderer.md",
        SLIDES_SKILL / "assets" / "marp-renderer.md",
    ],
    ids=["deck-skill", "slides-skill", "deck-renderer", "slides-renderer"],
)
def test_skill_docs_cross_reference_guide(doc: Path) -> None:
    assert doc.exists(), f"missing {doc}"
    text = doc.read_text(encoding="utf-8")
    assert "brand-theme-porting.md" in text, (
        f"{doc.relative_to(_REPO_ROOT)} must cross-reference the porting "
        "guide so it is discoverable from the skill"
    )


# ---------------------------------------------------------------------------
# Optional BRIEF `theme:` key (additive draft-command edit)
# ---------------------------------------------------------------------------


def test_deck_brief_documents_theme_key() -> None:
    text = (DECK_SKILL / "commands" / "deck-brief.md").read_text(
        encoding="utf-8"
    )
    assert "#### `theme` (optional" in text, (
        "deck-brief.md must document the optional BRIEF `theme:` "
        "frontmatter key"
    )
    assert "anvil-deck" in text


@pytest.mark.parametrize(
    "command,default_theme",
    [
        (DECK_SKILL / "commands" / "deck-draft.md", "anvil-deck"),
        (
            SLIDES_SKILL / "commands" / "slides-draft.md",
            "anvil-slides-theme",
        ),
    ],
    ids=["deck-draft", "slides-draft"],
)
def test_draft_commands_honor_brief_theme_key(
    command: Path, default_theme: str
) -> None:
    """Both draft commands copy BRIEF `theme:` into deck.md frontmatter,
    defaulting to the shipped theme when the key is absent."""
    text = command.read_text(encoding="utf-8")
    assert "Theme selection" in text, (
        f"{command.name} must document the BRIEF `theme:` key handling"
    )
    assert "brand-theme-porting.md" in text
    assert default_theme in text


# ---------------------------------------------------------------------------
# Conditional marp smoke render (test_marp_smoke.py precedent)
# ---------------------------------------------------------------------------

# A four-slide fixture exercising all four starter slots: title slide,
# section divider, callout box, and the footer/confidentiality strip
# (via the `footer:` directive + paginate).
_FOUR_SLOT_DECK = """\
---
marp: true
theme: brand-smoke
paginate: true
size: 16:9
math: mathjax
html: true
footer: "CONFIDENTIAL — Brand Smoke"
---

<!-- _class: title -->

# Brand Smoke Test

## Starter theme — four-slot fixture

---

<!-- _class: section -->

# Section Divider

---

## Callout box

<div class="callout">

**Key claim.** The callout box replaces the beamer block environment.

</div>

---

## Footer strip

Every slide carries the footer directive text plus pagination.
"""


@pytest.mark.skipif(
    shutil.which("marp") is None,
    reason="marp CLI not on PATH; skipping render smoke test "
    "(matches test_marp_smoke.py discipline)",
)
def test_starter_theme_renders_four_slot_fixture(
    tmp_path: Path, starter_text: str
) -> None:
    """A renamed copy of the starter renders the four-slot fixture to a
    non-empty PDF under ``marp --theme-set`` (#431 acceptance criterion)."""
    themed_css = tmp_path / "brand-smoke.css"
    themed_css.write_text(
        starter_text.replace(
            "/* @theme REPLACE-ME */", "/* @theme brand-smoke */"
        ),
        encoding="utf-8",
    )
    deck = tmp_path / "deck.md"
    deck.write_text(_FOUR_SLOT_DECK, encoding="utf-8")
    out_pdf = tmp_path / "deck.pdf"

    proc = subprocess.run(
        [
            "marp",
            str(deck),
            "--pdf",
            "--html",
            "--allow-local-files",
            "--theme-set",
            str(themed_css),
            "-o",
            str(out_pdf),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"marp render of the four-slot fixture failed "
        f"(rc={proc.returncode}); stderr={proc.stderr!r}"
    )
    assert out_pdf.is_file(), "marp produced no output file"
    assert out_pdf.stat().st_size > 0, "marp produced an empty PDF"
