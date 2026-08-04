"""Tests for the ``voice.corpus`` self-published exclusion (issue #890).

When ``essay-review`` (or any :func:`resolve_voice_docs` caller) reviews a
revision of an **already-published** thread, a ``voice.corpus`` glob that
covers the consumer's published archive resolves that thread's own prior
published form — calibrating dim 2 (Voice fidelity) against the very
artifact under review. This module exercises the fix:

- :func:`resolve_voice_docs`'s new ``exclude_self_slug`` kwarg, which
  drops a thread's own published form from a resolved ``corpus`` entry
  via two unioned sources — automatic slug-based inference
  (:func:`anvil.lib.project_brief._infer_self_published_paths`) and the
  declared :attr:`BriefDocument.voice_corpus_exclude` escape hatch for
  publish-path shapes the automatic rule cannot cover.
- The new :class:`ResolvedVoiceDoc` fields (``excluded`` /
  ``exclusion_reasons``) that make the exclusion auditable.
- ``BriefDocument.voice_corpus_exclude`` BRIEF parsing (scalar-or-list,
  the same normalization as ``spec_ref`` / ``code_ref``).

Every test that never passes ``exclude_self_slug`` (or never declares
``voice_corpus_exclude``) is the regression guard: this feature is a
complete no-op for every pre-#890 caller.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from anvil.lib.project_brief import (
    BriefDocument,
    CompanionRefTypeError,
    load_project_brief,
    resolve_voice_docs,
)
from anvil.lib.project_discovery import BRIEF_FILENAME


def _write_brief(project: Path, frontmatter: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / BRIEF_FILENAME).write_text(
        f"---\n{textwrap.dedent(frontmatter)}---\n\n# BRIEF\n",
        encoding="utf-8",
    )


def _make_consumer(tmp_path: Path) -> Path:
    consumer = tmp_path / "consumer"
    (consumer / ".anvil").mkdir(parents=True)
    return consumer


# ---------------------------------------------------------------------------
# BRIEF parsing: BriefDocument.voice_corpus_exclude
# ---------------------------------------------------------------------------


def test_voice_corpus_exclude_absent_is_none(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: my-post
            artifact_type: essay
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    doc = brief.document_for_slug("my-post")
    assert doc is not None
    assert doc.voice_corpus_exclude is None


def test_voice_corpus_exclude_scalar_normalizes_to_list(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: my-post
            artifact_type: essay
            voice_corpus_exclude: writing-corpus/my-post.md
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    doc = brief.document_for_slug("my-post")
    assert doc is not None
    assert doc.voice_corpus_exclude == ["writing-corpus/my-post.md"]


def test_voice_corpus_exclude_list_form(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: my-post
            artifact_type: essay
            voice_corpus_exclude:
              - writing-corpus/my-post.md
              - writing-corpus/my-post-reprint.md
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    doc = brief.document_for_slug("my-post")
    assert doc is not None
    assert doc.voice_corpus_exclude == [
        "writing-corpus/my-post.md",
        "writing-corpus/my-post-reprint.md",
    ]


def test_voice_corpus_exclude_empty_list_normalizes_to_none(
    tmp_path: Path,
) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: my-post
            artifact_type: essay
            voice_corpus_exclude: []
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    doc = brief.document_for_slug("my-post")
    assert doc is not None
    assert doc.voice_corpus_exclude is None


def test_voice_corpus_exclude_nonstring_element_raises(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: my-post
            artifact_type: essay
            voice_corpus_exclude:
              - writing-corpus/my-post.md
              - 7
        """,
    )
    with pytest.raises(CompanionRefTypeError):
        load_project_brief(project)


# ---------------------------------------------------------------------------
# resolve_voice_docs: baseline (no exclude_self_slug) is byte-identical
# ---------------------------------------------------------------------------


def test_no_exclude_self_slug_is_byte_identical(tmp_path: Path) -> None:
    """Omitting exclude_self_slug entirely is a complete no-op (regression guard)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          corpus: writing-corpus/*.md
        documents:
          - slug: my-post
            artifact_type: essay
        """,
    )
    corpus_dir = consumer / "writing-corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "my-post.md").write_text("body", encoding="utf-8")
    (corpus_dir / "other-post.md").write_text("body", encoding="utf-8")

    resolved = resolve_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    entry = resolved[0]
    assert entry.kind == "corpus"
    assert entry.missing is False
    assert len(entry.paths) == 2
    assert entry.excluded == []
    assert entry.exclusion_reasons == {}


