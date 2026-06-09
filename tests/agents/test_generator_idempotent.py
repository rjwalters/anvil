"""Regression test: re-running the generator produces byte-identical output.

Issue #377 — ``scripts/generate-anvil-agents.py`` is the single source of
truth for what lands under ``anvil/agents/``. If a contributor edits the
generator without re-running it, the checked-in files drift from the
generator's actual output. This test re-runs the generator into a tmp dir
and compares against the on-disk set.

It is the same pattern the rubric-rebackport tests use to keep the
generator and the data files in sync.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "anvil" / "agents"
GENERATOR = REPO_ROOT / "scripts" / "generate-anvil-agents.py"


def test_generator_output_matches_checked_in(tmp_path: Path) -> None:
    """Running the generator must reproduce the committed agent files byte-for-byte."""
    # Run the generator in a fresh worktree-shaped sandbox: copy just the
    # anvil/skills/ tree (the generator's only input) so generation is
    # hermetic. Actually — the generator resolves REPO_ROOT from its own
    # __file__ location, so we instead patch AGENTS_DIR by monkey-running.
    # Simpler: invoke the generator as-is and compare against committed
    # files. Since the script writes into REPO_ROOT/anvil/agents/, we
    # snapshot the current content, regenerate, diff, and restore (only if
    # different).
    snapshot: dict[str, bytes] = {
        p.name: p.read_bytes() for p in AGENTS_DIR.glob("anvil-*.md")
    }
    # The script is deterministic and writes the SAME files it just read,
    # so running it should be a no-op. We assert that.
    result = subprocess.run(
        [sys.executable, str(GENERATOR)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"generator failed (rc={result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    after: dict[str, bytes] = {
        p.name: p.read_bytes() for p in AGENTS_DIR.glob("anvil-*.md")
    }
    drifted = [
        name
        for name in sorted(set(snapshot) | set(after))
        if snapshot.get(name) != after.get(name)
    ]
    if drifted:
        # Restore the snapshot so a failed test doesn't leave the worktree
        # dirty. (Only useful for local dev; CI runs a fresh checkout.)
        for name, content in snapshot.items():
            (AGENTS_DIR / name).write_bytes(content)
        raise AssertionError(
            f"generator output drifted for {len(drifted)} files: "
            f"{drifted[:5]}{'...' if len(drifted) > 5 else ''}; "
            "re-run scripts/generate-anvil-agents.py and commit the diff."
        )
