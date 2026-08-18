"""Tests for ``scripts/check-surface-version-bump.sh`` (issue #1152).

``VERSION`` is the only mechanical signal a consumer has that its installed
``.anvil/`` copies are stale: ``scripts/install-anvil.sh`` reads it at install
time and records it in ``.anvil/install-metadata.json``, and every downstream
"am I current?" check diffs against that. Before this gate, ``VERSION`` moved
only when someone ran a bump by hand — it read ``0.11.0`` while ``main`` was 61
commits past the ``v0.11.0`` tag, so every consumer reported "current" for
changes it did not have.

The gate mirrors ``.loom/scripts/check-defaults-version-bump.sh`` (loom#5874)
but watches Anvil's real installed surface instead of loom's ``defaults/``:

- 0 = no surface change in the diff, OR VERSION was also changed, OR the
  ``<!-- loom:no-surface-change -->`` marker is present
- 1 = surface changed, VERSION did not, no marker
- 2 = bad usage / unresolvable refs

Each test builds a throwaway git repo so nothing here depends on this
repository's own history. Distinct file basename per the #58 cross-skill
collision convention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check-surface-version-bump.sh"

MARKER = "<!-- loom:no-surface-change -->"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _write(repo: Path, relpath: str, content: str) -> None:
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A minimal anvil-shaped git repo with a base commit on ``main``."""
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    _write(repo, "VERSION", "0.11.0\n")
    _write(repo, "anvil/skills/memo/SKILL.md", "# memo\n")
    _write(repo, "anvil/lib/critics.py", "# critics\n")
    _write(repo, "scripts/install-anvil.sh", "#!/usr/bin/env bash\n")
    _write(repo, "scripts/resync-installed.sh", "#!/usr/bin/env bash\n")
    _write(repo, "docs/README.md", "# docs\n")
    _write(repo, "tests/lib/test_critics.py", "# test\n")
    _write(repo, "WORK_LOG.md", "# work log\n")
    _commit(repo, "base commit")
    return repo


def _run(repo: Path, base: str = "main", head: str = "HEAD", pr_body: str | None = None):
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(repo)}
    if pr_body is not None:
        env["PR_BODY"] = pr_body
    return subprocess.run(
        ["bash", str(SCRIPT), "--base", base, "--head", head],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert SCRIPT.stat().st_mode & 0o111, "check-surface-version-bump.sh must be executable"


# --- (a) no surface change ----------------------------------------------------


def test_non_surface_change_passes(repo: Path) -> None:
    """A PR touching only docs/tests/work-log is outside the watched surface."""
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, "docs/README.md", "# docs, revised\n")
    _write(repo, "tests/lib/test_critics.py", "# test, revised\n")
    _write(repo, "WORK_LOG.md", "# work log, revised\n")
    _commit(repo, "docs: revise notes")

    result = _run(repo)
    assert result.returncode == 0, result.stderr
    assert "no installed-surface changes" in result.stdout


def test_changelog_only_change_passes(repo: Path) -> None:
    """CHANGELOG.md is not installed into a consumer — not part of the surface."""
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, "CHANGELOG.md", "# Changelog\n")
    _commit(repo, "docs: add changelog")

    result = _run(repo)
    assert result.returncode == 0, result.stderr


# --- (b) surface change + VERSION bump ---------------------------------------


@pytest.mark.parametrize(
    "relpath",
    [
        "anvil/skills/memo/SKILL.md",
        "anvil/lib/critics.py",
        "scripts/install-anvil.sh",
        "scripts/resync-installed.sh",
    ],
)
def test_surface_change_with_version_bump_passes(repo: Path, relpath: str) -> None:
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, relpath, "# changed\n")
    _write(repo, "VERSION", "0.11.1\n")
    _commit(repo, "feat: change the surface and bump")

    result = _run(repo)
    assert result.returncode == 0, result.stderr
    assert "VERSION was bumped" in result.stdout


# --- (c) marker exemption -----------------------------------------------------


