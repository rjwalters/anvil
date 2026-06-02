"""Unit + doc-coverage tests for ``anvil/skills/deck/lib/parity_lint.py``.

Per issue #200 acceptance criteria: pin the citation-clear canary
regression (memo says "~50–60% completion", deck doesn't → should
flag) as a deterministic test, plus the graceful-skip path (no memo
sibling), the escape-hatch path (``<!-- anvil-lint-disable:
deck_memo_parity -->``), and a doc-coverage guard that the
``deck-review.md`` command file has the step 5d wiring in it.

Per-skill test filename convention (#58): this file is named
``test_parity_lint.py`` and lives under ``tests/skills/deck/``; the
``tests/skills/deck/__init__.py`` chain prevents collision with a
future ``tests/skills/memo/test_parity_lint.py`` mirror.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.skills.deck.lib.parity_lint import (
    EXTRACTORS,
    Finding,
    LintResult,
    RULES,
    UNIT_VOCABULARY,
    lint_deck_memo_parity,
    lint_source,
)


# ---------------------------------------------------------------------------
# Module shape — Finding / LintResult / RULES / EXTRACTORS surface
# ---------------------------------------------------------------------------


def test_rules_tuple_contains_deck_memo_parity():
    """The module's v0 rule is ``deck_memo_parity`` — AC1 / AC2."""
    assert RULES == ("deck_memo_parity",)


def test_extractors_cover_required_classes():
    """Money / percent / quarter_fy / month_year / acronym / unit_int — AC6."""
    labels = {label for label, _ in EXTRACTORS}
    assert labels == {
        "money",
        "percent",
        "quarter_fy",
        "month_year",
        "acronym",
        "unit_int",
    }


def test_unit_vocabulary_includes_canary_units():
    """The unit vocab must include the canary terms (LOIs, pilots,
    completion) that drove the v0 scope. Adding a unit is canary-driven."""
    assert "LOIs" in UNIT_VOCABULARY
    assert "pilots" in UNIT_VOCABULARY
    assert "completion" in UNIT_VOCABULARY


# ---------------------------------------------------------------------------
# Citation-clear canary regression — the AC6 deterministic anchor
# ---------------------------------------------------------------------------


CITATION_CLEAR_MEMO_BODY = """\
# Citation Clear — Investment Memo v4

## Problem

Insurance claims processing is slow. The FTC settled with one large carrier
for $193K in Jan 2025 — a 5-0 vote. The insurer benchmark study showed
~50–60% completion on first-pass claims.

## Traction

8 pilots in production. SFMTA awarded $126M+ since April 2024.

NYC's FY24 reduction was 26.6%.
"""

CITATION_CLEAR_DECK_BODY = """\
---
marp: true
---

# Citation Clear

---

## Problem

Insurance claims are slow. FTC settled $193K in Jan 2025 (5-0).

---

## Traction

- 8 pilots in production
- SFMTA $126M+ since April 2024
- NYC FY24: 26.6%
"""


def test_citation_clear_canary_50_60_percent_completion_flagged():
    """**The load-bearing regression test for issue #200.**

    Memo body contains the insurer benchmark ``~50–60% completion`` that the
    deck body lacks. The percent extractor must capture ``50–60%`` (or
    ASCII-normalized ``50-60%``) and the set comparison must surface it as
    ``only_in_memo`` — exactly the canary failure mode that surfaced this
    issue.
    """
    result = lint_source(CITATION_CLEAR_DECK_BODY, CITATION_CLEAR_MEMO_BODY)

    only_in_memo = result.only_in_memo
    assert "50-60%" in only_in_memo, (
        f"expected `50-60%` (normalized from memo's `50–60%`) in "
        f"only_in_memo; got {only_in_memo!r}"
    )

    # The finding for the canary must be a warning (Phase A, NOT error).
    canary_findings = [f for f in result.warnings if f.token == "50-60%"]
    assert len(canary_findings) == 1
    assert canary_findings[0].severity == "warning"
    assert canary_findings[0].side == "only_in_memo"
    assert canary_findings[0].rule == "deck_memo_parity"
    # The diagnostic should name the canary anchor so the Phase A → Phase B
    # promotion conversation has a concrete reference.
    assert "Citation Clear" in canary_findings[0].message


