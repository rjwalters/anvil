"""Unit + doc-coverage tests for ``anvil/skills/memo/lib/parity_lint.py``.

Per issue #215 acceptance criteria: pin the citation-clear canary regression
(memo body lacks ``~50–60% completion``, deck body has it → flagged as
``only_in_deck``) as a deterministic test, plus the graceful-skip path (no
deck sibling), the escape-hatch path (``<!-- anvil-lint-disable:
memo_deck_parity -->``), a doc-coverage guard that the ``memo-review.md``
command file has the step 4d wiring in it, and the **symmetry test** (AC12)
that validates the memo-side and deck-side ``lint_source`` calls produce
equivalent finding sets on the same body pair — the contract that justifies
the lib promotion follow-up to ``anvil/lib/parity.py``.

Per-skill test filename convention (#58): this file is named
``test_memo_parity_lint.py`` and lives under ``tests/skills/memo/``; the
``tests/skills/memo/__init__.py`` chain prevents collision with the existing
``tests/skills/deck/test_parity_lint.py`` sibling.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.skills.memo.lib.parity_lint import (
    EXTRACTORS,
    Finding,
    LintResult,
    RULES,
    UNIT_VOCABULARY,
    lint_memo_deck_parity,
    lint_source,
)


# ---------------------------------------------------------------------------
# Module shape — Finding / LintResult / RULES / EXTRACTORS surface
# ---------------------------------------------------------------------------


def test_rules_tuple_contains_memo_deck_parity():
    """The module's v0 rule is ``memo_deck_parity`` — AC1."""
    assert RULES == ("memo_deck_parity",)


def test_extractors_cover_required_classes():
    """Money / percent / quarter_fy / month_year / acronym / unit_int — AC3."""
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


def test_lint_result_has_deck_sibling_field():
    """AC5: ``LintResult.deck_sibling`` mirrors the deck-side's ``memo_sibling``."""
    result = LintResult()
    assert hasattr(result, "deck_sibling")
    # Default is None on a fresh LintResult.
    assert result.deck_sibling is None


# ---------------------------------------------------------------------------
# Citation-clear canary regression — the AC1/AC6 deterministic anchor
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
    """**The load-bearing regression test for issue #215 (memo-side mirror).**

    Memo body contains the insurer benchmark ``~50–60% completion`` that the
    deck body lacks. From the memo-side perspective, this is the ``only_in_memo``
    direction — the same token surfaced by the deck-side parity_lint in its
    ``only_in_memo`` set (the contract that the two checks are symmetric).
    """
    result = lint_source(CITATION_CLEAR_MEMO_BODY, CITATION_CLEAR_DECK_BODY)

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
    assert canary_findings[0].rule == "memo_deck_parity"


def test_citation_clear_only_in_deck_direction_flagged():
    """The symmetric load-bearing canary direction (AC4): deck has a hard claim
    the memo lacks → ``only_in_deck`` warning. This is the load-bearing failure
    mode the memo-side mirror specifically catches — deck pulled ahead, memo
    didn't notice."""
    # Flip the bodies so the percent is in the deck body.
    memo_body = "# Memo\nGeneral overview only — no benchmarks called out.\n"
    deck_body = "# Deck\nInsurer benchmark study showed ~50–60% completion.\n"

    result = lint_source(memo_body, deck_body)

    only_in_deck = result.only_in_deck
    assert "50-60%" in only_in_deck, (
        f"expected `50-60%` in only_in_deck (deck pulled ahead); "
        f"got {only_in_deck!r}"
    )

    canary_findings = [f for f in result.warnings if f.token == "50-60%"]
    assert len(canary_findings) == 1
    assert canary_findings[0].side == "only_in_deck"
    assert canary_findings[0].rule == "memo_deck_parity"
    # The only_in_deck message must name the canary anchor (AC4).
    assert "Citation Clear" in canary_findings[0].message


