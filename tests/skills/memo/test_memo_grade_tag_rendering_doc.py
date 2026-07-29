"""Doc-coverage smoke tests for the evidence-grade rendering contract.

Per issue #751: evidence-grading vocabulary (``[SOLID]``, ``[DERIVED]``,
``[ESTIMATE from SOLID inputs]``, ``[MEDIUM]``, etc.) is internal
research-pipeline metadata. The preservation contract ("evidence grades
must be preserved") never said *where* they render, so drafters
satisfied it the cheapest literal way: transcribing the tag inline into
reader-facing prose. This test file is a cheap "grep-the-doc" regression
guard (the #747/#137 precedent) that the rendering rule stays documented
in the two files it touches (memo-draft.md, rubric.md) and that the two
documents reference each other coherently.

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The lifecycle commands themselves are
LLM-driven, so behavioural assertions belong in consumer-side integration
tests, not here.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with a similarly-shaped file
another skill might pick.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
RUBRIC_MD = SKILL_ROOT / "rubric.md"
DRAFT_MD = SKILL_ROOT / "commands" / "memo-draft.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# memo-draft.md — drafter has an explicit evidence-grade rendering rule
# ---------------------------------------------------------------------------


def test_memo_draft_has_evidence_grade_rendering_convention():
    body = _read(DRAFT_MD)
    assert "Evidence-grade rendering convention" in body, (
        "memo-draft.md MUST contain an explicit Evidence-grade rendering "
        "convention subsection (issue #751)"
    )


def test_memo_draft_names_example_grade_tags():
    body = _read(DRAFT_MD)
    for tag in ("[SOLID]", "[DERIVED]", "[ESTIMATE", "[MEDIUM]"):
        assert tag in body, (
            f"memo-draft.md MUST name the example grade tag {tag!r} so "
            "drafters recognize the taxonomy the rule governs (issue #751)"
        )


def test_memo_draft_names_apparatus_homes_for_grades():
    body = _read(DRAFT_MD)
    assert "Sources" in body, (
        "memo-draft.md's grade-tag rule MUST name the BRIEF.md Sources "
        "block as an apparatus home for evidence grades (issue #751)"
    )
    assert "exhibit ledger" in body or "Exhibit-D" in body, (
        "memo-draft.md's grade-tag rule MUST name the exhibit ledger as "
        "an apparatus home for evidence grades (issue #751)"
    )
    assert "refs/" in body, (
        "memo-draft.md's grade-tag rule MUST name refs/<key>.md stubs as "
        "an apparatus home for evidence grades (issue #751)"
    )


def test_memo_draft_requires_plain_language_hedge_in_body():
    body = _read(DRAFT_MD).lower()
    assert "plain-language hedge" in body or "in-prose hedge" in body, (
        "memo-draft.md MUST teach drafters to substitute a plain-language "
        "hedge for the bracket tag in body prose (issue #751)"
    )


def test_memo_draft_carries_worked_applied_compute_example():
    """The canary's before/after worked example (praetor memo.5) MUST be
    documented verbatim so drafters see the concrete substitution."""
    body = _read(DRAFT_MD)
    assert "Applied Compute" in body, (
        "memo-draft.md MUST carry the Applied Compute worked before/after "
        "example (issue #751 canary evidence)"
    )
    assert "verify before treating as load-bearing" in body, (
        "memo-draft.md MUST call out the drafter-directed-instruction "
        "smuggling failure mode from the canary's second worked instance "
        "(issue #751)"
    )


def test_memo_draft_references_rubric_dim_8_deduction():
    body = _read(DRAFT_MD)
    assert "Grade-tag leakage" in body, (
        "memo-draft.md MUST point at rubric.md's Grade-tag leakage "
        "subsection so the drafter knows where the deduction lands "
        "(issue #751)"
    )
    assert "dim 8" in body.lower(), (
        "memo-draft.md's grade-tag rule MUST reference dim 8 so the "
        "drafter knows which dimension carries the deduction (issue #751)"
    )


# ---------------------------------------------------------------------------
# rubric.md — dim 8 has a named Grade-tag leakage subsection
# ---------------------------------------------------------------------------


def test_rubric_has_grade_tag_leakage_subsection():
    body = _read(RUBRIC_MD)
    assert "Grade-tag leakage" in body, (
        "rubric.md MUST contain a 'Grade-tag leakage' subsection (issue #751)"
    )


def test_rubric_grade_tag_leakage_binds_to_dim_8():
    body = _read(RUBRIC_MD)
    # Anchor on the actual headings (## Dim 8 / ## Dim 9), not any
    # cross-reference prose mentioning "dim 8"/"dim 9" earlier in the
    # document (e.g. the #747 dim-9 cross-reference inside the dim-3
    # citation-hooks section).
    dim8_idx = body.find("## Dim 8")
    assert dim8_idx != -1, "rubric.md MUST contain a '## Dim 8' heading"
    dim9_idx = body.find("## Dim 9")
    assert dim9_idx != -1, "rubric.md MUST contain a '## Dim 9' heading"
    assert dim8_idx < body.find("Grade-tag leakage") < dim9_idx, (
        "rubric.md's Grade-tag leakage subsection MUST live under Dim 8, "
        "between the Dim 8 and Dim 9 headings (issue #751)"
    )


def test_rubric_documents_per_instance_deduction_for_grade_tags():
    body = _read(RUBRIC_MD).lower()
    grade_idx = body.find("grade-tag leakage")
    assert grade_idx != -1
    section = body[grade_idx:]
    assert "single-point" in section, (
        "rubric.md's Grade-tag leakage subsection MUST document the "
        "single-point deduction calibration (issue #751)"
    )
    assert "two-point" in section, (
        "rubric.md's Grade-tag leakage subsection MUST document the "
        "two-point deduction for pervasive leakage (issue #751)"
    )


def test_rubric_requires_named_instance_citation_for_grade_tags():
    body = _read(RUBRIC_MD)
    grade_idx = body.find("Grade-tag leakage")
    section = body[grade_idx : grade_idx + 3000]
    assert "instance-naming" in section.lower(), (
        "rubric.md's Grade-tag leakage subsection MUST require named-"
        "instance citation, matching the dim 3 citation-hooks standard "
        "(issue #751)"
    )


def test_rubric_documents_sources_block_exemption():
    body = _read(RUBRIC_MD)
    grade_idx = body.find("Grade-tag leakage")
    section = body[grade_idx : grade_idx + 3000]
    assert "exemption" in section.lower(), (
        "rubric.md's Grade-tag leakage subsection MUST document the "
        "Sources-block / ledger exemption (issue #751)"
    )
    assert "refs/" in section, (
        "rubric.md's Sources-block exemption MUST name refs/<key>.md "
        "stubs alongside the Sources block and exhibit ledger (issue #751)"
    )


def test_rubric_documents_audience_opt_out_via_rubric_overrides():
    body = _read(RUBRIC_MD)
    grade_idx = body.find("Grade-tag leakage")
    section = body[grade_idx : grade_idx + 3000]
    assert "dim_8_calibration" in section, (
        "rubric.md's Grade-tag leakage subsection MUST document the "
        "dim_8_calibration rubric_overrides opt-out for internal-audience "
        "artifact types (issue #751 acceptance sketch)"
    )
    assert "rubric_overrides" in section, (
        "rubric.md's Grade-tag leakage subsection MUST name the "
        "rubric_overrides surface used for the audience opt-out "
        "(issue #751)"
    )


def test_rubric_grade_tag_leakage_preserves_dim9_section():
    """The new Dim 8 subsection MUST NOT displace the existing Dim 9
    rhetorical-economy section (issue #747's redundant-provenance rule
    lives there)."""
    body = _read(RUBRIC_MD)
    assert "Redundant provenance restatement" in body, (
        "rubric.md MUST preserve the existing Dim 9 'Redundant provenance "
        "restatement' subsection (issue #747)"
    )


# ---------------------------------------------------------------------------
# Cross-doc coherence — memo-draft.md and rubric.md reference each other
# ---------------------------------------------------------------------------


def test_memo_draft_and_rubric_reference_issue_751_by_number():
    assert "#751" in _read(DRAFT_MD), (
        "memo-draft.md's grade-tag rendering convention MUST cite issue "
        "#751 for audit-trail traceability"
    )
    assert "#751" in _read(RUBRIC_MD), (
        "rubric.md's Grade-tag leakage subsection MUST cite issue #751 "
        "for audit-trail traceability"
    )
