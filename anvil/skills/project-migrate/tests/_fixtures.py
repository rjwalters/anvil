"""Programmatic fixture builders for `anvil:project-migrate` tests (issue #297).

The skill's fixtures are tree shapes the tests construct in tmp dirs
rather than baked-on-disk snapshots. This keeps the repo small and the
fixtures readable next to the tests that consume them.

Each builder takes a parent ``tmp_path`` and a project name and produces
the full project tree, returning the project root.

Builders match the three on-disk shapes the detector recognizes:

- ``build_pre_283_classic`` — `memo.N/` siblings directly under project
  root, no project BRIEF, `memo.md` body.
- ``build_post_283_anvil_json`` — `<project>/BRIEF.md` + `<slug>/<slug>.N/`
  with `.anvil.json` (per-thread or root) and possibly `memo.md` bodies.
- ``build_fully_migrated`` — target shape (everything correct).
- ``build_bessemer_shaped`` — sanitized multi-thread snapshot exercising
  the canary case (multiple memo.N versions + critic siblings).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Optional


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_pre_283_classic(
    root: Path,
    project_name: str = "acme-investment",
    *,
    n_versions: int = 3,
) -> Path:
    """Build a pre-#283 classic project under ``root/<project_name>/``.

    Shape:
      <project>/
        memo.1/memo.md
        memo.2/memo.md
        memo.3/memo.md
        .anvil.json
        BRIEF.md            ← optional, per-thread brief (NOT a project BRIEF)

    Returns the project root path.
    """
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    for n in range(1, n_versions + 1):
        version_dir = project_dir / f"memo.{n}"
        _write(
            version_dir / "memo.md",
            f"# memo version {n}\n\nSee memo.{n - 1} for prior context.\n"
            if n > 1
            else f"# memo version {n}\n\nFirst draft.\n",
        )
        _write(
            version_dir / "_progress.json",
            json.dumps(
                {
                    "version": 1,
                    "thread": "memo",
                    "phases": {"draft": {"state": "done"}},
                },
                indent=2,
            ) + "\n",
        )
    # Per-thread BRIEF.md (no documents: key — not a project BRIEF).
    brief_text = (
        "---\n"
        f"company: {project_name}\n"
        "sector: TODO\n"
        "---\n"
        "\n"
        f"# Brief: {project_name}\n"
        "\n"
        "Free-form per-thread brief from the pre-#283 era.\n"
    )
    _write(project_dir / "BRIEF.md", brief_text)
    _write(
        project_dir / ".anvil.json",
        json.dumps(
            {
                "max_iterations": 4,
                "target_length": {"words": [8000, 11000]},
            },
            indent=2,
        ) + "\n",
    )
    return project_dir


def build_post_283_anvil_json(
    root: Path,
    project_name: str = "brains-for-robots",
    *,
    slugs: Optional[list] = None,
) -> Path:
    """Build a post-#283 project with `.anvil.json` files.

    Shape:
      <project>/
        BRIEF.md            ← project BRIEF with documents: list
        investment-memo/
          investment-memo.1/memo.md   ← skill-fixed body filename
          investment-memo.2/memo.md
          .anvil.json                  ← per-thread config
        latency-wall/
          latency-wall.1/memo.md
          .anvil.json
    """
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    if slugs is None:
        slugs = ["investment-memo", "latency-wall"]

    # Project BRIEF — has documents: but missing per-doc config.
    doc_lines: list = []
    for s in slugs:
        doc_lines.append(f"  - slug: {s}")
        doc_lines.append(f"    artifact_type: investment-memo")
    documents_yaml = "\n".join(doc_lines)
    brief_text = (
        "---\n"
        f"project: {project_name}\n"
        "audience:\n"
        "  - Operator\n"
        "hard_rules: []\n"
        "documents:\n"
        f"{documents_yaml}\n"
        "---\n"
        "\n"
        "# Project BRIEF\n"
    )
    _write(project_dir / "BRIEF.md", brief_text)

    for slug in slugs:
        slug_dir = project_dir / slug
        # Two version dirs per thread by default.
        for n in (1, 2):
            version_dir = slug_dir / f"{slug}.{n}"
            _write(
                version_dir / "memo.md",
                f"# {slug} v{n}\n\nBody for {slug}.\n",
            )
            _write(
                version_dir / "_progress.json",
                json.dumps(
                    {
                        "version": 1,
                        "thread": slug,
                        "phases": {"draft": {"state": "done"}},
                    },
                    indent=2,
                ) + "\n",
            )
        # Per-thread .anvil.json
        _write(
            slug_dir / ".anvil.json",
            json.dumps(
                {
                    "max_iterations": 4,
                    "target_length": {"words": [5000, 8000]},
                    "rubric_overrides": {
                        "memo_subtype": "synthesis-brief",
                        "dim_1_calibration": "Calibration text for dim 1.",
                    },
                },
                indent=2,
            ) + "\n",
        )
    return project_dir


def build_fully_migrated(
    root: Path,
    project_name: str = "brains-for-robots-migrated",
    *,
    slugs: Optional[list] = None,
) -> Path:
    """Build a fully-migrated project.

    Shape:
      <project>/
        BRIEF.md             ← project BRIEF absorbing all config
        investment-memo/
          investment-memo.1/investment-memo.md
          investment-memo.2/investment-memo.md
        latency-wall/
          latency-wall.1/latency-wall.md
    """
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    if slugs is None:
        slugs = ["investment-memo", "latency-wall"]

    # Build documents YAML with target_length + rubric_overrides absorbed.
    doc_lines: list = []
    for s in slugs:
        doc_lines.append(f"  - slug: {s}")
        doc_lines.append(f"    artifact_type: investment-memo")
        doc_lines.append(f"    target_length: {{ words: [5000, 8000] }}")
        doc_lines.append(f"    rubric_overrides:")
        doc_lines.append(f"      memo_subtype: synthesis-brief")
        doc_lines.append(f"      dim_1_calibration: \"Calibration text for dim 1.\"")
    documents_yaml = "\n".join(doc_lines)
    brief_text = (
        "---\n"
        f"project: {project_name}\n"
        "audience:\n"
        "  - Operator\n"
        "hard_rules: []\n"
        "documents:\n"
        f"{documents_yaml}\n"
        "---\n"
        "\n"
        "# Project BRIEF\n"
    )
    _write(project_dir / "BRIEF.md", brief_text)

    for slug in slugs:
        slug_dir = project_dir / slug
        for n in (1, 2):
            version_dir = slug_dir / f"{slug}.{n}"
            _write(
                version_dir / f"{slug}.md",
                f"# {slug} v{n}\n\nBody for {slug}.\n",
            )
            _write(
                version_dir / "_progress.json",
                json.dumps(
                    {
                        "version": 1,
                        "thread": slug,
                        "phases": {"draft": {"state": "done"}},
                    },
                    indent=2,
                ) + "\n",
            )
    return project_dir


def build_bessemer_shaped(
    root: Path, project_name: str = "bessemer"
) -> Path:
    """Build a sanitized bessemer-shaped pre-#283 snapshot.

    Multiple memo.N versions with critic siblings (review and audit dirs)
    to exercise the canary case where critic siblings need renaming
    alongside their version dirs.

    Shape:
      bessemer/
        memo.1/memo.md
        memo.1.review/verdict.md
        memo.2/memo.md
        memo.2.review/verdict.md
        memo.2.audit/findings.md
        memo.3/memo.md
        memo.3.review/verdict.md
        .anvil.json
    """
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    for n in (1, 2, 3):
        version_dir = project_dir / f"memo.{n}"
        body_text = f"# bessemer memo v{n}\n\n"
        if n == 3:
            # Add a cross-thread reference to memo.2 to exercise rewriting.
            body_text += (
                "See `memo.2` §3 for the original framing. The memo.1 "
                "draft is preserved at `memo.1/memo.md`.\n"
            )
        _write(version_dir / "memo.md", body_text)
        _write(
            version_dir / "_progress.json",
            json.dumps(
                {
                    "version": 1,
                    "thread": "memo",
                    "phases": {"draft": {"state": "done"}},
                },
                indent=2,
            ) + "\n",
        )
        # Review sibling.
        review_dir = project_dir / f"memo.{n}.review"
        _write(
            review_dir / "verdict.md",
            f"# Review of memo.{n}\n\nVerdict: advance.\n",
        )
        _write(
            review_dir / "_meta.json",
            json.dumps(
                {"critic": "reviewer", "scorecard_kind": "human-verdict"},
                indent=2,
            ) + "\n",
        )
    # Add an audit sibling on memo.2.
    audit_dir = project_dir / "memo.2.audit"
    _write(audit_dir / "findings.md", "# Audit\n\nClean.\n")
    # Project-level .anvil.json (pre-#283 layout).
    _write(
        project_dir / ".anvil.json",
        json.dumps(
            {
                "max_iterations": 4,
                "target_length": {"words": [8000, 11000]},
            },
            indent=2,
        ) + "\n",
    )
    return project_dir


__all__ = [
    "build_bessemer_shaped",
    "build_fully_migrated",
    "build_post_283_anvil_json",
    "build_pre_283_classic",
]
