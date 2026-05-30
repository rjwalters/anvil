"""Drift-guard test: ``CLAUDE.md`` and ``pyproject.toml`` must agree on Anvil's version.

Issue #109: anvil has two version-bearing files — ``CLAUDE.md``'s
``**Anvil Version**: X.Y.Z`` line, and ``pyproject.toml``'s top-level
``[project]`` ``version = "X.Y.Z"`` line. ``scripts/version.sh set X.Y.Z``
is the only supported way to bump both at once; this test backstops it in CI
so a one-file-only manual edit (or a broken ``version.sh``) cannot land
unnoticed.

This test parses both files INDEPENDENTLY (pure Python regex, no shell-out
to ``scripts/version.sh``) — otherwise the test would be tautological, since
``version.sh`` is precisely the thing that could be broken. Mirrors the
precedent set by ``tests/lib/test_figures.py::test_palette_constants_match_css_root``
(#74): "no generator, just a test" sync contract.

Note: ``scripts/install-anvil.sh`` independently re-parses the version
from ``CLAUDE.md`` with its own grep (it does not source ``version.sh``).
That is acceptable today specifically because this drift test guarantees
the two files agree — the installer's CLAUDE.md value is always the right
one. If that contract ever changes, this docstring should be revisited.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"


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


def test_anvil_version_files_in_sync() -> None:
    """``CLAUDE.md`` and ``pyproject.toml`` must hold the same version string.

    Failure message names BOTH file paths AND BOTH parsed values, so the
    operator immediately sees which file drifted from which.
    """
    claude = _claude_version()
    pyproj = _pyproject_version()
    assert claude == pyproj, (
        f"version drift between Anvil's two version-bearing files:\n"
        f"  {CLAUDE_MD} -> '{claude}'\n"
        f"  {PYPROJECT} -> '{pyproj}'\n"
        f"Both files MUST agree. Run `./scripts/version.sh check` locally and use "
        f"`./scripts/version.sh set <X.Y.Z>` to update both atomically — never "
        f"edit either file by hand."
    )