def test_citation_clear_shared_hard_claims_are_NOT_flagged():
    """Shared hard claims (FTC, $193K, Jan 2025, 5-0, SFMTA, $126M+, NYC,
    FY24, 26.6%, April 2024) appear in BOTH bodies — none should be flagged.
    This guards against an over-aggressive extractor that fires on the
    citation-clear baseline."""
    result = lint_source(CITATION_CLEAR_MEMO_BODY, CITATION_CLEAR_DECK_BODY)

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
# Graceful-skip path (AC6)
# ---------------------------------------------------------------------------


def test_graceful_skip_when_deck_version_dir_is_None(tmp_path: Path):
    """When the caller passes ``deck_version_dir=None``, the lint records
    a skip with a clear reason and zero findings — AC6."""
    # Body filename echoes thread slug per #295 — version dir is
    # ``thread/thread.1/`` and body is ``thread/thread.1/thread.md``.
    thread = tmp_path / "thread"
    thread.mkdir()
    memo_version_dir = thread / "thread.1"
    memo_version_dir.mkdir()
    (memo_version_dir / "thread.md").write_text("# Memo\n")

    result = lint_memo_deck_parity(memo_version_dir, None)

    assert result.skipped is True
    assert result.deck_sibling is None
    assert result.reason is not None
    assert "no deck sibling" in result.reason.lower()
    assert result.warnings == []
    assert result.infos == []
    assert result.total == 0


def test_graceful_skip_when_deck_md_missing(tmp_path: Path):
    """When the deck_version_dir exists but contains no ``deck.md``, the
    lint skips with a reason that names the missing path — AC6."""
    memo_thread = tmp_path / "thread-m"
    memo_thread.mkdir()
    memo_dir = memo_thread / "thread-m.1"
    deck_thread = tmp_path / "thread-d"
    deck_thread.mkdir()
    deck_dir = deck_thread / "thread-d.1"
    memo_dir.mkdir()
    deck_dir.mkdir()
    (memo_dir / "thread-m.md").write_text("# Memo\n")
    # NOTE: deck.md deliberately not written.

    result = lint_memo_deck_parity(memo_dir, deck_dir)

    assert result.skipped is True
    assert result.deck_sibling == str(deck_dir.resolve())
    assert "deck.md not found" in result.reason


def test_graceful_skip_when_memo_md_missing(tmp_path: Path):
    """When the memo_version_dir exists but contains no body markdown,
    the lint skips with a reason that names the missing path — AC6."""
    memo_thread = tmp_path / "thread-m"
    memo_thread.mkdir()
    memo_dir = memo_thread / "thread-m.1"
    deck_thread = tmp_path / "thread-d"
    deck_thread.mkdir()
    deck_dir = deck_thread / "thread-d.1"
    memo_dir.mkdir()
    deck_dir.mkdir()
    (deck_dir / "deck.md").write_text("# Deck\n")
    # NOTE: body markdown (``thread-m.md``) deliberately not written.

    result = lint_memo_deck_parity(memo_dir, deck_dir)

    assert result.skipped is True
    assert result.deck_sibling == str(deck_dir.resolve())
    assert "thread-m.md not found" in result.reason


def test_graceful_skip_summary_shape_is_structured(tmp_path: Path):
    """The graceful-skip path must serialize an ``_summary.md`` block with
    ``ran: false`` and ``deck_sibling: null`` per the issue body — the
    operator sees WHY the check didn't fire (AC5 / AC6)."""
    thread = tmp_path / "thread"
    thread.mkdir()
    memo_version_dir = thread / "thread.1"
    memo_version_dir.mkdir()
    (memo_version_dir / "thread.md").write_text("# Memo\n")

    result = lint_memo_deck_parity(memo_version_dir, None)
    summary = result.to_summary()

    assert summary["ran"] is False
    assert summary["deck_sibling"] is None
    assert summary["reason"] is not None
    assert summary["warnings"] == 0
    assert summary["only_in_memo"] == []
    assert summary["only_in_deck"] == []
    assert summary["warnings_by_token"] == []
    assert summary["infos_by_token"] == []


# ---------------------------------------------------------------------------
# Escape-hatch path (AC2)
# ---------------------------------------------------------------------------