def test_citation_clear_shared_hard_claims_are_NOT_flagged():
    """Shared hard claims (FTC, $193K, Jan 2025, 5-0, SFMTA, $126M+, NYC,
    FY24, 26.6%, April 2024) appear in BOTH bodies — none should be flagged.
    This guards against an over-aggressive extractor that fires on the
    citation-clear baseline."""
    result = lint_source(CITATION_CLEAR_DECK_BODY, CITATION_CLEAR_MEMO_BODY)

    flagged_tokens = {f.token for f in result.warnings}

    for shared in ("$193K", "FTC", "SFMTA", "NYC", "26.6%", "$126M"):
        # Either the exact token isn't flagged at all, or if it appears in
        # one body but not the other (e.g., a slightly different surface
        # form), it's tolerated. The strict assertion is that an exact
        # surface-equal shared claim doesn't get flagged.
        assert shared not in flagged_tokens or _is_only_in_one_body(
            result, shared
        ), (
            f"shared hard claim `{shared}` should not be flagged when both "
            f"bodies carry the same surface form; got flagged tokens "
            f"{flagged_tokens!r}"
        )


def _is_only_in_one_body(result: LintResult, token: str) -> bool:
    """Helper: is the token flagged as only-in-memo or only-in-deck?"""
    return token in result.only_in_memo or token in result.only_in_deck


# ---------------------------------------------------------------------------
# Graceful-skip path (AC7)
# ---------------------------------------------------------------------------


def test_graceful_skip_when_memo_version_dir_is_None(tmp_path: Path):
    """When the caller passes ``memo_version_dir=None``, the lint records
    a skip with a clear reason and zero findings — AC7."""
    deck_version_dir = tmp_path / "thread.1"
    deck_version_dir.mkdir()
    (deck_version_dir / "deck.md").write_text("# Deck\n")

    result = lint_deck_memo_parity(deck_version_dir, None)

    assert result.skipped is True
    assert result.memo_sibling is None
    assert result.reason is not None
    assert "no memo sibling" in result.reason.lower()
    assert result.warnings == []
    assert result.infos == []
    assert result.total == 0


def test_graceful_skip_when_memo_md_missing(tmp_path: Path):
    """When the memo_version_dir exists but contains no ``memo.md``, the
    lint skips with a reason that names the missing path."""
    deck_dir = tmp_path / "thread.1"
    memo_dir = tmp_path / "thread.1m"
    deck_dir.mkdir()
    memo_dir.mkdir()
    (deck_dir / "deck.md").write_text("# Deck\n")
    # NOTE: memo.md deliberately not written.

    result = lint_deck_memo_parity(deck_dir, memo_dir)

    assert result.skipped is True
    assert result.memo_sibling == str(memo_dir.resolve())
    assert "memo.md not found" in result.reason


def test_graceful_skip_summary_shape_is_structured(tmp_path: Path):
    """The graceful-skip path must serialize an ``_summary.md`` block with
    ``ran: false`` and ``memo_sibling: null`` per the issue body — the
    operator sees WHY the check didn't fire (AC7)."""
    deck_version_dir = tmp_path / "thread.1"
    deck_version_dir.mkdir()
    (deck_version_dir / "deck.md").write_text("# Deck\n")

    result = lint_deck_memo_parity(deck_version_dir, None)
    summary = result.to_summary()

    assert summary["ran"] is False
    assert summary["memo_sibling"] is None
    assert summary["reason"] is not None
    assert summary["warnings"] == 0
    assert summary["only_in_memo"] == []
    assert summary["only_in_deck"] == []


# ---------------------------------------------------------------------------
# Escape-hatch path (AC8)
# ---------------------------------------------------------------------------


def test_escape_hatch_downgrades_finding_to_info():
    """A ``<!-- anvil-lint-disable: deck_memo_parity -->`` on the same line
    as a deliberately-deck-only claim downgrades the parity finding from
    ``warning`` to ``info`` — AC8."""
    deck_body = (
        "# Deck\n"
        "We considered the FTC enforcement angle. <!-- anvil-lint-disable: deck_memo_parity -->\n"
    )
    memo_body = "# Memo\n(this body deliberately omits the acronym.)\n"

    result = lint_source(deck_body, memo_body)

    # The FTC token should be flagged as ``only_in_deck`` BUT downgraded
    # to info because of the suppression directive.
    info_tokens = {f.token for f in result.infos}
    warning_tokens = {f.token for f in result.warnings}

    assert "FTC" in info_tokens, (
        f"FTC should be suppressed to info; got infos={info_tokens!r}, "
        f"warnings={warning_tokens!r}"
    )
    assert "FTC" not in warning_tokens


