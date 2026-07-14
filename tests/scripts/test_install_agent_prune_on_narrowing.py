"""Regression tests: installer Stage 7.5 prunes stale agents on a narrowing.

Issue #685 (tractatus canary, 0.7.1 -> 0.8.0 upgrade, 2026-07-14). Companion to
#662/#675, which scoped Stage 7.5's *copy* to ``SELECTED_SKILLS`` but left an
explicit follow-up gap: re-running the installer with a **narrower** ``--skills=``
set after a **wider** prior install did not remove the now-out-of-scope
``anvil-<skill>-*.md`` files a previous install had already written into the
consumer's ``.claude/agents/``. Those stale shims kept registering in the agent
picker until manually deleted (tractatus PR #36).

The fix adds a prune pass after the copy loop that removes exactly the
``anvil-<skill>-*.md`` files under ``.claude/agents/`` that resolve (via the
same ``agent_skill_for`` longest-prefix resolver used by the copy filter) to a
**known** skill **not** in the current ``SELECTED_SKILLS``. Guardrails:

  * Skipped entirely on a full/unscoped install (``SELECTED_SKILLS ==
    ALL_SKILLS``): no "unselected skill" concept exists, so the pass is a no-op
    in the common case.
  * Non-anvil files (e.g. a sibling Loom install's ``loom-*.md`` shim) and
    shared/unprefixed anvil agents (``agent_skill_for`` -> ``""``) are never
    touched. Removal is per-file, never a directory blow-away.
  * ``--dry-run`` reports the count of files that *would* be removed and writes
    nothing (issue #81 honesty discipline).

Safety rationale: every ``anvil-<skill>-*.md`` file is an installer-owned
artifact (every byte originates from ``anvil/agents/`` in the source repo and is
recopied verbatim on each install), so auto-removal loses no consumer-authored
content — unlike the companion #684 (tracked ``.anvil/__pycache__``), which
stays hint-only because it may touch consumer git state.

These tests exercise the installer via ``subprocess`` at the real entry point.
Pattern mirrors ``test_install_agents_skill_filter.py``. Distinct filename per
the #58 packaging convention. Assertions prefer set-membership / set-difference
over hard-coded registry totals, since the agent roster is actively growing.
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Narrowing prunes the now-out-of-scope skill's agents
# ---------------------------------------------------------------------------


def test_narrowing_reinstall_prunes_deselected_skill_agents(
    tmp_path: Path,
) -> None:
    """A wide install then a narrower re-install removes the dropped skill.

    ``--skills=pub,memo`` writes both skills' shims; a follow-up
    ``--skills=pub`` must prune the ``anvil-memo-*.md`` files and keep the
    ``anvil-pub-*.md`` files (still present, refreshed by the copy step).
    """

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=pub,memo", str(target)))
    wide = _installed_agents(target)
    memo_shims = {a for a in wide if a.startswith("anvil-memo-")}
    pub_shims = {a for a in wide if a.startswith("anvil-pub-")}
    assert memo_shims, "wide install did not write any anvil-memo-* shims"
    assert pub_shims, "wide install did not write any anvil-pub-* shims"

    result = _run("--skills=pub", str(target))
    _assert_ok(result)

    narrowed = _installed_agents(target)
    assert narrowed == pub_shims, (
        f"narrowing to --skills=pub should leave exactly the pub shims; "
        f"got {sorted(narrowed)}"
    )
    assert not (narrowed & memo_shims), (
        f"narrowing did not prune the deselected memo shims: "
        f"{sorted(narrowed & memo_shims)}"
    )
    assert "removed" in result.stdout and "stale agent file" in result.stdout, (
        f"expected a prune note on the narrowing re-install; got:\n"
        f"{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Prune never touches non-anvil consumer files
# ---------------------------------------------------------------------------


def test_prune_leaves_non_anvil_files_untouched(tmp_path: Path) -> None:
    """A ``loom-*.md`` shim survives a narrowing re-install untouched."""

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=pub,memo", str(target)))

    agents_dir = target / ".claude" / "agents"
    loom_shim = agents_dir / "loom-foo.md"
    loom_content = "loom shim body — must survive the prune\n"
    loom_shim.write_text(loom_content, encoding="utf-8")

    result = _run("--skills=pub", str(target))
    _assert_ok(result)

    assert loom_shim.exists(), "prune removed a non-anvil (loom-*) agent shim"
    assert loom_shim.read_text(encoding="utf-8") == loom_content, (
        "prune disturbed the contents of a non-anvil agent shim"
    )
    # And the memo shims were still pruned.
    narrowed = _installed_agents(target)
    assert not {a for a in narrowed if a.startswith("anvil-memo-")}, (
        "memo shims survived the narrowing prune"
    )


# ---------------------------------------------------------------------------
# Prune never touches shared/unprefixed anvil agents
# ---------------------------------------------------------------------------


def test_prune_leaves_unresolved_anvil_named_files_untouched(
    tmp_path: Path,
) -> None:
    """An ``anvil-*.md`` file that resolves to no known skill is kept.

    ``agent_skill_for`` returns ``""`` for such a file (shared/unprefixed
    framework agent, or a consumer hand-authored file with an ``anvil-``-looking
    name that matches no real skill), so the prune pass must leave it in place
    even on a narrowing re-install.
    """

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=pub,memo", str(target)))

    agents_dir = target / ".claude" / "agents"
    shared = agents_dir / "anvil-notaskill-helper.md"
    shared_content = "shared/unresolved anvil agent — must not be pruned\n"
    shared.write_text(shared_content, encoding="utf-8")

    result = _run("--skills=pub", str(target))
    _assert_ok(result)

    assert shared.exists(), (
        "prune removed an anvil-*.md file that resolves to no known skill"
    )
    assert shared.read_text(encoding="utf-8") == shared_content, (
        "prune disturbed a shared/unresolved anvil-*.md file"
    )


# ---------------------------------------------------------------------------
# Full install performs no pruning (widen-back-out)
# ---------------------------------------------------------------------------


def test_full_install_after_narrowing_prunes_nothing(tmp_path: Path) -> None:
    """A full (no ``--skills=``) install never triggers the prune pass.

    After a narrower ``--skills=pub`` install, widening back to a full install
    must add the rest of the registry and remove nothing — the prune guard
    (``SELECTED_SKILLS == ALL_SKILLS``) makes the pass a no-op.
    """

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=pub", str(target)))

    result = _run(str(target))
    _assert_ok(result)

    # No prune note should fire on a full install.
    assert "stale agent file" not in result.stdout, (
        f"full install emitted a prune note (should be a no-op):\n"
        f"{result.stdout}"
    )
    # The full registry is present (superset of the earlier pub-only set).
    installed = _installed_agents(target)
    assert {a for a in installed if a.startswith("anvil-memo-")}, (
        "widening to a full install did not restore the memo shims"
    )


# ---------------------------------------------------------------------------
# --dry-run reports the count and writes nothing
# ---------------------------------------------------------------------------


def test_dry_run_narrowing_reports_count_and_writes_nothing(
    tmp_path: Path,
) -> None:
    """``--dry-run`` on a narrowing reports the stale count and prunes nothing."""

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=pub,memo", str(target)))
    before = _installed_agents(target)
    memo_shims = {a for a in before if a.startswith("anvil-memo-")}
    assert memo_shims, "wide install did not write any anvil-memo-* shims"

    result = subprocess.run(
        [
            "bash",
            str(INSTALLER),
            "--dry-run",
            "--skills=pub",
            str(target),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(result)

    assert "[dry-run] would remove" in result.stdout, (
        f"expected a '[dry-run] would remove N stale agent file(s)' line; "
        f"got:\n{result.stdout}"
    )
    # Nothing was actually removed.
    after = _installed_agents(target)
    assert after == before, (
        f"--dry-run narrowing mutated .claude/agents/; before={sorted(before)} "
        f"after={sorted(after)}"
    )
    assert memo_shims <= after, "--dry-run removed memo shims from disk"


# ---------------------------------------------------------------------------
# Idempotence: a repeated identical selection prunes nothing
# ---------------------------------------------------------------------------


def test_repeated_identical_selection_is_idempotent(tmp_path: Path) -> None:
    """Two consecutive identical ``--skills=pub`` runs prune 0 files."""

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=pub", str(target)))
    first = _installed_agents(target)

    result = _run("--skills=pub", str(target))
    _assert_ok(result)
    second = _installed_agents(target)

    assert second == first, (
        f"second identical install changed the agent set; "
        f"first={sorted(first)} second={sorted(second)}"
    )
    # No stale files existed to prune on the second run.
    assert "stale agent file" not in result.stdout, (
        f"idempotent re-run emitted a prune note:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# ip-uspto / ip-uspto-provisional collision under the prune path
# ---------------------------------------------------------------------------


def test_narrowing_respects_ip_uspto_prefix_collision(tmp_path: Path) -> None:
    """Narrowing to ``ip-uspto`` prunes provisional shims but keeps its own.

    Exercises the longest-prefix-match collision on the prune side: a prior
    ``--skills=ip-uspto,ip-uspto-provisional`` install writes both skills'
    shims; narrowing to ``--skills=ip-uspto`` must remove exactly the
    ``anvil-ip-uspto-provisional-*`` files and keep the bare
    ``anvil-ip-uspto-*`` files.
    """

    target = tmp_path / "target"
    target.mkdir()

    _assert_ok(_run("--skills=ip-uspto,ip-uspto-provisional", str(target)))
    wide = _installed_agents(target)
    provisional = {
        a for a in wide if a.startswith("anvil-ip-uspto-provisional-")
    }
    bare = {
        a
        for a in wide
        if a.startswith("anvil-ip-uspto-")
        and not a.startswith("anvil-ip-uspto-provisional-")
    }
    assert provisional and bare, (
        "wide install did not write both ip-uspto and provisional shims"
    )

    result = _run("--skills=ip-uspto", str(target))
    _assert_ok(result)

    narrowed = _installed_agents(target)
    assert bare <= narrowed, (
        f"narrowing to ip-uspto wrongly pruned bare ip-uspto shims; "
        f"missing: {sorted(bare - narrowed)}"
    )
    assert not (narrowed & provisional), (
        f"narrowing to ip-uspto failed to prune provisional shims: "
        f"{sorted(narrowed & provisional)}"
    )


# ---------------------------------------------------------------------------
# Fresh install with no prior .claude/agents/ is a silent no-op for the prune
# ---------------------------------------------------------------------------


def test_fresh_narrow_install_no_prior_agents_dir(tmp_path: Path) -> None:
    """A first-time ``--skills=pub`` install (no prior agents dir) works.

    The prune pass must be a silent no-op when ``.claude/agents/`` did not
    pre-exist — not an error — while the copy step still installs the pub set.
    """

    target = tmp_path / "target"
    target.mkdir()

    result = _run("--skills=pub", str(target))
    _assert_ok(result)

    installed = _installed_agents(target)
    assert installed == {
        "anvil-pub-auditor.md",
        "anvil-pub-drafter.md",
        "anvil-pub-figurer.md",
        "anvil-pub-reviewer.md",
        "anvil-pub-reviser.md",
    }, f"fresh --skills=pub install produced the wrong set: {sorted(installed)}"
    assert "stale agent file" not in result.stdout, (
        f"fresh install emitted a prune note:\n{result.stdout}"
    )
