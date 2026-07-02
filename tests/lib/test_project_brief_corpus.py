"""Tests for the top-level ``corpus:`` BRIEF key + ``resolve_corpus_dirs`` (issue #597).

The local-corpus claim-provenance contract's parsing/resolution half: an
optional **top-level** ``corpus:`` key on the project BRIEF declares a
list of read-only ground-truth *directory* paths (interview transcripts,
family letters, engagement notes), parsed into
``ProjectBrief.corpus: Optional[List[str]]`` and resolved — project-root
first, then consumer-root — by :func:`resolve_corpus_dirs`. Missing-dir
results are structured ``missing: true`` :class:`ResolvedCorpusDir`
entries (never a raise); an absent key is the byte-identical inactive
path.

This is the substance-verification tier (does the corpus *contain* the
claimed fact?), distinct from — and independent of — the ``voice.corpus``
glob (author-persona published exemplars, #461) and the ``voice.subjects``
voice-fidelity tier (#598). A project may carry both a top-level
``corpus:`` and a nested ``voice.corpus`` with no conflict.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from anvil.lib.project_brief import (
    ProjectBrief,
    ResolvedCorpusDir,
    load_project_brief,
    resolve_corpus_dirs,
    resolve_voice_docs,
)
from anvil.lib.project_discovery import BRIEF_FILENAME


def _write_brief(project: Path, frontmatter: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / BRIEF_FILENAME).write_text(
        f"---\n{textwrap.dedent(frontmatter)}---\n\n# BRIEF\n",
        encoding="utf-8",
    )


# NOTE: continuation lines carry the same 8-space base indent as the test
# f-string templates below, so textwrap.dedent inside _write_brief strips a
# uniform prefix and yields well-formed YAML.
_DOCS_STANZA = (
    "documents:\n"
    "          - slug: acme\n"
    "            artifact_type: investment-memo\n"
)


def _make_consumer(tmp_path: Path) -> Path:
    consumer = tmp_path / "consumer"
    (consumer / ".anvil").mkdir(parents=True)
    return consumer


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


def test_corpus_list_parses(tmp_path: Path) -> None:
    """``corpus: [transcripts/, letters/]`` parses to the ordered list."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - transcripts/
          - letters/
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.corpus == ["transcripts/", "letters/"]


def test_corpus_flow_list_parses(tmp_path: Path) -> None:
    """The YAML flow-list shape parses identically to the block shape."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus: [transcripts/, letters/]
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.corpus == ["transcripts/", "letters/"]


def test_single_string_normalizes_to_list(tmp_path: Path) -> None:
    """``corpus: transcripts/`` normalizes to ``["transcripts/"]``."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus: transcripts/
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.corpus == ["transcripts/"]


def test_empty_list_normalizes_to_none(tmp_path: Path) -> None:
    """``corpus: []`` normalizes to None (tier inactive)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus: []
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.corpus is None
    # Inactive: resolver treats the empty list exactly like absence.
    assert resolve_corpus_dirs(project, consumer_root=tmp_path) == []


def test_absent_corpus_key_is_none(tmp_path: Path) -> None:
    """No ``corpus:`` key → ``ProjectBrief.corpus is None`` (byte-identical)."""
    project = tmp_path / "proj"
    _write_brief(project, f"project: proj\n{_DOCS_STANZA}")
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.corpus is None


def test_null_corpus_is_none(tmp_path: Path) -> None:
    """An explicit ``corpus: null`` normalizes to None (inactive)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus: null
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.corpus is None


def test_whitespace_only_entries_dropped(tmp_path: Path) -> None:
    """Whitespace-only entries are dropped; an all-blank list → None."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - transcripts/
          - "   "
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.corpus == ["transcripts/"]


def test_non_string_list_element_rejected(tmp_path: Path) -> None:
    """A non-string list element raises with the field path ``corpus[1]``."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - transcripts/
          - 42
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"BRIEF\.corpus\[1\]"):
        load_project_brief(project)


