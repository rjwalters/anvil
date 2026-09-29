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

Issue #1320 extends the same contract to the **Stage 11 end-of-install
summary**. #633's per-file warning carries the right data but scrolls past
mid-run; the summary is what a human actually reads, and it used to list
skipped skill NAMES ONLY before closing with an unconditional
``ok: Anvil vX.Y.Z installed``. A run that delivered none of the new skill
bodies therefore read exactly like a run that delivered all of them — the
reported incident being a 0.10.1 → 0.11.6 upgrade that stamped ``0.11.6`` over
a tree where 467 files still differed from source. The
``test_stage11_summary_*`` cases below pin the summary text specifically, and
are deliberately keyed on the summary-only marker ``frozen at`` so they cannot
pass on the strength of the per-file ``last installed:`` warning alone.

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
    shutil.copy(REPO_ROOT / "VERSION", dst / "VERSION")
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
    """Rewrite the fake checkout's VERSION file (and CLAUDE.md, for realism) to ``version``.

    This is how a test simulates "the installing anvil is a newer release than
    the one that laid down the consumer's install" — the installer reads
    ``ANVIL_VERSION`` from the root ``VERSION`` file (issue #894); CLAUDE.md's
    ``**Anvil Version**:`` line is also rewritten to keep the fake checkout
    internally consistent, even though the installer no longer reads it.
    """

    version_file = fake_anvil / "VERSION"
    version_file.write_text(f"{version}\n")

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


def _stage11_section(result: subprocess.CompletedProcess[str]) -> str:
    """Return ONLY the Stage 11 summary portion of an installer run's output.

    Issue #1320's contract is about what the *summary* says, not what the
    per-file skip warning says — and #633 already put ``last installed: vX,
    current: vY`` in the latter. Slicing the output at the ``Stage 11: summary``
    banner is what keeps these assertions from passing on the strength of a
    warning that scrolled past forty lines earlier.
    """

    combined = result.stdout + result.stderr
    marker = "Stage 11: summary"
    idx = combined.find(marker)
    assert idx != -1, f"installer output has no Stage 11 summary banner:\n{combined}"
    return combined[idx:]


def _setup_frozen_skill(
    tmp_path: Path, *, skills: str, modify: tuple[str, ...]
) -> tuple[subprocess.CompletedProcess[str], str, str]:
    """Install, consumer-modify ``modify``, then re-install from a v99 checkout.

    Returns ``(second_run, prior_version, new_version)``. This is the shared
    arrangement behind every Stage 11 summary case: the only way to produce a
    non-empty ``skipped_overrides`` at a *different* version from the running
    installer.
    """

    target = tmp_path / "summary-target"
    target.mkdir()

    first = _run("-y", "--no-sync", f"--skills={skills}", str(target))
    assert first.returncode == 0, first.stderr
    prior_version = _anvil_version()

    for skill in modify:
        _consumer_modify(target, skill)

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil-newer")
    new_version = "99.0.0"
    _set_fake_anvil_version(fake_anvil, new_version)
    for skill in modify:
        _mutate_skill_source(fake_anvil, skill)

    second = _run_from_fake_anvil(
        fake_anvil, "-y", "--no-sync", f"--skills={skills}", str(target)
    )
    assert second.returncode == 0, second.stderr
    return second, prior_version, new_version


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


# ---------------------------------------------------------------------------
# Stage 11 end-of-install summary (issue #1320)
# ---------------------------------------------------------------------------


def test_stage11_summary_names_skipped_skill_and_frozen_version(
    tmp_path: Path,
) -> None:
    """The SUMMARY — not just the per-file warning — names the frozen skill+version.

    This is the core #1320 regression. Every assertion runs against the Stage
    11 slice only, so a run whose summary still said a bare ``memo`` fails here
    even though the #633 per-file warning above it is unchanged and correct.
    """

    second, prior_version, new_version = _setup_frozen_skill(
        tmp_path, skills="memo,deck", modify=("memo",)
    )
    summary = _stage11_section(second)

    assert "memo" in summary, f"summary does not name the skipped skill:\n{summary}"
    assert "frozen at" in summary, (
        "summary still lists skipped skills with no version context — the "
        f"#1320 defect:\n{summary}"
    )
    assert f"frozen at {prior_version}" in summary, (
        f"summary does not say how far behind memo is (expected 'frozen at "
        f"{prior_version}'):\n{summary}"
    )
    assert f"NOT uniformly at v{new_version}" in summary, (
        "summary does not state plainly that the tree is not uniformly at the "
        f"reported version:\n{summary}"
    )
    # deck upgraded cleanly; it must not be reported as frozen.
    assert "deck (frozen at" not in summary, (
        f"an auto-upgraded skill was reported as frozen:\n{summary}"
    )


def test_stage11_final_line_is_qualified_when_skills_are_frozen(
    tmp_path: Path,
) -> None:
    """The closing line never makes an unqualified 'installed' currency claim.

    The pre-#1320 closer was ``ok: Anvil vX.Y.Z installed into <target>`` on
    every successful run, including one that installed no new skill bodies at
    all. A skipped-override run must carry an explicit PARTIAL qualifier while
    still exiting 0 (the skip is correct behavior, not a failure).
    """

    second, _prior, new_version = _setup_frozen_skill(
        tmp_path, skills="memo,deck", modify=("memo",)
    )
    summary = _stage11_section(second)

    assert "PARTIAL" in summary, (
        f"closing line carries no PARTIAL qualifier:\n{summary}"
    )
    assert f"Anvil v{new_version} installed into" not in summary, (
        "closing line still claims an unqualified install at the new version "
        f"while skills are frozen behind it:\n{summary}"
    )
    assert second.returncode == 0, "a skipped-override run must still exit 0"