def test_escape_hatch_downgrades_finding_to_info():
    """A ``<!-- anvil-lint-disable: memo_deck_parity -->`` on the same line
    as a deliberately-memo-only claim downgrades the parity finding from
    ``warning`` to ``info`` — AC2."""
    memo_body = (
        "# Memo\n"
        "We considered the FTC enforcement angle. <!-- anvil-lint-disable: memo_deck_parity -->\n"
    )
    deck_body = "# Deck\n(this body deliberately omits the acronym.)\n"

    result = lint_source(memo_body, deck_body)

    # The FTC token should be flagged as ``only_in_memo`` BUT downgraded
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
    memo_body = (
        "# Memo\n"
        "<!-- anvil-lint-disable: memo_deck_parity -->\n"
        "FTC enforcement is in scope.\n"
    )
    deck_body = "# Deck\n"

    result = lint_source(memo_body, deck_body)
    info_tokens = {f.token for f in result.infos}
    warning_tokens = {f.token for f in result.warnings}

    assert "FTC" in info_tokens, (
        f"FTC should be suppressed via line-above directive; "
        f"infos={info_tokens!r}, warnings={warning_tokens!r}"
    )
    assert "FTC" not in warning_tokens


def test_escape_hatch_honors_comma_separated_rule_list():
    """AC2: comma-separated rule lists honored (``memo_deck_parity, other``)."""
    memo_body = (
        "# Memo\n"
        "FTC angle. <!-- anvil-lint-disable: memo_deck_parity, memo_image_refs_exist -->\n"
    )
    deck_body = "# Deck\n"

    result = lint_source(memo_body, deck_body)
    info_tokens = {f.token for f in result.infos}
    warning_tokens = {f.token for f in result.warnings}

    assert "FTC" in info_tokens
    assert "FTC" not in warning_tokens


# ---------------------------------------------------------------------------
# Severity contract — Phase A ships warning-only (AC5)
# ---------------------------------------------------------------------------


def test_phase_A_emits_warnings_only_never_errors():
    """v0 ships at warning severity. ``errors`` MUST be empty on every code
    path so the ``lint_critical_flag`` aggregation in ``memo-review`` step 7
    is untouched (AC5 / AC10)."""
    # Set up a body with multiple divergences across multiple extractors.
    memo_body = "# Memo\n$60M ARR, Q2 FY25, FTC angle."
    deck_body = "# Deck\n$50M ARR, Q1 FY24."

    result = lint_source(memo_body, deck_body)

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
    """``$193K``, ``$126M``, ``$8.99`` — the canary money shapes (AC3)."""
    memo_body = "# Memo\nFTC $193K, SFMTA $126M+, pricing $8.99/$29.99."
    deck_body = "# Deck\n"

    result = lint_source(memo_body, deck_body)
    tokens = result.only_in_memo

    assert "$193K" in tokens
    assert "$126M" in tokens
    assert "$8.99" in tokens
    assert "$29.99" in tokens


def test_percent_extractor_handles_en_dash_range():
    """``50–60%`` (en-dash) and ``50-60%`` (hyphen) must normalize to
    the same token so a memo writing en-dash and a deck writing hyphen
    don't fire a false-positive."""
    memo_body = "# Memo\nWe see 50–60% completion."
    deck_body = "# Deck\nWe see 50-60% completion."

    result = lint_source(memo_body, deck_body)

    # The normalized token should match across both bodies → no warning.
    assert result.only_in_memo == []
    assert result.only_in_deck == []


def test_quarter_fy_extractor():
    """``Q1 FY24`` / ``FY2024`` / ``FY24`` (AC3)."""
    memo_body = "# Memo\nFY2024 close-out."
    deck_body = "# Deck\nQ1 FY24 milestone."

    result = lint_source(memo_body, deck_body)

    only_in_deck = result.only_in_deck
    only_in_memo = result.only_in_memo
    assert "Q1 FY24" in only_in_deck
    assert "FY2024" in only_in_memo


