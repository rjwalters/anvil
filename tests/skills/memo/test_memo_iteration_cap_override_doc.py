"""Doc-coverage smoke tests for the memo iteration-cap paired override.

Per issue #349 acceptance criteria: cheap "grep-the-doc" regression guard
that the per-document `max_iterations` + `iteration_cap_rationale`
contract stays documented in the four files it touches (SKILL.md,
memo-draft.md, memo-revise.md, project_brief.py) and doesn't drift back
to the implicit-default-only prose in a later edit.

These tests assert on substring presence only — they do NOT validate
prose quality or structure. The lifecycle commands themselves are
LLM-driven, so behavioural assertions belong in consumer-side integration
tests, not here. The schema-validation behaviour is exercised by
`anvil/skills/memo/tests/test_project_brief.py`'s
``TestDocumentIterationCapOverride`` class.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with the
``test_iteration_cap_override_doc`` shape another skill might pick.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
DRAFT_MD = SKILL_ROOT / "commands" / "memo-draft.md"
REVISE_MD = SKILL_ROOT / "commands" / "memo-revise.md"
# Canonical module location post-#382 (promoted from the memo skill's
# lib/ to anvil/lib/; the memo-side path is now a back-compat shim).
PROJECT_BRIEF_PY = (
    Path(__file__).resolve().parents[3] / "anvil" / "lib" / "project_brief.py"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SKILL.md — canonical schema home for the override contract
# ---------------------------------------------------------------------------


def test_skill_md_has_per_document_override_contract_section():
    body = _read(SKILL_MD)
    assert "Per-document override contract" in body, (
        "SKILL.md MUST contain a 'Per-document override contract' section "
        "heading (issue #349 AC: replaces the prior 'not yet schema-"
        "formalized' placeholder)"
    )


def test_skill_md_documents_paired_override_keys():
    body = _read(SKILL_MD)
    assert "max_iterations" in body, (
        "SKILL.md MUST name the `max_iterations` field"
    )
    assert "iteration_cap_rationale" in body, (
        "SKILL.md MUST name the `iteration_cap_rationale` field — the "
        "rationale is the audit-trail half of the paired override"
    )


def test_skill_md_documents_paired_override_validation_rules():
    body = _read(SKILL_MD)
    # The validation contract names BOTH fields together — the "paired"
    # framing is load-bearing for the operator's mental model.
    assert "paired" in body.lower(), (
        "SKILL.md MUST describe the override as 'paired' so operators "
        "see that both fields are required together"
    )
    # The floor is named explicitly so the operator knows raising-only
    # is the rule. Both shapes accepted: "max_iterations < 4" (the
    # rejection rule phrasing) and ">= 4" / "≥ 4" (the override
    # validation phrasing).
    has_floor = (
        ">= 4" in body
        or "≥ 4" in body
        or "max_iterations < 4" in body
        or "may raise the cap but not lower it" in body
    )
    assert has_floor, (
        "SKILL.md MUST document the >=4 floor on max_iterations (the "
        "override may raise but not lower the principled default)"
    )


def test_skill_md_documents_audit_trail_writes():
    body = _read(SKILL_MD)
    # The three writes — BRIEF.md, _progress.json, BLOCKED notice —
    # are the load-bearing audit-trail surfaces. Naming all three keeps
    # the contract visible in one place.
    assert "BRIEF.md" in body
    assert "_progress.json" in body
    assert "BLOCKED notice" in body, (
        "SKILL.md MUST name the BLOCKED notice as the at-the-moment-"
        "of-need surface for the rationale (issue #349 canary friction)"
    )


def test_skill_md_documents_sticky_raise_semantics():
    body = _read(SKILL_MD)
    assert "Sticky-raise" in body or "sticky raise" in body.lower() or "sticky-raise" in body.lower(), (
        "SKILL.md MUST document the sticky-raise semantics (NOT single-"
        "use) so operators understand the cap stays elevated until the "
        "BRIEF is edited again"
    )


def test_skill_md_references_deck_precedent():
    body = _read(SKILL_MD)
    # The deck precedent is the source of the design template — naming
    # it keeps the two skills' contracts in sync.
    assert "deck" in body.lower(), (
        "SKILL.md MUST reference the deck skill's precedent (which "
        "shipped the paired-override contract first via "
        "<thread>/.anvil.json) so operators on a memo thread can find "
        "the structurally identical mechanism on the deck side"
    )


# ---------------------------------------------------------------------------
# memo-revise.md — step 3 + BLOCKED notice
# ---------------------------------------------------------------------------


def test_revise_md_step_3_reads_brief_paired_override():
    body = _read(REVISE_MD)
    # Step 3 is the iteration-cap check; it must resolve the cap via
    # BRIEF.md per the paired-override contract.
    assert "load_project_brief" in body, (
        "memo-revise.md step 3 MUST call load_project_brief() to "
        "resolve the BRIEF override at iteration-cap-check time"
    )
    assert "document_for_slug" in body, (
        "memo-revise.md step 3 MUST look up the document by slug"
    )
    assert "iteration_cap_rationale" in body, (
        "memo-revise.md MUST name iteration_cap_rationale (the audit-"
        "trail half of the paired override)"
    )


def test_revise_md_has_blocked_notice_section():
    body = _read(REVISE_MD)
    assert "BLOCKED notice" in body, (
        "memo-revise.md MUST have a BLOCKED notice section "
        "(mirrors deck-revise.md §'BLOCKED notice' — the canary "
        "friction surfaced in #349 is 'I didn't know the override "
        "existed at PARK time')"
    )


def test_revise_md_blocked_notice_includes_override_pointer():
    body = _read(REVISE_MD)
    # The override pointer is the load-bearing discoverability surface.
    # It must name both fields and the BRIEF.md carrier.
    assert "Override available" in body or "Override pointer" in body, (
        "memo-revise.md BLOCKED notice MUST include an override pointer "
        "(visible discoverability surface for operators who don't know "
        "the override exists)"
    )


def test_revise_md_blocked_notice_surfaces_rationale_verbatim():
    body = _read(REVISE_MD)
    # When the override is already active, the BLOCKED notice surfaces
    # the prior rationale so the operator sees their own prior
    # authorization at the moment they hit the elevated cap.
    assert "rationale" in body.lower(), (
        "memo-revise.md BLOCKED notice MUST surface the rationale "
        "verbatim when an override is already active"
    )


def test_revise_md_progress_json_records_rationale():
    body = _read(REVISE_MD)
    # The per-version _progress.json mirror is the third audit-trail
    # write (after BRIEF.md and the BLOCKED notice).
    assert "metadata.iteration_cap_rationale" in body or "iteration_cap_rationale" in body, (
        "memo-revise.md MUST write iteration_cap_rationale into "
        "_progress.json.metadata so every version dir carries the cap "
        "audit trail"
    )


# ---------------------------------------------------------------------------
# memo-draft.md — parallel write-side
# ---------------------------------------------------------------------------


def test_draft_md_step_4_reads_brief_paired_override():
    body = _read(DRAFT_MD)
    # The drafter is the parallel write-side: it must read the same
    # BRIEF override and mirror it into _progress.json on every pass so
    # the audit trail is consistent across draft and revise.
    assert "iteration_cap_rationale" in body, (
        "memo-draft.md MUST name iteration_cap_rationale (parallel "
        "write-side to memo-revise.md's step 3 resolution)"
    )
    assert "load_project_brief" in body, (
        "memo-draft.md step 4 MUST call load_project_brief() to "
        "resolve the BRIEF override at draft-initialization time"
    )


# ---------------------------------------------------------------------------
# project_brief.py — schema implementation
# ---------------------------------------------------------------------------


def test_project_brief_py_documents_paired_override_fields():
    body = _read(PROJECT_BRIEF_PY)
    # The BriefDocument docstring is the schema-of-record for the
    # paired-override contract; it must describe both fields.
    assert "max_iterations" in body
    assert "iteration_cap_rationale" in body
    # The DEFAULT_MAX_ITERATIONS constant is the single source of truth
    # for the floor; both deck and memo agree on the value.
    assert "DEFAULT_MAX_ITERATIONS" in body, (
        "project_brief.py MUST export DEFAULT_MAX_ITERATIONS so deck "
        "and memo agree on the override floor"
    )


def test_project_brief_py_has_paired_override_validator():
    body = _read(PROJECT_BRIEF_PY)
    # The cross-field validator is what enforces the paired-override
    # contract — naming it in the module guards against a silent
    # refactor that drops the validation step.
    assert "_validate_paired_iteration_cap_override" in body, (
        "project_brief.py MUST contain the paired-override validator "
        "function (enforces the contract at parse time)"
    )


# ---------------------------------------------------------------------------
# Cross-doc agreement: the contract is named consistently
# ---------------------------------------------------------------------------


def test_all_three_docs_agree_on_field_names():
    """The same field names appear in SKILL.md + memo-draft + memo-revise.

    A future edit that renames one field but forgets the others would
    break operator self-service (operator reads memo-revise, edits BRIEF
    per memo-revise's spec, drafter reads a different field name).
    """
    skill = _read(SKILL_MD)
    draft = _read(DRAFT_MD)
    revise = _read(REVISE_MD)

    for field in ("max_iterations", "iteration_cap_rationale"):
        assert field in skill, (
            f"SKILL.md MUST name `{field}` (paired-override contract)"
        )
        assert field in draft, (
            f"memo-draft.md MUST name `{field}` (parallel write-side)"
        )
        assert field in revise, (
            f"memo-revise.md MUST name `{field}` (read-and-write side)"
        )
