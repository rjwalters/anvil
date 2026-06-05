"""Unit tests for ``anvil/lib/parity.py`` — the shared parity-lint primitive.

Per issue #317 (the second-consumer-trigger promotion of the two skill-local
``parity_lint.py`` mirrors), this file covers the shared library directly:
extractor surface, normalization, escape-hatch, graceful-skip, symmetry
contract, and the unified ``lint_parity`` wrapper.

The skill-local test files (``tests/skills/deck/test_parity_lint.py``,
``tests/skills/memo/test_memo_parity_lint.py``) continue to exercise the
skill-local re-exports — this file is the defensive coverage at the
shared-module layer.

Per the #58 per-file packaging convention, ``tests/lib/__init__.py`` is in
place so this filename does not collide with ``tests/skills/*/test_*.py``
during pytest collection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.lib.parity import (
    EXTRACTORS,
    Finding,
    LintResult,
    RULES_DECK,
    RULES_MEMO,
    UNIT_VOCABULARY,
    lint_deck_memo_parity,
    lint_memo_deck_parity,
    lint_parity,
    lint_source,
)


# ---------------------------------------------------------------------------
# Module shape — public surface
# ---------------------------------------------------------------------------


def test_rules_constants_carry_per_side_labels():
    """The two RULES tuples preserve the per-side rule labels documented
    in the two ``*-review.md`` command files."""
    assert RULES_DECK == ("deck_memo_parity",)
    assert RULES_MEMO == ("memo_deck_parity",)


def test_extractors_cover_required_classes():
    """Money / percent / quarter_fy / month_year / acronym / unit_int."""
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
    completion) that drove the v0 scope."""
    assert "LOIs" in UNIT_VOCABULARY
    assert "pilots" in UNIT_VOCABULARY
    assert "completion" in UNIT_VOCABULARY


def test_lint_result_has_both_sibling_fields():
    """``LintResult`` carries BOTH ``memo_sibling`` and ``deck_sibling``
    after promotion. Deck-side wrapper sets the former; memo-side wrapper
    sets the latter; both default to ``None``."""
    result = LintResult()
    assert hasattr(result, "memo_sibling")
    assert hasattr(result, "deck_sibling")
    assert result.memo_sibling is None
    assert result.deck_sibling is None


def test_summary_carries_both_sibling_fields():
    """``LintResult.to_summary()`` includes both sibling fields so neither
    skill's ``_summary.md`` schema breaks."""
    result = LintResult()
    summary = result.to_summary()
    assert "memo_sibling" in summary
    assert "deck_sibling" in summary


# ---------------------------------------------------------------------------
# Citation-clear canary regression — ported from both skill-local suites
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


def test_citation_clear_canary_50_60_percent_completion_flagged_deck_rule():
    """**The load-bearing regression test for issue #200.**

    Memo body contains the insurer benchmark ``~50–60% completion`` that the
    deck body lacks. With ``rule="deck_memo_parity"`` (the default), the
    finding must surface as ``only_in_memo`` and the diagnostic must name
    the Citation Clear canary anchor.
    """
    result = lint_source(CITATION_CLEAR_DECK_BODY, CITATION_CLEAR_MEMO_BODY)

    only_in_memo = result.only_in_memo
    assert "50-60%" in only_in_memo, (
        f"expected `50-60%` in only_in_memo; got {only_in_memo!r}"
    )

    canary_findings = [f for f in result.warnings if f.token == "50-60%"]
    assert len(canary_findings) == 1
    assert canary_findings[0].severity == "warning"
    assert canary_findings[0].side == "only_in_memo"
    assert canary_findings[0].rule == "deck_memo_parity"
    # Deck-side canary-anchor wording.
    assert "Citation Clear" in canary_findings[0].message


