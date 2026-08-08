"""Tests for the top-level ``quarantine:`` BRIEF key (issue #914).

An optional **top-level** ``quarantine:`` key on the project BRIEF declares
a list of literal figure/range tokens that a ``hard_rules`` entry forbids
porting from a project's private artifacts (e.g. a memo) into its
customer-facing siblings (e.g. a deck). Parsed into
``ProjectBrief.quarantine: List[str]`` via the same
``_normalize_string_list`` helper that already normalizes ``hard_rules`` —
list-of-strings shape, empty list default when the key is absent.

Distinct from ``hard_rules`` (free-form reviewer prose): ``quarantine`` is
the machine-matchable token surface ``anvil/lib/parity.py``'s deck↔memo
parity lint consumes via ``_extract_quarantine_corpus`` /
``quarantine_corpus`` — see ``tests/lib/test_parity.py`` for the
lint-side behavior this field feeds.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from anvil.lib.project_brief import ProjectBrief, load_project_brief
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


def test_quarantine_list_parses(tmp_path: Path) -> None:
    """``quarantine: [$400M, 20-40%]`` parses to the ordered list."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        quarantine:
          - "$400M"
          - "20-40%"
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.quarantine == ["$400M", "20-40%"]


def test_absent_quarantine_key_is_empty_list(tmp_path: Path) -> None:
    """No ``quarantine:`` key → ``ProjectBrief.quarantine == []`` (byte-identical
    to pre-#914 BRIEFs — the default matches ``hard_rules``' empty-list
    default, not ``corpus``'s ``None`` default)."""
    project = tmp_path / "proj"
    _write_brief(project, f"project: proj\n{_DOCS_STANZA}")
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.quarantine == []


def test_null_quarantine_is_empty_list(tmp_path: Path) -> None:
    """An explicit ``quarantine: null`` normalizes to ``[]`` (inactive)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        quarantine: null
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.quarantine == []


def test_quarantine_distinct_from_hard_rules(tmp_path: Path) -> None:
    """``hard_rules`` (prose) and ``quarantine`` (literal tokens) coexist
    without either field bleeding into the other."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        hard_rules:
          - "Cite $256M net revenue, never the $400M gross figure."
        quarantine:
          - "$400M"
        {_DOCS_STANZA}""",
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.hard_rules == ["Cite $256M net revenue, never the $400M gross figure."]
    assert brief.quarantine == ["$400M"]


def test_quarantine_non_list_raises_value_error(tmp_path: Path) -> None:
    """A non-list ``quarantine:`` value raises the same STRICT type error
    the other ``_normalize_string_list`` fields (``hard_rules`` /
    ``audience``) raise."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        quarantine: "$400M"
        {_DOCS_STANZA}""",
    )
    try:
        load_project_brief(project)
        raised = False
    except ValueError as exc:
        raised = True
        assert "quarantine" in str(exc)
    assert raised, "a non-list quarantine value must raise ValueError"


def test_quarantine_field_default_is_empty_list() -> None:
    """Schema-level default (no BRIEF involved): constructing a
    ``ProjectBrief`` without ``quarantine=`` yields ``[]``."""
    brief = ProjectBrief(
        project="proj",
        documents=[{"slug": "acme", "artifact_type": "investment-memo"}],
    )
    assert brief.quarantine == []
