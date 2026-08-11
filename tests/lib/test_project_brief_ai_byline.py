"""Tests for the top-level ``ai_byline:`` BRIEF key + ``resolve_ai_byline``
(issue #941).

The opt-in AI-authorship disclosure contract's parsing/resolution half:
an optional **top-level** ``ai_byline:`` key on the project BRIEF
declares whether anvil should append a short, configurable provenance
line to rendered artifacts, parsed into
``ProjectBrief.ai_byline: Optional[AiByline]`` and resolved —
strictly opt-in, ``enabled: false`` by default — by
:func:`resolve_ai_byline`. Absent key, ``null``, or ``enabled: false``
are all the byte-identical inactive path: no line is ever rendered.

Distinct from the ``corpus:`` claim-provenance tier (#597, substance
verification) and the ``voice:`` grounding-docs tier (#461, register
fidelity) — a project may declare any combination of the three with no
conflict.
"""

from __future__ import annotations

import textwrap
import warnings
from pathlib import Path

import pytest

from anvil.lib.ai_byline import DEFAULT_PLACEMENT, DEFAULT_TEXT
from anvil.lib.project_brief import (
    AiByline,
    ProjectBrief,
    ResolvedAiByline,
    load_project_brief,
    resolve_ai_byline,
)
from anvil.lib.project_discovery import BRIEF_FILENAME


def _write_brief(project: Path, frontmatter: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / BRIEF_FILENAME).write_text(
        f"---\n{textwrap.dedent(frontmatter)}---\n\n# BRIEF\n",
        encoding="utf-8",
    )


_DOCS_STANZA = (
    "documents:\n"
    "          - slug: acme\n"
    "            artifact_type: investment-memo\n"
)


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


def test_absent_ai_byline_key_is_none(tmp_path: Path) -> None:
    """No ``ai_byline:`` key -> ``ProjectBrief.ai_byline is None`` (the
    byte-identical inactive path, mirroring ``corpus``/``voice``)."""
    project = tmp_path / "proj"
    _write_brief(project, f"project: proj\n{_DOCS_STANZA}")
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.ai_byline is None


def test_null_ai_byline_is_none(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline: null
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.ai_byline is None


def test_enabled_true_parses(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.ai_byline is not None
    assert brief.ai_byline.enabled is True
    assert brief.ai_byline.text is None
    assert brief.ai_byline.placement is None
    assert brief.ai_byline.model_name is None


def test_enabled_absent_defaults_false(tmp_path: Path) -> None:
    """A block declared with no ``enabled:`` key still defaults to False —
    strictly opt-in even with other sub-keys set."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          text: "Custom line."
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.ai_byline is not None
    assert brief.ai_byline.enabled is False


def test_full_block_parses(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
          text: "Drafted with {{model}} assistance, edited by Robb."
          placement: footer
          model_name: Claude
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.ai_byline == AiByline(
        enabled=True,
        text="Drafted with {model} assistance, edited by Robb.",
        placement="footer",
        model_name="Claude",
        unknown_keys={},
    )


def test_enabled_non_bool_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: "true"
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"BRIEF\.ai_byline\.enabled must be a bool"):
        load_project_brief(project)


def test_unrecognized_placement_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
          placement: sidebar
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"BRIEF\.ai_byline\.placement must be one of"):
        load_project_brief(project)


@pytest.mark.parametrize("placement", ["byline", "footer", "frontmatter-only"])
def test_recognized_placements_accepted(tmp_path: Path, placement: str) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
          placement: {placement}
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.ai_byline is not None
    assert brief.ai_byline.placement == placement


def test_non_string_text_rejected(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
          text: 42
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"BRIEF\.ai_byline\.text must be a string"):
        load_project_brief(project)


def test_mapping_ai_byline_required(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline: enabled
        {_DOCS_STANZA}""",
    )
    with pytest.raises(ValueError, match=r"BRIEF\.ai_byline must be a mapping"):
        load_project_brief(project)


def test_unknown_sub_key_preserved_and_warns(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
          tone: cheeky
        {_DOCS_STANZA}""",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        brief = load_project_brief(project)
    assert brief is not None
    assert brief.ai_byline is not None
    assert brief.ai_byline.unknown_keys == {"tone": "cheeky"}
    assert any("ai_byline.tone" in str(w.message) for w in caught)


def test_whitespace_only_text_normalizes_to_none(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
          text: "   "
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.ai_byline is not None
    assert brief.ai_byline.text is None


# ---------------------------------------------------------------------------
# Resolution tests (resolve_ai_byline)
# ---------------------------------------------------------------------------


def test_resolve_inactive_when_absent(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(project, f"project: proj\n{_DOCS_STANZA}")
    assert resolve_ai_byline(project, consumer_root=tmp_path) is None


def test_resolve_inactive_when_enabled_false(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: false
          text: "Should never appear."
        {_DOCS_STANZA}""",
    )
    assert resolve_ai_byline(project, consumer_root=tmp_path) is None


def test_resolve_no_brief_returns_none(tmp_path: Path) -> None:
    project = tmp_path / "no-brief"
    project.mkdir()
    assert resolve_ai_byline(project, consumer_root=tmp_path) is None


def test_resolve_invalid_brief_returns_none(tmp_path: Path) -> None:
    """A structurally invalid BRIEF degrades to the inactive path (lenient
    swallow, mirrors resolve_corpus_dirs / resolve_voice_docs)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        ai_byline:
          enabled: true
        documents:
          - slug: acme
            artifact_type: not-a-registered-type
        """,
    )
    assert resolve_ai_byline(project, consumer_root=tmp_path) is None


