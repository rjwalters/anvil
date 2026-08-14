"""Regression test: ``version.sh --tag`` must create an ANNOTATED tag.

Issue #1034: both ``--tag`` blocks in ``scripts/version.sh`` (the ``set`` and
``bump`` case-arms) created the release tag with plain ``git tag "v$new"``,
which produces a **lightweight** tag. ``git push --follow-tags`` only pushes
**annotated** tags, so a release push silently left the new tag behind — this
bit the v0.11.0 release, where ``gh release create`` then failed with
``tag v0.11.0 exists locally but has not been pushed`` and the tag needed an
explicit ``git push origin v0.11.0``.

The fix switches both call sites to ``git tag -a "v$new" -m "v$new"``. This
file asserts the created tag's object type is ``tag`` (annotated), not
``commit`` (lightweight), for both the ``bump --tag`` and ``set --tag`` call
sites.

Subprocess-based (no Python-side mocking of the shell logic); follows the
``_mirror_repo`` / ``_git_init`` pattern from ``tests/scripts/
test_version_bump.py`` (#590). Distinct file basename per the #58 cross-skill
collision convention.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_SH = REPO_ROOT / "scripts" / "version.sh"
VERSION_FILE = REPO_ROOT / "VERSION"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"
README_MD = REPO_ROOT / "README.md"


def _mirror_repo(tmp_path: Path) -> Path:
    """Copy ``scripts/version.sh`` + the version-bearing files into ``tmp_path``."""
    (tmp_path / "scripts").mkdir()
    shutil.copy(VERSION_SH, tmp_path / "scripts" / "version.sh")
    shutil.copy(VERSION_FILE, tmp_path / "VERSION")
    shutil.copy(CLAUDE_MD, tmp_path / "CLAUDE.md")
    shutil.copy(PYPROJECT, tmp_path / "pyproject.toml")
    shutil.copy(README_MD, tmp_path / "README.md")
    (tmp_path / "scripts" / "version.sh").chmod(0o755)
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


def _tag_object_type(root: Path, tag: str) -> str:
    """Return the git object type the tag ref points at directly.

    Annotated tags point at a ``tag`` object; lightweight tags point directly
    at the ``commit`` object.
    """
    result = _run(["git", "cat-file", "-t", tag], cwd=root)
    assert result.returncode == 0, (
        f"`git cat-file -t {tag}` failed:\n{result.stderr}"
    )
    return result.stdout.strip()


def test_bump_tag_creates_annotated_tag(tmp_path: Path) -> None:
    """``bump patch --tag`` must create an annotated tag, not a lightweight one."""
    root = _mirror_repo(tmp_path)
    _git_init(root)
    script = root / "scripts" / "version.sh"

    result = _run(["bash", str(script), "bump", "patch", "--tag"], cwd=root)
    assert result.returncode == 0, (
        f"`bump patch --tag` failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    tags = _run(["git", "tag", "--list"], cwd=root).stdout.split()
    assert len(tags) == 1, f"expected exactly one tag; got {tags!r}"
    tag = tags[0]

    assert _tag_object_type(root, tag) == "tag", (
        f"{tag!r} must be an annotated tag (object type 'tag') so that "
        f"`git push --follow-tags` carries it; got a lightweight tag instead "
        f"(object type 'commit')"
    )


def test_set_tag_creates_annotated_tag(tmp_path: Path) -> None:
    """``set X.Y.Z --tag`` (the second call site) also creates an annotated tag."""
    root = _mirror_repo(tmp_path)
    _git_init(root)
    script = root / "scripts" / "version.sh"

    result = _run(["bash", str(script), "set", "9.9.9", "--tag"], cwd=root)
    assert result.returncode == 0, (
        f"`set 9.9.9 --tag` failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    assert _tag_object_type(root, "v9.9.9") == "tag", (
        "v9.9.9 must be an annotated tag (object type 'tag') so that "
        "`git push --follow-tags` carries it; got a lightweight tag instead "
        "(object type 'commit')"
    )
