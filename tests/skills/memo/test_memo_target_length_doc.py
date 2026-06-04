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
    # Both spec forms must be documented as accepted. Post-#296 the BRIEF.md
    # surface uses YAML (`words:` and `pages:` unquoted) rather than the
    # historical JSON (`"words"` / `"pages"`); accept either form.
    assert '"words"' in body or "`words`" in body or "words:" in body, (
        "SKILL.md MUST show the words spec form"
    )
    assert '"pages"' in body or "`pages`" in body or "pages:" in body or "pages: [" in body, (
        "SKILL.md MUST show the pages spec form (accepted, converted internally)"
    )


def test_skill_md_documents_backward_compatibility():
    body = _read(SKILL_MD)
    # Backward-compat is AC6 — absence of target_length must behave as today.
    # Post-#296 the BRIEF parser is strict on schema (the absence path remains
    # tolerated — no target_length on a documents: entry yields no target —
    # but malformed shapes raise). Accept either the prior "backward
    # compatibility" framing or the new "absent → no target" prose.
    lower = body.lower()
    assert (
        "backward compatibility" in lower
        or "backward compatible" in lower
        or "absent the skill behaves" in lower
        or "no target" in lower
    )


def test_skill_md_documents_resolution_order_for_per_version_overrides():
    """Per issue #145 AC1 + AC2 — the deferred prose flipped.

    SKILL.md previously asserted "per-version overrides are intentionally not
    supported in v0" (PR #122 placeholder). Issue #145 ships the per-version
    overrides; this test guards that the deferred-prose is gone AND the
    resolution-order prose is present in its place.
    """
    body = _read(SKILL_MD)
    # The deferred-to-v0 prose MUST be gone.
    assert "intentionally not supported in v0" not in body, (
        "SKILL.md MUST NOT still defer per-version overrides — issue #145 "
        "ships them. Replace the deferred-prose paragraph with the "
        "resolution-order documentation."
    )
    assert "ship as a separate follow-on issue" not in body, (
        "SKILL.md MUST NOT still reference 'follow-on issue' for per-version "
        "overrides — issue #145 IS that follow-on."
    )
    # The new resolution-order prose MUST be present.
    assert "overrides" in body, (
        "SKILL.md MUST document the target_length.overrides block (issue #145 AC1)"
    )
    assert "Resolution order" in body or "resolution order" in body, (
        "SKILL.md MUST document the resolution order for per-version overrides "
        "(issue #145 AC2)"
    )


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


# ---------------------------------------------------------------------------
# Issue #145 — per-version overrides schema, resolution order, provenance
# ---------------------------------------------------------------------------


def test_skill_md_documents_default_and_overrides_keys():
    """AC1: target_length + target_length_overrides surfaces are documented.

    Post-#296 the BRIEF.md schema uses a per-doc ``target_length`` as the
    document-level default and a separate ``target_length_overrides`` map
    (keyed by version-number string: ``"1"``, ``"2"``, …) for per-version
    overrides. The historical extended shape (``target_length.default`` /
    ``target_length.overrides.v{N}``) has been replaced.
    """
    body = _read(SKILL_MD)
    # The per-doc target_length must still be documented.
    assert "target_length" in body, (
        "SKILL.md MUST document the per-doc target_length key (issue #145 AC1)"
    )
    # The per-version override surface must be documented (BRIEF-side shape).
    assert "target_length_overrides" in body, (
        "SKILL.md MUST document the target_length_overrides per-version map "
        "(issue #296 — replaces the prior target_length.overrides.v{N} shape)"
    )


