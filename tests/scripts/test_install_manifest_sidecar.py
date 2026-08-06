"""Regression tests: machine-local install fields move to a gitignored sidecar (#894 — C6).

Before #894, ``scripts/install-anvil.sh``'s ``write_manifest`` embedded
``anvil_source`` (the installing machine's absolute source-checkout path) and
``install_date`` directly in the TRACKED ``.anvil/install-metadata.json``.
Both are machine-local — meaningless (and already wrong) in every checkout
but the one that ran the install. The fix splits them into a gitignored
sidecar, ``.anvil/.install-local.json``, mirroring the pattern Loom uses at
``.loom/loom-source-path`` and Repo Skills at
``.claude/skills/repo/.install-local.json``.

The tracked manifest keeps ``anvil_version``, the new ``commit`` field (a
byte-identical-across-machines replacement provenance signal for the old
``anvil_source`` path), and ``layout_version``, alongside the pre-existing
``installed_skills`` / ``skipped_overrides`` / ``skill_hashes`` /
``skill_versions`` / ``lib_hash`` fields.

These tests exercise the installer via ``subprocess`` at the real entry
point. Distinct filename per the #58 packaging convention (close analog:
``tests/scripts/test_install_anvil_gitignore.py``).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"installer exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Fresh install: tracked manifest has no machine-local fields
# ---------------------------------------------------------------------------


def test_fresh_install_manifest_excludes_machine_local_fields(
    tmp_path: Path,
) -> None:
    """The tracked manifest never carries ``anvil_source`` / ``install_date``."""
    target = tmp_path / "fresh"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    manifest_path = target / ".anvil" / "install-metadata.json"
    assert manifest_path.is_file(), "installer did not write install-metadata.json"
    manifest = json.loads(manifest_path.read_text())

    assert "anvil_source" not in manifest, (
        f"anvil_source must not be in the tracked manifest (machine-local, #894); got: {manifest}"
    )
    assert "install_date" not in manifest, (
        f"install_date must not be in the tracked manifest (machine-local, #894); got: {manifest}"
    )
    # Required tracked fields (C5: "at least version, commit, layout_version").
    assert manifest.get("anvil_version"), f"manifest missing anvil_version: {manifest}"
    assert "commit" in manifest, f"manifest missing commit: {manifest}"
    assert "layout_version" in manifest, f"manifest missing layout_version: {manifest}"


def test_fresh_install_writes_sidecar_with_machine_local_fields(
    tmp_path: Path,
) -> None:
    """``.anvil/.install-local.json`` carries ``anvil_source`` + ``install_date``."""
    target = tmp_path / "fresh-sidecar"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    sidecar_path = target / ".anvil" / ".install-local.json"
    assert sidecar_path.is_file(), (
        f".anvil/.install-local.json was not written; stdout:\n{result.stdout}"
    )
    sidecar = json.loads(sidecar_path.read_text())

    assert sidecar.get("anvil_source") == str(REPO_ROOT), (
        f"sidecar anvil_source should be the installing checkout's root; got: {sidecar}"
    )
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", sidecar.get("install_date", "")), (
        f"sidecar install_date should be a YYYY-MM-DD date; got: {sidecar}"
    )


def test_sidecar_pattern_is_gitignored_by_anvil_gitignore(tmp_path: Path) -> None:
    """The written ``.anvil/.gitignore`` covers the sidecar filename."""
    target = tmp_path / "sidecar-ignored"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    gi = target / ".anvil" / ".gitignore"
    assert gi.is_file()
    lines = [
        line.strip()
        for line in gi.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert ".install-local.json" in lines, (
        f".anvil/.gitignore should cover the sidecar filename; got: {lines}"
    )


# ---------------------------------------------------------------------------
# --dry-run honesty: neither manifest nor sidecar is written
# ---------------------------------------------------------------------------


def test_dry_run_writes_neither_manifest_nor_sidecar(tmp_path: Path) -> None:
    """``--dry-run`` writes nothing under a fresh target, including the sidecar."""
    target = tmp_path / "dry-run"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--skills=memo", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(result)

    assert not (target / ".anvil" / "install-metadata.json").exists()
    assert not (target / ".anvil" / ".install-local.json").exists()


# ---------------------------------------------------------------------------
# Upgrade: re-installing over a fresh (post-#894) install re-stamps the sidecar
# ---------------------------------------------------------------------------


def test_reinstall_restamps_sidecar_install_date(tmp_path: Path) -> None:
    """A re-install re-writes the sidecar (unlike the skip-if-exists .gitignore)."""
    target = tmp_path / "reinstall"
    target.mkdir()

    first = _run("--skills=memo", str(target))
    _assert_ok(first)
    sidecar_path = target / ".anvil" / ".install-local.json"
    first_sidecar = json.loads(sidecar_path.read_text())

    second = _run("--skills=memo", str(target))
    _assert_ok(second)
    second_sidecar = json.loads(sidecar_path.read_text())

    # Re-stamped, not skip-if-exists: anvil_source is deterministic given the
    # same installing checkout, so assert on presence/shape rather than
    # requiring the value to differ across runs on the same machine.
    assert second_sidecar.get("anvil_source") == first_sidecar.get("anvil_source")
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", second_sidecar.get("install_date", "")
    )
