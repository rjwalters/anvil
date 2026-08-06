"""Drift-guard test: ``VERSION``, ``CLAUDE.md``, ``pyproject.toml``, and ``README.md`` must agree on Anvil's version.

Issue #109: anvil has version-bearing files — ``CLAUDE.md``'s
``**Anvil Version**: X.Y.Z`` line, and ``pyproject.toml``'s top-level
``[project]`` ``version = "X.Y.Z"`` line. ``scripts/version.sh set X.Y.Z``
is the only supported way to bump them at once; this test backstops it in CI
so a one-file-only manual edit (or a broken ``version.sh``) cannot land
unnoticed.

Issue #661 added ``README.md``'s ``**Status:** vX.Y.Z`` status line to
``version.sh``'s managed set (its ``VERSION_FILES`` array and the matching
``get_version_from_file`` / ``set_version`` case-arms), so this test parses
that line too and asserts it agrees with ``CLAUDE.md``.

Issue #894 added a root ``VERSION`` file — the single source of truth
``scripts/install-anvil.sh`` now reads at install time (previously it
independently re-parsed ``CLAUDE.md`` prose with its own grep, which broke
outright on any rewording of that line). ``VERSION`` was also added to
``scripts/version.sh``'s ``VERSION_FILES`` set, so this test parses it too.

This test parses all files INDEPENDENTLY (pure Python regex, no shell-out
to ``scripts/version.sh``) — otherwise the test would be tautological, since
``version.sh`` is precisely the thing that could be broken. Mirrors the
precedent set by ``tests/lib/test_figures.py::test_palette_constants_match_css_root``
(#74): "no generator, just a test" sync contract.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = REPO_ROOT / "VERSION"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"
README_MD = REPO_ROOT / "README.md"


def _version_file_version() -> str:
    """Parse the plain ``X.Y.Z`` version string from the root ``VERSION`` file."""
    text = VERSION_FILE.read_text().strip()
    match = re.fullmatch(r"\d+\.\d+\.\d+", text)
    assert match is not None, (
        f"expected a bare 'X.Y.Z' version string in {VERSION_FILE}, got {text!r}"
    )
    return match.group(0)


def _claude_version() -> str:
    """Parse the ``**Anvil Version**: X.Y.Z`` line from ``CLAUDE.md``."""
    text = CLAUDE_MD.read_text()
    match = re.search(r"\*\*Anvil Version\*\*:\s*(\d+\.\d+\.\d+)", text)
    assert match is not None, (
        f"could not parse '**Anvil Version**: X.Y.Z' from {CLAUDE_MD}"
    )
    return match.group(1)


def _pyproject_version() -> str:
    """Parse the top-level ``[project]`` ``version = "X.Y.Z"`` line from ``pyproject.toml``.

    The regex is anchored on ``^...$`` (``re.MULTILINE``) so it only matches the
    top-level project version line, not any future nested-table
    ``version = "..."`` string that might appear later in the file
    (e.g. inside a ``[tool.foo]`` block).
    """
    text = PYPROJECT.read_text()
    match = re.search(
        r'^version = "(\d+\.\d+\.\d+)"$', text, re.MULTILINE
    )
    assert match is not None, (
        f"could not parse top-level 'version = \"X.Y.Z\"' from {PYPROJECT}"
    )
    return match.group(1)


def _readme_version() -> str:
    """Parse the ``**Status:** vX.Y.Z`` status line from ``README.md``.

    Anchored on the ``**Status:** v`` prefix so it only matches the opening
    status line, never an unrelated ``vX.Y.Z``-shaped substring elsewhere in
    the file (e.g. a version mentioned inside a skill description). Mirrors the
    tight-anchoring precedent of ``version.sh``'s README case-arm (#661).
    """
    text = README_MD.read_text()
    match = re.search(r"\*\*Status:\*\* v(\d+\.\d+\.\d+)", text)
    assert match is not None, (
        f"could not parse '**Status:** vX.Y.Z' status line from {README_MD}"
    )
    return match.group(1)


def test_anvil_version_files_in_sync() -> None:
    """``VERSION``, ``CLAUDE.md``, ``pyproject.toml``, and ``README.md`` must hold the same version string.

    Failure message names ALL file paths AND ALL parsed values, so the
    operator immediately sees which file drifted from which.
    """
    version_file = _version_file_version()
    claude = _claude_version()
    pyproj = _pyproject_version()
    readme = _readme_version()
    assert version_file == claude == pyproj == readme, (
        f"version drift between Anvil's version-bearing files:\n"
        f"  {VERSION_FILE} -> '{version_file}'\n"
        f"  {CLAUDE_MD} -> '{claude}'\n"
        f"  {PYPROJECT} -> '{pyproj}'\n"
        f"  {README_MD} -> '{readme}'\n"
        f"All files MUST agree. Run `./scripts/version.sh check` locally and use "
        f"`./scripts/version.sh set <X.Y.Z>` to update them atomically — never "
        f"edit any of them by hand."
    )
