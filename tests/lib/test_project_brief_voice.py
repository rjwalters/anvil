"""Tests for the project BRIEF ``voice:`` block + ``resolve_voice_docs`` (issue #461).

The voice/persona grounding-docs contract: an optional top-level
``voice:`` key on the project BRIEF declares up to four persona docs
(``style_guide`` / ``vocabulary`` / ``values`` / ``corpus`` glob),
parsed into :class:`VoiceDocs` and resolved — project-root first, then
consumer-root — by :func:`resolve_voice_docs`. Missing-file results
are structured ``missing: true`` entries (never a raise); an absent
block is the byte-identical inactive path.

One deliberate deviation from the curation comment's "unknown sub-keys
rejected (STRICT)" line, per the orchestration note on the build:
unknown sub-keys are TOLERATED — preserved verbatim under
``VoiceDocs.unknown_keys`` with a ``warnings.warn`` breadcrumb (the
lenient inner-block posture of ``rubric_overrides.unknown_keys``). The
recognized sub-keys remain STRICT on type (non-string values raise).

Issue #468 wired the fifth recognized sub-key, ``rhetoric_rules`` — a
gate-side JSON rule file for the #463 rhetoric lint, resolved by the
dedicated :func:`resolve_rhetoric_rules` (NOT a grounding doc: it
never appears in ``resolve_voice_docs`` output and does not count
toward ``is_empty``). Those tests live in the dedicated section below.
"""

from __future__ import annotations

import textwrap
import warnings
from pathlib import Path

import pytest

from anvil.lib.project_brief import (
    VOICE_DOC_KINDS,
    ProjectBrief,
    ResolvedSubjectVoice,
    ResolvedVoiceDoc,
    SubjectVoiceEntry,
    VoiceDocs,
    load_project_brief,
    load_rubric_overrides_for_slug,
    resolve_rhetoric_rules,
    resolve_subject_voice_docs,
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
    """Unknown sub-keys are preserved under unknown_keys (forward-compat),
    with a warning. (Fixture migrated off ``rhetoric_rules`` when #468
    made it a recognized key — ``tone_matrix`` is synthetic.)"""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: VALUES.md
          tone_matrix: TONE.md
        {_DOCS_STANZA}""",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.unknown_keys == {"tone_matrix": "TONE.md"}
    assert brief.voice.values == "VALUES.md"
    assert any("tone_matrix" in str(w.message) for w in caught)


def test_unknown_keys_only_block_is_inactive(tmp_path: Path) -> None:
    """A block declaring ONLY unknown sub-keys does not activate the tier.
    (Fixture migrated off ``rhetoric_rules`` when #468 made it a
    recognized key.)"""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          tone_matrix: TONE.md
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
# Private (.gitignored) grounding — resolution lock (issue #577)
# ---------------------------------------------------------------------------
#
# resolve_voice_docs never consults git status, so a .gitignored declared doc
# must resolve and activate the tier IDENTICALLY to a committed one. These
# tests lock that designed posture: writing a real .gitignore that ignores the
# declared doc changes nothing about resolution. The byte-identical-when-absent
# contract (#428/#452) is re-asserted alongside so a privacy special-case can
# never sneak in that hides a broken private declaration.


def test_private_gitignored_doc_resolves_and_activates_tier(tmp_path: Path) -> None:
    """A declared doc that is .gitignored resolves + activates — git is ignored."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    # The documented private convention: a *.local.md suffix.
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: VALUES.local.md
        {_DOCS_STANZA}""",
    )
    # The private doc exists on disk...
    (consumer / "VALUES.local.md").write_text("private stances", encoding="utf-8")
    # ...and is gitignored at the consumer root (the protected posture #577 ships).
    (consumer / ".gitignore").write_text("*.local.md\n", encoding="utf-8")

    resolved = resolve_voice_docs(project, consumer_root=consumer)
    # Tier ACTIVATES: one entry, resolved, not missing — identical to a
    # committed doc. resolve_voice_docs never consults .gitignore.
    assert len(resolved) == 1
    entry = resolved[0]
    assert entry.kind == "values"
    assert entry.missing is False
    assert entry.source == "consumer"
    assert entry.paths == [str((consumer / "VALUES.local.md").resolve())]


def test_private_voice_locus_doc_resolves(tmp_path: Path) -> None:
    """The alternative `.voice/` locus convention also resolves when gitignored."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: .voice/VALUES.md
        {_DOCS_STANZA}""",
    )
    voice_dir = consumer / ".voice"
    voice_dir.mkdir()
    (voice_dir / "VALUES.md").write_text("private stances", encoding="utf-8")
    (consumer / ".gitignore").write_text("/.voice/\n", encoding="utf-8")

    resolved = resolve_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    assert resolved[0].kind == "values"
    assert resolved[0].missing is False
    assert resolved[0].source == "consumer"
    assert resolved[0].paths == [str((voice_dir / "VALUES.md").resolve())]


def test_private_declared_but_missing_still_surfaces_major_finding(
    tmp_path: Path,
) -> None:
    """A gitignored-but-absent private declaration is NOT special-cased away.

    Privacy must not hide a broken declaration: a declared private doc that
    does not exist on disk surfaces the same structured ``missing: true``
    entry as any other missing declared doc (the reviewer's ``major``
    finding). The .gitignore presence is irrelevant.
    """
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: VALUES.local.md
        {_DOCS_STANZA}""",
    )
    # Gitignore the pattern, but never create the file.
    (consumer / ".gitignore").write_text("*.local.md\n", encoding="utf-8")

    resolved = resolve_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    entry = resolved[0]
    assert entry.kind == "values"
    assert entry.missing is True
    assert entry.paths == []
    assert entry.declared == "VALUES.local.md"