def test_mapping_corpus_rejected(tmp_path: Path) -> None:
    """A mapping value (neither list nor string) raises naming the shapes."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          transcripts: yes
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"BRIEF\.corpus must be a list"):
        load_project_brief(project)


# ---------------------------------------------------------------------------
# Resolution tests (resolve_corpus_dirs)
# ---------------------------------------------------------------------------


def test_resolve_project_root_hit_wins(tmp_path: Path) -> None:
    """Project-root dir shadows the consumer-root dir (first hit wins)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - transcripts/
        {_DOCS_STANZA}""",
    )
    (consumer / "transcripts").mkdir()
    (project / "transcripts").mkdir()

    resolved = resolve_corpus_dirs(project, consumer_root=consumer)
    assert len(resolved) == 1
    entry = resolved[0]
    assert isinstance(entry, ResolvedCorpusDir)
    assert entry.declared == "transcripts/"
    assert entry.missing is False
    assert entry.source == "project"
    assert entry.path == str((project / "transcripts").resolve())


def test_resolve_consumer_root_fallback(tmp_path: Path) -> None:
    """No project-root dir → the consumer-root dir resolves (the common
    project-level evidence-base shape)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - transcripts/
        {_DOCS_STANZA}""",
    )
    (consumer / "transcripts").mkdir()

    resolved = resolve_corpus_dirs(project, consumer_root=consumer)
    assert len(resolved) == 1
    entry = resolved[0]
    assert entry.missing is False
    assert entry.source == "consumer"
    assert entry.path == str((consumer / "transcripts").resolve())


def test_resolve_missing_dir_structured_entry(tmp_path: Path) -> None:
    """Declared-but-missing comes back as a structured entry — no raise."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - transcripts/
        {_DOCS_STANZA}""",
    )
    resolved = resolve_corpus_dirs(project, consumer_root=consumer)
    assert len(resolved) == 1
    entry = resolved[0]
    assert entry.missing is True
    assert entry.path is None
    assert entry.source is None
    assert entry.declared == "transcripts/"


def test_resolve_file_of_same_name_is_missing(tmp_path: Path) -> None:
    """A *file* named like the declared corpus dir does NOT satisfy the
    directory contract — it resolves missing."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - transcripts/
        {_DOCS_STANZA}""",
    )
    (consumer / "transcripts").write_text("not a dir", encoding="utf-8")

    resolved = resolve_corpus_dirs(project, consumer_root=consumer)
    assert len(resolved) == 1
    assert resolved[0].missing is True


def test_resolve_mixed_present_missing_declared_order(tmp_path: Path) -> None:
    """Two entries, one present one absent → two entries in declared order,
    each resolved independently."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - transcripts/
          - letters/
        {_DOCS_STANZA}""",
    )
    (consumer / "transcripts").mkdir()  # present
    # letters/ intentionally absent

    resolved = resolve_corpus_dirs(project, consumer_root=consumer)
    assert [e.declared for e in resolved] == ["transcripts/", "letters/"]
    assert resolved[0].missing is False
    assert resolved[0].source == "consumer"
    assert resolved[1].missing is True
    assert resolved[1].source is None


def test_resolve_absolute_path(tmp_path: Path) -> None:
    """An absolute declared dir bypasses the root walk (source=absolute)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    abs_dir = tmp_path / "elsewhere" / "transcripts"
    abs_dir.mkdir(parents=True)
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - {abs_dir}
        {_DOCS_STANZA}""",
    )
    resolved = resolve_corpus_dirs(project, consumer_root=consumer)
    assert len(resolved) == 1
    assert resolved[0].source == "absolute"
    assert resolved[0].missing is False
    assert resolved[0].path == str(abs_dir.resolve())


def test_resolve_absolute_missing_is_structured(tmp_path: Path) -> None:
    """An absolute declared dir that does not exist → missing, no raise."""
    project = tmp_path / "proj"
    abs_dir = tmp_path / "elsewhere" / "transcripts"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - {abs_dir}
        {_DOCS_STANZA}""",
    )
    resolved = resolve_corpus_dirs(project, consumer_root=tmp_path)
    assert len(resolved) == 1
    assert resolved[0].missing is True
    assert resolved[0].path is None


def test_resolve_no_consumer_root_project_only(tmp_path: Path) -> None:
    """Without a ``.anvil/`` ancestor (and no explicit consumer_root), only
    the project root participates in resolution."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - transcripts/
        {_DOCS_STANZA}""",
    )
    (project / "transcripts").mkdir()
    resolved = resolve_corpus_dirs(project)
    assert len(resolved) == 1
    assert resolved[0].source == "project"
    assert resolved[0].missing is False


