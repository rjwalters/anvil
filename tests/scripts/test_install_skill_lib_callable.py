"""Regression test: every skill's ``lib/*.py`` is importable post-install.

Issue #375: the install ships skill-lib Python correctly at
``<consumer>/.anvil/anvil/skills/<name>/lib/`` (Stage 7 mirror in
``scripts/install-anvil.sh``, post-#230), but a class of regressions can
cause that mirror to silently drop a module — e.g., a future installer
refactor that branches the skill-lib copy off the framework-lib copy and
misses one tree, or a packaging change that breaks the ``anvil.skills.<X>.lib``
import path.

The studio canary failure mode the issue documents was *doc-vs-code drift*
(the deck-review.md prose pointed agents at filesystem paths that no longer
exist), but the install-script-regression case the canary asked for is "is
every skill-lib module actually importable from the consumer install?" —
i.e., the contract the docs were silently relying on.

This test enumerates every ``anvil/skills/<name>/lib/*.py`` in the source
tree and asserts that, after a clean ``install-anvil.sh`` (all skills)
+ ``uv sync --project .anvil``, ``uv run --project .anvil python -c
"importlib.import_module('anvil.skills.<name>.lib.<modname>')"`` exits 0
for every module.

Template: ``tests/scripts/test_install_uv_runnable.py:259-305``
(``test_uv_sync_and_import_skill_lib_succeeds``) is the single-skill
single-module precedent; this test generalizes to every skill that ships
a ``lib/`` subdir. Performance: one install + one sync + one parametrized
import-per-module — re-running the installer per module would multiply
the wall-clock cost by ~40x for no additional signal (the Stage 7 mirror
fires identically per skill regardless of which skills were selected).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"
SKILLS_DIR = REPO_ROOT / "anvil" / "skills"


# ---------------------------------------------------------------------------
# Helpers (mirrored from test_install_uv_runnable.py to keep this file
# self-contained; the cross-skill collision discipline forbids importing
# from a sibling test module).
# ---------------------------------------------------------------------------


def _uv_present() -> bool:
    """``uv`` on PATH is required for the post-install import assertions."""

    return shutil.which("uv") is not None


def _sanitized_env() -> dict[str, str]:
    """Return an env dict with PYTHONPATH stripped of the source-repo path.

    Same rationale as ``test_install_uv_runnable.py::_sanitized_env``: a
    regression that re-introduces a source-path dependency for skill-lib
    imports must surface as an import failure, not be masked by the
    developer's PYTHONPATH happening to include the source checkout.
    """

    env = dict(os.environ)
    pythonpath = env.get("PYTHONPATH", "")
    if pythonpath:
        keep = [
            part
            for part in pythonpath.split(os.pathsep)
            if part and not part.startswith(str(REPO_ROOT))
        ]
        if keep:
            env["PYTHONPATH"] = os.pathsep.join(keep)
        else:
            env.pop("PYTHONPATH", None)
    return env


def _discover_skill_lib_modules() -> list[tuple[str, str]]:
    """Enumerate every ``anvil/skills/<name>/lib/<module>.py`` in the source tree.

    Returns a list of ``(skill_name, module_name)`` tuples. Skips
    ``__init__.py`` (the package anchor, asserted via the parent import in
    the same test) and non-``.py`` files (e.g. JSON schemas). Skips skills
    with no ``lib/`` subdir.

    Skills with no shippable ``.py`` modules under ``lib/`` (other than
    ``__init__.py``) are skipped at the param-collection level — the
    ``__init__.py``-only-lib shape is asserted by the ``anvil.skills.<X>.lib``
    package import that the parametrized test runs.
    """

    discovered: list[tuple[str, str]] = []
    if not SKILLS_DIR.is_dir():
        return discovered

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        lib_dir = skill_dir / "lib"
        if not lib_dir.is_dir():
            continue
        for entry in sorted(lib_dir.iterdir()):
            if not entry.is_file():
                continue
            if entry.suffix != ".py":
                continue
            if entry.name == "__init__.py":
                continue
            discovered.append((skill_dir.name, entry.stem))
    return discovered


# Parametrize collection at module-import time. If the discovery returns
# an empty list (no skills with shippable lib modules — unlikely given
# the v0.4 state), pytest emits a single "no tests collected" message
# rather than passing vacuously.
_SKILL_LIB_MODULES = _discover_skill_lib_modules()


# ---------------------------------------------------------------------------
# Shared session-scoped consumer install
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def consumer_install() -> Path:
    """Install anvil (all skills) into a session-scoped tmpdir + ``uv sync``.

    Performance: re-running ``install-anvil.sh`` + ``uv sync`` per
    parametrized module would multiply wall-clock cost by ~40x for no
    additional signal — the Stage 7 mirror in ``scripts/install-anvil.sh``
    fires once per selected skill regardless of which other skills are
    selected, so a single install with all skills selected is the same
    code path as N separate single-skill installs, modulo the per-skill
    body copy. Run once at the session level and re-use across every
    module's import assertion.
    """

    if not _uv_present():
        pytest.skip("uv not on PATH")

    # Use a manually-managed tmpdir so the fixture is session-scoped (the
    # built-in ``tmp_path`` is function-scoped and cannot be reused).
    tmpdir = tempfile.mkdtemp(prefix="anvil-install-skill-lib-")
    target = Path(tmpdir) / "consumer"
    target.mkdir()

    # No --skills= flag installs all skills (see install-anvil.sh:278-280).
    install = subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert install.returncode == 0, (
        f"installer failed (all skills):\n"
        f"--- stdout ---\n{install.stdout}\n"
        f"--- stderr ---\n{install.stderr}"
    )

    env = _sanitized_env()

    sync = subprocess.run(
        ["uv", "sync", "--project", ".anvil"],
        capture_output=True,
        text=True,
        cwd=target,
        env=env,
    )
    assert sync.returncode == 0, (
        f"uv sync failed at {target!r}:\n"
        f"--- stdout ---\n{sync.stdout}\n"
        f"--- stderr ---\n{sync.stderr}"
    )

    return target


# ---------------------------------------------------------------------------
# The regression assertion (issue #375)
# ---------------------------------------------------------------------------


def _param_for(skill: str, module: str) -> object:
    """Build the parametrize entry for ``(skill, module)``."""

    return pytest.param(skill, module, id=f"{skill}.{module}")


@pytest.mark.skipif(not _uv_present(), reason="uv not on PATH")
@pytest.mark.parametrize(
    ("skill", "module"),
    [_param_for(skill, module) for skill, module in _SKILL_LIB_MODULES],
)
def test_skill_lib_module_is_importable_post_install(
    consumer_install: Path,
    skill: str,
    module: str,
) -> None:
    """Every skill-local ``lib/<module>.py`` must be importable post-install.

    The canary failure mode (issue #375): deck-review.md instructed the
    reviewer agent to invoke ``anvil/skills/deck/lib/parity_lint.py`` as a
    filesystem path. Post-#230 the lib lives at
    ``.anvil/anvil/skills/deck/lib/parity_lint.py`` and is invokable only
    via the Python import path ``anvil.skills.deck.lib.parity_lint``. A
    reviewer agent reading the (now-fixed) doc and resolving the path
    against the install root would not find the file and would silently
    skip the lint.

    The doc fix is in ``commands/deck-review.md`` (rewrite filesystem-path
    references to Python-import form). The install-script regression case
    is this test: every shippable skill-lib module must satisfy
    ``importlib.import_module("anvil.skills.<X>.lib.<Y>")`` from a clean
    consumer install.

    Why this is at the install-script-test layer (not just a unit import
    test in the source tree): the source tree's ``anvil/skills/<X>/lib/``
    is always importable from the source root; the canary failure mode is
    specifically the *consumer install* layout where the lib is mirrored
    to ``.anvil/anvil/skills/<X>/lib/`` and the consumer's ``uv sync``
    materializes the venv that resolves the import. A unit test in
    ``tests/lib/`` would not catch a Stage 7 mirror regression in
    ``scripts/install-anvil.sh``.
    """

    target = consumer_install
    env = _sanitized_env()

    dotted = f"anvil.skills.{skill}.lib.{module}"
    # Use ``importlib.import_module`` so hyphenated skill directory names
    # (``project-migrate``, ``rubric-rebackport``) resolve cleanly — the
    # ``import x`` statement form rejects hyphenated identifiers, but
    # ``importlib.import_module`` resolves directory-shape modules just
    # fine. The on-disk shape post-install mirrors the source tree, so
    # the import behavior is identical to a source-tree resolve.
    invoke = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            ".anvil",
            "python",
            "-c",
            (
                "import importlib; "
                f"m = importlib.import_module({dotted!r}); "
                "print(m.__name__)"
            ),
        ],
        capture_output=True,
        text=True,
        cwd=target,
        env=env,
    )
    assert invoke.returncode == 0, (
        f"skill-lib module {dotted!r} not importable at {target!r}:\n"
        f"--- stdout ---\n{invoke.stdout}\n"
        f"--- stderr ---\n{invoke.stderr}\n"
        f"The Stage 7 skill-lib mirror in scripts/install-anvil.sh may "
        f"have regressed — check that "
        f".anvil/anvil/skills/{skill}/lib/{module}.py exists in the "
        f"consumer install."
    )
    assert dotted in invoke.stdout, (
        f"module name not resolved to {dotted!r}; got:\n{invoke.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Sanity: the discovery itself found at least one shippable module
# ---------------------------------------------------------------------------


def test_discovery_found_at_least_one_skill_lib_module() -> None:
    """Discovery sanity check: at least one skill ships a ``lib/<X>.py``.

    Guards against a regression where the parametrization silently
    collapses to zero cases (e.g. ``anvil/skills/`` moved or the file
    extension changed) and the parametrized assertion above passes
    vacuously. As of v0.4 every artifact-class skill except the
    installation skill ships at least one ``lib/*.py``.
    """

    assert len(_SKILL_LIB_MODULES) > 0, (
        "no skill-lib modules discovered under "
        f"{SKILLS_DIR} — either the source tree moved or the "
        "discovery glob is broken. Check anvil/skills/*/lib/*.py."
    )
