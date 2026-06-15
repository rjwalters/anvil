"""Doc-coverage tests: the report skill consumes the voice contract (#578).

Phase C of epic #575 broadens voice-grounding consumption beyond ``essay``
(owns dim 2) and ``memo`` (dim 8 calibration) to the ``report`` skill, which
calibrates its **dim 8 (Tone & audience calibration)** — the rubric's native
register/voice home — when the project BRIEF declares a ``voice:`` block. The
wiring copies the memo dim-8 precedent exactly: a triggered fixed suffix on a
named dimension, NO tenth dimension, NO change to the /44 total.

These grep-tests pin the four contract surfaces so future drift is caught (the
``test_memo_voice_grounding_doc.py`` precedent):

1. ``rubric.md`` §"Dim 8 — voice-grounding calibration" (verbatim suffix; /44
   total unchanged; no tenth dim; byte-identical-when-absent).
2. ``report-review.md`` — the step 4d load, the dim 8 triggered suffix, the
   ``_summary.md.voice_grounding`` block, the no-``ran:false`` convention, and
   the declared-but-missing → major-finding posture.
3. ``report-draft.md`` — the advisory load + the ``voice_exemplars`` record.
4. ``report-revise.md`` — the read-and-preserve cross-reference.

The load-bearing **activation** assertions: (a) the calibration is gated on a
non-empty resolved voice-doc list (active ONLY when the ``voice:`` tier is
declared), and (b) absence of a ``voice:`` block is byte-identical to
pre-#578 (the #428/#452 contract).

Per the #58 packaging convention, this filename is unique across
``tests/skills/*/``.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "anvil" / "skills" / "report"
RUBRIC = SKILL_ROOT / "rubric.md"
DRAFT_COMMAND = SKILL_ROOT / "commands" / "report-draft.md"
REVIEW_COMMAND = SKILL_ROOT / "commands" / "report-review.md"
REVISE_COMMAND = SKILL_ROOT / "commands" / "report-revise.md"

# The verbatim triggered suffix — identical to the memo dim-8 precedent so the
# audit trail reads the same across skills.
VOICE_SUFFIX = (
    "voice grounding active — dim 8 scored against "
    "<resolved values/style_guide paths>; voice deductions must quote "
    "corpus exemplars"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _norm(p: Path) -> str:
    """Whitespace-normalized body — phrase checks tolerate markdown wrapping."""
    return " ".join(p.read_text(encoding="utf-8").split())


# ---------------------------------------------------------------------------
# rubric.md — dim 8 calibration section + /44 invariant
# ---------------------------------------------------------------------------


def test_rubric_documents_dim8_calibration_section() -> None:
    body = _norm(RUBRIC)
    assert "## Dim 8 — voice-grounding calibration" in body, (
        "report rubric.md MUST have a §'Dim 8 — voice-grounding calibration' "
        "section (issue #578)"
    )
    assert VOICE_SUFFIX in body, (
        "report rubric.md MUST document the verbatim triggered suffix (copied "
        "from the memo dim-8 precedent)"
    )


def test_rubric_keeps_44_total_no_tenth_dim() -> None:
    body = _read(RUBRIC)
    # The /44 total row is unchanged — calibration, not a new dimension.
    assert "| | **Total** | **44** |" in body, (
        "report rubric total row must remain /44 — the voice calibration is a "
        "suffix on dim 8, never a tenth dimension"
    )
    norm = _norm(RUBRIC)
    assert "does NOT add a tenth dimension" in norm, (
        "report rubric.md MUST state the calibration adds no tenth dimension"
    )
    # No dimension numbered 10 is introduced in the dimensions table.
    assert "\n| 10 |" not in body, (
        "report rubric introduced a dimension #10 — the calibration must stay "
        "a dim 8 suffix"
    )


def test_rubric_dim8_documents_byte_identical_backwards_compat() -> None:
    body = _read(RUBRIC)
    section = body.split("## Dim 8 — voice-grounding calibration", 1)[1]
    section = section.split("\n## ", 1)[0]
    assert "byte-identical" in section, (
        "report rubric's dim 8 voice section MUST document the "
        "byte-identical-when-absent contract (#428/#452)"
    )


# ---------------------------------------------------------------------------
# report-review.md — the three reviewer touch-points + activation gating
# ---------------------------------------------------------------------------


def test_review_references_snippet_and_resolver() -> None:
    body = _norm(REVIEW_COMMAND)
    assert "anvil/lib/snippets/voice_grounding.md" in body, (
        "report-review.md MUST reference the voice_grounding snippet"
    )
    assert "resolve_voice_docs" in body, (
        "report-review.md MUST invoke "
        "anvil/lib/project_brief.py::resolve_voice_docs"
    )
    assert "4d." in body, (
        "report-review.md MUST add the voice-doc load as a step (4d)"
    )


def test_review_carries_verbatim_suffix() -> None:
    body = _norm(REVIEW_COMMAND)
    assert VOICE_SUFFIX in body, (
        "report-review.md MUST document the verbatim dim 8 triggered suffix"
    )


def test_review_activation_is_gated_on_resolved_docs() -> None:
    """The calibration fires ONLY when the resolved voice-doc list is non-empty."""
    body = _norm(REVIEW_COMMAND)
    assert "when the cached `voice_docs_resolved` from step 4d is non-empty" in body, (
        "report-review.md MUST gate the dim 8 sub-step on a non-empty resolved "
        "voice-doc list (active only when the voice: tier is declared)"
    )
    assert "Inert when not triggered" in body, (
        "report-review.md MUST document the inert-when-not-triggered behavior"
    )


def test_review_byte_identical_when_absent() -> None:
    body = _norm(REVIEW_COMMAND)
    assert "byte-identical" in body, (
        "report-review.md MUST document the no-voice-block → byte-identical "
        "review contract (#428/#452)"
    )
    # No suffix when inactive.
    assert "no dim 8 suffix" in body, (
        "report-review.md MUST state that no dim 8 suffix is emitted when the "
        "voice tier is inactive"
    )


def test_review_documents_summary_block() -> None:
    body = _norm(REVIEW_COMMAND)
    assert '"voice_grounding"' in body, (
        "report-review.md MUST document the _summary.md voice_grounding block"
    )
    assert "exemplars_quoted" in body and "docs_loaded" in body, (
        "report-review.md MUST document the {ran, docs_loaded, exemplars_quoted} "
        "block shape"
    )


def test_review_documents_no_ran_false_convention() -> None:
    body = _norm(REVIEW_COMMAND)
    assert "the block is NOT emitted at all" in body, (
        "report-review.md MUST document that an inactive voice tier emits NO "
        "voice_grounding block (not a ran:false entry)"
    )


def test_review_documents_missing_doc_major_finding() -> None:
    body = _norm(REVIEW_COMMAND)
    assert "declared-but-missing doc" in body or "declared-but-missing" in body, (
        "report-review.md MUST document declared-but-missing voice docs"
    )
    assert "tier stays ACTIVE" in body, (
        "report-review.md MUST keep the tier active on a missing declared doc "
        "(surface as a major finding, not an opt-out)"
    )


def test_review_documents_anti_stance_critical_flag() -> None:
    body = _norm(REVIEW_COMMAND)
    assert "Voice anti-stance violation" in body, (
        "report-review.md step 6 MUST route anti-stance violations through the "
        "existing critical-flag machinery"
    )
    assert "no new flag category is introduced" in body


# ---------------------------------------------------------------------------
# report-draft.md
# ---------------------------------------------------------------------------


def test_draft_references_exemplar_record() -> None:
    body = _norm(DRAFT_COMMAND)
    assert "voice_exemplars" in body, (
        "report-draft.md MUST document the "
        "_progress.json.metadata.voice_exemplars record"
    )
    assert "resolve_voice_docs" in body
    assert "anvil/lib/snippets/voice_grounding.md" in body


def test_draft_byte_identical_when_absent() -> None:
    body = _norm(DRAFT_COMMAND)
    assert "byte-identical" in body, (
        "report-draft.md MUST document the no-voice-block → byte-identical "
        "drafting contract"
    )


# ---------------------------------------------------------------------------
# report-revise.md
# ---------------------------------------------------------------------------


def test_revise_cross_references_voice_docs() -> None:
    body = _norm(REVISE_COMMAND)
    assert "resolve_voice_docs" in body, (
        "report-revise.md MUST cross-reference reading the voice docs when the "
        "tier is active"
    )
    assert "preserve voice signatures" in body, (
        "report-revise.md MUST instruct the reviser to preserve voice "
        "signatures the reviewer flagged as working"
    )