def test_absent_private_declaration_is_byte_identical_empty(tmp_path: Path) -> None:
    """No private declaration → empty list (the #428/#452 zero-new-reads path).

    A .gitignore that *could* match a private doc, with NO ``voice:`` block,
    must still resolve to nothing: the privacy posture adds no new reads when
    the tier is inactive.
    """
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    project.mkdir(parents=True, exist_ok=True)
    (project / BRIEF_FILENAME).write_text(
        "---\nproject: proj\n---\n\n# BRIEF\n", encoding="utf-8"
    )
    (consumer / ".gitignore").write_text("*.local.md\n", encoding="utf-8")
    (consumer / "VALUES.local.md").write_text("orphan private doc", encoding="utf-8")

    assert resolve_voice_docs(project, consumer_root=consumer) == []


# ---------------------------------------------------------------------------
# rhetoric_rules sub-key + resolve_rhetoric_rules (issue #468)
# ---------------------------------------------------------------------------


def test_rhetoric_rules_recognized_no_warning(tmp_path: Path) -> None:
    """``rhetoric_rules`` parses as a typed field — not unknown_keys,
    no warning (issue #468 AC 1)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: VALUES.md
          rhetoric_rules: rhetoric-rules.json
        {_DOCS_STANZA}""",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.rhetoric_rules == "rhetoric-rules.json"
    assert brief.voice.unknown_keys == {}
    assert not any("rhetoric_rules" in str(w.message) for w in caught)


def test_rhetoric_rules_non_string_rejected(tmp_path: Path) -> None:
    """STRICT on type, same as the four grounding-doc sub-keys."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          rhetoric_rules: [a.json, b.json]
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"BRIEF\.voice\.rhetoric_rules"):
        load_project_brief(project)


def test_rhetoric_rules_whitespace_normalizes_to_none(tmp_path: Path) -> None:
    """Whitespace-only value → None → resolver returns None (kwarg omitted)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          rhetoric_rules: "   "
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.rhetoric_rules is None
    assert resolve_rhetoric_rules(project, consumer_root=tmp_path) is None


def test_rhetoric_rules_only_block_does_not_activate_grounding_tier(
    tmp_path: Path,
) -> None:
    """The asymmetry contract (issue #468 AC 3/4): a rhetoric_rules-only
    block keeps ``is_empty`` True, ``resolve_voice_docs`` returns [],
    and ``rhetoric_rules`` never appears in resolve_voice_docs output —
    but ``resolve_rhetoric_rules`` still resolves."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          rhetoric_rules: rhetoric-rules.json
        {_DOCS_STANZA}""",
    )
    (project / "rhetoric-rules.json").write_text("{}", encoding="utf-8")

    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.is_empty
    assert resolve_voice_docs(project, consumer_root=consumer) == []

    entry = resolve_rhetoric_rules(project, consumer_root=consumer)
    assert entry is not None
    assert entry.kind == "rhetoric_rules"
    assert entry.missing is False