def test_marker_in_pr_body_exempts(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, "anvil/skills/memo/SKILL.md", "# memo (typo fix)\n")
    _commit(repo, "docs: fix a typo in the memo skill")

    result = _run(repo, pr_body=f"## Summary\n\nTypo only.\n\n{MARKER}\n")
    assert result.returncode == 0, result.stderr
    assert "marker found in the PR body" in result.stdout


def test_marker_in_commit_message_exempts(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, "anvil/skills/memo/SKILL.md", "# memo (typo fix)\n")
    _commit(repo, f"docs: fix a typo in the memo skill\n\n{MARKER}\n")

    result = _run(repo)
    assert result.returncode == 0, result.stderr
    assert "marker found in a commit message" in result.stdout


def test_unrelated_pr_body_does_not_exempt(repo: Path) -> None:
    """A body without the exact marker string is not an exemption."""
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, "anvil/lib/critics.py", "# critics, revised\n")
    _commit(repo, "feat: revise critics")

    result = _run(repo, pr_body="## Summary\n\nNo surface change, honest.\n")
    assert result.returncode == 1


# --- (d) surface change alone -------------------------------------------------


@pytest.mark.parametrize(
    "relpath",
    [
        "anvil/skills/memo/SKILL.md",
        "anvil/lib/critics.py",
        "anvil/roles/reviewer.md",
        "anvil/agents/anvil-memo-draft.md",
        "anvil/templates/themes/starter/theme.css",
        "scripts/install-anvil.sh",
        "scripts/resync-installed.sh",
    ],
)
def test_surface_change_without_bump_fails(repo: Path, relpath: str) -> None:
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, relpath, "# changed\n")
    _commit(repo, "feat: change the installed surface")

    result = _run(repo)
    assert result.returncode == 1
    assert "without a VERSION bump" in result.stderr
    assert relpath in result.stderr
    assert "./scripts/version.sh bump patch" in result.stderr
    assert MARKER in result.stderr


def test_deleted_surface_file_without_bump_fails(repo: Path) -> None:
    """Removing an installed file is a consumer-visible change too."""
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "anvil/skills/memo/SKILL.md").unlink()
    _commit(repo, "feat: drop the memo skill body")

    result = _run(repo)
    assert result.returncode == 1


# --- usage / contract ---------------------------------------------------------


def test_missing_base_is_usage_error(repo: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "--base <ref> is required" in result.stderr


def test_unresolvable_base_is_usage_error(repo: Path) -> None:
    result = _run(repo, base="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
    assert result.returncode == 2
    assert "not found" in result.stderr


def test_list_paths_matches_documented_surface() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--list-paths"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [
        "anvil/",
        "scripts/install-anvil.sh",
        "scripts/resync-installed.sh",
    ]


def test_watched_paths_exist_in_this_repo() -> None:
    """The watched surface must name real paths, or the gate is a silent no-op.

    This is the failure mode that made the vendored
    ``.loom/scripts/check-defaults-version-bump.sh`` useless here: it watches
    ``defaults/``, which this repo does not have, so it always exits 0.
    """
    result = subprocess.run(
        ["bash", str(SCRIPT), "--list-paths"],
        capture_output=True,
        text=True,
        check=True,
    )
    for raw in result.stdout.split():
        assert (REPO_ROOT / raw).exists(), f"watched path does not exist: {raw}"


def test_workflow_wires_the_script() -> None:
    workflow = REPO_ROOT / ".github" / "workflows" / "version-bump-gate.yml"
    assert workflow.is_file(), f"missing {workflow}"
    text = workflow.read_text(encoding="utf-8")
    assert "./scripts/check-surface-version-bump.sh" in text
    assert "fetch-depth: 0" in text, "a shallow checkout makes the base sha unresolvable"
    assert "PR_BODY:" in text, "the PR-body marker path needs PR_BODY plumbed in"
    assert "pull_request:" in text


def test_marker_convention_is_documented_in_claude_md() -> None:
    text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert MARKER in text, "the no-surface-change marker must be documented in CLAUDE.md"
    assert "check-surface-version-bump.sh" in text
