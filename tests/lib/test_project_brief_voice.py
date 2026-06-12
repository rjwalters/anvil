"""Tests for the project BRIEF ``voice:`` block + ``resolve_voice_docs`` (issue #461).

The voice/persona grounding-docs contract: an optional top-level
``voice:`` key on the project BRIEF declares up to four persona docs
(``style_guide`` / ``vocabulary`` / ``values`` / ``corpus`` glob),
parsed into :class:`VoiceDocs` and resolved — project-root first, then
consumer-root — by :func:`resolve_voice_docs`. Missing-file results
are structured ``missing: true`` entries (never a raise); an absent
block is the byte-identical inactive path.

One deliberate deviation from the curation comment's "unknown sub-keys
rejected (STRICT)" line, per the orchestration note on the build: the
companion rhetoric lint (issue #463, building in parallel) may add a
``voice.rhetoric_rules`` sub-key, so unknown sub-keys are TOLERATED —
preserved verbatim under ``VoiceDocs.unknown_keys`` with a
``warnings.warn`` breadcrumb (the lenient inner-block posture of
``rubric_overrides.unknown_keys``). The recognized sub-keys remain
STRICT on type (non-string values raise).
"""

from __future__ import annotations

import textwrap
import warnings
from pathlib import Path

import pytest

from anvil.lib.project_brief import (
    VOICE_DOC_KINDS,
    ProjectBrief,
    ResolvedVoiceDoc,
    VoiceDocs,
    load_project_brief,
    load_rubric_overrides_for_slug,
    resolve_voice_docs,
)
from anvil.lib.project_discovery import BRIEF_FILENAME


def _write_brief(project: Path, frontmatter: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / BRIEF_FILENAME).write_text(
        f"---\n{textwrap.dedent(frontmatter)}---\n\n# BRIEF\n",
        encoding="utf-8",
    )


# NOTE: continuation lines carry the same 8-space base indent as the
# test f-string templates below, so the textwrap.dedent inside
# _write_brief strips a uniform prefix and yields well-formed YAML.
_DOCS_STANZA = (
    "documents:\n"
    "          - slug: acme\n"
    "            artifact_type: investment-memo\n"
)


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


def test_full_voice_block_parses(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          style_guide: STYLE_GUIDE.md
          vocabulary: VOCABULARY.md
          values: VALUES.md
          corpus: writing-corpus/**/*.md
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.voice is not None
    assert brief.voice.style_guide == "STYLE_GUIDE.md"
    assert brief.voice.vocabulary == "VOCABULARY.md"
    assert brief.voice.values == "VALUES.md"
    assert brief.voice.corpus == "writing-corpus/**/*.md"
    assert brief.voice.unknown_keys == {}
    assert not brief.voice.is_empty


def test_partial_voice_block_parses(tmp_path: Path) -> None:
    """Every sub-key is optional — a values-only block is legal."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: VALUES.md
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.values == "VALUES.md"
    assert brief.voice.style_guide is None
    assert brief.voice.vocabulary is None
    assert brief.voice.corpus is None
    assert not brief.voice.is_empty


def test_empty_voice_block_parses_as_empty(tmp_path: Path) -> None:
    """``voice: {}`` parses to an all-None VoiceDocs (inactive tier)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice: {{}}
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.is_empty
    # Inactive: the resolver treats the empty block exactly like absence.
    assert resolve_voice_docs(project, consumer_root=tmp_path) == []


def test_absent_voice_block_is_none(tmp_path: Path) -> None:
    """No ``voice:`` key → ``ProjectBrief.voice is None`` (byte-identical)."""
    project = tmp_path / "proj"
    _write_brief(project, f"project: proj\n{_DOCS_STANZA}")
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.voice is None


def test_unknown_sub_key_tolerated_with_warning(tmp_path: Path) -> None:
    """Unknown sub-keys are preserved under unknown_keys (forward-compat
    for the #463 ``rhetoric_rules`` surface), with a warning."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: VALUES.md
          rhetoric_rules: RHETORIC.md
        {_DOCS_STANZA}""",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.unknown_keys == {"rhetoric_rules": "RHETORIC.md"}
    assert brief.voice.values == "VALUES.md"
    assert any("rhetoric_rules" in str(w.message) for w in caught)


def test_unknown_keys_only_block_is_inactive(tmp_path: Path) -> None:
    """A block declaring ONLY unknown sub-keys does not activate the tier."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          rhetoric_rules: RHETORIC.md
        {_DOCS_STANZA}""",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        brief = load_project_brief(project)
        assert brief is not None and brief.voice is not None
        assert brief.voice.is_empty
        assert resolve_voice_docs(project, consumer_root=tmp_path) == []


@pytest.mark.parametrize(
    "raw",
    ["[a.md, b.md]", "42", "true", "{nested: x}"],
)
def test_non_string_path_rejected(tmp_path: Path, raw: str) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: {raw}
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"BRIEF\.voice\.values"):
        load_project_brief(project)


