"""Regression test: ``version.sh --tag`` stages CHANGELOG.md into the release commit.

Issue #638: the ``--tag`` blocks in ``scripts/version.sh`` (both the ``set``
and ``bump`` case-arms) staged only the two ``VERSION_FILES`` before
committing and tagging. The release convention promotes ``## [Unreleased]``
to ``## [X.Y.Z] — DATE`` in ``CHANGELOG.md`` as part of the same release
step, so the changelog edit sat dirty in the working tree and the tagged
release commit shipped without it (this bit the v0.7.1 release: ``c472032``
had to be amended to ``73c194d`` and the tag force-moved).

The fix adds a guarded ``git add CHANGELOG.md`` (``if [ -f ... ]`` form, safe
under ``set -euo pipefail``) to both ``--tag`` blocks. This file asserts:

- ``bump <level> --tag`` with a dirty tracked CHANGELOG.md includes it in the
  tagged commit (alongside the two version files);
- ``set X.Y.Z --tag`` does the same (second call site);
- a *clean* CHANGELOG.md is a harmless no-op (commit contains only the two
  version files);
- an *absent* CHANGELOG.md doesn't trip ``set -e`` (regression cover for the
  existing ``test_version_bump.py`` fixtures, which deliberately omit one).

Subprocess-based (no Python-side mocking of the shell logic); follows the
``_mirror_repo`` / ``_git_init`` pattern from ``tests/scripts/
test_version_bump.py`` (#590), extended with a synthetic CHANGELOG.md
fixture. Distinct file basename per the #58 cross-skill collision convention.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_SH = REPO_ROOT / "scripts" / "version.sh"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"
README_MD = REPO_ROOT / "README.md"

CHANGELOG_FIXTURE = """\
# Changelog

## [Unreleased]

### Fixed

- Something important.
"""


def _mirror_repo(tmp_path: Path, *, with_changelog: bool) -> Path:
    """Copy ``scripts/version.sh`` + the two version files into ``tmp_path``.

    Unlike the ``test_version_bump.py`` helper, this one can also write a
    synthetic ``CHANGELOG.md`` fixture — the file under test here.
    """
    (tmp_path / "scripts").mkdir()
    shutil.copy(VERSION_SH, tmp_path / "scripts" / "version.sh")
    shutil.copy(CLAUDE_MD, tmp_path / "CLAUDE.md")
    shutil.copy(PYPROJECT, tmp_path / "pyproject.toml")
    shutil.copy(README_MD, tmp_path / "README.md")
    (tmp_path / "scripts" / "version.sh").chmod(0o755)
    if with_changelog:
        (tmp_path / "CHANGELOG.md").write_text(CHANGELOG_FIXTURE)
    return tmp_path


def _git_init(root: Path) -> None:
    """Initialize a throwaway git repo in ``root`` with an initial commit."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@anvil.local"], cwd=root, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Anvil Test"], cwd=root, check=True
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial"], cwd=root, check=True
    )


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, cwd=cwd)


def _claude_version(claude_md: Path) -> str:
    match = re.search(
        r"\*\*Anvil Version\*\*:\s*(\d+\.\d+\.\d+)", claude_md.read_text()
    )
    assert match is not None, f"could not parse Anvil Version from {claude_md}"
    return match.group(1)


def _dirty_changelog(root: Path, new_version: str) -> None:
    """Simulate the release-notes promotion: ``[Unreleased]`` -> ``[X.Y.Z]``."""
    changelog = root / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text().replace(
            "## [Unreleased]", f"## [{new_version}] — 2026-07-07"
        )
    )


def _head_files(root: Path) -> set[str]:
    """File paths touched by the HEAD commit."""
    out = _run(
        ["git", "show", "--name-only", "--pretty=format:", "HEAD"], cwd=root
    ).stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def _next_patch(version: str) -> str:
    maj, minor, pat = version.split(".")
    return f"{maj}.{minor}.{int(pat) + 1}"


# ---------- dirty CHANGELOG.md rides the tagged commit ----------


