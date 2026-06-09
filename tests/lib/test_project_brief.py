"""Canonical-path tests for ``anvil.lib.project_brief`` (issue #382).

Promoted from ``anvil/skills/memo/lib/`` under factoring A of issue
#382. The full behavioral corpus lives at
``anvil/skills/memo/tests/test_project_brief.py`` and continues to run
against the canonical implementation through the memo back-compat shim.
This file pins the promotion contracts (canonical import path + shim
identity) plus representative parse behavior, including the paired
iteration-cap override that ``anvil:project-migrate`` now writes when
merging a deck thread's ``.anvil.json`` (issue #382).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from anvil.lib.project_brief import (
    DEFAULT_MAX_ITERATIONS,
    BriefDocument,
    ProjectBrief,
    load_project_brief,
)
from anvil.lib.project_discovery import BRIEF_FILENAME


def _write_brief(project: Path, frontmatter: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / BRIEF_FILENAME).write_text(
        f"---\n{textwrap.dedent(frontmatter)}---\n\n# BRIEF\n",
        encoding="utf-8",
    )


def test_shim_reexports_same_objects() -> None:
    from anvil.skills.memo.lib import project_brief as shim

    assert shim.load_project_brief is load_project_brief
    assert shim.ProjectBrief is ProjectBrief
    assert shim.BriefDocument is BriefDocument
    assert shim.DEFAULT_MAX_ITERATIONS == DEFAULT_MAX_ITERATIONS
    # Non-__all__ module attributes historically importable from the
    # memo path (consumed by sys.path-injected top-level imports).
    assert shim.BRIEF_FILENAME == BRIEF_FILENAME


def test_load_well_formed_brief(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert [d.slug for d in brief.documents] == ["acme"]


def test_absent_brief_returns_none(tmp_path: Path) -> None:
    project = tmp_path / "empty"
    project.mkdir()
    assert load_project_brief(project) is None


def test_paired_iteration_cap_override_parses(tmp_path: Path) -> None:
    """The shape project-migrate writes for a deck thread (issue #382)."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: series-a-deck
            artifact_type: investment-memo
            max_iterations: 6
            iteration_cap_rationale: |
              One extra pass to land the outcome detail.
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    doc = brief.documents[0]
    assert doc.max_iterations == 6
    assert "outcome detail" in (doc.iteration_cap_rationale or "")


def test_unpaired_max_iterations_rejected(tmp_path: Path) -> None:
    """STRICT contract: max_iterations without rationale raises — this is
    why the migrate planner drops unpaired overrides instead of carrying
    them into the BRIEF."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: acme
            artifact_type: investment-memo
            max_iterations: 6
        """,
    )
    with pytest.raises(ValueError):
        load_project_brief(project)


@pytest.mark.parametrize("value", ["deck", "slides", "proposal"])
def test_skill_identity_artifact_types_accepted(
    tmp_path: Path, value: str
) -> None:
    """Issue #386: the enum grew skill-identity values so migration can
    write honest types for deck/slides/proposal threads."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        f"""\
        project: proj
        documents:
          - slug: some-thread
            artifact_type: {value}
        """,
    )
    brief = load_project_brief(project)
    assert brief is not None
    assert brief.documents[0].artifact_type.value == value


def test_unknown_artifact_type_rejected(tmp_path: Path) -> None:
    """Closed-ended governance retained (#386): the studio's informal
    'pitch-deck' is NOT registered — the error lists the registered set
    so the fix is self-correcting."""
    project = tmp_path / "proj"
    _write_brief(
        project,
        """\
        project: proj
        documents:
          - slug: series-a-deck
            artifact_type: pitch-deck
        """,
    )
    with pytest.raises(ValueError, match="pitch-deck"):
        load_project_brief(project)
