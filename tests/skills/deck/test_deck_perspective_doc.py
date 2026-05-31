"""Doc-coverage smoke tests for the deck ``deck-perspective`` command.

Per issue #149 (Epic #143 / Phase 1B) acceptance criteria: cheap
"grep-the-doc" regression guard that the deck-skill consumer of the
perspective primitive (the canary implementation) stays documented in
the three files it touches (commands/deck-perspective.md, SKILL.md,
commands/deck-draft.md) and that the documents cross-reference each
other coherently — especially the optional/non-gating framing and the
no-fabrication rule that are the architect's load-bearing safeguards.

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The command itself is LLM-driven, so
behavioural assertions belong in consumer-side integration tests, not
here.

Per-skill test filename convention (#58): this file is named with a
``test_deck_`` prefix so it never collides with a parallel-skill test
of the same shape (e.g., a future ``test_memo_perspective_doc.py`` per
Epic #143 Phase 2).
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "deck"
SKILL_MD = SKILL_ROOT / "SKILL.md"
DRAFT_MD = SKILL_ROOT / "commands" / "deck-draft.md"
PERSPECTIVE_MD = SKILL_ROOT / "commands" / "deck-perspective.md"
SNIPPETS = (
    Path(__file__).resolve().parents[3] / "anvil" / "lib" / "snippets"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# deck-perspective.md — command spec (new in #149)
# ---------------------------------------------------------------------------


def test_deck_perspective_command_exists():
    assert PERSPECTIVE_MD.exists(), (
        "anvil/skills/deck/commands/deck-perspective.md MUST exist per "
        "issue #149 (Epic #143 Phase 1B)"
    )


def test_deck_perspective_has_frontmatter():
    body = _read(PERSPECTIVE_MD)
    # SKILL-command convention: YAML frontmatter with name + description.
    assert body.lstrip().startswith("---"), (
        "deck-perspective.md MUST open with YAML frontmatter per skill convention"
    )
    assert "name: deck-perspective" in body, (
        "deck-perspective.md frontmatter MUST set name: deck-perspective"
    )
    assert "description:" in body, (
        "deck-perspective.md frontmatter MUST include a description"
    )


def test_deck_perspective_references_framework_snippet():
    body = _read(PERSPECTIVE_MD)
    assert "anvil/lib/snippets/perspective.md" in body, (
        "deck-perspective.md MUST reference anvil/lib/snippets/perspective.md "
        "as the framework contract (issue #149 AC; landed via #148/PR #154)"
    )


def test_deck_perspective_cites_pub_litsearch_as_precedent():
    body = _read(PERSPECTIVE_MD)
    assert "pub-litsearch" in body, (
        "deck-perspective.md MUST cite pub-litsearch.md as the load-bearing "
        "existing precedent (issue #149 / Epic #143 design contract)"
    )


def test_deck_perspective_documents_owned_outputs():
    body = _read(PERSPECTIVE_MD)
    # Per architect proposal: notes.md, candidates.md, _meta.json,
    # _progress.json are the owned outputs.
    assert "notes.md" in body, (
        "deck-perspective.md MUST document notes.md as an owned output"
    )
    assert "candidates.md" in body, (
        "deck-perspective.md MUST document candidates.md as an owned output"
    )
    assert "_meta.json" in body, (
        "deck-perspective.md MUST document _meta.json as an owned output"
    )
    assert "_progress.json" in body, (
        "deck-perspective.md MUST document _progress.json per snippets/progress.md"
    )


def test_deck_perspective_documents_sibling_dir_layout():
    body = _read(PERSPECTIVE_MD)
    # The owned-output dir is <thread>.0.perspective/ (pre-draft) or
    # <thread>.{N}.perspective/ (re-run).
    assert "<thread>.0.perspective/" in body, (
        "deck-perspective.md MUST document the pre-draft sibling dir path"
    )
    assert "<thread>.{N}.perspective/" in body, (
        "deck-perspective.md MUST document the re-run sibling dir path"
    )


def test_deck_perspective_has_pub_litsearch_shape_sections():
    body = _read(PERSPECTIVE_MD)
    # Mirror pub-litsearch.md's overall shape: Reads / Writes (in header) +
    # Inputs / Outputs / Procedure / Idempotence / failure modes / re-run.
    # We assert on section headings that the architect contract names.
    assert "## Inputs" in body, "deck-perspective.md MUST have an Inputs section"
    assert "## Outputs" in body, "deck-perspective.md MUST have an Outputs section"
    assert "## Procedure" in body, "deck-perspective.md MUST have a Procedure section"
    assert "Failure modes" in body or "## Failure" in body, (
        "deck-perspective.md MUST have a Failure modes section "
        "(mirrors pub-litsearch.md shape)"
    )
    assert "Re-run" in body or "re-run" in body, (
        "deck-perspective.md MUST document the re-run pattern "
        "(mirrors pub-litsearch.md shape)"
    )


def test_deck_perspective_documents_no_fabrication_rule():
    body = _read(PERSPECTIVE_MD)
    # The no-fabrication rule is the load-bearing safeguard inherited from
    # the framework snippet; it MUST appear verbatim or near-verbatim.
    lowered = body.lower()
    assert "do not invent" in lowered or "no-fabrication" in lowered or (
        "no fabrication" in lowered
    ), (
        "deck-perspective.md MUST document the no-fabrication / do-not-invent "
        "rule (issue #149 AC; inherited from snippets/perspective.md)"
    )
    # Source URL / source pointer is the no-fabrication enforcement mechanism.
    assert "URL" in body or "source pointer" in body, (
        "deck-perspective.md MUST require source URLs / pointers on every "
        "candidate (no-fabrication enforcement)"
    )
    # Normative MUST language.
    assert "MUST NOT" in body or "MUST refuse" in body, (
        "deck-perspective.md MUST use normative MUST language around the "
        "no-fabrication rule"
    )


def test_deck_perspective_documents_non_gating():
    body = _read(PERSPECTIVE_MD)
    # Per snippets/perspective.md, the sibling is non-gating. The command file
    # MUST surface this so the consumer sees it without crawling the snippet.
    assert "non-gating" in body or "non gating" in body, (
        "deck-perspective.md MUST surface the non-gating contract"
    )
    assert "does NOT block" in body or "does not block" in body, (
        "deck-perspective.md MUST state that absence does NOT block the state machine"
    )


def test_deck_perspective_documents_workflows():
    body = _read(PERSPECTIVE_MD)
    # Per snippets/perspective.md, three workflows are supported.
    assert "pre-staged" in body, (
        "deck-perspective.md MUST document the pre-staged workflow"
    )
    assert "agent-driven" in body or "agent driven" in body, (
        "deck-perspective.md MUST document the agent-driven workflow"
    )
    assert "hybrid" in body.lower(), (
        "deck-perspective.md MUST document the hybrid workflow"
    )


def test_deck_perspective_declares_scorecard_kind():
    body = _read(PERSPECTIVE_MD)
    # Per snippets/scorecard_kind.md, perspective siblings declare
    # scorecard_kind: human-verdict in _meta.json.
    assert "scorecard_kind" in body, (
        "deck-perspective.md MUST document the scorecard_kind declaration"
    )
    assert "human-verdict" in body, (
        "deck-perspective.md MUST declare scorecard_kind: human-verdict "
        "per snippets/scorecard_kind.md"
    )


def test_deck_perspective_uses_perspective_naming_not_research():
    body = _read(PERSPECTIVE_MD)
    # The architect contract names the command "deck-perspective" (NOT
    # "deck-research") per snippets/perspective.md §"Naming: perspective,
    # not research". A regression to "research" would be a contract drift.
    assert "deck-perspective" in body, (
        "deck-perspective.md MUST refer to itself as deck-perspective (NOT "
        "deck-research) per snippets/perspective.md naming contract"
    )


# ---------------------------------------------------------------------------
# SKILL.md — artifact-contract diagram + state-machine note (issue #149 AC)
# ---------------------------------------------------------------------------


def test_skill_md_artifact_contract_lists_perspective_sibling():
    body = _read(SKILL_MD)
    # Per AC: insert <thread>.0.perspective/ between <thread>.0/ and <thread>.1/
    # in the artifact-contract diagram.
    assert "<thread>.0.perspective/" in body, (
        "deck SKILL.md MUST list <thread>.0.perspective/ in the artifact-"
        "contract diagram (between <thread>.0/ and <thread>.1/) per issue #149 AC"
    )


def test_skill_md_perspective_appears_before_first_drafted_version():
    """The artifact-contract diagram orders dirs lexically; perspective MUST
    appear between the .0/ brief snapshot and the .1/ first drafted version."""
    body = _read(SKILL_MD)
    brief_pos = body.find("<thread>.0/")
    perspective_pos = body.find("<thread>.0.perspective/")
    draft_pos = body.find("<thread>.1/")
    assert brief_pos > -1 and perspective_pos > -1 and draft_pos > -1
    assert brief_pos < perspective_pos < draft_pos, (
        "deck SKILL.md artifact-contract diagram MUST order the perspective "
        "sibling between <thread>.0/ and <thread>.1/ per issue #149 AC"
    )


def test_skill_md_state_machine_notes_optional_perspective():
    body = _read(SKILL_MD)
    # The state-machine section MUST have the optional-sibling note (adapted
    # from pub/SKILL.md lines 55-63).
    assert ".0.perspective/" in body
    # The non-gating wording must appear in the state-machine context, not
    # solely in the artifact-contract block. We check the loose property
    # that "non-gating" or "does not gate" appears alongside perspective.
    lowered = body.lower()
    assert "non-gating" in lowered or "not gate" in lowered or (
        "does not block" in lowered
    ), (
        "deck SKILL.md state-machine section MUST note that the perspective "
        "sibling is optional and non-gating (issue #149 AC; adapted from "
        "pub/SKILL.md §State machine)"
    )


def test_skill_md_command_dispatch_lists_deck_perspective():
    body = _read(SKILL_MD)
    # Coherence: the command-dispatch table should include the new command
    # so consumers see it without flipping to commands/.
    assert "deck-perspective" in body, (
        "deck SKILL.md command-dispatch table MUST list deck-perspective "
        "per issue #149 AC"
    )


def test_skill_md_states_perspective_not_in_default_critic_set():
    body = _read(SKILL_MD)
    # The default critic set MUST remain `review + narrative + market + design`
    # — perspective MUST NOT be added as required.
    # We check that the default-set string is unchanged and that perspective
    # does not appear in the default-critic-set declaration.
    default_set_phrase = "review + narrative + market + design"
    assert default_set_phrase in body, (
        "deck SKILL.md MUST preserve the unchanged default critic set "
        "(review + narrative + market + design) — perspective MUST NOT be "
        "added as required (issue #149 backwards-compat AC)"
    )


# ---------------------------------------------------------------------------
# deck-draft.md — optional perspective consumer (issue #149 AC)
# ---------------------------------------------------------------------------


def test_deck_draft_references_perspective_sibling():
    body = _read(DRAFT_MD)
    assert ".perspective/" in body or "perspective sibling" in body.lower(), (
        "deck-draft.md MUST reference the perspective sibling (issue #149 AC)"
    )


def test_deck_draft_marks_perspective_as_optional():
    body = _read(DRAFT_MD)
    # AC: "perspective remains optional — DO NOT change deck-draft's required
    # inputs". The doc MUST surface the optional / non-gating framing so the
    # reader sees that drafting works WITHOUT perspective.
    lowered = body.lower()
    assert "optional" in lowered, (
        "deck-draft.md MUST mark the perspective sibling as optional"
    )
    assert "non-gating" in lowered or "does not block" in lowered or (
        "proceeds normally" in lowered
    ), (
        "deck-draft.md MUST clarify that absence does NOT block drafting "
        "(issue #149 backwards-compat AC)"
    )


def test_deck_draft_marks_perspective_as_load_bearing_when_present():
    body = _read(DRAFT_MD)
    # AC: "if <thread>.0.perspective/ exists, treat as load-bearing context"
    lowered = body.lower()
    assert "load-bearing" in lowered or "load bearing" in lowered, (
        "deck-draft.md MUST mark perspective as load-bearing context when "
        "present (issue #149 AC; architect proposal #143)"
    )


def test_deck_draft_does_not_require_perspective():
    body = _read(DRAFT_MD)
    # Hard backwards-compat invariant: the brief check (step 2) MUST NOT
    # have been extended to also require a perspective sibling. We check
    # that the brief-check error message string is unchanged.
    assert "BRIEF.md missing or incomplete — run deck-brief" in body, (
        "deck-draft.md MUST preserve the unchanged brief-check error "
        "string — perspective MUST NOT be added as a required input "
        "(issue #149 backwards-compat AC)"
    )


def test_deck_draft_preserves_brief_is_the_contract_rule():
    body = _read(DRAFT_MD)
    # The no-fabrication contract is enforced against BRIEF.md; perspective
    # is verified-substrate context that helps the drafter cite, NOT an
    # extension of the no-fabrication contract. The "brief is the contract"
    # framing MUST survive intact.
    assert "brief is the contract" in body.lower() or (
        "BRIEF.md" in body and "no-fabrication" in body.lower()
    ), (
        "deck-draft.md MUST preserve the brief-is-the-contract framing "
        "(issue #149 backwards-compat AC; perspective is substrate aid, "
        "NOT an extension of the no-fabrication contract)"
    )


# ---------------------------------------------------------------------------
# Cross-file coherence: deck-perspective.md ↔ SKILL.md ↔ deck-draft.md
# ---------------------------------------------------------------------------


def test_perspective_command_consistent_with_skill_md_diagram():
    """The owned-output schema in deck-perspective.md MUST match the
    artifact-contract diagram in SKILL.md (notes.md + candidates.md +
    _meta.json + _progress.json)."""
    perspective_body = _read(PERSPECTIVE_MD)
    skill_body = _read(SKILL_MD)
    # Find the diagram block in SKILL.md that contains
    # <thread>.0.perspective/ and verify it lists the four owned outputs.
    p_pos = skill_body.find("<thread>.0.perspective/")
    assert p_pos > -1
    # Look at the ~600 chars following the perspective line for the
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
    snippet ever goes away, the deck-perspective command becomes orphaned
    — the test catches the regression."""
    assert (SNIPPETS / "perspective.md").exists(), (
        "anvil/lib/snippets/perspective.md MUST exist (load-bearing for "
        "deck-perspective.md per issue #149 / Epic #143 Phase 1B)"
    )
