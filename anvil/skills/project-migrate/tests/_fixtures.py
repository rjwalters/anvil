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


def build_aldus_shaped_deck(
    root: Path,
    project_name: str = "brains-for-robots",
    *,
    thread: str = "series-a-deck",
    with_project_brief: bool = False,
) -> Path:
    """Build a nested-but-flat deck project (issue #382).

    Sanitized snapshot of the studio canary's pre-``2cf3f37`` deck
    thread: a thread-root directory carrying the thread-level BRIEF,
    refs/, assets/, and the per-thread ``.anvil.json`` (the deck
    iteration-cap-rationale carrier), with the version dirs and critic
    siblings sitting FLAT at the project root.

    Shape:
      <project>/
        series-a-deck/
          BRIEF.md             ← thread-level deck brief (no documents:)
          refs/transcript-founder.md
          assets/logo.png
          .anvil.json          ← paired max_iterations + rationale
        series-a-deck.1/
          deck.md              ← Marp source (retained body filename)
          speaker-notes.md
          _progress.json
        series-a-deck.1.review/verdict.md
        series-a-deck.2/deck.md + speaker-notes.md
        series-a-deck.2.design/findings.md

    Migration target: ``<project>/series-a-deck/series-a-deck.N/`` with
    the thread-root contents (BRIEF/refs/assets) staying in place and
    the ``.anvil.json`` merged into the project BRIEF.

    When ``with_project_brief`` is True, a project-level BRIEF.md with a
    ``documents:`` list (naming only the deck thread) is also written —
    this exercises the POST_283 mixed-grammar dispatch (a flat thread in
    a BRIEF-bearing project).
    """
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    thread_root = project_dir / thread
    _write(
        thread_root / "BRIEF.md",
        "---\n"
        "company: Aldus Robotics\n"
        "stage: series-a\n"
        "---\n"
        "\n"
        f"# Brief: {thread}\n"
        "\n"
        "Thread-level deck brief (intake output).\n",
    )
    _write(
        thread_root / "refs" / "transcript-founder.md",
        "# Founder transcript\n\nQuote substrate.\n",
    )
    _write(thread_root / "assets" / "logo.png", "PNG-PLACEHOLDER\n")
    _write(
        thread_root / ".anvil.json",
        json.dumps(
            {
                "max_iterations": 6,
                "iteration_cap_rationale": (
                    "Well-conditioned thread: trajectory v1-v4 "
                    "monotonically improving; one extra pass to land "
                    "the outcome detail."
                ),
            },
            indent=2,
        ) + "\n",
    )

    for n in (1, 2):
        version_dir = project_dir / f"{thread}.{n}"
        _write(
            version_dir / "deck.md",
            f"---\nmarp: true\n---\n\n# {thread} v{n}\n\n---\n\n## Ask\n",
        )
        _write(
            version_dir / "speaker-notes.md",
            f"# Speaker notes v{n}\n",
        )
        _write(
            version_dir / "_progress.json",
            json.dumps(
                {
                    "version": 1,
                    "thread": thread,
                    "phases": {"draft": {"state": "done"}},
                },
                indent=2,
            ) + "\n",
        )
    _write(
        project_dir / f"{thread}.1.review" / "verdict.md",
        f"# Review of {thread}.1\n\nVerdict: revise.\n",
    )
    _write(
        project_dir / f"{thread}.2.design" / "findings.md",
        "# Design findings\n\nClean.\n",
    )

    if with_project_brief:
        _write(
            project_dir / "BRIEF.md",
            "---\n"
            f"project: {project_name}\n"
            "audience: []\n"
            "hard_rules: []\n"
            "documents:\n"
            f"  - slug: {thread}\n"
            "    artifact_type: investment-memo\n"
            "---\n"
            "\n"
            "# Project BRIEF\n",
        )

    return project_dir


