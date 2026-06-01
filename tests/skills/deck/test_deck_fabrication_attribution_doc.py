"""Doc-coverage smoke tests for the deck fabrication-attribution contract
(Epic #130 / Phase 3F / issue #187).

The contract activates ONLY when ``imagery_policy: generative-eligible``
is the effective policy (per Phase 1B / PR #170): every reference to a
generated asset under ``assets/generated/<slot>.png`` carries
attribution language in alt-text, FORBIDDEN documentary-truth phrases
MUST NOT appear, and load-bearing slides require on-slide visible
attribution.

This file is a deterministic substring grep over the drafter / reviser
command specs and SKILL.md. It does NOT validate prose quality or
agent-runtime behavior — those belong in consumer-side integration
tests and in Phase 3G's runtime audit enforcement (issue #188, parallel
to Phase 3F).

The assertions encode the issue #187 acceptance criteria:

- allowed-language list present in deck-draft.md (concept render,
  aspirational mockup, illustrative scene)
- forbidden-language list present in deck-draft.md (product screenshot,
  actual photo, customer deployment, actual user, from the field)
- rule scoped to ``generative-eligible`` policy (no behavior change for
  deterministic-only or consumer-provided threads)
- revise-side contract present (reviser MUST NOT strip attribution)
- PR #170 (imagery_policy) regression guard — the imagery_policy
  enumeration is still documented and the drafter still resolves it.

Per-skill test filename convention (#58): this file is named with a
``test_deck_`` prefix so it never collides with a parallel-skill test
of the same shape.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "deck"
DRAFT_MD = SKILL_ROOT / "commands" / "deck-draft.md"
REVISE_MD = SKILL_ROOT / "commands" / "deck-revise.md"
SKILL_MD = SKILL_ROOT / "SKILL.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# deck-draft.md — drafter-side contract (allowed + forbidden language lists)
# ---------------------------------------------------------------------------


def test_deck_draft_documents_fabrication_attribution_contract():
    body = _read(DRAFT_MD)
    assert "Fabrication-attribution contract" in body, (
        "deck-draft.md MUST document the 'Fabrication-attribution contract' "
        "section per Phase 3F / issue #187 AC"
    )


def test_deck_draft_documents_allowed_attribution_language():
    """Allowed attribution phrases per issue #187 AC."""
    body = _read(DRAFT_MD).lower()
    assert "concept render" in body, (
        "deck-draft.md MUST list 'concept render' as allowed attribution "
        "language (issue #187 AC; canonical default)"
    )
    assert "aspirational mockup" in body, (
        "deck-draft.md MUST list 'aspirational mockup' as allowed attribution "
        "language (issue #187 AC)"
    )
    assert "illustrative scene" in body, (
        "deck-draft.md MUST list 'illustrative scene' as allowed attribution "
        "language (issue #187 AC)"
    )


def test_deck_draft_documents_forbidden_attribution_language():
    """Forbidden documentary-truth phrases per issue #187 AC.

    These phrases imply documentary truth (camera-captured photo, named
    customer, deployed product) and MUST be explicitly forbidden so an
    attribution-respecting drafter doesn't accidentally reach for them.
    """
    body = _read(DRAFT_MD).lower()
    assert "product screenshot" in body, (
        "deck-draft.md MUST list 'product screenshot' as FORBIDDEN attribution "
        "language (issue #187 AC)"
    )
    assert "actual photo" in body, (
        "deck-draft.md MUST list 'actual photo' as FORBIDDEN attribution "
        "language (issue #187 AC)"
    )
    assert "customer deployment" in body, (
        "deck-draft.md MUST list 'customer deployment' as FORBIDDEN attribution "
        "language (issue #187 AC)"
    )
    assert "actual user" in body, (
        "deck-draft.md MUST list 'actual user' as FORBIDDEN attribution "
        "language (issue #187 AC)"
    )
    assert "from the field" in body, (
        "deck-draft.md MUST list 'from the field' as FORBIDDEN attribution "
        "language (issue #187 AC)"
    )


def test_deck_draft_scopes_attribution_rule_to_generative_eligible():
    """The attribution contract activates ONLY when
    ``imagery_policy: generative-eligible``. Deterministic-only and
    consumer-provided decks are byte-identical to today's behavior
    (backwards-compat preserved per issue #187 AC).

    The grep checks that the contract section is co-located with the
    ``generative-eligible`` policy text (the section is nested under
    that policy's heading) so a deck on a different policy doesn't pick
    up the rule by accident.
    """
    body = _read(DRAFT_MD)
    # Locate the section.
    section_start = body.find("Fabrication-attribution contract")
    assert section_start > -1, (
        "deck-draft.md MUST contain the 'Fabrication-attribution contract' "
        "section (issue #187 AC)"
    )
    # The section MUST appear AFTER the generative-eligible heading.
    gen_heading = body.find("`imagery_policy: generative-eligible`")
    assert gen_heading > -1, (
        "deck-draft.md MUST still document the generative-eligible policy "
        "(regression guard for PR #170 / Phase 1B)"
    )
    assert gen_heading < section_start, (
        "Fabrication-attribution contract section MUST be nested under the "
        "generative-eligible policy heading (scoped activation per "
        "issue #187 AC)"
    )
    # The section body MUST name the scoping condition explicitly.
    section_body = body[section_start:section_start + 4000]
    assert "generative-eligible" in section_body, (
        "Fabrication-attribution contract section MUST explicitly name "
        "'generative-eligible' as the activation condition (issue #187 AC)"
    )
    # Explicit backwards-compat surfacing.
    lowered_section = section_body.lower()
    assert (
        "deterministic-only" in lowered_section
        or "backwards compat" in lowered_section
        or "backwards-compat" in lowered_section
        or "unaffected" in lowered_section
    ), (
        "Fabrication-attribution contract section MUST surface the "
        "backwards-compat framing (deterministic-only / consumer-provided "
        "decks unaffected) per issue #187 AC"
    )