def test_bump_tag_stages_dirty_changelog(tmp_path: Path) -> None:
    """``bump patch --tag`` includes a dirty tracked CHANGELOG.md in the commit."""
    root = _mirror_repo(tmp_path, with_changelog=True)
    _git_init(root)
    script = root / "scripts" / "version.sh"

    expected = _next_patch(_claude_version(root / "CLAUDE.md"))
    _dirty_changelog(root, expected)

    result = _run(["bash", str(script), "bump", "patch", "--tag"], cwd=root)
    assert result.returncode == 0, (
        f"`bump patch --tag` failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    files = _head_files(root)
    assert files == {"CHANGELOG.md", "CLAUDE.md", "pyproject.toml", "README.md"}, (
        f"tagged release commit should contain CHANGELOG.md + all version "
        f"files; got {sorted(files)!r}"
    )

    tags = _run(["git", "tag", "--list"], cwd=root).stdout.split()
    assert f"v{expected}" in tags, (
        f"expected tag v{expected} not found; tags: {tags!r}"
    )

    # Nothing left dangling in the working tree.
    status = _run(["git", "status", "--short"], cwd=root).stdout.strip()
    assert status == "", f"working tree should be clean after --tag: {status!r}"


def test_set_tag_stages_dirty_changelog(tmp_path: Path) -> None:
    """``set X.Y.Z --tag`` (the second call site) also stages CHANGELOG.md."""
    root = _mirror_repo(tmp_path, with_changelog=True)
    _git_init(root)
    script = root / "scripts" / "version.sh"

    _dirty_changelog(root, "9.9.9")

    result = _run(["bash", str(script), "set", "9.9.9", "--tag"], cwd=root)
    assert result.returncode == 0, (
        f"`set 9.9.9 --tag` failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    files = _head_files(root)
    assert files == {"CHANGELOG.md", "CLAUDE.md", "pyproject.toml", "README.md"}, (
        f"tagged release commit should contain CHANGELOG.md + all version "
        f"files; got {sorted(files)!r}"
    )

    tags = _run(["git", "tag", "--list"], cwd=root).stdout.split()
    assert "v9.9.9" in tags, f"expected tag v9.9.9 not found; tags: {tags!r}"


# ---------- clean CHANGELOG.md is a no-op ----------


def test_bump_tag_clean_changelog_is_noop(tmp_path: Path) -> None:
    """A clean tracked CHANGELOG.md doesn't error and doesn't ride the commit."""
    root = _mirror_repo(tmp_path, with_changelog=True)
    _git_init(root)
    script = root / "scripts" / "version.sh"

    result = _run(["bash", str(script), "bump", "patch", "--tag"], cwd=root)
    assert result.returncode == 0, (
        f"`bump patch --tag` with clean CHANGELOG.md failed:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    files = _head_files(root)
    assert files == {"CLAUDE.md", "pyproject.toml", "README.md"}, (
        f"release commit with a clean CHANGELOG.md should contain only the "
        f"version files; got {sorted(files)!r}"
    )


# ---------- absent CHANGELOG.md doesn't trip set -e ----------


def test_bump_tag_without_changelog_succeeds(tmp_path: Path) -> None:
    """No CHANGELOG.md at all: guard must not trip ``set -e``; commit + tag land.

    This mirrors the existing ``test_version_bump.py`` fixtures (which omit
    CHANGELOG.md) and pins the absent-file edge case explicitly.
    """
    root = _mirror_repo(tmp_path, with_changelog=False)
    _git_init(root)
    script = root / "scripts" / "version.sh"

    expected = _next_patch(_claude_version(root / "CLAUDE.md"))

    result = _run(["bash", str(script), "bump", "patch", "--tag"], cwd=root)
    assert result.returncode == 0, (
        f"`bump patch --tag` without CHANGELOG.md failed (set -e tripped by "
        f"the guard?):\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    files = _head_files(root)
    assert files == {"CLAUDE.md", "pyproject.toml", "README.md"}
    tags = _run(["git", "tag", "--list"], cwd=root).stdout.split()
    assert f"v{expected}" in tags, (
        f"expected tag v{expected} not found; tags: {tags!r}"
    )
