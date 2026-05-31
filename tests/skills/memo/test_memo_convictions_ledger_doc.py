"""Doc-coverage smoke tests for the memo ``_convictions.md`` advisory contract.

Per issue #147 (Epic #142 / Phase A) acceptance criteria: cheap
"grep-the-doc" regression guard that the narrow conclusions-ledger primitive
stays documented in the files it touches (SKILL.md, memo-revise.md,
BRIEF.migration.md.example) and that the documents cross-reference each
other coherently — especially the body-anchor requirement and the
"advisory: not scored, not gating, no state-machine impact" framing that
are the architect's risk mitigations against scope creep.

These tests assert on substring presence only — they do NOT validate prose
quality or structure. The reviser command itself is LLM-driven, so
behavioural assertions belong in consumer-side integration tests, not here.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with a similarly-shaped
``test_convictions_ledger_doc`` another skill might pick up if/when Phase C
extends the contract beyond memo (see Epic #142 staging).

Phase B kill switch reminder: if the canary does not consume
``_convictions.md`` within 2-4 weeks of merge, this file and the four
source-doc additions it guards are removed entirely per the PR #40 / PR #72
negative-result precedent. The tests stay with the contract — when the
contract goes, this file goes.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
REVISE_MD = SKILL_ROOT / "commands" / "memo-revise.md"
BRIEF_MIGRATION = SKILL_ROOT / "templates" / "BRIEF.migration.md.example"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SKILL.md — canonical contract home (§Convictions ledger)
# ---------------------------------------------------------------------------


def test_skill_md_documents_convictions_file():
    body = _read(SKILL_MD)
    assert "_convictions.md" in body, (
        "SKILL.md MUST document the _convictions.md file (issue #147 / Epic #142 Phase A)"
    )


def test_skill_md_has_convictions_ledger_section():
    body = _read(SKILL_MD)
    assert "Convictions ledger" in body, (
        "SKILL.md MUST contain a 'Convictions ledger' section under §Artifact contract"
    )


def test_skill_md_documents_body_anchor_requirement():
    body = _read(SKILL_MD)
    # The body-anchor requirement is the architect's load-bearing risk
    # mitigation; it must appear explicitly in the contract section.
    assert "body-anchor" in body.lower() or "body anchor" in body.lower(), (
        "SKILL.md MUST document the body-anchor requirement (each conviction "
        "names a section/paragraph in current memo.md) — this is the "
        "architect's load-bearing safeguard against ledger drift"
    )


def test_skill_md_documents_advisory_only_framing():
    body = _read(SKILL_MD)
    # The "not scored, not gating, no state-machine impact" phrasing is the
    # explicit architect contract; it must appear verbatim or near-verbatim.
    lowered = body.lower()
    assert "not scored" in lowered, (
        "SKILL.md MUST state '_convictions.md' is not scored (advisory contract)"
    )
    assert "not gating" in lowered, (
        "SKILL.md MUST state '_convictions.md' is not gating (advisory contract)"
    )
    assert "state-machine" in lowered or "state machine" in lowered, (
        "SKILL.md MUST state '_convictions.md' has no state-machine impact"
    )


def test_skill_md_names_writer_and_reader():
    body = _read(SKILL_MD)
    # The contract names a single writer (memo-revise) and single reader
    # (next memo-revise). This is the falsifiability anchor for Phase B.
    assert "memo-revise" in body, (
        "SKILL.md MUST name memo-revise as the sole writer/reader of "
        "_convictions.md (single named consumer per architect proposal)"
    )


def test_skill_md_documents_phase_b_kill_switch():
    body = _read(SKILL_MD)
    # The kill-switch ("if not consumed in 2-4 weeks, remove") must be
    # visible in SKILL.md so future maintainers see it without having to
    # crawl WORK_LOG.md.
    lowered = body.lower()
    assert "kill switch" in lowered or "kill-switch" in lowered, (
        "SKILL.md MUST document the Phase B kill switch in the Convictions "
        "ledger section"
    )
    assert "2" in body and ("4 weeks" in body or "4-week" in body or "weeks" in body), (
        "SKILL.md MUST document the 2-4 week canary-observation window"
    )


# ---------------------------------------------------------------------------
# memo-revise.md — write step (after changelog) + read step (before re-litigation)
# ---------------------------------------------------------------------------


def test_memo_revise_documents_convictions_file():
    body = _read(REVISE_MD)
    assert "_convictions.md" in body, (
        "memo-revise.md MUST reference _convictions.md (issue #147 Phase A)"
    )


def test_memo_revise_has_read_step_before_relitigation():
    body = _read(REVISE_MD)
    # The read step happens BEFORE the body-production step; the architect
    # contract says "before re-litigating settled issues". The simplest
    # grep-the-doc guard: the file is mentioned in a step before step 8
    # (Produce memo.md). We assert on the explicit "re-litigat" stem so
    # rewordings stay caught.
    lowered = body.lower()
    assert "re-litigat" in lowered or "relitigat" in lowered, (
        "memo-revise.md MUST document a read step framed as 'before "
        "re-litigating settled issues' (issue #147 AC)"
    )


def test_memo_revise_has_write_step_after_changelog():
    body = _read(REVISE_MD)
    # The write step lives in the procedure AFTER the changelog step. The
    # cheap grep-the-doc check: the _convictions.md reference appears in
    # the body somewhere after the changelog.md step.
    changelog_pos = body.find("changelog.md")
    convictions_pos = body.find("_convictions.md")
    assert changelog_pos > -1 and convictions_pos > -1, (
        "memo-revise.md MUST reference both changelog.md and _convictions.md"
    )
    assert convictions_pos > changelog_pos, (
        "memo-revise.md MUST write _convictions.md AFTER the changelog step "
        "(issue #147 AC; architect proposal #142 procedure ordering)"
    )


def test_memo_revise_documents_body_anchor_requirement():
    body = _read(REVISE_MD)
    # Body-anchor requirement also appears in memo-revise.md so the writer
    # sees it without having to flip back to SKILL.md.
    assert "anchor" in body.lower(), (
        "memo-revise.md MUST document the body-anchor requirement at the "
        "write step (each conviction names a section/paragraph in current memo.md)"
    )


def test_memo_revise_cross_references_skill_md():
    body = _read(REVISE_MD)
    # Coherence check: the contract section in SKILL.md is the canonical
    # home; memo-revise.md should point readers at it for the full contract.
    assert "Convictions ledger" in body or "SKILL.md" in body, (
        "memo-revise.md MUST cross-reference SKILL.md §Convictions ledger "
        "as the canonical contract home"
    )


def test_memo_revise_documents_advisory_framing():
    body = _read(REVISE_MD)
    # The "advisory only" framing appears at the write step so the writer
    # is reminded the file is not scored/gating before producing it.
    lowered = body.lower()
    assert "advisory" in lowered or "not scored" in lowered, (
        "memo-revise.md MUST surface the advisory-only framing at the "
        "write step"
    )


# ---------------------------------------------------------------------------
# BRIEF.migration.md.example — shape demonstration
# ---------------------------------------------------------------------------


def test_brief_migration_demonstrates_convictions_shape():
    body = _read(BRIEF_MIGRATION)
    assert "_convictions.md" in body, (
        "BRIEF.migration.md.example MUST demonstrate the _convictions.md "
        "shape (issue #147 AC; the migration template is the natural place "
        "to show carry-forward because migration is when it matters most)"
    )


def test_brief_migration_shows_body_anchor_in_example():
    body = _read(BRIEF_MIGRATION)
    # The shape demonstration must show the body-anchor format (§... refs)
    # so the consumer sees how an anchor is written in practice.
    # The architect contract leans on this being visible in an example,
    # not just declared in prose.
    assert "§" in body, (
        "BRIEF.migration.md.example MUST show body-anchor refs in the "
        "convictions shape demonstration (§Section ¶N format)"
    )


def test_brief_migration_notes_advisory_framing():
    body = _read(BRIEF_MIGRATION)
    lowered = body.lower()
    assert "advisory" in lowered, (
        "BRIEF.migration.md.example MUST note that _convictions.md is "
        "advisory only (not scored, not gating) so the consumer reading "
        "the example doesn't infer it's a graded artifact"
    )


def test_brief_migration_clarifies_file_location():
    body = _read(BRIEF_MIGRATION)
    # The migration template must be explicit that the convictions file
    # lives at <thread>.{N}/_convictions.md, not in the brief itself —
    # otherwise the demonstration could mislead consumers into adding
    # convictions to BRIEF.md directly.
    assert "_convictions.md" in body and (
        "<thread>" in body or "version" in body.lower()
    ), (
        "BRIEF.migration.md.example MUST clarify that _convictions.md lives "
        "in the version dir, not in BRIEF.md — the brief is only "
        "demonstrating the shape"
    )
