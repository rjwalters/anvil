"""Doc-coverage tests for the `recommendation_target: undecided` calibration.

Issue #348 promotes the informal `recommendation_target` frontmatter key
on `<thread>/BRIEF.md` into a typed signal that triggers a dim 1
calibration when the operator declares the thread is in pre-decision
mode (`recommendation_target: undecided`). The implementation surface
is three files; this test pins the doc-coverage so future drift is
caught early:

1. `anvil/skills/memo/rubric.md` documents the calibration in a new
   §"Dim 1 — `recommendation_target: undecided` calibration" section
   with the trigger, the five-point scoring posture, the suffix shape,
   and the backwards-compat contract.
2. `anvil/skills/memo/commands/memo-review.md` references the new
   step (4j) that loads `recommendation_target` from the thread-level
   BRIEF, the dim 1 sub-step in step 5 that applies the calibration,
   and the `_summary.md.recommendation_target_resolved` block in step
   9 that records the audit trail.
3. The helper `load_recommendation_target` is exported from
   `anvil/skills/memo/lib/project_brief.py`.

Per the #58 packaging convention, this filename
(`test_memo_recommendation_target_doc.py`) is unique across
`tests/skills/*/` so it does not collide with other skills' tests.
"""

from __future__ import annotations

from pathlib import Path


# tests/skills/memo → anvil/skills/memo
SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
RUBRIC = SKILL_ROOT / "rubric.md"
REVIEW_COMMAND = SKILL_ROOT / "commands" / "memo-review.md"
PROJECT_BRIEF = SKILL_ROOT / "lib" / "project_brief.py"
FRESH_TEMPLATE = SKILL_ROOT / "templates" / "BRIEF.fresh.md.example"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# rubric.md — new §"Dim 1 — recommendation_target: undecided calibration"
# ---------------------------------------------------------------------------


def test_rubric_documents_recommendation_target_undecided_section() -> None:
    """The rubric MUST have a section dedicated to the undecided calibration."""
    body = _read(RUBRIC)
    assert (
        "Dim 1 — `recommendation_target: undecided` calibration" in body
        or "Dim 1 — recommendation_target: undecided calibration" in body
    ), (
        "rubric.md MUST have a `## Dim 1 — `recommendation_target: undecided` "
        "calibration` section documenting the new calibration (issue #348)"
    )


def test_rubric_undecided_section_documents_trigger() -> None:
    """The section MUST describe the trigger (recommendation_target: undecided in BRIEF)."""
    body = _read(RUBRIC)
    # The trigger is the thread-level BRIEF carrying recommendation_target: undecided.
    assert "recommendation_target: undecided" in body, (
        "rubric.md MUST mention `recommendation_target: undecided` as the "
        "trigger value for the new dim 1 calibration (issue #348)"
    )


def test_rubric_undecided_section_documents_decision_framework_clarity() -> None:
    """The section MUST contrast decision-framework clarity vs. recommendation clarity."""
    body = _read(RUBRIC)
    assert "decision-framework clarity" in body, (
        "rubric.md MUST document that the undecided calibration scores dim 1 "
        "on `decision-framework clarity` (rather than recommendation clarity) "
        "(issue #348 acceptance criteria)"
    )


def test_rubric_undecided_section_documents_suffix_shape() -> None:
    """The section MUST document the verbatim suffix shape for the audit trail."""
    body = _read(RUBRIC)
    assert (
        "recommendation_target: undecided — scoring dim 1 on decision-framework clarity, not recommendation clarity"
        in body
    ), (
        "rubric.md MUST document the verbatim suffix appended to dim 1's "
        "scoring.md justification when the undecided calibration fires "
        "(issue #348 acceptance criteria — suffix shape recorded for "
        "reproducible audit trail)"
    )


def test_rubric_undecided_section_documents_backwards_compat() -> None:
    """The section MUST document the byte-identical-when-absent contract."""
    body = _read(RUBRIC)
    assert "byte-identical" in body.lower() or "zero-impact" in body.lower(), (
        "rubric.md MUST document that the calibration is byte-identical / "
        "zero-impact when the trigger value is absent or non-undecided "
        "(issue #348 backwards-compat AC)"
    )


def test_rubric_undecided_section_documents_five_point_ladder() -> None:
    """The section MUST document the five-point scoring ladder (5/5 ... 0/5)."""
    body = _read(RUBRIC)
    # At minimum the ladder anchors at 5/5 and 0/5; the 4/5, 3/5, 2/5 rungs
    # are also documented but the anchors are the load-bearing reference.
    assert "5/5" in body and "0/5" in body, (
        "rubric.md MUST document the five-point scoring ladder for the "
        "undecided calibration (5/5 full weight → 0/5 no decision framing) "
        "(issue #348 acceptance criteria — five-point scoring posture)"
    )


