"""Regression test: installer never copies dev-machine __pycache__/*.pyc/.DS_Store
cruft into a consumer install.

Issue #818: ``install-anvil.sh``'s tree-copy helpers (``copy_tree``,
``replace_tree``, ``copy_lib_preserving_overrides``, and
``copy_skill_body_excluding_lib``) all used a bare ``cp -R "$src/." "$dst/"``
with no exclusion of ``__pycache__/`` dirs, ``*.pyc`` files, or macOS
``.DS_Store`` files. A dev checkout that has run ``pytest``/``pip install -e``
accumulates untracked ``__pycache__/`` dirs under ``anvil/skills/*`` and
``anvil/lib/``; those got physically copied into every consumer's ``.anvil/``
tree at install time, making installs non-deterministic and potentially
shipping ``.pyc`` files compiled under the wrong Python version.

The fix adds a shared ``strip_pycache_artifacts`` helper, invoked at the end
of every tree-copy helper, that removes any ``__pycache__`` dir, ``*.pyc``
file, or ``.DS_Store`` file from the destination post-copy. It also makes the
override-detection hash/diff helpers (``dir_hash``, ``dir_hash_body_only``,
``dirs_identical``, ``dirs_identical_body_only``) exclude the same patterns,
so a source tree that itself carries stray build artifacts still compares
"unmodified" against its (always cruft-free) installed copy.

These tests exercise the installer via ``subprocess`` so the contract is
enforced at the real entry point a consumer hits. Pattern mirrors
``test_install_hash_upgrade.py`` / ``test_install_lib_hash_upgrade.py``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _copy_anvil_checkout(dst: Path) -> Path:
    """Copy the minimum subset of the anvil source tree the installer reads.

    Mirrors ``test_install_hash_upgrade.py``'s helper of the same name.
    """

    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "CLAUDE.md", dst / "CLAUDE.md")
    shutil.copy(REPO_ROOT / "VERSION", dst / "VERSION")
    shutil.copytree(REPO_ROOT / "anvil", dst / "anvil")
    (dst / "scripts").mkdir(exist_ok=True)
    shutil.copy(
        REPO_ROOT / "scripts" / "install-anvil.sh",
        dst / "scripts" / "install-anvil.sh",
    )
    return dst


def _plant_cruft(fake_anvil: Path) -> None:
    """Plant stray __pycache__/*.pyc/.DS_Store files across the source tree,
    simulating a dev checkout that has run pytest / pip install -e (issue
    #818's exact reproduction scenario) — in locations covered by each of the
    four `cp -R`-based tree-copy sites:

      * a skill's lib/ (importable-mirror copy: copy_tree/replace_tree)
      * a skill's body OUTSIDE lib/ (copy_skill_body_excluding_lib)
      * anvil/lib itself (copy_tree/copy_lib_preserving_overrides)
    """

    # 1. Skill lib/ __pycache__ (e.g. anvil/skills/memo/lib/__pycache__).
    memo_lib_pycache = fake_anvil / "anvil" / "skills" / "memo" / "lib" / "__pycache__"
    memo_lib_pycache.mkdir(parents=True, exist_ok=True)
    (memo_lib_pycache / "project_brief.cpython-312.pyc").write_bytes(b"\x00\x01")

    # 2. Skill body __pycache__ OUTSIDE lib/ (e.g. tests/__pycache__ and the
    #    skill-root __init__.py bytecode dir) — the copy_skill_body_excluding_lib
    #    path, the one most likely to be missed by a partial fix.
    memo_root_pycache = fake_anvil / "anvil" / "skills" / "memo" / "__pycache__"
    memo_root_pycache.mkdir(parents=True, exist_ok=True)
    (memo_root_pycache / "__init__.cpython-312.pyc").write_bytes(b"\x00\x01")

    memo_tests_pycache = (
        fake_anvil / "anvil" / "skills" / "memo" / "tests" / "__pycache__"
    )
    memo_tests_pycache.mkdir(parents=True, exist_ok=True)
    (memo_tests_pycache / "test_foo.cpython-312-pytest-9.0.3.pyc").write_bytes(
        b"\x00\x01"
    )

    # 3. A stray .pyc directly alongside source (not inside __pycache__),
    #    which the *.pyc glob (not just the dir prune) must also catch.
    (fake_anvil / "anvil" / "skills" / "memo" / "stray.pyc").write_bytes(b"\x00\x01")

    # 4. macOS Finder cruft, at both the skill body and the framework lib root.
    (fake_anvil / "anvil" / "skills" / "memo" / ".DS_Store").write_bytes(b"\x00")

    # 5. Framework lib (anvil/lib) __pycache__ + .DS_Store — the
    #    copy_tree/copy_lib_preserving_overrides path.
    anvil_lib_pycache = fake_anvil / "anvil" / "lib" / "__pycache__"
    anvil_lib_pycache.mkdir(parents=True, exist_ok=True)
    (anvil_lib_pycache / "cite.cpython-312.pyc").write_bytes(b"\x00\x01")
    (fake_anvil / "anvil" / "lib" / ".DS_Store").write_bytes(b"\x00")


def _find_cruft(root: Path) -> list[Path]:
    """Return every __pycache__ dir, *.pyc file, or .DS_Store file under root."""

    hits: list[Path] = []
    hits.extend(root.rglob("__pycache__"))
    hits.extend(root.rglob("*.pyc"))
    hits.extend(root.rglob(".DS_Store"))
    return hits


def _run_from_fake_anvil(
    fake_anvil: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    installer = fake_anvil / "scripts" / "install-anvil.sh"
    return subprocess.run(
        ["bash", str(installer), *args],
        capture_output=True,
        text=True,
        cwd=fake_anvil,
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_fresh_install_strips_pycache_and_ds_store(tmp_path: Path) -> None:
    """A fresh install from a cruft-laden source tree ships a clean .anvil/."""

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    _plant_cruft(fake_anvil)

    # Sanity: the cruft really is present in the source tree before install.
    assert _find_cruft(fake_anvil / "anvil"), (
        "test setup failed to plant cruft in the source tree"
    )

    target = tmp_path / "target"
    target.mkdir()

    result = _run_from_fake_anvil(fake_anvil, "-y", "--skills=memo", str(target))
    assert result.returncode == 0, (
        f"install failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    installed_cruft = _find_cruft(target / ".anvil")
    assert installed_cruft == [], (
        "installed .anvil/ tree contains __pycache__/*.pyc/.DS_Store cruft "
        f"copied from the dev source tree: {installed_cruft}"
    )


def test_reinstall_over_cruft_laden_source_stays_unmodified(tmp_path: Path) -> None:
    """Re-installing from a cruft-laden source doesn't spuriously flag the
    skill as consumer-modified.

    This is the correctness half of the fix: stripping cruft post-copy while
    leaving the override-detection hash naive about the same cruft would make
    every "untouched since install" skill look consumer-modified on the very
    next run (the source-side hash would include the cruft; the dst-side hash
    never would, since it's always stripped). The hash/diff helpers must
    exclude the same patterns so this never happens.
    """

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    _plant_cruft(fake_anvil)

    target = tmp_path / "target"
    target.mkdir()

    first = _run_from_fake_anvil(fake_anvil, "-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=memo", str(target))
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr
    assert "skipped: consumer-modified" not in combined, (
        "re-install falsely flagged memo as consumer-modified due to "
        f"cruft-sensitive hashing:\n{combined}"
    )

    installed_cruft = _find_cruft(target / ".anvil")
    assert installed_cruft == [], (
        f"installed .anvil/ tree contains cruft after re-install: {installed_cruft}"
    )


def test_stage5_lib_copy_strips_pycache(tmp_path: Path) -> None:
    """The Stage 5 framework-lib copy (anvil/lib -> .anvil/anvil/lib) also
    strips cruft, independent of any skill selection."""

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    _plant_cruft(fake_anvil)

    target = tmp_path / "target"
    target.mkdir()

    result = _run_from_fake_anvil(fake_anvil, "-y", "--skills=memo", str(target))
    assert result.returncode == 0, result.stderr

    dst_lib = target / ".anvil" / "anvil" / "lib"
    assert dst_lib.is_dir()
    installed_cruft = _find_cruft(dst_lib)
    assert installed_cruft == [], (
        f"Stage 5 lib copy shipped cruft into {dst_lib}: {installed_cruft}"
    )
