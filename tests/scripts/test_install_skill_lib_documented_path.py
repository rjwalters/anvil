"""Regression test: ``.anvil/skills/<name>/lib/`` (the documented direct-
invocation path) exists on a consumer install.

Issue #743: every SKILL.md's lifecycle wiring instructs the *executing
agent* to run a phase CLI as a plain filesystem path — e.g. ``python3
.anvil/skills/memo/lib/render_phase.py <version-dir>`` — not a Python
import. Prior to this fix, ``install-anvil.sh`` Stage 7 only mirrored a
skill's ``lib/`` subdir to the *importable* location,
``.anvil/anvil/skills/<name>/lib/`` (``anvil.skills.<name>.lib.*``); the
documented path never existed post-install, so every such invocation
failed with "No such file or directory". Because the render-phase CLIs are
documented as non-blocking (always exit 0), the failure was silent: a
drafter/reviser pass would "succeed" with no rendered artifact.

The fix ships the skill's ``lib/`` subdir to a SECOND destination,
``.anvil/skills/<name>/lib/`` — a sibling of the importable mirror, not a
replacement for it. This test asserts that sibling copy lands, is
byte-identical to source, is directly executable at the documented path,
and — per the #152 override-detection discipline — still refreshes on
every install even when the skill's body is skipped as consumer-modified
(the lib copy is unconditional, exactly like the importable mirror it
mirrors).

Pattern mirrors ``test_install_skill_lib_callable.py`` (importable-mirror
regression) and the consumer-modified-skip scenarios in
``test_install_hash_upgrade.py`` / ``test_install_lib_hash_upgrade.py``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

# memo ships anvil/skills/memo/lib/render_phase.py, the exact file the
# issue reproduces the bug against.
SRC_RENDER_PHASE = REPO_ROOT / "anvil" / "skills" / "memo" / "lib" / "render_phase.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Invoke the installer with ``args`` and capture text stdout+stderr."""

    return subprocess.run(
        ["bash", str(INSTALLER), *args],
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
    )


def _run_from_fake_anvil(
    fake_anvil: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    """Invoke a copy of the installer rooted at ``fake_anvil``.

    The installer resolves ``ANVIL_ROOT`` from its own path, so a separate
    "fake anvil checkout" is the natural way to simulate "source moved
    forward in a later release" without touching the real checkout under
    test.
    """

    installer = fake_anvil / "scripts" / "install-anvil.sh"
    return subprocess.run(
        ["bash", str(installer), *args],
        capture_output=True,
        text=True,
        cwd=fake_anvil,
    )


def _copy_anvil_checkout(dst: Path) -> Path:
    """Copy the minimum subset of the anvil source tree the installer reads."""

    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "CLAUDE.md", dst / "CLAUDE.md")
    shutil.copytree(REPO_ROOT / "anvil", dst / "anvil")
    (dst / "scripts").mkdir(exist_ok=True)
    shutil.copy(
        REPO_ROOT / "scripts" / "install-anvil.sh",
        dst / "scripts" / "install-anvil.sh",
    )
    return dst


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_fresh_install_populates_documented_lib_path(tmp_path: Path) -> None:
    """A fresh install writes ``.anvil/skills/memo/lib/render_phase.py``.

    This is the exact path the issue's repro invokes and gets "No such
    file or directory" for pre-fix.
    """

    target = tmp_path / "fresh-target"
    target.mkdir()

    result = _run("-y", "--skills=memo", str(target))
    assert result.returncode == 0, (
        f"install failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    documented_path = target / ".anvil" / "skills" / "memo" / "lib" / "render_phase.py"
    assert documented_path.is_file(), (
        f"documented direct-invocation path missing: {documented_path} "
        "(install-anvil.sh Stage 7 should mirror the skill lib/ subdir here "
        "as a sibling of the importable mirror — issue #743)"
    )
    assert documented_path.read_bytes() == SRC_RENDER_PHASE.read_bytes(), (
        "documented-path copy is not byte-identical to source render_phase.py"
    )

    # The importable mirror must ALSO still exist — this is a sibling copy,
    # not a replacement (issue #743 explicitly preserves both).
    importable_mirror = (
        target
        / ".anvil"
        / "anvil"
        / "skills"
        / "memo"
        / "lib"
        / "render_phase.py"
    )
    assert importable_mirror.is_file(), (
        "importable mirror at .anvil/anvil/skills/memo/lib/ regressed — "
        "the #743 fix must be additive, not a relocation"
    )


def test_documented_lib_path_is_directly_invocable(tmp_path: Path) -> None:
    """``python3 .anvil/skills/memo/lib/render_phase.py`` runs, as SKILL.md
    documents it (memo/SKILL.md's lifecycle-wiring invocation, issue #743).
    """

    target = tmp_path / "invoke-target"
    target.mkdir()

    result = _run("-y", "--skills=memo", str(target))
    assert result.returncode == 0, result.stderr

    invoke = subprocess.run(
        [
            "python3",
            ".anvil/skills/memo/lib/render_phase.py",
            "--help",
        ],
        capture_output=True,
        text=True,
        cwd=target,
    )
    assert invoke.returncode == 0, (
        f"documented invocation failed:\n--- stdout ---\n{invoke.stdout}\n"
        f"--- stderr ---\n{invoke.stderr}"
    )


def test_skipped_body_still_refreshes_documented_lib_path(tmp_path: Path) -> None:
    """Consumer-modified skill body is preserved, but the documented lib/
    copy still refreshes — it is unconditional code, not an override
    target (mirrors the importable-mirror carve-out already covered by
    ``test_install_hash_upgrade.py``).
    """

    target = tmp_path / "skip-target"
    target.mkdir()

    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr

    # Consumer hand-edits a body file (NOT under lib/) to force the skip
    # branch on the next install.
    skill_md = target / ".anvil" / "skills" / "memo" / "SKILL.md"
    skill_md.write_text(skill_md.read_text() + "\n<!-- consumer edit -->\n")

    # Source moves forward: both the body (SKILL.md) and the lib module
    # change upstream.
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    src_skill_md = fake_anvil / "anvil" / "skills" / "memo" / "SKILL.md"
    src_skill_md.write_text(src_skill_md.read_text() + "\n<!-- upstream change -->\n")
    src_render_phase = fake_anvil / "anvil" / "skills" / "memo" / "lib" / "render_phase.py"
    src_render_phase.write_text(
        src_render_phase.read_text() + "\n# upstream lib change\n"
    )

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=memo", str(target))
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr
    assert "skipped: consumer-modified .anvil/skills/memo" in combined, (
        f"consumer-modified body did not trigger the skip warning:\n{combined}"
    )

    # Body edit preserved.
    assert "<!-- consumer edit -->" in skill_md.read_text(), (
        "consumer body edit was overwritten despite the skip warning"
    )
    assert "<!-- upstream change -->" not in skill_md.read_text(), (
        "consumer-modified body received the upstream change despite the skip"
    )

    # CARVE-OUT: the documented lib/ path still upgrades.
    documented_path = target / ".anvil" / "skills" / "memo" / "lib" / "render_phase.py"
    assert "# upstream lib change" in documented_path.read_text(), (
        "documented direct-invocation lib/ path was left stale on the "
        "body-skip path — carve-out violated (issue #743)"
    )
