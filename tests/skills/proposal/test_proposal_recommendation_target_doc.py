"""Doc-coverage tests for the proposal `recommendation_target: undecided` calibration.

Issue #356 promotes the informal `recommendation_target` frontmatter key
on a proposal thread's `<thread>/BRIEF.md` into a typed signal that
triggers a **dim 8 (Open decisions)** calibration when the operator
declares the thread is in pre-decision / concept-stage mode
(`recommendation_target: undecided`). The implementation surface is
four files; this test pins the doc-coverage so future drift is caught
early:

1. `anvil/skills/proposal/rubric.md` documents the calibration in a new
   §"Dim 8 — `recommendation_target: undecided` calibration" section
   with the trigger, the five-point scoring posture, the suffix shape,
   the rationale for calibrating dim 8 (NOT dim 1 — proposal dim 1 is
   *Intent / requirements clarity*, not *Recommendation clarity*), and
   the backwards-compat contract.
2. `anvil/skills/proposal/commands/proposal-review.md` references the
   new step 4j (load `recommendation_target` from the thread BRIEF),
   the dim 8 sub-step in step 5 that applies the calibration, and the
   `_summary.md.recommendation_target_resolved` block in step 9b that
   records the audit trail.
3. The helper `load_recommendation_target` is exported from
   `anvil/skills/proposal/lib/project_brief.py`.
4. The shipped `anvil/skills/proposal/templates/BRIEF.md.example`
   demonstrates `recommendation_target: undecided` as the documented
   default.

Per the #58 packaging convention, this filename
(`test_proposal_recommendation_target_doc.py`) is unique across
`tests/skills/*/` so it does not collide with other skills' tests
(notably `tests/skills/memo/test_memo_recommendation_target_doc.py`).
"""

from __future__ import annotations

from pathlib import Path


# tests/skills/proposal → anvil/skills/proposal
SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "proposal"
RUBRIC = SKILL_ROOT / "rubric.md"
REVIEW_COMMAND = SKILL_ROOT / "commands" / "proposal-review.md"
DRAFT_COMMAND = SKILL_ROOT / "commands" / "proposal-draft.md"
PROJECT_BRIEF = SKILL_ROOT / "lib" / "project_brief.py"
BRIEF_TEMPLATE = SKILL_ROOT / "templates" / "BRIEF.md.example"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# rubric.md — new §"Dim 8 — recommendation_target: undecided calibration"
# ---------------------------------------------------------------------------


def test_rubric_documents_recommendation_target_undecided_section() -> None:
    """The rubric MUST have a section dedicated to the dim 8 undecided calibration."""
    body = _read(RUBRIC)
    assert (
        "Dim 8 — `recommendation_target: undecided` calibration" in body
        or "Dim 8 — recommendation_target: undecided calibration" in body
    ), (
        "rubric.md MUST have a `## Dim 8 — `recommendation_target: undecided` "
        "calibration` section documenting the new calibration (issue #356)"
    )


def test_rubric_undecided_section_documents_trigger() -> None:
    """The section MUST describe the trigger (recommendation_target: undecided in BRIEF)."""
    body = _read(RUBRIC)
    # The trigger is the thread-level BRIEF carrying recommendation_target: undecided.
    assert "recommendation_target: undecided" in body, (
        "rubric.md MUST mention `recommendation_target: undecided` as the "
        "trigger value for the new dim 8 calibration (issue #356)"
    )


def test_rubric_undecided_section_documents_open_decision_framing() -> None:
    """The section MUST document scoring on open-decision framing clarity."""
    body = _read(RUBRIC)
    assert "open-decision framing clarity" in body, (
        "rubric.md MUST document that the undecided calibration scores dim 8 "
        "on `open-decision framing clarity` (the proposal-shaped analog to "
        "memo's `decision-framework clarity`) (issue #356 acceptance criteria)"
    )


