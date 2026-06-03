"""Regression test: a consumer install is ``uv``-runnable without the source repo.

Issue #230: prior installs shipped framework Python at ``.anvil/lib/`` and
skill Python at ``.anvil/skills/<name>/lib/`` — but there was no ``anvil/``
package root and no consumer-side ``pyproject.toml``, so ``from anvil.lib
import ...`` failed unless the consumer also had the anvil source repo
cloned at the install-time path recorded in ``install-metadata.json``.

The studio canary hit this failure mode on a fresh machine where the
install-time source path didn't exist; the workaround required cloning the
anvil source, ``uv sync`` in the source tree, and constructing a transient
symlink shim to fabricate an importable ``anvil/`` package.

The fix reshapes the installer to:

  * Ship the importable Python mirror at ``<consumer>/.anvil/anvil/`` (the
    framework + each skill's ``lib/`` subdir + the package ``__init__.py``
    chain).
  * Generate ``<consumer>/.anvil/pyproject.toml`` declaring ``pydantic`` +
    ``pyyaml`` as base deps, with ``setuptools.packages.find`` rooted at
    the in-tree ``anvil/``.
  * Optionally run ``uv sync --project .anvil`` as a final install step
    (default; ``--no-sync`` opts out for offline installs).

This test exercises the contract end-to-end: install into a *throwaway*
consumer tmpdir, then assert ``uv run --project .anvil python -c
"from anvil.lib.render_gate import gate"`` succeeds from the consumer
root. The test does NOT depend on the anvil source repo being present at
the install-time path — it explicitly drops the source path from the
subprocess environment (and from PYTHONPATH) so a regression that re-
introduces a source-path dependency would surface as an import failure.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uv_present() -> bool:
    """``uv`` on PATH is required for the import-cycle assertions."""

    return shutil.which("uv") is not None


def _install_into(
    target: Path,
    *,
    skills: str = "memo",
    no_sync: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Install anvil into ``target`` and capture the installer's output.

    Defaults to ``--no-sync`` so each test controls the sync timing
    explicitly (we want to assert the post-install layout independently
    of whether uv was on PATH, and run a *single* sync per test rather
    than re-syncing in every sub-assertion).
    """

    args = ["bash", str(INSTALLER), "-y", f"--skills={skills}"]
    if no_sync:
        args.append("--no-sync")
    args.append(str(target))
    return subprocess.run(args, capture_output=True, text=True, cwd=REPO_ROOT)


def _sanitized_env() -> dict[str, str]:
    """Return an env dict with PYTHONPATH stripped of the source-repo path.

    A regression test that runs the installed ``.anvil`` from the consumer
    must not accidentally satisfy the import via the developer's source
    checkout being on ``PYTHONPATH``. Strip it so a re-introduced
    source-path dependency surfaces as a failed import.
    """

    env = dict(os.environ)
    # Drop any PYTHONPATH entry pointing into the anvil source tree.
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


# ---------------------------------------------------------------------------
# Layout assertions
# ---------------------------------------------------------------------------


