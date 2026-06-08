"""Programmatic fixture builders for `anvil:rubric-rebackport` tests (issue #358).

The skill's fixtures are project trees the tests construct in tmp
directories rather than baked-on-disk snapshots. This keeps the repo
small and the fixtures readable next to the tests that consume them.

Builders cover the four named fixtures from the curator notes:

- ``build_legacy_unstamped`` — single /40 memo thread with one
  reviewer sibling whose ``_meta.json`` lacks rubric stamping
  everywhere.
- ``build_partially_stamped`` — single /40 memo thread with a
  ``_meta.json`` already stamped but the ``_progress.json``
  ``score_history[]`` rows not.
- ``build_fully_stamped`` — single thread where every file is
  already stamped (no-op input).
- ``build_mixed_skill_portfolio`` — memo + proposal threads with
  mixed stamping. Exercises ``--skill=`` scoping.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _meta_legacy() -> dict:
    """Return a legacy reviewer ``_meta.json`` (no stamping fields)."""
    return {
        "critic": "review",
        "role": "memo-review.md",
        "started": "2026-05-01T12:00:00Z",
        "finished": "2026-05-01T12:05:00Z",
        "model": "claude-opus-4-1",
        "schema_version": 1,
        "scorecard_kind": "human-verdict",
        # Note: rubric_total IS present here so the heuristic can fire
        # without --legacy-rubric.
        "rubric_total": 40,
    }


def _meta_stamped_v1() -> dict:
    """Return a fully-stamped /40 ``_meta.json``."""
    m = _meta_legacy()
    m["rubric_id"] = "anvil-memo-v1-legacy-40"
    m["advance_threshold"] = 32
    return m


def _progress_legacy(thread: str) -> dict:
    """Return a legacy ``_progress.json`` whose score_history rows lack rubric_id."""
    return {
        "version": 1,
        "thread": thread,
        "phases": {
            "review": {"state": "done"},
        },
        "metadata": {
            "iteration": 1,
            "max_iterations": 4,
            "score_history": [
                {"iteration": 1, "total": 30, "threshold": 32},
            ],
        },
    }


def _progress_stamped(thread: str) -> dict:
    """Return a fully-stamped ``_progress.json``."""
    p = _progress_legacy(thread)
    for row in p["metadata"]["score_history"]:
        row["rubric_id"] = "anvil-memo-v1-legacy-40"
    return p


def _brief_for_skill(slug: str, artifact_type: str) -> str:
    """Return a minimal project BRIEF.md text with the given slug + type."""
    return (
        "---\n"
        f"project: {slug}-project\n"
        "audience: []\n"
        "hard_rules: []\n"
        "documents:\n"
        f"  - slug: {slug}\n"
        f"    artifact_type: {artifact_type}\n"
        "---\n"
        "\n"
        "# Project BRIEF\n"
    )


# ---------------------------------------------------------------------------
# Fixture: legacy_unstamped
# ---------------------------------------------------------------------------


def build_legacy_unstamped(
    root: Path,
    project_name: str = "legacy-memo",
    *,
    slug: str = "memo",
) -> Path:
    """Build a single /40 memo thread whose review is fully unstamped.

    Shape:
      <project>/
        BRIEF.md
        memo/
          memo.1/
            memo.md
            _progress.json
          memo.1.review/
            _meta.json
            _summary.md
            verdict.md
    """
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    _write(project_dir / "BRIEF.md", _brief_for_skill(slug, "investment-memo"))

    thread_dir = project_dir / slug
    v1 = thread_dir / f"{slug}.1"
    _write(v1 / "memo.md", "# memo v1\n\nBody.\n")
    _write(
        v1 / "_progress.json",
        json.dumps(_progress_legacy(slug), indent=2) + "\n",
    )

    review_dir = thread_dir / f"{slug}.1.review"
    _write(
        review_dir / "_meta.json",
        json.dumps(_meta_legacy(), indent=2) + "\n",
    )
    _write(
        review_dir / "_summary.md",
        "---\n"
        "for_version: 1\n"
        "scorecard_kind: human-verdict\n"
        "critical_flag: false\n"
        "---\n"
        "\n"
        "# Review summary\n\nLegacy summary body.\n",
    )
    _write(review_dir / "verdict.md", "# Verdict\n\nLegacy verdict.\n")
    return project_dir


# ---------------------------------------------------------------------------
# Fixture: partially_stamped
# ---------------------------------------------------------------------------


def build_partially_stamped(
    root: Path,
    project_name: str = "partial-memo",
    *,
    slug: str = "memo",
) -> Path:
    """Build a thread whose `_meta.json` is stamped but progress rows are not."""
    project_dir = build_legacy_unstamped(root, project_name, slug=slug)
    review_dir = project_dir / slug / f"{slug}.1.review"
    # Overwrite the _meta.json with a stamped variant.
    _write(
        review_dir / "_meta.json",
        json.dumps(_meta_stamped_v1(), indent=2) + "\n",
    )
    # The progress file is still legacy (rows lack rubric_id).
    return project_dir


# ---------------------------------------------------------------------------
# Fixture: fully_stamped
# ---------------------------------------------------------------------------


def build_fully_stamped(
    root: Path,
    project_name: str = "stamped-memo",
    *,
    slug: str = "memo",
) -> Path:
    """Build a thread that's fully stamped — should be a no-op for the tool."""
    project_dir = build_legacy_unstamped(root, project_name, slug=slug)
    review_dir = project_dir / slug / f"{slug}.1.review"
    _write(
        review_dir / "_meta.json",
        json.dumps(_meta_stamped_v1(), indent=2) + "\n",
    )
    # Stamp the progress file's score_history rows.
    v1 = project_dir / slug / f"{slug}.1"
    _write(
        v1 / "_progress.json",
        json.dumps(_progress_stamped(slug), indent=2) + "\n",
    )
    return project_dir