def build_mixed_memo_deck_proposal(
    root: Path,
    project_name: str = "mixed-project",
) -> Path:
    """Build the mixed-skill canary case (issue #382).

    One project root with three pre-#295 flat threads:

    - ``aldus`` — memo thread (``aldus.N/memo.md`` + review sibling;
      skill-fixed body needs the slug-echo rename).
    - ``series-a-deck`` — deck thread in the nested-but-flat shape
      (thread root with BRIEF/refs/assets/.anvil.json as a sibling of
      flat ``series-a-deck.N/`` version dirs; ``deck.md`` body
      retained).
    - ``gossamer-lan`` — proposal thread (thread root with BRIEF/refs
      as a sibling of flat ``gossamer-lan.N/`` version dirs;
      ``proposal.tex`` body retained).

    No project-level BRIEF — the whole project classifies as
    PRE_283_CLASSIC and every thread gets the nesting plan.
    """
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    # --- memo thread (flat, named stem, skill-fixed body) ---
    for n in (1, 2):
        version_dir = project_dir / f"aldus.{n}"
        _write(
            version_dir / "memo.md",
            f"# aldus memo v{n}\n\nBody.\n",
        )
        _write(
            version_dir / "_progress.json",
            json.dumps(
                {
                    "version": 1,
                    "thread": "aldus",
                    "phases": {"draft": {"state": "done"}},
                },
                indent=2,
            ) + "\n",
        )
    _write(
        project_dir / "aldus.2.review" / "verdict.md",
        "# Review of aldus.2\n\nVerdict: advance.\n",
    )

    # --- deck thread (nested-but-flat; reuse the aldus-shaped builder
    # pieces inline so this fixture stays self-describing) ---
    deck = "series-a-deck"
    deck_root = project_dir / deck
    _write(
        deck_root / "BRIEF.md",
        "---\ncompany: Aldus Robotics\nstage: series-a\n---\n\n"
        f"# Brief: {deck}\n",
    )
    _write(
        deck_root / "refs" / "transcript-founder.md",
        "# Founder transcript\n",
    )
    _write(deck_root / "assets" / "logo.png", "PNG-PLACEHOLDER\n")
    _write(
        deck_root / ".anvil.json",
        json.dumps(
            {
                "max_iterations": 6,
                "iteration_cap_rationale": "One extra pass to land detail.",
            },
            indent=2,
        ) + "\n",
    )
    for n in (1, 2):
        version_dir = project_dir / f"{deck}.{n}"
        _write(
            version_dir / "deck.md",
            f"---\nmarp: true\n---\n\n# {deck} v{n}\n",
        )
        _write(version_dir / "speaker-notes.md", f"# Notes v{n}\n")
        _write(
            version_dir / "_progress.json",
            json.dumps(
                {
                    "version": 1,
                    "thread": deck,
                    "phases": {"draft": {"state": "done"}},
                },
                indent=2,
            ) + "\n",
        )
    _write(
        project_dir / f"{deck}.1.review" / "verdict.md",
        f"# Review of {deck}.1\n\nVerdict: revise.\n",
    )

    # --- proposal thread (nested-but-flat; LaTeX body) ---
    prop = "gossamer-lan"
    prop_root = project_dir / prop
    _write(
        prop_root / "BRIEF.md",
        "---\ncustomer_kind: external\n---\n\n"
        f"# Brief: {prop}\n",
    )
    _write(
        prop_root / "refs" / "quote-vendor.md",
        "# Vendor quote\n",
    )
    _write(
        project_dir / f"{prop}.1" / "proposal.tex",
        "\\documentclass{anvil-proposal}\n"
        "\\begin{document}\nGossamer LAN v1.\n\\end{document}\n",
    )
    _write(
        project_dir / f"{prop}.1" / "_progress.json",
        json.dumps(
            {
                "version": 1,
                "thread": prop,
                "phases": {"draft": {"state": "done"}},
            },
            indent=2,
        ) + "\n",
    )
    _write(
        project_dir / f"{prop}.1.review" / "verdict.md",
        f"# Review of {prop}.1\n\nVerdict: advance.\n",
    )
    _write(
        project_dir / f"{prop}.1.audit" / "findings.md",
        "# Audit findings\n\nBOM arithmetic clean.\n",
    )

    return project_dir


def build_bare_version_dir_threads(
    root: Path,
    project_name: str = "paper",
    *,
    slug: str = "bispectral-imaging",
    documentclass: str = "article",
) -> Path:
    """Build a BARE version-dir project (issue #408).

    Anonymized reproduction of the adoption-target monorepo shape: a
    hand-rolled review/revise workflow that independently converged on
    Anvil's ``{thread}.{N}/`` + ``.review``/``.audit`` sibling grammar,
    but carries ZERO anvil config (no BRIEF.md anywhere, no
    ``.anvil.json``) and a fixed ``paper.tex`` body filename consumed
    by external tooling (root-level ``paper.tex``/``paper.pdf`` build
    artifacts).

    Shape (version gaps deliberate — no ``.2``):

      <project>/
        <slug>.1/paper.tex
        <slug>.3/paper.tex
        <slug>.3.review/review.md      ← hand-rolled, unstamped
        <slug>.4/paper.tex
        <slug>.4.review/review.md
        <slug>.5/paper.tex
        <slug>.6/paper.tex
        <slug>.6.audit/audit.md        ← hand-rolled, unstamped
        <slug>.7/paper.tex
        figures/fig1.png
        paper.tex                      ← root-level build entrypoint
        paper.pdf

    ``documentclass`` parametrizes the inference path: ``article``
    (default) infers ``pub``; ``anvil-proposal`` infers ``proposal``.
    """
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    versions = (1, 3, 4, 5, 6, 7)
    for n in versions:
        _write(
            project_dir / f"{slug}.{n}" / "paper.tex",
            f"\\documentclass{{{documentclass}}}\n"
            "\\begin{document}\n"
            f"Bispectral imaging draft v{n}.\n"
            "\\end{document}\n",
        )
    # Hand-rolled review siblings: a bare `review.md` is NOT a
    # recognizable payload for `discover_critics` (no `_review.json`,
    # no legacy triple) — invisible-but-intact per the #346 additive
    # contract; rebackportable later via anvil:rubric-rebackport.
    for n in (3, 4):
        _write(
            project_dir / f"{slug}.{n}.review" / "review.md",
            f"# Review of draft v{n}\n\nHand-rolled reviewer notes.\n",
        )
    _write(
        project_dir / f"{slug}.6.audit" / "audit.md",
        "# Audit of draft v6\n\nHand-rolled audit notes.\n",
    )
    # Root-level build artifacts: direct evidence that external tooling
    # (latexmk / Makefile) consumes the fixed `paper.tex` name — the
    # #382 slug-echo carve-out applies (record, never rename).
    _write(
        project_dir / "paper.tex",
        f"\\documentclass{{{documentclass}}}\n"
        "% build entrypoint consumed by latexmk\n",
    )
    _write(project_dir / "paper.pdf", "PDF-PLACEHOLDER\n")
    _write(project_dir / "figures" / "fig1.png", "PNG-PLACEHOLDER\n")
    return project_dir


__all__ = [
    "build_aldus_shaped_deck",
    "build_bare_version_dir_threads",
    "build_bessemer_shaped",
    "build_fully_migrated",
    "build_mixed_memo_deck_proposal",
    "build_post_283_anvil_json",
    "build_pre_283_classic",
]