def test_deck_draft_documents_alt_text_discipline():
    body = _read(DRAFT_MD)
    lowered = body.lower()
    assert "alt-text" in lowered or "alt text" in lowered, (
        "deck-draft.md MUST document the alt-text discipline (every "
        "<img> reference to assets/generated/<slot>.png MUST carry "
        "attribution language in alt-text) per issue #187 AC"
    )
    # The discipline targets the assets/generated namespace specifically.
    assert "assets/generated/" in body, (
        "deck-draft.md MUST scope the alt-text discipline to the "
        "assets/generated/ namespace (issue #187 AC)"
    )


def test_deck_draft_documents_on_slide_attribution_rule():
    """On-slide attribution belongs visibly on the slide when imagery
    is load-bearing for a claim — not just in alt-text. Per issue #187 AC.
    """
    body = _read(DRAFT_MD)
    lowered = body.lower()
    assert "on-slide" in lowered or "on slide" in lowered, (
        "deck-draft.md MUST document the on-slide attribution rule "
        "(visible caption when imagery is load-bearing for a claim) "
        "per issue #187 AC"
    )
    assert "load-bearing" in lowered or "load bearing" in lowered, (
        "deck-draft.md MUST document the load-bearing threshold for "
        "on-slide visible attribution per issue #187 AC"
    )


# ---------------------------------------------------------------------------
# deck-revise.md — reviser-side mirror of the contract
# ---------------------------------------------------------------------------


def test_deck_revise_documents_attribution_preservation():
    """The reviser MUST NOT strip attribution language for brevity.

    Per issue #187 AC: same attribution rule in revise mode (reviser
    MUST NOT strip attributions for brevity).
    """
    body = _read(REVISE_MD)
    lowered = body.lower()
    # The reviser-side contract MUST name attribution and MUST forbid
    # stripping it.
    assert "attribution" in lowered, (
        "deck-revise.md MUST document the attribution-preservation "
        "contract per issue #187 AC"
    )
    # The "MUST NOT strip" framing is the canonical phrasing.
    assert "strip" in lowered or "remove" in lowered, (
        "deck-revise.md MUST document that the reviser cannot strip / "
        "remove attribution (issue #187 AC: reviser MUST NOT strip "
        "attributions for brevity)"
    )


def test_deck_revise_lists_allowed_attribution_tokens():
    """The reviser-side contract MUST name the same allowed tokens as
    the drafter so a reviser reading deck-revise.md alone can apply the
    contract without cross-reading deck-draft.md.
    """
    body = _read(REVISE_MD).lower()
    assert "concept render" in body, (
        "deck-revise.md MUST name 'concept render' (allowed attribution "
        "language carried from deck-draft.md) so the reviser preserves it"
    )
    assert "aspirational mockup" in body, (
        "deck-revise.md MUST name 'aspirational mockup' so the reviser "
        "preserves it"
    )
    assert "illustrative scene" in body, (
        "deck-revise.md MUST name 'illustrative scene' so the reviser "
        "preserves it"
    )


def test_deck_revise_lists_forbidden_attribution_tokens():
    """The reviser MUST NOT introduce FORBIDDEN attribution language
    even when a critic finding's suggested edit uses such a word.
    """
    body = _read(REVISE_MD).lower()
    assert "product screenshot" in body, (
        "deck-revise.md MUST name 'product screenshot' as FORBIDDEN so "
        "the reviser does not introduce it"
    )
    assert "actual photo" in body, (
        "deck-revise.md MUST name 'actual photo' as FORBIDDEN"
    )
    assert "customer deployment" in body, (
        "deck-revise.md MUST name 'customer deployment' as FORBIDDEN"
    )


def test_deck_revise_cross_references_drafter_contract():
    """The reviser-side contract MUST point at the drafter-side contract
    so a reviser landing on deck-revise.md can find the canonical
    allowed/forbidden language lists.
    """
    body = _read(REVISE_MD)
    assert "Fabrication-attribution contract" in body, (
        "deck-revise.md MUST reference the 'Fabrication-attribution "
        "contract' (drafter-side source of truth) per issue #187 AC"
    )
    assert "deck-draft.md" in body, (
        "deck-revise.md MUST cross-reference deck-draft.md for the "
        "canonical allowed/forbidden language lists"
    )


