"""Canonical-path tests for the promoted ``anvil/lib/project_detect.py`` (issue #407).

The detector core was promoted from
``anvil/skills/project-migrate/lib/detect.py`` when ``anvil:project-scout``
became its second consumer. This suite pins:

1. The canonical module imports cleanly and exposes the public API.
2. The skill-local shim re-exports **identical objects** (``is``-identity,
   not equal copies) — including the private surface the migrate siblings
   consume (``_classify``, ``_VERSION_DIR_RE``, ``_has_project_brief``, …).
3. Representative behavior through the canonical path (a classic-shape
   fixture classifies ``PRE_283_CLASSIC``; a bare fixture flags
   ``is_bare``).

The deep behavioral corpus stays in
``anvil/skills/project-migrate/tests/`` and runs against the shim — that
is deliberate (proves the shim carries the whole contract).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from anvil.lib import project_detect


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHIM_PATH = (
    _REPO_ROOT / "anvil" / "skills" / "project-migrate" / "lib" / "detect.py"
)


def _load_shim():
    """Load the skill-local shim by file path (skill dirs are not packages)."""
    name = "_test_project_detect_shim"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SHIM_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_canonical_module_public_api() -> None:
    for name in (
        "Shape",
        "ProjectInventory",
        "ThreadInventory",
        "detect_shape",
        "inventory_project",
        "BRIEF_FILENAME",
        "ANVIL_JSON_FILENAME",
    ):
        assert hasattr(project_detect, name), name


def test_shim_reexports_identical_objects() -> None:
    shim = _load_shim()
    # Public surface.
    assert shim.Shape is project_detect.Shape
    assert shim.ProjectInventory is project_detect.ProjectInventory
    assert shim.ThreadInventory is project_detect.ThreadInventory
    assert shim.detect_shape is project_detect.detect_shape
    assert shim.inventory_project is project_detect.inventory_project
    # Private surface the migrate siblings + tests consume.
    assert shim._classify is project_detect._classify
    assert shim._VERSION_DIR_RE is project_detect._VERSION_DIR_RE
    assert shim._has_project_brief is project_detect._has_project_brief
    assert shim._extract_frontmatter is project_detect._extract_frontmatter
    assert shim._project_brief_slugs is project_detect._project_brief_slugs
    assert (
        shim._SKILL_FIXED_BODY_FILENAMES
        is project_detect._SKILL_FIXED_BODY_FILENAMES
    )
    assert (
        shim._RETAINED_BODY_FILENAMES
        is project_detect._RETAINED_BODY_FILENAMES
    )
    assert (
        shim._INFRASTRUCTURE_DIRS is project_detect._INFRASTRUCTURE_DIRS
    )


def test_classic_shape_via_canonical_path() -> None:
    with TemporaryDirectory() as td:
        project = Path(td) / "acme-memo"
        for n in (1, 2):
            vd = project / f"memo.{n}"
            vd.mkdir(parents=True)
            (vd / "memo.md").write_text(f"# Draft v{n}\n", encoding="utf-8")
        (project / ".anvil.json").write_text("{}\n", encoding="utf-8")
        shape = project_detect.detect_shape(project)
        assert shape is project_detect.Shape.PRE_283_CLASSIC
        inv = project_detect.inventory_project(project)
        assert not inv.is_bare  # .anvil.json + memo.md body present


def test_bare_substate_via_canonical_path() -> None:
    with TemporaryDirectory() as td:
        project = Path(td) / "paper"
        for n in (1, 3, 4):
            vd = project / f"draft.{n}"
            vd.mkdir(parents=True)
            (vd / "paper.tex").write_text(
                "\\documentclass{article}\n", encoding="utf-8"
            )
        inv = project_detect.inventory_project(project)
        assert project_detect._classify(inv) is (
            project_detect.Shape.PRE_283_CLASSIC
        )
        assert inv.is_bare
