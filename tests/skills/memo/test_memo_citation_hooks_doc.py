"""Doc-coverage smoke tests for the memo citation-hook contract.

Per issue #137 acceptance criteria: cheap "grep-the-doc" regression guard
that the drafter-side citation-hook contract stays documented in the three
files it touches (memo-draft.md, rubric.md, SKILL.md) and that the three
documents reference each other coherently.

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The lifecycle commands themselves are
LLM-driven, so behavioural assertions belong in consumer-side integration
tests, not here.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with a similarly-shaped
``test_citation_hooks_doc`` another skill might pick.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
RUBRIC_MD = SKILL_ROOT / "rubric.md"
DRAFT_MD = SKILL_ROOT / "commands" / "memo-draft.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# memo-draft.md — drafter has an explicit citation-hook contract
# ---------------------------------------------------------------------------


def test_memo_draft_has_citation_hook_contract():
    body = _read(DRAFT_MD)
    assert "Citation-hook contract" in body or "citation-hook contract" in body, (
        "memo-draft.md MUST contain an explicit Citation-hook contract subsection "
        "(issue #137 Edit 1)"
    )


def test_memo_draft_names_three_hook_options():
    body = _read(DRAFT_MD).lower()
    # The contract names three alternative hooks: footnote, refs/ stub, hedge.
    assert "inline footnote" in body, (
        "memo-draft.md MUST name inline footnote as a citation hook option"
    )
    assert "refs/" in body and "stub" in body, (
        "memo-draft.md MUST name refs/<key>.md stubs as a citation hook option"
    )
    assert "hedge" in body or "hedged" in body, (
        "memo-draft.md MUST name in-prose hedging as a citation hook option"
    )


def test_memo_draft_names_load_bearing_claim_categories():
    body = _read(DRAFT_MD).lower()
    # The contract anchors on author-year citations + quantitative claims.
    assert "author-year" in body, (
        "memo-draft.md MUST name 'author-year' citations as triggering the hook contract"
    )
    # At least one of the named quantitative categories must appear in the contract prose.
    assert any(token in body for token in ("dollar amount", "percentage", "date", "multiplier")), (
        "memo-draft.md MUST name specific quantitative-claim categories "
        "(dollar amounts, percentages, dates, multipliers)"
    )


def test_memo_draft_permits_todo_stub():
    body = _read(DRAFT_MD)
    # The minimal stub form must be documented verbatim so the drafter knows
    # the floor of compliance.
    assert "TODO: source for" in body, (
        "memo-draft.md MUST document the minimal '# TODO: source for <claim>' stub form"
    )


def test_memo_draft_references_rubric_deduction():
    body = _read(DRAFT_MD).lower()
    # The drafter contract must point the reader at the rubric-side deduction rule.
    assert "dim 3" in body, (
        "memo-draft.md MUST reference dim 3 so the drafter knows where the "
        "deduction lands"
    )


# ---------------------------------------------------------------------------
# rubric.md — dim 3 has a named Citation hooks subsection with deduction rule
# ---------------------------------------------------------------------------


def test_rubric_has_citation_hooks_subsection():
    body = _read(RUBRIC_MD)
    assert "Citation hooks" in body, (
        "rubric.md MUST contain a 'Citation hooks' subsection (issue #137 Edit 2)"
    )


def test_rubric_citation_hooks_names_dim_3():
    body = _read(RUBRIC_MD)
    # The subsection heading should bind explicitly to dim 3.
    assert "dim 3" in body.lower(), (
        "rubric.md citation-hooks subsection MUST bind to dim 3 Evidence quality"
    )


def test_rubric_documents_per_instance_deduction_rule():
    body = _read(RUBRIC_MD).lower()
    # The rule must be per-instance, not a vague calibration adjustment.
    assert "per-instance" in body or "per instance" in body, (
        "rubric.md MUST document the per-instance deduction rule for citation hooks"
    )


def test_rubric_documents_one_two_point_calibration():
    body = _read(RUBRIC_MD).lower()
    # The single-point / two-point split is the calibration anchor.
    assert "single-point" in body or "one-point" in body or "1-point" in body, (
        "rubric.md MUST document the single-point deduction calibration"
    )
    assert "two-point" in body or "2-point" in body, (
        "rubric.md MUST document the two-point deduction for pervasive absence"
    )


def test_rubric_exempts_hedged_estimates():
    body = _read(RUBRIC_MD).lower()
    # The hedge exemption is the lighter-touch valve and must be documented.
    assert "hedged" in body or "hedge" in body, (
        "rubric.md MUST document that hedged estimates are exempt from deduction"
    )


def test_rubric_preserves_length_targets_subsection():
    """The new Citation hooks subsection MUST NOT displace the Length targets
    subsection added for issue #121."""
    body = _read(RUBRIC_MD)
    assert "Length targets" in body, (
        "rubric.md MUST preserve the existing 'Length targets (dim 7)' subsection"
    )


