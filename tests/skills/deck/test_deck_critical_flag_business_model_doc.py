"""Doc-coverage smoke tests for the 5th standing deck critical flag
(``Incoherent or absent business model``, wire-key
``incoherent_or_absent_business_model``) introduced by issue #552.

The canary contract this guards (per issue #552 acceptance criteria):

  1. ``rubric.md`` §"Critical flags" lists **five** standing flags
     (the intro prose bumps "four standing critical flags" → "five
     standing critical flags") and adds the new flag's prose entry
     parallel to absent-ask, naming all three trigger conditions
     (no revenue mechanic / contradictory unit economics /
     counterparty-rejecting terms) and the wire-key.
  2. The new flag's ownership is documented as ``deck-economics``
     (primary, post-#551) with ``deck-review`` as the fallback when
     ``deck-economics`` is skipped from the critic fan-out.
  3. ``commands/deck-review.md`` step 7 enumerates the new flag with
     its three trigger conditions and names ``deck-economics`` as the
     primary owner / this critic as fallback.
  4. ``commands/deck-economics.md`` step 6 flips the pre-#552
     placeholder ("If #552 has NOT landed at #551 build time…the
     dedicated flag does not yet exist; this critic does NOT raise
     it") into an active flag-raise procedure naming this critic as
     the **primary** raiser.
  5. ``commands/deck-narrative.md`` line 65 (the ``Absent ask``
     structural twin) is updated to cross-reference the new flag.
  6. ``SKILL.md`` bumps both "four deck-specific critical flags" →
     "five" and "four critical-flag conditions" → "five" and
     enumerates the new flag with its wire-key.
  7. ``commands/deck-revise.md`` step 2 aggregation prose enumerates
     all five standing flag types (the OR semantics already covered
     any new flag — this is documentation, not logic).
  8. ``commands/deck-audit.md`` ``critical_flag_notes[].type``
     example block documents the five standing types.

These tests assert on substring presence only — they do NOT validate
prose quality or the LLM-driven runtime semantics. Behavioural
assertions belong in consumer-side integration tests.

Per-skill test filename convention (#58): file is named with a
``test_deck_critical_flag_`` prefix so it never collides with parallel
tests for the existing flag set.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "deck"

RUBRIC_MD = SKILL_ROOT / "rubric.md"
SKILL_MD = SKILL_ROOT / "SKILL.md"
REVIEW_MD = SKILL_ROOT / "commands" / "deck-review.md"
ECONOMICS_MD = SKILL_ROOT / "commands" / "deck-economics.md"
NARRATIVE_MD = SKILL_ROOT / "commands" / "deck-narrative.md"
REVISE_MD = SKILL_ROOT / "commands" / "deck-revise.md"
AUDIT_MD = SKILL_ROOT / "commands" / "deck-audit.md"

WIRE_KEY = "incoherent_or_absent_business_model"
DISPLAY_NAME = "Incoherent or absent business model"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC1: rubric.md §"Critical flags" lists five standing flags and the new
# flag's prose entry names all three trigger conditions + wire-key
# ---------------------------------------------------------------------------


def test_rubric_md_intro_bumps_to_five_standing_critical_flags():
    """AC1: the §"Critical flags" intro prose must bump from "four
    standing critical flags" to "five standing critical flags"."""
    body = _read(RUBRIC_MD)
    assert "five standing critical flags" in body, (
        'rubric.md §"Critical flags" intro MUST say "five standing '
        'critical flags" — issue #552 introduces the 5th standing flag.'
    )
    # The pre-#552 phrasing must be gone.
    assert "four standing critical flags" not in body, (
        'rubric.md MUST NOT retain the pre-#552 "four standing critical '
        'flags" prose.'
    )


def test_rubric_md_critical_flags_lists_new_flag_display_name():
    """AC1: the §"Critical flags" list must contain the new flag's
    display name."""
    body = _read(RUBRIC_MD)
    assert DISPLAY_NAME in body, (
        f'rubric.md §"Critical flags" MUST list the new flag '
        f'"{DISPLAY_NAME}" as the 5th standing flag.'
    )


