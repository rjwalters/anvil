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

Issue #473 added the **writer half** (``update_latest_symlinks``) next
to the resolver; its unit corpus lives here (the canonical home — the
writer never had a memo-local life).
"""

from __future__ import annotations

import os
from pathlib import Path

from anvil.lib.latest_resolution import (
    ACTION_CREATED,
    ACTION_PINNED,
    ACTION_REFUSED_REAL_DIR,
    ACTION_REPOINTED,
    ACTION_SKIPPED,
    ACTION_UNCHANGED,
    LATEST,
    resolve_latest,
    update_latest_symlinks,
)


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


# ---------------------------------------------------------------------------
# Writer half (issue #473): update_latest_symlinks
# ---------------------------------------------------------------------------


def _mk_thread(tmp_path: Path, slug: str, ns=(1, 2, 3), review_ns=()) -> Path:
    thread = tmp_path / slug
    thread.mkdir()
    for n in ns:
        (thread / f"{slug}.{n}").mkdir()
    for n in review_ns:
        (thread / f"{slug}.{n}.review").mkdir()
    return thread


def _age_symlink(link: Path, seconds: float = 1000.0) -> None:
    """Backdate a symlink's own mtime (lstat) below its siblings'.

    Reproduces the steady-lifecycle shape: the link was last set before
    the newest version dir was written.
    """
    past = link.lstat().st_mtime - seconds
    os.utime(link, (past, past), follow_symlinks=False)


def _by_name(updates) -> dict:
    return {u.link_name: u for u in updates}


def test_writer_fresh_create_both_families(tmp_path: Path) -> None:
    """Fresh thread (the PerfectCan canary shape): both symlinks created."""
    thread = _mk_thread(tmp_path, "acme", ns=(1, 2, 3), review_ns=(1, 2))
    updates = _by_name(update_latest_symlinks(thread, "acme"))
    assert updates["acme.latest"].action == ACTION_CREATED
    assert os.readlink(thread / "acme.latest") == "acme.3"
    assert updates["acme.latest.review"].action == ACTION_CREATED
    assert os.readlink(thread / "acme.latest.review") == "acme.2.review"
    # Relative targets — the documented ln -sfn idiom.
    assert not Path(os.readlink(thread / "acme.latest")).is_absolute()


def test_writer_repoints_superseded_tracking_link(tmp_path: Path) -> None:
    """The steady-lifecycle tracking path (#473 AC1).

    The link points at the immediately-superseded version and predates
    the new highest dir → re-pointed without operator action.
    """
    thread = _mk_thread(tmp_path, "acme", ns=(1, 2))
    link = thread / "acme.latest"
    link.symlink_to("acme.2")
    _age_symlink(link)
    (thread / "acme.3").mkdir()  # the lifecycle's new version write
    updates = _by_name(update_latest_symlinks(thread, "acme"))
    assert updates["acme.latest"].action == ACTION_REPOINTED
    assert os.readlink(link) == "acme.3"


def test_writer_preserves_pin_set_after_newer_version(tmp_path: Path) -> None:
    """#288 pin AC: a link set to non-highest AFTER the newer version
    existed (its lstat mtime >= the highest dir's) is an operator pin."""
    thread = _mk_thread(tmp_path, "acme", ns=(1, 2, 3))
    link = thread / "acme.latest"
    link.symlink_to("acme.2")  # created after acme.3 → deliberate pin
    updates = _by_name(update_latest_symlinks(thread, "acme"))
    assert updates["acme.latest"].action == ACTION_PINNED
    assert os.readlink(link) == "acme.2"


def test_writer_preserves_deep_lag_pin_even_when_link_is_old(
    tmp_path: Path,
) -> None:
    """A link lagging by more than one version is a pin regardless of
    mtime — pins survive subsequent version writes (durability)."""
    thread = _mk_thread(tmp_path, "acme", ns=(1, 2))
    link = thread / "acme.latest"
    link.symlink_to("acme.1")
    _age_symlink(link)
    (thread / "acme.3").mkdir()
    updates = _by_name(update_latest_symlinks(thread, "acme"))
    assert updates["acme.latest"].action == ACTION_PINNED
    assert os.readlink(link) == "acme.1"


def test_writer_force_repoints_pin(tmp_path: Path) -> None:
    thread = _mk_thread(tmp_path, "acme", ns=(1, 2, 3))
    link = thread / "acme.latest"
    link.symlink_to("acme.2")
    updates = _by_name(update_latest_symlinks(thread, "acme", force=True))
    assert updates["acme.latest"].action == ACTION_REPOINTED
    assert os.readlink(link) == "acme.3"


def test_writer_unchanged_is_idempotent_noop(tmp_path: Path) -> None:
    thread = _mk_thread(tmp_path, "acme", ns=(1, 2, 3), review_ns=(2,))
    update_latest_symlinks(thread, "acme")
    updates = _by_name(update_latest_symlinks(thread, "acme"))
    assert updates["acme.latest"].action == ACTION_UNCHANGED
    assert updates["acme.latest.review"].action == ACTION_UNCHANGED


def test_writer_per_family_independence(tmp_path: Path) -> None:
    """`.latest` and `.latest.review` are independent: the review link
    may lag the version link by one (the studio heirloom shape)."""
    thread = _mk_thread(tmp_path, "memo", ns=(1, 2, 3, 4, 5), review_ns=(4,))
    updates = _by_name(update_latest_symlinks(thread, "memo"))
    assert os.readlink(thread / "memo.latest") == "memo.5"
    assert os.readlink(thread / "memo.latest.review") == "memo.4.review"
    assert updates["memo.latest"].action == ACTION_CREATED
    assert updates["memo.latest.review"].action == ACTION_CREATED


def test_writer_repairs_dangling_symlink(tmp_path: Path) -> None:
    thread = _mk_thread(tmp_path, "acme", ns=(1, 2, 3))
    link = thread / "acme.latest"
    link.symlink_to("acme.9")  # target never existed → dangling
    updates = _by_name(update_latest_symlinks(thread, "acme"))
    assert updates["acme.latest"].action == ACTION_REPOINTED
    assert os.readlink(link) == "acme.3"


def test_writer_never_replaces_real_directory(tmp_path: Path) -> None:
    thread = _mk_thread(tmp_path, "acme", ns=(1, 2))
    (thread / "acme.latest").mkdir()  # shape 2: a real dir, not a symlink
    for force in (False, True):
        updates = _by_name(update_latest_symlinks(thread, "acme", force=force))
        assert updates["acme.latest"].action == ACTION_REFUSED_REAL_DIR
        assert (thread / "acme.latest").is_dir()
        assert not (thread / "acme.latest").is_symlink()


def test_writer_empty_thread_dir_is_noop(tmp_path: Path) -> None:
    thread = tmp_path / "empty"
    thread.mkdir()
    assert update_latest_symlinks(thread, "empty") == []


def test_writer_missing_thread_dir_is_noop(tmp_path: Path) -> None:
    assert update_latest_symlinks(tmp_path / "nope", "nope") == []


def test_writer_repoints_existing_tag_family_only(tmp_path: Path) -> None:
    """An already-existing `.latest.<tag>` family is maintained; absent
    tag families are never invented."""
    thread = _mk_thread(tmp_path, "acme", ns=(1, 2))
    (thread / "acme.1.design").mkdir()
    (thread / "acme.2.design").mkdir()
    (thread / "acme.1.audit").mkdir()
    link = thread / "acme.latest.design"
    link.symlink_to("acme.1.design")
    _age_symlink(link)
    updates = _by_name(update_latest_symlinks(thread, "acme"))
    assert updates["acme.latest.design"].action == ACTION_REPOINTED
    assert os.readlink(link) == "acme.2.design"
    # No audit family link existed → none invented.
    assert "acme.latest.audit" not in updates
    assert not (thread / "acme.latest.audit").exists()


def test_writer_dangling_link_with_no_targets_is_skipped(
    tmp_path: Path,
) -> None:
    thread = _mk_thread(tmp_path, "acme", ns=(1,))
    link = thread / "acme.latest.review"
    link.symlink_to("acme.1.review")  # no review siblings exist at all
    updates = _by_name(update_latest_symlinks(thread, "acme"))
    assert updates["acme.latest.review"].action == ACTION_SKIPPED
    assert "no version-family target" in updates["acme.latest.review"].note


def test_writer_does_not_perturb_discovery_enumeration(
    tmp_path: Path,
) -> None:
    """The #120/#153 load-bearing guarantee survives the writer: the
    symlinks it creates remain invisible to resolve_latest's
    walk-to-highest enumeration (digit-N anchor)."""
    thread = _mk_thread(tmp_path, "acme", ns=(1, 2, 3), review_ns=(3,))
    update_latest_symlinks(thread, "acme")
    # Remove the bare symlink so resolve_latest exercises step 3
    # (walk-to-highest) with `.latest.review` still present.
    (thread / "acme.latest").unlink()
    resolved = resolve_latest(thread, "acme")
    assert resolved is not None and resolved.name == "acme.3"


def test_writer_shim_reexports_writer() -> None:
    from anvil.skills.memo.lib import latest_resolution as shim

    assert shim.update_latest_symlinks is update_latest_symlinks
