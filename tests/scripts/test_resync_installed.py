"""Regression tests: the consumer-side ``.anvil/scripts/resync-installed.sh`` (#894 — C7).

Anvil is a COPY installer, so a fix merged to the source repo's ``main``
does not reach an already-installed consumer until the installer is
re-run. ``scripts/resync-installed.sh`` (shipped into a consumer at
``.anvil/scripts/resync-installed.sh`` by ``install-anvil.sh``'s Stage 8.7)
closes that gap: it resolves the recorded Anvil source checkout (sidecar
``.anvil/.install-local.json`` first, then the legacy inline
``install-metadata.json`` field, matching the resolution order
``.claude/commands/repo/update-tools.md`` documents), reads the currently
installed skill set from the tracked manifest, and re-invokes that source's
own ``install-anvil.sh`` with exactly that skill set and no ``--force`` — the
existing hash-tracked "preserve consumer edits" contract IS the
non-destructive refresh; passing back the recorded skill set unchanged means
the installer's Stage 7.6 removed-skill prune can never fire.

These tests exercise a REAL install (subprocess against
``scripts/install-anvil.sh``) into a tmp target, then invoke the resync
script that install wrote at ``.anvil/scripts/resync-installed.sh`` (its
resolved Anvil source is this checkout, since that's what performed the
real install). Distinct filename per the #58 packaging convention.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _install(target: Path, *, skills: str = "memo,help") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", f"--skills={skills}", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"command exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def _resync(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    script = target / ".anvil" / "scripts" / "resync-installed.sh"
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True,
        text=True,
        cwd=target,
    )


def _installed_skills(target: Path) -> list[str]:
    manifest = json.loads(
        (target / ".anvil" / "install-metadata.json").read_text()
    )
    return manifest["installed_skills"]


# ---------------------------------------------------------------------------
# The installer ships the resync script
# ---------------------------------------------------------------------------


def test_installer_ships_resync_script(tmp_path: Path) -> None:
    """Every install writes an executable ``.anvil/scripts/resync-installed.sh``."""
    target = tmp_path / "ships-resync"
    target.mkdir()

    result = _install(target)
    _assert_ok(result)

    script = target / ".anvil" / "scripts" / "resync-installed.sh"
    assert script.is_file(), f"resync script not written; stdout:\n{result.stdout}"
    assert script.stat().st_mode & 0o111, "resync script must be executable"


# ---------------------------------------------------------------------------
# --dry-run: reports planned changes, writes nothing
# ---------------------------------------------------------------------------


def test_dry_run_reports_and_writes_nothing(tmp_path: Path) -> None:
    """``--dry-run`` relays the underlying installer's dry-run preview and mutates nothing."""
    target = tmp_path / "dry-run"
    target.mkdir()
    _assert_ok(_install(target))

    manifest_path = target / ".anvil" / "install-metadata.json"
    before = manifest_path.read_text()
    before_mtime = manifest_path.stat().st_mtime_ns

    result = _resync(target, "--dry-run")
    assert result.returncode == 0, (
        f"--dry-run should exit 0:\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "[dry-run]" in result.stdout, (
        f"expected the underlying installer's dry-run markers; got:\n{result.stdout}"
    )
    assert "no files were written" in result.stdout, (
        f"expected the dry-run-honesty summary line; got:\n{result.stdout}"
    )

    after = manifest_path.read_text()
    assert after == before, "resync --dry-run modified install-metadata.json"
    assert manifest_path.stat().st_mtime_ns == before_mtime, (
        "resync --dry-run touched install-metadata.json's mtime"
    )


# ---------------------------------------------------------------------------
# A real (non-dry-run) resync never uninstalls
# ---------------------------------------------------------------------------


