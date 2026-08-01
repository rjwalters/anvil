"""Contract tests for memo's adoption of the pending-marker gate (issue #845).

Phase 4 of the #841 pending-marker epic — wiring the framework-level
``anvil/lib/pending_marker.py`` primitive (issue #842) into ``anvil:memo``.
The wiring itself is documented in ``anvil/skills/memo/SKILL.md``
§"Pending-marker terminal gate", ``anvil/skills/memo/commands/memo-review.md``
step 4n / step 6 / step 7 / step 10, and
``anvil/skills/memo/commands/memo-revise.md`` step 6 / §"Notes for the
reviser agent" — prose specs, not new Python modules. What this file
covers is the **contract surface** those LLM-driven memo commands rely
on, mirroring the style of ``test_memo_no_go_terminal.py``:

1. ``anvil/lib/pending_marker.py`` detects a well-formed ``[PENDING
   <source>]`` marker in a memo-shaped body (``<thread>.{N}/<thread>.md``
   per the #295 slug-echo convention) and writes the
   ``<thread>.{N}.pending/_review.json`` sidecar, auto-discovered by
   ``anvil/lib/critics.py::discover_critics`` alongside a ``.review/``
   sibling with NO aggregator change.
2. The emitted ``pending_dependency`` flag is VISIBLE in the aggregate
   but NEVER forces ``Verdict.BLOCK`` on its own — a pending-only memo
   aggregates to ``Verdict.ADVANCE`` (score-driven), never ``BLOCK``.
3. **Composition with the NO-GO terminal state (issue #559) is
   orthogonal**: a ``no_go`` flag from ``memo-review``'s step-6
   promotion policy fires ``Verdict.NO_GO`` regardless of whether a
   pending marker is also present, and ``has_pending_dependency_flag``
   is independently ``True``/``False`` regardless of the NO-GO outcome
   — neither classification reads the other's result.
4. An unrelated ordinary critical flag (e.g. a refs-back-check
   ``CONTRADICTED``) still forces ``Verdict.BLOCK`` even when a pending
   marker also co-occurs — the pending flag never "shields" a real
   defect.
5. A ``<!-- anvil-lint-disable: pending_marker -->``-suppressed marker
   never gates (``passed()`` is ``True``, no ``pending_dependency``
   flag emitted).
6. Resolving the marker (replacing the bracketed text with the real
   value) clears the gate on the next detector pass — the full
   draft -> pending -> surfaced -> resolved -> clean lifecycle.

Per the per-skill test filename convention (#58 — distinct filenames
across skills, ``__init__.py`` chains in every test dir), this file is
named ``test_memo_pending_marker_contract.py``.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.convergence import (
    PENDING_DEPENDENCY_FLAG_TYPE,
    has_pending_dependency_flag,
)
from anvil.lib.critics import aggregate, discover_critics
from anvil.lib.pending_marker import (
    check_pending_markers,
    write_review_dir,
)
from anvil.lib.review_schema import CriticalFlag, Review, Score, Verdict


# ---------------------------------------------------------------------------
# Fixture helpers — a memo-shaped version dir (<thread>.{N}/<thread>.md).
# ---------------------------------------------------------------------------

THREAD_SLUG = "acme-seed"

PENDING_BODY = """# Acme Seed — Investment Memo

## Financial reasoning

Acme's unit economics land at [PENDING: series-a-term-sheet] once the
Series A term sheet is signed; interim modeling uses the pre-money
valuation the founders quoted verbally.

## Market sizing

Customer references are [PENDING customer-ref-acme] pending the
reference call scheduled for next week.
"""

RESOLVED_BODY = """# Acme Seed — Investment Memo

## Financial reasoning

Acme's unit economics land at a $42M post-money valuation per the
signed Series A term sheet.

## Market sizing

Customer references confirmed strong retention in the reference call
with Acme's lead design partner.
"""

SUPPRESSED_BODY = """# Acme Seed — Investment Memo

## Appendix: marker syntax

The pending-marker convention looks like `[PENDING <source>]`.