def test_exclude_self_slug_no_match_is_untouched(tmp_path: Path) -> None:
    """A thread whose published form isn't in the corpus glob: no-op."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          corpus: writing-corpus/*.md
        documents:
          - slug: brand-new-thread
            artifact_type: essay
        """,
    )
    corpus_dir = consumer / "writing-corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "other-post.md").write_text("body", encoding="utf-8")

    resolved = resolve_voice_docs(
        project, consumer_root=consumer, exclude_self_slug="brand-new-thread"
    )
    entry = resolved[0]
    assert len(entry.paths) == 1
    assert entry.excluded == []


# ---------------------------------------------------------------------------
# Automatic exclusion (slug-inferred)
# ---------------------------------------------------------------------------


def test_exclude_self_slug_plain_filename_match(tmp_path: Path) -> None:
    """Published filename == slug (essay's own <slug>.md convention)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          corpus: writing-corpus/*.md
        documents:
          - slug: the-loop-is-the-unit
            artifact_type: essay
        """,
    )
    corpus_dir = consumer / "writing-corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "the-loop-is-the-unit.md").write_text("self", encoding="utf-8")
    (corpus_dir / "the-example-coherence-gate.md").write_text(
        "other", encoding="utf-8"
    )

    resolved = resolve_voice_docs(
        project,
        consumer_root=consumer,
        exclude_self_slug="the-loop-is-the-unit",
    )
    entry = resolved[0]
    assert entry.missing is False
    assert [Path(p).name for p in entry.paths] == ["the-example-coherence-gate.md"]
    assert len(entry.excluded) == 1
    assert entry.excluded[0].endswith("the-loop-is-the-unit.md")
    assert (
        entry.exclusion_reasons[entry.excluded[0]]
        == "published self (inferred from slug)"
    )


def test_exclude_self_slug_date_prefixed_filename_match(tmp_path: Path) -> None:
    """Published filename carries a leading YYYY-MM-DD- prefix."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          corpus: writing-corpus/*.md
        documents:
          - slug: the-loop-is-the-unit
            artifact_type: essay
        """,
    )
    corpus_dir = consumer / "writing-corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "2026-05-27-the-loop-is-the-unit.md").write_text(
        "self", encoding="utf-8"
    )
    (corpus_dir / "2026-04-01-the-toaster-gate.md").write_text(
        "other", encoding="utf-8"
    )

    resolved = resolve_voice_docs(
        project,
        consumer_root=consumer,
        exclude_self_slug="the-loop-is-the-unit",
    )
    entry = resolved[0]
    assert [Path(p).name for p in entry.paths] == ["2026-04-01-the-toaster-gate.md"]
    assert len(entry.excluded) == 1


