"""Doc-coverage smoke tests for the deck ``iteration_cap_rationale`` field.

Per issue #129 acceptance criteria: cheap "grep-the-doc" regression guard
that the paired-override contract (``max_iterations`` + REQUIRED
``iteration_cap_rationale``) stays documented across the five files it
touches (SKILL.md, three command docs, the orchestrator) and doesn't
drift back to the bare-override prose in a later edit.

The canary friction (#129) was twofold:
  1. The bare ``max_iterations`` override silently degraded to "set a
     bigger number and forget" — no audit trail of *why* this thread
     deserves more passes.
  2. The override was poorly discoverable at PARK time — the BLOCKED
     notice didn't tell the operator the override existed.

These tests assert on substring presence only — they do NOT validate
prose quality or the LLM-driven runtime semantics. Behavioural assertions
belong in consumer-side integration tests.

Per-skill test filename convention (#58): file is named with a
``test_deck_`` prefix so it never collides with a parallel-skill test
of the same shape.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "deck"
SKILL_MD = SKILL_ROOT / "SKILL.md"
BRIEF_MD = SKILL_ROOT / "commands" / "deck-brief.md"
DRAFT_MD = SKILL_ROOT / "commands" / "deck-draft.md"
REVISE_MD = SKILL_ROOT / "commands" / "deck-revise.md"
DECK_MD = SKILL_ROOT / "commands" / "deck.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SKILL.md — canonical schema home (issue #129 AC1, AC2)
# ---------------------------------------------------------------------------


def test_skill_md_documents_iteration_cap_rationale_field():
    body = _read(SKILL_MD)
    assert "iteration_cap_rationale" in body, (
        "SKILL.md MUST document the iteration_cap_rationale field "
        "(issue #129 AC1)"
    )


def test_skill_md_documents_required_when_set_contract():
    body = _read(SKILL_MD)
    # The rationale is REQUIRED when max_iterations is set; without it
    # the override silently degrades to default.
    assert "required" in body.lower(), (
        "SKILL.md MUST document that iteration_cap_rationale is REQUIRED "
        "when max_iterations is set (issue #129 AC1)"
    )


def test_skill_md_documents_malformed_fallback_to_default():
    body = _read(SKILL_MD)
    # AC1: malformed (no rationale) → fall back to default 4.
    assert "fall back" in body.lower() or "fallback" in body.lower(), (
        "SKILL.md MUST document the malformed-override → fall-back-to-default "
        "contract (issue #129 AC1)"
    )
    # Default cap of 4 must be named in the fallback context.
    assert "default" in body.lower() and "4" in body, (
        "SKILL.md MUST name the default cap of 4 as the fallback target"
    )


def test_skill_md_documents_sanity_floor():
    body = _read(SKILL_MD)
    # The override may not LOWER the cap below 4 — that's the sanity floor.
    assert "max_iterations < 4" in body or "below" in body.lower() or "lower" in body.lower(), (
        "SKILL.md MUST document the >=4 sanity floor on the override"
    )


def test_skill_md_documents_graceful_degradation_precedent():
    body = _read(SKILL_MD)
    # AC1 / AC8: parse errors are tolerated, never fatal — mirrors
    # _read_anvil_json precedent.
    assert "_read_anvil_json" in body or "graceful" in body.lower(), (
        "SKILL.md MUST reference the _read_anvil_json graceful-degradation "
        "precedent (issue #129)"
    )


def test_skill_md_defers_per_version_overrides():
    body = _read(SKILL_MD)
    # AC: per-version overrides explicitly deferred to a follow-on.
    assert "per-version" in body.lower() or "Per-version" in body
    assert "v0" in body.lower() or "deferred" in body.lower() or "follow-on" in body, (
        "SKILL.md MUST document that per-version overrides are deferred in v0"
    )


def test_skill_md_progress_json_snippet_includes_rationale():
    body = _read(SKILL_MD)
    # AC2: the _progress.json snippet shows iteration_cap_rationale as a
    # metadata field carried into each version dir.
    assert '"iteration_cap_rationale"' in body, (
        "SKILL.md _progress.json snippet MUST include iteration_cap_rationale "
        "(issue #129 AC2)"
    )


# ---------------------------------------------------------------------------
# deck-brief.md — consumer override block (issue #129 AC3)
# ---------------------------------------------------------------------------


def test_brief_md_documents_paired_override():
    body = _read(BRIEF_MD)
    assert "iteration_cap_rationale" in body, (
        "deck-brief.md MUST document the iteration_cap_rationale field "
        "alongside max_iterations (issue #129 AC3)"
    )


def test_brief_md_progress_json_snippet_includes_rationale():
    body = _read(BRIEF_MD)
    assert '"iteration_cap_rationale"' in body, (
        "deck-brief.md _progress.json snippet MUST include "
        "iteration_cap_rationale"
    )


# ---------------------------------------------------------------------------
# deck-draft.md — _progress.json init carries rationale (issue #129 AC4)
# ---------------------------------------------------------------------------


def test_draft_md_reads_iteration_cap_rationale():
    body = _read(DRAFT_MD)
    assert "iteration_cap_rationale" in body, (
        "deck-draft.md MUST document reading iteration_cap_rationale from "
        ".anvil.json into _progress.json.metadata (issue #129 AC4)"
    )


def test_draft_md_documents_paired_validation():
    body = _read(DRAFT_MD)
    # AC4: paired validation — both keys required when overriding.
    assert ".anvil.json" in body, (
        "deck-draft.md MUST reference .anvil.json as the override config home"
    )
    # The drafter MUST surface the fallback warning when the override is
    # malformed.
    assert "warning" in body.lower(), (
        "deck-draft.md MUST surface a warning when the override is malformed "
        "and falls back to default"
    )


def test_draft_md_progress_json_snippet_includes_rationale():
    body = _read(DRAFT_MD)
    assert '"iteration_cap_rationale"' in body, (
        "deck-draft.md _progress.json snippet MUST include "
        "iteration_cap_rationale"
    )


# ---------------------------------------------------------------------------
# deck-revise.md — iteration cap check + BLOCKED notice (issue #129 AC5, AC6)
# ---------------------------------------------------------------------------


def test_revise_md_validates_paired_override():
    body = _read(REVISE_MD)
    assert "iteration_cap_rationale" in body, (
        "deck-revise.md MUST validate the iteration_cap_rationale pair in "
        "the iteration cap check (issue #129 AC5)"
    )


def test_revise_md_documents_fallback_to_default_on_malformed():
    body = _read(REVISE_MD)
    # AC5: present-and-valid → use it; malformed → fall back to default 4.
    assert "fall back" in body.lower() or "fallback" in body.lower(), (
        "deck-revise.md MUST document the fall-back-to-default behaviour "
        "on a malformed override"
    )


def test_revise_md_blocked_notice_has_override_pointer():
    body = _read(REVISE_MD)
    # AC6: BLOCKED notice includes a one-line pointer to the override
    # mechanism so operators discover it at the moment they need it.
    assert "BLOCKED notice" in body or "BLOCKED" in body, (
        "deck-revise.md MUST contain a BLOCKED notice contract (issue #129 AC6)"
    )
    # The pointer must surface the override-available-here breadcrumb.
    assert "Override available" in body or "override" in body.lower(), (
        "deck-revise.md BLOCKED notice MUST include a discoverability "
        "pointer to the override mechanism"
    )


def test_revise_md_blocked_notice_references_skill_md_state_machine():
    body = _read(REVISE_MD)
    # The pointer should direct the operator to the canonical
    # contract documentation in SKILL.md.
    assert "SKILL.md" in body, (
        "deck-revise.md BLOCKED notice MUST point to SKILL.md for the "
        "override contract details"
    )


def test_revise_md_progress_json_snippet_includes_rationale():
    body = _read(REVISE_MD)
    assert '"iteration_cap_rationale"' in body, (
        "deck-revise.md _progress.json snippet MUST include "
        "iteration_cap_rationale"
    )


# ---------------------------------------------------------------------------
# deck.md (orchestrator) — portfolio view surfaces rationale (issue #129 AC7)
# ---------------------------------------------------------------------------


def test_orchestrator_displays_iteration_cap_rationale():
    body = _read(DECK_MD)
    assert "iteration_cap_rationale" in body, (
        "deck.md (orchestrator) MUST surface iteration_cap_rationale in "
        "the portfolio view (issue #129 AC7)"
    )


def test_orchestrator_documents_truncation():
    body = _read(DECK_MD)
    # AC7: rationale truncated to ~80 chars when long.
    assert "truncat" in body.lower() or "80" in body, (
        "deck.md MUST document truncation of the rationale for the table "
        "display (issue #129 AC7)"
    )


def test_orchestrator_documents_blocked_discoverability_pointer():
    body = _read(DECK_MD)
    # Portfolio orchestrator should surface the override pointer for
    # BLOCKED threads so the operator learns about it from the portfolio
    # view too, not only when running deck-revise directly.
    assert "BLOCKED" in body, (
        "deck.md MUST mention BLOCKED state in the operator notes context"
    )