<!-- anvil-lint-disable: pending_marker -->
Example (suppressed, documentation only): [PENDING vendor-quote-acme]
"""


def _make_memo_version_dir(tmp_path: Path, body: str, *, n: int = 1) -> Path:
    """Write a memo-shaped version dir: <project>/<slug>/<slug>.{N}/<slug>.md.

    ``pending_marker._body_path`` derives the slug-echo filename from
    ``version_dir.parent.name`` (the #295 project-org model lock: the
    thread directory is named for its slug), so the thread dir MUST be
    named ``THREAD_SLUG`` — a bare ``tmp_path / "<slug>.{N}"`` layout
    (with no named thread dir in between) does not match the real
    on-disk shape and is rejected by ``_body_path``.
    """
    thread_dir = tmp_path / THREAD_SLUG
    thread_dir.mkdir(exist_ok=True)
    version_dir = thread_dir / f"{THREAD_SLUG}.{n}"
    version_dir.mkdir()
    (version_dir / f"{THREAD_SLUG}.md").write_text(body, encoding="utf-8")
    return version_dir


# ---------------------------------------------------------------------------
# 1. Detection + sidecar discovery in a memo-shaped version dir.
# ---------------------------------------------------------------------------


def test_pending_marker_detected_in_memo_shaped_body(tmp_path):
    version_dir = _make_memo_version_dir(tmp_path, PENDING_BODY)
    result = check_pending_markers(version_dir)

    assert result.passed() is False
    assert result.outstanding_sources == [
        "series-a-term-sheet",
        "customer-ref-acme",
    ]
    # Body-file discovery found the #295 slug-echo <thread>.md, not main.tex.
    assert result.body_path == f"{THREAD_SLUG}.md"


def test_pending_sidecar_written_and_auto_discovered_alongside_review(tmp_path):
    """`.pending/` sits alongside `.review/` and is picked up by
    discover_critics with no aggregator change (single path segment)."""
    version_dir = _make_memo_version_dir(tmp_path, PENDING_BODY)
    result = check_pending_markers(version_dir)
    write_review_dir(version_dir, result)

    # A sibling .review/ dir with a canonical _review.json (as memo-review
    # would write) is also present.
    review_dir = version_dir.parent / f"{version_dir.name}.review"
    review_dir.mkdir()
    (review_dir / "_review.json").write_text("{}", encoding="utf-8")

    siblings = discover_critics(version_dir)
    sibling_names = {p.name for p in siblings}
    assert f"{THREAD_SLUG}.1.pending" in sibling_names
    assert f"{THREAD_SLUG}.1.review" in sibling_names


# ---------------------------------------------------------------------------
# 2. A pending-only memo aggregates to ADVANCE, never BLOCK.
# ---------------------------------------------------------------------------


def _memo_review_scores(*, threshold: int = 35) -> list:
    return [
        Score(dimension="dim_1", score=5, max=5),
        Score(dimension="dim_2", score=6, max=6),
        Score(dimension="dim_3", score=6, max=6),
        Score(dimension="dim_4", score=5, max=5),
        Score(dimension="dim_5", score=4, max=4),
        Score(dimension="dim_6", score=5, max=5),
        Score(dimension="dim_7", score=4, max=4),
        Score(dimension="dim_8", score=5, max=5),
        Score(dimension="dim_9", score=4, max=4),
    ]


def test_pending_only_memo_advances_despite_active_marker(tmp_path):
    """A pending_dependency flag alone never forces BLOCK — the score-driven
    verdict (ADVANCE at >=35/44, 0 ordinary critical flags) wins. The
    terminal-state gate (READY) is a SEPARATE query the skill applies via
    SKILL.md's state-machine table, not the aggregator's Verdict."""
    version_dir = _make_memo_version_dir(tmp_path, PENDING_BODY)
    result = check_pending_markers(version_dir)
    pending_review = result.to_review(version_dir=version_dir.name)

    memo_review = Review(
        version_dir=version_dir.name,
        critic_id="memo-review",
        scores=_memo_review_scores(),
        critical_flags=[],  # zero ordinary critical flags
        threshold=35,
    )

    agg = aggregate([memo_review, pending_review])

    assert agg.verdict == Verdict.ADVANCE
    # But the pending flag is still VISIBLE in the aggregate for the
    # terminal-state gate.
    assert has_pending_dependency_flag(agg.critical_flags) is True
    types = {cf.type for cf in agg.critical_flags}
    assert PENDING_DEPENDENCY_FLAG_TYPE in types


# ---------------------------------------------------------------------------
# 3. Orthogonal to NO-GO: a no_go flag fires Verdict.NO_GO regardless of an
#    active pending marker, and the pending-dependency query is independent.
# ---------------------------------------------------------------------------


def test_no_go_verdict_fires_independent_of_pending_marker_state(tmp_path):
    """A NO-GO memo may still carry active pending markers — the two
    signals compose without interfering (issue #845 acceptance criterion:
    'a NO-GO memo can still have pending markers; those are moot once
    NO-GO fires')."""
    version_dir = _make_memo_version_dir(tmp_path, PENDING_BODY)
    result = check_pending_markers(version_dir)
    pending_review = result.to_review(version_dir=version_dir.name)

    memo_review_no_go = Review(
        version_dir=version_dir.name,
        critic_id="memo-review",
        scores=_memo_review_scores(),
        critical_flags=[
            CriticalFlag(
                type="no_go",
                justification=(
                    "Load-bearing red-team objection SURVIVES four passes "
                    "of revision; iteration budget exhausted."
                ),
            ),
        ],
        threshold=35,
    )

    agg = aggregate([memo_review_no_go, pending_review])

    assert agg.verdict == Verdict.NO_GO
    # The pending signal is still independently readable — NO-GO does not
    # suppress or consume it, it's simply moot for the (already-terminal)
    # NO-GO outcome.
    assert has_pending_dependency_flag(agg.critical_flags) is True


def test_resolved_pending_marker_does_not_affect_no_go_classification(tmp_path):
    """The converse: clearing every pending marker never overrides or
    suppresses a no_go verdict — the two code paths read independent
    evidence."""
    version_dir = _make_memo_version_dir(tmp_path, RESOLVED_BODY)
    result = check_pending_markers(version_dir)
    assert result.passed() is True  # no active markers
    pending_review = result.to_review(version_dir=version_dir.name)
    assert has_pending_dependency_flag(pending_review.critical_flags) is False

    memo_review_no_go = Review(
        version_dir=version_dir.name,
        critic_id="memo-review",
        scores=_memo_review_scores(),
        critical_flags=[
            CriticalFlag(type="no_go", justification="thesis fails"),
        ],
        threshold=35,
    )

    agg = aggregate([memo_review_no_go, pending_review])
    assert agg.verdict == Verdict.NO_GO


# ---------------------------------------------------------------------------
# 4. An unrelated ordinary critical flag still blocks, pending or not.
# ---------------------------------------------------------------------------


def test_ordinary_critical_flag_still_blocks_alongside_pending_marker(tmp_path):
    """The pending_dependency flag never shields a real defect — an
    ordinary critical flag (e.g. refs back-check CONTRADICTED) co-occurring
    with an active pending marker still forces Verdict.BLOCK."""
    version_dir = _make_memo_version_dir(tmp_path, PENDING_BODY)
    result = check_pending_markers(version_dir)
    pending_review = result.to_review(version_dir=version_dir.name)

    memo_review_blocked = Review(
        version_dir=version_dir.name,
        critic_id="memo-review",
        scores=_memo_review_scores(),
        critical_flags=[
            CriticalFlag(
                type="refs_back_check_contradicted",
                justification=(
                    "Team bio claim CONTRADICTED by refs/cv.pdf: 'Sphere "
                    "Staff Scientist, 15+ years' vs. 'Acme Semi, "
                    "2026-current'."
                ),
            ),
        ],
        threshold=35,
    )

    agg = aggregate([memo_review_blocked, pending_review])

    assert agg.verdict == Verdict.BLOCK
    types = {cf.type for cf in agg.critical_flags}
    assert "refs_back_check_contradicted" in types
    assert PENDING_DEPENDENCY_FLAG_TYPE in types
    assert has_pending_dependency_flag(agg.critical_flags) is True


# ---------------------------------------------------------------------------
# 5. A suppressed marker never gates.
# ---------------------------------------------------------------------------


def test_suppressed_marker_does_not_gate(tmp_path):
    version_dir = _make_memo_version_dir(tmp_path, SUPPRESSED_BODY)
    result = check_pending_markers(version_dir)

    assert result.passed() is True
    assert result.outstanding_sources == []
    assert result.to_critical_flags() == []


# ---------------------------------------------------------------------------
# 6. Full lifecycle: draft w/ marker -> surfaced -> resolved -> clean gate.
# ---------------------------------------------------------------------------


def test_full_pending_to_resolved_lifecycle(tmp_path):
    # v1: active marker present — the terminal-state gate would hold READY.
    v1 = _make_memo_version_dir(tmp_path, PENDING_BODY, n=1)
    result_v1 = check_pending_markers(v1)
    assert result_v1.passed() is False
    assert has_pending_dependency_flag(
        result_v1.to_critical_flags()
    ) is True

    # v2: the drafter/reviser replaced the marker with the real value —
    # the next detector pass finds nothing and the gate clears.
    v2 = _make_memo_version_dir(tmp_path, RESOLVED_BODY, n=2)
    result_v2 = check_pending_markers(v2)
    assert result_v2.passed() is True
    assert result_v2.to_critical_flags() == []
