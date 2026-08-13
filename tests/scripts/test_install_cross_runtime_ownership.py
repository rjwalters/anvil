"""Cross-runtime (Claude/Codex) upgrade + removal ownership tests.

Issue #1005 (final phase of the #1000 epic, "Make Anvil artifact skills
discoverable in Claude and Codex"). #1003 (closed via PR #1010) added the
Codex CLI registration shim at ``.agents/skills/anvil-<name>/SKILL.md`` in
parallel to the pre-existing Claude shim at
``.claude/skills/anvil-<name>/SKILL.md``, wired into every call site the
Claude shim already had (the happy-path install and both override-skip
branches) plus a Stage 7.6 stale-shim cleanup pass on a ``--skills=``
narrowing. #1004 (closed via PR #1014) added the analogous additive,
marker-bounded ``AGENTS.md`` merge (Codex's entry point) alongside the
pre-existing ``CLAUDE.md`` merge.

Both phases have their own unit coverage
(``tests/scripts/test_install_codex_shim.py``,
``tests/scripts/test_install_agents_md_merge.py``). This module's job is
narrower and compositional: it exercises **both runtimes together, in one
install/upgrade/removal pass**, and pins the ownership boundary the #1000
epic's acceptance criteria call out explicitly --

  * consumer-owned content (a skill body override, or hand-written prose
    outside the ``<!-- BEGIN ANVIL -->``/``<!-- END ANVIL -->`` markers in
    either ``CLAUDE.md`` or ``AGENTS.md``) survives a re-install;
  * framework-owned content (the registration shims themselves, and any
    *other*, not-hand-edited skill's canonical body) keeps updating on the
    same re-install pass, on both runtimes symmetrically;
  * narrowing ``--skills=`` on a re-install cleans up BOTH runtimes'
    registrations for a dropped skill and leaves BOTH runtimes' registrations
    for a retained skill untouched.

Distinct filename per the #58 packaging convention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

ANVIL_MARK_BEGIN = "<!-- BEGIN ANVIL -->"


def _run_install(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Run the installer non-interactively against ``target``.

    ``--no-sync`` keeps the tests independent of uv availability and fast.
    """

    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", *extra, str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"installer exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def _both_runtime_paths(target: Path, skill: str) -> tuple[Path, Path]:
    claude = target / ".claude" / "skills" / f"anvil-{skill}" / "SKILL.md"
    codex = target / ".agents" / "skills" / f"anvil-{skill}" / "SKILL.md"
    return claude, codex


# ---------------------------------------------------------------------------
# Upgrade ownership: a hand-edited skill body (consumer override) survives a
# re-install, and BOTH runtimes' registration shims keep regenerating around
# it (they are generated pointers, not part of the override surface, on
# either runtime).
# ---------------------------------------------------------------------------


def test_skill_body_override_survives_reinstall_both_shims_still_regenerate(
    tmp_path: Path,
) -> None:
    target = tmp_path / "ownership-skill-body-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo,deck"))
    claude_shim, codex_shim = _both_runtime_paths(target, "memo")
    assert claude_shim.is_file() and codex_shim.is_file()

    # Hand-edit the shared canonical skill body -- the file BOTH runtimes'
    # shims point back to.
    skill_body = target / ".anvil" / "skills" / "memo" / "SKILL.md"
    skill_body.write_text(
        skill_body.read_text(encoding="utf-8") + "\n<!-- consumer override -->\n",
        encoding="utf-8",
    )
    claude_shim_before = claude_shim.read_bytes()
    codex_shim_before = codex_shim.read_bytes()

    result = _run_install(target, "--skills=memo,deck")
    _assert_ok(result)
    assert "skipped: consumer-modified" in result.stdout, (
        f"expected the installer to report the skill body as consumer-modified "
        f"and skip overwriting it; got:\n{result.stdout}"
    )

    # The consumer's edit to the shared canonical body survives.
    assert "<!-- consumer override -->" in skill_body.read_text(encoding="utf-8")

    # Both runtimes' shims are generated pointers, not override targets --
    # they still exist (regenerated) and are unaffected by the skip, on
    # both runtimes symmetrically.
    assert claude_shim.is_file()
    assert codex_shim.is_file()
    assert claude_shim.read_bytes() == claude_shim_before
    assert codex_shim.read_bytes() == codex_shim_before


