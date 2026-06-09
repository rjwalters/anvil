"""Canonical-path tests for ``anvil.lib.latest_resolution`` (issue #382).

The module was promoted from ``anvil/skills/memo/lib/`` to ``anvil/lib/``
when deck/slides/proposal became the 2nd-4th consumers of the project-org
primitives. The full behavioral corpus lives at
``anvil/skills/memo/tests/test_latest_resolution.py`` and continues to
run against the canonical implementation through the memo back-compat
shim (the shim star-imports the same function objects). This file pins
the two promotion contracts:

1. The canonical ``anvil.lib`` import path works directly.
2. The memo shim re-exports the SAME objects (not copies), so behavior
   cannot drift between the two import paths.

Plus a representative behavior check per public API entry so a broken
move (e.g., a stale duplicate) fails here even if the shim hides it.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.latest_resolution import LATEST, resolve_latest


def test_shim_reexports_same_objects() -> None:
    from anvil.skills.memo.lib import latest_resolution as shim

    assert shim.resolve_latest is resolve_latest
    assert shim.LATEST == LATEST


def test_walk_to_highest_fallback(tmp_path: Path) -> None:
    """No symlink, no .latest dir → highest-numbered version dir wins."""
    thread = tmp_path / "acme"
    for n in (1, 2, 10):
        (thread / f"acme.{n}").mkdir(parents=True)
    resolved = resolve_latest(thread, "acme")
    assert resolved is not None
    assert resolved.name == "acme.10"


def test_pinned_symlink_wins_over_highest(tmp_path: Path) -> None:
    thread = tmp_path / "acme"
    for n in (1, 2, 3):
        (thread / f"acme.{n}").mkdir(parents=True)
    (thread / f"acme.{LATEST}").symlink_to(thread / "acme.2")
    resolved = resolve_latest(thread, "acme")
    assert resolved is not None
    assert resolved.resolve() == (thread / "acme.2").resolve()


def test_no_version_dirs_returns_none(tmp_path: Path) -> None:
    thread = tmp_path / "empty-thread"
    thread.mkdir()
    assert resolve_latest(thread, "empty-thread") is None
