"""Tests for ``BriefDocument.pending_sources`` / ``resolve_pending_sources``
(issue #842, phase 1 of #841).

Covers the acceptance criteria's activation contract — mirroring
``spec_ref``'s documented behavior (see
``tests/lib/test_project_brief.py``'s companion-ref section):

- **undeclared** -> ``resolve_pending_sources`` returns ``None`` (tier
  INACTIVE).
- **declared and every source resolves** -> ``missing=False``,
  ``unresolved=[]``.
- **declared but ZERO sources resolve** -> ``missing=True`` (tier
  ACTIVE, degrades gracefully).
- **declared and SOME (not all) sources resolve** -> ``missing=False``
  with the non-matching entries named in ``unresolved``.
- **malformed** ``pending_sources`` (wrong shape) -> the #718
  declared-but-broken posture: ``missing=True`` with ``error`` set,
  never silently swallowed to the inactive ``None`` path. A malformed
  *unrelated* companion field (``spec_ref``) does not affect
  ``resolve_pending_sources``.
- Parse-time shape validation: bare-string shorthand, ``{source,
  expected_by}`` mappings, a YAML-parsed date ``expected_by`` value, and
  the STRICT unknown-key / missing-``source`` rejections.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from anvil.lib.project_brief import (
    CompanionRefTypeError,
    PendingSourceEntry,
    resolve_pending_sources,
    resolve_spec_ref,
)
from anvil.lib.project_discovery import BRIEF_FILENAME


def _write_brief(project: Path, frontmatter: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / BRIEF_FILENAME).write_text(
        f"---\n{textwrap.dedent(frontmatter)}---\n\n# BRIEF\n",
        encoding="utf-8",
    )


def _write_report_brief(project: Path, doc_lines: str) -> None:
    _write_brief(
        project,
        f"""\
        project: proj
        documents:
          - slug: q3-report
            artifact_type: report
{doc_lines}
        """,
    )


# ---------------------------------------------------------------------------
# Parse-time shape validation
# ---------------------------------------------------------------------------


def test_undeclared_pending_sources_is_none_on_document(tmp_path: Path) -> None:
    from anvil.lib.project_brief import load_project_brief

    project = tmp_path / "proj"
    _write_report_brief(project, "")
    brief = load_project_brief(project)
    assert brief.document_for_slug("q3-report").pending_sources is None


def test_bare_string_shorthand_scalar(tmp_path: Path) -> None:
    from anvil.lib.project_brief import load_project_brief

    project = tmp_path / "proj"
    _write_report_brief(
        project, "            pending_sources: customer survey"
    )
    brief = load_project_brief(project)
    entries = brief.document_for_slug("q3-report").pending_sources
    assert entries == [PendingSourceEntry(source="customer survey")]


def test_bare_string_shorthand_in_list(tmp_path: Path) -> None:
    from anvil.lib.project_brief import load_project_brief

    project = tmp_path / "proj"
    _write_report_brief(
        project,
        "            pending_sources:\n"
        "              - customer survey\n"
        "              - source: Q3 earnings\n"
        "                expected_by: 2026-10-15\n",
    )
    brief = load_project_brief(project)
    entries = brief.document_for_slug("q3-report").pending_sources
    assert entries == [
        PendingSourceEntry(source="customer survey"),
        PendingSourceEntry(source="Q3 earnings", expected_by="2026-10-15"),
    ]


def test_yaml_date_expected_by_coerced_to_isoformat_string(
    tmp_path: Path,
) -> None:
    """A YAML author's unquoted ISO date parses as datetime.date — this
    is coerced to its isoformat string rather than rejected."""
    from anvil.lib.project_brief import load_project_brief

    project = tmp_path / "proj"
    _write_report_brief(
        project,
        "            pending_sources:\n"
        "              - source: Q3 earnings\n"
        "                expected_by: 2026-10-15\n",
    )
    brief = load_project_brief(project)
    entry = brief.document_for_slug("q3-report").pending_sources[0]
    assert entry.expected_by == "2026-10-15"


def test_empty_list_normalizes_to_none(tmp_path: Path) -> None:
    from anvil.lib.project_brief import load_project_brief

    project = tmp_path / "proj"
    _write_report_brief(project, "            pending_sources: []")
    brief = load_project_brief(project)
    assert brief.document_for_slug("q3-report").pending_sources is None


def test_null_normalizes_to_none(tmp_path: Path) -> None:
    from anvil.lib.project_brief import load_project_brief

    project = tmp_path / "proj"
    _write_report_brief(project, "            pending_sources:")
    brief = load_project_brief(project)
    assert brief.document_for_slug("q3-report").pending_sources is None


def test_unknown_key_in_mapping_raises(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(
        project,
        "            pending_sources:\n"
        "              - source: x\n"
        "                bogus_key: y\n",
    )
    with pytest.raises(CompanionRefTypeError) as exc_info:
        from anvil.lib.project_brief import load_project_brief

        load_project_brief(project)
    assert exc_info.value.field == "pending_sources"


def test_missing_source_key_in_mapping_raises(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(
        project,
        "            pending_sources:\n"
        "              - expected_by: 2026-10-15\n",
    )
    with pytest.raises(CompanionRefTypeError):
        from anvil.lib.project_brief import load_project_brief

        load_project_brief(project)


def test_empty_string_source_in_mapping_raises(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(
        project,
        "            pending_sources:\n"
        "              - source: '   '\n",
    )
    with pytest.raises(CompanionRefTypeError):
        from anvil.lib.project_brief import load_project_brief

        load_project_brief(project)


def test_non_string_element_raises(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(
        project, "            pending_sources:\n              - 42\n"
    )
    with pytest.raises(CompanionRefTypeError):
        from anvil.lib.project_brief import load_project_brief

        load_project_brief(project)


def test_non_list_non_string_raises(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(project, "            pending_sources: 42")
    with pytest.raises(CompanionRefTypeError):
        from anvil.lib.project_brief import load_project_brief

        load_project_brief(project)


# ---------------------------------------------------------------------------
# resolve_pending_sources — the four-state activation contract
# ---------------------------------------------------------------------------


def test_resolve_undeclared_is_inactive(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(project, "")
    assert resolve_pending_sources(project, "q3-report", "anything") is None


def test_resolve_no_matching_document_is_inactive(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(
        project, "            pending_sources: customer survey"
    )
    assert resolve_pending_sources(project, "no-such-slug", "text") is None


def test_resolve_declared_and_resolves(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(
        project,
        "            pending_sources:\n"
        "              - Q3 earnings report\n"
        "              - customer survey results\n",
    )
    body = (
        "Waiting on [PENDING Q3 earnings report] and "
        "[PENDING customer survey results]."
    )
    resolved = resolve_pending_sources(project, "q3-report", body)
    assert resolved is not None
    assert resolved.missing is False
    assert resolved.unresolved == []
    assert resolved.error is None
    assert all(e.resolved for e in resolved.entries)


def test_resolve_declared_but_missing_zero_resolve(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(
        project, "            pending_sources: Q3 earnings report"
    )
    resolved = resolve_pending_sources(project, "q3-report", "no markers here")
    assert resolved is not None
    assert resolved.missing is True
    assert resolved.entries[0].resolved is False


def test_resolve_partial_resolve(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(
        project,
        "            pending_sources:\n"
        "              - Q3 earnings report\n"
        "              - customer survey results\n",
    )
    body = "Waiting on [PENDING Q3 earnings report] only."
    resolved = resolve_pending_sources(project, "q3-report", body)
    assert resolved is not None
    assert resolved.missing is False
    assert resolved.unresolved == ["customer survey results"]
    resolved_map = {e.source: e.resolved for e in resolved.entries}
    assert resolved_map["Q3 earnings report"] is True
    assert resolved_map["customer survey results"] is False


def test_resolve_ignores_suppressed_markers(tmp_path: Path) -> None:
    """A suppressed marker (anvil-lint-disable) does not count as resolving
    its declared source — mirrors pending_marker's own suppression
    contract (suppressed hits never gate, and here, never resolve)."""
    project = tmp_path / "proj"
    _write_report_brief(
        project, "            pending_sources: Q3 earnings report"
    )
    body = (
        "[PENDING Q3 earnings report] "
        "<!-- anvil-lint-disable: pending_marker -->\n"
    )
    resolved = resolve_pending_sources(project, "q3-report", body)
    assert resolved.missing is True


def test_resolve_ignores_malformed_markers(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(
        project, "            pending_sources: Q3 earnings report"
    )
    resolved = resolve_pending_sources(project, "q3-report", "[PENDING]")
    assert resolved.missing is True


def test_resolve_empty_body_text_all_unresolved(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_report_brief(
        project, "            pending_sources: Q3 earnings report"
    )
    resolved = resolve_pending_sources(project, "q3-report", "")
    assert resolved.missing is True


# ---------------------------------------------------------------------------
# Malformed declaration — #718 declared-but-broken posture
# ---------------------------------------------------------------------------


def test_resolve_malformed_pending_sources_is_missing_with_error(
    tmp_path: Path,
) -> None:
    project = tmp_path / "proj"
    _write_report_brief(project, "            pending_sources: 42")
    resolved = resolve_pending_sources(project, "q3-report", "anything")
    assert resolved is not None
    assert resolved.missing is True
    assert resolved.error is not None
    assert resolved.declared == []
    assert resolved.entries == []


def test_resolve_ignores_unrelated_malformed_spec_ref(tmp_path: Path) -> None:
    """A malformed spec_ref (unrelated companion field) must not make
    resolve_pending_sources return a false missing=True — it should
    swallow to None exactly as any other BRIEF-parse failure would,
    mirroring resolve_code_ref's own #718 test."""
    project = tmp_path / "proj"
    _write_report_brief(
        project,
        "            spec_ref: [1, 2]\n"
        "            pending_sources: Q3 earnings report\n",
    )
    # The BRIEF itself fails to parse structurally (spec_ref is malformed)
    # -> both resolvers see the same CompanionRefTypeError(field="spec_ref").
    # pending_sources' resolver only special-cases ITS OWN field's
    # CompanionRefTypeError, so an unrelated field's malformation swallows
    # to None (tier inactive) — the resolve_code_ref-documented posture for
    # an unrelated malformed field. spec_ref's OWN resolver, by contrast,
    # DOES own this exception and activates its declared-but-broken path.
    assert resolve_pending_sources(project, "q3-report", "text") is None
    resolved_spec = resolve_spec_ref(project, "q3-report")
    assert resolved_spec is not None
    assert resolved_spec.missing is True


def test_resolve_structurally_invalid_brief_is_none(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(project, "project: proj\n")  # no documents key -> ValueError
    assert resolve_pending_sources(project, "q3-report", "text") is None


def test_resolve_absent_brief_is_none(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir(parents=True, exist_ok=True)
    assert resolve_pending_sources(project, "q3-report", "text") is None