# ---------------------------------------------------------------------------
# The registration shims themselves are framework-owned on BOTH runtimes --
# a direct hand-edit to either one does NOT survive a re-install (contrast
# with the skill-body override case above).
# ---------------------------------------------------------------------------


def test_claude_shim_hand_edit_does_not_survive_reinstall(tmp_path: Path) -> None:
    target = tmp_path / "ownership-claude-shim-edit-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo"))
    claude_shim, _codex_shim = _both_runtime_paths(target, "memo")
    original = claude_shim.read_text(encoding="utf-8")
    claude_shim.write_text(original + "\n<!-- hand edit -->\n", encoding="utf-8")

    _assert_ok(_run_install(target, "--skills=memo"))

    after = claude_shim.read_text(encoding="utf-8")
    assert "<!-- hand edit -->" not in after, (
        "a direct hand-edit to the Claude registration shim survived a "
        "re-install -- the shim must be unconditionally regenerated, not "
        "treated as consumer-owned"
    )
    assert after == original


def test_codex_shim_hand_edit_does_not_survive_reinstall(tmp_path: Path) -> None:
    """Symmetric to the Claude case: same framework-owned, always-regenerated
    contract applies to the Codex-side registration shim."""

    target = tmp_path / "ownership-codex-shim-edit-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo"))
    _claude_shim, codex_shim = _both_runtime_paths(target, "memo")
    original = codex_shim.read_text(encoding="utf-8")
    codex_shim.write_text(original + "\n<!-- hand edit -->\n", encoding="utf-8")

    _assert_ok(_run_install(target, "--skills=memo"))

    after = codex_shim.read_text(encoding="utf-8")
    assert "<!-- hand edit -->" not in after, (
        "a direct hand-edit to the Codex registration shim survived a "
        "re-install -- the shim must be unconditionally regenerated, not "
        "treated as consumer-owned"
    )
    assert after == original


# ---------------------------------------------------------------------------
# Root entry-point ownership: consumer prose outside the Anvil marker block
# survives a re-install on BOTH CLAUDE.md (Claude) and AGENTS.md (Codex).
# ---------------------------------------------------------------------------


def test_claude_md_and_agents_md_hand_edits_outside_markers_both_survive(
    tmp_path: Path,
) -> None:
    target = tmp_path / "ownership-entrypoint-target"
    target.mkdir()

    consumer_claude = "# Repo notes (Claude)\n\nConsumer-authored content.\n"
    consumer_agents = "# Repo notes (Codex)\n\nConsumer-authored content.\n"
    (target / "CLAUDE.md").write_text(consumer_claude, encoding="utf-8")
    (target / "AGENTS.md").write_text(consumer_agents, encoding="utf-8")

    _assert_ok(_run_install(target, "--skills=memo"))

    claude_text = (target / "CLAUDE.md").read_text(encoding="utf-8")
    agents_text = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert claude_text.startswith(consumer_claude)
    assert agents_text.startswith(consumer_agents)
    assert claude_text.count(ANVIL_MARK_BEGIN) == 1
    assert agents_text.count(ANVIL_MARK_BEGIN) == 1

    # A second, upgrade-shaped re-install keeps the consumer content intact
    # on both files while the Anvil block itself stays present and singular.
    result = _run_install(target, "--skills=memo")
    _assert_ok(result)
    claude_text_2 = (target / "CLAUDE.md").read_text(encoding="utf-8")
    agents_text_2 = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert claude_text_2.startswith(consumer_claude)
    assert agents_text_2.startswith(consumer_agents)
    assert claude_text_2.count(ANVIL_MARK_BEGIN) == 1
    assert agents_text_2.count(ANVIL_MARK_BEGIN) == 1


# ---------------------------------------------------------------------------
# Framework-owned content keeps updating on the SAME re-install pass that
# skips a sibling skill's consumer-modified body -- the skip is scoped per
# skill, not repo-wide, on both runtimes.
# ---------------------------------------------------------------------------