def test_citation_clear_only_in_deck_direction_flagged_memo_rule():
    """The symmetric load-bearing canary direction from the memo POV
    (issue #215): deck has a hard claim the memo lacks → ``only_in_deck``
    warning with the memo-side canary anchor wording."""
    memo_body = "# Memo\nGeneral overview only — no benchmarks called out.\n"
    deck_body = "# Deck\nInsurer benchmark study showed ~50–60% completion.\n"

    # Memo-side direction: pass sources in deck/memo positional order with
    # rule="memo_deck_parity" — this is the same dispatch the memo-side
    # re-export wrapper performs.
    result = lint_source(deck_body, memo_body, rule="memo_deck_parity")

    only_in_deck = result.only_in_deck
    assert "50-60%" in only_in_deck, (
        f"expected `50-60%` in only_in_deck; got {only_in_deck!r}"
    )

    canary_findings = [f for f in result.warnings if f.token == "50-60%"]
    assert len(canary_findings) == 1
    assert canary_findings[0].side == "only_in_deck"
    assert canary_findings[0].rule == "memo_deck_parity"
    # Memo-side canary-anchor wording (different from deck-side).
    assert "Citation Clear" in canary_findings[0].message


# ---------------------------------------------------------------------------
# Canary-message wordings preserved verbatim across both rules
# ---------------------------------------------------------------------------


def test_deck_side_canary_message_preserves_verbatim_wording():
    """Deck-side ``only_in_memo`` message names ``memo.4 introduced a``
    canary anchor verbatim from the pre-promotion module."""
    result = lint_source(CITATION_CLEAR_DECK_BODY, CITATION_CLEAR_MEMO_BODY)
    canary = [f for f in result.warnings if f.token == "50-60%"]
    assert len(canary) == 1
    # The exact substring is grep-pinned by the deck-side skill test.
    assert "memo.4 introduced a" in canary[0].message


def test_memo_side_canary_message_preserves_verbatim_wording():
    """Memo-side ``only_in_deck`` message names ``memo.4 ↔ deck.3 — the
    symmetric direction`` verbatim from the pre-promotion module."""
    memo_body = "# Memo\nNo benchmarks here.\n"
    deck_body = "# Deck\nInsurer ~50–60% completion benchmark.\n"
    result = lint_source(deck_body, memo_body, rule="memo_deck_parity")

    canary = [f for f in result.warnings if f.token == "50-60%"]
    assert len(canary) == 1
    # The exact substring distinguishes memo-side from deck-side wording.
    assert "the symmetric direction" in canary[0].message


# ---------------------------------------------------------------------------
# Graceful-skip path
# ---------------------------------------------------------------------------


def test_lint_deck_memo_parity_graceful_skip_no_sibling(tmp_path: Path):
    """Deck-side wrapper graceful-skips when ``memo_version_dir=None``."""
    deck_version_dir = tmp_path / "thread.1"
    deck_version_dir.mkdir()
    (deck_version_dir / "deck.md").write_text("# Deck\n")

    result = lint_deck_memo_parity(deck_version_dir, None)
    assert result.skipped is True
    assert result.memo_sibling is None
    assert result.deck_sibling is None
    assert "no memo sibling" in result.reason.lower()
    assert result.total == 0


def test_lint_memo_deck_parity_graceful_skip_no_sibling(tmp_path: Path):
    """Memo-side wrapper graceful-skips when ``deck_version_dir=None``."""
    thread = tmp_path / "thread"
    thread.mkdir()
    memo_version_dir = thread / "thread.1"
    memo_version_dir.mkdir()
    (memo_version_dir / "thread.md").write_text("# Memo\n")

    result = lint_memo_deck_parity(memo_version_dir, None)
    assert result.skipped is True
    assert result.deck_sibling is None
    assert result.memo_sibling is None
    assert "no deck sibling" in result.reason.lower()
    assert result.total == 0


# ---------------------------------------------------------------------------
# Escape-hatch path
# ---------------------------------------------------------------------------


def test_escape_hatch_downgrades_finding_to_info_deck_rule():
    """``<!-- anvil-lint-disable: deck_memo_parity -->`` downgrades a
    deck-only finding to ``info`` under the deck-side rule."""
    deck_body = (
        "# Deck\n"
        "We considered the FTC enforcement angle. <!-- anvil-lint-disable: deck_memo_parity -->\n"
    )
    memo_body = "# Memo\n(this body deliberately omits the acronym.)\n"
    result = lint_source(deck_body, memo_body, rule="deck_memo_parity")

    info_tokens = {f.token for f in result.infos}
    warning_tokens = {f.token for f in result.warnings}
    assert "FTC" in info_tokens
    assert "FTC" not in warning_tokens


