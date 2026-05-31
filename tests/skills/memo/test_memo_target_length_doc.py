"""Doc-coverage smoke tests for the memo ``target_length`` config field.

Per issue #121 acceptance criteria: cheap "grep-the-doc" regression guard
that the configurable-target-length contract stays documented in the five
files it touches (SKILL.md, three command docs, rubric.md) and doesn't
drift back to the implicit-default-only prose in a later edit.

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The lifecycle commands themselves are
LLM-driven, so behavioural assertions belong in consumer-side integration
tests, not here.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with the ``test_target_length_doc``
shape another skill might pick.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
RUBRIC_MD = SKILL_ROOT / "rubric.md"
DRAFT_MD = SKILL_ROOT / "commands" / "memo-draft.md"
REVIEW_MD = SKILL_ROOT / "commands" / "memo-review.md"
REVISE_MD = SKILL_ROOT / "commands" / "memo-revise.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SKILL.md — canonical schema home
# ---------------------------------------------------------------------------


def test_skill_md_documents_target_length_field():
    body = _read(SKILL_MD)
    assert "target_length" in body, (
        "SKILL.md MUST document the target_length field (issue #121 AC1)"
    )


def test_skill_md_has_length_targets_section():
    body = _read(SKILL_MD)
    assert "Length targets" in body, (
        "SKILL.md MUST contain a 'Length targets' section heading"
    )


def test_skill_md_documents_600_words_per_page_conversion():
    body = _read(SKILL_MD)
    assert "600 words/page" in body or "600 words per page" in body, (
        "SKILL.md MUST document the 600-words/page conversion ratio "
        "(issue #121 AC2)"
    )


def test_skill_md_shows_words_and_pages_spec_forms():
    body = _read(SKILL_MD)
    # Both spec forms must be documented as accepted.
    assert '"words"' in body, "SKILL.md MUST show the words spec form"
    assert '"pages"' in body or "pages: [" in body, (
        "SKILL.md MUST show the pages spec form (accepted, converted internally)"
    )


def test_skill_md_documents_backward_compatibility():
    body = _read(SKILL_MD)
    # Backward-compat is AC6 — absence of target_length must behave as today.
    assert "Backward compatibility" in body or "backward compatible" in body.lower()


def test_skill_md_defers_per_version_overrides():
    body = _read(SKILL_MD)
    # AC7: per-version overrides explicitly deferred to a follow-on.
    assert "per-version" in body.lower() or "Per-version" in body
    assert "follow-on" in body or "deferred" in body.lower() or "v0" in body


# ---------------------------------------------------------------------------
# memo-draft.md — drafter reads target_length and injects into prompt
# ---------------------------------------------------------------------------


def test_memo_draft_reads_target_length():
    body = _read(DRAFT_MD)
    assert "target_length" in body, (
        "memo-draft.md MUST document reading target_length from .anvil.json "
        "(issue #121 AC3)"
    )


def test_memo_draft_specifies_soft_target_prompt_wording():
    body = _read(DRAFT_MD)
    # AC3: exact prompt wording is specified so reviser behaviour is reproducible.
    assert "Target length:" in body, (
        "memo-draft.md MUST specify the exact 'Target length:' prompt wording"
    )


def test_memo_draft_documents_pages_conversion():
    body = _read(DRAFT_MD)
    assert "600" in body, (
        "memo-draft.md MUST document the 600 words/page conversion when "
        "normalizing pages -> words"
    )


# ---------------------------------------------------------------------------
# memo-revise.md — reviser reads target_length and surfaces in plan
# ---------------------------------------------------------------------------


def test_memo_revise_reads_target_length():
    body = _read(REVISE_MD)
    assert "target_length" in body, (
        "memo-revise.md MUST document reading target_length (issue #121 AC3)"
    )


def test_memo_revise_specifies_soft_target_prompt_wording():
    body = _read(REVISE_MD)
    # AC3: exact wording for reviser too.
    assert "Target length:" in body, (
        "memo-revise.md MUST specify the exact 'Target length:' prompt wording"
    )


# ---------------------------------------------------------------------------
# memo-review.md — dim 7 length comparison logic
# ---------------------------------------------------------------------------


def test_memo_review_reads_target_length():
    body = _read(REVIEW_MD)
    assert "target_length" in body, (
        "memo-review.md MUST document reading target_length (issue #121 AC4)"
    )


def test_memo_review_documents_dim7_comparison_logic():
    body = _read(REVIEW_MD)
    # AC4: dim 7 must compute word count and compare against declared range.
    assert "word count" in body.lower(), (
        "memo-review.md MUST document computing the memo word count for dim 7"
    )
    # Justification format requirement: BOTH declared target AND actual count.
    assert "declared" in body.lower() and "actual" in body.lower(), (
        "memo-review.md MUST require recording both declared target and actual "
        "count in the dim 7 justification"
    )


def test_memo_review_documents_meaningful_deviation_threshold():
    body = _read(REVIEW_MD)
    # AC4: only flag on meaningful deviation, not modest deviation.
    assert "deviation" in body.lower(), (
        "memo-review.md MUST document the 'meaningful deviation' calibration "
        "for dim 7 length comparison"
    )


# ---------------------------------------------------------------------------
# rubric.md — dim 7 row updated; comparison logic documented
# ---------------------------------------------------------------------------


def test_rubric_dim7_row_mentions_declared_target():
    body = _read(RUBRIC_MD)
    # AC5: dim 7 row prose reflects declared-target semantics.
    assert "target_length" in body, (
        "rubric.md MUST mention target_length in the dim 7 row (issue #121 AC5)"
    )


def test_rubric_dim7_preserves_implicit_default_fallback():
    body = _read(RUBRIC_MD)
    # AC5: the implicit-default fallback prose must be preserved.
    assert "reasonable for the decision" in body, (
        "rubric.md MUST preserve the implicit-default fallback prose in dim 7"
    )


def test_rubric_has_length_targets_subsection():
    body = _read(RUBRIC_MD)
    assert "Length targets" in body, (
        "rubric.md MUST contain a 'Length targets' subsection clarifying "
        "the comparison logic and the 600-words/page conversion"
    )


def test_rubric_documents_600_words_per_page_in_length_section():
    body = _read(RUBRIC_MD)
    # The length-targets section must document the conversion ratio.
    assert "600" in body, (
        "rubric.md MUST document the 600 words/page conversion ratio in "
        "the Length targets subsection"
    )