def test_rubric_undecided_section_documents_why_dim_8_not_dim_1() -> None:
    """The section MUST document why dim 8 (not dim 1) is calibrated."""
    body = _read(RUBRIC)
    # The curator's load-bearing rationale: proposal dim 1 is Intent /
    # requirements clarity, not Recommendation clarity — so dim 1 is the
    # wrong dim to re-scope. The doc-coverage guard ensures this rationale
    # stays in the rubric so a future reader does not "fix" it.
    assert "Intent / requirements clarity" in body, (
        "rubric.md MUST document that proposal dim 1 is *Intent / "
        "requirements clarity* (not *Recommendation clarity*) to explain "
        "why dim 8 (not dim 1) is the calibrated dimension — the curator's "
        "load-bearing rationale on issue #356"
    )
    assert "dim 8" in body.lower() and (
        "NOT dim 1" in body or "not dim 1" in body
    ), (
        "rubric.md MUST explicitly state that the calibration lands on "
        "dim 8 and NOT dim 1 (issue #356 curator rationale)"
    )


def test_rubric_undecided_section_documents_suffix_shape() -> None:
    """The section MUST document the verbatim suffix shape for the audit trail."""
    body = _read(RUBRIC)
    assert (
        "recommendation_target: undecided — scoring dim 8 on open-decision framing clarity"
        in body
    ), (
        "rubric.md MUST document the verbatim suffix appended to dim 8's "
        "scoring.md justification when the undecided calibration fires "
        "(issue #356 acceptance criteria — suffix shape recorded for "
        "reproducible audit trail)"
    )


def test_rubric_undecided_section_documents_backwards_compat() -> None:
    """The section MUST document the byte-identical-when-absent contract."""
    body = _read(RUBRIC)
    assert "byte-identical" in body.lower() or "zero-impact" in body.lower(), (
        "rubric.md MUST document that the calibration is byte-identical / "
        "zero-impact when the trigger value is absent or non-undecided "
        "(issue #356 backwards-compat AC)"
    )


def test_rubric_undecided_section_documents_five_point_ladder() -> None:
    """The section MUST document the five-point scoring ladder (5/5 ... 0/5)."""
    body = _read(RUBRIC)
    # At minimum the ladder anchors at 5/5 and 0/5; intermediate rungs
    # are also documented but the anchors are the load-bearing reference.
    assert "5/5" in body and "0/5" in body, (
        "rubric.md MUST document the five-point scoring ladder for the "
        "undecided calibration (5/5 full weight → 0/5 no open-decision "
        "framing) (issue #356 acceptance criteria — five-point scoring "
        "posture parallel to memo dim 1)"
    )


# ---------------------------------------------------------------------------
# proposal-review.md — step 4j (load) + step 5 sub-step (apply) + step 9b block
# ---------------------------------------------------------------------------


def test_proposal_review_references_load_recommendation_target() -> None:
    """proposal-review.md MUST reference the new load_recommendation_target helper."""
    body = _read(REVIEW_COMMAND)
    assert "load_recommendation_target" in body, (
        "proposal-review.md MUST reference `load_recommendation_target` so "
        "the reviewer agent knows to call the helper when reading inputs "
        "(issue #356 acceptance criteria)"
    )


def test_proposal_review_describes_step_4j_or_loader_step() -> None:
    """proposal-review.md MUST describe loading recommendation_target as a step."""
    body = _read(REVIEW_COMMAND)
    # The plumbing step is named 4j in the implementation; allow for future
    # renumbering by matching on the load step's substance.
    assert (
        "Load `recommendation_target`" in body
        or "load_recommendation_target" in body
    ), (
        "proposal-review.md MUST document a step that loads "
        "`recommendation_target` from the thread-level BRIEF (issue #356)"
    )


def test_proposal_review_describes_dim_8_calibration_sub_step() -> None:
    """proposal-review.md MUST describe the dim 8 sub-step that applies the calibration."""
    body = _read(REVIEW_COMMAND)
    # The cached value name is recommendation_target_resolved (mirrors memo).
    assert "recommendation_target_resolved" in body, (
        "proposal-review.md MUST cache the resolved value as "
        "`recommendation_target_resolved` and reference it in the dim 8 "
        "scoring sub-step + the `_summary.md` write (issue #356)"
    )
    # The sub-step MUST name dim 8 (not dim 1) per the curator's correction.
    assert "Dim 8" in body or "dim 8" in body, (
        "proposal-review.md MUST name dim 8 as the calibrated dimension "
        "(NOT dim 1 — issue #356 curator correction)"
    )