def test_exclude_self_slug_case_insensitive(tmp_path: Path) -> None:
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          corpus: writing-corpus/*.md
        documents:
          - slug: the-loop-is-the-unit
            artifact_type: essay
        """,
    )
    corpus_dir = consumer / "writing-corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "The-Loop-Is-The-Unit.md").write_text("self", encoding="utf-8")

    resolved = resolve_voice_docs(
        project,
        consumer_root=consumer,
        exclude_self_slug="the-loop-is-the-unit",
    )
    entry = resolved[0]
    assert entry.paths == []
    assert len(entry.excluded) == 1


def test_exclude_self_slug_no_false_positive_on_related_slug(
    tmp_path: Path,
) -> None:
    """A DIFFERENT thread whose slug is a superstring must NOT be excluded.

    Precision guard: excluding the wrong file would silently thin an
    unrelated thread's calibration base with no operator-visible signal.
    """
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          corpus: writing-corpus/*.md
        documents:
          - slug: the-loop-is-the-unit
            artifact_type: essay
        """,
    )
    corpus_dir = consumer / "writing-corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "the-loop-is-the-unit-revisited.md").write_text(
        "unrelated", encoding="utf-8"
    )

    resolved = resolve_voice_docs(
        project,
        consumer_root=consumer,
        exclude_self_slug="the-loop-is-the-unit",
    )
    entry = resolved[0]
    assert len(entry.paths) == 1
    assert entry.excluded == []


# ---------------------------------------------------------------------------
# Declared voice_corpus_exclude (escape hatch)
# ---------------------------------------------------------------------------


def test_declared_corpus_exclude_covers_inference_gap(tmp_path: Path) -> None:
    """A publish path the automatic rule cannot infer (title-cased, nested)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          corpus: writing-corpus/*.md
        documents:
          - slug: the-loop-is-the-unit
            artifact_type: essay
            voice_corpus_exclude: writing-corpus/The Loop Is The Unit.md
        """,
    )
    corpus_dir = consumer / "writing-corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "The Loop Is The Unit.md").write_text("self", encoding="utf-8")
    (corpus_dir / "other-post.md").write_text("other", encoding="utf-8")

    resolved = resolve_voice_docs(
        project,
        consumer_root=consumer,
        exclude_self_slug="the-loop-is-the-unit",
    )
    entry = resolved[0]
    assert [Path(p).name for p in entry.paths] == ["other-post.md"]
    assert len(entry.excluded) == 1
    reason = entry.exclusion_reasons[entry.excluded[0]]
    assert "declared corpus_exclude" in reason


def test_declared_and_automatic_exclusion_union_dedup(tmp_path: Path) -> None:
    """Both sources matching the SAME path dedupe to one excluded entry."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          corpus: writing-corpus/*.md
        documents:
          - slug: the-loop-is-the-unit
            artifact_type: essay
            voice_corpus_exclude: writing-corpus/the-loop-is-the-unit.md
        """,
    )
    corpus_dir = consumer / "writing-corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "the-loop-is-the-unit.md").write_text("self", encoding="utf-8")
    (corpus_dir / "other-post.md").write_text("other", encoding="utf-8")

    resolved = resolve_voice_docs(
        project,
        consumer_root=consumer,
        exclude_self_slug="the-loop-is-the-unit",
    )
    entry = resolved[0]
    assert len(entry.excluded) == 1
    assert [Path(p).name for p in entry.paths] == ["other-post.md"]
    # Automatic inference reason wins when both sources match the same path.
    assert (
        entry.exclusion_reasons[entry.excluded[0]]
        == "published self (inferred from slug)"
    )


def test_declared_corpus_exclude_only_applies_to_its_own_document(
    tmp_path: Path,
) -> None:
    """Another document's voice_corpus_exclude never leaks into this review."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          corpus: writing-corpus/*.md
        documents:
          - slug: thread-a
            artifact_type: essay
            voice_corpus_exclude: writing-corpus/other-post.md
          - slug: thread-b
            artifact_type: essay
        """,
    )
    corpus_dir = consumer / "writing-corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "other-post.md").write_text("other", encoding="utf-8")

    resolved = resolve_voice_docs(
        project, consumer_root=consumer, exclude_self_slug="thread-b"
    )
    entry = resolved[0]
    assert [Path(p).name for p in entry.paths] == ["other-post.md"]
    assert entry.excluded == []


# ---------------------------------------------------------------------------
# Thin-corpus edge case: exclusion leaves zero remaining exemplars
# ---------------------------------------------------------------------------


def test_exclusion_leaving_zero_remaining_paths_stays_active_not_missing(
    tmp_path: Path,
) -> None:
    """A single-exemplar corpus, fully excluded, is NOT recast as `missing`.

    `missing` names "the declaration matched nothing" — a distinct defect
    from "matched something, but it was all this thread's own published
    form." Callers (essay-review) are expected to check
    ``len(entry.paths)`` directly for the thin/zero-exemplar warning
    (issue #890 AC 3) rather than overload ``missing``.
    """
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          corpus: writing-corpus/*.md
        documents:
          - slug: the-loop-is-the-unit
            artifact_type: essay
        """,
    )
    corpus_dir = consumer / "writing-corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "the-loop-is-the-unit.md").write_text("self", encoding="utf-8")

    resolved = resolve_voice_docs(
        project,
        consumer_root=consumer,
        exclude_self_slug="the-loop-is-the-unit",
    )
    entry = resolved[0]
    assert entry.paths == []
    assert entry.missing is False
    assert len(entry.excluded) == 1


def test_exclude_self_slug_when_corpus_already_missing_is_noop(
    tmp_path: Path,
) -> None:
    """A glob matching zero files stays `missing=True` — exclusion never runs."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          corpus: writing-corpus/*.md
        documents:
          - slug: the-loop-is-the-unit
            artifact_type: essay
        """,
    )
    resolved = resolve_voice_docs(
        project,
        consumer_root=consumer,
        exclude_self_slug="the-loop-is-the-unit",
    )
    entry = resolved[0]
    assert entry.missing is True
    assert entry.paths == []
    assert entry.excluded == []
