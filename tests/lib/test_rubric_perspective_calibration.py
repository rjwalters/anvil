"""Cross-skill doc-coverage smoke tests for the rubric-perspective
calibration co-dependency (Epic #143 / Phase 3, issue #189).

Per issue #189 acceptance criteria: cheap "grep-the-doc" regression
guard that the rubric calibration co-dependency stays documented in
the framework snippet (`anvil/lib/snippets/rubric.md`) and that the
per-skill rubric extensions (deck dims 3+4, memo dim 3, proposal dims
6+4, paper dim 4) cross-reference the framework primitive coherently —
especially the **opportunistic, not punitive** framing that is the
architect's load-bearing design contract.

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The rubric calibration is a doc-only
contract; behavioural assertions belong in consumer-side integration
tests, not here.

Filename convention (#58): this file is named with a
``test_rubric_perspective_calibration_`` prefix that does NOT collide
with sibling lib-level rubric tests (test_rubric.py, test_snippet_
contents.py) or per-skill perspective tests (the per-skill
test_<skill>_perspective_doc.py family).
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SNIPPETS = REPO_ROOT / "anvil" / "lib" / "snippets"
SKILLS = REPO_ROOT / "anvil" / "skills"

RUBRIC_SNIPPET = SNIPPETS / "rubric.md"
PERSPECTIVE_SNIPPET = SNIPPETS / "perspective.md"

DECK_RUBRIC = SKILLS / "deck" / "rubric.md"
MEMO_RUBRIC = SKILLS / "memo" / "rubric.md"
PROPOSAL_RUBRIC = SKILLS / "proposal" / "rubric.md"
PAPER_RUBRIC = SKILLS / "paper" / "rubric.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Framework snippet: anvil/lib/snippets/rubric.md (extended in #189)
# ---------------------------------------------------------------------------


def test_rubric_snippet_has_perspective_interaction_section():
    body = _read(RUBRIC_SNIPPET)
    assert "Rubric–perspective interaction" in body or (
        "Rubric-perspective interaction" in body
    ), (
        "rubric.md MUST contain a 'Rubric–perspective interaction' section "
        "per issue #189 AC (the framework-level rule that per-skill rubric "
        "extensions reference)"
    )


def test_rubric_snippet_documents_opportunistic_not_punitive():
    body = _read(RUBRIC_SNIPPET)
    # Per architect: this framing is the load-bearing design contract.
    # The phrase MUST appear verbatim (or near-verbatim) so the contract is
    # discoverable by grep from any per-skill rubric extension. Normalize
    # whitespace to handle prose line wrap.
    normalized = " ".join(body.lower().split())
    assert "opportunistic" in normalized, (
        "rubric.md MUST contain the 'opportunistic' framing for the "
        "perspective interaction (issue #189 AC; architect's core design call)"
    )
    assert "not punitive" in normalized, (
        "rubric.md MUST contain the 'not punitive' framing for the "
        "perspective interaction (issue #189 AC; architect's core design call)"
    )


def test_rubric_snippet_documents_no_new_deduction_for_absence():
    body = _read(RUBRIC_SNIPPET)
    # Normalize whitespace so "No new\n  deduction" matches the literal
    # "no new deduction" phrase. The framework snippet wraps prose at ~70
    # cols so multiword phrases may straddle a newline.
    normalized = " ".join(body.lower().split())
    # The backwards-compat AC: legacy threads without a perspective sibling
    # MUST NOT take a new deduction.
    assert "no new deduction" in normalized or "no deduction" in normalized, (
        "rubric.md MUST state that perspective absence introduces no new "
        "deduction (issue #189 AC; backwards-compat for legacy threads)"
    )


def test_rubric_snippet_documents_score_can_go_up_not_down():
    body = _read(RUBRIC_SNIPPET)
    lowered = body.lower()
    # The opportunistic rule: cited candidates raise the ceiling.
    assert "up" in lowered and "down" in lowered, (
        "rubric.md MUST contrast 'up' vs 'down' to make the asymmetric "
        "(opportunistic) rule visible"
    )
    # And the substrate-backed framing — perspective citations are evidence.
    assert "substrate-backed" in body or "substrate backed" in body, (
        "rubric.md MUST use the 'substrate-backed' framing for cited "
        "perspective claims (issue #189 AC)"
    )


def test_rubric_snippet_names_v0_adopter_skills():
    body = _read(RUBRIC_SNIPPET)
    # The framework snippet should name the v0 adopters so consumers see the
    # per-skill rollout at a glance.
    assert "deck" in body, (
        "rubric.md MUST name 'deck' as a v0 adopter of the perspective "
        "interaction (issue #189 AC)"
    )
    assert "memo" in body, (
        "rubric.md MUST name 'memo' as a v0 adopter of the perspective "
        "interaction (issue #189 AC)"
    )
    assert "proposal" in body, (
        "rubric.md MUST name 'proposal' as a v0 adopter of the perspective "
        "interaction (issue #189 AC)"
    )
    assert "paper" in body, (
        "rubric.md MUST name 'paper' as a v0 adopter of the perspective "
        "interaction (issue #189 AC)"
    )


def test_rubric_snippet_names_out_of_scope_skills():
    body = _read(RUBRIC_SNIPPET)
    # The framework snippet should name the skills that explicitly do NOT
    # adopt (slides, installation, ip-uspto, report) so consumers see the
    # canary-signal boundary.
    section_idx = body.find("Rubric–perspective interaction")
    if section_idx < 0:
        section_idx = body.find("Rubric-perspective interaction")
    assert section_idx >= 0
    # Look at the section content (until next H2).
    section_end = body.find("\n## ", section_idx + 5)
    section = body[section_idx : section_end if section_end > 0 else len(body)]
    # At least name slides + report (the two most likely future-adopters).
    assert "slides" in section, (
        "rubric.md MUST name 'slides' as an out-of-scope skill in the "
        "perspective interaction section (issue #189 AC)"
    )
    assert "report" in section, (
        "rubric.md MUST name 'report' as an out-of-scope skill (Phase 4 "
        "deferred per issue #189 / architect Phase 4 deferral)"
    )


def test_rubric_snippet_cross_references_perspective_snippet():
    body = _read(RUBRIC_SNIPPET)
    # The framework snippet must cross-reference perspective.md (the contract
    # this calibration rule depends on).
    assert "perspective.md" in body, (
        "rubric.md MUST cross-reference perspective.md (issue #189 AC; the "
        "calibration rule depends on the perspective sibling contract)"
    )


def test_rubric_snippet_see_also_lists_perspective():
    body = _read(RUBRIC_SNIPPET)
    # Verify the See also section names perspective.md so cross-discovery
    # works in both directions.
    see_also_idx = body.find("## See also")
    assert see_also_idx >= 0, (
        "rubric.md MUST have a See also section per snippet convention"
    )
    see_also = body[see_also_idx:]
    assert "perspective.md" in see_also, (
        "rubric.md See also section MUST list perspective.md (issue #189 AC)"
    )


def test_rubric_snippet_references_load_bearing_architect_quote():
    body = _read(RUBRIC_SNIPPET)
    lowered = body.lower()
    # The "drafters will skip it" framing is the load-bearing architect quote
    # from Epic #143. Per issue #189 body: "Adding `{skill}-perspective`
    # commands without touching the rubric will produce minimal behavior
    # change — drafters will skip it." This snippet MUST surface that
    # framing so the design rationale is discoverable in the framework.
    assert "skip" in lowered or "drafters" in lowered, (
        "rubric.md MUST surface the architect's 'drafters will skip it' "
        "framing OR equivalent rationale (issue #189 / Epic #143 design call)"
    )


# ---------------------------------------------------------------------------
# Per-skill rubric extensions: deck (dims 3, 4)
# ---------------------------------------------------------------------------


def test_deck_rubric_has_perspective_substrate_subsection():
    body = _read(DECK_RUBRIC)
    # Per issue #189 AC: deck rubric extends dim 3 + dim 4.
    assert "Perspective substrate" in body, (
        "deck/rubric.md MUST contain a 'Perspective substrate' subsection "
        "covering dims 3 + 4 (issue #189 AC)"
    )


def test_deck_rubric_perspective_section_names_dims_3_and_4():
    body = _read(DECK_RUBRIC)
    # The subsection MUST name dim 3 (Market size credibility) and dim 4
    # (Solution differentiation) explicitly.
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    assert "dim 3" in section.lower() or "dimension 3" in section.lower() or (
        "Market size credibility" in section
    ), (
        "deck/rubric.md 'Perspective substrate' subsection MUST name dim 3 "
        "(Market size credibility) per issue #189 AC"
    )
    assert "dim 4" in section.lower() or "dimension 4" in section.lower() or (
        "Solution differentiation" in section
    ), (
        "deck/rubric.md 'Perspective substrate' subsection MUST name dim 4 "
        "(Solution differentiation) per issue #189 AC"
    )


def test_deck_rubric_anchors_to_framework_snippet():
    body = _read(DECK_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    assert "anvil/lib/snippets/rubric.md" in section, (
        "deck/rubric.md 'Perspective substrate' subsection MUST anchor to "
        "anvil/lib/snippets/rubric.md (issue #189 AC; cross-skill primitive)"
    )


def test_deck_rubric_documents_opportunistic_not_punitive():
    body = _read(DECK_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    normalized = " ".join(section.lower().split())
    assert "opportunistic" in normalized, (
        "deck/rubric.md MUST surface the 'opportunistic' framing in the "
        "perspective substrate subsection (issue #189 backwards-compat AC)"
    )
    assert "not punitive" in normalized, (
        "deck/rubric.md MUST surface the 'not punitive' framing (issue #189 AC)"
    )


def test_deck_rubric_documents_no_new_deduction_for_absence():
    body = _read(DECK_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    normalized = " ".join(section.lower().split())
    assert "no new deduction" in normalized or "no deduction" in normalized or (
        "legacy" in normalized and "unchanged" in normalized
    ), (
        "deck/rubric.md perspective substrate subsection MUST state that "
        "absence introduces no new deduction (issue #189 backwards-compat AC)"
    )


# ---------------------------------------------------------------------------
# Per-skill rubric extensions: memo (dim 3)
# ---------------------------------------------------------------------------


def test_memo_rubric_has_perspective_substrate_subsection():
    body = _read(MEMO_RUBRIC)
    # Per issue #189 AC: memo rubric extends dim 3 with a named subsection
    # sibling to §"Citation hooks (dim 3)" (PR #140) and §"Refs back-check
    # (dim 3)" (PR #162).
    assert "Perspective substrate (dim 3)" in body or (
        "Perspective substrate" in body and "dim 3" in body.lower()
    ), (
        "memo/rubric.md MUST contain a 'Perspective substrate (dim 3)' "
        "subsection sibling to §'Citation hooks (dim 3)' and §'Refs back-"
        "check (dim 3)' (issue #189 AC)"
    )


def test_memo_rubric_perspective_subsection_anchors_to_framework():
    body = _read(MEMO_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    assert "anvil/lib/snippets/rubric.md" in section, (
        "memo/rubric.md 'Perspective substrate' subsection MUST anchor to "
        "anvil/lib/snippets/rubric.md (issue #189 AC)"
    )


def test_memo_rubric_perspective_subsection_sibling_to_citation_hooks():
    """The §'Perspective substrate (dim 3)' subsection MUST appear sibling
    to (not nested inside) §'Citation hooks (dim 3)' and §'Refs back-check
    (dim 3)' so the three sub-rules read coherently."""
    body = _read(MEMO_RUBRIC)
    cite_idx = body.find("## Citation hooks (dim 3)")
    persp_idx = body.find("## Perspective substrate")
    refs_idx = body.find("## Refs back-check (dim 3)")
    assert cite_idx > -1, "memo/rubric.md MUST preserve §'Citation hooks (dim 3)' as H2"
    assert persp_idx > -1, "memo/rubric.md MUST add §'Perspective substrate' as H2"
    assert refs_idx > -1, "memo/rubric.md MUST preserve §'Refs back-check (dim 3)' as H2"
    # All three are H2 siblings; the test is order-tolerant but enforces
    # the sibling-not-nested relationship by requiring each as an H2.


