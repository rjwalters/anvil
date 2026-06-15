"""Doc-coverage smoke tests for the dim 10 perspective substrate extension.

Per issue #554 acceptance criteria: assert that the deck perspective
substrate rule (originally feeding dims 3 + 4 per issue #150 / PR #154 /
the rubric–perspective interaction snippet) has been extended to **also
feed dim 10 (Business-model & unit-economics credibility)** without
introducing a new deduction on perspective-absent threads (the
opportunistic-not-punitive contract).

The canary contract this guards (post-#550 baseline + #554 extension):

  1. ``anvil/skills/deck/rubric.md`` §"Perspective substrate" is
     retitled to name dims 3, 4, **and 10**, and gains a parallel-shape
     dim 10 bullet describing the pricing / margin / rev-share
     substrate behavior.
  2. The opportunistic-not-punitive contract is restated for dim 10:
     with-perspective-cited can lift the score; without-perspective
     takes **no new deduction** (backward compat — load-bearing).
  3. ``anvil/skills/deck/commands/deck-review.md`` dim 10 sub-step
     references the substrate behavior (and points at the rubric
     §"Perspective substrate" section rather than re-implementing the
     discovery rule).
  4. Dim 10 substrate ownership is described as "owned by whichever
     critic owns dim 10 at build time — `deck-review` as fallback in
     v0; future `deck-economics` after #551." This issue does NOT
     depend on #551 landing first.
  5. ``anvil/lib/snippets/rubric.md`` v0-adopters paragraph is updated
     to "`anvil:deck` (dims 3 + 4 + 10)" so the cross-skill substrate
     contract list (the single source of truth for which skill consumes
     perspective on which dims) does not drift out of sync.

These tests assert on substring presence only — they do NOT validate
prose quality or the LLM-driven runtime semantics. Behavioural
assertions belong in consumer-side integration tests.

Per-skill test filename convention (#58): file is named with a
``test_deck_review_`` prefix (dim 10 is owned by ``deck-review`` in v0
as fallback) so it never collides with the existing parallel-shape
``test_deck_market_perspective_crosscheck_doc.py`` for dims 3 / 4.
After #551 merges and ownership moves to ``deck-economics``, the test
stays at its current path — it's a substrate-behavior pin, not a
critic-implementation pin (same shape as
``test_deck_market_perspective_crosscheck_doc.py`` surviving any
future market-critic refactor).
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "deck"
RUBRIC_MD = SKILL_ROOT / "rubric.md"
REVIEW_MD = SKILL_ROOT / "commands" / "deck-review.md"

SNIPPETS_RUBRIC = (
    Path(__file__).resolve().parents[3]
    / "anvil"
    / "lib"
    / "snippets"
    / "rubric.md"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# rubric.md — §"Perspective substrate" retitled + dim 10 bullet (AC1)
# ---------------------------------------------------------------------------


def test_rubric_md_perspective_substrate_section_names_dim10():
    """AC1: the §"Perspective substrate" section title must name dims 3,
    4, AND 10 so the cross-skill scope is unambiguous at the section
    header (not buried in a paragraph)."""
    body = _read(RUBRIC_MD)
    assert "Perspective substrate (dims 3, 4, 10)" in body, (
        "rubric.md §\"Perspective substrate\" MUST be retitled to "
        "\"Perspective substrate (dims 3, 4, 10)\" per issue #554 AC1 "
        "— the section header is the single load-bearing signal that "
        "dim 10 has joined the substrate rule. A bare "
        "\"Perspective substrate (dims 3, 4)\" title is a "
        "documentation-drift bug waiting to happen."
    )


def test_rubric_md_dim10_substrate_bullet_present():
    """AC1: the dim 10 substrate bullet must be present and named for
    business-model / unit-economics credibility, parallel in shape to
    the existing dim 3 / dim 4 bullets."""
    body = _read(RUBRIC_MD)
    # The dim 10 bullet must name the dim and at least one of the three
    # canary failure modes (pricing / margin / rev-share). The bullet is
    # the load-bearing prose; the section title alone is not enough.
    assert "Business-model & unit-economics credibility (dim 10)" in body, (
        "rubric.md §\"Perspective substrate\" MUST contain a dim 10 "
        "bullet titled \"Business-model & unit-economics credibility "
        "(dim 10)\" per issue #554 AC1 — parallel in shape to the "
        "existing dim 3 / dim 4 bullets."
    )
    # The bullet must mention at least pricing AND rev-share (the two
    # named canary anchors from the issue body).
    assert "rev-share" in body.lower() or "rev share" in body.lower(), (
        "rubric.md dim 10 substrate bullet MUST mention rev-share as a "
        "canary substrate type (Nubart-shaped comparables, per "
        "issue #554)."
    )
    assert "pricing" in body.lower(), (
        "rubric.md dim 10 substrate bullet MUST mention pricing as a "
        "canary substrate type (pricing gravity, per issue #554)."
    )


# ---------------------------------------------------------------------------
# rubric.md — opportunistic-not-punitive contract for dim 10 (AC2)
# ---------------------------------------------------------------------------


def test_rubric_md_dim10_opportunistic_not_punitive_contract():
    """AC2 (load-bearing backward-compat): the opportunistic-not-punitive
    contract must be restated for dim 10. The substring co-occurrence
    check mirrors the union-form assertion shape used by the existing
    dim 3 / 4 doc-coverage tests — assert all three load-bearing tokens
    appear in the file so a future edit cannot drift the rule to a
    punitive shape without tripping the test.

    The three tokens:
      1. "opportunistic" — the framework's name for the rule shape.
      2. "no new deduction" — the explicit backward-compat assertion.
      3. "Without perspective" — the without-perspective branch must be
         named (otherwise a reader can't tell whether the rule applies
         only with-perspective).
    """
    body = _read(RUBRIC_MD)
    assert "opportunistic, not" in body.lower() or "opportunistic-not-punitive" in body.lower(), (
        "rubric.md §\"Perspective substrate\" MUST restate the "
        "opportunistic-not-punitive contract for dim 10 (the framework "
        "name for the rule shape — see "
        "anvil/lib/snippets/rubric.md §\"Rubric–perspective "
        "interaction\")."
    )
    assert "No new deduction" in body or "no new deduction" in body, (
        "rubric.md §\"Perspective substrate\" MUST explicitly state "
        "\"no new deduction\" for the without-perspective branch — "
        "load-bearing backward-compat assertion per issue #554 AC2. "
        "Without this token, a future edit can accidentally drift the "
        "rule punitive (the failure mode this assertion exists to "
        "catch)."
    )
    assert "Without perspective" in body, (
        "rubric.md §\"Perspective substrate\" MUST name the "
        "\"Without perspective\" branch explicitly so a reader can "
        "tell which branch the no-new-deduction rule applies to."
    )
    # The without-perspective branch must explicitly name dim 10 alongside
    # dims 3 / 4 (otherwise the dim 10 backward-compat assertion is
    # implicit and prone to drift).
    assert "dims 3, 4, and 10" in body or "dim 10" in body, (
        "rubric.md §\"Perspective substrate\" MUST name dim 10 "
        "explicitly in the opportunistic-not-punitive contract "
        "restatement so the dim 10 backward-compat is unambiguous."
    )


# ---------------------------------------------------------------------------
# rubric.md — dim 10 substrate ownership wiring (AC3)
# ---------------------------------------------------------------------------


def test_rubric_md_dim10_substrate_ownership_names_deck_review_fallback():
    """AC3: the substrate ownership prose must describe dim 10 as
    "owned by whichever critic owns dim 10 at build time — `deck-review`
    as fallback in v0; future `deck-economics` after #551." This issue
    does NOT depend on #551 landing first, so the prose must name
    deck-review as the v0 owner and deck-economics as the post-#551
    successor."""
    body = _read(RUBRIC_MD)
    # The §"Perspective substrate" section must name both deck-review
    # (v0 fallback owner) and deck-economics (post-#551 primary owner)
    # so the substrate prose is internally consistent at every
    # intermediate state (#554 lands without #551).
    assert "deck-economics" in body, (
        "rubric.md §\"Perspective substrate\" MUST name "
        "deck-economics as the post-#551 primary owner for dim 10 "
        "substrate (issue #554 AC3 — the ownership-pointer language "
        "ships with #554 even though #551 has not merged)."
    )
    # The v0 fallback must be named deck-review specifically.
    assert "deck-review" in body, (
        "rubric.md §\"Perspective substrate\" MUST name deck-review "
        "as the v0 fallback owner for dim 10 substrate (issue #554 AC3)."
    )


# ---------------------------------------------------------------------------
# deck-review.md — Dim 10 sub-step references substrate behavior (AC4)
# ---------------------------------------------------------------------------


def test_deck_review_md_dim10_substep_references_perspective_substrate():
    """AC4: the deck-review.md Dim 10 sub-step must reference the
    substrate behavior or point at the rubric §"Perspective substrate"
    section (so the reviewer / agent learns the substrate-backed scoring
    upgrade exists)."""
    body = _read(REVIEW_MD)
    # The dim 10 sub-step (or its perspective sub-bullet) must mention
    # perspective AND substrate-backed scoring. The substring "Dim 10"
    # appears multiple times in the file (in the dim definition, in the
    # worked-example table, and in the new sub-step); we assert the
    # union-form presence of the substrate vocabulary near dim 10
    # vocabulary.
    assert "Dim 10" in body, (
        "deck-review.md MUST contain a Dim 10 sub-step (already shipped "
        "in #550)."
    )
    assert "Perspective substrate" in body, (
        "deck-review.md Dim 10 sub-step MUST reference the rubric "
        "§\"Perspective substrate\" section by name so the reviewer "
        "knows to apply the substrate-backed scoring upgrade per "
        "issue #554 AC4."
    )
    assert "substrate-backed" in body, (
        "deck-review.md Dim 10 sub-step MUST use the term "
        "\"substrate-backed\" to label the with-perspective scoring "
        "upgrade (parallel to the existing dim 3 / 4 substrate prose "
        "in rubric.md)."
    )


def test_deck_review_md_dim10_substep_documents_graceful_skip():
    """AC4 (backward-compat reinforcement at the command level): the
    deck-review Dim 10 sub-step must explicitly describe the
    perspective-absent path as graceful (no error, no finding, no new
    deduction) so the agent does not surface "perspective missing" as a
    dim 10 finding on legacy threads."""
    body = _read(REVIEW_MD)
    # The graceful-skip vocabulary must appear within the dim 10 prose.
    # We do a coarse file-level check (mirroring the dim 3 / 4 test's
    # union-form assertion at lines 119-156 of
    # test_deck_market_perspective_crosscheck_doc.py).
    assert "graceful skip" in body.lower() or "gracefully" in body.lower() or "graceful" in body.lower(), (
        "deck-review.md Dim 10 sub-step MUST document the "
        "perspective-absent path as graceful (no error, no finding) "
        "per issue #554 AC4 + the backward-compat contract."
    )
    assert "no new deduction" in body.lower(), (
        "deck-review.md Dim 10 sub-step MUST explicitly state "
        "\"no new deduction\" for the perspective-absent path — "
        "load-bearing backward-compat assertion mirrored from the "
        "rubric.md substrate prose."
    )


# ---------------------------------------------------------------------------
# snippets/rubric.md — v0 adopters list names dim 10 (AC5)
# ---------------------------------------------------------------------------


def test_snippets_rubric_md_v0_adopters_names_deck_dim10():
    """AC5: the cross-skill v0-adopters paragraph in
    anvil/lib/snippets/rubric.md (the single source of truth for which
    skill consumes perspective on which dims) MUST be updated to name
    anvil:deck as adopting dim 10 alongside dims 3 + 4. Missing this
    update is a documentation drift bug — the snippet is the contract
    other skills read to understand the substrate-rule shape."""
    body = _read(SNIPPETS_RUBRIC)
    assert "anvil:deck` (dims 3 + 4 + 10)" in body, (
        "anvil/lib/snippets/rubric.md v0-adopters paragraph MUST be "
        "updated from \"`anvil:deck` (dims 3 + 4)\" to "
        "\"`anvil:deck` (dims 3 + 4 + 10)\" per issue #554 AC5. The "
        "cross-skill substrate contract list is the single source of "
        "truth for which skill consumes perspective on which dims; "
        "missing the dim 10 update here is a documentation drift bug "
        "waiting to happen."
    )


# ---------------------------------------------------------------------------
# Backward compatibility — explicit pin so a future edit cannot drift
# the rule punitive (AC6 / risks section in #554 body)
# ---------------------------------------------------------------------------


def test_rubric_md_dim10_substrate_backward_compat_pin():
    """Load-bearing backward-compat pin: the dim 10 substrate prose
    must explicitly state either "no new deduction" OR "scores against
    the pre-perspective baseline" (preferably both) so a future edit
    cannot accidentally drift the rule punitive. This mirrors the
    existing dim 3 / 4 baseline language in the same section."""
    body = _read(RUBRIC_MD)
    # Either token alone is sufficient backward-compat protection; both
    # appearing in the substrate section is the documented contract.
    has_no_new_deduction = (
        "no new deduction" in body.lower()
    )
    has_pre_perspective_baseline = (
        "pre-perspective baseline" in body.lower()
    )
    assert has_no_new_deduction and has_pre_perspective_baseline, (
        "rubric.md §\"Perspective substrate\" MUST explicitly state "
        "BOTH \"no new deduction\" AND \"pre-perspective baseline\" "
        "for the perspective-absent branch — the load-bearing "
        "backward-compat assertions per issue #554 AC2 + the risks "
        "section of the issue body. A future edit that drops either "
        "token risks drifting the rule punitive without tripping the "
        "test."
    )