def test_resolve_voice_docs_excludes_rhetoric_rules(tmp_path: Path) -> None:
    """Mixed block: the grounding docs resolve via resolve_voice_docs;
    rhetoric_rules never joins that list (return shape unchanged)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: VALUES.md
          rhetoric_rules: rhetoric-rules.json
        {_DOCS_STANZA}""",
    )
    (project / "VALUES.md").write_text("v", encoding="utf-8")
    (project / "rhetoric-rules.json").write_text("{}", encoding="utf-8")

    resolved = resolve_voice_docs(project, consumer_root=consumer)
    assert [e.kind for e in resolved] == ["values"]


def test_resolve_rhetoric_rules_project_root_hit_wins(tmp_path: Path) -> None:
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          rhetoric_rules: rhetoric-rules.json
        {_DOCS_STANZA}""",
    )
    (consumer / "rhetoric-rules.json").write_text("{}", encoding="utf-8")
    (project / "rhetoric-rules.json").write_text("{}", encoding="utf-8")

    entry = resolve_rhetoric_rules(project, consumer_root=consumer)
    assert entry is not None
    assert entry.source == "project"
    assert entry.paths == [str((project / "rhetoric-rules.json").resolve())]


def test_resolve_rhetoric_rules_consumer_fallback(tmp_path: Path) -> None:
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          rhetoric_rules: rhetoric-rules.json
        {_DOCS_STANZA}""",
    )
    (consumer / "rhetoric-rules.json").write_text("{}", encoding="utf-8")

    entry = resolve_rhetoric_rules(project, consumer_root=consumer)
    assert entry is not None
    assert entry.source == "consumer"
    assert entry.paths == [str((consumer / "rhetoric-rules.json").resolve())]


def test_resolve_rhetoric_rules_both_missing_structured(tmp_path: Path) -> None:
    """Declared-but-missing → structured ``missing: true`` entry (never
    a raise, never None) — the caller forwards the joined path anyway."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          rhetoric_rules: rhetoric-rules.json
        {_DOCS_STANZA}""",
    )
    entry = resolve_rhetoric_rules(project, consumer_root=consumer)
    assert entry is not None
    assert entry.missing is True
    assert entry.paths == []
    assert entry.source is None
    assert entry.declared == "rhetoric-rules.json"


