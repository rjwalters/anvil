"""Doc-coverage smoke tests for the deck-market ↔ perspective cross-check.

Per issue #150 (Epic #143 / Phase 1C) acceptance criteria: assert that
``deck-market.md`` documents the perspective cross-check pattern from
``anvil/lib/snippets/perspective.md`` (PR #154) and that the new
"unmatched competitor" finding is defined with severity + graceful-skip
behavior.

The canary contract this guards:

  1. ``deck-market.md`` consults ``<thread>.{N}.perspective/candidates.md``
     when present (Phase 1C behavior).
  2. ``deck-market.md`` gracefully skips when the perspective sibling is
     absent — NO error, NO finding about the absence (preserves v0
     backwards-compat for threads that have never run
     ``deck-perspective``).
  3. The new finding type "unmatched competitor" is defined with
     severity = warning (NOT critical on its own; the existing
     "Fabricated competitive claims" critical flag remains the
     escalation surface, with the unmatched-competitor warning as its
     evidentiary base).
  4. The deck rubric (``rubric.md``) acknowledges the perspective
     cross-check on dim 4 (Solution differentiation).

These tests assert on substring presence only — they do NOT validate
prose quality or the LLM-driven runtime semantics. Behavioural assertions
belong in consumer-side integration tests.

Per-skill test filename convention (#58): file is named with a
``test_deck_market_`` prefix so it never collides with a parallel-skill
test of the same shape (e.g., a future ``test_memo_perspective_*`` for
Phase 2).
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "deck"
MARKET_MD = SKILL_ROOT / "commands" / "deck-market.md"
RUBRIC_MD = SKILL_ROOT / "rubric.md"

PERSPECTIVE_SNIPPET = (
    Path(__file__).resolve().parents[3]
    / "anvil"
    / "lib"
    / "snippets"
    / "perspective.md"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Sanity: the framework snippet (PR #154) is the contract being consumed
# ---------------------------------------------------------------------------


def test_perspective_snippet_exists():
    """PR #154 must be on disk: deck-market's cross-check soft-depends on
    the snippet's ``candidates.md`` contract."""
    assert PERSPECTIVE_SNIPPET.exists(), (
        "anvil/lib/snippets/perspective.md (PR #154) must exist — "
        "deck-market's perspective cross-check is wired against this "
        "contract."
    )


def test_perspective_snippet_defines_candidates_md():
    """The snippet must document ``candidates.md`` as a load-bearing file
    name in the perspective sibling layout."""
    body = _read(PERSPECTIVE_SNIPPET)
    assert "candidates.md" in body, (
        "perspective.md snippet must document candidates.md as a "
        "load-bearing file name in the perspective sibling layout."
    )


# ---------------------------------------------------------------------------
# deck-market.md — perspective cross-check wiring (issue #150 AC1, AC3, AC4)
# ---------------------------------------------------------------------------


def test_market_md_references_perspective_candidates():
    """AC1: deck-market.md must reference ``candidates.md`` to wire the
    perspective cross-check against the architect-specified path."""
    body = _read(MARKET_MD)
    assert "candidates.md" in body, (
        "deck-market.md MUST reference candidates.md to consult the "
        "perspective sibling per issue #150 / Epic #143 / Phase 1C."
    )


def test_market_md_references_perspective_sibling_path():
    """The canonical path ``<thread>.{N}.perspective/candidates.md`` must
    appear so the agent has a concrete discovery target."""
    body = _read(MARKET_MD)
    assert "perspective/candidates.md" in body, (
        "deck-market.md MUST reference the perspective sibling path "
        "<thread>.{N}.perspective/candidates.md per issue #150."
    )


def test_market_md_references_perspective_snippet():
    """deck-market.md should point readers at the framework snippet
    contract (anvil/lib/snippets/perspective.md) so the discovery and
    no-fabrication rules are not re-implemented locally."""
    body = _read(MARKET_MD)
    assert "anvil/lib/snippets/perspective.md" in body, (
        "deck-market.md MUST point to anvil/lib/snippets/perspective.md "
        "as the canonical contract for perspective sibling shape."
    )


def test_market_md_documents_graceful_skip_when_absent():
    """AC3 + AC4: deck-market MUST NOT error if the perspective sibling
    is absent — the cross-check gracefully skips. Document the
    backwards-compat path explicitly."""
    body = _read(MARKET_MD)
    # The doc must surface both the "absent" path and a "graceful"
    # framing so the agent doesn't treat absence as an error.
    assert "absent" in body.lower(), (
        "deck-market.md MUST document the perspective-absent path."
    )
    assert "graceful" in body.lower() or "gracefully" in body.lower(), (
        "deck-market.md MUST describe the perspective-absent behavior as "
        "graceful (no error) per issue #150 AC4."
    )


def test_market_md_documents_no_error_on_absent_perspective():
    """The graceful-skip prose must explicitly say absence is NOT an
    error and NOT a finding (so the agent doesn't surface 'perspective
    missing' as a deck-market finding)."""
    body = _read(MARKET_MD)
    assert "NEVER an error" in body or "never an error" in body.lower(), (
        "deck-market.md MUST state that absence of perspective is "
        "NEVER an error (issue #150 AC4)."
    )


