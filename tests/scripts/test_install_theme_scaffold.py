"""Regression tests: installer scaffolds the consumer-owned starter theme.

Issue #471: the framework ``anvil/lib/memo/styles.css`` is deliberately
minimal by maintainer policy (black-on-white, no accents), so every fresh
consumer's first rendered memo looked indistinguishable from "the styling
failed." The fix (Option A-prime per the curator verification) seeds the
**theme tier** — the only consumer-owned path the installer never touches
on upgrade:

  * ``anvil/templates/themes/starter/`` ships ``theme.yml`` + a
    navy-accented ``memo/styles.css`` that preserves the framework
    default's functional baseline (booktabs-class tables, ``@page``
    footer page counter).
  * Installer Stage 7.8 scaffolds it to ``<target>/.anvil/themes/starter/``
    when ``memo`` is among the selected skills, **skip-if-exists** — the
    installer never overwrites anything under ``.anvil/themes/``, so
    consumer edits survive every re-install including ``--force``.
  * Stage 11 prints the override-path hint with the correct post-#230
    paths and the one-line BRIEF ``theme: starter`` enable step (the
    scaffold alone is inert — the theme tier activates only via the
    project BRIEF declaration).
  * ``--dry-run`` reports the would-scaffold action and writes nothing
    (issue #81 honesty discipline).

A docs guard also pins the ``anvil/lib/memo/README.md`` correction: the
pre-#471 claim that in-place lib edits are "respected" under the ``--force``
discipline was inaccurate — the Stage 5 lib copy is unconditional (no hash
tracking), so in-place edits under ``.anvil/anvil/lib/memo/`` are clobbered
on every upgrade. The durable path is the theme tier.

These tests exercise the installer via ``subprocess`` so the contract is
enforced at the real entry point a consumer hits. Pattern mirrors
``test_install_dry_run_honesty.py`` and ``test_install_hash_upgrade.py``.
Distinct filename per the #58 packaging convention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

STARTER_THEME_SRC = REPO_ROOT / "anvil" / "templates" / "themes" / "starter"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the installer with ``args`` and capture text stdout+stderr.

    ``--no-sync`` keeps the tests independent of uv availability and fast
    (Stage 10.5 is a convenience, not part of the scaffold contract under
    test).
    """

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
# Source-tree shape
# ---------------------------------------------------------------------------


def test_starter_theme_source_ships_required_files() -> None:
    """The source scaffold ships theme.yml + memo/styles.css."""

    assert (STARTER_THEME_SRC / "theme.yml").is_file(), (
        f"missing starter theme source: {STARTER_THEME_SRC / 'theme.yml'}"
    )
    assert (STARTER_THEME_SRC / "memo" / "styles.css").is_file(), (
        f"missing starter theme source: "
        f"{STARTER_THEME_SRC / 'memo' / 'styles.css'}"
    )


def test_starter_css_keeps_functional_baseline() -> None:
    """The starter CSS preserves the framework default's functional baseline.

    Acceptance criterion from #471: booktabs-class tables and the ``@page``
    footer page counter must survive in the starter theme — the scaffold is
    a tasteful accent layer, not a regression of the functional defaults.
    """

    css = (STARTER_THEME_SRC / "memo" / "styles.css").read_text(
        encoding="utf-8"
    )

    # @page footer page counter (review-grade artifacts need page numbers).
    assert "@page" in css, "starter CSS lost the @page paged-media rule"
    assert 'counter(page) " / " counter(pages)' in css, (
        "starter CSS lost the footer page counter"
    )
    # Booktabs-class table rules (#238): collapse + tabular-nums.
    assert "border-collapse: collapse" in css, (
        "starter CSS lost the booktabs-class table baseline"
    )
    assert "font-variant-numeric: tabular-nums" in css, (
        "starter CSS lost tabular-nums digit alignment"
    )
    # Navy palette accent per anvil/lib/figures/palette.py::ANVIL_NAVY.
    assert "#1f4e7a" in css, (
        "starter CSS does not use the canonical ANVIL_NAVY accent (#1f4e7a)"
    )


# ---------------------------------------------------------------------------
# Fresh install scaffolds
# ---------------------------------------------------------------------------


