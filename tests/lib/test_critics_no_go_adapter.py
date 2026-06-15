"""Tests for the NO-GO recognition in the memo legacy adapter (issue #559).

Covers:

- ``_adapt_memo_legacy`` recognizes ``**Verdict**: NO-GO`` (and the
  ``Verdict: NO-GO`` non-bold variant; the ``NO_GO`` underscore variant) in
  ``verdict.md`` prose and emits ``Verdict.NO_GO`` on the returned ``Review``.
- ``parse_memo_verdict_no_go`` returns ``True`` only for NO-GO prose.
- ``parse_memo_verdict_kill_rationale`` extracts the ``## Kill rationale``
  paragraph; returns ``None`` for non-NO-GO prose.
- Backwards-compat: pre-#559 ``verdict.md`` prose (``Decision: advance:
  true|false``) emits ``Verdict.ADVANCE`` / ``Verdict.REVISE`` exactly as
  before — the new NO-GO branch never fires unless the prose carries the
  explicit ``Verdict: NO-GO`` line.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.lib.critics import (
    _adapt_memo_legacy,
    parse_memo_verdict_decision,
    parse_memo_verdict_kill_rationale,
    parse_memo_verdict_no_go,
)
from anvil.lib.review_schema import Verdict


# Sample NO-GO verdict.md per the SKILL.md §"NO-GO terminal state" shape.
NO_GO_VERDICT_MD = """\
# NO-GO — terminal

**Verdict**: NO-GO
**Iteration**: 4
**Triggering flag**: redteam_survives
**Source critic**: memo-redteam

## Kill rationale

The red-team objection that the addressable market is two orders of magnitude smaller than the memo's TAM figure (and is structurally constrained by regulatory caps that no execution choice can bypass) SURVIVES four passes of revision. The memo's response in v4 reframes the TAM as a 10-year aspiration but does not reduce the recommendation's funding ask or check size — the thesis as written presupposes a market size that the red-team has demonstrated does not exist.

## Evidence

- thread.4/thread.md:L120-L138 (TAM reframe in v4 §3.2)
- thread.4/thread.md:L210-L225 (recommendation check size unchanged)

## Operator override

To resurrect this thread, run `memo-revise <thread> --override-no-go "<reason>"`.
"""

# Pre-#559 verdict.md (standard ADVANCE shape).
ADVANCE_VERDICT_MD = """\
# Verdict

**Total**: `37` / `44`
**Decision**: `advance: true`

## Critical flags

(none)

## Dimension summary

| # | Dimension | Score |
| 1 | Recommendation clarity | 4 / 5 |

## Top 3 revision priorities

(advance: true — no revision priorities)
"""

# Pre-#559 verdict.md (standard REVISE shape).
REVISE_VERDICT_MD = """\
# Verdict

**Total**: `30` / `44`
**Decision**: `advance: false`

## Critical flags

(none)
"""

# Standard scoring.md / comments.md for the adapter's other reads.
SCORING_MD = """\
| # | Dimension | Weight | Score | Justification |
|---|-----------|--------|-------|---------------|
| 1 | Recommendation clarity | 5 | 4 | clear recommendation |
| 2 | Thesis coherence | 6 | 5 | thesis holds |
"""

COMMENTS_MD = """\
## Severity: blocker

(none)

## Severity: major

