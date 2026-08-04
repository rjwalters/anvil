"""Tests for ``anvil.lib.skill_lib_loader`` (issue #879).

Covers the acceptance criteria for the shared loader helper that
replaces every hand-written ``_<skill>_skill_lib.py`` importlib
incantation:

1. Hyphenated skill names derive a valid, unique Python package name.
2. A loaded submodule's own relative imports (``from .leaf import ...``)
   resolve correctly, in either declaration order, without the caller
   supplying a dependency-safe load order.
3. Two different skills' lib packages never collide even when they ship
   same-named submodules (the #358 / #367 precedent this module must
   preserve).
4. Loading is idempotent (repeat calls return the cached module) and a
   missing ``__init__.py`` raises a clear error rather than a confusing
   import failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from anvil.lib.skill_lib_loader import (
    default_package_name,
    import_skill_lib_module,
    load_skill_lib,
    load_skill_lib_package,
)


@pytest.fixture(autouse=True)
def _isolate_sys_modules():
    """Remove any package this test file registers in ``sys.modules``.

    The loader is deliberately cache-y (idempotent via ``sys.modules``),
    which is exactly what production callers want but would let one test
    in this file poison another (or a later, unrelated test module) if
    two tests happened to reuse a package name. Snapshot-and-restore
    keeps each test's registrations from leaking.
    """

    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        del sys.modules[name]


def _write_fixture_lib(root: Path, *, leaf_value: int = 1) -> Path:
    """Build a minimal two-module package with a relative import.

    ``leaf.py`` defines ``VALUE``; ``mid.py`` imports it via
    ``from .leaf import VALUE`` and derives ``DOUBLED``. This is the
    shape (``orchestrate.py`` importing ``from .cluster import ...``)
    the real skill libs use.
    """

    lib_dir = root / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "__init__.py").write_text('"""Fixture skill lib."""\n')
    (lib_dir / "leaf.py").write_text(f"VALUE = {leaf_value}\n")
    (lib_dir / "mid.py").write_text(
        "from .leaf import VALUE\n\nDOUBLED = VALUE * 2\n"
    )
    return lib_dir


class TestDefaultPackageName:
    def test_single_hyphen(self) -> None:
        assert default_package_name("project-scout") == "project_scout_lib"

    def test_multiple_hyphens(self) -> None:
        assert (
            default_package_name("ip-uspto-provisional")
            == "ip_uspto_provisional_lib"
        )

    def test_no_hyphen(self) -> None:
        assert default_package_name("help") == "help_lib"


class TestLoadSkillLibPackage:
    def test_registers_package_with_correct_path(self, tmp_path: Path) -> None:
        lib_dir = _write_fixture_lib(tmp_path)

        package = load_skill_lib_package("fixture-skill-a", lib_dir)

        assert package.__name__ == "fixture_skill_a_lib"
        assert sys.modules["fixture_skill_a_lib"] is package
        assert list(package.__path__) == [str(lib_dir.resolve())]

    def test_idempotent_returns_cached_module(self, tmp_path: Path) -> None:
        lib_dir = _write_fixture_lib(tmp_path)

        first = load_skill_lib_package("fixture-skill-b", lib_dir)
        second = load_skill_lib_package("fixture-skill-b", lib_dir)

        assert first is second

    def test_missing_init_raises_file_not_found(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "lib"
        empty_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="__init__.py"):
            load_skill_lib_package("fixture-skill-c", empty_dir)

    def test_explicit_package_name_override(self, tmp_path: Path) -> None:
        lib_dir = _write_fixture_lib(tmp_path)

        package = load_skill_lib_package(
            "fixture-skill-d", lib_dir, package_name="custom_pkg_name"
        )

        assert package.__name__ == "custom_pkg_name"
        assert "fixture_skill_d_lib" not in sys.modules
        assert sys.modules["custom_pkg_name"] is package


class TestImportSkillLibModule:
    def test_relative_import_resolves(self, tmp_path: Path) -> None:
        lib_dir = _write_fixture_lib(tmp_path, leaf_value=21)

        mid = import_skill_lib_module("fixture-skill-e", lib_dir, "mid")

        assert mid.DOUBLED == 42

    def test_leaf_module_alone_also_works(self, tmp_path: Path) -> None:
        lib_dir = _write_fixture_lib(tmp_path, leaf_value=5)

        leaf = import_skill_lib_module("fixture-skill-f", lib_dir, "leaf")

        assert leaf.VALUE == 5

    def test_idempotent_reimport_returns_same_module(self, tmp_path: Path) -> None:
        lib_dir = _write_fixture_lib(tmp_path)

        first = import_skill_lib_module("fixture-skill-g", lib_dir, "mid")
        second = import_skill_lib_module("fixture-skill-g", lib_dir, "mid")

        assert first is second


class TestLoadSkillLib:
    def test_loads_requested_modules_as_attributes(self, tmp_path: Path) -> None:
        lib_dir = _write_fixture_lib(tmp_path, leaf_value=3)

        ns = load_skill_lib("fixture-skill-h", lib_dir, ["leaf", "mid"])

        assert ns.leaf.VALUE == 3
        assert ns.mid.DOUBLED == 6
        assert ns.package.__name__ == "fixture_skill_h_lib"

    def test_order_of_module_names_does_not_matter(self, tmp_path: Path) -> None:
        """Requesting the dependent module before its dependency still works.

        Real skill libs (e.g. project-scout's ``orchestrate`` importing
        ``cluster``, which imports ``walk``/``foreign``/``docish``) rely
        on this: callers must not have to hand-derive a load order.
        """

        lib_dir = _write_fixture_lib(tmp_path, leaf_value=10)

        ns = load_skill_lib("fixture-skill-i", lib_dir, ["mid", "leaf"])

        assert ns.mid.DOUBLED == 20
        assert ns.leaf.VALUE == 10

    def test_two_skills_with_same_submodule_name_do_not_collide(
        self, tmp_path: Path
    ) -> None:
        """Two different (hyphenated) skills' same-named submodules stay isolated.

        Regression armor for the #358 / #367 cross-skill ``lib`` package
        collision the hand-written vendored helpers were built to dodge.
        """

        skill_a_dir = _write_fixture_lib(tmp_path / "skill_a", leaf_value=100)
        skill_b_dir = _write_fixture_lib(tmp_path / "skill_b", leaf_value=200)

        ns_a = load_skill_lib("fixture-skill-collide-a", skill_a_dir, ["leaf"])
        ns_b = load_skill_lib("fixture-skill-collide-b", skill_b_dir, ["leaf"])

        assert ns_a.leaf.VALUE == 100
        assert ns_b.leaf.VALUE == 200
        assert ns_a.leaf is not ns_b.leaf