def test_install_produces_importable_anvil_package_mirror(tmp_path: Path) -> None:
    """The installer must ship an importable ``anvil/`` package at ``.anvil/anvil/``.

    The pre-#230 layout (`.anvil/lib/` and `.anvil/skills/<name>/lib/`)
    is not load-bearing for runtime invocation anymore; the new mirror
    is the canonical import target.
    """

    target = tmp_path / "consumer"
    target.mkdir()

    result = _install_into(target, skills="memo")
    assert result.returncode == 0, (
        f"install failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    # Importable package anchor.
    assert (target / ".anvil" / "anvil" / "__init__.py").is_file(), (
        "missing .anvil/anvil/__init__.py — `import anvil` would fail"
    )
    # Framework lib (the canary-reproducer module lives here).
    assert (target / ".anvil" / "anvil" / "lib" / "render_gate.py").is_file()
    assert (target / ".anvil" / "anvil" / "lib" / "__init__.py").is_file()
    # Skills sub-package + memo skill lib.
    assert (target / ".anvil" / "anvil" / "skills" / "__init__.py").is_file()
    assert (target / ".anvil" / "anvil" / "skills" / "memo" / "__init__.py").is_file()
    assert (
        target / ".anvil" / "anvil" / "skills" / "memo" / "lib" / "__init__.py"
    ).is_file()


def test_install_produces_consumer_pyproject_toml(tmp_path: Path) -> None:
    """``.anvil/pyproject.toml`` declares the base deps + package layout.

    AC2: the file must exist, declare pydantic + pyyaml as base deps, and
    point setuptools.packages.find at the in-tree ``anvil/`` directory.
    """

    target = tmp_path / "consumer"
    target.mkdir()

    result = _install_into(target, skills="memo")
    assert result.returncode == 0, result.stderr

    pyproject = target / ".anvil" / "pyproject.toml"
    assert pyproject.is_file(), ".anvil/pyproject.toml not written by installer"

    body = pyproject.read_text()
    # Base deps mirror source; pyyaml is the load-bearing addition gated on
    # #231 (which has landed — see WORK_LOG entry for PR #268).
    assert 'name = "anvil"' in body
    assert "pydantic>=2.0" in body, "pydantic missing from consumer pyproject base deps"
    assert "pyyaml>=6.0" in body, "pyyaml missing from consumer pyproject base deps"
    # Package layout points at the in-tree anvil/ mirror.
    assert '[tool.setuptools.packages.find]' in body
    assert 'include = ["anvil*"]' in body


def test_install_records_layout_version_two_in_manifest(tmp_path: Path) -> None:
    """``install-metadata.json.layout_version`` flags the post-#230 shape.

    Consumers (and any downstream tooling that branches on the on-disk
    layout) can read the layout_version to tell apart the pre-#230 shape
    (no value present, treat as 1) from the post-#230 uv-runnable mirror.
    """

    target = tmp_path / "consumer"
    target.mkdir()

    result = _install_into(target, skills="memo")
    assert result.returncode == 0, result.stderr

    manifest = json.loads(
        (target / ".anvil" / "install-metadata.json").read_text()
    )
    assert manifest.get("layout_version") == 2, (
        f"expected layout_version=2 in manifest, got: {manifest!r}"
    )


# ---------------------------------------------------------------------------
# AC3 — uv-runnable import works without the source repo
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _uv_present(), reason="uv not on PATH")
def test_uv_sync_and_import_render_gate_succeeds_from_consumer(tmp_path: Path) -> None:
    """The canonical AC3 assertion: ``uv run ... from anvil.lib.render_gate
    import gate`` succeeds from the consumer root.

    This is the studio canary failure mode being closed. A regression that
    re-introduces a source-path dependency (e.g. setuptools.packages.find
    pointed at a directory that doesn't exist on the consumer, or a hard-
    coded ``sys.path`` insert in the installer that points at ANVIL_ROOT)
    would surface here as a non-zero subprocess exit.
    """

    target = tmp_path / "consumer"
    target.mkdir()

    install = _install_into(target, skills="memo")
    assert install.returncode == 0, install.stderr

    env = _sanitized_env()

    # uv sync materializes the venv at <target>/.anvil/.venv.
    sync = subprocess.run(
        ["uv", "sync", "--project", ".anvil"],
        capture_output=True,
        text=True,
        cwd=target,
        env=env,
    )
    assert sync.returncode == 0, (
        f"uv sync failed at {target!r}:\n"
        f"--- stdout ---\n{sync.stdout}\n--- stderr ---\n{sync.stderr}"
    )

    # The canary-style import. We assert the module attribute matches the
    # full dotted path so a silently-shadowed `gate` (e.g. via PYTHONPATH
    # leakage) would still surface as a regression — the only path that
    # legitimately produces ``anvil.lib.render_gate`` is the one shipped
    # under .anvil/anvil/.
    invoke = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            ".anvil",
            "python",
            "-c",
            "from anvil.lib.render_gate import gate; print(gate.__module__)",
        ],
        capture_output=True,
        text=True,
        cwd=target,
        env=env,
    )
    assert invoke.returncode == 0, (
        f"import-cycle failed at {target!r}:\n"
        f"--- stdout ---\n{invoke.stdout}\n--- stderr ---\n{invoke.stderr}"
    )
    assert "anvil.lib.render_gate" in invoke.stdout, (
        f"gate.__module__ not resolved to anvil.lib.render_gate; got:\n"
        f"{invoke.stdout!r}"
    )


@pytest.mark.skipif(not _uv_present(), reason="uv not on PATH")
def test_uv_sync_and_import_skill_lib_succeeds(tmp_path: Path) -> None:
    """Skill-side Python is importable via the same uv-runnable mirror.

    The Python under ``anvil/skills/<name>/lib/`` lives at
    ``<consumer>/.anvil/anvil/skills/<name>/lib/`` post-#230. A regression
    where the skill-lib copy is dropped or mis-pathed (e.g. the installer
    only mirrors framework lib, not skill lib) would surface here.
    """

    target = tmp_path / "consumer"
    target.mkdir()

    install = _install_into(target, skills="memo")
    assert install.returncode == 0, install.stderr

    env = _sanitized_env()

    sync = subprocess.run(
        ["uv", "sync", "--project", ".anvil"],
        capture_output=True,
        text=True,
        cwd=target,
        env=env,
    )
    assert sync.returncode == 0, sync.stderr

    invoke = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            ".anvil",
            "python",
            "-c",
            "from anvil.skills.memo.lib import memo_image_refs; print(memo_image_refs.__name__)",
        ],
        capture_output=True,
        text=True,
        cwd=target,
        env=env,
    )
    assert invoke.returncode == 0, (
        f"skill-lib import failed at {target!r}:\n"
        f"--- stdout ---\n{invoke.stdout}\n--- stderr ---\n{invoke.stderr}"
    )
    assert "anvil.skills.memo.lib.memo_image_refs" in invoke.stdout


