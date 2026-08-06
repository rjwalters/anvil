"""Regression tests: the installer reads its version from the root ``VERSION`` file (#894).

Issue #894 (C8): ``scripts/install-anvil.sh`` used to derive ``ANVIL_VERSION``
by regex-scraping the ``**Anvil Version**: X.Y.Z`` line out of ``CLAUDE.md``
prose — a purely cosmetic doc edit (rewording, re-bolding, moving the line)
broke the installer outright, and there was no fallback. The fix reads a
plain ``X.Y.Z`` string from a dedicated ``VERSION`` file at the repo root
instead — a version-bearing file with exactly one job, immune to prose churn.

These tests build a "fake anvil checkout" (mirroring the pattern in
``tests/scripts/test_install_hash_upgrade.py``) so the VERSION content can be
deliberately mismatched against CLAUDE.md's line — proving the installer
reads ``VERSION``, not ``CLAUDE.md`` prose, and exercising the missing/invalid
``VERSION`` error paths a real checkout would never hit.

Distinct filename per the #58 cross-skill collision convention.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _copy_anvil_checkout(dst: Path) -> Path:
    """Copy the minimum subset of the anvil source tree the installer reads."""
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
# VERSION is the value the installer actually uses
# ---------------------------------------------------------------------------


def test_installer_reads_version_from_version_file_not_claude_md(
    tmp_path: Path,
) -> None:
    """The installer's ANVIL_VERSION comes from VERSION, even when it disagrees with CLAUDE.md.

    Deliberately mismatching the two files proves the installer is not
    falling back to (or still reading) the CLAUDE.md prose scrape.
    """
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    (fake_anvil / "VERSION").write_text("7.7.7\n")
    # CLAUDE.md's line is deliberately left at the real repo's version, so if
    # the installer regressed to scraping CLAUDE.md this test fails loudly
    # (manifest would read the real repo's version, not "7.7.7").

    target = tmp_path / "target"
    target.mkdir()

    result = _run_from_fake_anvil(
        fake_anvil, "-y", "--no-sync", "--skills=memo", str(target)
    )
    assert result.returncode == 0, (
        f"install failed:\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "ANVIL_VERSION=7.7.7" in result.stdout, (
        f"expected the installer to report ANVIL_VERSION=7.7.7 (from VERSION, "
        f"not CLAUDE.md); got:\n{result.stdout}"
    )

    manifest = json.loads(
        (target / ".anvil" / "install-metadata.json").read_text()
    )
    assert manifest["anvil_version"] == "7.7.7", (
        f"manifest anvil_version should come from VERSION, not CLAUDE.md; got: {manifest}"
    )


def test_missing_version_file_errors_clearly(tmp_path: Path) -> None:
    """A source checkout with no VERSION file fails fast with a clear error."""
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil-no-version")
    (fake_anvil / "VERSION").unlink()

    target = tmp_path / "target"
    target.mkdir()

    result = _run_from_fake_anvil(
        fake_anvil, "-y", "--no-sync", "--skills=memo", str(target)
    )
    assert result.returncode != 0, (
        f"installer should fail without a VERSION file; got exit 0:\n{result.stdout}"
    )
    combined = result.stdout + result.stderr
    assert "VERSION" in combined, (
        f"error message should name the missing VERSION file; got:\n{combined}"
    )
    assert not (target / ".anvil").exists(), (
        "a failed version resolution should not have written anything to the target"
    )


def test_invalid_version_content_errors_clearly(tmp_path: Path) -> None:
    """A VERSION file with non-semver content fails fast with a clear error."""
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil-bad-version")
    (fake_anvil / "VERSION").write_text("not-a-version\n")

    target = tmp_path / "target"
    target.mkdir()

    result = _run_from_fake_anvil(
        fake_anvil, "-y", "--no-sync", "--skills=memo", str(target)
    )
    assert result.returncode != 0, (
        f"installer should fail on invalid VERSION content; got exit 0:\n{result.stdout}"
    )
    combined = result.stdout + result.stderr
    assert "VERSION" in combined and "not-a-version" in combined, (
        f"error message should name the file and the bad content; got:\n{combined}"
    )
    assert not (target / ".anvil").exists(), (
        "a failed version resolution should not have written anything to the target"
    )