def test_unmodified_sibling_skill_still_auto_upgrades_while_another_is_skipped(
    tmp_path: Path,
) -> None:
    target = tmp_path / "ownership-sibling-isolation-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo,deck"))

    # Hand-edit only 'memo's body -- 'deck' stays pristine (unmodified-since-
    # install).
    memo_body = target / ".anvil" / "skills" / "memo" / "SKILL.md"
    memo_body.write_text(
        memo_body.read_text(encoding="utf-8") + "\n<!-- consumer override -->\n",
        encoding="utf-8",
    )
    deck_claude_shim, deck_codex_shim = _both_runtime_paths(target, "deck")
    assert deck_claude_shim.is_file() and deck_codex_shim.is_file()

    result = _run_install(target, "--skills=memo,deck")
    _assert_ok(result)
    assert "skipped: consumer-modified .anvil/skills/memo" in result.stdout

    # 'deck's canonical body, and both of its runtime registrations, are
    # untouched by memo's skip -- framework-owned content for the
    # not-hand-edited skill keeps flowing through on the same pass.
    assert "skipped: consumer-modified .anvil/skills/deck" not in result.stdout
    assert deck_claude_shim.is_file()
    assert deck_codex_shim.is_file()
    canonical_deck_source = REPO_ROOT / "anvil" / "skills" / "deck" / "SKILL.md"
    installed_deck_body = target / ".anvil" / "skills" / "deck" / "SKILL.md"
    assert installed_deck_body.read_text(
        encoding="utf-8"
    ) == canonical_deck_source.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Removal ownership: narrowing --skills= on a re-install cleans up BOTH
# runtimes' registrations for the dropped skill, and leaves BOTH runtimes'
# registrations (and the full on-disk footprint) for the retained skill
# untouched.
# ---------------------------------------------------------------------------


def test_narrowed_reinstall_cleans_up_both_runtimes_for_dropped_skill_only(
    tmp_path: Path,
) -> None:
    target = tmp_path / "ownership-narrow-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo,deck"))
    memo_claude, memo_codex = _both_runtime_paths(target, "memo")
    deck_claude, deck_codex = _both_runtime_paths(target, "deck")
    assert all(p.is_file() for p in (memo_claude, memo_codex, deck_claude, deck_codex))

    deck_body = target / ".anvil" / "skills" / "deck"
    deck_pymirror = target / ".anvil" / "anvil" / "skills" / "deck"
    assert deck_body.is_dir()
    assert deck_pymirror.is_dir()

    result = _run_install(target, "--skills=memo")
    _assert_ok(result)

    # Dropped skill 'deck': BOTH runtime registrations gone, plus its full
    # installer-owned footprint (canonical body + Python mirror).
    assert not deck_claude.exists(), "Claude registration for dropped skill survived"
    assert not deck_codex.exists(), "Codex registration for dropped skill survived"
    assert not deck_body.exists(), "canonical skill body for dropped skill survived"
    assert not deck_pymirror.exists(), "Python mirror for dropped skill survived"

    # Retained skill 'memo': BOTH runtime registrations, and its full
    # footprint, are untouched by the narrowing.
    assert memo_claude.is_file(), "Claude registration for retained skill was removed"
    assert memo_codex.is_file(), "Codex registration for retained skill was removed"
    assert (target / ".anvil" / "skills" / "memo").is_dir()
    assert (target / ".anvil" / "anvil" / "skills" / "memo").is_dir()


def test_narrowed_reinstall_preserves_consumer_authored_skill_on_both_runtimes(
    tmp_path: Path,
) -> None:
    """A consumer-authored skill (never installer-provenanced) is never a
    removal candidate, on either runtime, even though it was never
    registered on either runtime by the installer in the first place --
    Stage 7.6's provenance check (prior manifest, not a bare disk scan)
    protects it regardless of which runtimes are in play."""

    target = tmp_path / "ownership-consumer-authored-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo,deck"))

    custom_skill_dir = target / ".anvil" / "skills" / "my-custom-doctype"
    custom_skill_dir.mkdir(parents=True)
    (custom_skill_dir / "SKILL.md").write_text(
        "---\nname: my-custom-doctype\n---\n\nConsumer-authored, not anvil-shipped.\n",
        encoding="utf-8",
    )

    result = _run_install(target, "--skills=memo")
    _assert_ok(result)

    assert custom_skill_dir.is_dir(), (
        "narrowed re-install swept a consumer-authored skill directory that "
        "the installer never shipped on either runtime"
    )
    assert (custom_skill_dir / "SKILL.md").is_file()