def test_resolve_gitignored_dir_resolves(tmp_path: Path) -> None:
    """Resolution is filesystem-driven, never git-aware: a gitignored corpus
    dir resolves identically to a committed one (#577 private-grounding
    posture applies to the corpus tier)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    (consumer / ".gitignore").write_text("transcripts/\n", encoding="utf-8")
    _write_brief(
        project,
        f"""\
        project: proj
        corpus:
          - transcripts/
        {_DOCS_STANZA}""",
    )
    (consumer / "transcripts").mkdir()

    resolved = resolve_corpus_dirs(project, consumer_root=consumer)
    assert len(resolved) == 1
    assert resolved[0].missing is False


def test_resolve_no_brief_returns_empty(tmp_path: Path) -> None:
    project = tmp_path / "no-brief"
    project.mkdir()
    assert resolve_corpus_dirs(project, consumer_root=tmp_path) == []


def test_resolve_no_corpus_key_returns_empty(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(project, f"project: proj\n{_DOCS_STANZA}")
    assert resolve_corpus_dirs(project, consumer_root=tmp_path) == []


def test_resolve_invalid_brief_returns_empty(tmp_path: Path) -> None:
    """A structurally invalid BRIEF degrades to the inactive path (lenient
    swallow, mirrors resolve_voice_docs)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        corpus:
          - transcripts/
        documents:
          - slug: acme
            artifact_type: not-a-registered-type
        """,
    )
    assert resolve_corpus_dirs(project, consumer_root=tmp_path) == []


# ---------------------------------------------------------------------------
# Independence from voice.corpus + inertness + exports
# ---------------------------------------------------------------------------


def test_top_level_corpus_independent_of_voice_corpus(tmp_path: Path) -> None:
    """A project may carry BOTH a nested ``voice.corpus`` glob and a
    top-level ``corpus:`` list — they resolve through different helpers with
    no conflict."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          corpus: writing-corpus/**/*.md
        corpus:
          - transcripts/
        {_DOCS_STANZA}""",
    )
    (project / "transcripts").mkdir()
    wc = consumer / "writing-corpus"
    wc.mkdir()
    (wc / "post.md").write_text("exemplar", encoding="utf-8")

    brief = load_project_brief(project)
    assert brief is not None
    # Top-level corpus (factual ground truth) is a list of dirs.
    assert brief.corpus == ["transcripts/"]
    # voice.corpus (author exemplars) is a single glob string.
    assert brief.voice is not None
    assert brief.voice.corpus == "writing-corpus/**/*.md"

    # The two resolvers operate independently.
    corpus_dirs = resolve_corpus_dirs(project, consumer_root=consumer)
    assert len(corpus_dirs) == 1 and corpus_dirs[0].source == "project"
    voice_docs = resolve_voice_docs(project, consumer_root=consumer)
    assert [e.kind for e in voice_docs] == ["corpus"]


def test_inertness_no_corpus_key_byte_identical(tmp_path: Path) -> None:
    """A BRIEF without ``corpus:`` parses to the same surfaces as before the
    field shipped: ``corpus is None`` and ``resolve_corpus_dirs`` returns
    ``[]`` (the byte-identical-when-absent regression lock)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        voice:
          values: VALUES.md
        documents:
          - slug: acme
            artifact_type: investment-memo
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.corpus is None
    assert resolve_corpus_dirs(project, consumer_root=tmp_path) == []


def test_corpus_names_exported() -> None:
    import anvil.lib.project_brief as pb

    assert "ResolvedCorpusDir" in pb.__all__
    assert "resolve_corpus_dirs" in pb.__all__
    assert ResolvedCorpusDir is pb.ResolvedCorpusDir
    assert resolve_corpus_dirs is pb.resolve_corpus_dirs
    assert isinstance(ProjectBrief.model_fields["corpus"].default, type(None))


# ---------------------------------------------------------------------------
# provenance.md snippet presence (test_snippet_contents.py pattern)
# ---------------------------------------------------------------------------


def _provenance_snippet_path() -> Path:
    import anvil.lib as lib

    return Path(lib.__file__).parent / "snippets" / "provenance.md"


def test_provenance_snippet_exists() -> None:
    assert _provenance_snippet_path().is_file()


@pytest.mark.parametrize(
    "needle",
    [
        # Section 1 — BRIEF activation
        "corpus:",
        # Section 2 — provenance.md file shape
        "provenance.md",
        # Section 4 — audit-critic contract
        "tool_evidence",
        "tool_calls",
        # Section 5 — five-way classification
        "VERIFIED",
        "PARAPHRASE_OK",
        "MISMATCH",
        "NOT_FOUND",
        "FABRICATED",
        # Section 6 — fabrication-class critical flags
        "fabricated_quote",
        "fabricated_fact",
        "misattribution_of_substance",
        "anachronism",
        "unattributed_paraphrase",
        # Section 7 — _progress.json shape
        "provenance_summary",
        # Section 8 — sibling dir naming
        "corpus-audit",
    ],
)
def test_provenance_snippet_documents_contract(needle: str) -> None:
    text = _provenance_snippet_path().read_text(encoding="utf-8")
    assert needle in text, f"provenance.md missing required contract token: {needle}"