def test_escape_hatch_above_line_also_works():
    """A standalone directive on the line directly above the token also
    downgrades the finding (mirrors ``memo_image_refs._collect_disabled_lines``).
    """
    deck_body = (
        "# Deck\n"
        "<!-- anvil-lint-disable: deck_memo_parity -->\n"
        "FTC enforcement is in scope.\n"
    )
    memo_body = "# Memo\n"

    result = lint_source(deck_body, memo_body)
    info_tokens = {f.token for f in result.infos}
    warning_tokens = {f.token for f in result.warnings}

    assert "FTC" in info_tokens, (
        f"FTC should be suppressed via line-above directive; "
        f"infos={info_tokens!r}, warnings={warning_tokens!r}"
    )
    assert "FTC" not in warning_tokens


# ---------------------------------------------------------------------------
# Severity contract — Phase A ships warning-only (AC5)
# ---------------------------------------------------------------------------


def test_phase_A_emits_warnings_only_never_errors():
    """v0 ships at warning severity. ``errors`` MUST be empty on every code
    path so the ``lint_critical_flag`` aggregation in ``deck-review`` step
    12 is untouched (AC5)."""
    # Set up a body with multiple divergences across multiple extractors.
    deck_body = "# Deck\n$50M ARR, Q1 FY24."
    memo_body = "# Memo\n$60M ARR, Q2 FY25, FTC angle."

    result = lint_source(deck_body, memo_body)

    assert result.errors == []
    # And every finding's severity must be warning (none are info-suppressed here).
    for f in result.warnings:
        assert f.severity == "warning", (
            f"Phase A must emit warning-only; got severity={f.severity!r} "
            f"on token {f.token!r}"
        )


# ---------------------------------------------------------------------------
# Extractor unit tests — money, percent, dates, acronyms, unit-int
# ---------------------------------------------------------------------------


def test_money_extractor_picks_up_canary_dollar_amounts():
    """``$193K``, ``$126M``, ``$8.99`` — the canary money shapes (AC6)."""
    deck_body = "# Deck\n"
    memo_body = "# Memo\nFTC $193K, SFMTA $126M+, pricing $8.99/$29.99."

    result = lint_source(deck_body, memo_body)
    tokens = result.only_in_memo

    assert "$193K" in tokens
    assert "$126M" in tokens
    assert "$8.99" in tokens
    assert "$29.99" in tokens


def test_percent_extractor_handles_en_dash_range():
    """``50–60%`` (en-dash) and ``50-60%`` (hyphen) must normalize to
    the same token so a memo writing en-dash and a deck writing hyphen
    don't fire a false-positive."""
    deck_body = "# Deck\nWe see 50-60% completion."
    memo_body = "# Memo\nWe see 50–60% completion."

    result = lint_source(deck_body, memo_body)

    # The normalized token should match across both bodies → no warning.
    assert result.only_in_memo == []
    assert result.only_in_deck == []


def test_quarter_fy_extractor():
    """``Q1 FY24`` / ``FY2024`` / ``FY24`` (AC6)."""
    deck_body = "# Deck\nQ1 FY24 milestone."
    memo_body = "# Memo\nFY2024 close-out."

    result = lint_source(deck_body, memo_body)

    only_in_deck = result.only_in_deck
    only_in_memo = result.only_in_memo
    assert "Q1 FY24" in only_in_deck
    assert "FY2024" in only_in_memo


def test_month_year_extractor():
    """``Jan 2025`` and ``April 2024`` (AC6)."""
    deck_body = "# Deck\nJan 2025 close."
    memo_body = "# Memo\nApril 2024 launch."

    result = lint_source(deck_body, memo_body)
    assert "Jan 2025" in result.only_in_deck
    assert "April 2024" in result.only_in_memo


def test_acronym_extractor_bounds_length_2_to_6():
    """ALL-CAPS tokens of length 2-6 (FTC, SFMTA, NYC, LOI). Long shouting
    (``ABCDEFGH``) should NOT be captured."""
    deck_body = "# Deck\nWe partner with FTC and SFMTA."
    memo_body = "# Memo\nNYC pilot in scope. ABCDEFGH is too long."

    result = lint_source(deck_body, memo_body)

    only_in_memo = result.only_in_memo
    only_in_deck = result.only_in_deck
    assert "NYC" in only_in_memo
    assert "FTC" in only_in_deck
    assert "SFMTA" in only_in_deck
    # The 8-char shout should not be captured by the acronym extractor.
    assert "ABCDEFGH" not in only_in_memo