def test_market_md_documents_backwards_compat():
    """AC3: behavior on threads with no perspective sibling is
    unchanged from the v0 brief-only cross-check."""
    body = _read(MARKET_MD)
    assert (
        "backwards-compat" in body.lower()
        or "backwards compat" in body.lower()
        or "v0 behavior" in body.lower()
    ), (
        "deck-market.md MUST document that perspective-absent behavior "
        "preserves the v0 (pre-#150) brief-only cross-check."
    )


# ---------------------------------------------------------------------------
# deck-market.md — new finding type "unmatched competitor" (issue #150 AC2)
# ---------------------------------------------------------------------------


def test_market_md_defines_unmatched_competitor_finding():
    """AC2: a new finding type with the name "unmatched competitor"
    must be defined."""
    body = _read(MARKET_MD)
    assert "unmatched competitor" in body.lower(), (
        "deck-market.md MUST define the 'unmatched competitor' finding "
        "type per issue #150 AC2."
    )


def test_market_md_unmatched_competitor_severity_is_warning():
    """The new finding must declare severity = warning (NOT critical)."""
    body = _read(MARKET_MD)
    # The severity-warning declaration MUST appear near the unmatched-
    # competitor definition. We do a coarse co-occurrence check — both
    # tokens must be present in the file and the file must explicitly
    # mark the severity as 'warning' (not critical) somewhere in the
    # unmatched-competitor prose.
    assert "unmatched competitor" in body.lower(), (
        "Severity test prereq: unmatched competitor must be defined."
    )
    assert "warning" in body.lower(), (
        "deck-market.md MUST mark the unmatched-competitor finding "
        "severity as 'warning' per issue #150."
    )
    # Verify it explicitly contrasts with critical to avoid drift.
    assert "not critical" in body.lower() or "NOT critical" in body, (
        "deck-market.md MUST explicitly contrast the new warning with "
        "the existing 'Fabricated competitive claims' critical flag "
        "to prevent severity drift."
    )


def test_market_md_unmatched_competitor_links_to_fabricated_claims():
    """The new warning is the evidentiary base for the existing
    "Fabricated competitive claims" critical flag — the doc must link
    them so the agent understands the escalation pattern."""
    body = _read(MARKET_MD)
    assert "Fabricated competitive claims" in body, (
        "deck-market.md MUST reference the existing 'Fabricated "
        "competitive claims' critical flag as the escalation surface "
        "for the unmatched-competitor warning (issue #150)."
    )
    assert "evidentiary base" in body.lower(), (
        "deck-market.md MUST frame the unmatched-competitor warning as "
        "the 'evidentiary base' that makes the Fabricated competitive "
        "claims critical flag triggerable (issue #150)."
    )


def test_market_md_documents_reference_set_union():
    """The cross-check substrate is brief ∪ perspective candidates; the
    doc must document this union semantics so the agent does not
    over-flag (e.g., flag a name that's in the brief but not in
    perspective)."""
    body = _read(MARKET_MD)
    # The union must be expressed in some form: either "∪", "union", or
    # the spelled-out "brief and perspective" / "brief AND perspective".
    has_union_form = (
        "∪" in body
        or "union" in body.lower()
        or "AND" in body  # "brief AND perspective" pattern
    )
    assert has_union_form, (
        "deck-market.md MUST document the reference-set union "
        "(brief ∪ perspective candidates) so the agent does not "
        "over-flag names attested by the brief alone."
    )


# ---------------------------------------------------------------------------
# rubric.md — dim 4 ownership references the cross-check (issue #150 AC2)
# ---------------------------------------------------------------------------


def test_rubric_md_dim4_references_perspective_crosscheck():
    """The deck rubric must acknowledge the new cross-check semantics on
    dim 4 (Solution differentiation) — the dimension owned by
    deck-market that scores competitive framing."""
    body = _read(RUBRIC_MD)
    assert "perspective" in body.lower(), (
        "rubric.md MUST reference the perspective cross-check now that "
        "deck-market consults the perspective sibling for competitor "
        "attestation (issue #150)."
    )


def test_rubric_md_documents_unmatched_competitor_warning():
    """The rubric should document the new warning so reviewers
    aggregating critic outputs understand the credit-reducer signal."""
    body = _read(RUBRIC_MD)
    assert "unmatched competitor" in body.lower(), (
        "rubric.md MUST document the 'unmatched competitor' warning "
        "type so the reviser interprets deck-market findings correctly "
        "(issue #150)."
    )


def test_rubric_md_links_warning_to_fabricated_competitive_claims():
    """The rubric must connect the warning to the existing Fabricated
    competitive claims critical flag — the escalation pattern is the
    load-bearing semantic, not the warning in isolation."""
    body = _read(RUBRIC_MD)
    assert "Fabricated competitive claims" in body, (
        "rubric.md MUST reference 'Fabricated competitive claims' as "
        "the critical-flag escalation for the new warning (issue #150)."
    )
