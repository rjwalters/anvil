"""Regression test: top-level ``lib_hash`` baseline drives Stage 5 lib override
detection.

Issue #490: ``install-anvil.sh`` Stage 5 previously copied ``anvil/lib`` →
``<consumer>/.anvil/anvil/lib/`` via an unconditional ``copy_tree``. Unlike
Stage 7 (skill bodies), it recorded no as-installed hash and performed no
override detection. A consumer who hand-edited the documented "consumer
single-tenant" override tier (``.anvil/anvil/lib/memo/styles.css``,
``template.tex``, ``template.html`` — ``anvil/lib/memo/README.md``) lost those
edits *silently* on the next install/upgrade: no warning, no skip, no
``--force`` gate.

The fix (Option 1 from the issue, mirroring the #152 skill-body discipline)
records a single top-level ``lib_hash`` over the documented override-target
assets in the manifest at install time. On re-install, the installer compares
the current override-asset hash to the recorded baseline:

  * override hash == source override hash → assets untouched vs source,
    plain framework upgrade.
  * override hash == recorded baseline (but differs from source) → consumer
    never touched them; source moved forward. Auto-upgrade.
  * recorded baseline absent (legacy manifest) → skip-with-warning, preserve
    override assets, require ``--force``. One-time migration cost.
  * recorded baseline present and != current → consumer modified an override
    asset. Skip-with-warning, preserve it, require ``--force``.

CRITICAL CARVE-OUT: in *every* branch the rest of the lib tree (importable
``anvil.lib.*`` framework code, schema JSON, figures, marp config) and
``anvil/__init__.py`` always upgrade. Only the documented override-target
assets are ever preserved — a consumer can never pin stale framework code by
editing an override asset.

These tests exercise the installer via ``subprocess`` so the contract is
enforced at the real entry point a consumer hits. Pattern mirrors
``test_install_hash_upgrade.py``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

# The documented lib override-target assets (LIB_OVERRIDE_TARGETS in the
# installer): the memo brandable templates plus the shared mermaid diagram
# theme (issue #634 — consumers patch it to match their palette).
OVERRIDE_ASSET = Path(".anvil") / "anvil" / "lib" / "memo" / "styles.css"
# The shared mermaid theme override target (issue #634).
MERMAID_THEME = Path(".anvil") / "anvil" / "lib" / "figures" / "mermaid-theme.json"
# A non-override framework lib file: must ALWAYS upgrade (the carve-out).
FRAMEWORK_LIB_FILE = Path(".anvil") / "anvil" / "lib" / "render_gate.py"
# The import anchor: must ALWAYS upgrade.
ANVIL_INIT = Path(".anvil") / "anvil" / "__init__.py"


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
    "fake anvil checkout" is the natural way to simulate "source moved forward
    in a later release" without touching the real checkout under test.
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


def _lib_override_hash(lib_root: Path) -> str:
    """Recompute the installer's ``lib_override_hash`` over the documented
    override-target assets present under ``lib_root``.

    Mirrors the installer's pipeline exactly (shell out rather than reimplement
    in Python) so the test asserts byte-identity with the manifest value.
    """

    targets = [
        "memo/styles.css",
        "memo/template.html",
        "memo/template.tex",
        "figures/mermaid-theme.json",
    ]
    existing = [t for t in targets if (lib_root / t).is_file()]
    assert existing, f"no override targets exist under {lib_root}"
    # printf '<paths>\0' | sort -z | xargs -0 shasum -a 256 | shasum -a 256
    args = "".join(f"{t}\\0" for t in existing)
    inner = subprocess.run(
        f"printf '{args}' | LC_ALL=C sort -z | xargs -0 shasum -a 256",
        shell=True,
        cwd=lib_root,
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
# Test cases (per curator test plan)
# ---------------------------------------------------------------------------


def test_fresh_install_records_lib_hash(tmp_path: Path) -> None:
    """Fresh install writes a top-level ``lib_hash`` matching the override hash."""

    target = tmp_path / "fresh-target"
    target.mkdir()

    result = _run("-y", "--skills=memo", str(target))
    assert result.returncode == 0, (
        f"install failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    manifest = _read_manifest(target)
    assert "lib_hash" in manifest, f"manifest missing 'lib_hash':\n{manifest}"
    assert manifest["lib_hash"], "lib_hash recorded as empty on fresh install"

    actual = _lib_override_hash(target / ".anvil" / "anvil" / "lib")
    assert manifest["lib_hash"] == actual, (
        f"recorded lib_hash {manifest['lib_hash']!r} does not match the actual "
        f"override-asset hash {actual!r}; manifest is lying about the snapshot."
    )


def test_unmodified_upgrade_clobbers_cleanly(tmp_path: Path) -> None:
    """Re-install with no consumer edits upgrades the lib tree, no ``--force``.

    Source moves forward (the override asset changes upstream). With no
    consumer edit, the installer must auto-upgrade the asset (no skip warning),
    refresh ``lib_hash``, and leave the dst asset equal to the new source.
    """

    target = tmp_path / "unmodified-target"
    target.mkdir()

    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr
    original_hash = _read_manifest(target)["lib_hash"]

    # Source moves forward: the override asset changes upstream.
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    src_asset = fake_anvil / "anvil" / "lib" / "memo" / "styles.css"
    src_asset.write_text(src_asset.read_text() + "\n/* upstream tweak */\n")

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=memo", str(target))
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr
    assert "skipped: consumer-modified" not in combined, (
        f"unmodified upgrade incorrectly flagged a consumer modification:\n{combined}"
    )

    # The dst asset must now equal the new upstream source.
    dst_asset = target / OVERRIDE_ASSET
    assert "/* upstream tweak */" in dst_asset.read_text(), (
        "unmodified upgrade did not advance the override asset to new source"
    )

    # lib_hash refreshed to the new source override hash.
    new_hash = _read_manifest(target)["lib_hash"]
    assert new_hash != original_hash, "lib_hash was not refreshed on upgrade"
    assert new_hash == _lib_override_hash(fake_anvil / "anvil" / "lib"), (
        "refreshed lib_hash does not match the new source override hash"
    )


def test_consumer_modified_asset_skips_with_warning(tmp_path: Path) -> None:
    """A hand-edited override asset is skipped-with-warning and preserved.

    Fresh-install memo, edit ``.anvil/anvil/lib/memo/styles.css``, re-run the
    installer (source also moved forward). The recorded ``lib_hash`` no longer
    matches the now-edited asset, so the installer protects the consumer's edit
    by preserving it — but framework code still upgrades (the carve-out).
    """

    target = tmp_path / "modified-target"
    target.mkdir()

    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr

    dst_asset = target / OVERRIDE_ASSET
    consumer_text = dst_asset.read_text() + "\n/* consumer brand edit */\n"
    dst_asset.write_text(consumer_text)

    # Source also moves forward so dst differs from source for an honest test.
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    src_asset = fake_anvil / "anvil" / "lib" / "memo" / "styles.css"
    src_asset.write_text(src_asset.read_text() + "\n/* upstream tweak */\n")

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=memo", str(target))
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr
    assert "skipped: consumer-modified .anvil/anvil/lib" in combined, (
        f"consumer-modified override asset did not trigger the skip warning:\n{combined}"
    )
    # Not the legacy fallback — a recorded lib_hash exists.
    assert "legacy install, no recorded lib_hash" not in combined, (
        f"consumer-modified asset incorrectly hit the legacy fallback:\n{combined}"
    )

    # The consumer's edit must survive; the upstream tweak must NOT land.
    preserved = dst_asset.read_text()
    assert "/* consumer brand edit */" in preserved, (
        "consumer override asset was overwritten despite the skip warning"
    )
    assert "/* upstream tweak */" not in preserved, (
        "consumer override asset received the upstream tweak despite the skip"
    )


def test_consumer_modified_asset_force_overwrites(tmp_path: Path) -> None:
    """``--force`` overwrites a consumer-modified override asset and re-records.

    The ``--force`` escape hatch must remain unconditional. After force, the
    asset matches new source and ``lib_hash`` equals the new source hash.
    """

    target = tmp_path / "force-target"
    target.mkdir()

    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr

    dst_asset = target / OVERRIDE_ASSET
    dst_asset.write_text(dst_asset.read_text() + "\n/* consumer brand edit */\n")

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    src_asset = fake_anvil / "anvil" / "lib" / "memo" / "styles.css"
    src_asset.write_text(src_asset.read_text() + "\n/* upstream tweak */\n")

    second = _run_from_fake_anvil(
        fake_anvil, "-y", "--force", "--skills=memo", str(target)
    )
    assert second.returncode == 0, second.stderr

    overwritten = dst_asset.read_text()
    assert "/* consumer brand edit */" not in overwritten, (
        "--force did not overwrite the consumer's override edit"
    )
    assert "/* upstream tweak */" in overwritten, (
        "--force did not install the new upstream source asset"
    )

    manifest = _read_manifest(target)
    assert manifest["lib_hash"] == _lib_override_hash(fake_anvil / "anvil" / "lib"), (
        "post-force lib_hash does not match the new source override hash"
    )


def test_legacy_manifest_falls_back_to_skip(tmp_path: Path) -> None:
    """Manifest without ``lib_hash`` hits the legacy skip-with-warning once.

    Hand-degrade the manifest to drop ``lib_hash`` (simulates a consumer who
    installed before this PR), edit the override asset, then re-install with a
    forward-moved source. The installer must skip-with-warning (legacy
    qualifier), preserve the override asset, and STILL upgrade framework code.
    """

    target = tmp_path / "legacy-target"
    target.mkdir()

    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr

    # Degrade the manifest to the pre-#490 shape (no lib_hash).
    manifest_path = target / ".anvil" / "install-metadata.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("lib_hash", None)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    # Consumer edits the override asset.
    dst_asset = target / OVERRIDE_ASSET
    dst_asset.write_text(dst_asset.read_text() + "\n/* legacy consumer edit */\n")

    # Source moves forward (framework code + override asset).
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    src_asset = fake_anvil / "anvil" / "lib" / "memo" / "styles.css"
    src_asset.write_text(src_asset.read_text() + "\n/* upstream tweak */\n")
    src_fw = fake_anvil / "anvil" / "lib" / "render_gate.py"
    src_fw.write_text(src_fw.read_text() + "\n# upstream framework change\n")

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=memo", str(target))
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr
    assert "skipped: consumer-modified .anvil/anvil/lib" in combined, (
        f"legacy-manifest path did not skip with warning:\n{combined}"
    )
    assert "legacy install, no recorded lib_hash" in combined, (
        f"legacy path did not emit the diagnostic qualifier:\n{combined}"
    )

    # Override asset preserved.
    assert "/* legacy consumer edit */" in dst_asset.read_text(), (
        "legacy skip path did not preserve the consumer override asset"
    )
    # Carve-out: framework code STILL upgraded.
    assert "# upstream framework change" in (target / FRAMEWORK_LIB_FILE).read_text(), (
        "legacy skip path left framework lib code stale (carve-out violated)"
    )

    # lib_hash now backfilled (non-empty) so the next install detects drift.
    assert _read_manifest(target)["lib_hash"], (
        "legacy skip path left lib_hash empty; next install would loop the "
        "legacy fallback forever"
    )


def test_framework_code_always_upgrades_carveout(tmp_path: Path) -> None:
    """THE carve-out: editing an override asset skips, but framework code and
    ``anvil/__init__.py`` still upgrade — the importable mirror is never stale.

    This is the critical invariant the curator flagged: a consumer must not be
    able to pin stale framework code by hand-editing a documented override
    asset. We edit ``styles.css`` (an override target), move BOTH the framework
    lib code and ``anvil/__init__.py`` forward upstream, then re-install with
    NO ``--force``. The override asset must be preserved while the framework
    code advances.
    """

    target = tmp_path / "carveout-target"
    target.mkdir()

    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr

    # Consumer edits the override asset (triggers the skip branch).
    dst_asset = target / OVERRIDE_ASSET
    dst_asset.write_text(dst_asset.read_text() + "\n/* consumer brand edit */\n")

    # Source moves forward: framework lib code AND the import anchor change.
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    src_fw = fake_anvil / "anvil" / "lib" / "render_gate.py"
    src_fw.write_text(src_fw.read_text() + "\n# upstream framework change\n")
    src_init = fake_anvil / "anvil" / "__init__.py"
    src_init.write_text(src_init.read_text() + "\n# upstream init change\n")

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=memo", str(target))
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr
    assert "skipped: consumer-modified .anvil/anvil/lib" in combined, (
        f"override-asset edit did not trigger the skip branch:\n{combined}"
    )

    # Override asset preserved.
    assert "/* consumer brand edit */" in dst_asset.read_text(), (
        "override asset overwritten despite the skip warning"
    )

    # CARVE-OUT: framework lib code upgraded despite the skip.
    fw_text = (target / FRAMEWORK_LIB_FILE).read_text()
    assert "# upstream framework change" in fw_text, (
        "framework lib code was left stale on the skip path — carve-out "
        "violated; a consumer could pin stale anvil.lib.* code"
    )
    # CARVE-OUT: the import anchor upgraded despite the skip.
    init_text = (target / ANVIL_INIT).read_text()
    assert "# upstream init change" in init_text, (
        "anvil/__init__.py was left stale on the skip path — carve-out violated"
    )


def test_fresh_install_populates_mermaid_theme(tmp_path: Path) -> None:
    """Fresh install populates ``.anvil/anvil/lib/figures/mermaid-theme.json``.

    Issue #634: the shared mermaid theme must ship under the importable
    ``.anvil/anvil/lib/`` tree (not the legacy ``.anvil/lib/``) and be covered
    by the recorded ``lib_hash`` so subsequent installs can detect consumer
    edits.
    """

    target = tmp_path / "mermaid-fresh-target"
    target.mkdir()

    result = _run("-y", "--skills=deck", str(target))
    assert result.returncode == 0, (
        f"install failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    theme = target / MERMAID_THEME
    assert theme.is_file(), (
        f"fresh install did not populate the mermaid theme at {theme}"
    )
    # The theme participates in the recorded override hash.
    assert _read_manifest(target)["lib_hash"] == _lib_override_hash(
        target / ".anvil" / "anvil" / "lib"
    ), "lib_hash does not cover the mermaid theme override target"


def test_consumer_modified_mermaid_theme_skips_with_warning(tmp_path: Path) -> None:
    """A hand-edited mermaid theme is skipped-with-warning and preserved.

    Issue #634: the studio patches ``mermaid-theme.json`` locally to match its
    brand palette. That edit must survive the next ``install-anvil.sh`` run (no
    ``--force``) with the same skip-with-warning discipline memo templates
    enjoy, while framework code still upgrades (the carve-out).
    """

    target = tmp_path / "mermaid-modified-target"
    target.mkdir()

    first = _run("-y", "--skills=deck", str(target))
    assert first.returncode == 0, first.stderr

    theme = target / MERMAID_THEME
    consumer_text = theme.read_text().replace("}", '  ,"__brand__":true}', 1)
    theme.write_text(consumer_text)

    # Source also moves forward so dst differs from source for an honest test.
    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    src_theme = fake_anvil / "anvil" / "lib" / "figures" / "mermaid-theme.json"
    src_theme.write_text(src_theme.read_text() + "\n")
    src_fw = fake_anvil / "anvil" / "lib" / "render_gate.py"
    src_fw.write_text(src_fw.read_text() + "\n# upstream framework change\n")

    second = _run_from_fake_anvil(fake_anvil, "-y", "--skills=deck", str(target))
    assert second.returncode == 0, second.stderr

    combined = second.stdout + second.stderr
    assert "skipped: consumer-modified .anvil/anvil/lib" in combined, (
        f"consumer-modified mermaid theme did not trigger the skip warning:\n{combined}"
    )

    # The consumer's brand edit must survive.
    assert "__brand__" in theme.read_text(), (
        "consumer mermaid theme was overwritten despite the skip warning"
    )
    # Carve-out: framework code STILL upgraded.
    assert "# upstream framework change" in (target / FRAMEWORK_LIB_FILE).read_text(), (
        "mermaid-theme skip path left framework lib code stale (carve-out violated)"
    )


def test_force_overwrites_modified_mermaid_theme(tmp_path: Path) -> None:
    """``--force`` overwrites a consumer-modified mermaid theme and re-records."""

    target = tmp_path / "mermaid-force-target"
    target.mkdir()

    first = _run("-y", "--skills=deck", str(target))
    assert first.returncode == 0, first.stderr

    theme = target / MERMAID_THEME
    theme.write_text(theme.read_text().replace("}", '  ,"__brand__":true}', 1))

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    src_theme = fake_anvil / "anvil" / "lib" / "figures" / "mermaid-theme.json"
    src_theme.write_text(src_theme.read_text() + "\n")

    second = _run_from_fake_anvil(
        fake_anvil, "-y", "--force", "--skills=deck", str(target)
    )
    assert second.returncode == 0, second.stderr

    assert "__brand__" not in theme.read_text(), (
        "--force did not overwrite the consumer's mermaid theme edit"
    )
    manifest = _read_manifest(target)
    assert manifest["lib_hash"] == _lib_override_hash(fake_anvil / "anvil" / "lib"), (
        "post-force lib_hash does not match the new source override hash"
    )


def test_dry_run_reports_verdict_without_mutating(tmp_path: Path) -> None:
    """``--dry-run`` names the Stage 5 lib verdict without touching disk.

    Mirrors ``test_install_dry_run_honesty.py``: the consumer-modified-asset
    scenario must surface the skip verdict in the dry-run preview while leaving
    the dst asset's mtime unchanged and the manifest's lib_hash intact.
    """

    target = tmp_path / "dry-run-target"
    target.mkdir()

    first = _run("-y", "--skills=memo", str(target))
    assert first.returncode == 0, first.stderr
    original_lib_hash = _read_manifest(target)["lib_hash"]

    dst_asset = target / OVERRIDE_ASSET
    dst_asset.write_text(dst_asset.read_text() + "\n/* consumer brand edit */\n")
    asset_mtime_before = dst_asset.stat().st_mtime

    fake_anvil = _copy_anvil_checkout(tmp_path / "fake-anvil")
    src_asset = fake_anvil / "anvil" / "lib" / "memo" / "styles.css"
    src_asset.write_text(src_asset.read_text() + "\n/* upstream tweak */\n")

    dry = _run_from_fake_anvil(
        fake_anvil, "--dry-run", "--skills=memo", str(target)
    )
    assert dry.returncode == 0, dry.stderr

    assert "skip override assets (consumer-modified)" in dry.stdout, (
        f"dry-run did not advertise the lib skip verdict:\n{dry.stdout}"
    )

    # Nothing mutated: asset content + mtime unchanged, manifest lib_hash intact.
    assert dst_asset.stat().st_mtime == asset_mtime_before, (
        "dry-run mutated the override asset"
    )
    assert "/* upstream tweak */" not in dst_asset.read_text(), (
        "dry-run wrote the upstream tweak to the override asset"
    )
    assert _read_manifest(target)["lib_hash"] == original_lib_hash, (
        "dry-run rewrote the manifest lib_hash"
    )
