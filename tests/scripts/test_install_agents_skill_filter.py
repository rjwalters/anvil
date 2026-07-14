"""Regression tests: installer Stage 7.5 scopes the agents copy by --skills=.

Issue #662: a single-skill install (the tractatus canary, 2026-07-13, ran
``--skills=pub`` — the skill was renamed ``pub`` → ``paper`` under #694; these
tests exercise the current ``--skills=paper``) copied **all 54**
``anvil-<skill>-<phase>.md`` subagent shims into the consumer's
``.claude/agents/``, even though only the 5 ``anvil-paper-*.md`` files belong to
the selected skill. The other ~49 register agents for skills the consumer never
installed — agent-picker noise and a larger-than-necessary write footprint that
contradicts the ``--skills=`` flag's own "strict subset" framing.

The fix scopes Stage 7.5's copy to ``SELECTED_SKILLS``:

  * Agent filenames follow ``anvil-<skill>-<phase>.md``; each ``<skill>``
    matches a directory under ``anvil/skills/`` (the same ``ALL_SKILLS``
    enumeration Stage 4 builds).
  * The resolver strips the ``anvil-`` prefix and ``.md`` suffix, then finds
    the **longest** skill name in ``ALL_SKILLS`` that is a ``-``-delimited
    prefix of what remains — so ``anvil-ip-uspto-provisional-drafter.md``
    resolves to ``ip-uspto-provisional``, **not** the shorter ``ip-uspto``.
    This is the load-bearing collision case: ``ip-uspto`` and
    ``ip-uspto-provisional`` share a filename prefix, and a naive
    substring/glob filter would leak the provisional shims into an
    ``ip-uspto``-only install.
  * Any agent file whose name resolves to no known skill is copied
    unconditionally (defensive default for a future shared/framework agent;
    no such file exists today).
  * ``--dry-run`` reports the **filtered** count and writes nothing (issue #81
    honesty discipline).
  * Non-anvil files already under the consumer's ``.claude/agents/`` (e.g. a
    sibling Loom install's ``loom-*.md`` shim) are left untouched (per-file
    ``cp``, not ``replace_tree``).

Pruning previously-installed, now-out-of-scope agents on a narrowing
re-install is explicitly OUT OF SCOPE for #662.

These tests exercise the installer via ``subprocess`` so the contract is
enforced at the real entry point a consumer hits. Pattern mirrors
``test_install_theme_scaffold.py``. Distinct filename per the #58 packaging
convention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

SRC_AGENTS = REPO_ROOT / "anvil" / "agents"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the installer with ``args`` and capture text stdout+stderr.

    ``--no-sync`` keeps the tests independent of uv availability and fast
    (Stage 10.5 is a convenience, not part of the filter contract under test).
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


def _installed_agents(target: Path) -> set[str]:
    agents_dir = target / ".claude" / "agents"
    if not agents_dir.is_dir():
        return set()
    return {p.name for p in agents_dir.glob("*.md")}


def _all_source_agents() -> set[str]:
    return {p.name for p in SRC_AGENTS.glob("anvil-*.md")}


# ---------------------------------------------------------------------------
# Source-tree shape (sanity: the mapping this fix relies on)
# ---------------------------------------------------------------------------


def test_source_ships_the_expected_agent_registry() -> None:
    """The source registry is 64 ``anvil-<skill>-<phase>.md`` files.

    This pins the total the full-install no-regression test compares against.
    If the registry grows/shrinks, update this and the full-install count in
    lockstep — that's the intended coupling. (Grew from 54 to 59 under issue
    #686, which added the 5 ``anvil-primer-*.md`` lifecycle agents; grew from
    59 to 64 under issue #697/#706, which added the 5 ``anvil-spec-*.md``
    lifecycle agents.)
    """

    assert len(_all_source_agents()) == 64, (
        "expected 64 anvil-*.md source agents; the registry changed — update "
        "this test and test_full_install_still_ships_all_agents together"
    )


# ---------------------------------------------------------------------------
# Single-skill install: only that skill's agents
# ---------------------------------------------------------------------------


def test_single_skill_install_scopes_agents(tmp_path: Path) -> None:
    """``--skills=paper`` installs exactly the 5 ``anvil-paper-*.md`` files."""

    target = tmp_path / "paper-target"
    target.mkdir()

    result = _run("--skills=paper", str(target))
    _assert_ok(result)

    installed = _installed_agents(target)
    assert installed == {
        "anvil-paper-auditor.md",
        "anvil-paper-drafter.md",
        "anvil-paper-figurer.md",
        "anvil-paper-reviewer.md",
        "anvil-paper-reviser.md",
    }, (
        f"--skills=paper installed the wrong agent set: {sorted(installed)}; "
        f"stdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Longest-prefix-match collision: ip-uspto vs ip-uspto-provisional
# ---------------------------------------------------------------------------


def test_ip_uspto_excludes_provisional_shims(tmp_path: Path) -> None:
    """``--skills=ip-uspto`` must NOT leak ``anvil-ip-uspto-provisional-*``.

    The load-bearing regression case: a naive substring/glob filter would
    match both prefixes. Longest-prefix, ``-``-delimited matching resolves the
    provisional shims to their own skill and excludes them here.
    """

    target = tmp_path / "ipu-target"
    target.mkdir()

    result = _run("--skills=ip-uspto", str(target))
    _assert_ok(result)

    installed = _installed_agents(target)
    assert installed == {
        "anvil-ip-uspto-auditor.md",
        "anvil-ip-uspto-drafter.md",
        "anvil-ip-uspto-figurer.md",
        "anvil-ip-uspto-reviewer.md",
        "anvil-ip-uspto-reviser.md",
    }, (
        f"--skills=ip-uspto installed the wrong agent set: {sorted(installed)}"
    )
    leaked = {a for a in installed if a.startswith("anvil-ip-uspto-provisional-")}
    assert not leaked, (
        f"--skills=ip-uspto leaked provisional shims (longest-prefix-match "
        f"regression): {sorted(leaked)}"
    )


def test_ip_uspto_provisional_installs_only_its_own(tmp_path: Path) -> None:
    """``--skills=ip-uspto-provisional`` installs only its own 5 files."""

    target = tmp_path / "ipp-target"
    target.mkdir()

    result = _run("--skills=ip-uspto-provisional", str(target))
    _assert_ok(result)

    installed = _installed_agents(target)
    assert installed == {
        "anvil-ip-uspto-provisional-auditor.md",
        "anvil-ip-uspto-provisional-drafter.md",
        "anvil-ip-uspto-provisional-figurer.md",
        "anvil-ip-uspto-provisional-reviewer.md",
        "anvil-ip-uspto-provisional-reviser.md",
    }, (
        f"--skills=ip-uspto-provisional installed the wrong agent set: "
        f"{sorted(installed)}"
    )
    # And no bare ip-uspto (non-provisional) shims should have leaked in.
    bare = {
        a
        for a in installed
        if a.startswith("anvil-ip-uspto-")
        and not a.startswith("anvil-ip-uspto-provisional-")
    }
    assert not bare, (
        f"--skills=ip-uspto-provisional leaked bare ip-uspto shims: "
        f"{sorted(bare)}"
    )


# ---------------------------------------------------------------------------
# Multi-skill install: the union
# ---------------------------------------------------------------------------


def test_multi_skill_install_is_the_union(tmp_path: Path) -> None:
    """``--skills=paper,memo`` installs the union (5 + 4 = 9 files)."""

    target = tmp_path / "multi-target"
    target.mkdir()

    result = _run("--skills=paper,memo", str(target))
    _assert_ok(result)

    installed = _installed_agents(target)
    expected = {
        "anvil-paper-auditor.md",
        "anvil-paper-drafter.md",
        "anvil-paper-figurer.md",
        "anvil-paper-reviewer.md",
        "anvil-paper-reviser.md",
        "anvil-memo-drafter.md",
        "anvil-memo-figurer.md",
        "anvil-memo-reviewer.md",
        "anvil-memo-reviser.md",
    }
    assert installed == expected, (
        f"--skills=paper,memo installed {sorted(installed)}, "
        f"expected the union {sorted(expected)}"
    )


# ---------------------------------------------------------------------------
# Full install: no regression (all 64)
# ---------------------------------------------------------------------------


def test_full_install_still_ships_all_agents(tmp_path: Path) -> None:
    """A no-``--skills=`` install still copies every source agent (all 64)."""

    target = tmp_path / "full-target"
    target.mkdir()

    result = _run(str(target))
    _assert_ok(result)

    installed = _installed_agents(target)
    assert installed == _all_source_agents(), (
        "full install (no --skills=) did not ship the complete agent "
        f"registry; missing: "
        f"{sorted(_all_source_agents() - installed)}; extra: "
        f"{sorted(installed - _all_source_agents())}"
    )


# ---------------------------------------------------------------------------
# --dry-run honesty (issue #81): filtered count, no writes
# ---------------------------------------------------------------------------


def test_dry_run_reports_filtered_count_and_writes_nothing(
    tmp_path: Path,
) -> None:
    """``--dry-run --skills=paper`` reports 5 agent files and writes nothing."""

    target = tmp_path / "dry-target"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--skills=paper", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(result)

    assert "[dry-run] copy 5 agent files" in result.stdout, (
        "expected the filtered '[dry-run] copy 5 agent files ...' action line "
        f"for --skills=paper; got:\n{result.stdout}"
    )
    assert not (target / ".claude").exists(), (
        "--dry-run wrote .claude/ to the target"
    )
    # The post-action confirmation must not fire under --dry-run.
    assert "subagent registration(s) installed" not in result.stdout, (
        "--dry-run emitted the lying 'subagent registration(s) installed' "
        f"confirmation; got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Per-file copy: non-anvil consumer agents survive
# ---------------------------------------------------------------------------


def test_preexisting_non_anvil_agent_survives(tmp_path: Path) -> None:
    """A pre-existing ``loom-*.md`` shim is left untouched by the install."""

    target = tmp_path / "loom-target"
    agents_dir = target / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    loom_shim = agents_dir / "loom-foo.md"
    loom_content = "loom shim body — must not be touched\n"
    loom_shim.write_text(loom_content, encoding="utf-8")

    result = _run("--skills=paper", str(target))
    _assert_ok(result)

    assert loom_shim.read_text(encoding="utf-8") == loom_content, (
        "installer disturbed a pre-existing non-anvil (loom-*) agent shim"
    )
    # The paper agents landed alongside it.
    assert "anvil-paper-drafter.md" in _installed_agents(target), (
        "paper agents were not installed alongside the pre-existing loom shim"
    )


# ---------------------------------------------------------------------------
# Comment-block correction guard
# ---------------------------------------------------------------------------


def test_stage_7_5_comment_reflects_filtered_behavior() -> None:
    """Stage 7.5's design rationale must not still claim "NOT scoped".

    The pre-#662 comment asserted the agents copy was "NOT scoped by --skills="
    and framed the narrowed-install case as "purely a documentation / dev
    path." Both claims are now wrong; the comment must describe the filtered
    behavior and the longest-prefix-match collision hazard.
    """

    script = INSTALLER.read_text(encoding="utf-8")

    assert "the agents/ copy is NOT scoped by --skills=" not in script, (
        "Stage 7.5 comment still claims the agents copy is NOT scoped by "
        "--skills= (the pre-#662 rationale)"
    )
    assert "the agents/ copy IS scoped by --skills=" in script, (
        "Stage 7.5 comment does not document the new filtered behavior"
    )
    assert "ip-uspto-provisional" in script, (
        "Stage 7.5 comment does not flag the ip-uspto / ip-uspto-provisional "
        "longest-prefix-match collision hazard"
    )