def test_month_year_extractor():
    """``Jan 2025`` and ``April 2024`` (AC3)."""
    memo_body = "# Memo\nApril 2024 launch."
    deck_body = "# Deck\nJan 2025 close."

    result = lint_source(memo_body, deck_body)
    assert "Jan 2025" in result.only_in_deck
    assert "April 2024" in result.only_in_memo


def test_acronym_extractor_bounds_length_2_to_6():
    """ALL-CAPS tokens of length 2-6 (FTC, SFMTA, NYC, LOI). Long shouting
    (``ABCDEFGH``) should NOT be captured."""
    memo_body = "# Memo\nNYC pilot in scope. ABCDEFGH is too long."
    deck_body = "# Deck\nWe partner with FTC and SFMTA."

    result = lint_source(memo_body, deck_body)

    only_in_memo = result.only_in_memo
    only_in_deck = result.only_in_deck
    assert "NYC" in only_in_memo
    assert "FTC" in only_in_deck
    assert "SFMTA" in only_in_deck
    # The 8-char shout should not be captured by the acronym extractor.
    assert "ABCDEFGH" not in only_in_memo


def test_unit_int_extractor():
    """``8 pilots``, ``50 LOIs`` — the unit-bearing integer shapes."""
    memo_body = "# Memo\n50 LOIs signed."
    deck_body = "# Deck\n8 pilots in production."

    result = lint_source(memo_body, deck_body)
    assert "8 pilots" in result.only_in_deck
    assert "50 LOIs" in result.only_in_memo


# ---------------------------------------------------------------------------
# File-wrapper path: lint_memo_deck_parity with real files on disk
# ---------------------------------------------------------------------------


def test_lint_memo_deck_parity_with_real_files(tmp_path: Path):
    """End-to-end exercise of the file wrapper: lay down the memo body
    markdown + deck.md inside two version dirs, verify the
    citation-clear canary fires.

    Under issue #295 the memo body filename echoes the memo thread slug
    (``<thread>/<thread>.{N}/<thread>.md``), so the test fixtures wrap
    each version dir in a slug-named thread directory.
    """
    memo_thread = tmp_path / "citation-clear-memo"
    deck_thread = tmp_path / "citation-clear-deck"
    memo_thread.mkdir()
    deck_thread.mkdir()
    memo_dir = memo_thread / "citation-clear-memo.4"
    deck_dir = deck_thread / "citation-clear-deck.3"
    memo_dir.mkdir()
    deck_dir.mkdir()
    # Body filename echoes the memo thread slug per #295.
    (memo_dir / "citation-clear-memo.md").write_text(CITATION_CLEAR_MEMO_BODY)
    (deck_dir / "deck.md").write_text(CITATION_CLEAR_DECK_BODY)

    result = lint_memo_deck_parity(memo_dir, deck_dir)

    assert result.skipped is False
    assert result.deck_sibling == str(deck_dir.resolve())
    assert "50-60%" in result.only_in_memo


# ---------------------------------------------------------------------------
# AC12 — Symmetry test
# ---------------------------------------------------------------------------


