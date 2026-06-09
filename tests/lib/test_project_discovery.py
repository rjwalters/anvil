"""Canonical-path tests for ``anvil.lib.project_discovery`` (issue #382).

Promoted from ``anvil/skills/memo/lib/`` under factoring A of issue
#382. The full behavioral corpus lives at
``anvil/skills/memo/tests/test_project_discovery.py`` and continues to
run against the canonical implementation through the memo back-compat
shim. This file pins the promotion contracts (canonical import path +
shim identity) plus representative discovery behavior, including the
cross-skill case the promotion exists for: discovery inside a deck-style
thread whose body filename is NOT slug-echo (``deck.md``).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from anvil.lib.project_discovery import (
    BRIEF_FILENAME,
    DOCUMENTS_FRONTMATTER_KEY,
    LAYOUT_PROJECT_BRIEF,
    DiscoveryResult,
    discover_thread_root,
    has_project_brief,
)


def _make_project(tmp_path: Path, slugs: list) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    doc_lines = "\n".join(
        f"  - slug: {s}\n    artifact_type: investment-memo" for s in slugs
    )
    (project / BRIEF_FILENAME).write_text(
        textwrap.dedent(
            """\
            ---
            project: proj
            documents:
            """
        )
        + doc_lines
        + "\n---\n\n# Project BRIEF\n",
        encoding="utf-8",
    )
    return project


def test_shim_reexports_same_objects() -> None:
    from anvil.skills.memo.lib import project_discovery as shim

    assert shim.discover_thread_root is discover_thread_root
    assert shim.has_project_brief is has_project_brief
    assert shim.DiscoveryResult is DiscoveryResult
    assert shim.BRIEF_FILENAME == BRIEF_FILENAME
    assert shim.DOCUMENTS_FRONTMATTER_KEY == DOCUMENTS_FRONTMATTER_KEY


def test_discovery_from_memo_style_thread(tmp_path: Path) -> None:
    project = _make_project(tmp_path, ["acme"])
    body = project / "acme" / "acme.1" / "acme.md"
    body.parent.mkdir(parents=True)
    body.write_text("# memo\n", encoding="utf-8")

    result = discover_thread_root(body)
    assert result is not None
    assert result.slug == "acme"
    assert result.project_root == project
    assert result.thread_root == project / "acme"
    assert result.layout == LAYOUT_PROJECT_BRIEF


def test_discovery_from_deck_style_thread(tmp_path: Path) -> None:
    """Discovery is body-filename-agnostic: a nested deck thread with a
    retained deck.md body (issue #382's scope-out) resolves identically."""
    project = _make_project(tmp_path, ["series-a-deck"])
    body = project / "series-a-deck" / "series-a-deck.1" / "deck.md"
    body.parent.mkdir(parents=True)
    body.write_text("---\nmarp: true\n---\n# deck\n", encoding="utf-8")
    # Thread-level BRIEF (no documents:) must not terminate the walk-up.
    (project / "series-a-deck" / BRIEF_FILENAME).write_text(
        "---\ncompany: Aldus\n---\n\n# thread brief\n", encoding="utf-8"
    )

    result = discover_thread_root(body)
    assert result is not None
    assert result.slug == "series-a-deck"
    assert result.project_root == project
    assert result.thread_root == project / "series-a-deck"


def test_unlisted_slug_returns_none(tmp_path: Path) -> None:
    project = _make_project(tmp_path, ["acme"])
    rogue = project / "rogue" / "rogue.1"
    rogue.mkdir(parents=True)
    assert discover_thread_root(rogue) is None


def test_has_project_brief_requires_documents(tmp_path: Path) -> None:
    project = tmp_path / "p"
    project.mkdir()
    (project / BRIEF_FILENAME).write_text(
        "---\ncompany: x\n---\n\nprose\n", encoding="utf-8"
    )
    assert has_project_brief(project) is False
    assert has_project_brief(_make_project(tmp_path, ["a"])) is True