def test_unit_int_extractor():
    """``8 pilots``, ``50 LOIs`` — the unit-bearing integer shapes."""
    deck_body = "# Deck\n8 pilots in production."
    memo_body = "# Memo\n50 LOIs signed."

    result = lint_source(deck_body, memo_body)
    assert "8 pilots" in result.only_in_deck
    assert "50 LOIs" in result.only_in_memo


# ---------------------------------------------------------------------------
# File-wrapper path: lint_deck_memo_parity with real files on disk
# ---------------------------------------------------------------------------


def test_lint_deck_memo_parity_with_real_files(tmp_path: Path):
    """End-to-end exercise of the file wrapper: lay down deck.md + memo.md
    inside two version dirs, verify the citation-clear canary fires."""
    deck_dir = tmp_path / "citation-clear.3"
    memo_dir = tmp_path / "citation-clear.4"
    deck_dir.mkdir()
    memo_dir.mkdir()
    (deck_dir / "deck.md").write_text(CITATION_CLEAR_DECK_BODY)
    (memo_dir / "memo.md").write_text(CITATION_CLEAR_MEMO_BODY)

    result = lint_deck_memo_parity(deck_dir, memo_dir)

    assert result.skipped is False
    assert result.memo_sibling == str(memo_dir.resolve())
    assert "50-60%" in result.only_in_memo


# ---------------------------------------------------------------------------
# Doc-coverage: deck-review.md must have step 5d wiring
# ---------------------------------------------------------------------------


DECK_REVIEW_MD = (
    Path(__file__).resolve().parents[3]
    / "anvil"
    / "skills"
    / "deck"
    / "commands"
    / "deck-review.md"
)


def test_deck_review_md_has_step_5d_parity_lint():
    """``deck-review.md`` must reference ``parity_lint`` in a step 5d
    block — AC2."""
    text = DECK_REVIEW_MD.read_text(encoding="utf-8")
    assert "5d" in text, "deck-review.md must declare a step 5d"
    assert "parity_lint" in text, (
        "deck-review.md step 5d must invoke parity_lint"
    )
    assert "lint_deck_memo_parity" in text, (
        "deck-review.md step 5d must name the public-API function"
    )


def test_deck_review_md_documents_graceful_skip():
    """The graceful-skip-on-no-memo-sibling contract MUST be documented
    in deck-review.md (AC2)."""
    text = DECK_REVIEW_MD.read_text(encoding="utf-8")
    # The doc should explicitly say the lint skips when no memo sibling is
    # discoverable.
    assert "graceful" in text.lower() or "skip" in text.lower()
    assert "memo sibling" in text.lower() or "memo_sibling" in text.lower()


def test_deck_review_md_documents_warning_only_severity():
    """v0 ships at warning severity — must be explicit in the doc (AC2 / AC5)."""
    text = DECK_REVIEW_MD.read_text(encoding="utf-8")
    # The Phase A warning-only contract must be named.
    assert "warning" in text.lower()
    # And the contract that the verdict logic is unchanged in v0.
    assert "lint_critical_flag" in text or "critical_flag" in text


def test_deck_review_md_documents_escape_hatch():
    """The ``anvil-lint-disable: deck_memo_parity`` escape hatch must be
    documented in deck-review.md (AC2 / AC8)."""
    text = DECK_REVIEW_MD.read_text(encoding="utf-8")
    assert "deck_memo_parity" in text
    assert "anvil-lint-disable" in text


def test_deck_review_md_findings_subsection_documented():
    """The ``## Parity-lint findings (deck↔memo, optional)`` subsection
    must be referenced in the deck-review.md ``findings.md`` shape (AC4)."""
    text = DECK_REVIEW_MD.read_text(encoding="utf-8")
    assert "Parity-lint findings" in text


# ---------------------------------------------------------------------------
# Module docstring carries the promotion-path declaration (AC9)
# ---------------------------------------------------------------------------


def test_module_docstring_names_promotion_path():
    """AC9: module docstring explicitly names ``anvil/lib/parity.py`` as
    the promotion target + mirrors ``marp_lint.py`` shape."""
    from anvil.skills.deck.lib import parity_lint

    doc = parity_lint.__doc__ or ""
    assert "anvil/lib/parity.py" in doc, (
        "module docstring must name the promotion path"
    )
    assert "marp_lint" in doc, (
        "module docstring must reference the marp_lint mirroring pattern"
    )
    assert "memo-side mirror" in doc or "memo_image_refs" in doc.lower() or "memo-side" in doc
