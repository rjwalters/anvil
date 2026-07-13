"""Integration test: ``./scripts/version.sh set X.Y.Z`` must update ALL version-bearing files.

Issue #109: ``VERSION_FILES`` historically contained only ``CLAUDE.md``;
``pyproject.toml`` was added in the same fix. Issue #661 added ``README.md``.
This test guarantees that ``set X.Y.Z`` exercised end-to-end — copying the
real script + the real version files into a tmp dir layout that mirrors the
repo, then invoking ``bash scripts/version.sh set 9.9.9`` against it — touches
every managed file. Afterwards it re-runs ``check`` in the tmp dir and asserts
exit 0 to prove the multi-file ``check`` agrees.

Subprocess-based (no Python-side mocking of the shell logic); follows the
pattern from ``tests/scripts/test_install_quoting.py`` (#80) and
``tests/scripts/test_install_dry_run_honesty.py`` (#81). Distinct file
basename per the #58 cross-skill collision convention.

The test does NOT mutate the real repo files — all writes happen inside
``tmp_path``. ``version.sh``'s ``REPO_ROOT`` derives from its own
``$(dirname "$0")/..``, so copying it into ``tmp_path/scripts/`` makes
it operate on ``tmp_path/`` automatically.
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

NEW_VERSION = "9.9.9"


def _mirror_repo(tmp_path: Path) -> Path:
    """Copy ``scripts/version.sh`` + the version-bearing files into ``tmp_path``.

    Returns the tmp-dir REPO_ROOT (i.e. ``tmp_path`` itself).
    """
    (tmp_path / "scripts").mkdir()
    shutil.copy(VERSION_SH, tmp_path / "scripts" / "version.sh")
    shutil.copy(CLAUDE_MD, tmp_path / "CLAUDE.md")
    shutil.copy(PYPROJECT, tmp_path / "pyproject.toml")
    shutil.copy(README_MD, tmp_path / "README.md")
    # Make sure the copied script is executable (shutil.copy preserves bits,
    # but be explicit so the test is independent of the source-tree perms).
    (tmp_path / "scripts" / "version.sh").chmod(0o755)
    return tmp_path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


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


def test_version_set_updates_both_files(tmp_path: Path) -> None:
    """``./scripts/version.sh set 9.9.9`` writes the new version into every managed file."""
    root = _mirror_repo(tmp_path)
    script = root / "scripts" / "version.sh"

    # Sanity: before running set, all files agree on the current version.
    pre_claude = _claude_version(root / "CLAUDE.md")
    pre_pyproj = _pyproject_version(root / "pyproject.toml")
    pre_readme = _readme_version(root / "README.md")
    assert pre_claude == pre_pyproj == pre_readme, (
        f"test-setup precondition failed: copied files already disagree "
        f"({pre_claude} vs {pre_pyproj} vs {pre_readme})"
    )

    result = _run(["bash", str(script), "set", NEW_VERSION], cwd=root)
    assert result.returncode == 0, (
        f"`version.sh set {NEW_VERSION}` failed:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    post_claude = _claude_version(root / "CLAUDE.md")
    post_pyproj = _pyproject_version(root / "pyproject.toml")
    post_readme = _readme_version(root / "README.md")
    assert post_claude == NEW_VERSION, (
        f"CLAUDE.md not updated by `set`: got {post_claude!r}, expected {NEW_VERSION!r}"
    )
    assert post_pyproj == NEW_VERSION, (
        f"pyproject.toml not updated by `set`: got {post_pyproj!r}, expected {NEW_VERSION!r}"
    )
    assert post_readme == NEW_VERSION, (
        f"README.md not updated by `set`: got {post_readme!r}, expected {NEW_VERSION!r}"
    )


def test_version_check_passes_after_set(tmp_path: Path) -> None:
    """After ``set X.Y.Z``, ``./scripts/version.sh check`` must exit 0 with both files in sync."""
    root = _mirror_repo(tmp_path)
    script = root / "scripts" / "version.sh"

    set_result = _run(["bash", str(script), "set", NEW_VERSION], cwd=root)
    assert set_result.returncode == 0, (
        f"`set {NEW_VERSION}` failed before check could run:\n"
        f"--- stdout ---\n{set_result.stdout}\n--- stderr ---\n{set_result.stderr}"
    )

    check_result = _run(["bash", str(script), "check"], cwd=root)
    assert check_result.returncode == 0, (
        f"`check` failed after `set {NEW_VERSION}` updated both files:\n"
        f"--- stdout ---\n{check_result.stdout}\n--- stderr ---\n{check_result.stderr}"
    )
    # Belt-and-braces: the check output should mention BOTH files at the new
    # version. If pyproject.toml were silently missing from VERSION_FILES this
    # assertion would catch it even if exit code happened to be 0.
    assert "CLAUDE.md" in check_result.stdout
    assert "pyproject.toml" in check_result.stdout
    assert "README.md" in check_result.stdout
    assert NEW_VERSION in check_result.stdout


def test_version_check_detects_drift(tmp_path: Path) -> None:
    """Edit one file and confirm ``check`` exits non-zero, naming the drifting file."""
    root = _mirror_repo(tmp_path)
    script = root / "scripts" / "version.sh"
    pyproject = root / "pyproject.toml"

    # Mutate ONLY pyproject.toml, leaving CLAUDE.md alone. This is the exact
    # bug scenario from issue #109 (pre-fix `check` silently passed because
    # pyproject.toml was not in VERSION_FILES).
    #
    # Read the current version dynamically rather than hardcoding a sentinel
    # like 0.0.1 — that would silently start no-op'ing the moment the real
    # files bump (caught the release PR for 0.1.0; if we hardcoded the bug
    # would re-surface on every future bump).
    current = _pyproject_version(pyproject)
    drifted_version = "9.9.9"
    assert current != drifted_version, (
        "test invariant: drifted_version must differ from current"
    )
    drifted = pyproject.read_text().replace(
        f'version = "{current}"', f'version = "{drifted_version}"'
    )
    pyproject.write_text(drifted)

    check_result = _run(["bash", str(script), "check"], cwd=root)
    assert check_result.returncode != 0, (
        "version.sh check must exit non-zero on drift between CLAUDE.md and "
        "pyproject.toml. Got exit 0 with stdout:\n" + check_result.stdout
    )
    # The drift message should clearly identify pyproject.toml as the
    # mismatched file (operator-readable diagnostic).
    combined = check_result.stdout + check_result.stderr
    assert "pyproject.toml" in combined
    assert drifted_version in combined
