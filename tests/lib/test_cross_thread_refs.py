"""Canonical-path tests for ``anvil.lib.cross_thread_refs`` (issue #382).

Promoted from ``anvil/skills/memo/lib/`` under factoring A of issue
#382. The full behavioral corpus lives at
``anvil/skills/memo/tests/test_cross_thread_refs.py`` and continues to
run against the canonical implementation through the memo back-compat
shim. This file pins the promotion contracts (canonical import path +
shim identity + the intra-lib ``latest_resolution`` re-export) plus
representative find/resolve behavior.
"""

from __future__ import annotations

from pathlib import Path

from anvil.lib.cross_thread_refs import (
    LATEST,
    CrossThreadRef,
    find_cross_thread_refs,
    resolve_cross_thread_refs,
    resolve_latest,
)


def test_shim_reexports_same_objects() -> None:
    from anvil.skills.memo.lib import cross_thread_refs as shim

    assert shim.find_cross_thread_refs is find_cross_thread_refs
    assert shim.resolve_cross_thread_refs is resolve_cross_thread_refs
    assert shim.CrossThreadRef is CrossThreadRef


def test_latest_reexport_is_canonical() -> None:
    """The LATEST / resolve_latest re-export now sources from
    anvil.lib.latest_resolution (the intra-lib import updated during the
    move) — same objects on every path."""
    from anvil.lib import latest_resolution

    assert resolve_latest is latest_resolution.resolve_latest
    assert LATEST == latest_resolution.LATEST


def test_find_refs_in_body_text() -> None:
    text = (
        "# memo\n"
        "Per [[../latency-wall/latency-wall.latest]] the wall holds.\n"
        "See [[../broadcom-thesis/broadcom-thesis.2/memo.md]] for prior.\n"
    )
    refs = find_cross_thread_refs(text)
    assert len(refs) == 2
    assert refs[0].other_slug == "latency-wall"
    assert refs[0].version == "latest"
    assert refs[1].other_slug == "broadcom-thesis"
    assert refs[1].version == "2"
    assert refs[1].file == "memo.md"


def test_resolve_against_on_disk_siblings(tmp_path: Path) -> None:
    portfolio = tmp_path
    sibling = portfolio / "latency-wall" / "latency-wall.3"
    sibling.mkdir(parents=True)

    text = "See [[../latency-wall/latency-wall.latest]].\n"
    resolutions = resolve_cross_thread_refs(text, portfolio)
    assert len(resolutions) == 1
    assert resolutions[0].resolved is True

    missing = resolve_cross_thread_refs(
        "See [[../no-such-thread/no-such-thread.1]].\n", portfolio
    )
    assert len(missing) == 1
    assert missing[0].resolved is False
