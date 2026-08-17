"""Regression tests: installer writes/prunes the Codex CLI registration shim.

Issue #1003 (phase 2 of the #1000 epic, "Make Anvil artifact skills
discoverable in Claude and Codex"). ``scripts/install-anvil.sh`` already
writes a thin Claude registration shim per skill via ``write_shim()`` at
``.claude/skills/anvil-<name>/SKILL.md``. Codex CLI got no equivalent
registration.

The research spike #1002 (``docs/codex-skill-adapter.md``) verified, from
the official ``developers.openai.com/codex/build-skills`` docs, that Codex
scans repo-root ``.agents/skills/<name>/SKILL.md`` (NOT ``.codex/skills/``)
and that its minimal ``SKILL.md`` frontmatter contract (``name`` +
``description``) is identical to Claude Code's, with no wrapping plugin
manifest required for discovery.

This fix adds ``write_codex_shim()`` -- structured in parallel to
``write_shim()`` -- wired into every call site the Claude shim has (the
happy-path Stage 7 install and both override-skip branches), with the same
``--skills=`` filtering and ``--dry-run`` honesty, plus a matching Stage 7.6
cleanup pass for stale Codex shims on a ``--skills=``-narrowed re-install.

These tests run the installer end-to-end via ``subprocess`` (mirroring the
pattern in ``test_install_shim_depth.py``, the Claude-shim analog) so the
contract is enforced at the real entry point a consumer hits. Distinct
filename per the #58 packaging convention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from anvil.lib.testing import assert_ok as _assert_ok

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _run_install(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Run the installer non-interactively against ``target``.

    Captures stdout+stderr as text so test assertions can quote installer
    output in failure messages. ``--no-sync`` keeps the tests independent of
    uv availability and fast.
    """

    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", *extra, str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _run_dry_run(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--no-sync", *extra, str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


# ---------------------------------------------------------------------------
# The Codex shim is written at the verified `.agents/skills/anvil-<name>/`
# path, pointing back at the canonical `.anvil/skills/<name>/SKILL.md` body.
# ---------------------------------------------------------------------------


def test_codex_shim_written_at_verified_path(tmp_path: Path) -> None:
    """The per-skill Codex shim lands at ``.agents/skills/anvil-<skill>/SKILL.md``.

    Per docs/codex-skill-adapter.md this is the repo-root path Codex CLI
    scans for skills -- NOT ``.codex/skills/`` (a blog-sourced hypothesis the
    spike refuted).
    """

    target = tmp_path / "codex-shim-target"
    target.mkdir()

    result = _run_install(target, "--skills=memo")
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

    # Must NOT land at the refuted `.codex/skills/` hypothesis path.
    refuted_path = target / ".codex" / "skills" / "anvil-memo" / "SKILL.md"
    assert not refuted_path.exists(), (
        f"Codex shim written at the refuted .codex/skills/ path: {refuted_path}"
    )


def test_codex_shim_points_at_canonical_body_never_copies_it(tmp_path: Path) -> None:
    """The Codex shim is a thin pointer, never a copy of the skill body."""

    target = tmp_path / "codex-shim-pointer-target"
    target.mkdir()

    result = _run_install(target, "--skills=memo")
    _assert_ok(result)

    shim = target / ".agents" / "skills" / "anvil-memo" / "SKILL.md"
    body = shim.read_text(encoding="utf-8")

    assert "name: anvil-memo" in body, f"shim frontmatter missing name: {body}"
    assert ".anvil/skills/memo/SKILL.md" in body, (
        f"shim does not point back at the canonical body: {body}"
    )

    canonical = target / ".anvil" / "skills" / "memo" / "SKILL.md"
    assert canonical.is_file(), "canonical skill body was not installed"
    canonical_body = canonical.read_text(encoding="utf-8")

    # The shim is a short pointer, not a duplicate of the (much longer) real
    # skill body.
    assert len(body) < len(canonical_body), (
        "Codex shim looks like a full copy of the skill body, not a thin pointer"
    )
    assert body != canonical_body


def test_codex_and_claude_shims_track_1to1(tmp_path: Path) -> None:
    """Every skill that gets a Claude shim also gets a Codex shim, same run."""

    target = tmp_path / "codex-claude-parity-target"
    target.mkdir()

    selected = ["memo", "deck", "report"]
    result = _run_install(target, f"--skills={','.join(selected)}")
    _assert_ok(result)

    for skill in selected:
        claude_shim = target / ".claude" / "skills" / f"anvil-{skill}" / "SKILL.md"
        codex_shim = target / ".agents" / "skills" / f"anvil-{skill}" / "SKILL.md"
        assert claude_shim.is_file(), f"Claude shim missing for {skill!r}"
        assert codex_shim.is_file(), f"Codex shim missing for {skill!r}"