def test_resolve_rhetoric_rules_absolute_path(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    abs_rules = tmp_path / "elsewhere" / "rhetoric-rules.json"
    abs_rules.parent.mkdir(parents=True)
    abs_rules.write_text("{}", encoding="utf-8")
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          rhetoric_rules: {abs_rules}
        {_DOCS_STANZA}""",
    )
    entry = resolve_rhetoric_rules(project, consumer_root=tmp_path)
    assert entry is not None
    assert entry.source == "absolute"
    assert entry.paths == [str(abs_rules)]


def test_resolve_rhetoric_rules_inactive_returns_none(tmp_path: Path) -> None:
    """No BRIEF / no voice block / no sub-key / malformed BRIEF → None
    (the caller omits the kwarg; byte-identical defaults-only gate)."""
    # No BRIEF at all.
    bare = tmp_path / "no-brief"
    bare.mkdir()
    assert resolve_rhetoric_rules(bare, consumer_root=tmp_path) is None

    # BRIEF without a voice block.
    no_voice = tmp_path / "no-voice"
    _write_brief(no_voice, f"project: no-voice\n{_DOCS_STANZA}")
    assert resolve_rhetoric_rules(no_voice, consumer_root=tmp_path) is None

    # voice block without the sub-key.
    no_key = tmp_path / "no-key"
    _write_brief(
        no_key,
        f"""\
        project: no-key
        voice:
          values: VALUES.md
        {_DOCS_STANZA}""",
    )
    assert resolve_rhetoric_rules(no_key, consumer_root=tmp_path) is None

    # Structurally invalid BRIEF → lenient swallow.
    invalid = tmp_path / "invalid"
    _write_brief(
        invalid,
        """\
        project: invalid
        voice:
          rhetoric_rules: rhetoric-rules.json
        documents:
          - slug: acme
            artifact_type: not-a-registered-type
        """,
    )
    assert resolve_rhetoric_rules(invalid, consumer_root=tmp_path) is None


def test_rhetoric_rules_not_in_voice_doc_kinds() -> None:
    """The load-order tuple stays a four-doc grounding surface."""
    assert "rhetoric_rules" not in VOICE_DOC_KINDS


def test_resolve_rhetoric_rules_exported() -> None:
    import anvil.lib.project_brief as pb

    assert "resolve_rhetoric_rules" in pb.__all__
    assert resolve_rhetoric_rules is pb.resolve_rhetoric_rules


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


# ===========================================================================
# Subject voice tier (issue #598)
# ===========================================================================
#
# The subject voice tier grounds a third party's rendered dialogue in that
# speaker's *spoken* corpus (interview transcripts), as opposed to the
# author-persona tier above. It activates INDEPENDENTLY of the author tier:
# a subjects-only ``voice:`` block keeps ``VoiceDocs.is_empty == True`` while
# ``has_subjects`` is True and ``resolve_subject_voice_docs`` returns entries.


# ---------------------------------------------------------------------------
# Subject schema parsing
# ---------------------------------------------------------------------------


def test_subject_entry_full_parses(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
              voice_doc: planning/grani-voice.md
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.subjects is not None
    assert len(brief.voice.subjects) == 1
    entry = brief.voice.subjects[0]
    assert isinstance(entry, SubjectVoiceEntry)
    assert entry.name == "grani"
    assert entry.corpus == "transcripts/grani/**/*.md"
    assert entry.voice_doc == "planning/grani-voice.md"


def test_subject_entry_voice_doc_optional(tmp_path: Path) -> None:
    """``voice_doc`` is optional — corpus alone activates the entry."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: aunt-jo
              corpus: transcripts/aunt-jo/**/*.md
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.subjects is not None and len(brief.voice.subjects) == 1
    assert brief.voice.subjects[0].voice_doc is None


def test_subjects_list_parses_in_declared_order(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
            - name: aunt-jo
              corpus: transcripts/aunt-jo/**/*.md
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.subjects is not None
    assert [s.name for s in brief.voice.subjects] == ["grani", "aunt-jo"]


def test_subjects_only_block_keeps_is_empty_true(tmp_path: Path) -> None:
    """The load-bearing independence property: a subjects-only block does
    NOT activate the author voice tier (``is_empty`` stays True), but the
    subject tier IS active (``has_subjects`` True)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.is_empty is True
    assert brief.voice.has_subjects is True
    # The author-tier resolver stays byte-identical empty for subjects-only.
    assert resolve_voice_docs(project, consumer_root=tmp_path) == []


def test_both_tiers_active_independently(tmp_path: Path) -> None:
    """A memoir declaring both an author persona and subjects activates
    both tiers independently."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: VALUES.md
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.is_empty is False  # author tier active (values)
    assert brief.voice.has_subjects is True  # subject tier active


def test_empty_subjects_list_treated_as_absent(tmp_path: Path) -> None:
    """``subjects: []`` normalizes to None (tier inactive) — an empty list
    does not activate the tier."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects: []
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.subjects is None
    assert brief.voice.has_subjects is False
    assert resolve_subject_voice_docs(project, consumer_root=tmp_path) == []


def test_subjects_missing_name_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - corpus: transcripts/grani/**/*.md
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"voice\.subjects\[0\]\.name"):
        load_project_brief(project)


def test_subjects_missing_corpus_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"voice\.subjects\[0\]\.corpus"):
        load_project_brief(project)


def test_subjects_non_string_name_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: 42
              corpus: transcripts/grani/**/*.md
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"voice\.subjects\[0\]\.name"):
        load_project_brief(project)


def test_subjects_non_string_voice_doc_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
              voice_doc: [a.md, b.md]
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"voice\.subjects\[0\]\.voice_doc"):
        load_project_brief(project)


def test_subjects_non_mapping_entry_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - just-a-string
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"voice\.subjects\[0\] must be a mapping"):
        load_project_brief(project)


def test_subjects_non_list_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects: transcripts/grani/**/*.md
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"voice\.subjects must be a list"):
        load_project_brief(project)


def test_subjects_whitespace_voice_doc_normalizes_to_none(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
              voice_doc: "   "
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.subjects is not None
    assert brief.voice.subjects[0].voice_doc is None


def test_subjects_unknown_sub_key_tolerated_with_warning(tmp_path: Path) -> None:
    """Unknown sub-keys inside a subject entry warn and are dropped
    (forward-compat), the lenient inner-block posture."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
              cadence_hint: clipped
        {_DOCS_STANZA}""",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        brief = load_project_brief(project)
    assert brief is not None and brief.voice is not None
    assert brief.voice.subjects is not None and len(brief.voice.subjects) == 1
    assert brief.voice.subjects[0].name == "grani"
    assert any("cadence_hint" in str(w.message) for w in caught)


# ---------------------------------------------------------------------------
# Subject resolution (resolve_subject_voice_docs)
# ---------------------------------------------------------------------------


def test_resolve_subject_project_root_hit(tmp_path: Path) -> None:
    """A subject corpus + voice_doc resolve project-root-first."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
              voice_doc: planning/grani-voice.md
        {_DOCS_STANZA}""",
    )
    tx = project / "transcripts" / "grani"
    tx.mkdir(parents=True)
    (tx / "02.md").write_text("clipped.", encoding="utf-8")
    (tx / "01.md").write_text("Well, I tell you.", encoding="utf-8")
    (project / "planning").mkdir()
    (project / "planning" / "grani-voice.md").write_text("cadence", encoding="utf-8")

    resolved = resolve_subject_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    entry = resolved[0]
    assert isinstance(entry, ResolvedSubjectVoice)
    assert entry.name == "grani"
    assert entry.corpus.kind == "subject_corpus"
    assert entry.corpus.missing is False
    assert entry.corpus.source == "project"
    assert [Path(p).name for p in entry.corpus.paths] == ["01.md", "02.md"]
    assert entry.voice_doc is not None
    assert entry.voice_doc.kind == "subject_voice_doc"
    assert entry.voice_doc.missing is False
    assert entry.voice_doc.source == "project"


def test_resolve_subject_consumer_root_fallback(tmp_path: Path) -> None:
    """A subject corpus resolves against the consumer root when absent at
    the project root."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
        {_DOCS_STANZA}""",
    )
    tx = consumer / "transcripts" / "grani"
    tx.mkdir(parents=True)
    (tx / "01.md").write_text("Well, now.", encoding="utf-8")

    resolved = resolve_subject_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    assert resolved[0].corpus.missing is False
    assert resolved[0].corpus.source == "consumer"
    assert resolved[0].voice_doc is None


def test_resolve_subject_missing_corpus_structured(tmp_path: Path) -> None:
    """A subject corpus glob matching nothing comes back missing:true — no
    raise (the major-finding signal, tier stays active)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
        {_DOCS_STANZA}""",
    )
    resolved = resolve_subject_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    assert resolved[0].corpus.missing is True
    assert resolved[0].corpus.paths == []
    assert resolved[0].corpus.source is None


def test_resolve_subject_missing_voice_doc_structured(tmp_path: Path) -> None:
    """A declared-but-missing subject voice_doc is a missing:true entry,
    NOT None (None means the entry declared no voice_doc)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
              voice_doc: planning/grani-voice.md
        {_DOCS_STANZA}""",
    )
    tx = project / "transcripts" / "grani"
    tx.mkdir(parents=True)
    (tx / "01.md").write_text("Well.", encoding="utf-8")

    resolved = resolve_subject_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    assert resolved[0].corpus.missing is False
    assert resolved[0].voice_doc is not None
    assert resolved[0].voice_doc.missing is True
    assert resolved[0].voice_doc.paths == []


def test_resolve_subject_mixed_present_missing(tmp_path: Path) -> None:
    """Two subjects: one fully present, one wholly missing — declared order
    preserved, each resolved independently."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
              voice_doc: planning/grani-voice.md
            - name: aunt-jo
              corpus: transcripts/aunt-jo/**/*.md
        {_DOCS_STANZA}""",
    )
    tx = project / "transcripts" / "grani"
    tx.mkdir(parents=True)
    (tx / "01.md").write_text("Well.", encoding="utf-8")
    (project / "planning").mkdir()
    (project / "planning" / "grani-voice.md").write_text("cadence", encoding="utf-8")

    resolved = resolve_subject_voice_docs(project, consumer_root=consumer)
    assert [e.name for e in resolved] == ["grani", "aunt-jo"]
    assert resolved[0].corpus.missing is False
    assert resolved[0].voice_doc is not None and resolved[0].voice_doc.missing is False
    assert resolved[1].corpus.missing is True
    assert resolved[1].voice_doc is None


def test_resolve_subject_absolute_corpus(tmp_path: Path) -> None:
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    abs_dir = tmp_path / "abs-transcripts"
    abs_dir.mkdir()
    (abs_dir / "01.md").write_text("Well.", encoding="utf-8")
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: {abs_dir}/**/*.md
        {_DOCS_STANZA}""",
    )
    resolved = resolve_subject_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    assert resolved[0].corpus.missing is False
    assert resolved[0].corpus.source == "absolute"


def test_resolve_subject_declared_order_preserved(tmp_path: Path) -> None:
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: zebra
              corpus: transcripts/zebra/**/*.md
            - name: alpha
              corpus: transcripts/alpha/**/*.md
        {_DOCS_STANZA}""",
    )
    resolved = resolve_subject_voice_docs(project, consumer_root=consumer)
    assert [e.name for e in resolved] == ["zebra", "alpha"]


def test_resolve_subject_no_subjects_returns_empty(tmp_path: Path) -> None:
    """An author-only voice block resolves no subject entries (byte-identical
    empty)."""
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
    assert resolve_subject_voice_docs(project, consumer_root=consumer) == []


def test_resolve_subject_no_voice_block_returns_empty(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(project, f"project: proj\n{_DOCS_STANZA}")
    assert resolve_subject_voice_docs(project, consumer_root=tmp_path) == []


def test_resolve_subject_no_brief_returns_empty(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    assert resolve_subject_voice_docs(project, consumer_root=tmp_path) == []


def test_resolve_subject_invalid_brief_returns_empty(tmp_path: Path) -> None:
    """A structurally invalid BRIEF is swallowed leniently (mirrors
    resolve_voice_docs) — the resolver never raises."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "BRIEF.md").write_text(
        "---\nproject: proj\ndocuments: not-a-list\n---\n# BRIEF\n",
        encoding="utf-8",
    )
    assert resolve_subject_voice_docs(project, consumer_root=tmp_path) == []


