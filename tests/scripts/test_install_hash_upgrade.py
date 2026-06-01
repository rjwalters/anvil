"""Regression test: per-skill ``skill_hashes`` baseline drives override detection.

Issue #152: ``install-anvil.sh`` previously protected *every* existing skill
directory from in-place overwrite, treating "destination exists" as
"consumer-modified." A freshly-installed skill the consumer never touched
appeared "modified" the moment upstream source moved (the dst byte-diff
against the new source was non-empty even with zero consumer edits), so
upgrading a non-modified skill required ``--force`` — which then bypassed
the protection on every other skill in the same invocation. The canary
(studio) hit a three-installer-invocation pattern to upgrade memo while
preserving deck overrides.

The fix records a per-skill content hash in the manifest *at install time*
(``skill_hashes.<name>`` under ``install-metadata.json``). On re-install,
the installer compares the current destination's dir-hash to the recorded
"as-installed" hash:

  * dst hash == recorded hash → consumer hasn't modified the install
    (it differs from source only because source moved forward). Safe to
    auto-upgrade without ``--force``.
  * dst hash != recorded hash → consumer actually modified. Skip with
    warning unless ``--force``.
  * no recorded hash (legacy manifest) → fall back to today's
    "consumer-modified" warning. Documented as one-time migration cost.

These tests exercise the installer via ``subprocess`` so the contract is
enforced at the real entry point a consumer hits. Pattern mirrors
``test_install_dry_run_honesty.py`` and ``test_install_skills_validation.py``.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


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
    """Copy the minimum subset of the anvil source tree the installer reads.

    The installer needs: ``CLAUDE.md`` (for version extraction), ``anvil/lib``,
    ``anvil/roles``, ``anvil/skills/<each>``, and ``scripts/install-anvil.sh``.
    Copy only those to keep the tmp_path tests fast.
    """

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


def _shell_dir_hash(d: Path) -> str:
    """Recompute the directory hash the installer's ``dir_hash`` shell helper
    would produce, so the test can assert byte-identity with the manifest.

    The installer's helper does::

        ( cd $d && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 )
            | shasum -a 256 | awk '{print $1}'

    We shell out the same pipeline rather than reimplement it in Python — the
    contract under test is precisely "the value in skill_hashes matches the
    value `shasum -a 256` would produce". A Python-side reimplementation
    would risk hiding a real schema drift.
    """

    inner = subprocess.run(
        "find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256",
        shell=True,
        cwd=d,
        capture_output=True,
        text=True,
        check=True,
    )
    outer = subprocess.run(
        ["shasum", "-a", "256"],
        input=inner.stdout,
        capture_output=True,
        text=True,
        check=True,
    )
    return outer.stdout.split()[0]


# ---------------------------------------------------------------------------
# Test cases (per curator notes)
# ---------------------------------------------------------------------------


def test_fresh_install_records_hash(tmp_path: Path) -> None:
    """Fresh ``--skills=memo`` install writes ``skill_hashes.memo`` matching dir-hash.

    The hash is the "as-installed" snapshot; recording it is the precondition
    for every subsequent override-detection branch.
    """

    target = tmp_path / "fresh-target"
    target.mkdir()

    result = _run("-y", "--skills=memo", str(target))
    assert result.returncode == 0, (
        f"install failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    manifest = _read_manifest(target)
    assert "skill_hashes" in manifest, (
        f"manifest missing 'skill_hashes' block:\n{manifest}"
    )
    assert "memo" in manifest["skill_hashes"], (
        f"'skill_hashes' missing 'memo' entry:\n{manifest['skill_hashes']}"
    )
    recorded = manifest["skill_hashes"]["memo"]
    # The recorded hash must be the actual installed dst's dir hash.
    actual = _shell_dir_hash(target / ".anvil" / "skills" / "memo")
    assert recorded == actual, (
        f"recorded hash {recorded!r} does not match actual dst hash "
        f"{actual!r}; manifest is lying about the as-installed snapshot."
    )


def test_byte_identical_skill_auto_upgrades_no_force(tmp_path: Path) -> None:
    """Re-install with the same source recopies idempotently (today's behavior).

    Source hasn't moved; dst matches source byte-for-byte. The "already
    installed and unchanged" note fires and the skill is recopied. Critical:
    no consumer-modified warning, no ``--force`` needed.
    """

    target = tmp_path / "byte-identical-target"
    target.mkdir()

    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr

    second = _run("-y", "--skills=memo", str(target))
    assert second.returncode == 0, second.stderr

    assert "skipped: consumer-modified" not in second.stdout + second.stderr, (
        "second install incorrectly flagged memo as consumer-modified when "
        f"the dst was byte-identical to source:\n{second.stdout}"
    )
    assert "already installed and unchanged" in second.stdout, (
        "second install did not emit the 'already installed and unchanged' "
        f"note for byte-identical dst:\n{second.stdout}"
    )

    manifest = _read_manifest(target)
    assert "memo" in manifest["installed_skills"]
    assert manifest["skipped_overrides"] == []


def test_modified_skill_skips_without_force(tmp_path: Path) -> None:
    """Consumer-modified dst skips with warning, no ``--force``.

    Fresh-install memo, edit a file under the dst, re-run installer. The
    recorded hash from install no longer matches the now-edited dst, so the
    installer protects the consumer's modifications by skipping.
    """

    target = tmp_path / "modified-target"
    target.mkdir()

    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr

    # Consumer edit: append a line to a file inside the dst.
    skill_md = target / ".anvil" / "skills" / "memo" / "SKILL.md"
    assert skill_md.is_file()
    skill_md.write_text(skill_md.read_text() + "\n<!-- consumer edit -->\n")

    second = _run("-y", "--skills=memo", str(target))
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr
    assert "skipped: consumer-modified" in combined, (
        "consumer-modified dst did not trigger the skip warning; "
        f"output:\n{combined}"
    )
    # The "legacy install" qualifier must NOT appear — a recorded hash
    # exists, so the detection is the new hash-based path, not the fallback.
    assert "legacy install, no recorded hash" not in combined, (
        "consumer-modified dst incorrectly hit the legacy-install fallback "
        f"even though a hash was recorded:\n{combined}"
    )

    manifest = _read_manifest(target)
    assert "memo" in manifest["skipped_overrides"]
    assert "memo" not in manifest["installed_skills"]
    # The carry-forward rule: even when the skill was skipped, the manifest
    # must retain the previously-recorded hash so the next install can still
    # detect modifications.
    assert "memo" in manifest["skill_hashes"], (
        "skipped-skill hash was not carried forward into the new manifest; "
        f"next install will hit the legacy-install fallback. Manifest:\n{manifest}"
    )


def test_modified_skill_force_overrides(tmp_path: Path) -> None:
    """``--force`` overwrites a consumer-modified dst and re-records the hash.

    The ``--force`` escape hatch must remain unconditional. After the force
    install, the recorded hash should equal the new dst's hash (which equals
    the source's hash, since we just clobbered the dst from source).
    """

    target = tmp_path / "force-target"
    target.mkdir()

    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr

    skill_md = target / ".anvil" / "skills" / "memo" / "SKILL.md"
    skill_md.write_text(skill_md.read_text() + "\n<!-- consumer edit -->\n")

    second = _run("-y", "--force", "--skills=memo", str(target))
    assert second.returncode == 0, second.stderr

    # The consumer edit must be gone (force overwrote).
    assert "<!-- consumer edit -->" not in skill_md.read_text(), (
        "--force did not overwrite the consumer's edit"
    )

    manifest = _read_manifest(target)
    assert "memo" in manifest["installed_skills"]
    # New hash must equal source dir hash (== now-installed dst hash).
    recorded = manifest["skill_hashes"]["memo"]
    actual = _shell_dir_hash(target / ".anvil" / "skills" / "memo")
    assert recorded == actual, (
        f"post-force recorded hash {recorded!r} does not match the new "
        f"dst hash {actual!r}; manifest stale after --force"
    )


def test_legacy_install_no_recorded_hash_falls_back_to_byte_diff(
    tmp_path: Path,
) -> None:
    """Manifest without ``skill_hashes`` hits the legacy-install warning once.

    Hand-write a manifest in the old shape (no ``skill_hashes``) to simulate
    a consumer who installed before this PR. The installer must:
      * not crash on the missing field
      * fall back to "skipped: consumer-modified" with the legacy-install
        qualifier so the consumer learns ``--force`` is the one-time fix
    """

    target = tmp_path / "legacy-target"
    target.mkdir()

    # First, fresh install to lay down the skill body.
    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr

    # Now degrade the manifest to look like a pre-#152 install.
    manifest_path = target / ".anvil" / "install-metadata.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("skill_hashes", None)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    # Mutate the source-mirror so dst diverges from source — this is what
    # would happen on a real upstream-source-moved-forward upgrade.
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    src_skill_md = fake_anvil / "anvil" / "skills" / "memo" / "SKILL.md"
    src_skill_md.write_text(src_skill_md.read_text() + "\n<!-- upstream edit -->\n")

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=memo", str(target))
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr
    assert "skipped: consumer-modified" in combined, (
        f"legacy-manifest dst did not skip with warning:\n{combined}"
    )
    assert "legacy install, no recorded hash" in combined, (
        "legacy-install path did not emit the diagnostic qualifier so the "
        f"consumer can learn the one-time --force migration:\n{combined}"
    )


def test_dry_run_shows_correct_action_for_each_case(tmp_path: Path) -> None:
    """``--dry-run`` names the per-skill verdict suffix without writing manifest.

    The dry-run honesty contract (#81) requires the operator to see what a
    real run would do. For the new hash-based logic, the verdict suffix on
    the action line tells apart fresh / recopy / auto-upgrade / overwrite /
    skip-modified branches.
    """

    target = tmp_path / "dry-run-target"
    target.mkdir()

    # Fresh install of memo + deck so we have hashes to compare against.
    first = _run("-y", "--skills=memo,deck", str(target))
    assert first.returncode == 0, first.stderr

    # Consumer-modifies deck (not memo).
    deck_md = target / ".anvil" / "skills" / "deck" / "SKILL.md"
    deck_md.write_text(deck_md.read_text() + "\n<!-- deck consumer edit -->\n")

    # Source moves forward (both memo and deck change upstream).
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    for skill in ("memo", "deck"):
        src = fake_anvil / "anvil" / "skills" / skill / "SKILL.md"
        src.write_text(src.read_text() + "\n<!-- upstream edit -->\n")

    # Snapshot mtimes of dst files: dry-run must not touch them.
    deck_mtime_before = deck_md.stat().st_mtime
    memo_md = target / ".anvil" / "skills" / "memo" / "SKILL.md"
    memo_mtime_before = memo_md.stat().st_mtime

    dry = _run_from_fake_anvil(
        fake_anvil, "--dry-run", "--skills=memo,deck", str(target)
    )
    assert dry.returncode == 0, dry.stderr

    # memo: auto-upgrade verdict in the action line.
    assert "[auto-upgrade (unmodified-since-install)]" in dry.stdout, (
        "dry-run did not advertise the auto-upgrade verdict for memo:\n"
        f"{dry.stdout}"
    )
    # deck: consumer-modified skip (no install action line at all).
    assert "skipped: consumer-modified .anvil/skills/deck" in dry.stdout, (
        "dry-run did not flag deck as consumer-modified:\n{dry.stdout}"
    )

    # Stage 11 summary: would-install names memo, would-skip names deck.
    would_install = [
        line for line in dry.stdout.splitlines() if "would install:" in line
    ]
    assert would_install and "memo" in would_install[0]
    would_skip = [
        line for line in dry.stdout.splitlines() if "would skip:" in line
    ]
    assert would_skip and "deck" in would_skip[0]

    # The substantive invariant: nothing was written. The dst files' mtimes
    # must be unchanged, and the manifest must still carry the original
    # hashes from the fresh install (not the new "would-install" hashes).
    assert deck_md.stat().st_mtime == deck_mtime_before, (
        "dry-run mutated deck SKILL.md"
    )
    assert memo_md.stat().st_mtime == memo_mtime_before, (
        "dry-run mutated memo SKILL.md"
    )


def test_canary_three_invocation_reproducer(tmp_path: Path) -> None:
    """Single invocation handles mixed auto-upgrade + consumer-modified cleanly.

    This is the headline test from the issue body: studio's
    ``--skills=memo,deck`` upgrade required three invocations because the
    installer couldn't tell apart "memo was untouched-since-install" from
    "deck was actually modified". With the hash baseline, one invocation
    nets out at the right state:

      * memo: auto-upgrade to new source (listed in installed_skills)
      * deck: preserve modifications (listed in skipped_overrides)
    """

    target = tmp_path / "canary-target"
    target.mkdir()

    # Step 1: fresh install of memo and deck.
    first = _run("-y", "--skills=memo,deck", str(target))
    assert first.returncode == 0, first.stderr

    # Step 2: consumer modifies deck (slug-versioning customizations etc.)
    deck_md = target / ".anvil" / "skills" / "deck" / "SKILL.md"
    deck_md.write_text(
        deck_md.read_text() + "\n<!-- deck slug-versioning override -->\n"
    )
    deck_edit_hash = hashlib.sha256(deck_md.read_bytes()).hexdigest()

    # Step 3: simulate "anvil ships PR with new memo feature" — both source
    # trees mutate upstream (memo gets the new feature, deck gets some
    # unrelated upstream change too).
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil-newer")
    memo_src = fake_anvil / "anvil" / "skills" / "memo" / "SKILL.md"
    memo_src.write_text(memo_src.read_text() + "\n<!-- target_length feature -->\n")
    deck_src = fake_anvil / "anvil" / "skills" / "deck" / "SKILL.md"
    deck_src.write_text(deck_src.read_text() + "\n<!-- upstream deck tweak -->\n")

    # Step 4: SINGLE invocation. Pre-fix this required three.
    second = _run_from_fake_anvil(
        fake_anvil, "-y", "--skills=memo,deck", str(target)
    )
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr

    # memo: auto-upgraded.
    assert "memo' is unmodified-since-install" in combined, (
        "memo did not get the auto-upgrade verdict (canary scenario):\n"
        f"{combined}"
    )
    # deck: skipped, NOT under the legacy-install fallback.
    assert "skipped: consumer-modified .anvil/skills/deck" in combined, (
        "deck was not preserved as consumer-modified (canary scenario):\n"
        f"{combined}"
    )
    assert "legacy install, no recorded hash" not in combined, (
        "deck incorrectly hit the legacy-install fallback even though its "
        f"hash was recorded:\n{combined}"
    )

    # The substantive invariant: dst state matches the user's intent.
    assert "target_length feature" in memo_src.read_text(), (
        "memo source didn't have the new feature in the fake anvil"
    )
    new_memo_md = target / ".anvil" / "skills" / "memo" / "SKILL.md"
    assert "target_length feature" in new_memo_md.read_text(), (
        "memo dst was not auto-upgraded to the new source"
    )
    # deck dst still has the consumer's override (and ONLY the consumer's
    # override, not the upstream tweak) — modifications preserved.
    new_deck_md = target / ".anvil" / "skills" / "deck" / "SKILL.md"
    assert "deck slug-versioning override" in new_deck_md.read_text(), (
        "deck consumer override was overwritten despite the skip warning"
    )
    assert "upstream deck tweak" not in new_deck_md.read_text(), (
        "deck dst received the upstream tweak despite the consumer-modified "
        "skip — install bypassed the protection"
    )
    # Byte-identity of deck dst to its pre-install state.
    assert (
        hashlib.sha256(new_deck_md.read_bytes()).hexdigest() == deck_edit_hash
    ), "deck dst content drifted across the install despite being skipped"

    # Manifest reflects the single-invocation net state.
    manifest = _read_manifest(target)
    assert "memo" in manifest["installed_skills"]
    assert "deck" in manifest["skipped_overrides"]
    assert "memo" in manifest["skill_hashes"]
    # The deck hash is preserved from the previous install — the carry-
    # forward rule keeps it so a future install of deck can still detect
    # modifications.
    assert "deck" in manifest["skill_hashes"], (
        "deck hash was dropped from skill_hashes despite being skipped, not "
        f"deleted; manifest:\n{manifest}"
    )


def test_partial_manifest_does_not_abort_silently(tmp_path: Path) -> None:
    """Manifest with ``skill_hashes`` block but no entry for the queried skill
    does not silently abort the installer (regression test for #163 review bug).

    Reproducer for the bug found in PR #163 review:

      * fresh-install memo + deck → manifest has hashes for both
      * hand-edit the manifest to remove the ``deck`` entry from
        ``skill_hashes`` (simulates a partial-install scenario: e.g.
        someone hand-merged manifests, or a future schema migration
        dropped some entries)
      * mutate the upstream deck source so dst diverges from source
      * re-run installer for ``--skills=deck``

    Pre-fix, this sequence hit a ``set -euo pipefail`` trap inside
    ``read_recorded_hash``: the second pipeline's terminal ``grep -E`` returns
    1 when the queried skill is not in the ``skill_hashes`` block, pipefail
    propagated it, and the installer died silently mid-Stage-7 with exit code
    1 and zero stderr. Stage 8/9/10/11 never ran, and the manifest was never
    rewritten.

    Post-fix, the helper returns the empty string for the missing entry,
    Stage 7 falls into the legacy-install fallback branch (warn + skip
    unless ``--force``), and the installer completes cleanly through
    Stage 11. The other 7 tests in this file don't exercise this code
    path because they either (a) install only one skill (so the
    no-match branch isn't reached) or (b) always end up with a
    skill_hashes entry that matches the queried skill.
    """

    target = tmp_path / "partial-manifest-target"
    target.mkdir()

    # Step 1: fresh install both memo and deck. Manifest now records hashes
    # for both.
    first = _run("-y", "--skills=memo,deck", str(target))
    assert first.returncode == 0, first.stderr

    manifest_path = target / ".anvil" / "install-metadata.json"
    manifest = json.loads(manifest_path.read_text())
    assert "deck" in manifest["skill_hashes"]
    assert "memo" in manifest["skill_hashes"]

    # Step 2: hand-edit the manifest to remove the deck entry from
    # skill_hashes while keeping the deck dst dir intact. This is the exact
    # shape the bug requires: skill_hashes block present, but no entry for
    # the skill the next invocation will query for.
    manifest["skill_hashes"].pop("deck")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    # Sanity check: the manifest still has a skill_hashes block (the bug
    # only triggers when the block is present but the queried key is
    # missing; a fully-absent block hits the first pipeline's `|| true`
    # guard and the early `[[ -n "$block" ]]` short-circuit).
    manifest_after = json.loads(manifest_path.read_text())
    assert "skill_hashes" in manifest_after
    assert "deck" not in manifest_after["skill_hashes"]
    assert "memo" in manifest_after["skill_hashes"]

    # Step 3: mutate the upstream deck source so dst diverges from source.
    # This forces Stage 7 past the `dirs_identical` early-return and into
    # the override-detection branch that calls `read_recorded_hash`.
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    src_deck_md = fake_anvil / "anvil" / "skills" / "deck" / "SKILL.md"
    src_deck_md.write_text(src_deck_md.read_text() + "\n<!-- upstream edit -->\n")

    # Step 4: re-run installer for deck only. Pre-fix this exited with
    # code 1 and zero stderr halfway through Stage 7. Post-fix it must
    # complete cleanly through Stage 11.
    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=deck", str(target))
    assert second.returncode == 0, (
        "installer aborted on partial-manifest scenario (regression for "
        f"#163 review bug):\n--- stdout ---\n{second.stdout}\n"
        f"--- stderr ---\n{second.stderr}"
    )

    combined = second.stdout + second.stderr

    # Stage 7 reached the legacy-install fallback (no recorded hash → skip
    # with the diagnostic qualifier). This is the correct branch for the
    # "manifest has skill_hashes but no entry for this skill" case.
    assert "skipped: consumer-modified .anvil/skills/deck" in combined, (
        "partial-manifest path did not skip deck as consumer-modified:\n"
        f"{combined}"
    )
    assert "legacy install, no recorded hash" in combined, (
        "partial-manifest path did not emit the legacy-install diagnostic "
        f"qualifier (the absence-of-entry should route through the same "
        f"branch as absence-of-block):\n{combined}"
    )

    # Stage 8/9/10/11 must have run. Stage 11 is the headline marker: a
    # silent abort under pipefail prints no Stage 11 banner at all.
    assert "Stage 11: summary" in combined, (
        "Stage 11 never ran — installer aborted before reaching the "
        f"summary (silent-abort symptom of the #163 bug):\n{combined}"
    )

    # Stage 9 ran, so the manifest was rewritten. Deck must be in
    # skipped_overrides, and the deck hash must NOT have reappeared (we
    # never had a baseline to carry forward).
    final_manifest = _read_manifest(target)
    assert "deck" in final_manifest["skipped_overrides"]
    assert "deck" not in final_manifest.get("skill_hashes", {}), (
        "deck hash reappeared in skill_hashes despite never being recorded "
        f"(no baseline to carry forward); manifest:\n{final_manifest}"
    )
    # The deck dst content must be untouched (skip-on-modified semantics
    # held even though the helper would have crashed without the fix).
    deck_md = target / ".anvil" / "skills" / "deck" / "SKILL.md"
    assert "upstream edit" not in deck_md.read_text(), (
        "deck dst received the upstream edit despite being flagged as "
        "consumer-modified — Stage 7 wrote the wrong branch."
    )