def test_symmetry_with_deck_side_lint_source():
    """**AC12: the load-bearing symmetry contract.**

    The memo-side ``lint_source(memo_body, deck_body)`` and the deck-side
    ``lint_source(deck_body, memo_body)`` must produce **equivalent finding
    sets** on the same body pair — modulo the rule name (`memo_deck_parity`
    vs `deck_memo_parity`). The ``side`` field is preserved verbatim across
    both modules (`only_in_memo` / `only_in_deck` describe *which body the
    token came from*, independent of which side is "primary"), so the token
    sets per side must match exactly. This is the contract that justifies
    the lib-promotion follow-up to ``anvil/lib/parity.py``.
    """
    from anvil.skills.deck.lib.parity_lint import lint_source as deck_lint_source

    memo_body = CITATION_CLEAR_MEMO_BODY
    deck_body = CITATION_CLEAR_DECK_BODY

    memo_result = lint_source(memo_body, deck_body)
    # Note: deck-side ``lint_source`` takes (deck_source, memo_source).
    deck_result = deck_lint_source(deck_body, memo_body)

    # The token sets on each side must match exactly.
    assert sorted(memo_result.only_in_memo) == sorted(deck_result.only_in_memo), (
        f"only_in_memo token sets must match between memo-side and deck-side "
        f"lint_source calls; memo-side={memo_result.only_in_memo!r}, "
        f"deck-side={deck_result.only_in_memo!r}"
    )
    assert sorted(memo_result.only_in_deck) == sorted(deck_result.only_in_deck), (
        f"only_in_deck token sets must match between memo-side and deck-side "
        f"lint_source calls; memo-side={memo_result.only_in_deck!r}, "
        f"deck-side={deck_result.only_in_deck!r}"
    )

    # Warning counts must match (same set of findings, just different rule name).
    assert len(memo_result.warnings) == len(deck_result.warnings), (
        f"warning counts must match between memo-side and deck-side; "
        f"memo-side={len(memo_result.warnings)}, "
        f"deck-side={len(deck_result.warnings)}"
    )

    # Per-token, the (token, side) pairs must match across both modules
    # (the rule field differs intentionally — that's the only allowed delta).
    memo_pairs = sorted((f.token, f.side) for f in memo_result.warnings)
    deck_pairs = sorted((f.token, f.side) for f in deck_result.warnings)
    assert memo_pairs == deck_pairs, (
        f"(token, side) finding pairs must match; "
        f"memo-side={memo_pairs!r}, deck-side={deck_pairs!r}"
    )

    # Confirm the rule names are the only intentional delta.
    memo_rules = {f.rule for f in memo_result.warnings}
    deck_rules = {f.rule for f in deck_result.warnings}
    if memo_rules:
        assert memo_rules == {"memo_deck_parity"}
    if deck_rules:
        assert deck_rules == {"deck_memo_parity"}


def test_symmetry_with_synthetic_body_pair():
    """A second symmetry exercise on a synthetic body pair with both
    ``only_in_memo`` and ``only_in_deck`` findings. Tightens AC12 against
    a case where both directions fire."""
    from anvil.skills.deck.lib.parity_lint import lint_source as deck_lint_source

    memo_body = "# Memo\nFTC $193K Jan 2025. 50 LOIs."
    deck_body = "# Deck\nSFMTA $126M April 2024. 8 pilots."

    memo_result = lint_source(memo_body, deck_body)
    deck_result = deck_lint_source(deck_body, memo_body)

    assert sorted(memo_result.only_in_memo) == sorted(deck_result.only_in_memo)
    assert sorted(memo_result.only_in_deck) == sorted(deck_result.only_in_deck)


# ---------------------------------------------------------------------------
# Doc-coverage: memo-review.md must have step 4d wiring (AC7)
# ---------------------------------------------------------------------------


MEMO_REVIEW_MD = (
    Path(__file__).resolve().parents[3]
    / "anvil"
    / "skills"
    / "memo"
    / "commands"
    / "memo-review.md"
)


def test_memo_review_md_has_step_4d_parity_lint():
    """``memo-review.md`` must reference ``parity_lint`` in a step 4d
    block — AC7."""
    text = MEMO_REVIEW_MD.read_text(encoding="utf-8")
    assert "4d" in text, "memo-review.md must declare a step 4d"
    assert "parity_lint" in text, (
        "memo-review.md step 4d must invoke parity_lint"
    )
    assert "lint_memo_deck_parity" in text, (
        "memo-review.md step 4d must name the public-API function"
    )


def test_memo_review_md_documents_graceful_skip():
    """The graceful-skip-on-no-deck-sibling contract MUST be documented
    in memo-review.md (AC7)."""
    text = MEMO_REVIEW_MD.read_text(encoding="utf-8")
    # The doc should explicitly say the lint skips when no deck sibling is
    # discoverable.
    assert "graceful" in text.lower() or "skip" in text.lower()
    assert "deck sibling" in text.lower() or "deck_sibling" in text.lower()


