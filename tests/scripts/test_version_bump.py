"""Integration test: ``./scripts/version.sh list`` and ``bump <level> [--tag]``.

Issue #590: anvil's ``scripts/version.sh`` must implement the upstream Loom
v0.10.4 ``release.md`` interface contract for ``list`` (Phase 5 step 2) and
``bump <level> --tag`` (Phase 5 step 3). Until this lands, the upstream
canonical ``release.md`` cannot drive an end-to-end release flow against
anvil — Phase 5 step 2 errors with ``unknown command: list`` and Phase 5
step 3's ``./scripts/version.sh bump patch --tag`` errors the same way.

Subprocess-based (no Python-side mocking of the shell logic); follows the
pattern from ``tests/scripts/test_version_set.py`` (#109). Mirror the script
+ the two version files into ``tmp_path`` so the test never mutates the real
repo. The ``--tag`` paths additionally initialize a throwaway git repo in
the tmp dir so the commit/tag steps have somewhere to land.

Distinct file basename per the #58 cross-skill collision convention.
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


def _mirror_repo(tmp_path: Path) -> Path:
    """Copy ``scripts/version.sh`` + the version-bearing files into ``tmp_path``."""
    (tmp_path / "scripts").mkdir()
    shutil.copy(VERSION_SH, tmp_path / "scripts" / "version.sh")
    shutil.copy(CLAUDE_MD, tmp_path / "CLAUDE.md")
    shutil.copy(PYPROJECT, tmp_path / "pyproject.toml")
    shutil.copy(README_MD, tmp_path / "README.md")
    (tmp_path / "scripts" / "version.sh").chmod(0o755)
    return tmp_path


def _git_init(root: Path) -> None:
    """Initialize a throwaway git repo in ``root`` with an initial commit.

    Required for ``bump <level> --tag`` and ``set X.Y.Z --tag``: the script's
    ``--tag`` path runs ``git add``, ``git commit``, ``git tag`` and needs a
    real repo to operate on.
    """
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    # Configure local identity so the commit doesn't fail on bare gh runners
    # without a global git config.
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


def _pyproject_version(pyproject: Path) -> str:
    match = re.search(
        r'^version = "(\d+\.\d+\.\d+)"$', pyproject.read_text(), re.MULTILINE
    )
    assert match is not None, f"could not parse version from {pyproject}"
    return match.group(1)


def _readme_version(readme: Path) -> str:
    match = re.search(r"\*\*Status:\*\* v(\d+\.\d+\.\d+)", readme.read_text())
    assert match is not None, f"could not parse status-line version from {readme}"
    return match.group(1)


# ---------- list subcommand ----------


def test_list_prints_version_files(tmp_path: Path) -> None:
    """``./scripts/version.sh list`` must print each entry in VERSION_FILES."""
    root = _mirror_repo(tmp_path)
    script = root / "scripts" / "version.sh"

    result = _run(["bash", str(script), "list"], cwd=root)
    assert result.returncode == 0, (
        f"`version.sh list` failed:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert "CLAUDE.md" in lines, f"list output missing CLAUDE.md: {lines!r}"
    assert "pyproject.toml" in lines, (
        f"list output missing pyproject.toml: {lines!r}"
    )
    assert "README.md" in lines, f"list output missing README.md: {lines!r}"
    # Exactly three entries today (README.md was added in #661; any future
    # addition should update this assertion AND VERSION_FILES; we want the
    # test to catch silent drops).
    assert len(lines) == 3, (
        f"list output should have exactly 3 entries (CLAUDE.md, "
        f"pyproject.toml, README.md); got {lines!r}"
    )


# ---------- bump subcommand (no --tag) ----------


def test_bump_patch_increments_patch(tmp_path: Path) -> None:
    """``bump patch`` increments the last component in both files."""
    root = _mirror_repo(tmp_path)
    script = root / "scripts" / "version.sh"

    before = _claude_version(root / "CLAUDE.md")
    parts = before.split(".")
    expected = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

    result = _run(["bash", str(script), "bump", "patch"], cwd=root)
    assert result.returncode == 0, (
        f"`bump patch` failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
    assert _claude_version(root / "CLAUDE.md") == expected
    assert _pyproject_version(root / "pyproject.toml") == expected
    assert _readme_version(root / "README.md") == expected


def test_bump_minor_resets_patch(tmp_path: Path) -> None:
    """``bump minor`` increments the middle component and zeroes the last."""
    root = _mirror_repo(tmp_path)
    script = root / "scripts" / "version.sh"

    before = _claude_version(root / "CLAUDE.md")
    parts = before.split(".")
    expected = f"{parts[0]}.{int(parts[1]) + 1}.0"

    result = _run(["bash", str(script), "bump", "minor"], cwd=root)
    assert result.returncode == 0, result.stderr
    assert _claude_version(root / "CLAUDE.md") == expected
    assert _pyproject_version(root / "pyproject.toml") == expected
    assert _readme_version(root / "README.md") == expected


def test_bump_major_resets_minor_and_patch(tmp_path: Path) -> None:
    """``bump major`` increments the first component and zeroes the rest."""
    root = _mirror_repo(tmp_path)
    script = root / "scripts" / "version.sh"

    before = _claude_version(root / "CLAUDE.md")
    parts = before.split(".")
    expected = f"{int(parts[0]) + 1}.0.0"

    result = _run(["bash", str(script), "bump", "major"], cwd=root)
    assert result.returncode == 0, result.stderr
    assert _claude_version(root / "CLAUDE.md") == expected
    assert _pyproject_version(root / "pyproject.toml") == expected
    assert _readme_version(root / "README.md") == expected


def test_bump_invalid_level_errors(tmp_path: Path) -> None:
    """``bump foo`` must exit non-zero with a helpful error message."""
    root = _mirror_repo(tmp_path)
    script = root / "scripts" / "version.sh"

    result = _run(["bash", str(script), "bump", "foo"], cwd=root)
    assert result.returncode != 0, (
        f"`bump foo` should have failed but exited 0:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "foo" in combined, (
        "error message should name the offending level; got: " + combined
    )
    # The error should also enumerate the accepted levels so the operator
    # knows what to type instead.
    assert "patch" in combined
    assert "minor" in combined
    assert "major" in combined


def test_bump_missing_level_errors(tmp_path: Path) -> None:
    """``bump`` (no argument) must exit non-zero with the usage hint."""
    root = _mirror_repo(tmp_path)
    script = root / "scripts" / "version.sh"

    result = _run(["bash", str(script), "bump"], cwd=root)
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "bump" in combined
    assert "patch" in combined or "minor" in combined or "major" in combined


# ---------- bump subcommand (with --tag) ----------


def test_bump_without_tag_does_not_commit(tmp_path: Path) -> None:
    """``bump patch`` (no --tag) updates files but does NOT commit or tag."""
    root = _mirror_repo(tmp_path)
    _git_init(root)
    script = root / "scripts" / "version.sh"

    head_before = _run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    tags_before = _run(["git", "tag", "--list"], cwd=root).stdout.strip()

    result = _run(["bash", str(script), "bump", "patch"], cwd=root)
    assert result.returncode == 0, result.stderr

    head_after = _run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    tags_after = _run(["git", "tag", "--list"], cwd=root).stdout.strip()
    assert head_before == head_after, (
        "bump without --tag should NOT create a commit (HEAD moved)"
    )
    assert tags_before == tags_after, (
        "bump without --tag should NOT create a tag"
    )
    # But the files should be modified (so a follow-up `git status` shows them).
    status = _run(["git", "status", "--short"], cwd=root).stdout
    assert "CLAUDE.md" in status
    assert "pyproject.toml" in status
    assert "README.md" in status


def test_bump_with_tag_creates_commit_and_tag(tmp_path: Path) -> None:
    """``bump patch --tag`` updates files, commits, and tags ``v<X.Y.Z>``."""
    root = _mirror_repo(tmp_path)
    _git_init(root)
    script = root / "scripts" / "version.sh"

    before = _claude_version(root / "CLAUDE.md")
    parts = before.split(".")
    expected = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

    result = _run(["bash", str(script), "bump", "patch", "--tag"], cwd=root)
    assert result.returncode == 0, (
        f"`bump patch --tag` failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    # Files updated.
    assert _claude_version(root / "CLAUDE.md") == expected
    assert _pyproject_version(root / "pyproject.toml") == expected
    assert _readme_version(root / "README.md") == expected

    # Tag exists.
    tags = _run(["git", "tag", "--list"], cwd=root).stdout.split()
    assert f"v{expected}" in tags, (
        f"expected tag v{expected} not found; tags: {tags!r}"
    )

    # Commit message uses the release voice (distinct from `set`'s
    # "bump version to" wording — `bump --tag` is the release path).
    head_msg = _run(
        ["git", "log", "-1", "--pretty=%s"], cwd=root
    ).stdout.strip()
    assert head_msg == f"chore: release v{expected}", (
        f"commit message should be 'chore: release v{expected}', "
        f"got: {head_msg!r}"
    )