def test_skill_md_documents_legacy_flat_shape_backward_compat():
    """The per-doc ``target_length`` (formerly "flat shape") still works.

    Post-#296 the flat per-doc ``target_length`` (a single ``words`` or
    ``pages`` range) is the document-level default; per-version overrides
    live on the sibling ``target_length_overrides`` map. The historical
    "legacy_flat" source label is retired.
    """
    body = _read(SKILL_MD)
    # The per-doc default range must be documented.
    lower = body.lower()
    assert (
        "default range" in lower
        or "per-doc target_length" in lower.replace("`", "")
        or "per-doc default" in lower
    ), (
        "SKILL.md MUST document the per-doc target_length as the document-"
        "level default range (issue #296 consolidation)"
    )


def test_skill_md_documents_resolution_order():
    """Resolution order target_length_overrides[<N>] -> target_length -> none."""
    body = _read(SKILL_MD)
    # The resolution order documentation must mention the per-version
    # override branch (BRIEF-side shape uses `overrides.<N>` after the #296
    # consolidation — no `v` prefix).
    assert "overrides." in body or "target_length_overrides" in body, (
        "SKILL.md MUST document the per-version overrides branch of the "
        "resolution order (issue #296)"
    )
    # The fallback chain must be visible.
    lower = body.lower()
    assert "target_length" in lower and "overrides" in lower, (
        "SKILL.md MUST document both target_length default and overrides "
        "branches of the resolution order"
    )


def test_skill_md_documents_both_shapes_malformed_fallback():
    """AC8: both flat AND extended keys present → malformed, no target."""
    body = _read(SKILL_MD)
    # The both-shapes-set malformed case must be called out explicitly.
    assert "both flat" in body.lower() or "both shapes" in body.lower() or (
        "extended" in body.lower() and "flat" in body.lower() and "malformed" in body.lower()
    ), (
        "SKILL.md MUST document that a target_length with both flat and "
        "extended keys is malformed (issue #145 AC8; mirrors PR #122's "
        "both-words-and-pages-set fallback)"
    )


def test_skill_md_documents_target_length_resolved_provenance():
    """AC3/AC4/AC5: the _progress.json.metadata.target_length_resolved field."""
    body = _read(SKILL_MD)
    assert "target_length_resolved" in body, (
        "SKILL.md MUST document the _progress.json.metadata.target_length_resolved "
        "field that drafter/reviser write and reviewer reads (issue #145 AC3-5)"
    )
    # The source provenance values must be documented.
    assert "source" in body, (
        "SKILL.md MUST document the 'source' provenance field"
    )


# ---------------------------------------------------------------------------
# memo-draft.md — drafter writes target_length_resolved with provenance
# ---------------------------------------------------------------------------


def test_memo_draft_documents_resolution_for_v_n_plus_1():
    """AC3: drafter resolves against the version it is about to produce."""
    body = _read(DRAFT_MD)
    # The resolution must use N+1 (the version being produced).
    assert "N+1" in body, (
        "memo-draft.md MUST document resolving target_length against N+1 "
        "(the version about to be produced) — issue #145 AC3"
    )
    assert "overrides" in body, (
        "memo-draft.md MUST document reading target_length.overrides "
        "(issue #145 AC3)"
    )


def test_memo_draft_writes_target_length_resolved_to_progress():
    """AC3: drafter writes the resolved target + source to _progress.json.

    Post-#296 the source-value set is collapsed to three values:
    ``"overrides.<N>"``, ``"default"``, ``"none"``. The historical
    ``"legacy_flat"`` source label (for the pre-#145 flat-only shape)
    is retired along with the ``.anvil.json`` shape it served.
    """
    body = _read(DRAFT_MD)
    assert "target_length_resolved" in body, (
        "memo-draft.md MUST document writing metadata.target_length_resolved "
        "to _progress.json with source provenance (issue #145 AC3)"
    )
    # The current source values must be documented.
    for source in ('"overrides.', '"default"', '"none"'):
        assert source in body, (
            f"memo-draft.md MUST document the {source!r} source value for "
            "metadata.target_length_resolved (issue #296 — three-value set)"
        )


# ---------------------------------------------------------------------------
# memo-revise.md — reviser writes target_length_resolved with provenance
# ---------------------------------------------------------------------------


