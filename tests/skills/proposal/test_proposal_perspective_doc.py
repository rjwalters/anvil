"""Doc-coverage smoke tests for the proposal ``proposal-perspective`` command.

Per issue #180 (Epic #143 / Phase 2B) acceptance criteria: cheap
"grep-the-doc" regression guard that the proposal-skill consumer of the
perspective primitive stays documented in the four files it touches
(commands/proposal-perspective.md, SKILL.md, commands/proposal-draft.md,
commands/proposal-audit.md) and that the documents cross-reference each
other coherently — especially the optional/non-gating framing, the
no-fabrication rule, and the audit-side wiring that are the architect's
load-bearing safeguards.

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The command itself is LLM-driven, so
behavioural assertions belong in consumer-side integration tests, not
here.

Per-skill test filename convention (#58): this file is named with a
``test_proposal_`` prefix so it never collides with a parallel-skill test
of the same shape (deck/test_deck_perspective_doc.py, the precedent;
memo/test_memo_perspective_doc.py from Phase 2A parallel work).
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "proposal"
SKILL_MD = SKILL_ROOT / "SKILL.md"
DRAFT_MD = SKILL_ROOT / "commands" / "proposal-draft.md"
AUDIT_MD = SKILL_ROOT / "commands" / "proposal-audit.md"
PERSPECTIVE_MD = SKILL_ROOT / "commands" / "proposal-perspective.md"
SNIPPETS = (
    Path(__file__).resolve().parents[3] / "anvil" / "lib" / "snippets"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# proposal-perspective.md — command spec (new in #180)
# ---------------------------------------------------------------------------


def test_proposal_perspective_command_exists():
    assert PERSPECTIVE_MD.exists(), (
        "anvil/skills/proposal/commands/proposal-perspective.md MUST exist per "
        "issue #180 (Epic #143 Phase 2B)"
    )


def test_proposal_perspective_has_frontmatter():
    body = _read(PERSPECTIVE_MD)
    assert body.lstrip().startswith("---"), (
        "proposal-perspective.md MUST open with YAML frontmatter per skill convention"
    )
    assert "name: proposal-perspective" in body, (
        "proposal-perspective.md frontmatter MUST set name: proposal-perspective"
    )
    assert "description:" in body, (
        "proposal-perspective.md frontmatter MUST include a description"
    )


def test_proposal_perspective_references_framework_snippet():
    body = _read(PERSPECTIVE_MD)
    assert "anvil/lib/snippets/perspective.md" in body, (
        "proposal-perspective.md MUST reference anvil/lib/snippets/perspective.md "
        "as the framework contract (issue #180 AC; landed via #148/PR #154)"
    )


def test_proposal_perspective_cites_deck_perspective_precedent():
    body = _read(PERSPECTIVE_MD)
    assert "deck-perspective" in body, (
        "proposal-perspective.md MUST cite deck-perspective.md as the "
        "Phase 1B canary-skill precedent per issue #180"
    )


def test_proposal_perspective_documents_owned_outputs():
    body = _read(PERSPECTIVE_MD)
    # Per architect proposal: notes.md, candidates.md, _meta.json,
    # _progress.json are the owned outputs.
    assert "notes.md" in body, (
        "proposal-perspective.md MUST document notes.md as an owned output"
    )
    assert "candidates.md" in body, (
        "proposal-perspective.md MUST document candidates.md as an owned output"
    )
    assert "_meta.json" in body, (
        "proposal-perspective.md MUST document _meta.json as an owned output"
    )
    assert "_progress.json" in body, (
        "proposal-perspective.md MUST document _progress.json per snippets/progress.md"
    )


def test_proposal_perspective_documents_sibling_dir_layout():
    body = _read(PERSPECTIVE_MD)
    # The owned-output dir is <thread>.0.perspective/ (pre-draft) or
    # <thread>.{N}.perspective/ (re-run).
    assert "<thread>.0.perspective/" in body, (
        "proposal-perspective.md MUST document the pre-draft sibling dir path"
    )
    assert "<thread>.{N}.perspective/" in body, (
        "proposal-perspective.md MUST document the re-run sibling dir path"
    )


def test_proposal_perspective_has_pub_litsearch_shape_sections():
    body = _read(PERSPECTIVE_MD)
    # Mirror pub-litsearch.md's overall shape: Reads / Writes (in header) +
    # Inputs / Outputs / Procedure / Idempotence / failure modes / re-run.
    assert "## Inputs" in body, "proposal-perspective.md MUST have an Inputs section"
    assert "## Outputs" in body, "proposal-perspective.md MUST have an Outputs section"
    assert "## Procedure" in body, "proposal-perspective.md MUST have a Procedure section"
    assert "Failure modes" in body or "## Failure" in body, (
        "proposal-perspective.md MUST have a Failure modes section "
        "(mirrors pub-litsearch.md / deck-perspective.md shape)"
    )
    assert "Re-run" in body or "re-run" in body, (
        "proposal-perspective.md MUST document the re-run pattern "
        "(mirrors pub-litsearch.md / deck-perspective.md shape)"
    )


def test_proposal_perspective_documents_no_fabrication_rule():
    body = _read(PERSPECTIVE_MD)
    # The no-fabrication rule is the load-bearing safeguard inherited from
    # the framework snippet; it MUST appear verbatim or near-verbatim.
    lowered = body.lower()
    assert "do not invent" in lowered or "no-fabrication" in lowered or (
        "no fabrication" in lowered
    ), (
        "proposal-perspective.md MUST document the no-fabrication / "
        "do-not-invent rule (issue #180 AC; inherited from "
        "snippets/perspective.md)"
    )
    # Source URL / source pointer is the no-fabrication enforcement mechanism.
    assert "URL" in body or "source pointer" in body, (
        "proposal-perspective.md MUST require source URLs / pointers on every "
        "candidate (no-fabrication enforcement)"
    )
    # Normative MUST language.
    assert "MUST NOT" in body or "MUST refuse" in body, (
        "proposal-perspective.md MUST use normative MUST language around the "
        "no-fabrication rule"
    )


def test_proposal_perspective_documents_non_gating():
    body = _read(PERSPECTIVE_MD)
    # Per snippets/perspective.md, the sibling is non-gating. The command
    # file MUST surface this so the consumer sees it without crawling the
    # snippet.
    assert "non-gating" in body or "non gating" in body, (
        "proposal-perspective.md MUST surface the non-gating contract"
    )
    assert "does NOT block" in body or "does not block" in body, (
        "proposal-perspective.md MUST state that absence does NOT block the "
        "state machine"
    )


def test_proposal_perspective_documents_workflows():
    body = _read(PERSPECTIVE_MD)
    # Per snippets/perspective.md, three workflows are supported.
    assert "pre-staged" in body, (
        "proposal-perspective.md MUST document the pre-staged workflow"
    )
    assert "agent-driven" in body or "agent driven" in body, (
        "proposal-perspective.md MUST document the agent-driven workflow"
    )
    assert "hybrid" in body.lower(), (
        "proposal-perspective.md MUST document the hybrid workflow"
    )


def test_proposal_perspective_declares_scorecard_kind():
    body = _read(PERSPECTIVE_MD)
    # Per snippets/scorecard_kind.md, perspective siblings declare
    # scorecard_kind: human-verdict in _meta.json.
    assert "scorecard_kind" in body, (
        "proposal-perspective.md MUST document the scorecard_kind declaration"
    )
    assert "human-verdict" in body, (
        "proposal-perspective.md MUST declare scorecard_kind: human-verdict "
        "per snippets/scorecard_kind.md"
    )


def test_proposal_perspective_uses_perspective_naming_not_research():
    body = _read(PERSPECTIVE_MD)
    # The architect contract names the command "proposal-perspective" (NOT
    # "proposal-research") per snippets/perspective.md §"Naming: perspective,
    # not research". A regression to "research" would be a contract drift.
    assert "proposal-perspective" in body, (
        "proposal-perspective.md MUST refer to itself as proposal-perspective "
        "(NOT proposal-research) per snippets/perspective.md naming contract"
    )


def test_proposal_perspective_documents_proposal_specific_substrate():
    """Proposal-side perspective targets DIFFERENT substrate than deck:
    comparable-project research, vendor-quote substrate, and regulatory /
    permitting context — NOT pitch-deck market positioning. The command file
    MUST surface this domain emphasis so a reader sees the proposal-specific
    framing immediately."""
    body = _read(PERSPECTIVE_MD)
    lowered = body.lower()
    # Comparable-project research substrate
    assert "comparable" in lowered, (
        "proposal-perspective.md MUST mention comparable-project substrate "
        "(per issue #180 / architect Phase 2B contract)"
    )
    # Vendor-quote substrate
    assert "vendor" in lowered and "quote" in lowered, (
        "proposal-perspective.md MUST mention vendor-quote substrate "
        "(per issue #180 / architect Phase 2B contract)"
    )
    # Regulatory / permitting context
    assert "regulatory" in lowered or "permit" in lowered or "compliance" in lowered, (
        "proposal-perspective.md MUST mention regulatory / permitting / "
        "compliance substrate (per issue #180 / architect Phase 2B contract)"
    )


# ---------------------------------------------------------------------------
# SKILL.md — artifact-contract diagram + state-machine note + command dispatch
# ---------------------------------------------------------------------------


def test_skill_md_artifact_contract_lists_perspective_sibling():
    body = _read(SKILL_MD)
    # Per AC: insert <thread>.0.perspective/ between brief snapshot and first
    # drafted version in the artifact-contract diagram.
    assert "<thread>.0.perspective/" in body, (
        "proposal SKILL.md MUST list <thread>.0.perspective/ in the artifact-"
        "contract diagram per issue #180 AC"
    )


def test_skill_md_perspective_appears_before_first_drafted_version():
    """The artifact-contract diagram MUST order perspective sibling between
    the thread root (with BRIEF.md) and the .1/ first drafted version."""
    body = _read(SKILL_MD)
    thread_root_pos = body.find("<thread>/")
    perspective_pos = body.find("<thread>.0.perspective/")
    draft_pos = body.find("<thread>.1/")
    assert thread_root_pos > -1 and perspective_pos > -1 and draft_pos > -1
    assert thread_root_pos < perspective_pos < draft_pos, (
        "proposal SKILL.md artifact-contract diagram MUST order the "
        "perspective sibling between <thread>/ (root with BRIEF.md) and "
        "<thread>.1/ (first drafted version) per issue #180 AC"
    )


def test_skill_md_state_machine_notes_optional_perspective():
    body = _read(SKILL_MD)
    # The state-machine section MUST have the optional-sibling note (adapted
    # from deck/SKILL.md state-machine section).
    assert ".0.perspective/" in body
    # The non-gating wording must appear in the state-machine context.
    lowered = body.lower()
    assert "non-gating" in lowered or "not gate" in lowered or (
        "does not block" in lowered
    ), (
        "proposal SKILL.md state-machine section MUST note that the "
        "perspective sibling is optional and non-gating (issue #180 AC; "
        "adapted from deck/SKILL.md state-machine section)"
    )


def test_skill_md_command_dispatch_lists_proposal_perspective():
    body = _read(SKILL_MD)
    # Coherence: the command-dispatch table should include the new command
    # so consumers see it without flipping to commands/.
    assert "proposal-perspective" in body, (
        "proposal SKILL.md command-dispatch table MUST list proposal-perspective "
        "per issue #180 AC"
    )


def test_skill_md_preserves_required_critic_set():
    """The required critic set for proposal is review + audit (both REQUIRED).
    Perspective MUST NOT be added as required — backwards-compat AC."""
    body = _read(SKILL_MD)
    # The "two REQUIRED critic siblings" phrasing must survive intact (it
    # appears in commands/proposal-audit.md and commands/proposal-review.md;
    # SKILL.md uses the table-row REQUIRED-by-default phrasing).
    assert "REQUIRED by default" in body, (
        "proposal SKILL.md MUST preserve the REQUIRED-by-default audit "
        "framing — perspective MUST NOT be added as required (issue #180 "
        "backwards-compat AC)"
    )


# ---------------------------------------------------------------------------
# proposal-draft.md — optional perspective consumer (issue #180 AC)
# ---------------------------------------------------------------------------


def test_proposal_draft_references_perspective_sibling():
    body = _read(DRAFT_MD)
    assert ".perspective/" in body or "perspective sibling" in body.lower(), (
        "proposal-draft.md MUST reference the perspective sibling (issue #180 AC)"
    )


def test_proposal_draft_marks_perspective_as_optional():
    body = _read(DRAFT_MD)
    # AC: "Required inputs unchanged" — perspective MUST be marked optional /
    # non-gating so the reader sees that drafting works WITHOUT perspective.
    lowered = body.lower()
    assert "optional" in lowered, (
        "proposal-draft.md MUST mark the perspective sibling as optional"
    )
    assert "non-gating" in lowered or "does not block" in lowered or (
        "proceeds normally" in lowered
    ), (
        "proposal-draft.md MUST clarify that absence does NOT block drafting "
        "(issue #180 backwards-compat AC)"
    )


def test_proposal_draft_marks_perspective_as_load_bearing_when_present():
    body = _read(DRAFT_MD)
    # AC: "read perspective sibling as load-bearing context if present"
    lowered = body.lower()
    assert "load-bearing" in lowered or "load bearing" in lowered, (
        "proposal-draft.md MUST mark perspective as load-bearing context when "
        "present (issue #180 AC; architect Phase 2B contract)"
    )


def test_proposal_draft_preserves_brief_is_the_contract_rule():
    body = _read(DRAFT_MD)
    # The brief-is-the-contract framing MUST survive intact — perspective is
    # verified-substrate context, NOT an extension of what the drafter may
    # invent on top of the brief.
    lowered = body.lower()
    assert "brief-is-the-contract" in lowered or "brief is the contract" in lowered, (
        "proposal-draft.md MUST preserve the brief-is-the-contract framing "
        "(issue #180 backwards-compat AC; perspective is substrate aid, NOT "
        "an extension of the no-fabrication contract)"
    )


# ---------------------------------------------------------------------------
# proposal-audit.md — perspective candidates wired into BOM sourceability check
# (issue #180 AC; aligns with ROADMAP theme #2 — sourceability extension)
# ---------------------------------------------------------------------------


def test_proposal_audit_references_perspective_sibling():
    body = _read(AUDIT_MD)
    assert ".perspective/" in body or "perspective" in body.lower(), (
        "proposal-audit.md MUST reference the perspective sibling (issue #180 AC)"
    )


def test_proposal_audit_documents_perspective_sourceability_wiring():
    """AC: 'wire perspective candidates into the BOM sourceability check
    (per architect proposal Phase 2B's note + ROADMAP theme #2 alignment)'."""
    body = _read(AUDIT_MD)
    lowered = body.lower()
    # The wiring lives in the sourceability check (step 7) and references
    # candidates.md as additional substrate.
    assert "candidates.md" in body, (
        "proposal-audit.md MUST reference candidates.md as additional "
        "sourceability substrate (issue #180 AC)"
    )
    # The audit's wiring must mention sourceability / basis specifically.
    assert "sourceability" in lowered, (
        "proposal-audit.md MUST wire perspective into the sourceability check "
        "specifically (per architect Phase 2B note + ROADMAP theme #2)"
    )


def test_proposal_audit_documents_graceful_skip_when_perspective_absent():
    """AC: 'graceful skip when absent' — when no perspective sibling exists,
    the audit's existing cost-only sourceability behavior is unchanged."""
    body = _read(AUDIT_MD)
    lowered = body.lower()
    # The graceful-skip must be explicit so consumers see backwards-compat.
    assert (
        "inactive" in lowered
        or "backward-compat" in lowered
        or "backwards-compat" in lowered
        or "graceful skip" in lowered
    ), (
        "proposal-audit.md MUST document graceful skip when perspective is "
        "absent (issue #180 AC)"
    )
    # And specifically reference the pre-#180 behavior preservation.
    assert "pre-#180" in body or "no perspective sibling" in lowered, (
        "proposal-audit.md MUST name the pre-#180 behavior preservation OR "
        "the no-perspective-sibling case to make the graceful-skip explicit "
        "(issue #180 backwards-compat AC)"
    )


def test_proposal_audit_documents_perspective_anchor_resolution():
    """When the drafter cites a perspective anchor in the proposal (e.g., via
    LaTeX comment '% perspective: #acme-sfp-lr-quote'), the audit MUST
    resolve the anchor to the candidate entry and verify the candidate's own
    source pointer — anti-laundering safeguard per no-fabrication rule."""
    body = _read(AUDIT_MD)
    lowered = body.lower()
    assert "anchor" in lowered, (
        "proposal-audit.md MUST document anchor resolution (issue #180 AC; "
        "anti-laundering safeguard so the audit resolves perspective anchors "
        "back to ground-truth source pointers per the no-fabrication rule)"
    )


# ---------------------------------------------------------------------------
# Cross-file coherence
# ---------------------------------------------------------------------------


def test_perspective_command_consistent_with_skill_md_diagram():
    """The owned-output schema in proposal-perspective.md MUST match the
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
    snippet ever goes away, the proposal-perspective command becomes
    orphaned — the test catches the regression."""
    assert (SNIPPETS / "perspective.md").exists(), (
        "anvil/lib/snippets/perspective.md MUST exist (load-bearing for "
        "proposal-perspective.md per issue #180 / Epic #143 Phase 2B)"
    )


def test_deck_perspective_still_exists_as_precedent():
    """Guard: proposal-perspective.md cites deck-perspective.md as the
    Phase 1B canary precedent. If that file goes away, proposal-perspective
    loses the cross-skill rollout coherence the architect contract relies on."""
    deck_perspective = (
        Path(__file__).resolve().parents[3]
        / "anvil"
        / "skills"
        / "deck"
        / "commands"
        / "deck-perspective.md"
    )
    assert deck_perspective.exists(), (
        "anvil/skills/deck/commands/deck-perspective.md MUST exist (Phase 1B "
        "canary precedent that proposal-perspective.md mirrors per issue #180)"
    )