def test_fresh_install_scaffolds_starter_theme(tmp_path: Path) -> None:
    """Fresh install with memo selected creates the starter theme files."""

    target = tmp_path / "fresh-target"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    theme_yml = target / ".anvil" / "themes" / "starter" / "theme.yml"
    styles_css = (
        target / ".anvil" / "themes" / "starter" / "memo" / "styles.css"
    )
    assert theme_yml.is_file(), (
        f"fresh install did not scaffold {theme_yml}; "
        f"stdout:\n{result.stdout}"
    )
    assert styles_css.is_file(), (
        f"fresh install did not scaffold {styles_css}; "
        f"stdout:\n{result.stdout}"
    )

    # Byte-faithful copy of the shipped source.
    assert styles_css.read_text(encoding="utf-8") == (
        STARTER_THEME_SRC / "memo" / "styles.css"
    ).read_text(encoding="utf-8"), (
        "scaffolded styles.css differs from the shipped source"
    )


def test_install_without_memo_does_not_scaffold(tmp_path: Path) -> None:
    """``--skills=pub`` (no memo) installs no starter theme."""

    target = tmp_path / "no-memo-target"
    target.mkdir()

    result = _run("--skills=pub", str(target))
    _assert_ok(result)

    assert not (target / ".anvil" / "themes").exists(), (
        "installer scaffolded .anvil/themes/ even though memo was not "
        f"selected; stdout:\n{result.stdout}"
    )
    assert "skipping starter theme scaffold" in result.stdout, (
        "expected the memo-not-selected skip note in stdout; "
        f"got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Skip-if-exists: consumer edits survive re-install and --force
# ---------------------------------------------------------------------------


def test_reinstall_preserves_consumer_edits_to_starter_theme(
    tmp_path: Path,
) -> None:
    """Re-running the installer never overwrites files under .anvil/themes/.

    This includes ``--force`` — the flag governs the skill-body override
    matrix (issue #152), not the consumer-owned theme namespace.
    """

    target = tmp_path / "edit-target"
    target.mkdir()

    _assert_ok(_run("--skills=memo", str(target)))

    styles_css = (
        target / ".anvil" / "themes" / "starter" / "memo" / "styles.css"
    )
    sentinel = "/* consumer-edited: rose accent #be123c */\nbody { color: red; }\n"
    styles_css.write_text(sentinel, encoding="utf-8")

    # Plain re-install: preserved.
    second = _run("--skills=memo", str(target))
    _assert_ok(second)
    assert styles_css.read_text(encoding="utf-8") == sentinel, (
        "plain re-install overwrote the consumer-edited starter theme"
    )
    assert "preserving" in second.stdout, (
        "expected the skip-if-exists 'preserving' note on re-install; "
        f"got:\n{second.stdout}"
    )

    # --force re-install: STILL preserved.
    third = _run("--force", "--skills=memo", str(target))
    _assert_ok(third)
    assert styles_css.read_text(encoding="utf-8") == sentinel, (
        "--force re-install overwrote the consumer-edited starter theme; "
        "the installer must never write under .anvil/themes/ once it exists"
    )


def test_install_leaves_sibling_themes_untouched(tmp_path: Path) -> None:
    """A pre-existing sibling theme is not disturbed; starter is added."""

    target = tmp_path / "sibling-target"
    sibling_css = target / ".anvil" / "themes" / "acme" / "memo" / "styles.css"
    sibling_css.parent.mkdir(parents=True)
    sibling_content = "/* acme brand */ body { color: #be123c; }\n"
    sibling_css.write_text(sibling_content, encoding="utf-8")

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    assert sibling_css.read_text(encoding="utf-8") == sibling_content, (
        "installer disturbed a pre-existing sibling theme under .anvil/themes/"
    )
    assert (
        target / ".anvil" / "themes" / "starter" / "theme.yml"
    ).is_file(), (
        "starter theme was not scaffolded alongside a pre-existing sibling "
        f"theme; stdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# --dry-run honesty (issue #81)
# ---------------------------------------------------------------------------


def test_dry_run_reports_scaffold_and_writes_nothing(tmp_path: Path) -> None:
    """``--dry-run`` reports the would-scaffold action and writes nothing."""

    target = tmp_path / "dry-run-target"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--skills=memo", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(result)

    assert "[dry-run] scaffold starter theme" in result.stdout, (
        "expected the '[dry-run] scaffold starter theme ...' action line; "
        f"got:\n{result.stdout}"
    )
    assert not (target / ".anvil").exists(), (
        "--dry-run wrote .anvil/ to the target"
    )
    # The post-action confirmation must not fire under --dry-run.
    assert "ok: starter theme scaffolded" not in result.stdout, (
        "--dry-run emitted the lying 'ok: starter theme scaffolded' "
        f"confirmation; got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Stage 11 override-path hint
# ---------------------------------------------------------------------------


def test_summary_prints_override_path_hint(tmp_path: Path) -> None:
    """Stage 11 prints the post-#230 override paths + the BRIEF enable step.

    The scaffold alone is inert (the theme tier activates only when the
    project BRIEF declares ``theme: starter``), so the hint is load-bearing:
    without it the out-of-box render is unchanged and the operator has no
    breadcrumb.
    """

    target = tmp_path / "hint-target"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)
    stdout = result.stdout

    # The one-line enable step.
    assert "theme: starter" in stdout, (
        f"Stage 11 hint missing the 'theme: starter' enable step; "
        f"got:\n{stdout}"
    )
    # The correct post-#230 tiers (per theme_resolver.py::resolve_memo_asset),
    # NOT the dead pre-#230 .anvil/lib/memo/ path.
    assert ".anvil/themes/<theme>/memo/styles.css" in stdout, (
        f"Stage 11 hint missing the theme-tier override path; got:\n{stdout}"
    )
    assert ".anvil/anvil/lib/memo/styles.css" in stdout, (
        f"Stage 11 hint missing the in-place tier path; got:\n{stdout}"
    )
    # The in-place tier must carry its upgrade-clobber caveat.
    assert "overwritten on every re-install" in stdout, (
        f"Stage 11 hint missing the in-place upgrade-clobber caveat; "
        f"got:\n{stdout}"
    )


def test_hint_absent_when_memo_not_selected(tmp_path: Path) -> None:
    """No memo-styling hint when memo is not among the selected skills."""

    target = tmp_path / "no-hint-target"
    target.mkdir()

    result = _run("--skills=pub", str(target))
    _assert_ok(result)

    assert "theme: starter" not in result.stdout, (
        "memo styling hint printed even though memo was not selected; "
        f"got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Docs correction guard (anvil/lib/memo/README.md + styles.css header)
# ---------------------------------------------------------------------------


def test_memo_readme_no_longer_claims_in_place_edits_survive() -> None:
    """The override table must not claim in-place lib edits survive upgrades.

    Pre-#471 the README said the installer "respects in-place modifications
    under the standard ``--force`` discipline (see #163)" for the lib copy.
    That was inaccurate: Stage 5 copies ``anvil/lib`` unconditionally with
    no hash tracking (the #152 matrix guards skill bodies only). The README
    must document the clobber and point at the theme tier as the durable
    path.
    """

    readme = (REPO_ROOT / "anvil" / "lib" / "memo" / "README.md").read_text(
        encoding="utf-8"
    )

    assert "respects in-place modifications" not in readme, (
        "anvil/lib/memo/README.md still claims the installer respects "
        "in-place lib modifications — Stage 5's copy is unconditional"
    )
    assert "Overwritten on every re-install" in readme, (
        "anvil/lib/memo/README.md must document that the in-place tier is "
        "overwritten on every re-install/upgrade"
    )
    assert ".anvil/themes/starter/" in readme, (
        "anvil/lib/memo/README.md must point at the scaffolded starter "
        "theme as the durable override path"
    )


def test_framework_css_header_drops_dead_pre230_path() -> None:
    """The framework styles.css header must not quote the dead pre-#230 path.

    The issue-body confusion traced to this exact prose: the header pointed
    consumers at ``<consumer>/.anvil/lib/memo/styles.css``, a location the
    post-#230 resolver never consults.
    """

    css = (REPO_ROOT / "anvil" / "lib" / "memo" / "styles.css").read_text(
        encoding="utf-8"
    )

    assert "<consumer>/.anvil/lib/memo/styles.css" not in css, (
        "anvil/lib/memo/styles.css header still quotes the dead pre-#230 "
        "override path <consumer>/.anvil/lib/memo/styles.css"
    )
    assert ".anvil/themes/<theme>/memo/styles.css" in css, (
        "anvil/lib/memo/styles.css header must point at the theme-tier "
        "override path"
    )