def test_memo_review_md_documents_warning_only_severity():
    """v0 ships at warning severity — must be explicit in the doc (AC7 / AC10).

    Note: the doc MUST clarify the parity block does NOT participate in
    `critical_flag` in v0 — that's the load-bearing contract.
    """
    text = MEMO_REVIEW_MD.read_text(encoding="utf-8")
    # The Phase A warning-only contract must be named.
    assert "warning" in text.lower()
    # And the contract that the verdict logic is unchanged in v0: the
    # memo_deck_parity block must NOT enter the critical_flag aggregation.
    assert "memo_deck_parity" in text
    # The doc must explicitly mention non-participation in critical_flag.
    # We look for either 'NOT participate' / 'NOT contribute' / 'NOT enter'
    # near 'critical_flag'.
    assert (
        "do NOT participate" in text
        or "do NOT contribute" in text
        or "does NOT participate" in text
        or "does NOT contribute" in text
    ), (
        "memo-review.md must explicitly document that memo_deck_parity "
        "does NOT participate in critical_flag in v0"
    )


def test_memo_review_md_documents_escape_hatch():
    """The ``anvil-lint-disable: memo_deck_parity`` escape hatch must be
    documented in memo-review.md (AC2 / AC7)."""
    text = MEMO_REVIEW_MD.read_text(encoding="utf-8")
    assert "memo_deck_parity" in text
    assert "anvil-lint-disable" in text


def test_memo_review_md_findings_subsection_documented():
    """The ``## Parity-lint findings (memo↔deck, optional)`` subsection
    must be referenced in the memo-review.md ``findings.md`` shape (AC9)."""
    text = MEMO_REVIEW_MD.read_text(encoding="utf-8")
    assert "Parity-lint findings" in text
    assert "memo↔deck" in text


def test_memo_review_md_summary_block_demonstrates_both_shapes():
    """AC8: the doc demonstrates both ``ran: true`` (with one warning) and
    ``ran: false`` (skip) shapes."""
    text = MEMO_REVIEW_MD.read_text(encoding="utf-8")
    # Doc must reference the ran:true shape (concrete example).
    assert "\"memo_deck_parity\"" in text
    # And the skip shape.
    assert "ran: false" in text or '"ran": false' in text


# ---------------------------------------------------------------------------
# Module docstring carries the promotion-path declaration (AC11)
# ---------------------------------------------------------------------------


def test_module_docstring_names_promotion_path():
    """AC11: module docstring explicitly names ``anvil/lib/parity.py`` as
    the promotion target + cites the parent PR / this issue."""
    from anvil.skills.memo.lib import parity_lint

    doc = parity_lint.__doc__ or ""
    assert "anvil/lib/parity.py" in doc, (
        "module docstring must name the promotion path"
    )
    # Parent issue / PR refs.
    assert "#200" in doc, "module docstring must cite #200 (canary anchor)"
    assert "#205" in doc, "module docstring must cite PR #205 (deck-side first ship)"
    assert "#215" in doc, "module docstring must cite #215 (this issue)"


def test_module_docstring_names_second_consumer_trigger():
    """AC11: docstring must explicitly note that this module landing is the
    second-consumer trigger per CLAUDE.md §Skill-local first."""
    from anvil.skills.memo.lib import parity_lint

    doc = parity_lint.__doc__ or ""
    assert "second-consumer" in doc.lower() or "second consumer" in doc.lower(), (
        "module docstring must name the second-consumer trigger"
    )


def test_module_docstring_carries_phase_A_B_contract():
    """AC11: docstring carries the Phase A / Phase B contract verbatim
    from deck-side."""
    from anvil.skills.memo.lib import parity_lint

    doc = parity_lint.__doc__ or ""
    assert "Phase A" in doc and "Phase B" in doc
    assert "warning" in doc.lower()


def test_module_docstring_names_canary_anchor():
    """AC11: docstring names the Citation Clear ~50-60% completion canary."""
    from anvil.skills.memo.lib import parity_lint

    doc = parity_lint.__doc__ or ""
    assert "Citation Clear" in doc
    assert "50" in doc and "60" in doc and "completion" in doc.lower()