def test_non_mapping_voice_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice: VALUES.md
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"BRIEF\.voice must be a mapping"):
        load_project_brief(project)


def test_whitespace_only_path_normalizes_to_none(tmp_path: Path) -> None:
    """Empty-string values normalize to None (the ``theme`` precedent)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: "   "
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.values is None
    assert brief.voice.is_empty


# ---------------------------------------------------------------------------
# Resolution tests (resolve_voice_docs)
# ---------------------------------------------------------------------------


def _make_consumer(tmp_path: Path) -> Path:
    consumer = tmp_path / "consumer"
    (consumer / ".anvil").mkdir(parents=True)
    return consumer


def test_resolve_project_root_hit_wins(tmp_path: Path) -> None:
    """Project-root copy shadows the consumer-root copy (first hit wins)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: VALUES.md
        {_DOCS_STANZA}""",
    )
    (consumer / "VALUES.md").write_text("consumer persona", encoding="utf-8")
    (project / "VALUES.md").write_text("ghostwritten persona", encoding="utf-8")

    resolved = resolve_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    entry = resolved[0]
    assert entry.kind == "values"
    assert entry.missing is False
    assert entry.source == "project"
    assert entry.paths == [str((project / "VALUES.md").resolve())]


def test_resolve_consumer_root_fallback(tmp_path: Path) -> None:
    """No project-root copy → the consumer-root copy resolves (the common
    persona-level repo-root shape)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          style_guide: STYLE_GUIDE.md
        {_DOCS_STANZA}""",
    )
    (consumer / "STYLE_GUIDE.md").write_text("register rules", encoding="utf-8")

    resolved = resolve_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    entry = resolved[0]
    assert entry.kind == "style_guide"
    assert entry.missing is False
    assert entry.source == "consumer"
    assert entry.paths == [str((consumer / "STYLE_GUIDE.md").resolve())]


def test_resolve_both_missing_structured_entry(tmp_path: Path) -> None:
    """Declared-but-missing comes back as a structured entry — no raise."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          vocabulary: VOCABULARY.md
        {_DOCS_STANZA}""",
    )
    resolved = resolve_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    entry = resolved[0]
    assert entry.kind == "vocabulary"
    assert entry.missing is True
    assert entry.paths == []
    assert entry.source is None
    assert entry.declared == "VOCABULARY.md"


def test_resolve_corpus_glob_expansion_sorted(tmp_path: Path) -> None:
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          corpus: writing-corpus/**/*.md
        {_DOCS_STANZA}""",
    )
    corpus = consumer / "writing-corpus" / "2025"
    corpus.mkdir(parents=True)
    (corpus / "post-b.md").write_text("b", encoding="utf-8")
    (corpus / "post-a.md").write_text("a", encoding="utf-8")
    (consumer / "writing-corpus" / "top.md").write_text("t", encoding="utf-8")

    resolved = resolve_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    entry = resolved[0]
    assert entry.kind == "corpus"
    assert entry.missing is False
    assert entry.source == "consumer"
    assert entry.paths == sorted(entry.paths)
    assert [Path(p).name for p in entry.paths] == [
        "post-a.md",
        "post-b.md",
        "top.md",
    ]