def test_rubric_md_critical_flags_names_wire_key():
    """AC1: the §"Critical flags" entry for the new flag must name the
    snake_case wire-key used in ``_summary.md.critical_flag_notes[].type``."""
    body = _read(RUBRIC_MD)
    assert WIRE_KEY in body, (
        f'rubric.md MUST name the wire-key "{WIRE_KEY}" — the '
        f"snake_case identifier critic siblings emit in "
        f"`critical_flag_notes[].type`."
    )


def test_rubric_md_critical_flags_documents_all_three_trigger_conditions():
    """AC1: the new flag's prose entry must document all three trigger
    disjuncts (no revenue mechanic / contradictory unit economics /
    counterparty-rejecting terms)."""
    body = _read(RUBRIC_MD)
    # (a) no revenue mechanic
    assert "No revenue mechanic" in body or "no revenue mechanic" in body, (
        "rubric.md MUST name the (a) trigger: no revenue mechanic stated."
    )
    # (b) internally contradictory unit economics
    assert "Internally contradictory unit economics" in body or "internally contradictory unit economics" in body, (
        "rubric.md MUST name the (b) trigger: internally contradictory "
        "unit economics."
    )
    # (c) counterparty-rejecting terms
    assert "Counterparty-rejecting terms" in body or "counterparty-rejecting terms" in body, (
        "rubric.md MUST name the (c) trigger: counterparty-rejecting "
        "terms."
    )


# ---------------------------------------------------------------------------
# AC2: the new flag's ownership routes to deck-economics (primary) +
# deck-review (fallback)
# ---------------------------------------------------------------------------


def test_rubric_md_flag_ownership_names_deck_economics_primary():
    """AC2: rubric.md MUST name ``deck-economics`` as the primary
    raiser of the new flag (post-#551 ownership flip)."""
    body = _read(RUBRIC_MD)
    # Find the flag entry section and confirm deck-economics is named
    # as primary.
    flag_idx = body.find(DISPLAY_NAME)
    assert flag_idx >= 0, (
        "rubric.md MUST contain the new flag display name; ownership "
        "check requires the prose block to exist."
    )
    # Look in a reasonable window after the flag header
    window = body[flag_idx : flag_idx + 4000]
    assert "deck-economics" in window, (
        f'rubric.md §"Critical flags" entry for "{DISPLAY_NAME}" MUST '
        f"name `deck-economics` as the primary raiser."
    )
    assert "deck-review" in window, (
        f'rubric.md §"Critical flags" entry for "{DISPLAY_NAME}" MUST '
        f"name `deck-review` as the fallback raiser."
    )


# ---------------------------------------------------------------------------
# AC3: deck-review.md step 7 enumerates the new flag with three triggers +
# fallback-ownership note
# ---------------------------------------------------------------------------


def test_deck_review_md_step_7_enumerates_new_flag():
    """AC3: deck-review.md step 7 ("Identify critical flags") MUST
    enumerate the new flag with its display name and wire-key."""
    body = _read(REVIEW_MD)
    assert DISPLAY_NAME in body, (
        f'deck-review.md MUST enumerate "{DISPLAY_NAME}" in step 7.'
    )
    assert WIRE_KEY in body, (
        f'deck-review.md MUST name the wire-key "{WIRE_KEY}" — the '
        f"snake_case identifier this critic emits when it raises the "
        f"flag as fallback."
    )


def test_deck_review_md_names_deck_economics_as_primary_for_new_flag():
    """AC3: deck-review.md MUST name ``deck-economics`` as the primary
    owner of the new flag (this critic is the fallback)."""
    body = _read(REVIEW_MD)
    # Find the flag entry section and confirm deck-economics is named
    # as primary near it.
    flag_idx = body.find(DISPLAY_NAME)
    assert flag_idx >= 0
    window = body[flag_idx : flag_idx + 2000]
    assert "deck-economics" in window, (
        f"deck-review.md MUST name deck-economics as the primary "
        f'owner of "{DISPLAY_NAME}" (this critic raises only as '
        f"fallback)."
    )
    assert "fallback" in window.lower(), (
        f"deck-review.md MUST frame this critic's role as fallback "
        f'for "{DISPLAY_NAME}".'
    )


