"""Unit tests for ``anvil/lib/revise_consistency.py``.

Each fixture is a self-contained directory under
``tests/lib/fixtures/revise_consistency/<name>/`` with distinct
filenames per the #58 fixture-naming convention (no ``deck.md``
collision across fixtures — the source artifacts are named
``deck_old.md`` / ``deck_new.md`` and companion files have unique
names per fixture).

The 9 fixtures map 1:1 to the cases the curator pinned on issue #113.

Test module filename is distinct from other ``tests/lib/test_*``
modules per #58 (``test_revise_consistency.py`` vs the existing
``test_render_gate.py`` / ``test_critics.py`` / ...).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.lib.review_schema import Kind
from anvil.lib.revise_consistency import (
    DEFAULT_COMPANION_GLOBS,
    DEFAULT_IGNORE_TOKENS,
    DEFAULT_TOKEN_SET,
    DIM_CONSISTENCY,
    SWEEP_NAME,
    ConsistencyResult,
    StaleFinding,
    TokenSet,
    sweep,
)


FIXTURES = Path(__file__).parent / "fixtures" / "revise_consistency"


# -----------------------------------------------------------------------------
# Fixture-loading helpers
# -----------------------------------------------------------------------------


def _fixture_dir(name: str) -> Path:
    p = FIXTURES / name
    assert p.exists(), f"missing fixture dir: {p}"
    return p


# -----------------------------------------------------------------------------
# 1. Positive — money token removed, present in figure script.
# -----------------------------------------------------------------------------


def test_bower_chart_caption_stale_emits_finding():
    """deck_old has $54B+; deck_new has $25.9B; figure_caption.py still has $54B+.

    Mirrors the bower.v3 canary repro from the issue body. Expect 1
    finding naming the figure_caption.py path and the $54B+ token.
    """
    d = _fixture_dir("bower_chart_caption_stale")
    result = sweep(
        old_source=d / "deck_old.md",
        new_source=d / "deck_new.md",
        companion_files=[d / "figure_caption.py"],
    )
    assert not result.passed()
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.token == "$54B+"
    assert "figure_caption.py" in finding.companion_file
    assert finding.line >= 1
    # The new source should no longer contain the stale token; the
    # rationale should mention both filenames.
    assert "deck_new.md" in finding.rationale
    assert "figure_caption.py" in finding.rationale


# -----------------------------------------------------------------------------
# 2. Negative — token unchanged across versions.
# -----------------------------------------------------------------------------


def test_token_unchanged_no_finding():
    """Token present in both deck.md versions and in companion → 0 findings.

    Exercises safety rule #1: only-removed-tokens-are-candidates.
    """
    d = _fixture_dir("token_unchanged_no_finding")
    result = sweep(
        old_source=d / "deck_old.md",
        new_source=d / "deck_new.md",
        companion_files=[d / "figure_caption.py"],
    )
    assert result.passed()
    assert result.findings == []
    # The unchanged $25.9B token should NOT be in the removed set.
    assert "$25.9B" not in result.removed_tokens


# -----------------------------------------------------------------------------
# 3. Negative — token in allowlist.
# -----------------------------------------------------------------------------


def test_allowlist_year_no_finding():
    """Removed token suppressed because it's in ``ignore_tokens``.

    The deck removes ``25%`` (so the token IS removed); the companion
    still references it; the allowlist suppresses the finding.
    """
    d = _fixture_dir("allowlist_year_no_finding")
    result = sweep(
        old_source=d / "deck_old.md",
        new_source=d / "deck_new.md",
        companion_files=[d / "companion.md"],
        ignore_tokens=frozenset({"25%"}),
    )
    assert result.passed()
    assert result.findings == []
    # The allowlisted token should NOT be in the removed_tokens set
    # because the allowlist filter happens before the surviving filter.
    assert "25%" not in result.removed_tokens


def test_allowlist_default_is_empty():
    """``DEFAULT_IGNORE_TOKENS`` is empty — same fixture without allowlist fires."""
    d = _fixture_dir("allowlist_year_no_finding")
    result = sweep(
        old_source=d / "deck_old.md",
        new_source=d / "deck_new.md",
        companion_files=[d / "companion.md"],
    )
    assert not result.passed()
    assert any(f.token == "25%" for f in result.findings)


# -----------------------------------------------------------------------------
# 4. Negative — token survives in new (moved within file).
# -----------------------------------------------------------------------------


def test_token_survives_in_new_no_finding():
    """Token removed from one slide but appears in another within deck_new.md.

    Exercises safety rule #2: surviving-tokens-in-new filter. The
    token's literal text is still in ``new_source``, so even though
    its regex match position shifted, it is not a stale-token finding.
    """
    d = _fixture_dir("token_survives_in_new_no_finding")
    result = sweep(
        old_source=d / "deck_old.md",
        new_source=d / "deck_new.md",
        companion_files=[d / "figure_caption.py"],
    )
    assert result.passed()
    assert result.findings == []
    # The token regex-extracted from old_source IS in the initial
    # removed set but is then filtered out by the surviving-in-new
    # rule. After filtering, removed_tokens (which is the
    # filtered/candidate set) should not contain it.
    assert "$54B+" not in result.removed_tokens


# -----------------------------------------------------------------------------
# 5. Multi-file — same removed token in 3 companions.
# -----------------------------------------------------------------------------


def test_multi_file_multi_finding():
    """Same removed token in 3 companions → 3 findings, one per companion."""
    d = _fixture_dir("multi_file_multi_finding")
    companions = [d / "chart_a.py", d / "chart_b.py", d / "chart_c.mmd"]
    result = sweep(
        old_source=d / "deck_old.md",
        new_source=d / "deck_new.md",
        companion_files=companions,
    )
    assert not result.passed()
    assert len(result.findings) == 3
    files_flagged = {Path(f.companion_file).name for f in result.findings}
    assert files_flagged == {"chart_a.py", "chart_b.py", "chart_c.mmd"}
    # All three findings should name the same removed token.
    assert all(f.token == "$54B+" for f in result.findings)


# -----------------------------------------------------------------------------
# 6. Speaker-notes case (sub-case b — draftwell canary).
# -----------------------------------------------------------------------------


def test_draftwell_speaker_notes_stale():
    """deck_new SAM `$0.8-1.5B/yr`; speaker_notes still has `$2-4B`.

    Exercises sub-case (b) and the range tokenizer specifically:
    ``$2-4B`` is a money-range with hyphen; ``$0.8-1.5B`` is the
    replacement range. The replacement is parsed as a range (so
    extracting tokens from ``deck_new`` finds ``$0.8-1.5B``); the old
    ``$2-4B`` is removed and absent from new. The speaker_notes
    references ``$2-4B`` → 1 finding.
    """
    d = _fixture_dir("draftwell_speaker_notes_stale")
    result = sweep(
        old_source=d / "deck_old.md",
        new_source=d / "deck_new.md",
        companion_files=[d / "speaker_notes.md"],
    )
    assert not result.passed()
    assert len(result.findings) >= 1
    # The headline stale token: $2-4B should be flagged on speaker_notes.md.
    flagged_tokens = {f.token for f in result.findings}
    assert "$2-4B" in flagged_tokens
    speaker_notes_findings = [
        f for f in result.findings if "speaker_notes.md" in f.companion_file
    ]
    assert len(speaker_notes_findings) >= 1


# -----------------------------------------------------------------------------
# 7. Range with en-dash.
# -----------------------------------------------------------------------------


def test_en_dash_range_detected():
    """``$25–33M`` (en-dash) removed → figure with en-dash range flagged.

    The deck_new has ``$25-30M`` (hyphen); the figure still has the
    old ``$25–33M`` (en-dash). Different strings, so the en-dash
    token is fully removed (and not a surviving literal substring).
    """
    d = _fixture_dir("en_dash_range")
    result = sweep(
        old_source=d / "deck_old.md",
        new_source=d / "deck_new.md",
        companion_files=[d / "figure_caption.py"],
    )
    assert not result.passed()
    # The en-dash version should be in the findings.
    flagged_tokens = {f.token for f in result.findings}
    assert "$25–33M" in flagged_tokens


# -----------------------------------------------------------------------------
# 8. Empty case — no removed tokens.
# -----------------------------------------------------------------------------


def test_empty_no_findings_passes_clean():
    """No priced-number tokens in either source → clean pass; no findings."""
    d = _fixture_dir("empty_no_findings")
    result = sweep(
        old_source=d / "deck_old.md",
        new_source=d / "deck_new.md",
        companion_files=[d / "figure_caption.py"],
    )
    assert result.passed() is True
    assert result.findings == []
    assert result.removed_tokens == frozenset()


# -----------------------------------------------------------------------------
# 9. to_review shape.
# -----------------------------------------------------------------------------


def test_to_review_emits_tool_evidence_kind():
    """ConsistencyResult.to_review() returns Review(kind=TOOL_EVIDENCE).

    Findings → one Finding per StaleFinding with severity='minor',
    dimension='consistency', and tool_calls=[] (to satisfy the
    Kind.TOOL_EVIDENCE schema validator).
    """
    d = _fixture_dir("to_review_shape")
    result = sweep(
        old_source=d / "deck_old.md",
        new_source=d / "deck_new.md",
        companion_files=[d / "figure_caption.py"],
    )
    assert not result.passed()

    review = result.to_review(
        version_dir="to_review_shape.1", critic_id="revise-consistency"
    )

    assert review.kind == Kind.TOOL_EVIDENCE
    assert review.version_dir == "to_review_shape.1"
    assert review.critic_id == "revise-consistency"
    # One null-scored Score so the scorecard isn't empty (schema
    # requires non-empty scores list).
    assert len(review.scores) == 1
    assert review.scores[0].score is None
    assert review.scores[0].dimension == SWEEP_NAME
    # No critical flags emitted (warn-only contract).
    assert review.critical_flags == []
    # One Finding per StaleFinding.
    assert len(review.findings) == len(result.findings)
    for finding in review.findings:
        assert finding.severity == "minor"
        assert finding.dimension == DIM_CONSISTENCY
        # Kind.TOOL_EVIDENCE requires tool_calls on every finding.
        assert finding.tool_calls == []
        assert finding.evidence_span is not None
        assert ":L" in finding.evidence_span


# -----------------------------------------------------------------------------
# Public-API surface tests (smoke + invariants beyond the 9 fixtures)
# -----------------------------------------------------------------------------


def test_default_token_set_covers_all_four_classes():
    """``DEFAULT_TOKEN_SET`` exposes money, money_range, percent, percent_range."""
    assert DEFAULT_TOKEN_SET.money
    assert DEFAULT_TOKEN_SET.money_range
    assert DEFAULT_TOKEN_SET.percent
    assert DEFAULT_TOKEN_SET.percent_range
    # All four patterns should be in patterns().
    patterns = DEFAULT_TOKEN_SET.patterns()
    assert len(patterns) == 4


def test_default_companion_globs_includes_latex_for_forward_compat():
    """``DEFAULT_COMPANION_GLOBS`` covers .py/.csv/.mmd (deck) + .tex (latex)."""
    assert "*.py" in DEFAULT_COMPANION_GLOBS
    assert "*.csv" in DEFAULT_COMPANION_GLOBS
    assert "*.mmd" in DEFAULT_COMPANION_GLOBS
    # .tex is dormant until LaTeX skills adopt; documented in module docstring.
    assert "*.tex" in DEFAULT_COMPANION_GLOBS
    # .md included for the speaker-notes case.
    assert "*.md" in DEFAULT_COMPANION_GLOBS


def test_default_ignore_tokens_is_empty_frozenset():
    """``DEFAULT_IGNORE_TOKENS`` is an empty frozenset (operator-extendable)."""
    assert DEFAULT_IGNORE_TOKENS == frozenset()


def test_sweep_missing_companion_silently_skipped(tmp_path):
    """Missing companion file → silently skipped, no exception."""
    old = tmp_path / "old.md"
    old.write_text("Slide A: $54B+ figure.\n")
    new = tmp_path / "new.md"
    new.write_text("Slide A: $25B figure.\n")
    missing = tmp_path / "does_not_exist.py"

    result = sweep(old_source=old, new_source=new, companion_files=[missing])
    assert result.passed()
    assert result.findings == []


def test_sweep_empty_companion_list(tmp_path):
    """Empty companions list → empty result, no error."""
    old = tmp_path / "old.md"
    old.write_text("Slide A: $54B+ figure.\n")
    new = tmp_path / "new.md"
    new.write_text("Slide A: $25B figure.\n")

    result = sweep(old_source=old, new_source=new, companion_files=[])
    assert result.passed()
    assert result.findings == []


def test_sweep_missing_source_files_clean_pass(tmp_path):
    """Missing source files → empty token sets → clean pass.

    Mirrors render_gate's graceful-degrade contract: the sweep's job
    is to surface stale tokens, not to fail on a malformed pipeline
    state.
    """
    nonexistent_old = tmp_path / "no-such-old.md"
    nonexistent_new = tmp_path / "no-such-new.md"
    companion = tmp_path / "companion.py"
    companion.write_text("title = '$54B+'\n")

    result = sweep(
        old_source=nonexistent_old,
        new_source=nonexistent_new,
        companion_files=[companion],
    )
    assert result.passed()
    assert result.findings == []


def test_sweep_to_json_shape(tmp_path):
    """``to_json`` emits the documented JSON shape."""
    old = tmp_path / "old.md"
    old.write_text("Slide: $99B+ headline.\n")
    new = tmp_path / "new.md"
    new.write_text("Slide: reframed without headline figure.\n")
    companion = tmp_path / "fig.py"
    companion.write_text("title = '$99B+'\n")

    result = sweep(old_source=old, new_source=new, companion_files=[companion])
    payload = result.to_json()

    assert payload["sweep"] == SWEEP_NAME
    assert payload["old_source"] == str(old)
    assert payload["new_source"] == str(new)
    assert payload["pass"] is False
    assert "$99B+" in payload["removed_tokens"]
    assert len(payload["findings"]) == 1
    assert payload["findings"][0]["token"] == "$99B+"
    # Removed tokens are sorted for stable output.
    assert payload["removed_tokens"] == sorted(payload["removed_tokens"])


def test_token_repeated_in_same_companion_yields_one_finding_per_line(tmp_path):
    """A token appearing on 3 lines in one companion → 3 findings."""
    old = tmp_path / "old.md"
    old.write_text("The headline is $54B+ as cited everywhere.\n")
    new = tmp_path / "new.md"
    new.write_text("The headline is now $25.9B as recomputed.\n")
    companion = tmp_path / "fig.py"
    companion.write_text(
        "title_a = '$54B+'  # line 1\n"
        "title_b = '$54B+'  # line 2\n"
        "title_c = '$54B+'  # line 3\n"
    )

    result = sweep(old_source=old, new_source=new, companion_files=[companion])
    assert not result.passed()
    assert len(result.findings) == 3
    # Lines 1, 2, 3 — operator may want to see every location.
    lines = sorted(f.line for f in result.findings)
    assert lines == [1, 2, 3]


def test_custom_token_set_overrides_defaults(tmp_path):
    """Custom ``TokenSet`` is honored — caller can extend the vocabulary."""
    # Custom set that only matches "FOOBAR" tokens (replacing all four
    # default classes). The default $54B+ won't be flagged.
    custom = TokenSet(
        money=r"FOOBAR-?\w+",
        money_range=r"FOOBAR-RANGE",
        percent=r"FOOBAR-PCT",
        percent_range=r"FOOBAR-PCT-RANGE",
    )
    old = tmp_path / "old.md"
    old.write_text("FOOBAR-old in slide; $54B+ as baseline.\n")
    new = tmp_path / "new.md"
    new.write_text("FOOBAR-new in slide; $54B+ as baseline.\n")
    companion = tmp_path / "fig.py"
    companion.write_text("title = 'FOOBAR-old caption with $54B+'\n")

    result = sweep(
        old_source=old,
        new_source=new,
        companion_files=[companion],
        token_set=custom,
    )
    assert not result.passed()
    # Only the FOOBAR-old token should be flagged; $54B+ is not in the
    # custom token set, so it's invisible to the sweep.
    flagged = {f.token for f in result.findings}
    assert "FOOBAR-old" in flagged
    assert "$54B+" not in flagged


def test_stale_finding_to_dict_shape():
    """``StaleFinding.to_dict`` emits the documented keys."""
    sf = StaleFinding(
        companion_file="figures/src/cap.py",
        line=42,
        token="$54B+",
        rationale="deck.md no longer contains '$54B+'; cap.py still does.",
    )
    d = sf.to_dict()
    assert d == {
        "companion_file": "figures/src/cap.py",
        "line": 42,
        "token": "$54B+",
        "rationale": "deck.md no longer contains '$54B+'; cap.py still does.",
    }


def test_consistency_result_to_review_passes_clean_returns_empty_findings():
    """Clean ConsistencyResult → Review with no findings but still valid kind."""
    clean = ConsistencyResult(
        old_source="a.md",
        new_source="b.md",
        removed_tokens=frozenset(),
        findings=[],
    )
    review = clean.to_review(version_dir="t.1", critic_id="rc")
    # The null-scored Score is still present (schema requires non-empty
    # scores list).
    assert len(review.scores) == 1
    assert review.scores[0].score is None
    # No findings, no critical flags.
    assert review.findings == []
    assert review.critical_flags == []
    assert review.kind == Kind.TOOL_EVIDENCE