(none)
"""


# ---------------------------------------------------------------------------
# parse_memo_verdict_no_go
# ---------------------------------------------------------------------------


def test_parse_memo_verdict_no_go_recognizes_bold_dash():
    assert parse_memo_verdict_no_go(NO_GO_VERDICT_MD) is True


def test_parse_memo_verdict_no_go_recognizes_unbold():
    text = "Verdict: NO-GO\n\nrest"
    assert parse_memo_verdict_no_go(text) is True


def test_parse_memo_verdict_no_go_recognizes_underscore():
    # The defensive underscore variant is honored.
    text = "**Verdict**: NO_GO\n\nrest"
    assert parse_memo_verdict_no_go(text) is True


def test_parse_memo_verdict_no_go_case_insensitive():
    text = "**verdict**: no-go\n\nrest"
    assert parse_memo_verdict_no_go(text) is True


def test_parse_memo_verdict_no_go_returns_false_on_advance():
    assert parse_memo_verdict_no_go(ADVANCE_VERDICT_MD) is False


def test_parse_memo_verdict_no_go_returns_false_on_revise():
    assert parse_memo_verdict_no_go(REVISE_VERDICT_MD) is False


def test_parse_memo_verdict_no_go_returns_false_on_empty():
    assert parse_memo_verdict_no_go("") is False


# ---------------------------------------------------------------------------
# parse_memo_verdict_kill_rationale
# ---------------------------------------------------------------------------


def test_parse_memo_verdict_kill_rationale_extracts_paragraph():
    rationale = parse_memo_verdict_kill_rationale(NO_GO_VERDICT_MD)
    assert rationale is not None
    assert "addressable market" in rationale
    assert "SURVIVES four passes" in rationale
    # Does NOT include the next heading or beyond.
    assert "Evidence" not in rationale
    assert "Operator override" not in rationale


def test_parse_memo_verdict_kill_rationale_returns_none_on_non_no_go():
    assert parse_memo_verdict_kill_rationale(ADVANCE_VERDICT_MD) is None
    assert parse_memo_verdict_kill_rationale(REVISE_VERDICT_MD) is None


def test_parse_memo_verdict_kill_rationale_returns_none_when_heading_missing():
    # NO-GO line present but no `## Kill rationale` heading → None.
    text = "**Verdict**: NO-GO\n\nsome prose without a heading"
    assert parse_memo_verdict_kill_rationale(text) is None


# ---------------------------------------------------------------------------
# _adapt_memo_legacy — NO-GO recognition end-to-end
# ---------------------------------------------------------------------------


def _write_critic_dir(tmp_path: Path, verdict_md: str) -> Path:
    """Set up a critic sibling dir with the prose triple."""
    critic_dir = tmp_path / "thread.4.review"
    critic_dir.mkdir()
    (critic_dir / "verdict.md").write_text(verdict_md)
    (critic_dir / "scoring.md").write_text(SCORING_MD)
    (critic_dir / "comments.md").write_text(COMMENTS_MD)
    return critic_dir


def test_adapt_memo_legacy_emits_no_go_verdict(tmp_path):
    critic_dir = _write_critic_dir(tmp_path, NO_GO_VERDICT_MD)
    review = _adapt_memo_legacy(critic_dir)
    assert review.verdict == Verdict.NO_GO


def test_adapt_memo_legacy_emits_advance_for_pre_559_prose(tmp_path):
    critic_dir = _write_critic_dir(tmp_path, ADVANCE_VERDICT_MD)
    review = _adapt_memo_legacy(critic_dir)
    # Pre-#559 prose with `advance: true` and total 37/44 → ADVANCE.
    assert review.verdict == Verdict.ADVANCE


def test_adapt_memo_legacy_emits_revise_for_pre_559_prose(tmp_path):
    critic_dir = _write_critic_dir(tmp_path, REVISE_VERDICT_MD)
    review = _adapt_memo_legacy(critic_dir)
    # Total 30/44 < threshold-as-recorded (44), and no NO-GO line → REVISE.
    assert review.verdict == Verdict.REVISE


def test_adapt_memo_legacy_no_go_takes_precedence_over_advance_decision(
    tmp_path,
):
    # An (arguably malformed) verdict.md carrying BOTH advance: true AND
    # NO-GO: NO-GO takes precedence. Defensive: an evaluator-declared
    # thesis failure must not be silently downgraded.
    weird_text = """\
**Verdict**: NO-GO
**Decision**: `advance: true`
**Total**: `40` / `44`

## Kill rationale

thesis fails despite passing total.
"""
    critic_dir = _write_critic_dir(tmp_path, weird_text)
    review = _adapt_memo_legacy(critic_dir)
    assert review.verdict == Verdict.NO_GO


# ---------------------------------------------------------------------------
# parse_memo_verdict_decision — confirms pre-#559 prose still parses identically
# ---------------------------------------------------------------------------


def test_parse_memo_verdict_decision_unaffected_by_no_go_recognition():
    # NO-GO verdict.md doesn't carry a Decision: advance: line; the
    # existing parser returns None.
    assert parse_memo_verdict_decision(NO_GO_VERDICT_MD) is None
    # Pre-#559 prose continues to parse as before.
    assert parse_memo_verdict_decision(ADVANCE_VERDICT_MD) is True
    assert parse_memo_verdict_decision(REVISE_VERDICT_MD) is False