def test_deck_review_md_drops_sibling_552_placeholder():
    """AC3: deck-review.md MUST drop the pre-#552 placeholder
    ("sibling #552 introduces a dedicated 'Incoherent or absent
    business model' flag") — the conditional has resolved."""
    body = _read(REVIEW_MD)
    assert "sibling #552 introduces" not in body, (
        'deck-review.md MUST drop the pre-#552 placeholder "sibling '
        '#552 introduces a dedicated …" — the flag has shipped.'
    )


# ---------------------------------------------------------------------------
# AC4: deck-economics.md step 6 flips the placeholder into an active
# flag-raise procedure naming this critic as primary
# ---------------------------------------------------------------------------


def test_deck_economics_md_drops_pre_552_placeholder():
    """AC4: deck-economics.md MUST drop the pre-#552 conditional
    placeholder ("If #552 has NOT landed at #551 build time…") — the
    flag has shipped and this critic is now the primary raiser."""
    body = _read(ECONOMICS_MD)
    assert "If #552 has NOT landed" not in body, (
        'deck-economics.md step 6 MUST drop the "If #552 has NOT '
        'landed at #551 build time" placeholder — the conditional has '
        "resolved."
    )
    assert "this critic does NOT raise it" not in body, (
        "deck-economics.md step 6 MUST drop the negative phrasing "
        '"this critic does NOT raise it" — the critic IS the primary '
        "raiser now."
    )


def test_deck_economics_md_names_itself_as_primary_for_new_flag():
    """AC4: deck-economics.md MUST frame this critic as the **primary**
    raiser of the new flag with deck-review as fallback."""
    body = _read(ECONOMICS_MD)
    flag_idx = body.find(DISPLAY_NAME)
    assert flag_idx >= 0, (
        f"deck-economics.md MUST mention the new flag display name."
    )
    window = body[flag_idx : flag_idx + 4000]
    assert "PRIMARY" in window or "primary" in window, (
        "deck-economics.md MUST name this critic as the primary "
        "raiser of the new flag."
    )
    assert "fallback" in window.lower() and "deck-review" in window, (
        "deck-economics.md MUST name deck-review as the fallback "
        "raiser of the new flag."
    )


def test_deck_economics_md_documents_all_three_trigger_conditions():
    """AC4: deck-economics.md step 6 MUST document all three trigger
    disjuncts inline so the critic has actionable raise criteria."""
    body = _read(ECONOMICS_MD)
    flag_idx = body.find(DISPLAY_NAME)
    assert flag_idx >= 0
    window = body[flag_idx : flag_idx + 6000]
    # (a)
    assert "No revenue mechanic" in window or "no revenue mechanic" in window, (
        "deck-economics.md MUST document the (a) no-revenue-mechanic "
        "trigger inline."
    )
    # (b)
    assert "contradictory unit economics" in window.lower() or "Internally contradictory" in window, (
        "deck-economics.md MUST document the (b) contradictory-unit-"
        "economics trigger inline."
    )
    # (c)
    assert "counterparty-rejecting" in window.lower() or "Counterparty-rejecting" in window, (
        "deck-economics.md MUST document the (c) counterparty-"
        "rejecting-terms trigger inline."
    )


def test_deck_economics_md_names_wire_key_for_new_flag():
    """AC4: deck-economics.md MUST name the snake_case wire-key the
    critic emits in ``_summary.md.critical_flag_notes[].type``."""
    body = _read(ECONOMICS_MD)
    assert WIRE_KEY in body, (
        f'deck-economics.md MUST name the wire-key "{WIRE_KEY}".'
    )


# ---------------------------------------------------------------------------
# AC5: deck-narrative.md Absent-ask twin cross-references the new flag
# ---------------------------------------------------------------------------


