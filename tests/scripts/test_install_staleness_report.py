"""Regression test: per-skill ``skill_versions`` staleness surface for skips.

Issue #633 (deferred remedy 2 of #618): ``install-anvil.sh`` skip-on-consumer-
modified operates at whole-skill granularity. When a skill lands in
``skipped_overrides`` the installer preserves the consumer's copy — but nothing
surfaced *how far behind* that frozen copy was. The top-level ``anvil_version``
scalar records only the LAST installer run; it is overwritten every run, so a
skill last actually installed several releases earlier loses its install
provenance the moment a newer installer touches the repo.

The fix records a per-skill ``skill_versions`` object in the manifest, parallel
to the existing ``skill_hashes`` object: ``skill_versions.<name>`` is the
``anvil_version`` of the run that last ACTUALLY installed that skill's body. On
a skip run the prior value is carried forward (never overwritten with the new
version, never dropped), and the two ``SKIPPED_OVERRIDES+=`` skip warnings are
enriched to read ``last installed: vX, current: vY``.

These tests exercise the installer via ``subprocess`` so the contract is
enforced at the real entry point a consumer hits. The helper shape
(``_run`` / ``_run_from_fake_anvil`` / ``_copy_anvil_checkout`` /
``_read_manifest``) mirrors ``test_install_hash_upgrade.py``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

# The installer extracts this exact pattern from CLAUDE.md; mirror it so the
# test's notion of "current version" matches the installer's.
_VERSION_RE = re.compile(r"Anvil Version\*\*:\s*([0-9]+\.[0-9]+\.[0-9]+)")


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

    The installer resolves ``ANVIL_ROOT`` (and ``ANVIL_VERSION`` from that
    checkout's ``CLAUDE.md``) from its own path, so a separate "fake anvil
    checkout" is the natural way to simulate "anvil shipped a newer release"
    without touching the real checkout under test.
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


def _read_manifest(target: Path) -> dict:
    manifest_path = target / ".anvil" / "install-metadata.json"
    assert manifest_path.is_file(), (
        f"manifest not found at {manifest_path}; install did not write it"
    )
    return json.loads(manifest_path.read_text())


def _anvil_version(checkout: Path = REPO_ROOT) -> str:
    """Extract the Anvil version the same way the installer does."""

    match = _VERSION_RE.search((checkout / "CLAUDE.md").read_text())
    assert match, f"could not extract Anvil version from {checkout}/CLAUDE.md"
    return match.group(1)


def _set_fake_anvil_version(fake_anvil: Path, version: str) -> None:
    """Rewrite the fake checkout's CLAUDE.md version line to ``version``.

    This is how a test simulates "the installing anvil is a newer release than
    the one that laid down the consumer's install" — the installer reads
    ``ANVIL_VERSION`` from this exact line.
    """

    claude = fake_anvil / "CLAUDE.md"
    text = claude.read_text()
    new_text = re.sub(
        r"(Anvil Version\*\*:\s*)[0-9]+\.[0-9]+\.[0-9]+",
        rf"\g<1>{version}",
        text,
        count=1,
    )
    assert new_text != text, "failed to rewrite the fake anvil version line"
    claude.write_text(new_text)


def _mutate_skill_source(checkout: Path, skill: str) -> None:
    """Append a line to a skill's SKILL.md in ``checkout`` (source moved forward)."""

    src = checkout / "anvil" / "skills" / skill / "SKILL.md"
    src.write_text(src.read_text() + "\n<!-- upstream edit -->\n")


def _consumer_modify(target: Path, skill: str) -> None:
    """Append a line to an installed skill's SKILL.md (consumer edit)."""

    dst = target / ".anvil" / "skills" / skill / "SKILL.md"
    assert dst.is_file()
    dst.write_text(dst.read_text() + "\n<!-- consumer edit -->\n")


# ---------------------------------------------------------------------------
# Test cases (per curator test plan)
# ---------------------------------------------------------------------------


