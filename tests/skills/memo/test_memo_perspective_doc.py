"""Doc-coverage smoke tests for the memo ``memo-perspective`` command.

Per issue #179 (Epic #143 / Phase 2A) acceptance criteria: cheap
"grep-the-doc" regression guard that the memo-skill consumer of the
perspective primitive (the second-skill rollout following the deck
canary at #149) stays documented in the four files it touches
(commands/memo-perspective.md, SKILL.md, commands/memo-draft.md,
rubric.md) and that the documents cross-reference each other coherently
— especially the optional/non-gating framing, the no-fabrication rule,
and the rubric dim 3 extension that are the load-bearing safeguards.

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The command itself is LLM-driven, so
behavioural assertions belong in consumer-side integration tests, not
here.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with the parallel
``test_deck_perspective_doc.py`` (per Phase 1B / #149) or the
forthcoming ``test_proposal_perspective_doc.py`` (per Phase 2B / #180).
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
DRAFT_MD = SKILL_ROOT / "commands" / "memo-draft.md"
PERSPECTIVE_MD = SKILL_ROOT / "commands" / "memo-perspective.md"
RUBRIC_MD = SKILL_ROOT / "rubric.md"
SNIPPETS = (
    Path(__file__).resolve().parents[3] / "anvil" / "lib" / "snippets"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# memo-perspective.md — command spec (new in #179)
# ---------------------------------------------------------------------------


def test_memo_perspective_command_exists():
    assert PERSPECTIVE_MD.exists(), (
        "anvil/skills/memo/commands/memo-perspective.md MUST exist per "
        "issue #179 (Epic #143 Phase 2A)"
    )


def test_memo_perspective_has_frontmatter():
    body = _read(PERSPECTIVE_MD)
    # SKILL-command convention: YAML frontmatter with name + description.
    assert body.lstrip().startswith("---"), (
        "memo-perspective.md MUST open with YAML frontmatter per skill convention"
    )
    assert "name: memo-perspective" in body, (
        "memo-perspective.md frontmatter MUST set name: memo-perspective"
    )
    assert "description:" in body, (
        "memo-perspective.md frontmatter MUST include a description"
    )


def test_memo_perspective_references_framework_snippet():
    body = _read(PERSPECTIVE_MD)
    assert "anvil/lib/snippets/perspective.md" in body, (
        "memo-perspective.md MUST reference anvil/lib/snippets/perspective.md "
        "as the framework contract (issue #179 AC; landed via #148/PR #154)"
    )


def test_memo_perspective_cites_deck_perspective_as_precedent():
    body = _read(PERSPECTIVE_MD)
    # Phase 2A's whole point: the deck-perspective canary is the load-bearing
    # precedent. memo-perspective.md MUST cite it so the second-consumer
    # rollout pattern is visible in the docs.
    assert "deck-perspective" in body, (
        "memo-perspective.md MUST cite deck-perspective.md as the precedent "
        "this command mirrors (issue #179 / Epic #143 Phase 2A design contract)"
    )


def test_memo_perspective_documents_owned_outputs():
    body = _read(PERSPECTIVE_MD)
    # Per architect contract from #148: notes.md, candidates.md, _meta.json,
    # _progress.json are the owned outputs.
    assert "notes.md" in body, (
        "memo-perspective.md MUST document notes.md as an owned output"
    )
    assert "candidates.md" in body, (
        "memo-perspective.md MUST document candidates.md as an owned output"
    )
    assert "_meta.json" in body, (
        "memo-perspective.md MUST document _meta.json as an owned output"
    )
    assert "_progress.json" in body, (
        "memo-perspective.md MUST document _progress.json per snippets/progress.md"
    )


def test_memo_perspective_documents_sibling_dir_layout():
    body = _read(PERSPECTIVE_MD)
    # The owned-output dir is <thread>.0.perspective/ (pre-draft) or
    # <thread>.{N}.perspective/ (re-run).
    assert "<thread>.0.perspective/" in body, (
        "memo-perspective.md MUST document the pre-draft sibling dir path"
    )
    assert "<thread>.{N}.perspective/" in body, (
        "memo-perspective.md MUST document the re-run sibling dir path"
    )


def test_memo_perspective_has_standard_command_sections():
    body = _read(PERSPECTIVE_MD)
    # Mirror deck-perspective.md / pub-litsearch.md shape:
    # Inputs / Outputs / Procedure / Failure modes / Re-run pattern.
    assert "## Inputs" in body, "memo-perspective.md MUST have an Inputs section"
    assert "## Outputs" in body, "memo-perspective.md MUST have an Outputs section"
    assert "## Procedure" in body, "memo-perspective.md MUST have a Procedure section"
    assert "Failure modes" in body or "## Failure" in body, (
        "memo-perspective.md MUST have a Failure modes section "
        "(mirrors deck-perspective.md shape)"
    )
    assert "Re-run" in body or "re-run" in body, (
        "memo-perspective.md MUST document the re-run pattern "
        "(mirrors deck-perspective.md shape)"
    )


def test_memo_perspective_documents_no_fabrication_rule():
    body = _read(PERSPECTIVE_MD)
    # The no-fabrication rule is the load-bearing safeguard inherited from
    # the framework snippet; it MUST appear verbatim or near-verbatim.
    lowered = body.lower()
    assert "do not invent" in lowered or "no-fabrication" in lowered or (
        "no fabrication" in lowered
    ), (
        "memo-perspective.md MUST document the no-fabrication / do-not-invent "
        "rule (issue #179 AC; inherited from snippets/perspective.md)"
    )
    # Source URL / source pointer is the no-fabrication enforcement mechanism.
    assert "URL" in body or "source pointer" in body, (
        "memo-perspective.md MUST require source URLs / pointers on every "
        "candidate (no-fabrication enforcement)"
    )
    # Normative MUST language.
    assert "MUST NOT" in body or "MUST refuse" in body, (
        "memo-perspective.md MUST use normative MUST language around the "
        "no-fabrication rule"
    )


def test_memo_perspective_documents_non_gating():
    body = _read(PERSPECTIVE_MD)
    # Per snippets/perspective.md, the sibling is non-gating. The command file
    # MUST surface this so the consumer sees it without crawling the snippet.
    assert "non-gating" in body or "non gating" in body, (
        "memo-perspective.md MUST surface the non-gating contract"
    )
    assert "does NOT block" in body or "does not block" in body, (
        "memo-perspective.md MUST state that absence does NOT block the state machine"
    )


def test_memo_perspective_documents_workflows():
    body = _read(PERSPECTIVE_MD)
    # Per snippets/perspective.md, three workflows are supported.
    assert "pre-staged" in body, (
        "memo-perspective.md MUST document the pre-staged workflow"
    )
    assert "agent-driven" in body or "agent driven" in body, (
        "memo-perspective.md MUST document the agent-driven workflow"
    )
    assert "hybrid" in body.lower(), (
        "memo-perspective.md MUST document the hybrid workflow"
    )


def test_memo_perspective_declares_scorecard_kind():
    body = _read(PERSPECTIVE_MD)
    # Per snippets/scorecard_kind.md, perspective siblings declare
    # scorecard_kind: human-verdict in _meta.json.
    assert "scorecard_kind" in body, (
        "memo-perspective.md MUST document the scorecard_kind declaration"
    )
    assert "human-verdict" in body, (
        "memo-perspective.md MUST declare scorecard_kind: human-verdict "
        "per snippets/scorecard_kind.md"
    )


def test_memo_perspective_uses_perspective_naming_not_research():
    body = _read(PERSPECTIVE_MD)
    # The architect contract names the command "memo-perspective" (NOT
    # "memo-research") per snippets/perspective.md §"Naming: perspective,
    # not research". A regression to "research" would be a contract drift.
    assert "memo-perspective" in body, (
        "memo-perspective.md MUST refer to itself as memo-perspective (NOT "
        "memo-research) per snippets/perspective.md naming contract"
    )


def test_memo_perspective_documents_stub_filling_side_effect():
    """Per issue #179 AC: the perspective role MAY write to
    <thread>/refs/<key>.md citation stubs as a side effect (integrates with
    the existing §"Citation stubs" convention from PR #140). The
    command file MUST document the rule explicitly so the integration is
    visible at the contract surface."""
    body = _read(PERSPECTIVE_MD)
    # The side-effect must be named and gated on substrate availability.
    assert "stub" in body.lower(), (
        "memo-perspective.md MUST document the citation-stub side-effect "
        "(issue #179 AC; integrates with PR #140 stubs convention)"
    )
    # The side-effect must NOT extend the no-fabrication contract.
    lowered = body.lower()
    assert "stubs_filled" in body or "fill" in lowered, (
        "memo-perspective.md MUST name how stub-filling is recorded "
        "(stubs_filled in _meta.json) or how filling works mechanically"
    )


# ---------------------------------------------------------------------------
# SKILL.md — artifact-contract diagram + state-machine note (issue #179 AC)
# ---------------------------------------------------------------------------


def test_skill_md_artifact_contract_lists_perspective_sibling():
    body = _read(SKILL_MD)
    # Per AC: insert <thread>.0.perspective/ between <thread>/ (brief snapshot)
    # and <thread>.1/ (first draft) in the artifact-contract diagram.
    assert "<thread>.0.perspective/" in body, (
        "memo SKILL.md MUST list <thread>.0.perspective/ in the artifact-"
        "contract diagram (between <thread>/ and <thread>.1/) per issue #179 AC"
    )


def test_skill_md_perspective_appears_before_first_drafted_version():
    """The artifact-contract diagram orders dirs lexically; perspective MUST
    appear before the .1/ first drafted version."""
    body = _read(SKILL_MD)
    perspective_pos = body.find("<thread>.0.perspective/")
    draft_pos = body.find("<thread>.1/")
    assert perspective_pos > -1 and draft_pos > -1
    assert perspective_pos < draft_pos, (
        "memo SKILL.md artifact-contract diagram MUST order the perspective "
        "sibling before <thread>.1/ per issue #179 AC"
    )


def test_skill_md_state_machine_notes_optional_perspective():
    body = _read(SKILL_MD)
    # The state-machine section MUST have the optional-sibling note (adapted
    # from deck/SKILL.md as updated by PR #157 / Phase 1B).
    assert ".0.perspective/" in body
    # The non-gating wording must appear in the state-machine context, not
    # solely in the artifact-contract block. We check the loose property
    # that "non-gating" or "does not gate" appears alongside perspective.
    lowered = body.lower()
    assert "non-gating" in lowered or "not gate" in lowered or (
        "does not block" in lowered
    ), (
        "memo SKILL.md state-machine section MUST note that the perspective "
        "sibling is optional and non-gating (issue #179 AC; adapted from "
        "deck/SKILL.md §State machine per PR #157)"
    )


def test_skill_md_command_dispatch_lists_memo_perspective():
    body = _read(SKILL_MD)
    # Coherence: the command-dispatch table should include the new command
    # so consumers see it without flipping to commands/.
    assert "memo-perspective" in body, (
        "memo SKILL.md command-dispatch table MUST list memo-perspective "
        "per issue #179 AC"
    )


def test_skill_md_preserves_memo_lifecycle_phases():
    body = _read(SKILL_MD)
    # The memo lifecycle is `draft → review → revise → figures` per SKILL.md
    # §"Skill-specific phases". Adding memo-perspective MUST NOT add a
    # required phase — the lifecycle line must survive intact.
    assert "draft → review → revise → figures" in body, (
        "memo SKILL.md MUST preserve the unchanged memo lifecycle "
        "(draft → review → revise → figures) — perspective MUST NOT be "
        "added as a required phase (issue #179 backwards-compat AC)"
    )


# ---------------------------------------------------------------------------
# memo-draft.md — optional perspective consumer (issue #179 AC)
# ---------------------------------------------------------------------------


def test_memo_draft_references_perspective_sibling():
    body = _read(DRAFT_MD)
    assert ".perspective/" in body or "perspective sibling" in body.lower(), (
        "memo-draft.md MUST reference the perspective sibling (issue #179 AC)"
    )


def test_memo_draft_marks_perspective_as_optional():
    body = _read(DRAFT_MD)
    # AC: "DO NOT change required inputs — perspective remains optional".
    # The doc MUST surface the optional / non-gating framing so the reader
    # sees that drafting works WITHOUT perspective.
    lowered = body.lower()
    assert "optional" in lowered, (
        "memo-draft.md MUST mark the perspective sibling as optional"
    )
    assert "non-gating" in lowered or "does not block" in lowered or (
        "proceeds normally" in lowered or "proceed normally" in lowered
    ), (
        "memo-draft.md MUST clarify that absence does NOT block drafting "
        "(issue #179 backwards-compat AC)"
    )


def test_memo_draft_marks_perspective_as_load_bearing_when_present():
    body = _read(DRAFT_MD)
    # AC: "if <thread>.0.perspective/ exists, treat as load-bearing context"
    lowered = body.lower()
    assert "load-bearing" in lowered or "load bearing" in lowered, (
        "memo-draft.md MUST mark perspective as load-bearing context when "
        "present (issue #179 AC; mirrors deck-draft.md update per #149)"
    )


def test_memo_draft_does_not_require_perspective():
    body = _read(DRAFT_MD)
    # Hard backwards-compat invariant: the Inputs section's BRIEF.md handling
    # MUST NOT have been extended to also require a perspective sibling. We
    # check that the BRIEF.md scaffold sentence is unchanged.
    assert "this command does not write a brief on the user's behalf" in body, (
        "memo-draft.md MUST preserve the unchanged BRIEF.md scaffold sentence "
        "— perspective MUST NOT be added as a required input "
        "(issue #179 backwards-compat AC)"
    )


# ---------------------------------------------------------------------------
# rubric.md — dim 3 acknowledges perspective sibling as substrate evidence
# ---------------------------------------------------------------------------


def test_rubric_citation_hooks_extends_to_perspective():
    body = _read(RUBRIC_MD)
    # Per AC: extend §"Citation hooks (dim 3)" prose to reference perspective
    # sibling existence as evidence the drafter had substrate available.
    assert "Citation hooks" in body, (
        "rubric.md MUST still have a 'Citation hooks' subsection (preserve #137)"
    )
    assert "perspective" in body.lower(), (
        "rubric.md MUST mention the perspective sibling in the dim 3 context "
        "(issue #179 AC; extends §'Citation hooks (dim 3)' per architect proposal "
        "Phase 2A's note)"
    )


def test_rubric_perspective_extension_documents_no_deduction_for_absence():
    """The perspective sibling is non-gating; its absence MUST NOT introduce
    a new deduction on dim 3 (would break backwards-compat for legacy threads
    that have no perspective sibling)."""
    body = _read(RUBRIC_MD)
    lowered = body.lower()
    # The rubric extension must make clear that perspective absence is the
    # legacy case with no new deduction.
    assert "non-gating" in lowered or "no deduction" in lowered or (
        "legacy" in lowered
    ), (
        "rubric.md citation-hooks extension MUST clarify that absence of a "
        "perspective sibling does NOT introduce a new deduction (issue #179 "
        "backwards-compat AC)"
    )


def test_rubric_preserves_existing_citation_hook_rules():
    body = _read(RUBRIC_MD)
    # The pre-#179 citation-hook calibration (one/two-point) MUST survive.
    lowered = body.lower()
    assert "single-point" in lowered or "one-point" in lowered or "1-point" in lowered, (
        "rubric.md MUST preserve the single-point deduction calibration "
        "(issue #179 must not regress the #137 contract)"
    )
    assert "two-point" in lowered or "2-point" in lowered, (
        "rubric.md MUST preserve the two-point deduction for pervasive absence "
        "(issue #179 must not regress the #137 contract)"
    )


# ---------------------------------------------------------------------------
# Cross-file coherence: memo-perspective.md ↔ SKILL.md ↔ memo-draft.md ↔ rubric.md
# ---------------------------------------------------------------------------


def test_perspective_command_consistent_with_skill_md_diagram():
    """The owned-output schema in memo-perspective.md MUST match the
    artifact-contract diagram in SKILL.md (notes.md + candidates.md +
    _meta.json + _progress.json)."""
    perspective_body = _read(PERSPECTIVE_MD)
    skill_body = _read(SKILL_MD)
    # Find the diagram block in SKILL.md that contains
    # <thread>.0.perspective/ and verify it lists the four owned outputs.
    p_pos = skill_body.find("<thread>.0.perspective/")
    assert p_pos > -1
    # Look at the ~800 chars following the perspective line for the
    # listed files.
    block = skill_body[p_pos : p_pos + 800]
    assert "notes.md" in block, (
        "SKILL.md artifact-contract diagram MUST list notes.md under the "
        "<thread>.0.perspective/ block"
    )
    assert "candidates.md" in block, (
        "SKILL.md artifact-contract diagram MUST list candidates.md under "
        "the <thread>.0.perspective/ block"
    )
    # The perspective command MUST agree on the same owned outputs.
    assert "notes.md" in perspective_body
    assert "candidates.md" in perspective_body


def test_framework_snippet_still_exists():
    """Guard: the framework contract this command depends on lives at
    anvil/lib/snippets/perspective.md (landed via #148 / PR #154). If the
    snippet ever goes away, the memo-perspective command becomes orphaned
    — the test catches the regression."""
    assert (SNIPPETS / "perspective.md").exists(), (
        "anvil/lib/snippets/perspective.md MUST exist (load-bearing for "
        "memo-perspective.md per issue #179 / Epic #143 Phase 2A)"
    )


def test_deck_perspective_precedent_still_exists():
    """Guard: the deck-perspective canary (PR #157, Phase 1B) is the
    precedent memo-perspective mirrors. If it disappears, the docs
    cross-reference dangles."""
    deck_perspective = (
        Path(__file__).resolve().parents[3]
        / "anvil"
        / "skills"
        / "deck"
        / "commands"
        / "deck-perspective.md"
    )
    assert deck_perspective.exists(), (
        "anvil/skills/deck/commands/deck-perspective.md MUST exist as the "
        "load-bearing precedent memo-perspective.md mirrors (issue #179 / "
        "Epic #143 Phase 2A)"
    )
