"""Regression tests: installer emits a Codex-side registration shim (#1003).

Part of the #1000 epic ("Make Anvil artifact skills discoverable in Claude
and Codex"). #1002 verified Codex CLI's actual skill-discovery contract
(``docs/codex-skill-adapter.md``): Codex scans a repo-root ``.agents/skills``
directory for ``<name>/SKILL.md`` files, no wrapping plugin manifest is
required for discovery, and ``.codex/skills/`` is NOT part of the documented
contract.

This issue adds ``write_codex_shim()`` in ``scripts/install-anvil.sh``,
structured in parallel to the existing ``write_shim()`` (the Claude
counterpart, pinned by ``test_install_shim_depth.py``): same ``anvil-<name>``
naming, same thin-pointer content pattern, wired into the same three call
sites (happy-path install, and both "consumer-modified, skip body but
refresh shim" branches), with a matching Stage 7.6 stale-shim cleanup pass
for skills removed from the registry since the last install.

These tests exercise the installer via ``subprocess`` at the real entry
point, mirroring the patterns in ``test_install_shim_depth.py`` (basic
shape) and ``test_install_skill_removal_prune.py`` (removal parity). Distinct
filename per the #58 packaging convention.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the installer non-interactively and capture text stdout+stderr.

    ``--no-sync`` keeps the tests independent of uv availability and fast.
    """

    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _run_dry(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the installer in ``--dry-run`` mode (no ``-y`` needed)."""

    return subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--no-sync", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"installer exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def _manifest_path(target: Path) -> Path:
    return target / ".anvil" / "install-metadata.json"


def _read_installed_skills(target: Path) -> list[str]:
    data = json.loads(_manifest_path(target).read_text(encoding="utf-8"))
    return list(data.get("installed_skills", []))


# ---------------------------------------------------------------------------
# Basic shape: the shim exists, at the verified path, pointing at the body
# ---------------------------------------------------------------------------


def test_codex_shim_written_at_verified_path(tmp_path: Path) -> None:
    """The Codex shim lands at ``.agents/skills/anvil-<skill>/SKILL.md``.

    This is the repo-root scan path #1002 verified against
    ``https://developers.openai.com/codex/build-skills`` -- NOT
    ``.codex/skills/``, which is not part of the documented contract.
    """

    target = tmp_path / "codex-shim-target"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    expected_shim = target / ".agents" / "skills" / "anvil-memo" / "SKILL.md"
    assert expected_shim.is_file(), (
        f"expected Codex shim at {expected_shim} -- not found.\n"
        f"Tree under .agents/skills/:\n"
        + "\n".join(
            f"  {p.relative_to(target)}"
            for p in (target / ".agents" / "skills").rglob("*")
        )
    )

    # Must NOT be written under the unverified .codex/skills/ hypothesis.
    unverified_path = target / ".codex" / "skills" / "anvil-memo" / "SKILL.md"
    assert not unverified_path.exists(), (
        f"Codex shim written at the unverified {unverified_path} path; "
        "the verified contract (#1002) is .agents/skills/, not .codex/skills/."
    )


def test_codex_shim_points_at_canonical_body_not_a_copy(tmp_path: Path) -> None:
    """The shim is a thin pointer -- it never duplicates the skill body."""

    target = tmp_path / "codex-shim-pointer-target"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    shim = target / ".agents" / "skills" / "anvil-memo" / "SKILL.md"
    body = shim.read_text(encoding="utf-8")

    assert "name: anvil-memo" in body, f"shim missing frontmatter name: {body}"
    assert ".anvil/skills/memo/SKILL.md" in body, (
        f"shim does not point back at the canonical body: {body}"
    )
    # The shim is tiny -- a pointer, not a copy of the full skill body.
    canonical = target / ".anvil" / "skills" / "memo" / "SKILL.md"
    assert canonical.is_file()
    assert len(body) < len(canonical.read_text(encoding="utf-8")), (
        "Codex shim is not a thin pointer -- it appears to duplicate the "
        "canonical skill body"
    )


def test_codex_shim_no_wrapping_plugin_manifest(tmp_path: Path) -> None:
    """No ``.codex-plugin/plugin.json`` is emitted in the v1 adapter (#1002 AC4)."""

    target = tmp_path / "codex-shim-no-plugin-target"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    assert not (target / ".codex-plugin").exists(), (
        "installer wrote a .codex-plugin/ manifest; #1002 confirmed one is "
        "not required for skill discovery"
    )


# ---------------------------------------------------------------------------
# --skills= filtering: only selected skills get a Codex registration
# ---------------------------------------------------------------------------


def test_skills_filter_scopes_codex_shims(tmp_path: Path) -> None:
    """Only the ``--skills=`` selected skills receive a Codex shim."""

    target = tmp_path / "codex-shim-filter-target"
    target.mkdir()

    result = _run("--skills=memo,paper", str(target))
    _assert_ok(result)

    codex_skills_dir = target / ".agents" / "skills"
    installed = {p.name for p in codex_skills_dir.iterdir() if p.is_dir()}

    assert "anvil-memo" in installed
    assert "anvil-paper" in installed
    # `help` is an always-on utility skill (see test_install_always_on_help.py)
    # so its presence alongside a --skills= subset is expected; assert the
    # unselected artifact-class skills are absent instead of asserting an
    # exact set.
    assert "anvil-deck" not in installed, (
        f"unselected skill 'deck' unexpectedly got a Codex shim: {installed}"
    )
    assert "anvil-report" not in installed, (
        f"unselected skill 'report' unexpectedly got a Codex shim: {installed}"
    )


# ---------------------------------------------------------------------------
# --dry-run: planned Codex-shim writes are printed, nothing is written
# ---------------------------------------------------------------------------


def test_dry_run_lists_planned_codex_shim_writes(tmp_path: Path) -> None:
    """``--dry-run`` previews the Codex shim write and touches no disk."""

    target = tmp_path / "codex-shim-dryrun-target"
    target.mkdir()

    result = _run_dry("--skills=memo", str(target))
    _assert_ok(result)

    assert ".agents/skills/anvil-memo/SKILL.md" in result.stdout, (
        f"dry-run output does not advertise the planned Codex shim write; "
        f"got:\n{result.stdout}"
    )
    assert not (target / ".agents").exists(), (
        "--dry-run wrote .agents/ to disk despite the dry-run flag"
    )


# ---------------------------------------------------------------------------
# Stale-shim cleanup: a skill removed from the registry loses both runtimes'
# shims on the next reconciling install (Stage 7.6, issue #716's mechanism).
# ---------------------------------------------------------------------------


def _inject_removed_skill(target: Path, name: str) -> None:
    """Simulate a prior install that shipped ``name``, now removed upstream.

    Mirrors ``test_install_skill_removal_prune.py``'s helper, scoped to the
    two families this test cares about (Claude + Codex shims), plus the
    manifest entry that makes the removal provenance-checked.
    """

    manifest = _manifest_path(target)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if name not in data["installed_skills"]:
        data["installed_skills"].append(name)
    manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    claude_shim = target / ".claude" / "skills" / f"anvil-{name}"
    claude_shim.mkdir(parents=True, exist_ok=True)
    (claude_shim / "SKILL.md").write_text(f"claude shim for {name}\n")

    codex_shim = target / ".agents" / "skills" / f"anvil-{name}"
    codex_shim.mkdir(parents=True, exist_ok=True)
    (codex_shim / "SKILL.md").write_text(f"codex shim for {name}\n")


def test_removed_skill_prune_cleans_up_codex_shim_too(tmp_path: Path) -> None:
    """A skill removed from the registry loses its Codex shim on reinstall.

    This is the Codex-side analog of
    ``test_install_skill_removal_prune.py::test_full_install_prunes_removed_skill_all_four_families``
    -- Stage 7.6 now removes five path families, not four; this test pins
    the fifth (the Codex shim) without duplicating the whole suite.
    """

    target = tmp_path / "codex-shim-prune-target"
    target.mkdir()

    _assert_ok(_run("--skills=memo", str(target)))
    _inject_removed_skill(target, "fake-removed-skill")

    codex_shim = target / ".agents" / "skills" / "anvil-fake-removed-skill"
    claude_shim = target / ".claude" / "skills" / "anvil-fake-removed-skill"
    assert codex_shim.exists() and claude_shim.exists()

    result = _run(str(target))  # full/default reinstall — reconciles
    _assert_ok(result)

    assert not codex_shim.exists(), (
        "Codex shim for a registry-removed skill survived the Stage 7.6 prune"
    )
    assert not claude_shim.exists(), (
        "Claude shim for a registry-removed skill survived the Stage 7.6 prune"
    )
    assert "fake-removed-skill" not in _read_installed_skills(target)
    assert "all five path families removed" in result.stdout, (
        f"expected the Stage 7.6 note to count five path families; got:\n"
        f"{result.stdout}"
    )


def test_dry_run_removed_skill_codex_shim_survives(tmp_path: Path) -> None:
    """``--dry-run`` previews the Codex-shim removal but writes nothing."""

    target = tmp_path / "codex-shim-prune-dryrun-target"
    target.mkdir()

    _assert_ok(_run("--skills=memo", str(target)))
    _inject_removed_skill(target, "fake-removed-skill")

    codex_shim = target / ".agents" / "skills" / "anvil-fake-removed-skill"
    assert codex_shim.exists()

    result = _run_dry(str(target))
    _assert_ok(result)

    assert codex_shim.exists(), "--dry-run actually removed the Codex shim from disk"
    assert ".agents/skills/anvil-fake-removed-skill/" in result.stdout, (
        f"dry-run plan did not mention the Codex shim path; got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Consumer-modified skill body: shim still regenerates (matches Claude path)
# ---------------------------------------------------------------------------


def test_codex_shim_regenerates_on_consumer_modified_skip(tmp_path: Path) -> None:
    """Even when a skill body is skipped as consumer-modified, both shims refresh.

    Mirrors the existing Claude-side contract: ``write_shim()`` (and now
    ``write_codex_shim()``) is called from the override-skip branches too,
    so a consumer's hand-edited skill body is preserved while the thin
    registration shim -- installer-owned, never a consumer-override target --
    still regenerates on every run.
    """

    target = tmp_path / "codex-shim-override-skip-target"
    target.mkdir()

    _assert_ok(_run("--skills=memo", str(target)))

    # Simulate a legacy install with no recorded hash: hand-edit the skill
    # body so the next run treats it as consumer-modified and takes the
    # override-skip branch.
    (target / ".anvil" / "skills" / "memo" / "SKILL.md").write_text(
        "hand-edited by consumer\n", encoding="utf-8"
    )
    manifest = _manifest_path(target)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data.pop("skill_hashes", None)
    manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    codex_shim = target / ".agents" / "skills" / "anvil-memo" / "SKILL.md"
    assert codex_shim.is_file()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    assert "skipped: consumer-modified" in result.stdout, (
        f"expected the override-skip branch to fire; got:\n{result.stdout}"
    )
    assert codex_shim.is_file(), (
        "Codex shim was not regenerated on the consumer-modified-skip branch"
    )
    assert (target / ".anvil" / "skills" / "memo" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "hand-edited by consumer\n", (
        "consumer's hand-edited skill body was overwritten"
    )