# ---------------------------------------------------------------------------
# SKILL.md — Asset generation section cross-link
# ---------------------------------------------------------------------------


def test_skill_md_documents_fabrication_attribution_subsection():
    """Per issue #187 AC: SKILL.md adds a short subsection in
    §"Asset generation" referencing the attribution discipline.
    """
    body = _read(SKILL_MD)
    asset_section_start = body.find("## Asset generation")
    asset_section_end = body.find("## Output format")
    assert asset_section_start > -1 and asset_section_end > -1, (
        "SKILL.md MUST have the Asset generation section bounded by the "
        "Output format heading"
    )
    asset_block = body[asset_section_start:asset_section_end]
    assert "Fabrication-attribution contract" in asset_block, (
        "SKILL.md § 'Asset generation' MUST add a subsection on the "
        "fabrication-attribution contract per issue #187 AC"
    )


def test_skill_md_cross_links_phase_3g_audit_enforcement():
    """Per issue #187 AC: cross-link to Phase 3G's audit findings
    (forward reference — the runtime enforcement lands in #188 parallel
    to #187).
    """
    body = _read(SKILL_MD)
    asset_section_start = body.find("## Asset generation")
    asset_section_end = body.find("## Output format")
    asset_block = body[asset_section_start:asset_section_end]
    # The forward reference identifies Phase 3G and the parallel issue.
    assert "Phase 3G" in asset_block or "#188" in asset_block, (
        "SKILL.md § 'Asset generation' MUST forward-reference Phase 3G "
        "/ issue #188 (runtime audit enforcement) per issue #187 AC"
    )
    # Cross-link to deck-audit (the audit critic).
    assert "deck-audit" in asset_block, (
        "SKILL.md § 'Asset generation' MUST reference deck-audit (the "
        "runtime enforcement target) per issue #187 AC"
    )


def test_skill_md_cross_links_drafter_contract_doc():
    """SKILL.md's attribution subsection MUST point at the drafter-side
    canonical contract so a reader doesn't have to crawl commands/ to
    find the allowed/forbidden lists.
    """
    body = _read(SKILL_MD)
    asset_section_start = body.find("## Asset generation")
    asset_section_end = body.find("## Output format")
    asset_block = body[asset_section_start:asset_section_end]
    assert "deck-draft.md" in asset_block, (
        "SKILL.md § 'Asset generation' MUST cross-reference "
        "commands/deck-draft.md so the reader can find the canonical "
        "allowed/forbidden language lists"
    )


# ---------------------------------------------------------------------------
# PR #170 regression guard — imagery_policy contract still intact
# ---------------------------------------------------------------------------


def test_imagery_policy_enum_still_documented():
    """Regression guard for PR #170 (imagery_policy BRIEF.md frontmatter
    field). The Phase 3F attribution contract is layered ON TOP OF the
    Phase 1B imagery_policy enum; if the enum drifted out of deck-draft.md
    the attribution contract loses its activation condition.
    """
    body = _read(DRAFT_MD)
    # All three closed-enum values MUST still appear.
    assert "generative-eligible" in body, (
        "deck-draft.md MUST still document 'generative-eligible' "
        "(PR #170 regression guard)"
    )
    assert "consumer-provided" in body, (
        "deck-draft.md MUST still document 'consumer-provided' "
        "(PR #170 regression guard)"
    )
    assert "deterministic-only" in body, (
        "deck-draft.md MUST still document 'deterministic-only' "
        "(PR #170 regression guard)"
    )
    # The resolution-rule section MUST still exist (drafter reads
    # imagery_policy from BRIEF.md frontmatter and gates behavior).
    assert "Respecting `imagery_policy`" in body or "Respecting imagery_policy" in body, (
        "deck-draft.md MUST still have the 'Respecting imagery_policy' "
        "section (PR #170 regression guard)"
    )


def test_imagery_policy_cheat_sheet_still_present():
    """The allowed-vs-forbidden cheat sheet table from PR #170 MUST
    survive the Phase 3F edits.
    """
    body = _read(DRAFT_MD)
    assert "allowed-vs-forbidden cheat sheet" in body, (
        "deck-draft.md MUST still have the allowed-vs-forbidden cheat "
        "sheet table (PR #170 regression guard)"
    )
    # The table header line.
    assert "| Policy |" in body, (
        "deck-draft.md cheat-sheet table MUST still have the | Policy | "
        "header column (PR #170 regression guard)"
    )


def test_skill_md_imagery_policy_table_still_present():
    """SKILL.md's BRIEF.md frontmatter table from PR #170 MUST survive
    the Phase 3F edits.
    """
    body = _read(SKILL_MD)
    assert "| `imagery_policy` |" in body, (
        "SKILL.md MUST still have the imagery_policy row in its BRIEF.md "
        "frontmatter table (PR #170 regression guard)"
    )
