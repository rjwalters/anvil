"""Doc-coverage smoke tests for the memo ``.latest`` convenience-symlink contract.

Per issue #153 (follow-up to #120 / #123) acceptance criteria: cheap
"grep-the-doc" regression guard that the ``<thread>.latest`` symlink
convention stays explicitly documented in the memo skill — and that the
resolution questions (does the reviser follow it for input selection?
who updates it? does the reviewer / portfolio orchestrator dereference
it for enumeration?) are *all* answered in skill-level prose, not left
implicit and reachable only via the `version_layout.md` snippet.

**Amended under issue #473**: the convention moved from
"consumer-maintained, framework-tolerated" to "framework-maintained by
default, consumer-pinnable" — the lifecycle commands now end by
invoking the canonical latest-phase CLI
(``anvil/skills/memo/lib/latest_phase.py``), so the expected answers
changed: the *read side* is still "no — digit-N enumeration only", but
the *write side* is now "yes — via the canonical CLI, with operator
pins preserved." The tests assert on substring presence only; they do
NOT validate prose quality or judge the wording. The behavior under
test is documentation hygiene: a future PR that strips the explicit
Q&A back to the single-paragraph cross-ref shape should fail here.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with a similarly-shaped
``test_latest_symlink_doc`` if/when the cross-skill normalization
issue (called out in #153 "Out of scope") ports the same paragraph
shape to slides / paper / report / ip-uspto / installation / proposal.
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


def test_skill_md_answers_q2_lifecycle_updates_latest_via_canonical_cli():
    """Q2 (amended by #473): who updates .latest after writing v{N+1}?

    Answer: the lifecycle commands themselves, via the canonical
    latest-phase CLI — not hand-rolled ``ln -sfn``, not the consumer.
    """
    body = _read(SKILL_MD)
    assert "latest_phase.py" in body, (
        "SKILL.md MUST name the canonical latest-phase CLI as the single "
        "sanctioned .latest write path (issue #473 Q2 amendment)"
    )
    assert "update_latest_symlinks" in body, (
        "SKILL.md MUST name the canonical writer "
        "anvil.lib.latest_resolution.update_latest_symlinks (issue #473)"
    )


def test_skill_md_answers_q3_reviewer_orchestrator_enumerate_digit_n():
    """Q3: do memo-review / portfolio orchestrator dereference .latest
    for enumeration? Still no — the read side is unchanged under #473."""
    body = _read(SKILL_MD)
    assert "memo-review" in body and (
        "enumerate digit-N directories" in body
        or "do not dereference" in body
    ), (
        "SKILL.md MUST explicitly state that memo-review and the portfolio "
        "orchestrator enumerate digit-N directories only — .latest does "
        "not perturb state-machine derivation (issue #153 Q3, #473 "
        "read-side-unchanged framing)"
    )


def test_skill_md_states_framework_maintained_contract():
    body = _read(SKILL_MD)
    assert "framework-maintained by default" in body, (
        "SKILL.md MUST state the #473 contract: .latest symlinks are "
        "framework-maintained by default (consumer-pinnable)"
    )
    assert "preserved" in body, (
        "SKILL.md MUST state that operator pins are preserved "
        "(issues #288/#473)"
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


def test_revise_md_states_canonical_cli_is_only_write_path():
    """Amended by #473: the reviser DOES maintain .latest now — but only
    via the canonical latest-phase CLI (step 9.8), never hand-rolled."""
    body = _read(REVISE_MD)
    assert "latest_phase.py" in body, (
        "memo-revise.md MUST invoke the canonical latest-phase CLI "
        "(issue #473 step 9.8)"
    )
    assert "never *reads*" in body or "never reads" in body, (
        "memo-revise.md MUST still state that the reviser does not read "
        ".latest for input selection (issue #153 Change 2, read side "
        "unchanged under #473)"
    )
