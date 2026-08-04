"""Doc-coverage guard for essay-review.md's migrated-corpus recovery path
(issue #881).

A migrated corpus (`anvil:project-migrate --apply`) can leave a legacy
single-file `review.md` sitting at the canonical `<thread>.{N}.review/`
path. Step 1's idempotency check used to be bare directory-existence,
which either silently treated that foreign content as "already reviewed"
or forced a naive write straight into the `staged_sidecar`/`stage_enter`
`FileExistsError` refusal, with no documented recovery. These tests guard
that the doc now (a) makes the idempotency check content-aware via
`_has_recognizable_review`, and (b) documents the `stage_replace` /
`commit_replace` / `abort_replace` recovery surface for the
occupied-but-unrecognized case, including the CLI-shim analog for
non-Python-driver sessions.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "anvil" / "skills" / "essay" / "commands" / "essay-review.md"
SKILL_DOC = REPO_ROOT / "anvil" / "skills" / "essay" / "SKILL.md"


def _read() -> str:
    return DOC.read_text(encoding="utf-8")


def test_essay_review_doc_references_issue_881():
    text = _read()
    assert "#881" in text


def test_essay_review_doc_idempotency_check_is_content_aware():
    """Step 1 must check recognizability, not bare directory existence."""
    text = _read()
    assert "_has_recognizable_review" in text
    assert "content-aware" in text.lower() or "not bare" in text.lower()


def test_essay_review_doc_documents_stage_replace_surface():
    text = _read()
    for name in ("stage_replace", "commit_replace", "abort_replace"):
        assert name in text, f"{name} missing from essay-review.md prose"


def test_essay_review_doc_names_stage_replace_required_manifest():
    """The commit_replace manifest must include the preserved foreign
    filename (review.md) alongside the essay's own required files."""
    text = _read()
    assert "review.md" in text
    for name in (
        "verdict.md",
        "scoring.md",
        "comments.md",
        "_summary.md",
        "_gate.json",
        "_meta.json",
        "_progress.json",
    ):
        assert name in text

    # commit_replace's manifest example lists review.md alongside the
    # essay required-files set (not just mentioned in passing elsewhere).
    assert "commit_replace" in text
    idx = text.index("commit_replace(<thread>.{N}.review")
    window = text[idx : idx + 400]
    assert "review.md" in window


def test_essay_review_doc_references_adopt_review_precedent():
    """The recipe is documented as generalizing project-migrate's
    --adopt-review move-aside/stage/swap precedent, not invented fresh."""
    text = _read()
    assert "adopt_review.py" in text or "--adopt-review" in text
    assert "rubric-rebackport" in text or "project-migrate" in text


def test_essay_review_doc_preserves_350_guard_language():
    """The doc must be explicit that a real recognizable review is still
    never replaced — the #350 immutability guard is untouched."""
    text = _read()
    assert "#350" in text


def test_essay_review_doc_documents_cli_replace_shim():
    """Non-Python-driver sessions need the replace/commit-replace/
    abort-replace CLI analog, mirroring stage/commit/cleanup."""
    text = _read()
    assert "sidecar replace" in text
    assert "sidecar commit-replace" in text
    assert "sidecar abort-replace" in text


def test_essay_skill_doc_records_migrated_corpus_failure_mode():
    text = SKILL_DOC.read_text(encoding="utf-8")
    assert "#881" in text
    assert "stage_replace" in text