def test_resync_never_uninstalls(tmp_path: Path) -> None:
    """A real resync preserves the full previously-installed skill set."""
    target = tmp_path / "never-uninstalls"
    target.mkdir()
    _assert_ok(_install(target, skills="memo,help"))

    before_skills = set(_installed_skills(target))
    assert before_skills == {"memo", "help"}
    for skill in before_skills:
        assert (target / ".anvil" / "skills" / skill).is_dir()
        assert (target / ".claude" / "skills" / f"anvil-{skill}").is_dir()

    result = _resync(target)
    assert result.returncode == 0, (
        f"resync failed:\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )

    after_skills = set(_installed_skills(target))
    assert after_skills == before_skills, (
        f"resync changed the installed skill set: {before_skills} -> {after_skills}"
    )
    for skill in before_skills:
        assert (target / ".anvil" / "skills" / skill).is_dir(), (
            f"resync removed .anvil/skills/{skill}/"
        )
        assert (target / ".claude" / "skills" / f"anvil-{skill}").is_dir(), (
            f"resync removed .claude/skills/anvil-{skill}/"
        )


# ---------------------------------------------------------------------------
# --quiet suppresses per-stage noise but still reports the summary
# ---------------------------------------------------------------------------


def test_quiet_flag_suppresses_stage_noise(tmp_path: Path) -> None:
    """``--quiet`` output is a strict subset of the verbose output's lines."""
    target = tmp_path / "quiet"
    target.mkdir()
    _assert_ok(_install(target))

    verbose = _resync(target)
    assert verbose.returncode == 0, verbose.stderr

    quiet = _resync(target, "--quiet")
    assert quiet.returncode == 0, quiet.stderr

    assert len(quiet.stdout.splitlines()) < len(verbose.stdout.splitlines()), (
        "quiet output should be shorter than the verbose output:\n"
        f"--- verbose ---\n{verbose.stdout}\n--- quiet ---\n{quiet.stdout}"
    )
    assert "resync complete" in quiet.stdout


# ---------------------------------------------------------------------------
# Sidecar-then-inline fallback resolution
# ---------------------------------------------------------------------------


def test_resolves_source_from_sidecar_by_default(tmp_path: Path) -> None:
    """A fresh (post-#894) install resolves its source via the sidecar."""
    target = tmp_path / "sidecar-resolve"
    target.mkdir()
    _assert_ok(_install(target))

    result = _resync(target, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "via sidecar" in result.stdout, (
        f"expected sidecar-first resolution; got:\n{result.stdout}"
    )
    assert str(REPO_ROOT) in result.stdout


def test_falls_back_to_legacy_inline_source_field(tmp_path: Path) -> None:
    """A pre-#894 install (no sidecar, anvil_source inline in the manifest) still resolves."""
    target = tmp_path / "legacy-fallback"
    target.mkdir()
    _assert_ok(_install(target))

    sidecar_path = target / ".anvil" / ".install-local.json"
    manifest_path = target / ".anvil" / "install-metadata.json"
    sidecar = json.loads(sidecar_path.read_text())
    manifest = json.loads(manifest_path.read_text())

    # Simulate the pre-#894 shape: anvil_source inline in the tracked
    # manifest, no sidecar at all.
    manifest["anvil_source"] = sidecar["anvil_source"]
    manifest["install_date"] = sidecar["install_date"]
    manifest_path.write_text(json.dumps(manifest))
    sidecar_path.unlink()

    result = _resync(target, "--dry-run")
    assert result.returncode == 0, (
        f"resync should still resolve the source via the legacy inline field:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "via legacy inline field" in result.stdout, (
        f"expected the legacy inline fallback to be reported; got:\n{result.stdout}"
    )
    assert str(REPO_ROOT) in result.stdout


def test_errors_clearly_when_source_unresolvable(tmp_path: Path) -> None:
    """No sidecar and no inline field -> a clear error, not a crash."""
    target = tmp_path / "unresolvable"
    target.mkdir()
    _assert_ok(_install(target))

    (target / ".anvil" / ".install-local.json").unlink()
    manifest_path = target / ".anvil" / "install-metadata.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("anvil_source", None)
    manifest_path.write_text(json.dumps(manifest))

    result = _resync(target, "--dry-run")
    assert result.returncode != 0, (
        f"expected a non-zero exit when the source is unresolvable; got:\n{result.stdout}"
    )
    combined = result.stdout + result.stderr
    assert "could not resolve" in combined, (
        f"expected a clear 'could not resolve' error; got:\n{combined}"
    )
