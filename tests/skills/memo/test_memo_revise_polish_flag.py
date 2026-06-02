"""Doc-coverage smoke tests for the ``memo-revise --polish "<reason>"`` flag.

Per issue #201 acceptance criteria: cheap "grep-the-doc" regression guard
that the operator-initiated polish-pass entry point stays documented in
the three files it touches (memo-revise.md, SKILL.md, progress.md
snippet) and doesn't drift back to the default-refuse-only prose in a
later edit.

These tests assert on substring presence and structural ordering only —
they do NOT validate prose quality and they do NOT execute the reviser.
The reviser is LLM-driven, so behavioural assertions belong in
consumer-side integration tests (or in a future shell-level harness),
not here. The seven test functions map 1:1 to the seven test-plan items
in the issue:

1. Default path (no flag) is byte-identical — guarded by ``test_no_polish_flag_advance_true_refuses``.
2. ``--polish`` bypasses step 4 — guarded by ``test_polish_flag_bypasses_verdict_precheck``.
3. Required-reason rejection — guarded by ``test_polish_flag_empty_reason_rejected``.
4. Audit trail lands on disk — guarded by ``test_polish_flag_records_revision_mode_and_reason``.
5. Single-pass semantics — guarded by ``test_polish_flag_requires_fresh_review``.
6. Iteration cap still applies — guarded by ``test_polish_flag_still_blocked_at_iteration_cap``.
7. Full reviser contract honored — guarded by ``test_polish_flag_changelog_header_present``
   (the changelog header is the in-line visibility surface; step 5
   onward is exercised by the existing memo-revise.md prose which the
   polish flag does not alter).

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with the
``test_revise_polish_flag`` shape another skill might pick.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
REVISE_MD = SKILL_ROOT / "commands" / "memo-revise.md"
PROGRESS_SNIPPET = (
    Path(__file__).resolve().parents[3]
    / "anvil"
    / "lib"
    / "snippets"
    / "progress.md"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC1 / Test 1 — Default path (no flag) is byte-identical: regression guard
# ---------------------------------------------------------------------------


def test_no_polish_flag_advance_true_refuses():
    """The default verdict pre-check at step 4 must still refuse to revise
    an ``advance:true`` + 0-critical thread when ``--polish`` was NOT passed.

    This is the regression guard: the polish flag is purely additive and
    must not perturb the byte-identical default-refuse behavior on the
    universal canary shape (15/15 reviewed studio threads landed
    ``advance:true`` + 0 critical).
    """
    body = _read(REVISE_MD)
    # The step 4 prose must explicitly guard on "--polish was NOT passed"
    # so a future edit that drops the conditional falls under the test.
    assert "--polish" in body, (
        "memo-revise.md MUST document the --polish flag (issue #201 AC1)"
    )
    assert "advance == true" in body, (
        "memo-revise.md step 4 MUST keep the advance==true pre-check prose"
    )
    # The default-refuse path must be conditioned on the absence of
    # --polish — otherwise the regression guard is meaningless.
    lowered = body.lower()
    assert "polish` was not passed" in lowered or "polish was not passed" in lowered, (
        "memo-revise.md step 4 MUST condition the default-refuse path on "
        "the absence of --polish so the no-flag invocation stays "
        "byte-identical to current behavior (issue #201 AC1)"
    )


# ---------------------------------------------------------------------------
# AC2 / Test 2 — ``--polish`` bypasses step 4 (verdict pre-check)
# ---------------------------------------------------------------------------


def test_polish_flag_bypasses_verdict_precheck():
    """``--polish "<reason>"`` MUST skip step 4 entirely and proceed to
    step 5, producing a normal ``<thread>.{N+1}/`` version dir even when
    the latest review has ``advance:true`` + 0 critical.
    """
    body = _read(REVISE_MD)
    lowered = body.lower()
    # The bypass MUST be explicit — "skipped entirely" or equivalent
    # imperative wording so the reviser agent doesn't half-apply it.
    assert "skipped entirely" in lowered or "skip" in lowered, (
        "memo-revise.md MUST state that step 4 is skipped entirely when "
        "--polish is passed (issue #201 AC2)"
    )
    # The bypass MUST also state that the reviser proceeds to step 5 —
    # otherwise an over-eager reviser might also skip step 5 (initialize
    # _progress.json), losing the audit trail.
    assert "step 5" in lowered or "proceed to step" in lowered, (
        "memo-revise.md MUST state that --polish skips ONLY step 4 and "
        "proceeds to step 5 (issue #201 AC2)"
    )


# ---------------------------------------------------------------------------
# AC3 / Test 3 — Required-reason rejection (empty / whitespace / missing)
# ---------------------------------------------------------------------------


def test_polish_flag_empty_reason_rejected():
    """``--polish`` (no value), ``--polish ""`` (empty string), and
    ``--polish "   "`` (whitespace-only) MUST all be rejected with a clear
    error pointing at the rejection rule. The thread is left untouched.
    """
    body = _read(REVISE_MD)
    lowered = body.lower()
    # The required-reason rule MUST be explicit. The issue body anchors
    # the rejection on "empty/whitespace-only is rejected" — assert on
    # both stems so a partial rewording still trips.
    assert "required" in lowered, (
        "memo-revise.md MUST state the --polish reason argument is "
        "required (issue #201 AC3)"
    )
    assert "whitespace" in lowered, (
        "memo-revise.md MUST state whitespace-only --polish reasons are "
        "rejected (issue #201 AC3)"
    )
    # Cross-reference to the deck precedent — the iteration_cap_rationale
    # rejection pattern at deck/SKILL.md is the architectural anchor.
    assert "iteration_cap_rationale" in body or "deck" in lowered, (
        "memo-revise.md SHOULD cross-reference the deck "
        "iteration_cap_rationale precedent so the architectural pattern "
        "is discoverable (issue #201 implementation guidance)"
    )


# ---------------------------------------------------------------------------
# AC4 / Test 4 — Audit trail lands on disk
# (revision_mode + revise_force_reason fields)
# ---------------------------------------------------------------------------


def test_polish_flag_records_revision_mode_and_reason():
    """``<thread>.{N+1}/_progress.json.metadata.revision_mode`` equals
    ``"polish"`` and ``revise_force_reason`` equals the verbatim operator
    reason. Both fields are documented in three places: memo-revise.md
    (the writer), SKILL.md (the user-facing contract), and the lib
    progress.md snippet (the schema home).
    """
    revise = _read(REVISE_MD)
    skill = _read(SKILL_MD)
    snippet = _read(PROGRESS_SNIPPET)
    # memo-revise.md — the writer-side documentation
    assert "revision_mode" in revise, (
        "memo-revise.md MUST document metadata.revision_mode (issue #201 AC4)"
    )
    assert "revise_force_reason" in revise, (
        "memo-revise.md MUST document metadata.revise_force_reason (issue #201 AC4)"
    )
    assert '"polish"' in revise, (
        "memo-revise.md MUST show the revision_mode = \"polish\" value "
        "(issue #201 AC4)"
    )
    # The verbatim-reason discipline MUST be explicit so the writer
    # doesn't trim/normalize.
    assert "verbatim" in revise.lower(), (
        "memo-revise.md MUST state the operator reason is stored verbatim "
        "(issue #201 AC4 — no trimming, no normalization)"
    )
    # SKILL.md — the user-facing contract
    assert "revision_mode" in skill, (
        "SKILL.md MUST document metadata.revision_mode in the "
        "operator-initiated polish-passes section (issue #201 AC9)"
    )
    assert "revise_force_reason" in skill, (
        "SKILL.md MUST document metadata.revise_force_reason in the "
        "operator-initiated polish-passes section (issue #201 AC9)"
    )
    # progress.md snippet — schema home
    assert "revision_mode" in snippet, (
        "anvil/lib/snippets/progress.md MUST register revision_mode in "
        "the skill-specific extensions list (issue #201 AC9)"
    )
    assert "revise_force_reason" in snippet, (
        "anvil/lib/snippets/progress.md MUST register revise_force_reason "
        "in the skill-specific extensions list (issue #201 AC9)"
    )


def test_polish_flag_changelog_header_present():
    """``<thread>.{N+1}/changelog.md`` MUST include the polish-pass header
    note when produced under ``--polish``, with the operator reason quoted
    verbatim. The header is the in-line visibility surface for downstream
    readers (next reviewer, auditor, human reader).
    """
    body = _read(REVISE_MD)
    # The blockquote header note format must be documented at the
    # changelog step (step 9).
    assert "Polish pass" in body, (
        "memo-revise.md MUST document the 'Polish pass' header note for "
        "--polish-produced changelog.md (issue #201 AC4)"
    )
    assert "Operator reason:" in body, (
        "memo-revise.md MUST document the 'Operator reason: <verbatim>' "
        "shape in the changelog header note (issue #201 AC4)"
    )
    # The header note discipline (verbatim, no paraphrase) MUST be
    # explicit so a future edit doesn't reword it.
    lowered = body.lower()
    assert "verbatim" in lowered, (
        "memo-revise.md MUST state the operator reason is quoted "
        "verbatim in the changelog header (issue #201 AC4)"
    )


# ---------------------------------------------------------------------------
# AC5 / Test 5 — Single-pass semantics (no fresh review → reject)
# ---------------------------------------------------------------------------


def test_polish_flag_requires_fresh_review():
    """Running ``--polish`` twice in a row without an intervening
    ``memo-review`` MUST be rejected (no fresh review to polish against;
    same shape as step 1's "no review to revise against" error).
    """
    body = _read(REVISE_MD)
    lowered = body.lower()
    # The "fresh review required" check is documented at step 1; the
    # polish flag MUST NOT bypass it.
    assert "fresh review" in lowered or "no review to" in lowered, (
        "memo-revise.md MUST document that --polish requires a fresh "
        "review (issue #201 AC5 — single-pass semantics; no loop)"
    )
    # The "single pass / never loops" discipline must be explicit so a
    # future edit doesn't accidentally make --polish loopable.
    assert "single-pass" in lowered or "exactly one" in lowered or "never loops" in lowered, (
        "memo-revise.md MUST state --polish produces exactly one new "
        "version dir and never loops (issue #201 AC5)"
    )


# ---------------------------------------------------------------------------
# AC6 / Test 6 — Iteration cap still applies under --polish
# ---------------------------------------------------------------------------


def test_polish_flag_still_blocked_at_iteration_cap():
    """The iteration-cap check at step 3 still applies — ``--polish``
    against a thread at ``max_iterations`` MUST hit the BLOCKED notice
    unchanged. The polish flag bypasses step 4 ONLY.
    """
    body = _read(REVISE_MD)
    lowered = body.lower()
    # The "step 4 only" scoping must be explicit so the reviser doesn't
    # also bypass step 3 (iteration cap) or step 1 (fresh review).
    assert "step 4" in lowered and ("only" in lowered or "step 3" in lowered), (
        "memo-revise.md MUST state --polish bypasses step 4 ONLY (the "
        "iteration cap at step 3 still applies) (issue #201 AC6)"
    )
    # The BLOCKED notice must be referenced so the reviser knows what to
    # surface when the cap fires under --polish.
    assert "BLOCKED" in body or "iteration cap" in lowered or "max_iterations" in body, (
        "memo-revise.md MUST reference the BLOCKED notice / iteration "
        "cap so the reviser surfaces it under --polish at cap (issue #201 AC6)"
    )


# ---------------------------------------------------------------------------
# AC7 / Test 7 — Full reviser contract honored
# (the reviewer does NOT special-case the polish pass)
# ---------------------------------------------------------------------------


def test_polish_flag_full_reviser_contract_honored():
    """The full reviser contract from step 5 onward (target-length
    resolution, critic-sibling discovery, memo-render non-blocking call,
    phases.revise.state = done) MUST be honored unchanged under
    ``--polish``. The reviewer does NOT read revision_mode and does NOT
    special-case the polish pass — it scores the polished version on its
    own rubric merits.
    """
    revise = _read(REVISE_MD)
    skill = _read(SKILL_MD)
    lowered_revise = revise.lower()
    # The polish pass must explicitly not re-define steps 5-onward; the
    # bypass is documented as "step 4 only" with the rest of the
    # procedure honored.
    assert "proceed to step 5" in lowered_revise or "step 5 onward" in lowered_revise, (
        "memo-revise.md MUST state that --polish proceeds to step 5 "
        "(the full reviser contract from step 5 onward is honored) "
        "(issue #201 AC7)"
    )
    # SKILL.md MUST state that the reviewer does NOT read revision_mode
    # — this is the AC8 "reviewer does NOT special-case the polish pass"
    # guarantee, asserted here because it's part of the contract surface
    # that a future edit could quietly drop.
    lowered_skill = skill.lower()
    assert "does not read" in lowered_skill or "not read" in lowered_skill, (
        "SKILL.md MUST state the reviewer does NOT read revision_mode "
        "(issue #201 AC8 — the polish pass is not a leniency signal)"
    )
    # The audit-trail-only framing MUST be explicit so the contract
    # stays purely operator-side disclosure.
    assert "audit-trail" in lowered_skill or "audit trail" in lowered_skill, (
        "SKILL.md MUST state revision_mode / revise_force_reason are "
        "audit-trail only (issue #201 AC8)"
    )
    assert "not scored" in lowered_skill and "not gating" in lowered_skill, (
        "SKILL.md MUST state revision_mode is not scored, not gating "
        "(issue #201 AC8 — audit-trail-only contract)"
    )