# ---------------------------------------------------------------------------
# AC4 — --no-sync opts out of the post-install uv sync step
# ---------------------------------------------------------------------------


def test_no_sync_flag_skips_post_install_uv_sync(tmp_path: Path) -> None:
    """``--no-sync`` must opt out of the Stage 10.5 ``uv sync`` invocation.

    The note line ("skipping uv sync (--no-sync requested)") is the
    user-visible signal that the opt-out fired. We don't assert on the
    presence of a ``.venv`` here because uv may have created one in a
    prior test run sharing the tmpdir — the load-bearing check is the
    installer's own log line.
    """

    target = tmp_path / "consumer"
    target.mkdir()

    result = _install_into(target, skills="memo", no_sync=True)
    assert result.returncode == 0, result.stderr
    assert "skipping uv sync (--no-sync requested)" in result.stdout, (
        f"expected --no-sync note in stdout; got:\n{result.stdout}"
    )


def test_dry_run_prints_uv_sync_command_without_executing(tmp_path: Path) -> None:
    """Under ``--dry-run`` Stage 10.5 must surface the command, not run it.

    The dry-run honesty contract (issue #81) requires no writes; the uv
    sync step must observe the same contract. We assert the command line
    is printed (so the operator sees what a real run would do) and that
    no venv was created in the target.
    """

    target = tmp_path / "consumer"
    target.mkdir()

    result = subprocess.run(
        [
            "bash",
            str(INSTALLER),
            "--dry-run",
            "--skills=memo",
            str(target),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "[dry-run] uv sync --project" in result.stdout, (
        f"expected dry-run uv sync line in stdout; got:\n{result.stdout}"
    )
    # The dry-run honesty contract: target tree stays empty.
    assert not (target / ".anvil").exists(), (
        f"--dry-run created .anvil/ in target; tree:\n"
        f"{sorted(p.relative_to(target) for p in target.rglob('*'))}"
    )


# ---------------------------------------------------------------------------
# AC6 — manifest does not depend on anvil_source being live for runtime
# ---------------------------------------------------------------------------


def test_manifest_anvil_source_is_provenance_not_runtime_dependency(
    tmp_path: Path,
) -> None:
    """``install-metadata.json.anvil_source`` is install-provenance only.

    Post-#230, the runtime import path is rooted at ``.anvil/anvil/`` and
    does NOT consult ``anvil_source``. To prove this end-to-end we install
    into a tmpdir, then mutate the manifest's ``anvil_source`` to point at
    a non-existent path, then re-run the import-cycle assertion. The
    import should still succeed because the runtime layout is self-
    contained.

    (We don't actually delete the source repo on disk — that would break
    the rest of the test suite — but the manifest-level mutation simulates
    the consumer-machine case where ``anvil_source`` was set at install
    time from a different machine.)
    """

    if not _uv_present():
        pytest.skip("uv not on PATH")

    target = tmp_path / "consumer"
    target.mkdir()

    install = _install_into(target, skills="memo")
    assert install.returncode == 0, install.stderr

    manifest_path = target / ".anvil" / "install-metadata.json"
    manifest = json.loads(manifest_path.read_text())
    # Mutate anvil_source to a path that definitely doesn't exist.
    manifest["anvil_source"] = "/this/path/intentionally/does/not/exist"
    manifest_path.write_text(json.dumps(manifest))

    env = _sanitized_env()
    sync = subprocess.run(
        ["uv", "sync", "--project", ".anvil"],
        capture_output=True,
        text=True,
        cwd=target,
        env=env,
    )
    assert sync.returncode == 0, sync.stderr

    invoke = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            ".anvil",
            "python",
            "-c",
            "from anvil.lib.render_gate import gate; print(gate.__module__)",
        ],
        capture_output=True,
        text=True,
        cwd=target,
        env=env,
    )
    assert invoke.returncode == 0, (
        f"import failed after anvil_source mutation (regression — runtime "
        f"is depending on anvil_source being live on disk):\n"
        f"--- stdout ---\n{invoke.stdout}\n--- stderr ---\n{invoke.stderr}"
    )
    assert "anvil.lib.render_gate" in invoke.stdout
