"""Exemption guard: project-scout MUST NOT adopt the per-phase git
commit/sync hook (issues #426 / #436).

project-scout is strictly read-only by design — it walks a tree,
classifies anvil-adoptable document clusters, and reports; it never
writes to the working tree. Per ``anvil/lib/snippets/git_sync.md``
§"Which commands adopt", read-only commands are exempt by definition:
there is nothing to commit. This guard pins the exemption so a later
edit can't accidentally wire the hook into a command that has no writes
to stage.

Per the per-skill test filename convention (#58 — distinct filenames
across skills, ``__init__.py`` chains in every test dir), this file is
named ``test_project_scout_git_sync_exempt.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCOUT = REPO_ROOT / "anvil" / "skills" / "project-scout"


@pytest.mark.parametrize(
    "path",
    [
        SCOUT / "commands" / "project-scout.md",
        SCOUT / "SKILL.md",
    ],
    ids=["command", "skill_md"],
)
def test_project_scout_is_exempt_from_git_sync(path: Path):
    """The strictly read-only scout MUST NOT reference the git-sync hook
    knob or snippet — read-only commands are exempt by definition."""
    text = path.read_text(encoding="utf-8")
    assert "commit_per_phase" not in text, (
        f"{path.name} is read-only and MUST NOT adopt the git-sync hook"
    )
    assert "snippets/git_sync.md" not in text, (
        f"{path.name} is read-only and MUST NOT reference the git-sync "
        f"snippet"
    )
