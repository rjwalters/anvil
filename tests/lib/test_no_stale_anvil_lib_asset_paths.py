"""Doc-pin guard: no shipped file documents the legacy ``.anvil/lib/`` asset
consumer path for the ``marp/`` or ``figures/`` trees (issue #634).

Post-#230 (layout_version 2), the installer copies ``anvil/lib/`` →
``.anvil/anvil/lib/`` in a consumer repo. The legacy ``.anvil/lib/`` directory
is only present on pre-#230 installs; the installer warns about it and urges
removal. A *fresh* post-#230 install never populates ``.anvil/lib/`` — the
canonical consumer path for ALL framework assets is ``.anvil/anvil/lib/``.

PR #625 fixed the ``snippets/`` consumer-path annotations across ~115 files
but deliberately deferred the ``marp/`` and ``figures/`` asset trees. Issue
#634 completes that migration: every documented consumer invocation
(``--config-file .anvil/anvil/lib/marp/config.yml``,
``mmdc -c .anvil/anvil/lib/figures/mermaid-theme.json``, palette import
topology) must name the ``.anvil/anvil/lib/`` tree the installer actually
populates, not the legacy ``.anvil/lib/`` dir.

This guard pins that outcome so a future edit (or a "simplification" that
reintroduces the shorter-looking path) can't silently regress a documented
invocation back to a directory a fresh install does not create.

Scope: the guard forbids the *consumer* forms ``.anvil/lib/marp/`` and
``.anvil/lib/figures/`` (leading dot — the on-disk consumer path). The
source-tree forms ``anvil/lib/marp/`` / ``anvil/lib/figures/`` (no leading
dot — a reference to a path within the anvil source checkout, or a Python
module import) are legitimate and are NOT matched by these patterns.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# The legacy consumer-path prefixes a fresh post-#230 install never populates.
# The leading dot is load-bearing: it distinguishes the on-disk consumer path
# (``.anvil/lib/...``) from a source-checkout / module reference
# (``anvil/lib/...``), which is legitimate and must be left alone.
FORBIDDEN_STRINGS = (".anvil/lib/marp/", ".anvil/lib/figures/")

# Text-ish shipped files under the two trees an agent/critic reads and executes
# literally. Covers command specs, skill docs, templates, and asset headers.
SCAN_ROOTS = ("anvil/skills", "anvil/lib")
SCAN_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".css", ".j2", ".json", ".txt"}


def _scanned_files() -> List[Path]:
    files: List[Path] = []
    for root in SCAN_ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*")):
            if path.is_file() and path.suffix in SCAN_SUFFIXES:
                files.append(path)
    assert files, f"no files found under {SCAN_ROOTS!r}; scan globs are broken"
    return files


def _file_ids() -> List[str]:
    return [str(p.relative_to(REPO_ROOT)) for p in _scanned_files()]


@pytest.mark.parametrize("path", _scanned_files(), ids=_file_ids())
def test_file_has_no_legacy_anvil_lib_asset_path(path: Path):
    """Regression guard (issue #634): a shipped file MUST NOT document the
    legacy ``.anvil/lib/marp/`` or ``.anvil/lib/figures/`` consumer path. A
    fresh post-#230 install populates ``.anvil/anvil/lib/`` — the legacy dir is
    never created, so any such reference points an agent at a nonexistent path.
    """
    text = path.read_text(encoding="utf-8")
    for needle in FORBIDDEN_STRINGS:
        assert needle not in text, (
            f"{path.relative_to(REPO_ROOT)} references the legacy consumer "
            f"asset path {needle!r}. A fresh post-#230 install populates "
            f"'.anvil/anvil/lib/' — use '.anvil/anvil{needle}' instead "
            f"(issue #634)."
        )


def test_no_file_references_legacy_anvil_lib_asset_path_aggregate():
    """Aggregate companion: collect EVERY offending file in one pass so a
    multi-file regression reports all offenders at once."""
    offenders: List[str] = []
    for path in _scanned_files():
        text = path.read_text(encoding="utf-8")
        if any(needle in text for needle in FORBIDDEN_STRINGS):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == [], (
        "files must not reference the legacy '.anvil/lib/marp/' or "
        f"'.anvil/lib/figures/' consumer asset paths (issue #634); the "
        f"canonical consumer tree is '.anvil/anvil/lib/'. Offenders: {offenders}"
    )