def test_memo_rubric_perspective_documents_opportunistic_not_punitive():
    body = _read(MEMO_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    normalized = " ".join(section.lower().split())
    assert "opportunistic" in normalized, (
        "memo/rubric.md MUST surface the 'opportunistic' framing in the "
        "perspective substrate subsection (issue #189 AC)"
    )
    assert "not punitive" in normalized, (
        "memo/rubric.md MUST surface the 'not punitive' framing (issue #189 AC)"
    )


def test_memo_rubric_preserves_citation_hooks_subsection():
    """Backwards-compat AC: the existing §'Citation hooks (dim 3)' (PR #140)
    MUST survive intact."""
    body = _read(MEMO_RUBRIC)
    assert "## Citation hooks (dim 3)" in body, (
        "memo/rubric.md MUST preserve §'Citation hooks (dim 3)' from PR #140 "
        "(issue #189 backwards-compat)"
    )


def test_memo_rubric_preserves_refs_back_check_subsection():
    """Backwards-compat AC: the existing §'Refs back-check (dim 3)' (PR #162)
    MUST survive intact."""
    body = _read(MEMO_RUBRIC)
    assert "## Refs back-check (dim 3)" in body, (
        "memo/rubric.md MUST preserve §'Refs back-check (dim 3)' from PR #162 "
        "(issue #189 backwards-compat)"
    )


# ---------------------------------------------------------------------------
# Per-skill rubric extensions: proposal (dim 6 + dim 4)
# ---------------------------------------------------------------------------


def test_proposal_rubric_has_perspective_substrate_subsection():
    body = _read(PROPOSAL_RUBRIC)
    # Per issue #189 AC: proposal rubric picks a dim mapping to "external
    # substrate matters" — architect's hint was dim 4 (Scope completeness)
    # or dim 6 (Cost credibility). Builder discretion documented in the
    # commit message.
    assert "Perspective substrate" in body, (
        "proposal/rubric.md MUST contain a 'Perspective substrate' "
        "subsection (issue #189 AC)"
    )


def test_proposal_rubric_perspective_subsection_anchors_to_framework():
    body = _read(PROPOSAL_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    assert "anvil/lib/snippets/rubric.md" in section, (
        "proposal/rubric.md 'Perspective substrate' subsection MUST anchor "
        "to anvil/lib/snippets/rubric.md (issue #189 AC)"
    )


def test_proposal_rubric_perspective_documents_opportunistic_not_punitive():
    body = _read(PROPOSAL_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    normalized = " ".join(section.lower().split())
    assert "opportunistic" in normalized, (
        "proposal/rubric.md MUST surface the 'opportunistic' framing "
        "(issue #189 AC)"
    )
    assert "not punitive" in normalized, (
        "proposal/rubric.md MUST surface the 'not punitive' framing "
        "(issue #189 AC)"
    )


def test_proposal_rubric_perspective_documents_no_new_deduction_for_absence():
    body = _read(PROPOSAL_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    normalized = " ".join(section.lower().split())
    assert "no new deduction" in normalized or "no deduction" in normalized or (
        "legacy" in normalized and "unchanged" in normalized
    ), (
        "proposal/rubric.md perspective substrate subsection MUST state that "
        "absence introduces no new deduction (issue #189 backwards-compat AC)"
    )


def test_proposal_rubric_preserves_refs_back_check_subsection():
    """Backwards-compat AC: the existing §'Refs back-check (dim 6 + dim 4)'
    MUST survive intact."""
    body = _read(PROPOSAL_RUBRIC)
    assert "## Refs back-check (dim 6 + dim 4)" in body, (
        "proposal/rubric.md MUST preserve §'Refs back-check (dim 6 + dim 4)' "
        "(issue #189 backwards-compat)"
    )


# ---------------------------------------------------------------------------
# Per-skill rubric extensions: paper (dim 4)
# ---------------------------------------------------------------------------


def test_pub_rubric_has_perspective_substrate_subsection():
    body = _read(PAPER_RUBRIC)
    # Per issue #189 AC: paper rubric dim 4 codifies the existing implicit
    # litsearch rule by adding §"Perspective substrate (dim 4)" subsection.
    assert "Perspective substrate" in body, (
        "paper/rubric.md MUST contain a 'Perspective substrate' subsection "
        "for dim 4 (Related-work positioning) per issue #189 AC"
    )


def test_pub_rubric_perspective_subsection_names_dim_4():
    body = _read(PAPER_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    assert "dim 4" in section.lower() or "Related-work positioning" in section, (
        "paper/rubric.md 'Perspective substrate' subsection MUST name dim 4 "
        "(Related-work positioning) per issue #189 AC"
    )


def test_pub_rubric_perspective_anchors_to_litsearch_precedent():
    """Pub-side perspective is historically named 'litsearch'. The dim 4
    subsection MUST name paper-litsearch.md as the load-bearing precedent
    being codified into the framework-anchored shape."""
    body = _read(PAPER_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    assert "litsearch" in section.lower(), (
        "paper/rubric.md 'Perspective substrate' subsection MUST name litsearch "
        "as the pre-existing implicit rule being codified (issue #189 AC)"
    )
    assert "paper-litsearch" in section, (
        "paper/rubric.md MUST cite paper-litsearch.md as the load-bearing "
        "precedent (issue #189 AC)"
    )


def test_pub_rubric_perspective_anchors_to_framework_snippet():
    body = _read(PAPER_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    assert "anvil/lib/snippets/rubric.md" in section, (
        "paper/rubric.md 'Perspective substrate' subsection MUST anchor to "
        "anvil/lib/snippets/rubric.md (issue #189 AC; cross-skill primitive)"
    )
    assert "anvil/lib/snippets/perspective.md" in section, (
        "paper/rubric.md 'Perspective substrate' subsection MUST cross-reference "
        "anvil/lib/snippets/perspective.md (issue #189 AC; cross-skill primitive)"
    )


def test_pub_rubric_perspective_documents_opportunistic_not_punitive():
    body = _read(PAPER_RUBRIC)
    idx = body.find("Perspective substrate")
    assert idx >= 0
    section_end = body.find("\n## ", idx + 5)
    section = body[idx : section_end if section_end > 0 else len(body)]
    normalized = " ".join(section.lower().split())
    assert "opportunistic" in normalized, (
        "paper/rubric.md MUST surface the 'opportunistic' framing (issue #189 AC)"
    )
    assert "not punitive" in normalized, (
        "paper/rubric.md MUST surface the 'not punitive' framing (issue #189 AC)"
    )


# ---------------------------------------------------------------------------
# Out-of-scope skills: slides, installation, ip-uspto, report
#
# Per issue #189 out-of-scope: these skills do NOT consume perspective and
# adding rubric language would be premature. The tests below act as
# forward-guards: if a future PR adds perspective-substrate language to one
# of these skills WITHOUT also shipping a `<skill>-perspective` command,
# the test fails and surfaces the contract drift.
# ---------------------------------------------------------------------------


def test_out_of_scope_skills_do_not_yet_add_perspective_substrate():
    """Forward-guard: skills that do NOT currently ship a
    <skill>-perspective command MUST NOT add a 'Perspective substrate'
    rubric subsection (would be premature per issue #189 out-of-scope).

    The guard inverts to a positive test once the skill ships its
    perspective command — at that point, replace the assert-not-present
    with assert-present per the per-skill AC.
    """
    for skill in ("slides", "installation", "ip-uspto", "report"):
        rubric_path = SKILLS / skill / "rubric.md"
        if not rubric_path.exists():
            continue
        body = _read(rubric_path)
        # Loose check: a 'Perspective substrate' H2 in an out-of-scope skill
        # would be the drift signal. We don't enforce no-perspective-mention
        # at all (some skills may reference the snippet in passing); the
        # specific assertion is on the named subsection shape.
        assert "## Perspective substrate" not in body, (
            f"{skill}/rubric.md MUST NOT contain a 'Perspective substrate' "
            f"H2 subsection until the skill ships a <skill>-perspective "
            f"command (issue #189 out-of-scope; adding rubric language without "
            f"the corresponding command would be premature)"
        )


# ---------------------------------------------------------------------------
# Cross-file coherence: the four adopting skills all reference the framework
# snippet → bidirectional discovery works.
# ---------------------------------------------------------------------------


def test_all_v0_adopters_cross_reference_framework_snippet():
    """All four v0 adopter skills (deck, memo, proposal, paper) MUST
    cross-reference anvil/lib/snippets/rubric.md in their Perspective
    substrate subsection."""
    for skill_path in (DECK_RUBRIC, MEMO_RUBRIC, PROPOSAL_RUBRIC, PAPER_RUBRIC):
        body = _read(skill_path)
        idx = body.find("Perspective substrate")
        assert idx >= 0, f"{skill_path} MUST have a Perspective substrate subsection"
        section_end = body.find("\n## ", idx + 5)
        section = body[idx : section_end if section_end > 0 else len(body)]
        assert "anvil/lib/snippets/rubric.md" in section, (
            f"{skill_path} 'Perspective substrate' subsection MUST cross-"
            f"reference anvil/lib/snippets/rubric.md so the framework primitive "
            f"is discoverable from every per-skill extension (issue #189 AC)"
        )


def test_framework_snippet_still_exists():
    """Guard: the framework contract this calibration co-dependency lives at
    anvil/lib/snippets/rubric.md. If the snippet ever goes away, the per-skill
    rubric extensions become orphaned — the test catches the regression."""
    assert RUBRIC_SNIPPET.exists(), (
        "anvil/lib/snippets/rubric.md MUST exist (load-bearing for the "
        "perspective interaction rule per issue #189 / Epic #143 Phase 3)"
    )


def test_perspective_snippet_still_exists():
    """Guard: the perspective sibling contract that the calibration rule
    depends on lives at anvil/lib/snippets/perspective.md (landed via #148 /
    PR #154). If it ever goes away, the calibration rule loses its referent."""
    assert PERSPECTIVE_SNIPPET.exists(), (
        "anvil/lib/snippets/perspective.md MUST exist (load-bearing for the "
        "rubric interaction rule per issue #189 / Epic #143 Phase 3)"
    )
