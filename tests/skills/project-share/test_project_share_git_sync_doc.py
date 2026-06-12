"""Doc-coverage guard for the project-share packaging utility's adoption
of the per-phase git commit/sync hook (issue #426; rolled out to the
bridge/utility tools in issue #436).

project-share is not a ``<thread>.{N}`` lifecycle phase, so it uses the
non-thread commit shape (``anvil(project-share/share): <project>
[SHARED]``) canonicalized in ``anvil/lib/snippets/git_sync.md``
§Commit-message shape → "Non-thread commit shapes". The hook applies on
the apply (default) path only — ``--dry-run`` writes nothing.

Per the per-skill test filename convention (#58 — distinct filenames
across skills, ``__init__.py`` chains in every test dir), this file is
named ``test_project_share_git_sync_doc.py``.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
COMMAND = (
    REPO_ROOT / "anvil" / "skills" / "project-share" / "commands"
    / "project-share.md"
)
SKILL_MD = REPO_ROOT / "anvil" / "skills" / "project-share" / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_command_references_git_sync_snippet():
    assert "snippets/git_sync.md" in _read(COMMAND), (
        "project-share.md MUST reference anvil/lib/snippets/git_sync.md "
        "(issue #436)"
    )


def test_command_names_commit_per_phase_knob():
    assert "commit_per_phase" in _read(COMMAND), (
        "project-share.md MUST gate its git-sync step on "
        "git.commit_per_phase"
    )


def test_command_git_sync_step_is_default_off():
    assert "default off" in _read(COMMAND).lower(), (
        "project-share.md's git-sync step MUST state it is default off"
    )


def test_command_git_sync_uses_structured_message_shape():
    """The non-thread adaptation keeps the ``anvil(project-share/``
    prefix fixed while the version token becomes the project slug."""
    text = _read(COMMAND)
    assert "anvil(project-share/" in text
    assert "<project> [SHARED]" in text


def test_command_git_sync_is_dry_run_exempt():
    """--dry-run writes nothing — the hook must call out the silent
    no-op on that path."""
    text = _read(COMMAND)
    idx = text.find("## Git sync")
    assert idx >= 0, "project-share.md missing the Git sync section"
    assert "`--dry-run`" in text[idx:]


def test_skill_md_mentions_contract():
    text = _read(SKILL_MD)
    assert "git_sync.md" in text
    assert "commit_per_phase" in text
    assert ".anvil/config.json" in text