# ---------------------------------------------------------------------------
# Fixture: mixed_skill_portfolio
# ---------------------------------------------------------------------------


def build_mixed_skill_portfolio(
    root: Path,
    project_name: str = "portfolio",
) -> Path:
    """Build a portfolio with memo + proposal threads, both legacy unstamped.

    Shape:
      <project>/
        BRIEF.md          (documents: memo + proposal)
        memo/
          memo.1/memo.md + _progress.json
          memo.1.review/_meta.json + _summary.md + verdict.md
        proposal/
          proposal.1/proposal.md + _progress.json
          proposal.1.review/_meta.json + _summary.md + verdict.md
    """
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    brief = (
        "---\n"
        f"project: {project_name}\n"
        "audience: []\n"
        "hard_rules: []\n"
        "documents:\n"
        "  - slug: memo\n"
        "    artifact_type: investment-memo\n"
        "  - slug: proposal\n"
        "    artifact_type: proposal\n"
        "---\n"
        "\n"
        "# Project BRIEF\n"
    )
    _write(project_dir / "BRIEF.md", brief)

    for slug, body_name in (("memo", "memo.md"), ("proposal", "proposal.md")):
        thread_dir = project_dir / slug
        v1 = thread_dir / f"{slug}.1"
        _write(v1 / body_name, f"# {slug} v1\n\nBody.\n")
        _write(
            v1 / "_progress.json",
            json.dumps(_progress_legacy(slug), indent=2) + "\n",
        )
        review_dir = thread_dir / f"{slug}.1.review"
        meta = _meta_legacy()
        meta["role"] = f"{slug}-review.md"
        _write(
            review_dir / "_meta.json",
            json.dumps(meta, indent=2) + "\n",
        )
        _write(
            review_dir / "_summary.md",
            "---\n"
            "for_version: 1\n"
            "scorecard_kind: human-verdict\n"
            "---\n"
            "\n"
            "# Review summary\n",
        )
        _write(review_dir / "verdict.md", "# Verdict\n")
    return project_dir


# ---------------------------------------------------------------------------
# Fixture: pub_44_unstamped (post-#357 canary failure mode)
# ---------------------------------------------------------------------------


def _meta_legacy_pub_44() -> dict:
    """Return a /44-era pub reviewer ``_meta.json`` with rubric_total but no rubric_id."""
    return {
        "critic": "review",
        "role": "pub-review.md",
        "started": "2026-05-15T12:00:00Z",
        "finished": "2026-05-15T12:05:00Z",
        "model": "claude-opus-4-1",
        "schema_version": 1,
        "scorecard_kind": "human-verdict",
        # /44-era pub: rubric_total written, rubric_id absent. The
        # planner must heuristically pick `anvil-pub-v2` from the
        # (skill=pub, total=44) pair without --legacy-rubric.
        "rubric_total": 44,
    }


def build_pub_44_unstamped(
    root: Path,
    project_name: str = "legacy-pub-44",
    *,
    slug: str = "pub",
) -> Path:
    """Build a /44-era pub thread whose review is missing `rubric_id`.

    Exercises the post-#357 catalog entry for ``("pub", 44)`` — the
    canary failure mode that motivated issue #366.
    """
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    _write(project_dir / "BRIEF.md", _brief_for_skill(slug, "pub"))

    thread_dir = project_dir / slug
    v1 = thread_dir / f"{slug}.1"
    _write(v1 / f"{slug}.md", f"# {slug} v1\n\nBody.\n")
    _write(
        v1 / "_progress.json",
        json.dumps(_progress_legacy(slug), indent=2) + "\n",
    )

    review_dir = thread_dir / f"{slug}.1.review"
    _write(
        review_dir / "_meta.json",
        json.dumps(_meta_legacy_pub_44(), indent=2) + "\n",
    )
    _write(
        review_dir / "_summary.md",
        "---\n"
        "for_version: 1\n"
        "scorecard_kind: human-verdict\n"
        "critical_flag: false\n"
        "---\n"
        "\n"
        "# Review summary\n\nLegacy /44-era pub summary body.\n",
    )
    _write(review_dir / "verdict.md", "# Verdict\n\nLegacy verdict.\n")
    return project_dir


__all__ = [
    "build_fully_stamped",
    "build_legacy_unstamped",
    "build_mixed_skill_portfolio",
    "build_partially_stamped",
    "build_pub_44_unstamped",
]