def test_stage11_summary_clean_install_has_no_frozen_caveat(tmp_path: Path) -> None:
    """A run with nothing skipped keeps the plain, unqualified closing line.

    The caveat must be a property of the skipped-override branch only — a
    fresh install that delivered everything is genuinely uniformly current and
    must not be muddied with a PARTIAL warning.
    """

    target = tmp_path / "clean-target"
    target.mkdir()

    result = _run("-y", "--no-sync", "--skills=memo", str(target))
    assert result.returncode == 0, result.stderr
    summary = _stage11_section(result)

    assert "frozen at" not in summary, (
        f"clean install leaked a frozen-skill caveat:\n{summary}"
    )
    assert "PARTIAL" not in summary, (
        f"clean install leaked a PARTIAL qualifier:\n{summary}"
    )
    assert "NOT uniformly at" not in summary, (
        f"clean install leaked the not-uniformly-current headline:\n{summary}"
    )
    assert f"Anvil v{_anvil_version()} installed into" in summary, (
        f"clean install lost its plain closing line:\n{summary}"
    )


def test_stage11_summary_when_every_skill_is_skipped(tmp_path: Path) -> None:
    """Edge case: nothing was installed this run — say so, and name them all.

    ``help`` is always-on, so ``--skills=memo`` really installs ``memo`` and
    ``help``; modifying both is what produces the all-skipped state.
    """

    second, prior_version, new_version = _setup_frozen_skill(
        tmp_path, skills="memo", modify=("memo", "help")
    )
    summary = _stage11_section(second)

    for skill in ("memo", "help"):
        assert f"{skill} (frozen at {prior_version})" in summary, (
            f"summary does not report {skill} as frozen at {prior_version}:\n{summary}"
        )
    assert "no skill bodies were installed" in summary, (
        "an all-skipped run did not say plainly that nothing was installed:\n"
        f"{summary}"
    )
    assert "2 of 2 skill(s) are pinned" in summary, (
        f"summary does not report the full 2-of-2 frozen count:\n{summary}"
    )
    assert f"Anvil v{new_version} installed into" not in summary, (
        f"an all-skipped run still claims an unqualified install:\n{summary}"
    )


def test_stage11_summary_legacy_manifest_degrades_to_unknown(tmp_path: Path) -> None:
    """Edge case: a pre-#633 manifest yields 'unknown', never a crash or a guess.

    Mirrors ``test_legacy_manifest_no_skill_versions_falls_back_gracefully``
    but asserts on the Stage 11 summary rather than the per-file warning. A
    missing ``skill_versions`` block must not let the summary invent a version
    number, and must not abort the run under ``set -euo pipefail``.
    """

    target = tmp_path / "legacy-summary-target"
    target.mkdir()

    first = _run("-y", "--no-sync", "--skills=deck", str(target))
    assert first.returncode == 0, first.stderr

    manifest_path = target / ".anvil" / "install-metadata.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("skill_versions", None)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    _consumer_modify(target, "deck")

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    _set_fake_anvil_version(fake_anvil, "99.0.0")
    _mutate_skill_source(fake_anvil, "deck")

    second = _run_from_fake_anvil(
        fake_anvil, "-y", "--no-sync", "--skills=deck", str(target)
    )
    assert second.returncode == 0, (
        "installer aborted rendering the Stage 11 summary for a legacy "
        f"manifest:\n--- stdout ---\n{second.stdout}\n--- stderr ---\n{second.stderr}"
    )

    summary = _stage11_section(second)
    assert "deck (frozen at an unknown version)" in summary, (
        "legacy manifest did not degrade to the 'unknown version' wording:\n"
        f"{summary}"
    )
    assert "frozen at 99.0.0" not in summary, (
        "summary invented a frozen version for a skill with no recorded one — "
        f"it must say 'unknown', never the installer-run version:\n{summary}"
    )


def test_stage11_dry_run_summary_uses_conditional_wording(tmp_path: Path) -> None:
    """``--dry-run`` keeps the caveat but states it in the conditional.

    The dry-run-honesty contract (#81) is that the preview describes what a
    real run WOULD do without claiming it happened. The frozen-skill caveat
    inherits that: it appears, with the version context, but phrased as
    ``would NOT be uniformly at``.
    """

    target = tmp_path / "dryrun-target"
    target.mkdir()

    first = _run("-y", "--no-sync", "--skills=deck", str(target))
    assert first.returncode == 0, first.stderr
    prior_version = _anvil_version()

    _consumer_modify(target, "deck")

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil-newer")
    _set_fake_anvil_version(fake_anvil, "99.0.0")
    _mutate_skill_source(fake_anvil, "deck")

    preview = _run_from_fake_anvil(
        fake_anvil, "-y", "--no-sync", "--dry-run", "--skills=deck", str(target)
    )
    assert preview.returncode == 0, preview.stderr

    summary = _stage11_section(preview)
    assert f"would skip:          deck (frozen at {prior_version})" in summary, (
        f"dry-run 'would skip:' line lost its version context:\n{summary}"
    )
    assert "would NOT be uniformly at v99.0.0" in summary, (
        f"dry-run caveat is missing or not in the conditional:\n{summary}"
    )
    assert "is NOT uniformly at" not in summary, (
        f"dry-run caveat used the indicative, claiming a state it did not create:\n{summary}"
    )