def test_memo_revise_documents_resolution_for_v_n_plus_1():
    """AC4: reviser resolves against the version it is about to produce."""
    body = _read(REVISE_MD)
    assert "N+1" in body, (
        "memo-revise.md MUST document resolving target_length against N+1 "
        "(the version about to be produced) — issue #145 AC4"
    )
    assert "overrides" in body, (
        "memo-revise.md MUST document reading target_length.overrides "
        "(issue #145 AC4)"
    )


def test_memo_revise_writes_target_length_resolved_to_progress():
    """AC4: reviser writes the resolved target + source to _progress.json.

    Post-#296 the source-value set is three values: ``"overrides.<N>"``,
    ``"default"``, ``"none"``. The historical ``"legacy_flat"`` source
    label is retired.
    """
    body = _read(REVISE_MD)
    assert "target_length_resolved" in body, (
        "memo-revise.md MUST document writing metadata.target_length_resolved "
        "to _progress.json with source provenance (issue #145 AC4)"
    )
    for source in ('"overrides.', '"default"', '"none"'):
        assert source in body, (
            f"memo-revise.md MUST document the {source!r} source value for "
            "metadata.target_length_resolved (issue #296 — three-value set)"
        )


# ---------------------------------------------------------------------------
# memo-review.md — reviewer reads target_length_resolved (no re-resolution)
# ---------------------------------------------------------------------------


def test_memo_review_reads_target_length_resolved_from_progress():
    """AC5: reviewer prefers reading the resolved field over re-resolving."""
    body = _read(REVIEW_MD)
    assert "target_length_resolved" in body, (
        "memo-review.md MUST document reading metadata.target_length_resolved "
        "from the version-dir _progress.json (issue #145 AC5)"
    )
    # The "prevent drift" reasoning is load-bearing.
    assert "drift" in body.lower(), (
        "memo-review.md MUST explain that reading the resolved field "
        "(rather than re-resolving) prevents drift between drafter/reviser "
        "and reviewer (issue #145 AC5)"
    )


def test_memo_review_documents_provenance_in_dim7_justification():
    """AC5: dim 7 justification appends source provenance when override fired.

    Post-#296 the override source is ``overrides.<N>`` (no ``v`` prefix —
    BRIEF.md uses bare-integer-string keys per the YAML-natural shape).
    """
    body = _read(REVIEW_MD)
    # The provenance parenthetical for override sources must be shown.
    assert "from overrides." in body, (
        "memo-review.md MUST document the 'from overrides.<N>' provenance "
        "format in dim 7 justifications (issue #145 AC5 + #296)"
    )


# ---------------------------------------------------------------------------
# rubric.md — dim 7 resolution-order prose replaces deferred-follow-on prose
# ---------------------------------------------------------------------------


def test_rubric_documents_resolution_order_for_overrides():
    """AC6: rubric.md replaces the 'planned follow-on' prose with resolution-order docs."""
    body = _read(RUBRIC_MD)
    # The deferred prose must be gone.
    assert "per-version overrides are a planned follow-on" not in body, (
        "rubric.md MUST NOT still defer per-version overrides — issue #145 "
        "ships them. Replace the deferred-prose with the resolution-order "
        "documentation."
    )
    # The new prose must mention overrides (post-#296: BRIEF.md surface).
    assert "overrides" in body, (
        "rubric.md MUST document the per-version overrides resolution branch "
        "(issue #145 AC6)"
    )


def test_rubric_documents_provenance_in_dim7_justification():
    """AC6: dim 7 justification format documents the override-provenance parenthetical.

    Post-#296 the source label is ``overrides.<N>`` (no ``v`` prefix).
    """
    body = _read(RUBRIC_MD)
    assert "from overrides." in body, (
        "rubric.md MUST document the 'from overrides.<N>' provenance "
        "parenthetical in the dim 7 justification format (issue #145 AC6 + #296)"
    )