def test_resolve_corpus_zero_matches_is_missing(tmp_path: Path) -> None:
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          corpus: writing-corpus/**/*.md
        {_DOCS_STANZA}""",
    )
    resolved = resolve_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    assert resolved[0].kind == "corpus"
    assert resolved[0].missing is True
    assert resolved[0].paths == []


def test_resolve_load_order_values_first(tmp_path: Path) -> None:
    """Entries come back in the documented load order:
    values → style_guide → vocabulary → corpus."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          corpus: writing-corpus/*.md
          style_guide: STYLE_GUIDE.md
          vocabulary: VOCABULARY.md
          values: VALUES.md
        {_DOCS_STANZA}""",
    )
    resolved = resolve_voice_docs(project, consumer_root=consumer)
    assert [e.kind for e in resolved] == list(VOICE_DOC_KINDS)
    assert [e.kind for e in resolved] == [
        "values",
        "style_guide",
        "vocabulary",
        "corpus",
    ]


def test_resolve_no_brief_returns_empty(tmp_path: Path) -> None:
    project = tmp_path / "no-brief"
    project.mkdir()
    assert resolve_voice_docs(project, consumer_root=tmp_path) == []


def test_resolve_no_voice_block_returns_empty(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(project, f"project: proj\n{_DOCS_STANZA}")
    assert resolve_voice_docs(project, consumer_root=tmp_path) == []


def test_resolve_invalid_brief_returns_empty(tmp_path: Path) -> None:
    """A structurally invalid BRIEF degrades to the inactive path
    (mirrors load_rubric_overrides_for_slug's lenient swallow)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          values: VALUES.md
        documents:
          - slug: acme
            artifact_type: not-a-registered-type
        """,
    )
    assert resolve_voice_docs(project, consumer_root=tmp_path) == []


def test_resolve_no_consumer_root_project_only(tmp_path: Path) -> None:
    """Without a ``.anvil/`` ancestor (and no explicit consumer_root),
    only the project root participates in resolution."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: VALUES.md
        {_DOCS_STANZA}""",
    )
    (project / "VALUES.md").write_text("v", encoding="utf-8")
    resolved = resolve_voice_docs(project)
    assert len(resolved) == 1
    assert resolved[0].source == "project"
    assert resolved[0].missing is False


def test_resolve_absolute_path(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    abs_doc = tmp_path / "elsewhere" / "VALUES.md"
    abs_doc.parent.mkdir(parents=True)
    abs_doc.write_text("v", encoding="utf-8")
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: {abs_doc}
        {_DOCS_STANZA}""",
    )
    resolved = resolve_voice_docs(project, consumer_root=tmp_path)
    assert len(resolved) == 1
    assert resolved[0].source == "absolute"
    assert resolved[0].paths == [str(abs_doc)]


# ---------------------------------------------------------------------------
# Inertness regression (no voice block → byte-identical parse surfaces)
# ---------------------------------------------------------------------------


def test_inertness_no_voice_block_brief_unchanged(tmp_path: Path) -> None:
    """A BRIEF without ``voice:`` parses to the same surfaces as before
    the field shipped: ``voice is None`` and the RubricOverrides path is
    untouched."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
            rubric_overrides:
              dim_1_calibration: "decision-framework"
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.voice is None
    overrides = load_rubric_overrides_for_slug(project, "acme")
    assert overrides.calibration_for(1) == "decision-framework"
    assert not overrides.unknown_keys


def test_voice_docs_model_exported() -> None:
    """The new public names are exported from the canonical module."""
    import anvil.lib.project_brief as pb

    assert "VoiceDocs" in pb.__all__
    assert "ResolvedVoiceDoc" in pb.__all__
    assert "resolve_voice_docs" in pb.__all__
    assert "VOICE_DOC_KINDS" in pb.__all__
    assert VoiceDocs is pb.VoiceDocs
    assert ResolvedVoiceDoc is pb.ResolvedVoiceDoc
    assert isinstance(ProjectBrief.model_fields["voice"].default, type(None))
