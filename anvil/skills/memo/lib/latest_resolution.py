"""Canonical ``.latest`` resolution for memo thread version directories
(issue #288, sub-deliverable 5 of #283).

This module ships the **single source of truth** for resolving a
``<slug>.latest`` reference to a concrete version directory on disk. Per
issue #288's curator recommendation — **option (c): pure tolerance** —
anvil-shipped commands do NOT auto-create or maintain ``<slug>.latest``
symlinks (consumer-maintained per ``anvil/lib/snippets/version_layout.md``
§"Convenience ``.latest`` symlinks"); instead, every code path that has
to resolve a symbolic ``.latest`` reference goes through this helper,
which tolerates four on-disk shapes:

1. ``<thread_dir>/<slug>.latest`` exists as a **symlink** pointing at a
   ``<slug>.<N>/`` directory. The author pinned the symlink to a
   specific version (the load-bearing case for intentional pinning to a
   non-highest version — e.g., "publish ``.latest`` against the
   reviewed-and-AUDITED v3 even though v4 is in progress").
2. ``<thread_dir>/<slug>.latest`` exists as a **real directory** (no
   symlink). This is the rarer case — typically the operator hasn't
   migrated to the symlink convention yet, or is on a filesystem where
   symlinks are awkward (Windows without WSL).
3. No ``<slug>.latest`` of any shape, but one or more
   ``<slug>.<N>/`` sibling directories exist. The helper walks the
   children and returns the **highest-numbered** one. This is the
   walk-to-highest fallback — the load-bearing path for the "operator
   never created the symlink" case (the canary's common case today
   per #288's option (c) rationale).
4. None of the above — no symlink, no ``.latest/`` directory, no
   ``<slug>.<N>/`` siblings. The helper returns ``None``, leaving the
   caller to surface a clean "no version dirs" error to the operator.

Precedence is fixed: 1 > 2 > 3 > 4. **A pinned symlink always wins**
over walk-to-highest — an author who intentionally pins ``.latest`` to
v3 even though v4 exists gets v3 from this helper. This is the
load-bearing AC from the issue: "If ``<slug>.latest`` symlink exists, it
takes precedence (an author can pin ``.latest`` to a non-highest version
intentionally)."

Public API
----------

``resolve_latest(thread_dir: Path, slug: str) -> Optional[Path]``
    The canonical resolver. Returns the path to the resolved version
    directory (which may be the ``.latest`` symlink-or-directory itself,
    or the highest-numbered ``<slug>.<N>/``), or ``None`` when no
    resolution is possible. **Non-throwing**: filesystem errors during
    traversal degrade to ``None`` rather than propagating, mirroring the
    lenient-form precedent across the memo lib (``refs_resolver``,
    ``project_discovery``, ``project_brief``).

``LATEST``
    The literal string ``"latest"`` — the symbolic version specifier.
    Re-exported here as the single source of truth so callers that
    construct ``.latest`` paths (e.g., the cross-thread parser's regex)
    can reference one constant.

Relationship to ``cross_thread_refs``
-------------------------------------

Before this module shipped, the same walk-to-highest logic lived
privately inside ``cross_thread_refs._resolve_latest_version_dir`` (#287
/ PR #291). This module **extracts** that helper into a reusable public
surface so other call sites — intra-thread ``.latest`` resolution,
future ``memo-draft`` / ``memo-revise`` path resolution, downstream
tooling — can share the contract without re-implementing the regex or
the symlink-precedence rule. ``cross_thread_refs`` now delegates to
``resolve_latest`` to preserve a single source of truth.

Skill-local first
-----------------

Lives under ``anvil/skills/memo/lib/`` per the CLAUDE.md "skill-local
first, lib promotion later" pattern. Promotion to ``anvil/lib/`` is
queued for the second-consumer trigger (likely ``anvil:proposal`` —
which has its own portfolio shape — or ``anvil:pub``). Until then the
module has zero ``anvil.*`` runtime imports.

No new Python deps
------------------

Standard library only (``re``, ``pathlib``, ``typing``). The CLAUDE.md
"Python deps: subprocess-only by default" contract is preserved.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional


# The literal symbolic version specifier. Coupled to the consumer-side
# ``.latest`` symlink convention documented in
# ``anvil/lib/snippets/version_layout.md`` §"Convenience ``.latest``
# symlinks". Keeping the constant here (and re-exporting from
# ``cross_thread_refs``) ensures one source of truth for the literal.
LATEST = "latest"


def resolve_latest(thread_dir: Path, slug: str) -> Optional[Path]:
    """Resolve ``<slug>.latest`` to a concrete version directory on disk.

    The canonical four-step resolution rule per issue #288 option (c):

    1. If ``<thread_dir>/<slug>.latest`` exists as a **symlink** (whether
       resolvable or dangling-but-listed), return it. Symlink wins
       unconditionally — an author can pin ``.latest`` to a non-highest
       version intentionally.
    2. Else if ``<thread_dir>/<slug>.latest`` exists as a **real
       directory** (not a symlink), return it.
    3. Else, enumerate ``<thread_dir>/<slug>.<N>/`` for all integer ``N``,
       pick the highest, and return that directory.
    4. Else, return ``None``. No version dirs and no symlink — the
       caller should surface a clean "no version dirs" error.

    Parameters
    ----------
    thread_dir
        The parent directory that contains the thread's version dirs.
        For a thread at ``<portfolio>/investment-memo/`` with version
        dirs ``investment-memo.1/``, ``investment-memo.2/``, this is
        ``<portfolio>/investment-memo/``. For the cross-thread case,
        this is the sibling thread's directory under the portfolio root.
    slug
        The thread slug — the stem of the version dirs. For an
        ``investment-memo`` thread, slug is ``"investment-memo"`` and the
        helper looks for ``investment-memo.latest``,
        ``investment-memo.1``, ``investment-memo.2``, etc.

    Returns
    -------
    Path or None
        The resolved version directory path. **Note**: when steps 1 or 2
        fire, the return is the literal ``<thread_dir>/<slug>.latest``
        path (not the dereferenced target) — this matches the
        cross-thread resolver's pre-#288 behavior where the operator-
        visible path is what gets recorded in ``comments.md``. Callers
        that need the dereferenced target call ``.resolve()`` themselves.
        Returns ``None`` when no resolution is possible.

    Notes
    -----
    **Non-throwing**: any ``OSError`` during directory traversal (a
    symlink loop, a permission error, a vanished directory) degrades to
    ``None`` rather than propagating. The lenient-form precedent across
    the memo lib (``refs_resolver``, ``project_discovery``,
    ``project_brief``) is the consumer-friendly contract — errors surface
    as findings, not exceptions.

    **Symlink precedence**: a symlink at ``<slug>.latest`` wins even if
    its target does not exist (e.g., a dangling symlink left over from
    a deleted version dir). The caller is responsible for handling the
    case where the returned path's children do not exist — the
    cross-thread resolver, for example, surfaces such cases as
    ``"file not found"`` reasons on the higher-level resolution.

    Examples
    --------
    Symlink precedence (intentional pin to non-highest)::

        # On disk:
        #   <thread_dir>/<slug>.1/
        #   <thread_dir>/<slug>.2/
        #   <thread_dir>/<slug>.3/
        #   <thread_dir>/<slug>.latest -> <slug>.2  (pinned)
        # Returns: <thread_dir>/<slug>.latest (the symlink path)

    Walk-to-highest (no symlink)::

        # On disk:
        #   <thread_dir>/<slug>.1/
        #   <thread_dir>/<slug>.2/
        #   <thread_dir>/<slug>.7/
        # Returns: <thread_dir>/<slug>.7

    Real directory at ``.latest`` (no symlink)::

        # On disk:
        #   <thread_dir>/<slug>.1/
        #   <thread_dir>/<slug>.latest/    (real dir, not a symlink)
        # Returns: <thread_dir>/<slug>.latest

    No resolution::

        # On disk:
        #   <thread_dir>/   (empty)
        # Returns: None
    """
    thread_dir = Path(thread_dir)

    # Step 0: guard against the thread_dir itself not existing. A clean
    # ``None`` here lets the caller surface a "thread not found" error
    # at its preferred granularity (the cross-thread resolver has its
    # own dedicated error for this).
    try:
        if not thread_dir.is_dir():
            return None
    except OSError:
        return None

    latest_path = thread_dir / f"{slug}.{LATEST}"

    # Step 1: symlink wins. Use ``is_symlink`` (rather than ``exists``)
    # so dangling symlinks are also detected and returned — the operator
    # intentionally created the symlink, returning it is the right thing
    # even if the target has since been deleted.
    try:
        if latest_path.is_symlink():
            return latest_path
    except OSError:
        # Defensive: a permission error or weird filesystem state on
        # ``is_symlink``. Fall through to step 2.
        pass

    # Step 2: real directory at ``.latest`` (not a symlink).
    try:
        if latest_path.is_dir():
            return latest_path
    except OSError:
        pass

    # Step 3: walk-to-highest fallback.
    version_re = re.compile(rf"^{re.escape(slug)}\.(\d+)$")
    candidates: List[tuple[int, Path]] = []
    try:
        children = list(thread_dir.iterdir())
    except OSError:
        return None
    for child in children:
        try:
            if not child.is_dir():
                continue
        except OSError:
            # Skip children that vanished or that we can't stat. The
            # other children may still resolve cleanly.
            continue
        match = version_re.match(child.name)
        if match is None:
            continue
        try:
            n = int(match.group(1))
        except ValueError:
            # Defensive — the regex only matches digits, so int() should
            # not fail. Skip on the off-chance the platform / encoding
            # surfaces a surprising digit class.
            continue
        candidates.append((n, child))

    if not candidates:
        # Step 4: no resolution possible.
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


__all__ = [
    "LATEST",
    "resolve_latest",
]
