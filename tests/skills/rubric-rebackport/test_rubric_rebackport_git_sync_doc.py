"""Doc-coverage guard for the rubric-rebackport bridge tool's adoption
of the per-phase git commit/sync hook (issue #426; rolled out to the
bridge/utility tools in issue #436).

rubric-rebackport is not a ``<thread>.{N}`` lifecycle phase, so it uses
the per-review non-thread commit shapes
(``anvil(rubric-rebackport/stamp): <thread>.{N}.review [STAMPED]`` /
``anvil(rubric-rebackport/rescore): <thread>.{N}.review [RESCORED]``)
canonicalized in ``anvil/lib/snippets/git_sync.md`` §Commit-message
shape → "Non-thread commit shapes". The hook applies on the ``--apply``
path only — dry-run mode writes nothing.

Per the per-skill test filename convention (#58 — distinct filenames
across skills, ``__init__.py`` chains in every test dir), this file is
named ``test_rubric_rebackport_git_sync_doc.py``.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
COMMAND = (
    REPO_ROOT / "anvil" / "skills" / "rubric-rebackport" / "commands"
    / "rubric-rebackport.md"
)
SKILL_MD = REPO_ROOT / "anvil" / "skills" / "rubric-rebackport" / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_command_references_git_sync_snippet():
    assert "snippets/git_sync.md" in _read(COMMAND), (
        "rubric-rebackport.md MUST reference anvil/lib/snippets/git_sync.md "
        "(issue #436)"
    )


def test_command_names_commit_per_phase_knob():
    assert "commit_per_phase" in _read(COMMAND), (
        "rubric-rebackport.md MUST gate its git-sync step on "
        "git.commit_per_phase"
    )


def test_command_git_sync_step_is_default_off():
    assert "default off" in _read(COMMAND).lower(), (
        "rubric-rebackport.md's git-sync step MUST state it is default off"
    )


def test_command_git_sync_uses_structured_message_shape():
    """The per-review adaptation keeps the ``anvil(rubric-rebackport/``
    prefix fixed while the version token becomes the review path; both
    stamp and rescore shapes must be documented."""
    text = _read(COMMAND)
    assert "anvil(rubric-rebackport/" in text
    assert "[STAMPED]" in text
    assert "[RESCORED]" in text


def test_command_git_sync_is_apply_path_only():
    """Dry-run mode writes nothing — the hook must scope itself to the
    --apply path."""
    text = _read(COMMAND)
    idx = text.find("## Git sync")
    assert idx >= 0, "rubric-rebackport.md missing the Git sync section"
    assert "`--apply`" in text[idx:]


def test_skill_md_mentions_contract():
    text = _read(SKILL_MD)
    assert "git_sync.md" in text
    assert "commit_per_phase" in text
    assert ".anvil/config.json" in text