def test_fresh_install_records_skill_versions(tmp_path: Path) -> None:
    """Fresh ``--skills=memo,deck`` install populates ``skill_versions`` for both.

    The field is the precondition for every staleness-report branch: without it
    recorded on first install, a later skip run has nothing to carry forward.
    """

    target = tmp_path / "fresh-target"
    target.mkdir()

    result = _run("-y", "--skills=memo,deck", str(target))
    assert result.returncode == 0, (
        f"install failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    manifest = _read_manifest(target)
    assert "skill_versions" in manifest, (
        f"manifest missing 'skill_versions' block:\n{manifest}"
    )
    current = _anvil_version()
    for skill in ("memo", "deck"):
        assert skill in manifest["skill_versions"], (
            f"'skill_versions' missing '{skill}' entry:\n"
            f"{manifest['skill_versions']}"
        )
        recorded = manifest["skill_versions"][skill]
        assert recorded == current, (
            f"skill_versions[{skill!r}] is {recorded!r}, expected the install "
            f"version {current!r}; the field is not populated with ANVIL_VERSION"
        )
        assert recorded, f"skill_versions[{skill!r}] is empty on fresh install"


def test_skip_warn_contains_prior_and_current_version(tmp_path: Path) -> None:
    """Consumer-modified skip warn names BOTH the prior and the current version.

    Fresh-install deck (records ``skill_versions.deck = V1``), consumer-modify
    it, then upgrade from a fake anvil checkout whose version is bumped to V2.
    The skip warn line must surface the staleness: both V1 and V2 appear.
    """

    target = tmp_path / "warn-target"
    target.mkdir()

    first = _run("-y", "--skills=deck", str(target))
    assert first.returncode == 0, first.stderr
    prior_version = _anvil_version()

    _consumer_modify(target, "deck")

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil-newer")
    new_version = "99.0.0"
    _set_fake_anvil_version(fake_anvil, new_version)
    # Move the deck source forward too, so the scenario is a realistic upgrade
    # (source differs from dst independent of the consumer edit).
    _mutate_skill_source(fake_anvil, "deck")

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=deck", str(target))
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr
    assert "skipped: consumer-modified .anvil/skills/deck" in combined, (
        f"deck was not skipped as consumer-modified:\n{combined}"
    )
    assert "last installed:" in combined, (
        f"skip warn did not surface a 'last installed:' staleness line:\n{combined}"
    )
    assert prior_version in combined, (
        f"skip warn did not name the prior install version {prior_version!r}:\n"
        f"{combined}"
    )
    assert new_version in combined, (
        f"skip warn did not name the current install version {new_version!r}:\n"
        f"{combined}"
    )


def test_skip_carries_forward_skill_version_in_manifest(tmp_path: Path) -> None:
    """A skipped skill keeps its ORIGINAL install version in the new manifest.

    The carry-forward rule is what keeps the staleness baseline correct across
    runs: ``skill_versions.deck`` must equal the version recorded at first
    install — never ``""``, never the new installer's version, never dropped.
    """

    target = tmp_path / "carry-target"
    target.mkdir()

    first = _run("-y", "--skills=deck", str(target))
    assert first.returncode == 0, first.stderr
    original_version = _anvil_version()
    assert _read_manifest(target)["skill_versions"]["deck"] == original_version

    _consumer_modify(target, "deck")

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil-newer")
    _set_fake_anvil_version(fake_anvil, "99.0.0")
    _mutate_skill_source(fake_anvil, "deck")

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=deck", str(target))
    assert second.returncode == 0, second.stderr

    manifest = _read_manifest(target)
    assert "deck" in manifest["skipped_overrides"], (
        f"deck was not skipped:\n{manifest}"
    )
    carried = manifest["skill_versions"].get("deck")
    assert carried == original_version, (
        f"skill_versions[deck] is {carried!r} after skip; expected the "
        f"carried-forward original {original_version!r} (not the new installer's "
        f"99.0.0, not dropped, not empty). Manifest:\n{manifest}"
    )


def test_no_skip_upgrade_produces_no_staleness_in_warn(tmp_path: Path) -> None:
    """The auto-upgrade path emits NO 'last installed:' line.

    The staleness line is a property of the skipped-override branch only. An
    unmodified skill whose source moved forward auto-upgrades cleanly; the
    combined output must not contain the staleness marker for it.
    """

    target = tmp_path / "noskip-target"
    target.mkdir()

    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr

    # Source moves forward but the consumer never touched the install → the
    # recorded hash still matches the dst, so Stage 7 takes the auto-upgrade
    # branch, not a skip.
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil-newer")
    _set_fake_anvil_version(fake_anvil, "99.0.0")
    _mutate_skill_source(fake_anvil, "memo")

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=memo", str(target))
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr
    assert "unmodified-since-install" in combined, (
        f"memo did not take the auto-upgrade branch:\n{combined}"
    )
    assert "skipped: consumer-modified" not in combined, (
        f"memo was incorrectly skipped:\n{combined}"
    )
    assert "last installed:" not in combined, (
        "auto-upgrade path leaked a 'last installed:' staleness line — it must "
        f"appear only for skipped-override skills:\n{combined}"
    )

    # The as-installed version was refreshed to the new installer's version.
    manifest = _read_manifest(target)
    assert manifest["skill_versions"]["memo"] == "99.0.0", (
        f"memo version was not refreshed on auto-upgrade:\n{manifest}"
    )


def test_legacy_manifest_no_skill_versions_falls_back_gracefully(
    tmp_path: Path,
) -> None:
    """A manifest without ``skill_versions`` degrades to 'last installed: unknown'.

    Simulates a pre-#633 consumer install: the ``skill_versions`` block is
    absent. On a consumer-modified skip the installer must NOT abort (no
    pipefail trap in ``read_recorded_version``) and must print
    ``last installed: unknown`` so the operator still sees the current version
    context even without a recorded baseline.
    """

    target = tmp_path / "legacy-target"
    target.mkdir()

    first = _run("-y", "--skills=deck", str(target))
    assert first.returncode == 0, first.stderr

    # Degrade the manifest to a pre-#633 shape: drop skill_versions, keep
    # skill_hashes so the skip routes through the consumer-modified branch
    # (recorded hash present but != the consumer-edited dst).
    manifest_path = target / ".anvil" / "install-metadata.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("skill_versions", None)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    assert "skill_versions" not in json.loads(manifest_path.read_text())

    _consumer_modify(target, "deck")

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    _mutate_skill_source(fake_anvil, "deck")

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=deck", str(target))
    assert second.returncode == 0, (
        "installer aborted on a legacy manifest with no skill_versions block "
        f"(read_recorded_version must return '' cleanly):\n"
        f"--- stdout ---\n{second.stdout}\n--- stderr ---\n{second.stderr}"
    )

    combined = second.stdout + second.stderr
    assert "skipped: consumer-modified .anvil/skills/deck" in combined, (
        f"deck was not skipped as consumer-modified:\n{combined}"
    )
    assert "last installed: unknown" in combined, (
        "legacy-manifest skip did not fall back to 'last installed: unknown' "
        f"for the absent skill_versions block:\n{combined}"
    )

    # Stage 9 still ran and re-established a skill_versions block, carrying the
    # (now-unknown) deck forward as absent — the next install re-baselines on a
    # --force. The block itself must exist so future installs parse cleanly.
    final = _read_manifest(target)
    assert "skill_versions" in final, (
        f"installer did not re-write a skill_versions block:\n{final}"
    )