def test_escape_hatch_downgrades_finding_to_info_memo_rule():
    """``<!-- anvil-lint-disable: memo_deck_parity -->`` downgrades a
    memo-only finding to ``info`` under the memo-side rule."""
    memo_body = (
        "# Memo\n"
        "We considered the FTC angle. <!-- anvil-lint-disable: memo_deck_parity -->\n"
    )
    deck_body = "# Deck\n(this body deliberately omits the acronym.)\n"
    # Memo-side wrapper dispatch.
    result = lint_source(deck_body, memo_body, rule="memo_deck_parity")

    info_tokens = {f.token for f in result.infos}
    warning_tokens = {f.token for f in result.warnings}
    assert "FTC" in info_tokens
    assert "FTC" not in warning_tokens


def test_escape_hatch_rule_label_is_scoped():
    """A directive targeting a different rule label does NOT downgrade
    findings for the active rule — the per-side rule labels are
    distinct."""
    deck_body = (
        "# Deck\n"
        "FTC angle. <!-- anvil-lint-disable: memo_deck_parity -->\n"
    )
    memo_body = "# Memo\n"
    # Running under deck-side rule: the memo-side directive is ignored.
    result = lint_source(deck_body, memo_body, rule="deck_memo_parity")
    warning_tokens = {f.token for f in result.warnings}
    assert "FTC" in warning_tokens, (
        "deck_memo_parity rule must not honor memo_deck_parity disable directive"
    )


# ---------------------------------------------------------------------------
# Symmetry contract — the load-bearing AC6 of the promotion
# ---------------------------------------------------------------------------


def test_symmetry_contract_token_sets_match_across_rules():
    """The shared core produces the same token sets on each side
    regardless of which rule label is selected — rule names are the only
    intentional delta. This is the contract that justified the promotion."""
    deck_result = lint_source(
        CITATION_CLEAR_DECK_BODY,
        CITATION_CLEAR_MEMO_BODY,
        rule="deck_memo_parity",
    )
    memo_result = lint_source(
        CITATION_CLEAR_DECK_BODY,
        CITATION_CLEAR_MEMO_BODY,
        rule="memo_deck_parity",
    )

    assert sorted(deck_result.only_in_memo) == sorted(memo_result.only_in_memo)
    assert sorted(deck_result.only_in_deck) == sorted(memo_result.only_in_deck)

    # Rule labels are the only delta on each Finding.
    deck_rules = {f.rule for f in deck_result.warnings}
    memo_rules = {f.rule for f in memo_result.warnings}
    if deck_rules:
        assert deck_rules == {"deck_memo_parity"}
    if memo_rules:
        assert memo_rules == {"memo_deck_parity"}


# ---------------------------------------------------------------------------
# Unified wrapper — ``lint_parity``
# ---------------------------------------------------------------------------