# ---------------------------------------------------------------------------
# SKILL.md — refs/ contract acknowledges drafter-written stubs
# ---------------------------------------------------------------------------


def test_skill_md_refs_line_acknowledges_stubs():
    body = _read(SKILL_MD)
    # The layout-block refs/ description must mention citation stubs.
    assert "citation stubs" in body.lower() or "citation-hook" in body.lower(), (
        "SKILL.md refs/ description MUST acknowledge drafter-written citation stubs "
        "(issue #137 Edit 3)"
    )


def test_skill_md_has_citation_stubs_section():
    body = _read(SKILL_MD)
    assert "Citation stubs" in body, (
        "SKILL.md MUST contain a 'Citation stubs' prose section explaining the "
        "thread-level stub convention"
    )


def test_skill_md_citation_stubs_documents_thread_level_location():
    body = _read(SKILL_MD)
    # The thread-level (NOT version-level) location is the load-bearing
    # design point of this section.
    assert "thread level" in body.lower() or "thread-level" in body.lower(), (
        "SKILL.md citation-stubs section MUST document the thread-level (not "
        "version-level) location"
    )
    # Anchor the contract to the actual on-disk path.
    assert "<thread>/refs/" in body, (
        "SKILL.md citation-stubs section MUST reference the <thread>/refs/ path"
    )


def test_skill_md_citation_stubs_documents_minimal_stub_form():
    body = _read(SKILL_MD)
    # The minimal stub form must appear so the SKILL-level contract matches
    # the memo-draft contract.
    assert "TODO: source for" in body, (
        "SKILL.md citation-stubs section MUST document the minimal stub form"
    )


# ---------------------------------------------------------------------------
# Cross-doc coherence — the three docs reference each other
# ---------------------------------------------------------------------------


def test_memo_draft_points_at_skill_md_citation_stubs():
    """The drafter contract should point at SKILL.md so the drafter knows
    where stubs land on disk."""
    body = _read(DRAFT_MD)
    assert "SKILL.md" in body or "Citation stubs" in body, (
        "memo-draft.md MUST reference SKILL.md (or the Citation stubs section) "
        "so the drafter knows where stubs live"
    )


def test_skill_md_points_at_memo_draft_evidence_contract():
    """The SKILL.md citation-stubs section should point at memo-draft.md
    so the contract surfaces are discoverable in either direction."""
    body = _read(SKILL_MD)
    assert "memo-draft" in body, (
        "SKILL.md citation-stubs section MUST reference memo-draft so the "
        "drafter contract is discoverable from SKILL.md"
    )


def test_skill_md_citation_stubs_points_at_rubric_dim_3():
    """The SKILL.md prose should point at the rubric dim 3 deduction rule
    so the reviewer-side enforcement is discoverable from SKILL.md."""
    body = _read(SKILL_MD)
    assert "rubric.md" in body, (
        "SKILL.md citation-stubs section MUST reference rubric.md so the "
        "dim 3 deduction rule is discoverable from SKILL.md"
    )
