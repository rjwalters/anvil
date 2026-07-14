"""Regression tests: installer Stage 7.6 prunes upstream-removed/renamed skills.

Issue #716 (botho canary, 0.8.1 -> 0.9.0 upgrade, 2026-07-14). The 0.9.0 release
renamed ``pub`` -> ``paper`` (#694) and dropped ``pub`` from the shipped set. A
consumer upgrading via a plain ``install-anvil.sh <repo>`` (no ``--skills=``, the
documented way to pick up newly-shipped skills) was left with the entire renamed-
away ``pub`` footprint orphaned on disk — ~33 files across four path families,
including dispatchable ``anvil-pub-*.md`` agent shims pointing at command files
with no supported skill behind them. ``install-metadata.json`` correctly dropped
``pub`` from ``installed_skills``, so the manifest and the filesystem disagreed.

Root cause: the only prune logic that existed (Stage 7.5, #685/#688) is guarded
on ``SELECTED_SKILLS < ALL_SKILLS`` — a ``--skills=`` *narrowing*, always false on
a full/default install by construction. An upstream removal never trips that
guard on a plain install.

The fix adds a **Stage 7.6** reconciliation prune that computes the removal set as
a provenance-checked set difference against the PRIOR manifest, read before
Stage 9 overwrites it::

    REMOVED_SKILLS = previous_installed_skills - SELECTED_SKILLS

and removes all four installer-owned path families for each removed name:

  * ``.anvil/skills/<name>/``
  * ``.anvil/anvil/skills/<name>/``
  * ``.claude/skills/anvil-<name>/``
  * ``.claude/agents/anvil-<name>-*.md``

CRITICAL SAFETY: the removal signal is the prior *manifest*, NOT a bare disk
scan. A consumer-authored ``.anvil/skills/<custom>/`` that anvil never shipped is
never in any manifest's ``installed_skills``, so it can never enter the removal
set — it survives untouched. The ``test_consumer_authored_skill_survives_prune``
case below is the safety-critical negative test that pins this invariant.

Since the real registry no longer ships ``pub``, the "upstream removed a skill"
scenario is simulated by hand-editing the target's ``install-metadata.json`` after
a real install to inject a synthetic removed-skill entry plus matching directories
under all four path families — mimicking what a prior real install would have left
behind. This avoids depending on a real historical anvil version being checked out.

These tests exercise the installer via ``subprocess`` at the real entry point.
Pattern mirrors ``test_install_agent_prune_on_narrowing.py``. Distinct filename
per the #58 packaging convention.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the installer with ``args`` and capture text stdout+stderr.

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


def _families(target: Path, name: str) -> dict[str, Path]:
    """Return the four installer-owned path families for skill ``name``."""

    return {
        "anvil_skills": target / ".anvil" / "skills" / name,
        "pkg_mirror": target / ".anvil" / "anvil" / "skills" / name,
        "claude_shim": target / ".claude" / "skills" / f"anvil-{name}",
        # agent shims are a glob; represent the dir + prefix separately below.
    }


def _agent_shims(target: Path, name: str) -> set[Path]:
    agents_dir = target / ".claude" / "agents"
    if not agents_dir.is_dir():
        return set()
    return set(agents_dir.glob(f"anvil-{name}-*.md"))


def _inject_removed_skill(
    target: Path,
    name: str,
    *,
    with_agents: tuple[str, ...] = ("drafter", "reviewer", "reviser"),
) -> None:
    """Simulate a prior install that shipped ``name``, now removed upstream.

    Appends ``name`` to the manifest's ``installed_skills`` and materialises all
    four path families with marker content — exactly what a real prior install
    of ``name`` would have left behind.
    """

    manifest = _manifest_path(target)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if name not in data["installed_skills"]:
        data["installed_skills"].append(name)
    manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    for key, path in _families(target, name).items():
        path.mkdir(parents=True, exist_ok=True)
        (path / "marker.txt").write_text(f"{key} content for {name}\n")

    agents_dir = target / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for phase in with_agents:
        (agents_dir / f"anvil-{name}-{phase}.md").write_text(
            f"agent shim for {name} {phase}\n"
        )


def _assert_all_families_gone(target: Path, name: str) -> None:
    for key, path in _families(target, name).items():
        assert not path.exists(), (
            f"family '{key}' for removed skill '{name}' survived the prune: {path}"
        )
    assert not _agent_shims(target, name), (
        f"agent shims for removed skill '{name}' survived the prune: "
        f"{sorted(p.name for p in _agent_shims(target, name))}"
    )


# ---------------------------------------------------------------------------
# Full/default install prunes an upstream-removed skill (the #716 regression)
# ---------------------------------------------------------------------------


def test_full_install_prunes_removed_skill_all_four_families(
    tmp_path: Path,
) -> None:
    """A full/default reinstall reconciles a manifest that lists a gone skill.

    This is the exact 0.8.1 -> 0.9.0 pub/ scenario: no ``--skills=`` flag, a
    prior manifest listing a now-removed skill, and all four path families on
    disk. After the reinstall, every family is gone and the manifest no longer
    lists the removed name.
    """

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=memo", str(target)))
    _inject_removed_skill(target, "fake-removed-skill")

    result = _run(str(target))  # full/default install — NO --skills=
    _assert_ok(result)

    _assert_all_families_gone(target, "fake-removed-skill")
    assert "fake-removed-skill" not in _read_installed_skills(target), (
        "the reconciled manifest still lists the removed skill"
    )
    assert "path families removed" in result.stdout, (
        f"expected a Stage 7.6 prune note; got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# A narrower --skills= install prunes a removed skill too
# ---------------------------------------------------------------------------


def test_narrow_install_also_prunes_removed_skill(tmp_path: Path) -> None:
    """The prune fires regardless of flag shape — narrowed installs too.

    A removed skill should reconcile the same way whether the reinstall is full
    or narrowed; the authoritative signal is "in the prior manifest, absent from
    the current selection," not the flag shape.
    """

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=memo,paper", str(target)))
    _inject_removed_skill(target, "fake-removed-skill")

    result = _run("--skills=memo,paper", str(target))
    _assert_ok(result)

    _assert_all_families_gone(target, "fake-removed-skill")
    # memo and paper (still selected, still shipped) are untouched.
    assert (target / ".anvil" / "skills" / "memo").is_dir()
    assert (target / ".anvil" / "skills" / "paper").is_dir()


# ---------------------------------------------------------------------------
# SAFETY-CRITICAL: a consumer-authored skill never in any manifest survives
# ---------------------------------------------------------------------------


def test_consumer_authored_skill_survives_prune(tmp_path: Path) -> None:
    """A ``.anvil/skills/<custom>/`` anvil never shipped is NOT pruned.

    This is the highest-value negative test: it proves the prune keys on
    *provenance* (presence in a prior manifest's ``installed_skills``), not on a
    naive "on disk but not in the current selection" disk scan — which would
    wrongly delete a consumer's own custom skill directory.

    The custom skill is materialised on disk but deliberately NEVER added to the
    manifest's ``installed_skills``, so it has no anvil provenance. A removed
    (manifest-listed) skill is injected alongside it to prove the prune stage
    actually runs on this install — the custom dir must survive while the
    provenance-backed removed skill is pruned.
    """

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=memo", str(target)))

    # Consumer-authored skill: on disk, but NEVER in installed_skills.
    custom = target / ".anvil" / "skills" / "my-internal-doctype"
    custom.mkdir(parents=True)
    custom_body = "consumer-authored skill body — must survive reconciliation\n"
    (custom / "SKILL.md").write_text(custom_body, encoding="utf-8")
    # Also a matching Claude shim and agent shim the consumer might hand-author.
    custom_shim = target / ".claude" / "skills" / "anvil-my-internal-doctype"
    custom_shim.mkdir(parents=True)
    (custom_shim / "SKILL.md").write_text(custom_body, encoding="utf-8")
    custom_agent = (
        target / ".claude" / "agents" / "anvil-my-internal-doctype-drafter.md"
    )
    custom_agent.parent.mkdir(parents=True, exist_ok=True)
    custom_agent.write_text("consumer agent\n", encoding="utf-8")

    # A provenance-backed removed skill so the prune stage does fire this run.
    _inject_removed_skill(target, "fake-removed-skill")

    result = _run(str(target))
    _assert_ok(result)

    # The removed (manifest-provenanced) skill is pruned...
    _assert_all_families_gone(target, "fake-removed-skill")
    # ...but the consumer-authored skill (no manifest provenance) survives.
    assert custom.is_dir(), "prune deleted a consumer-authored skill directory"
    assert (custom / "SKILL.md").read_text(encoding="utf-8") == custom_body, (
        "prune disturbed a consumer-authored skill's contents"
    )
    assert custom_shim.is_dir(), (
        "prune deleted a consumer-authored .claude/skills shim"
    )
    assert custom_agent.exists(), (
        "prune deleted a consumer-authored agent shim"
    )


# ---------------------------------------------------------------------------
# --dry-run reports the plan and mutates nothing
# ---------------------------------------------------------------------------


def test_dry_run_reports_plan_and_writes_nothing(tmp_path: Path) -> None:
    """``--dry-run`` names the would-be-pruned skill and leaves disk untouched."""

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=memo", str(target)))
    _inject_removed_skill(target, "fake-removed-skill")

    # Snapshot the families before the dry-run.
    families = _families(target, "fake-removed-skill")
    shims_before = _agent_shims(target, "fake-removed-skill")

    result = _run_dry("--skills=memo", str(target))
    _assert_ok(result)

    assert "[dry-run] would prune" in result.stdout, (
        f"expected a '[dry-run] would prune ...' line; got:\n{result.stdout}"
    )
    assert "fake-removed-skill" in result.stdout, (
        "dry-run plan did not name the removed skill"
    )
    # Nothing was actually removed.
    for key, path in families.items():
        assert path.exists(), f"--dry-run removed family '{key}' from disk: {path}"
    assert _agent_shims(target, "fake-removed-skill") == shims_before, (
        "--dry-run removed agent shims from disk"
    )


# ---------------------------------------------------------------------------
# Fresh install (no prior manifest) is a silent no-op for the new stage
# ---------------------------------------------------------------------------


def test_fresh_install_no_prior_manifest_is_noop(tmp_path: Path) -> None:
    """A first-time install (no prior manifest) never prunes and never errors."""

    target = tmp_path / "target"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    assert "path families removed" not in result.stdout, (
        f"fresh install emitted a Stage 7.6 prune note (should be a no-op):\n"
        f"{result.stdout}"
    )
    # The Stage 7.6 header still prints (the stage runs), but the guard on a
    # missing prior manifest makes it inert.
    assert (target / ".anvil" / "skills" / "memo").is_dir()


# ---------------------------------------------------------------------------
# A still-selected skill in the prior manifest is never touched
# ---------------------------------------------------------------------------


def test_still_selected_skill_is_never_pruned(tmp_path: Path) -> None:
    """A skill in both the prior manifest and the current selection survives.

    The common case: unrelated skills on an unrelated reinstall. Nothing in
    ``installed_skills`` that is still selected may be pruned.
    """

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=memo,paper", str(target)))
    memo_dir = target / ".anvil" / "skills" / "memo"
    paper_dir = target / ".anvil" / "skills" / "paper"
    assert memo_dir.is_dir() and paper_dir.is_dir()

    result = _run("--skills=memo,paper", str(target))
    _assert_ok(result)

    assert memo_dir.is_dir(), "a still-selected skill (memo) was wrongly pruned"
    assert paper_dir.is_dir(), "a still-selected skill (paper) was wrongly pruned"
    assert "path families removed" not in result.stdout, (
        f"prune note fired with no removed skills:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Idempotence: rerun after a prune emits no further prune note
# ---------------------------------------------------------------------------


def test_idempotent_after_prune(tmp_path: Path) -> None:
    """Once the removed skill is pruned and gone from the manifest, reruns are quiet."""

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=memo", str(target)))
    _inject_removed_skill(target, "fake-removed-skill")

    first = _run(str(target))
    _assert_ok(first)
    assert "path families removed" in first.stdout
    _assert_all_families_gone(target, "fake-removed-skill")

    # Second run: the removed skill is no longer in the manifest, so nothing
    # to reconcile.
    second = _run(str(target))
    _assert_ok(second)
    assert "path families removed" not in second.stdout, (
        f"idempotent rerun emitted a prune note:\n{second.stdout}"
    )


# ---------------------------------------------------------------------------
# Sibling-prefix hazard: removing ip-uspto keeps ip-uspto-provisional shims
# ---------------------------------------------------------------------------


def test_sibling_prefix_removed_skill_spares_longer_sibling(
    tmp_path: Path,
) -> None:
    """Pruning a removed ``ip-uspto`` must not take out ``ip-uspto-provisional``.

    Exercises the longest-prefix resolver on the removal side: a bare
    ``anvil-ip-uspto-*.md`` glob would wrongly match the still-installed
    ``anvil-ip-uspto-provisional-*.md`` shims. The Stage 7.6 agent-shim leg
    resolves each shim to its longest-prefix owner across ALL_SKILLS +
    REMOVED_SKILLS, so the provisional shims resolve to the still-shipped
    ``ip-uspto-provisional`` and are spared.
    """

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=ip-uspto-provisional", str(target)))
    provisional_before = _agent_shims(target, "ip-uspto-provisional")
    assert provisional_before, "install did not write provisional agent shims"

    # Inject a bare ip-uspto shim + manifest entry as if a prior install shipped
    # ip-uspto (now treated as removed since the current selection omits it).
    manifest = _manifest_path(target)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if "ip-uspto" not in data["installed_skills"]:
        data["installed_skills"].append("ip-uspto")
    manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")
    bare = target / ".claude" / "agents" / "anvil-ip-uspto-drafter.md"
    bare.write_text("bare ip-uspto shim\n", encoding="utf-8")

    result = _run("--skills=ip-uspto-provisional", str(target))
    _assert_ok(result)

    assert not bare.exists(), "the bare ip-uspto agent shim was not pruned"
    # The longer sibling's shims must all survive.
    surviving = _agent_shims(target, "ip-uspto-provisional")
    assert provisional_before <= surviving, (
        "pruning ip-uspto wrongly removed ip-uspto-provisional shims: "
        f"missing {sorted(p.name for p in provisional_before - surviving)}"
    )