# ---------------------------------------------------------------------------
# --skills= filtering applies identically to the Codex output.
# ---------------------------------------------------------------------------


def test_codex_shim_respects_skills_filter(tmp_path: Path) -> None:
    """Only the selected skills get a Codex registration."""

    target = tmp_path / "codex-shim-filter-target"
    target.mkdir()

    result = _run_install(target, "--skills=memo")
    _assert_ok(result)

    codex_skills_dir = target / ".agents" / "skills"
    present = {p.name for p in codex_skills_dir.iterdir() if p.is_dir()}

    assert "anvil-memo" in present
    assert "anvil-deck" not in present, (
        f"unselected skill 'deck' got a Codex registration: {present}"
    )


# ---------------------------------------------------------------------------
# --dry-run reports the plan and writes nothing.
# ---------------------------------------------------------------------------


def test_dry_run_reports_codex_shim_plan_and_writes_nothing(tmp_path: Path) -> None:
    """``--dry-run`` names the planned Codex shim write and mutates nothing."""

    target = tmp_path / "codex-shim-dryrun-target"
    target.mkdir()

    result = _run_dry_run(target, "--skills=memo")
    _assert_ok(result)

    assert ".agents/skills/anvil-memo/SKILL.md" in result.stdout, (
        f"dry-run action line does not advertise the Codex shim path; "
        f"got:\n{result.stdout}"
    )
    assert not (target / ".agents").exists(), (
        "--dry-run wrote the .agents/ directory to disk"
    )


# ---------------------------------------------------------------------------
# Stale Codex shim cleanup on a `--skills=`-filtered re-install.
# ---------------------------------------------------------------------------


def test_narrowed_reinstall_prunes_stale_codex_shim(tmp_path: Path) -> None:
    """Removing a skill from ``--skills=`` on a re-install prunes its Codex shim too.

    Mirrors the existing Claude-shim cleanup guaranteed by Stage 7.6 (issue
    #716): a skill dropped from the current selection is removed from every
    installer-owned path family, including the new Codex one.
    """

    target = tmp_path / "codex-shim-narrow-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo,deck"))
    claude_deck_shim = target / ".claude" / "skills" / "anvil-deck"
    codex_deck_shim = target / ".agents" / "skills" / "anvil-deck"
    assert claude_deck_shim.is_dir()
    assert codex_deck_shim.is_dir()

    result = _run_install(target, "--skills=memo")
    _assert_ok(result)

    assert not codex_deck_shim.exists(), (
        "narrowed re-install left a stale Codex shim for a deselected skill"
    )
    assert not claude_deck_shim.exists(), (
        "narrowed re-install left a stale Claude shim for a deselected skill"
    )
    # The still-selected skill's shims survive on both runtimes.
    assert (target / ".claude" / "skills" / "anvil-memo").is_dir()
    assert (target / ".agents" / "skills" / "anvil-memo").is_dir()


def test_codex_shim_regenerated_on_consumer_modified_skip(tmp_path: Path) -> None:
    """The Codex shim regenerates even when the skill body is consumer-modified.

    Mirrors ``write_shim()``'s override-skip branch: the shim is a generated
    pointer, not part of the hash-tracked override surface, so it is always
    regenerated regardless of whether the skill body itself was skipped for
    being consumer-modified.
    """

    target = tmp_path / "codex-shim-override-skip-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo"))

    # Simulate a consumer hand-edit to the skill body (not the shim) so the
    # next install takes the "consumer-modified, skip body" branch.
    skill_body = target / ".anvil" / "skills" / "memo" / "SKILL.md"
    skill_body.write_text(
        skill_body.read_text(encoding="utf-8") + "\n<!-- consumer edit -->\n",
        encoding="utf-8",
    )

    result = _run_install(target, "--skills=memo")
    _assert_ok(result)
    assert "skipped: consumer-modified" in result.stdout, (
        f"expected an override-skip warning; got:\n{result.stdout}"
    )

    codex_shim = target / ".agents" / "skills" / "anvil-memo" / "SKILL.md"
    claude_shim = target / ".claude" / "skills" / "anvil-memo" / "SKILL.md"
    assert codex_shim.is_file(), (
        "Codex shim was not regenerated on the override-skip branch"
    )
    assert claude_shim.is_file()
    # The consumer's hand-edit to the skill body itself is preserved.
    assert "<!-- consumer edit -->" in skill_body.read_text(encoding="utf-8")