def test_resolve_active_default_text_and_placement(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
        {_DOCS_STANZA}""",
    )
    resolved = resolve_ai_byline(project, consumer_root=tmp_path)
    assert resolved == ResolvedAiByline(text=DEFAULT_TEXT, placement=DEFAULT_PLACEMENT)


def test_resolve_custom_text_and_placement(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
          text: "Drafted with {{model}} assistance."
          model_name: Claude
          placement: footer
        {_DOCS_STANZA}""",
    )
    resolved = resolve_ai_byline(project, consumer_root=tmp_path)
    assert resolved is not None
    assert resolved.text == "Drafted with Claude assistance."
    assert resolved.placement == "footer"


def test_resolve_model_name_kwarg_overrides_brief(tmp_path: Path) -> None:
    """A caller-supplied ``model_name=`` overrides the BRIEF-declared
    value (call-site override, e.g. a renderer that knows its own model
    string more precisely than the BRIEF author guessed)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
          text: "Drafted with {{model}}."
          model_name: "Some Model"
        {_DOCS_STANZA}""",
    )
    resolved = resolve_ai_byline(
        project, consumer_root=tmp_path, model_name="Claude Opus"
    )
    assert resolved is not None
    assert resolved.text == "Drafted with Claude Opus."


def test_resolve_date_kwarg_interpolates(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
          text: "Drafted with AI assistance on {{date}}."
        {_DOCS_STANZA}""",
    )
    resolved = resolve_ai_byline(project, consumer_root=tmp_path, date="2026-08-11")
    assert resolved is not None
    assert resolved.text == "Drafted with AI assistance on 2026-08-11."


def test_resolve_deterministic_no_clock_read(tmp_path: Path) -> None:
    """Two resolutions with identical inputs (no ``date=`` supplied)
    produce identical output — the resolver never reads the clock
    itself."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        ai_byline:
          enabled: true
        {_DOCS_STANZA}""",
    )
    first = resolve_ai_byline(project, consumer_root=tmp_path)
    second = resolve_ai_byline(project, consumer_root=tmp_path)
    assert first == second


# ---------------------------------------------------------------------------
# Independence from voice/corpus + inertness + exports
# ---------------------------------------------------------------------------


def test_ai_byline_independent_of_voice_and_corpus(tmp_path: Path) -> None:
    """A project may declare ``voice:``, ``corpus:``, and ``ai_byline:``
    together with no conflict — each resolves through its own helper."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        voice:
          values: VALUES.md
        corpus:
          - transcripts/
        ai_byline:
          enabled: true
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.voice is not None
    assert brief.corpus == ["transcripts/"]
    assert brief.ai_byline is not None
    assert brief.ai_byline.enabled is True

    resolved = resolve_ai_byline(project, consumer_root=tmp_path)
    assert resolved is not None
    assert resolved.text == DEFAULT_TEXT


def test_inertness_no_ai_byline_key_byte_identical(tmp_path: Path) -> None:
    """A BRIEF without ``ai_byline:`` parses to the same surfaces as
    before the field shipped: ``ai_byline is None`` and
    ``resolve_ai_byline`` returns ``None`` (byte-identical-when-absent
    regression lock)."""
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
    assert brief is not None
    assert brief.ai_byline is None
    assert resolve_ai_byline(project, consumer_root=tmp_path) is None


def test_ai_byline_names_exported() -> None:
    import anvil.lib.project_brief as pb

    assert "AiByline" in pb.__all__
    assert "ResolvedAiByline" in pb.__all__
    assert "resolve_ai_byline" in pb.__all__
    assert AiByline is pb.AiByline
    assert ResolvedAiByline is pb.ResolvedAiByline
    assert resolve_ai_byline is pb.resolve_ai_byline
    assert isinstance(ProjectBrief.model_fields["ai_byline"].default, type(None))