def test_proposal_review_documents_verbatim_suffix() -> None:
    """proposal-review.md MUST document the same verbatim suffix as rubric.md."""
    body = _read(REVIEW_COMMAND)
    assert (
        "recommendation_target: undecided — scoring dim 8 on open-decision framing clarity"
        in body
    ), (
        "proposal-review.md MUST document the verbatim suffix shape so the "
        "reviewer agent emits the same audit-trail string the rubric "
        "documents (issue #356 — suffix wording locked in rubric.md per the "
        "rubric.md schema-of-record precedent)"
    )


def test_proposal_review_summary_md_block_documented() -> None:
    """The `_summary.md.recommendation_target_resolved` block MUST be in the spec."""
    body = _read(REVIEW_COMMAND)
    # The block carries {value, applied}; both fields are load-bearing for
    # downstream audit-trail consumers.
    assert '"recommendation_target_resolved"' in body, (
        "proposal-review.md step 9b MUST show the "
        "`recommendation_target_resolved` block in the `_summary.md` example "
        "(issue #356 audit-trail AC)"
    )
    assert '"applied":' in body or "`applied`" in body, (
        "proposal-review.md MUST document the `applied` field on the "
        "`recommendation_target_resolved` block (issue #356)"
    )


# ---------------------------------------------------------------------------
# proposal-draft.md — recognized-keys list documents recommendation_target
# ---------------------------------------------------------------------------


def test_proposal_draft_documents_recommendation_target_key() -> None:
    """proposal-draft.md MUST recognize recommendation_target as a frontmatter key."""
    body = _read(DRAFT_COMMAND)
    assert "recommendation_target" in body, (
        "proposal-draft.md MUST list `recommendation_target` as a recognized "
        "frontmatter key on the proposal thread-level BRIEF (issue #356)"
    )


# ---------------------------------------------------------------------------
# Helper export — project_brief.py exposes load_recommendation_target
# ---------------------------------------------------------------------------


def test_project_brief_exports_load_recommendation_target() -> None:
    """The helper MUST be exported from project_brief.py via __all__."""
    body = _read(PROJECT_BRIEF)
    assert "def load_recommendation_target" in body, (
        "project_brief.py MUST define `load_recommendation_target` (issue #356)"
    )
    assert '"load_recommendation_target"' in body, (
        "project_brief.py's `__all__` MUST include "
        "`load_recommendation_target` (issue #356)"
    )


def test_project_brief_documents_closed_set() -> None:
    """The helper MUST document the closed set of recognized values."""
    body = _read(PROJECT_BRIEF)
    # All four values appear in the helper's recognized-set tuple.
    for value in ("invest", "pass", "conditional", "undecided"):
        assert value in body, (
            f"project_brief.py MUST recognize {value!r} as one of the "
            f"closed-set values for recommendation_target (issue #356)"
        )


def test_project_brief_stays_skill_local() -> None:
    """The helper MUST stay skill-local; promotion to anvil/lib/ is deferred."""
    # Skill-local-first per CLAUDE.md "wait for the second consumer before
    # generalizing"; proposal is the second consumer but the helper signature
    # is skill-specific (different dim calibrated, different rubric prose) so
    # promotion is premature. This test is a forward-looking guard: if a
    # future change promotes the helper to anvil/lib/project_brief.py the
    # test catches the move and forces the author to update the doc-
    # coverage guards accordingly.
    assert PROJECT_BRIEF.exists(), (
        "the proposal-local project_brief.py MUST live at "
        f"{PROJECT_BRIEF} (issue #356 — skill-local-first per CLAUDE.md)"
    )


# ---------------------------------------------------------------------------
# Template — the shipped BRIEF.md.example demonstrates the default
# ---------------------------------------------------------------------------


def test_brief_template_demonstrates_undecided_default() -> None:
    """The shipped BRIEF.md.example MUST carry the undecided default."""
    body = _read(BRIEF_TEMPLATE)
    assert "recommendation_target: undecided" in body, (
        "BRIEF.md.example MUST demonstrate "
        "`recommendation_target: undecided` as the documented default "
        "(issue #356 — mirror of memo's `templates/BRIEF.fresh.md.example`)"
    )