# ---------------------------------------------------------------------------
# memo-review.md — step 4j (load) + step 5 sub-step (apply) + step 9 block
# ---------------------------------------------------------------------------


def test_memo_review_references_load_recommendation_target() -> None:
    """memo-review.md MUST reference the new load_recommendation_target helper."""
    body = _read(REVIEW_COMMAND)
    assert "load_recommendation_target" in body, (
        "memo-review.md MUST reference `load_recommendation_target` so the "
        "reviewer agent knows to call the helper when reading inputs "
        "(issue #348 acceptance criteria)"
    )


def test_memo_review_describes_step_4j_or_loader_step() -> None:
    """memo-review.md MUST describe loading recommendation_target as a step."""
    body = _read(REVIEW_COMMAND)
    # The plumbing step is named 4j in the implementation; allow for future
    # renumbering by matching on the load step's substance.
    assert (
        "Load `recommendation_target`" in body
        or "load_recommendation_target" in body
    ), (
        "memo-review.md MUST document a step that loads "
        "`recommendation_target` from the thread-level BRIEF (issue #348)"
    )


def test_memo_review_describes_dim_1_calibration_sub_step() -> None:
    """memo-review.md MUST describe the dim 1 sub-step that applies the calibration."""
    body = _read(REVIEW_COMMAND)
    assert "recommendation_target_resolved" in body, (
        "memo-review.md MUST cache the resolved value as "
        "`recommendation_target_resolved` and reference it in the dim 1 "
        "scoring sub-step + the `_summary.md` write (issue #348)"
    )


def test_memo_review_documents_verbatim_suffix() -> None:
    """memo-review.md MUST document the same verbatim suffix as rubric.md."""
    body = _read(REVIEW_COMMAND)
    assert (
        "recommendation_target: undecided — scoring dim 1 on decision-framework clarity, not recommendation clarity"
        in body
    ), (
        "memo-review.md MUST document the verbatim suffix shape so the "
        "reviewer agent emits the same audit-trail string the rubric "
        "documents (issue #348 — suffix wording locked in rubric.md per the "
        "rubric.md schema-of-record precedent)"
    )


def test_memo_review_summary_md_block_documented() -> None:
    """The `_summary.md.recommendation_target_resolved` block MUST be in the spec."""
    body = _read(REVIEW_COMMAND)
    # The block carries {value, applied}; both fields are load-bearing for
    # downstream audit-trail consumers.
    assert '"recommendation_target_resolved"' in body, (
        "memo-review.md step 9 MUST show the "
        "`recommendation_target_resolved` block in the `_summary.md` example "
        "(issue #348 audit-trail AC)"
    )
    assert '"applied":' in body or "`applied`" in body, (
        "memo-review.md MUST document the `applied` field on the "
        "`recommendation_target_resolved` block (issue #348)"
    )


# ---------------------------------------------------------------------------
# Helper export — project_brief.py exposes load_recommendation_target
# ---------------------------------------------------------------------------


def test_project_brief_exports_load_recommendation_target() -> None:
    """The helper MUST be exported from project_brief.py via __all__."""
    body = _read(PROJECT_BRIEF)
    assert "def load_recommendation_target" in body, (
        "project_brief.py MUST define `load_recommendation_target` (issue #348)"
    )
    assert '"load_recommendation_target"' in body, (
        "project_brief.py's `__all__` MUST include `load_recommendation_target` "
        "(issue #348)"
    )


def test_project_brief_documents_closed_set() -> None:
    """The helper MUST document the closed set of recognized values."""
    body = _read(PROJECT_BRIEF)
    # All four values appear in the helper's recognized-set tuple.
    for value in ("invest", "pass", "conditional", "undecided"):
        assert value in body, (
            f"project_brief.py MUST recognize {value!r} as one of the "
            f"closed-set values for recommendation_target (issue #348)"
        )


# ---------------------------------------------------------------------------
# Template — the shipped fresh-thread example still demonstrates the default
# (no-regression guard against accidentally dropping the documented default).
# ---------------------------------------------------------------------------


def test_fresh_template_still_demonstrates_undecided_default() -> None:
    """Carry the #136 doc-coverage guard forward — the trigger value lives in the example."""
    body = _read(FRESH_TEMPLATE)
    assert "recommendation_target: undecided" in body, (
        "BRIEF.fresh.md.example MUST continue to demonstrate "
        "`recommendation_target: undecided` as the fresh-thread default "
        "(issue #136 contract preserved through #348)"
    )
