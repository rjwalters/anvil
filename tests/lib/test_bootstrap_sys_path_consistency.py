"""Tests for ``anvil.lib.skill_lib_loader.bootstrap_sys_path`` (issue #1100).

Consolidates the 4 previously byte-identical, independently-hand-written
``_bootstrap_sys_path()`` copies that lived in each bare-script CLI entry
point (``diff/lib/cli.py``, ``memo/lib/render_phase.py``,
``memo/lib/latest_phase.py``, ``project-share/lib/cli.py``) around one
canonical, unit-tested implementation.

The 4 call sites still each keep their own local copy of the algorithm —
that duplication is structurally unavoidable: a function whose whole job
is making ``import anvil`` resolvable in a bare script cannot itself
begin with ``from anvil.lib.skill_lib_loader import bootstrap_sys_path``,
because nothing would be on ``sys.path`` yet to resolve that import. What
this suite provides instead is exactly what the issue named as the real
gap — a way to keep the copies in sync "by the type checker/import graph"
rather than "by hand cross-referencing docstrings": :class:`TestCopiesMatchCanonical`
below parses each local copy's AST and asserts its body is
identical (modulo the docstring) to the canonical implementation, so any
future edit to one copy that isn't mirrored everywhere fails CI instead
of silently drifting.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from anvil.lib.skill_lib_loader import bootstrap_sys_path

REPO_ROOT = Path(__file__).resolve().parents[2]

# (skill CLI path, local function name) — every known bare-script bootstrap
# copy as of issue #1100.
_LOCAL_COPIES = [
    REPO_ROOT / "anvil" / "skills" / "diff" / "lib" / "cli.py",
    REPO_ROOT / "anvil" / "skills" / "memo" / "lib" / "render_phase.py",
    REPO_ROOT / "anvil" / "skills" / "memo" / "lib" / "latest_phase.py",
    REPO_ROOT / "anvil" / "skills" / "project-share" / "lib" / "cli.py",
]

_CANONICAL_PATH = REPO_ROOT / "anvil" / "lib" / "skill_lib_loader.py"


def _function_body_source(path: Path, function_name: str) -> str:
    """Return the unparsed source of `function_name`'s body, docstring stripped.

    Comparing unparsed ``ast`` output (rather than raw text) makes the
    comparison immune to incidental whitespace/formatting differences and
    to each copy's own (deliberately different) docstring.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            body = list(node.body)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]  # drop the docstring
            return "\n".join(ast.unparse(stmt) for stmt in body)
    raise AssertionError(f"{function_name} not found in {path}")


class TestCopiesMatchCanonical:
    """Every local ``_bootstrap_sys_path()`` must match the canonical body."""

    def test_canonical_implementation_is_present(self) -> None:
        canonical = _function_body_source(_CANONICAL_PATH, "bootstrap_sys_path")
        assert "here.parents" in canonical
        assert "anvil" in canonical

    @pytest.mark.parametrize(
        "path", _LOCAL_COPIES, ids=lambda p: str(p.relative_to(REPO_ROOT))
    )
    def test_local_copy_matches_canonical(self, path: Path) -> None:
        canonical = _function_body_source(_CANONICAL_PATH, "bootstrap_sys_path")
        # The canonical signature takes an explicit `anchor` argument (so it
        # is unit-testable in isolation, below); every local copy instead
        # reads its own `__file__` directly. Normalize that one, expected
        # difference before comparing the rest of the algorithm verbatim.
        canonical_normalized = canonical.replace("anchor", "__file__")
        local = _function_body_source(path, "_bootstrap_sys_path")
        assert local == canonical_normalized, (
            f"{path.relative_to(REPO_ROOT)}'s _bootstrap_sys_path() has "
            "drifted from anvil.lib.skill_lib_loader.bootstrap_sys_path — "
            "keep every bare-script copy byte-identical to the canonical "
            "algorithm (issue #1100)."
        )


class TestBootstrapSysPath:
    """Direct behavioral coverage for the canonical implementation."""

    def _make_layout(self, tmp_path: Path, *, script_depth: int) -> Path:
        """Build a fake ``anvil/__init__.py`` root plus a nested script path.

        Returns the path of a (non-existent, but that's fine — only its
        directory structure matters) script file `script_depth` directories
        below `tmp_path`, with `tmp_path/anvil/__init__.py` marking the
        root that should be discovered and inserted.
        """

        root = tmp_path / "root"
        (root / "anvil").mkdir(parents=True)
        (root / "anvil" / "__init__.py").write_text("")

        script_dir = root
        for i in range(script_depth):
            script_dir = script_dir / f"level{i}"
        script_dir.mkdir(parents=True)
        return script_dir / "cli.py"

    def test_inserts_ancestor_containing_anvil_package(self, tmp_path: Path) -> None:
        script = self._make_layout(tmp_path, script_depth=4)
        root = script.parents[4]
        assert str(root) not in sys.path

        try:
            bootstrap_sys_path(script)
            assert str(root) == sys.path[0]
        finally:
            if str(root) in sys.path:
                sys.path.remove(str(root))

    def test_shallow_layout_also_resolves(self, tmp_path: Path) -> None:
        """A script directly under the root that contains ``anvil/`` also resolves."""
        script = self._make_layout(tmp_path, script_depth=1)
        root = script.parents[1]
        assert str(root) not in sys.path

        try:
            bootstrap_sys_path(script)
            assert str(root) == sys.path[0]
        finally:
            if str(root) in sys.path:
                sys.path.remove(str(root))

    def test_idempotent_does_not_duplicate_sys_path_entry(self, tmp_path: Path) -> None:
        script = self._make_layout(tmp_path, script_depth=2)
        root = script.parents[2]

        try:
            bootstrap_sys_path(script)
            bootstrap_sys_path(script)
            assert sys.path.count(str(root)) == 1
        finally:
            if str(root) in sys.path:
                sys.path.remove(str(root))

    def test_no_anvil_marker_leaves_sys_path_unchanged(self, tmp_path: Path) -> None:
        script_dir = tmp_path / "no_anvil_here" / "lib"
        script_dir.mkdir(parents=True)
        script = script_dir / "cli.py"

        before = list(sys.path)
        bootstrap_sys_path(script)
        assert sys.path == before