def test_resolve_subject_gitignored_corpus_resolves(tmp_path: Path) -> None:
    """Resolution is filesystem-driven, never git-aware: a gitignored
    transcript corpus resolves identically to a committed one (the #577
    private-grounding posture applies to the subject tier)."""
    consumer = _make_consumer(tmp_path)
    project = consumer / "proj"
    (consumer / ".gitignore").write_text("transcripts/\n", encoding="utf-8")
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          subjects:
            - name: grani
              corpus: transcripts/grani/**/*.md
        {_DOCS_STANZA}""",
    )
    tx = project / "transcripts" / "grani"
    tx.mkdir(parents=True)
    (tx / "01.md").write_text("Well.", encoding="utf-8")

    resolved = resolve_subject_voice_docs(project, consumer_root=consumer)
    assert len(resolved) == 1
    assert resolved[0].corpus.missing is False


# ---------------------------------------------------------------------------
# Subject inertness + exports
# ---------------------------------------------------------------------------


def test_subject_inertness_no_voice_block(tmp_path: Path) -> None:
    """A BRIEF with no ``voice:`` block is byte-identical across BOTH the
    author-tier and subject-tier resolvers (#598 must not change pre-#598
    no-voice behavior)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None and brief.voice is None
    assert resolve_voice_docs(project, consumer_root=tmp_path) == []
    assert resolve_subject_voice_docs(project, consumer_root=tmp_path) == []


def test_subject_names_exported() -> None:
    import anvil.lib.project_brief as pb

    assert "SubjectVoiceEntry" in pb.__all__
    assert "ResolvedSubjectVoice" in pb.__all__
    assert "resolve_subject_voice_docs" in pb.__all__
    assert SubjectVoiceEntry is pb.SubjectVoiceEntry
    assert ResolvedSubjectVoice is pb.ResolvedSubjectVoice
    assert resolve_subject_voice_docs is pb.resolve_subject_voice_docs
