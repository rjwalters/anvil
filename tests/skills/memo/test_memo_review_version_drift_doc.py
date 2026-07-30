"""Doc-coverage guard for the memo-review version-drift block (#746).

Issue #746 landed `anvil/skills/memo/lib/version_drift.py` (deterministic,
pure-stdlib cross-version metrics — bold-word share, hedge-marker count,
meta-commentary count, plus four contextual metrics) with `memo-review`
step 4m as the pilot integration:

1. Step 4m invokes `compute_drift(<thread>.{N}/)`, which resolves
   `<thread>.{N-1}/` and (when available) `<thread>.{N-2}/` off the
   version dir's own name and computes the seven metrics for each.
2. A finding fires only when a densification metric (bold-word share,
   hedge-marker count, meta-commentary count) increased in BOTH of the
   last two version transitions — never on a single-transition increase.
3. Every finding is fixed at `severity: major`, `scope: reduce` and is
   echoed directly into `comments.md` (step 8) — the load-bearing
   consumption path, since `memo-revise`'s default `--scope important`
   filter reads `comments.md`, not `_summary.md` structured blocks.
4. The findings land in `_summary.md.version_drift` (step 9) and a
   `## Version drift findings` subsection in `findings.md`.
5. This check never sets `critical_flag` — a deliberate departure from
   the summary-detail / cross-thread-cite / strongman back-checks.

This file pins the memo-review.md and rubric.md prose shape so the
wiring can't silently drift.

Per the per-skill test filename convention (#58 — distinct filenames
across skills, ``__init__.py`` chains in every test dir), this file is
named ``test_memo_review_version_drift_doc.py``.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MEMO_REVIEW_DOC = (
    REPO_ROOT / "anvil" / "skills" / "memo" / "commands" / "memo-review.md"
)
RUBRIC_DOC = REPO_ROOT / "anvil" / "skills" / "memo" / "rubric.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_memo_review_doc_has_step_4m_version_drift_check():
    text = _read(MEMO_REVIEW_DOC)
    assert "4m." in text, "memo-review.md must add the step 4m version-drift check (#746)"
    assert "anvil/skills/memo/lib/version_drift.py" in text
    assert "compute_drift" in text


def test_memo_review_doc_names_the_seven_metrics():
    text = _read(MEMO_REVIEW_DOC)
    step_4m = text[text.find("4m.") : text.find("5. **Score each dimension**")]
    for metric in (
        "word_count",
        "bold_span_count",
        "bold_word_share",
        "hedge_marker_count",
        "meta_commentary_count",
        "mean_sentence_length",
        "exhibit_count",
    ):
        assert metric in step_4m, (
            f"memo-review.md step 4m must name the `{metric}` metric (#746)."
        )


def test_memo_review_doc_documents_two_transition_finding_rule():
    text = _read(MEMO_REVIEW_DOC)
    step_4m = text[text.find("4m.") : text.find("5. **Score each dimension**")]
    assert "both" in step_4m.lower()
    assert "single" in step_4m.lower(), (
        "memo-review.md step 4m must document that a single-transition "
        "increase is observational only (#746)."
    )


def test_memo_review_doc_never_sets_critical_flag():
    text = _read(MEMO_REVIEW_DOC)
    step_4m = text[text.find("4m.") : text.find("5. **Score each dimension**")]
    assert "never" in step_4m.lower() and "critical_flag" in step_4m, (
        "memo-review.md step 4m must document that this check never sets "
        "critical_flag (#746)."
    )


def test_memo_review_doc_echoes_finding_into_comments_md():
    """Load-bearing: the finding must land in comments.md, not just
    _summary.md, so the default --scope important reviser sees it."""
    text = _read(MEMO_REVIEW_DOC)
    assert "Version-drift echo" in text, (
        "memo-review.md step 8 must document the version-drift echo into "
        "comments.md (#746)."
    )
    step_8 = text[text.find("Version-drift echo") :]
    assert "scope: reduce, major" in step_8 or "scope: reduce`, `major`" in step_8


def test_memo_review_doc_has_summary_version_drift_block():
    text = _read(MEMO_REVIEW_DOC)
    assert "`version_drift`" in text, (
        "memo-review.md step 9 must document the `_summary.md.version_drift` "
        "block (#746)."
    )
    assert "VersionDriftResult" in text


def test_memo_review_doc_has_version_drift_findings_subsection():
    text = _read(MEMO_REVIEW_DOC)
    assert "## Version drift findings" in text


def test_memo_review_doc_references_issue_746():
    text = _read(MEMO_REVIEW_DOC)
    assert "#746" in text, (
        "memo-review.md must reference issue #746 in the step 4m prose "
        "for audit-trail traceability."
    )


def test_rubric_doc_has_version_drift_section():
    text = _read(RUBRIC_DOC)
    assert "## Version drift" in text
    assert "#746" in text


def test_rubric_doc_names_densification_metrics():
    text = _read(RUBRIC_DOC)
    section = text[text.find("## Version drift") : text.find("## Length targets")]
    for metric in ("bold_word_share", "hedge_marker_count", "meta_commentary_count"):
        assert metric in section, (
            f"rubric.md §Version drift must name the `{metric}` densification "
            "metric (#746)."
        )


def test_rubric_doc_documents_fixed_severity_and_scope():
    text = _read(RUBRIC_DOC)
    section = text[text.find("## Version drift") : text.find("## Length targets")]
    assert "major" in section
    assert "scope: reduce" in section or "`scope: reduce`" in section


def test_rubric_doc_documents_no_critical_flag_participation():
    text = _read(RUBRIC_DOC)
    section = text[text.find("## Version drift") : text.find("## Length targets")]
    assert "never sets `critical_flag`" in section or "never sets" in section.lower()


def test_rubric_doc_references_canary_evidence_numbers():
    """Pin the canary evidence table from the issue body — the worked
    example that motivated the check."""
    text = _read(RUBRIC_DOC)
    section = text[text.find("## Version drift") : text.find("## Length targets")]
    assert "19.9%" in section
    assert "25.5%" in section