def test_deck_narrative_md_absent_ask_cross_references_new_flag():
    """AC5: deck-narrative.md `Absent ask` (the structural twin on the
    narrative side) MUST cross-reference the new flag as the dim-10
    parallel disqualifier."""
    body = _read(NARRATIVE_MD)
    # Find the Absent ask section and confirm the new flag is named in
    # the same block.
    absent_idx = body.find("`Absent ask`")
    assert absent_idx >= 0, (
        "deck-narrative.md MUST contain the `Absent ask` flag entry."
    )
    window = body[absent_idx : absent_idx + 2000]
    assert DISPLAY_NAME in window or "Incoherent or absent business model" in window, (
        "deck-narrative.md `Absent ask` entry MUST cross-reference "
        '"Incoherent or absent business model" as the structural twin '
        "on the model side."
    )


# ---------------------------------------------------------------------------
# AC6: SKILL.md bumps the prose references from "four" to "five" and
# enumerates the new flag
# ---------------------------------------------------------------------------


def test_skill_md_bumps_critical_flags_count_to_five():
    """AC6: SKILL.md MUST bump "four deck-specific critical flags" →
    "five deck-specific critical flags" in the thresholds section."""
    body = _read(SKILL_MD)
    assert "five deck-specific critical flags" in body, (
        'SKILL.md MUST say "five deck-specific critical flags" in the '
        "thresholds section."
    )
    assert "four deck-specific critical flags" not in body, (
        'SKILL.md MUST NOT retain the pre-#552 "four deck-specific '
        'critical flags" prose.'
    )


def test_skill_md_bumps_critical_flag_conditions_count_to_five():
    """AC6: SKILL.md MUST bump "four critical-flag conditions" →
    "five critical-flag conditions" in the §Rubric pointer."""
    body = _read(SKILL_MD)
    assert "five critical-flag conditions" in body, (
        'SKILL.md MUST say "five critical-flag conditions" in the '
        "§Rubric pointer."
    )
    assert "four critical-flag conditions" not in body, (
        'SKILL.md MUST NOT retain the pre-#552 "four critical-flag '
        'conditions" prose.'
    )


def test_skill_md_enumerates_new_flag_with_wire_key():
    """AC6: SKILL.md MUST list the new flag as the 5th bullet in the
    deck-specific critical-flags list, with the wire-key."""
    body = _read(SKILL_MD)
    assert DISPLAY_NAME in body, (
        f"SKILL.md MUST list the new flag display name "
        f'"{DISPLAY_NAME}".'
    )
    assert WIRE_KEY in body, (
        f'SKILL.md MUST name the wire-key "{WIRE_KEY}".'
    )


# ---------------------------------------------------------------------------
# AC7: deck-revise.md step 2 aggregation enumerates all five standing flags
# ---------------------------------------------------------------------------


def test_deck_revise_md_aggregation_enumerates_five_standing_types():
    """AC7: deck-revise.md step 2 (aggregation prose) MUST enumerate
    all five standing flag types so the reviser's documentation is
    coherent with the rubric."""
    body = _read(REVISE_MD)
    # All five wire-keys should appear in the aggregation prose
    for wire_key in (
        "fabricated_traction",
        "fabricated_team_credentials",
        "market_math_error",
        "absent_ask",
        WIRE_KEY,
    ):
        assert wire_key in body, (
            f'deck-revise.md MUST enumerate the "{wire_key}" wire-key '
            f"in the step 2 aggregation prose so all five standing "
            f"flag types are documented."
        )


# ---------------------------------------------------------------------------
# AC8: deck-audit.md critical_flag_notes example block documents the new
# wire-key as a valid type
# ---------------------------------------------------------------------------


def test_deck_audit_md_critical_flag_notes_example_documents_new_type():
    """AC8: deck-audit.md ``critical_flag_notes[].type`` example block
    MUST surface the new wire-key as part of the documented five-type
    vocabulary (for the auditor to surface flags raised by prior
    critic siblings)."""
    body = _read(AUDIT_MD)
    assert WIRE_KEY in body, (
        f'deck-audit.md MUST name the wire-key "{WIRE_KEY}" in the '
        f"critical_flag_notes example block — the auditor surfaces "
        f"flags raised by prior critic siblings."
    )