def _make_citation_clear_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Helper: lay down both version dirs with the citation-clear bodies."""
    deck_thread = tmp_path / "citation-clear-deck"
    memo_thread = tmp_path / "citation-clear-memo"
    deck_thread.mkdir()
    memo_thread.mkdir()
    deck_dir = deck_thread / "citation-clear-deck.3"
    memo_dir = memo_thread / "citation-clear-memo.4"
    deck_dir.mkdir()
    memo_dir.mkdir()
    (deck_dir / "deck.md").write_text(CITATION_CLEAR_DECK_BODY)
    (memo_dir / "citation-clear-memo.md").write_text(CITATION_CLEAR_MEMO_BODY)
    return deck_dir, memo_dir


def test_lint_parity_deck_primary_dispatches_to_deck_wrapper(tmp_path: Path):
    """``lint_parity(deck_path, memo_path, primary_kind="deck", sibling_kind="memo")``
    must equal ``lint_deck_memo_parity(deck_path, memo_path)``."""
    deck_dir, memo_dir = _make_citation_clear_pair(tmp_path)

    via_unified = lint_parity(
        deck_dir, memo_dir, primary_kind="deck", sibling_kind="memo"
    )
    via_direct = lint_deck_memo_parity(deck_dir, memo_dir)

    assert via_unified.skipped == via_direct.skipped
    assert sorted(via_unified.only_in_memo) == sorted(via_direct.only_in_memo)
    assert sorted(via_unified.only_in_deck) == sorted(via_direct.only_in_deck)
    # Both produce the canary anchor.
    assert "50-60%" in via_unified.only_in_memo
    # Deck-side wrapper sets memo_sibling.
    assert via_unified.memo_sibling == str(memo_dir.resolve())


def test_lint_parity_memo_primary_dispatches_to_memo_wrapper(tmp_path: Path):
    """``lint_parity(memo_path, deck_path, primary_kind="memo", sibling_kind="deck")``
    must equal ``lint_memo_deck_parity(memo_path, deck_path)``."""
    deck_dir, memo_dir = _make_citation_clear_pair(tmp_path)

    via_unified = lint_parity(
        memo_dir, deck_dir, primary_kind="memo", sibling_kind="deck"
    )
    via_direct = lint_memo_deck_parity(memo_dir, deck_dir)

    assert via_unified.skipped == via_direct.skipped
    assert sorted(via_unified.only_in_memo) == sorted(via_direct.only_in_memo)
    assert sorted(via_unified.only_in_deck) == sorted(via_direct.only_in_deck)
    # Memo-side wrapper sets deck_sibling.
    assert via_unified.deck_sibling == str(deck_dir.resolve())


def test_lint_parity_unsupported_pair_raises_value_error(tmp_path: Path):
    """``lint_parity`` rejects same-kind pairs (e.g., memo↔memo)."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    with pytest.raises(ValueError, match="unsupported parity pair"):
        lint_parity(a, b, primary_kind="memo", sibling_kind="memo")


# ---------------------------------------------------------------------------
# Phase A severity contract
# ---------------------------------------------------------------------------


def test_phase_A_emits_warnings_only_never_errors():
    """v0 ships at warning severity. ``errors`` MUST be empty on every code
    path so the host review's ``lint_critical_flag`` aggregation is
    untouched."""
    deck_body = "# Deck\n$50M ARR, Q1 FY24."
    memo_body = "# Memo\n$60M ARR, Q2 FY25, FTC angle."
    result = lint_source(deck_body, memo_body)
    assert result.errors == []
    for f in result.warnings:
        assert f.severity == "warning"


# ---------------------------------------------------------------------------
# Re-export compatibility — both skill-local modules dispatch into shared core
# ---------------------------------------------------------------------------


def test_skill_local_re_exports_share_identity():
    """The two skill-local ``Finding`` / ``LintResult`` symbols must be
    the SAME objects as the shared module's — confirms the re-export is
    a real re-export, not a forked redefinition."""
    from anvil.skills.deck.lib import parity_lint as deck_side
    from anvil.skills.memo.lib import parity_lint as memo_side

    assert deck_side.Finding is Finding
    assert memo_side.Finding is Finding
    assert deck_side.LintResult is LintResult
    assert memo_side.LintResult is LintResult
    assert deck_side.EXTRACTORS is EXTRACTORS
    assert memo_side.EXTRACTORS is EXTRACTORS
    assert deck_side.UNIT_VOCABULARY is UNIT_VOCABULARY
    assert memo_side.UNIT_VOCABULARY is UNIT_VOCABULARY


def test_memo_side_lint_source_wrapper_flips_arg_order():
    """The memo-side ``lint_source`` wrapper takes ``(memo_source,
    deck_source)`` positionally — the asymmetry exploited by the
    symmetry test in ``tests/skills/memo/test_memo_parity_lint.py``.
    Same canary body pair, deck-side and memo-side wrappers must produce
    matching ``(token, side)`` finding pairs."""
    from anvil.skills.deck.lib.parity_lint import lint_source as deck_lint_source
    from anvil.skills.memo.lib.parity_lint import lint_source as memo_lint_source

    memo_body = CITATION_CLEAR_MEMO_BODY
    deck_body = CITATION_CLEAR_DECK_BODY

    deck_result = deck_lint_source(deck_body, memo_body)
    memo_result = memo_lint_source(memo_body, deck_body)

    deck_pairs = sorted((f.token, f.side) for f in deck_result.warnings)
    memo_pairs = sorted((f.token, f.side) for f in memo_result.warnings)
    assert deck_pairs == memo_pairs
