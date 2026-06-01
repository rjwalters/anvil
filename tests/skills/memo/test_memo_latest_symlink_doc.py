"""Doc-coverage smoke tests for the memo ``.latest`` convenience-symlink contract.

Per issue #153 (follow-up to #120 / #123) acceptance criteria: cheap
"grep-the-doc" regression guard that the optional ``<thread>.latest``
symlink convention stays explicitly documented in the memo skill — and
that the three resolution questions (does the reviser follow it? does
the reviser update it? does the reviewer / portfolio orchestrator
dereference it?) are *all* answered in skill-level prose, not left
implicit and reachable only via the `version_layout.md` snippet.

The expected answer to all three questions is "no — consumer-side." The
tests assert on substring presence only; they do NOT validate prose
quality or judge the wording. The behavior under test is documentation
hygiene: a future PR that strips the explicit Q&A back to the
single-paragraph cross-ref shape (the pre-#153 state) should fail here.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with a similarly-shaped
``test_latest_symlink_doc`` if/when the cross-skill normalization
issue (called out in #153 "Out of scope") ports the same paragraph
shape to slides / pub / report / ip-uspto / installation / proposal.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
REVISE_MD = SKILL_ROOT / "commands" / "memo-revise.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SKILL.md — explicit Q&A for the three resolution questions
# ---------------------------------------------------------------------------


def test_skill_md_documents_latest_symlink_convention():
    body = _read(SKILL_MD)
    assert ".latest" in body, (
        "SKILL.md MUST document the optional .latest convenience-symlink "
        "convention (issue #153 follow-up to #123)"
    )


def test_skill_md_cross_references_version_layout_snippet():
    body = _read(SKILL_MD)
    assert "version_layout.md" in body, (
        "SKILL.md MUST cross-reference anvil/lib/snippets/version_layout.md "
        "as the canonical .latest convention definition"
    )


def test_skill_md_answers_q1_memo_revise_does_not_follow_latest():
    """Q1: does memo-revise dereference .latest, or enumerate digit-N dirs?"""
    body = _read(SKILL_MD)
    assert "memo-revise" in body and "does not follow" in body, (
        "SKILL.md MUST explicitly state that memo-revise does not follow "
        "the .latest symlink (issue #153 Q1)"
    )


def test_skill_md_answers_q2_memo_revise_does_not_update_latest():
    """Q2: does memo-revise update .latest after writing v{N+1}?"""
    body = _read(SKILL_MD)
    assert "does not update" in body, (
        "SKILL.md MUST explicitly state that memo-revise does not update "
        "the .latest symlink after producing a new version dir (issue #153 Q2)"
    )


def test_skill_md_answers_q3_reviewer_orchestrator_do_not_dereference_latest():
    """Q3: do memo-review / portfolio orchestrator dereference .latest?"""
    body = _read(SKILL_MD)
    assert "memo-review" in body and "do not dereference" in body, (
        "SKILL.md MUST explicitly state that memo-review and the portfolio "
        "orchestrator do not dereference .latest (issue #153 Q3)"
    )


def test_skill_md_calls_out_consumer_side_maintenance():
    body = _read(SKILL_MD)
    assert "consumer-side" in body, (
        "SKILL.md MUST state that .latest symlink maintenance is "
        "consumer-side (issue #153 framing)"
    )


def test_skill_md_references_thread_state_regex_exclusion():
    """The 'why .latest is invisible' answer lives in thread_state.md."""
    body = _read(SKILL_MD)
    assert "thread_state.md" in body, (
        "SKILL.md MUST cross-reference anvil/lib/snippets/thread_state.md "
        "as the source of the digit-N regex that makes .latest invisible to "
        "state-machine enumeration"
    )


# ---------------------------------------------------------------------------
# memo-revise.md — short cross-reference to SKILL.md
# ---------------------------------------------------------------------------


def test_revise_md_cross_references_latest_convention():
    body = _read(REVISE_MD)
    assert ".latest" in body, (
        "memo-revise.md MUST contain a cross-reference to the .latest "
        "symlink convention (issue #153 Change 2)"
    )


def test_revise_md_states_reviser_does_not_touch_latest():
    body = _read(REVISE_MD)
    assert "neither reads nor updates" in body or (
        "does not read" in body and "does not update" in body
    ), (
        "memo-revise.md MUST explicitly state that the reviser neither "
        "reads nor updates the .latest symlink (issue #153 Change 2)"
    )
