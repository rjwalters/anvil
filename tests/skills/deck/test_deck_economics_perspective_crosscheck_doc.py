"""Doc-coverage smoke tests for the deck-economics ↔ perspective cross-check.

Per issue #551 (the new deck-economics critic owning dim 10) +
issue #557 (the perspective substrate extended to dim 10): assert that
``deck-economics.md`` documents the perspective cross-check pattern from
``anvil/lib/snippets/perspective.md`` (PR #154) and that the
substrate-backed scoring upgrade is described against the rubric §
"Perspective substrate (dims 3, 4, 10)" prose without re-implementing
the discovery rule locally.

The canary contract this guards:

  1. ``deck-economics.md`` consults ``<thread>.{N}.perspective/candidates.md``
     when present (issue #551 + post-#557 substrate ownership flip).
  2. ``deck-economics.md`` gracefully skips when the perspective sibling is
     absent — NO error, NO finding about the absence (preserves the
     opportunistic-not-punitive contract per
     ``anvil/lib/snippets/perspective.md``).
  3. The three substrate-backed canary failure modes are named:
     pricing gravity, rev-share comparables, margin comparables
     (per the #557 substrate prose).
  4. The doc references ``anvil/lib/snippets/perspective.md`` as the
     canonical contract for perspective sibling shape (so the discovery
     rule is not re-implemented locally).

These tests assert on substring presence only — they do NOT validate
prose quality or the LLM-driven runtime semantics. Behavioural
assertions belong in consumer-side integration tests.

Per-skill test filename convention (#58): file is named with a
``test_deck_economics_`` prefix so it never collides with the existing
parallel-shape ``test_deck_market_perspective_crosscheck_doc.py`` for
dims 3 / 4.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "deck"
ECONOMICS_MD = SKILL_ROOT / "commands" / "deck-economics.md"

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
    """The perspective snippet must be on disk: deck-economics's
    cross-check soft-depends on the snippet's ``candidates.md``
    contract."""
    assert PERSPECTIVE_SNIPPET.exists(), (
        "anvil/lib/snippets/perspective.md (PR #154) must exist — "
        "deck-economics's perspective cross-check is wired against this "
        "contract."
    )


# ---------------------------------------------------------------------------
# deck-economics.md — perspective cross-check wiring (issue #551, #557)
# ---------------------------------------------------------------------------


def test_economics_md_references_perspective_candidates():
    """deck-economics.md must reference ``candidates.md`` to wire the
    perspective cross-check against the architect-specified path."""
    body = _read(ECONOMICS_MD)
    assert "candidates.md" in body, (
        "deck-economics.md MUST reference candidates.md to consult the "
        "perspective sibling per issue #551 + post-#557 substrate "
        "ownership flip."
    )


def test_economics_md_references_perspective_sibling_path():
    """The canonical path ``<thread>.{N}.perspective/candidates.md`` must
    appear so the agent has a concrete discovery target."""
    body = _read(ECONOMICS_MD)
    assert "perspective/candidates.md" in body, (
        "deck-economics.md MUST reference the perspective sibling path "
        "<thread>.{N}.perspective/candidates.md per issue #551."
    )


def test_economics_md_references_perspective_snippet():
    """deck-economics.md should point readers at the framework snippet
    contract (anvil/lib/snippets/perspective.md) so the discovery and
    no-fabrication rules are not re-implemented locally."""
    body = _read(ECONOMICS_MD)
    assert "anvil/lib/snippets/perspective.md" in body, (
        "deck-economics.md MUST point to anvil/lib/snippets/perspective.md "
        "as the canonical contract for perspective sibling shape."
    )


def test_economics_md_documents_graceful_skip_when_absent():
    """deck-economics MUST NOT error if the perspective sibling is
    absent — the cross-check gracefully skips. Document the
    backwards-compat path explicitly."""
    body = _read(ECONOMICS_MD)
    # The doc must surface both the "absent" path and a "graceful"
    # framing so the agent doesn't treat absence as an error.
    assert "absent" in body.lower(), (
        "deck-economics.md MUST document the perspective-absent path."
    )
    assert "graceful" in body.lower() or "gracefully" in body.lower(), (
        "deck-economics.md MUST describe the perspective-absent behavior "
        "as graceful (no error) per the opportunistic-not-punitive "
        "contract."
    )


def test_economics_md_documents_no_error_on_absent_perspective():
    """The graceful-skip prose must explicitly say absence is NOT an
    error and NOT a finding (so the agent doesn't surface 'perspective
    missing' as a deck-economics finding)."""
    body = _read(ECONOMICS_MD)
    assert "NEVER an error" in body or "never an error" in body.lower(), (
        "deck-economics.md MUST state that absence of perspective is "
        "NEVER an error per the opportunistic-not-punitive contract."
    )


def test_economics_md_documents_backwards_compat():
    """Behavior on threads with no perspective sibling is unchanged
    from the brief-only baseline scoring."""
    body = _read(ECONOMICS_MD)
    assert (
        "backwards-compat" in body.lower()
        or "backwards compat" in body.lower()
        or "v0 behavior" in body.lower()
    ), (
        "deck-economics.md MUST document that perspective-absent "
        "behavior preserves the v0 (pre-perspective) brief-only "
        "scoring baseline."
    )


def test_economics_md_no_new_deduction_on_perspective_absent():
    """The opportunistic-not-punitive contract requires NO new deduction
    on perspective-absent threads — the substrate is a credit lift, not
    a punitive gate (parallel to deck-market dim 3 / 4 behaviour)."""
    body = _read(ECONOMICS_MD)
    assert "no new deduction" in body.lower() or "No new deduction" in body, (
        "deck-economics.md MUST explicitly state \"No new deduction\" "
        "for the perspective-absent path — the load-bearing "
        "backward-compat assertion mirrored from the rubric.md "
        "substrate prose."
    )


# ---------------------------------------------------------------------------
# deck-economics.md — three substrate-backed canary failure modes (#557)
# ---------------------------------------------------------------------------


def test_economics_md_names_pricing_gravity_canary():
    """The three substrate-backed canary failure modes are named in the
    #557 substrate prose. The first: pricing gravity (a comparable's
    free or low-priced offering anchors why the proposed price is or
    isn't defensible to the counterparty)."""
    body = _read(ECONOMICS_MD)
    assert "pricing gravity" in body.lower(), (
        "deck-economics.md MUST name the \"pricing gravity\" canary "
        "substrate failure mode (per the #557 substrate prose)."
    )


def test_economics_md_names_rev_share_comparables_canary():
    """Second canary: rev-share comparables (a published platform
    rev-share split anchors why the deck's proposed split is
    defensible)."""
    body = _read(ECONOMICS_MD)
    assert "rev-share comparables" in body.lower() or "rev share comparables" in body.lower(), (
        "deck-economics.md MUST name the \"rev-share comparables\" "
        "canary substrate failure mode (per the #557 substrate prose)."
    )


def test_economics_md_names_margin_comparables_canary():
    """Third canary: margin comparables (published gross margins for
    comparable SaaS / platform / hardware businesses anchor whether the
    deck's stated contribution margin at scale is plausible)."""
    body = _read(ECONOMICS_MD)
    assert "margin comparables" in body.lower(), (
        "deck-economics.md MUST name the \"margin comparables\" canary "
        "substrate failure mode (per the #557 substrate prose)."
    )


# ---------------------------------------------------------------------------
# deck-economics.md — substrate-backed scoring vocabulary
# ---------------------------------------------------------------------------


def test_economics_md_uses_substrate_backed_vocabulary():
    """The doc must use the term \"substrate-backed\" to label the
    with-perspective scoring upgrade (parallel to the existing dim 3 /
    4 substrate prose in rubric.md)."""
    body = _read(ECONOMICS_MD)
    assert "substrate-backed" in body, (
        "deck-economics.md MUST use the term \"substrate-backed\" to "
        "label the with-perspective scoring upgrade (parallel to the "
        "existing dim 3 / 4 substrate prose in rubric.md)."
    )
