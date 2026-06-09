"""Install smoke tests: ``install-anvil.sh`` copies anvil-*.md agents.

Issue #377 — Stage 7.5 in ``scripts/install-anvil.sh`` mirrors the
per-skill shim copy by writing ``.claude/agents/anvil-*.md`` files into the
consumer's tree. These tests run the installer end-to-end (mirroring the
pattern in ``tests/scripts/test_install_shim_depth.py``) so the contract
is enforced at the real entry point a consumer hits.

The tests do NOT attempt to dispatch a subagent — the harness integration
is out of scope for a pure pytest run. They DO verify:

- The agent files land in ``.claude/agents/`` with the right count.
- A pre-existing ``loom-*.md`` (or any other non-anvil) agent is preserved
  through an install (we copy by pattern, not by ``rm -rf``).
- Re-install is idempotent (no errors, files remain).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"
AGENTS_DIR = REPO_ROOT / "anvil" / "agents"


def _run_install(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Run the installer non-interactively with --no-sync (no venv side effects)."""
    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", *extra, str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_install_copies_all_agent_files(tmp_path: Path) -> None:
    """Every anvil-*.md under anvil/agents/ lands in <target>/.claude/agents/."""
    target = tmp_path / "agents-install-target"
    target.mkdir()

    result = _run_install(target)

    assert result.returncode == 0, (
        f"installer failed (rc={result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    dst_agents = target / ".claude" / "agents"
    assert dst_agents.is_dir(), (
        f"expected {dst_agents} after install; stdout: {result.stdout}"
    )

    src_count = sum(1 for _ in AGENTS_DIR.glob("anvil-*.md"))
    dst_count = sum(1 for _ in dst_agents.glob("anvil-*.md"))
    assert dst_count == src_count, (
        f"agent count mismatch: src={src_count} dst={dst_count}; "
        f"installer stdout:\n{result.stdout}"
    )

    # Spot-check filename round-trip (every source agent file appears in dst
    # with the same name).
    src_stems = {p.stem for p in AGENTS_DIR.glob("anvil-*.md")}
    dst_stems = {p.stem for p in dst_agents.glob("anvil-*.md")}
    assert src_stems == dst_stems, (
        f"agent stem mismatch:\n  src - dst: {sorted(src_stems - dst_stems)}\n"
        f"  dst - src: {sorted(dst_stems - src_stems)}"
    )


def test_install_preserves_non_anvil_agents(tmp_path: Path) -> None:
    """A pre-existing ``loom-*.md`` agent survives the install.

    The installer copies by pattern (``anvil-*.md``), not by ``rm -rf
    .claude/agents/``. This is load-bearing because anvil coexists with
    loom in the same consumer repo (see CLAUDE.md "Coexistence" section);
    a destructive install would wipe loom's agent set.
    """
    target = tmp_path / "preserves-target"
    target.mkdir()

    # First install creates .claude/agents/.
    first = _run_install(target)
    assert first.returncode == 0, first.stderr

    # Plant a loom-style agent file that anvil must not touch.
    loom_path = target / ".claude" / "agents" / "loom-fake-test-agent.md"
    loom_path.parent.mkdir(parents=True, exist_ok=True)
    loom_path.write_text(
        "---\nname: loom-fake-test-agent\ndescription: do not touch\ntools: Read\n---\nbody\n",
        encoding="utf-8",
    )

    # Re-install. Anvil-agent files should refresh; the loom file should
    # remain untouched.
    second = _run_install(target)
    assert second.returncode == 0, second.stderr

    assert loom_path.exists(), (
        f"non-anvil agent was destroyed by install: {loom_path}\n"
        f"installer stdout:\n{second.stdout}"
    )
    # And it should not have been overwritten — we just check the body
    # still contains our sentinel.
    assert "do not touch" in loom_path.read_text(encoding="utf-8")


def test_install_is_idempotent(tmp_path: Path) -> None:
    """Two back-to-back installs land the same agent set with no errors."""
    target = tmp_path / "idempotent-target"
    target.mkdir()

    first = _run_install(target)
    assert first.returncode == 0, first.stderr
    dst_agents = target / ".claude" / "agents"
    first_set = {p.name for p in dst_agents.glob("anvil-*.md")}

    second = _run_install(target)
    assert second.returncode == 0, second.stderr
    second_set = {p.name for p in dst_agents.glob("anvil-*.md")}

    assert first_set == second_set, (
        f"idempotent re-install produced a different agent set:\n"
        f"  first  - second: {sorted(first_set - second_set)}\n"
        f"  second - first : {sorted(second_set - first_set)}"
    )


def test_dry_run_reports_agent_count(tmp_path: Path) -> None:
    """``--dry-run`` surfaces the planned agent copy count in stdout.

    Mirrors the dry-run-honesty contract enforced by
    ``test_install_dry_run_honesty.py`` for skills: the operator sees what
    a real run would do without ANY side effect on disk.
    """
    target = tmp_path / "dryrun-target"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", "--dry-run", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr

    # The dry-run line shape: "[dry-run] copy N agent files from <src> to <dst>"
    src_count = sum(1 for _ in AGENTS_DIR.glob("anvil-*.md"))
    assert (
        f"copy {src_count} agent files" in result.stdout
    ), (
        f"expected agent dry-run line in stdout; got:\n{result.stdout}"
    )

    # No side effect: .claude/agents/ should not exist after a dry-run.
    dst = target / ".claude" / "agents"
    assert not dst.exists(), (
        f"dry-run wrote to disk (.claude/agents/ exists): {dst}"
    )
