"""Doc-coverage smoke tests for the dim 10 ownership flip from
``deck-review`` (v0 fallback) to ``deck-economics`` (primary) introduced
by issue #551.

The canary contract this guards:

  1. ``rubric.md`` §"Critic dimension ownership" table contains a
     ``deck-economics`` row primary-owning dim 10; the dim 10 dimension
     cell names ``deck-economics`` as owner; the ``deck-review`` row
     keeps dim 10 as fallback per the joint-ownership-with-fallback
     precedent (dim 8 between ``deck-design`` and ``deck-vision``).
  2. ``rubric.md`` §"Perspective substrate (dims 3, 4, 10)" prose names
     ``deck-economics`` (primary) with ``deck-review`` retained as
     fallback; the "after sibling #551 lands" conditional is dropped
     (the conditional has resolved).
  3. ``deck-review.md`` reframes dim 10 as fallback-only — NOT "v0
     fallback; #551 will introduce…" — and references
     ``deck-economics`` as the primary owner.
  4. ``deck-market.md`` line 19, ``deck-narrative.md`` line 20,
     ``deck-design.md`` line 18 all name ``deck-economics`` as primary
     dim 10 owner in the "Total ownership: X/49" prose.
  5. ``SKILL.md`` default critic set includes ``deck-economics``;
     description bumps to "four parallel critics"; sibling-critic
     convention block enumerates ``deck-economics``; the command
     dispatch table has a ``deck-economics`` row; the perspective
     fan-out list includes ``.economics/``.

These tests assert on substring presence only — they do NOT validate
prose quality or the LLM-driven runtime semantics. Behavioural
assertions belong in consumer-side integration tests.

Per-skill test filename convention (#58): file is named with a
``test_deck_economics_`` prefix so it never collides with parallel-shape
tests for the existing critics.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "deck"

RUBRIC_MD = SKILL_ROOT / "rubric.md"
SKILL_MD = SKILL_ROOT / "SKILL.md"
REVIEW_MD = SKILL_ROOT / "commands" / "deck-review.md"
MARKET_MD = SKILL_ROOT / "commands" / "deck-market.md"
NARRATIVE_MD = SKILL_ROOT / "commands" / "deck-narrative.md"
DESIGN_MD = SKILL_ROOT / "commands" / "deck-design.md"
REVISE_MD = SKILL_ROOT / "commands" / "deck-revise.md"
DECK_MD = SKILL_ROOT / "commands" / "deck.md"
ECONOMICS_MD = SKILL_ROOT / "commands" / "deck-economics.md"
README_MD = SKILL_ROOT / "README.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC1: rubric.md ownership table contains deck-economics row + dim 10 cell
# names deck-economics + deck-review retains fallback
# ---------------------------------------------------------------------------


def test_rubric_md_dimension_ownership_table_names_deck_economics_for_dim10():
    """AC1: the dim 10 dimension row in rubric.md §Dimensions table must
    name ``deck-economics`` as the owner (the trailing "Owned by critic"
    column entry), with ``deck-review`` retained as the fallback."""
    body = _read(RUBRIC_MD)
    # The dim 10 row must mention deck-economics as primary owner.
    assert "Owned by `deck-economics`" in body or "Owned by **`deck-economics`**" in body, (
        "rubric.md §Dimensions table dim 10 cell MUST name "
        "deck-economics as the primary owner — the v0 \"#551 will "
        "introduce\" placeholder has resolved."
    )


def test_rubric_md_critic_ownership_table_has_deck_economics_row():
    """AC1: the Critic dimension ownership table must contain a
    ``deck-economics`` row primary-owning dim 10 — the load-bearing
    structural signal that this critic exists and owns dim 10."""
    body = _read(RUBRIC_MD)
    # The new row format: | `deck-economics` | 10 | ... |
    assert "| `deck-economics` | 10 |" in body, (
        "rubric.md §Critic dimension ownership MUST contain a row "
        "for deck-economics primary-owning dim 10."
    )


def test_rubric_md_deck_review_row_retains_dim10_fallback():
    """AC1: the deck-review row must retain dim 10 as fallback ownership
    (parallel to the joint-ownership-with-fallback pattern between
    deck-design and deck-vision on dim 8)."""
    body = _read(RUBRIC_MD)
    # The deck-review row must still show dim 10 as fallback.
    assert "2, 5, 6, 10 (fallback)" in body, (
        "rubric.md §Critic dimension ownership deck-review row MUST "
        "retain dim 10 as fallback (per the joint-ownership-with-"
        "fallback precedent on dim 8 between deck-design and "
        "deck-vision)."
    )


# ---------------------------------------------------------------------------
# AC2: rubric.md §Perspective substrate prose names deck-economics primary
# + deck-review fallback; the "#551" conditional is dropped
# ---------------------------------------------------------------------------


def test_rubric_md_perspective_substrate_ownership_flipped_to_economics_primary():
    """AC2: the perspective substrate prose must name ``deck-economics``
    (primary) with ``deck-review`` retained as fallback. The "after
    sibling #551 lands" / "primary ownership moves to deck-economics"
    conditional MUST be dropped — the conditional has resolved."""
    body = _read(RUBRIC_MD)
    # Both must appear in the substrate prose
    assert "deck-economics" in body, (
        "rubric.md §\"Perspective substrate\" MUST name "
        "deck-economics as the primary owner for dim 10 substrate."
    )
    # The pre-#551 conditional phrasing should be replaced. Look for
    # the specific "(primary" framing that #551 introduces (a parenthetical
    # that names deck-economics as the primary owner — either
    # "(primary)" alone or "(primary, ...)" with additional qualifiers).
    assert "`deck-economics` (primary" in body, (
        "rubric.md §\"Perspective substrate\" MUST name "
        "deck-economics as \"(primary)\" or \"(primary, ...)\" — the "
        "pre-#551 conditional (\"after sibling #551 lands, primary "
        "ownership moves to deck-economics\") MUST be dropped because "
        "the conditional has resolved."
    )


def test_rubric_md_perspective_substrate_drops_post_551_conditional():
    """AC2 (load-bearing): the pre-#551 deferral language ("after
    sibling #551 lands, primary ownership moves to deck-economics") MUST
    be dropped — this is the load-bearing signal that the conditional
    has resolved and ownership is no longer deferred."""
    body = _read(RUBRIC_MD)
    # The exact pre-#551 phrasing must NOT appear post-flip.
    assert "after sibling #551 lands, primary ownership moves to `deck-economics`" not in body, (
        "rubric.md §\"Perspective substrate\" MUST drop the pre-#551 "
        "conditional phrasing — it has resolved and the prose should "
        "name deck-economics as the primary owner directly."
    )


# ---------------------------------------------------------------------------
# AC3: deck-review.md reframes dim 10 as fallback-only
# ---------------------------------------------------------------------------


def test_deck_review_md_dim10_fallback_only_reframe():
    """AC3: deck-review.md must reframe dim 10 as fallback ownership
    where the primary belongs to deck-economics. The "v0 fallback
    ownership — sibling #551 will introduce deck-economics" placeholder
    MUST be replaced."""
    body = _read(REVIEW_MD)
    # The pre-#551 placeholder phrasing must NOT appear post-flip in the
    # owned-dimensions block (line 20) or the dim 10 sub-step (line 118).
    assert "sibling #551 will introduce" not in body, (
        "deck-review.md MUST drop the \"sibling #551 will introduce\" "
        "placeholder — #551 has landed and the deferral has resolved."
    )
    # The new fallback phrasing must reference deck-economics by name.
    assert "deck-economics" in body, (
        "deck-review.md MUST reference deck-economics by name in the "
        "dim 10 ownership reframe (the primary owner this critic falls "
        "back from)."
    )


# ---------------------------------------------------------------------------
# AC4: deck-market.md, deck-narrative.md, deck-design.md ownership prose
# names deck-economics as primary dim 10 owner
# ---------------------------------------------------------------------------


def test_deck_market_md_total_ownership_prose_names_deck_economics():
    """AC4: deck-market.md "Total ownership: 10/49" prose must name
    deck-economics as the primary dim 10 owner (was: deck-review as
    fallback)."""
    body = _read(MARKET_MD)
    # The dim 10 prose must mention deck-economics as primary.
    assert "deck-economics" in body, (
        "deck-market.md MUST name deck-economics as primary dim 10 "
        "owner in the \"Total ownership: 10/49\" prose."
    )


def test_deck_narrative_md_total_ownership_prose_names_deck_economics():
    """AC4: deck-narrative.md "Total ownership: 15/49" prose must name
    deck-economics as the primary dim 10 owner."""
    body = _read(NARRATIVE_MD)
    assert "deck-economics" in body, (
        "deck-narrative.md MUST name deck-economics as primary dim 10 "
        "owner in the \"Total ownership: 15/49\" prose."
    )


def test_deck_design_md_total_ownership_prose_names_deck_economics():
    """AC4: deck-design.md "Total ownership: 5/49" prose must name
    deck-economics as the primary dim 10 owner."""
    body = _read(DESIGN_MD)
    assert "deck-economics" in body, (
        "deck-design.md MUST name deck-economics as primary dim 10 "
        "owner in the \"Total ownership: 5/49\" prose."
    )


# ---------------------------------------------------------------------------
# AC5: SKILL.md enumerates deck-economics in description, sibling-critic
# convention, default critic set, perspective fan-out, command dispatch
# table, parallel-critics section
# ---------------------------------------------------------------------------


def test_skill_md_description_enumerates_economics():
    """AC5: SKILL.md description must bump to "four parallel critics"
    and enumerate economics."""
    body = _read(SKILL_MD)
    assert "four parallel critics" in body or "four parallel critics (narrative, market, design, economics)" in body, (
        "SKILL.md description MUST bump from \"three parallel critics\" "
        "to \"four parallel critics\" and enumerate economics."
    )


def test_skill_md_default_critic_set_includes_economics():
    """AC5: SKILL.md default critic set must include deck-economics —
    "review + narrative + market + design + economics"."""
    body = _read(SKILL_MD)
    assert "review + narrative + market + design + economics" in body, (
        "SKILL.md \"Default critic set for deck\" MUST include "
        "economics — the five-critic default fan-out."
    )


def test_skill_md_perspective_fan_out_includes_economics():
    """AC5: SKILL.md perspective-sibling fan-out list must include
    ``.economics/`` alongside ``.review/``, ``.narrative/``,
    ``.market/``, ``.design/``, ``.audit/``."""
    body = _read(SKILL_MD)
    assert ".economics/" in body, (
        "SKILL.md perspective fan-out list MUST include .economics/ "
        "alongside the other critic siblings."
    )


def test_skill_md_command_dispatch_table_has_economics_row():
    """AC5: SKILL.md Command dispatch table must contain a
    ``deck-economics <thread>`` row."""
    body = _read(SKILL_MD)
    assert "deck-economics <thread>" in body or "`deck-economics <thread>`" in body, (
        "SKILL.md Command dispatch table MUST contain a "
        "`deck-economics <thread>` row."
    )


def test_skill_md_parallel_critics_section_bumped_to_four():
    """AC5: SKILL.md "Three parallel critics" section must bump to
    "Four parallel critics" and add an enumerated deck-economics
    bullet."""
    body = _read(SKILL_MD)
    assert "Four parallel critics" in body, (
        "SKILL.md MUST bump the \"Three parallel critics\" section "
        "heading to \"Four parallel critics\"."
    )
    # The deck-economics bullet must be present in the parallel-critics
    # section (named with its owned dim).
    assert "deck-economics" in body, (
        "SKILL.md parallel-critics section MUST add an enumerated "
        "deck-economics bullet."
    )


# ---------------------------------------------------------------------------
# AC6: deck-revise.md fan-out + deck.md portfolio orchestrator + README.md
# enumerate deck-economics
# ---------------------------------------------------------------------------


def test_deck_revise_md_fan_out_includes_economics():
    """AC6: deck-revise.md Convergence step 2 fan-out list MUST include
    deck-economics in the parallel critic run."""
    body = _read(REVISE_MD)
    assert "deck-economics" in body, (
        "deck-revise.md Convergence fan-out MUST include "
        "deck-economics in the parallel critic run."
    )


def test_deck_md_portfolio_orchestrator_fan_out_includes_economics():
    """AC6: deck.md portfolio orchestrator fan-out lines MUST enumerate
    deck-economics in the recommended-next-command table and in the
    parallel-critics note."""
    body = _read(DECK_MD)
    assert "deck-economics" in body, (
        "deck.md portfolio orchestrator MUST enumerate deck-economics "
        "in the fan-out lines."
    )
    # The note at the bottom must bump to "five critic commands"
    assert "five critic commands" in body, (
        "deck.md portfolio orchestrator notes section MUST bump from "
        "\"four critic commands\" to \"five critic commands\" "
        "enumerating deck-economics."
    )


def test_readme_md_enumerates_deck_economics():
    """AC6: README.md must list deck-economics in the at-a-glance table
    + the worked-example lifecycle paragraph + the critic-set row."""
    body = _read(README_MD)
    assert "deck-economics" in body, (
        "README.md MUST list deck-economics in the at-a-glance table "
        "and the worked-example lifecycle paragraph."
    )
    # The five-critic enumeration must appear
    assert "review + narrative + market + design + economics" in body, (
        "README.md MUST update the default critic set sentence to "
        "include economics."
    )


# ---------------------------------------------------------------------------
# Sanity: deck-economics.md exists
# ---------------------------------------------------------------------------


def test_deck_economics_md_exists():
    """The new deck-economics.md command file must be on disk — the
    structural signal that the critic shipped."""
    assert ECONOMICS_MD.exists(), (
        "anvil/skills/deck/commands/deck-economics.md MUST exist — "
        "issue #551 ships this new critic command file."
    )


def test_deck_economics_md_owns_dim_10():
    """deck-economics.md must name dim 10 as its owned rubric
    dimension."""
    body = _read(ECONOMICS_MD)
    assert "10 — Business-model & unit-economics credibility" in body, (
        "deck-economics.md MUST name dim 10 (Business-model & "
        "unit-economics credibility) as its owned rubric dimension."
    )
