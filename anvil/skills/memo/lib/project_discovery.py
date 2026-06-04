"""Dual-layout thread-root discovery for the memo skill (issue #284).

Sub-deliverable 1 of #283 — the **foundational** discovery primitive that
later sub-deliverables (BRIEF parser #285, rubric overlay selection #286,
cross-thread ref validation #287) depend on knowing where to look.

Background — two on-disk layouts
--------------------------------
The pre-#283 ``anvil:memo`` contract recognized exactly one on-disk shape:
the **classic siblings-under-portfolio** layout, where each thread is a
standalone directory carrying its own ``BRIEF.md`` and (optionally) its
own ``.anvil.json``::

    <portfolio>/
      <thread-a>/
        BRIEF.md              ← per-thread brief
        .anvil.json           ← per-thread config (optional)
        <thread-a>.1/
        <thread-a>.2/
        ...
      <thread-b>/
        BRIEF.md
        <thread-b>.1/
        ...

The Studio canary surfaced a **project-as-thread-root** layout where a
single project-level BRIEF carries shared context (audience, voice, hard
rules) and enumerates per-document metadata in a ``documents:``
frontmatter list. The per-thread BRIEFs collapse into the single project
BRIEF, and the per-document slug directories hold version dirs only::

    <project>/
      BRIEF.md                ← single project brief with documents: list
      .anvil.json             ← project-level defaults (optional)
      <slug-a>/
        <slug-a>.1/
        <slug-a>.2/
        ...
      <slug-b>/
        <slug-b>.1/
        ...
      research/               ← shared evidence pool (already shipped, #281)

See parent issue #283 and the [curator scope confirmation](
https://github.com/rjwalters/anvil/issues/283#issuecomment-4618645809)
for the consolidated model. This module is **scoped to discovery only**:
it recognizes which of the two layouts a path lives in and returns the
thread root + layout marker. Full BRIEF schema parsing is sub-deliverable
2 (#285); rubric overlay selection is sub-deliverable 3 (#286).

Public API
----------

``discover_thread_root(path: Path) -> Optional[DiscoveryResult]``
    Walk upward from ``path`` until a thread root is identified. Returns
    a typed result carrying the thread root, the matched layout (``"classic"``
    or ``"project-brief"``), and — for the project-brief layout — the
    project root and the thread's slug.

``DiscoveryResult`` (dataclass)
    Typed return value. ``layout`` is one of :data:`LAYOUT_CLASSIC` or
    :data:`LAYOUT_PROJECT_BRIEF`. ``project_root`` and ``slug`` are
    populated only for the project-brief layout.

``LAYOUT_CLASSIC`` / ``LAYOUT_PROJECT_BRIEF``
    String constants for the two recognized layouts. Surfaced so callers
    (the upcoming BRIEF parser, the overlay selector) dispatch on the
    same source-of-truth literals.

``BRIEF_FILENAME`` / ``DOCUMENTS_FRONTMATTER_KEY``
    Module constants for the on-disk filename (``"BRIEF.md"``) and the
    YAML frontmatter key (``"documents"``) that gates the project-brief
    layout. Surfaced as constants so the layout contract has a single
    source of truth across this module, its tests, and downstream
    consumers.

``has_project_brief(directory: Path) -> bool``
    Cheap predicate: returns True when ``<directory>/BRIEF.md`` exists
    AND its YAML frontmatter has a non-empty ``documents:`` list.
    Surfaced as a standalone helper so the layout-precedence rule
    (project-brief wins when the list is non-empty) is independently
    testable and reusable.

Algorithm
---------

Given a ``path`` (file or directory; may be a version dir, a thread
root, a project root, or any nested artifact like ``thread.1/memo.md``):

1. Normalize: start from ``path`` if it's a directory, else from
   ``path.parent``. Resolve to an absolute path to make the walk
   filesystem-stable.
2. Walk upward. At each candidate directory ``D``:

   a. **Version-dir check:** if ``D.name`` matches ``<parent>.<N>`` for
      some integer ``N`` (the version-dir naming convention), the thread
      root is ``D.parent``. Resolve layout by checking ``D.parent.parent``
      for a project BRIEF that lists ``D.parent.name`` as a slug.
   b. **Thread-root check:** if ``D`` contains any subdirectory matching
      ``<D.name>.<N>`` (i.e., version dirs whose stem matches ``D``'s
      basename), ``D`` is the thread root. Resolve layout by checking
      ``D.parent`` for a project BRIEF.
   c. **Project-root check:** if ``D`` has ``BRIEF.md`` with a non-empty
      ``documents:`` list AND the original ``path`` lives inside
      ``D/<slug>/`` for one of the slugs we can recognize from the path
      components, treat ``D/<slug>/`` as the thread root.
3. Stop at the filesystem root. Return ``None`` if no thread root
   identified.

Layout precedence
-----------------

Per the issue body's resolution of Open Question #6 from the curator
analysis: when **both** the classic and project-brief layouts could
match (e.g., a project has only one document and the author authored
both a per-thread BRIEF and a project BRIEF), prefer the **project-brief
layout when its ``documents:`` list is non-empty**, fall back to classic
otherwise.

This precedence is enforced **at the parent check**: once we've
identified a thread root candidate, we ask ``has_project_brief(parent)``.
If that returns True AND the thread's slug appears in the documents
list, the result is project-brief. Otherwise, classic — even when the
thread itself carries a BRIEF.

A project BRIEF with an **empty** ``documents:`` list (``documents: []``
or ``documents:`` with no value) does NOT win the precedence check —
``has_project_brief`` returns False, the classic layout is used, and
downstream parsing (sub-deliverable 2) is not triggered. This matches
the issue body's contract: "BRIEF exists with a **non-empty**
``documents:`` list" is the dispatch gate.

Backwards compatibility
-----------------------

For any path under a thread that does NOT have a project BRIEF at its
parent (i.e., every classic thread that exists today), the returned
``DiscoveryResult`` is::

    DiscoveryResult(
        thread_root=<thread_dir>,
        layout=LAYOUT_CLASSIC,
        project_root=None,
        slug=<thread_dir.name>,
    )

This is the v1 contract for the classic layout. Consumers that only
care about ``thread_root`` ignore the layout marker and behave
byte-identically to a pre-#284 ``thread_root`` resolver. The slug field
is populated for convenience (it matches ``thread_root.name`` in the
classic layout) so a single accessor pattern works across both layouts.

A future commands integration (sub-deliverables 2 + 3) will branch on
``layout`` to route BRIEF parsing and rubric overlay selection. The
commands shipped before this module — ``memo-draft``, ``memo-review``,
``memo-revise``, ``memo-audit``, ``memo-figures`` — do NOT yet consume
this utility. The wiring lands when the BRIEF parser and overlay
selector need to dispatch on layout.

No new Python deps
------------------

YAML frontmatter parsing uses ``yaml.safe_load`` from ``pyyaml``, which
is already declared as a base ``[project]`` dep in ``pyproject.toml``
(load-bearing for ``anvil/lib/rubric.py``). No new dependency is
introduced.

Skill-local first
-----------------

Lives under ``anvil/skills/memo/lib/`` per the CLAUDE.md "skill-local
first, lib promotion later" pattern and the precedent set by
``refs_resolver.py`` (PR #281) and ``rubric_overrides_suffix.py``
(PR #265). Promotion to ``anvil/lib/`` is queued for the second-consumer
trigger — likely ``anvil:proposal`` (which has its own portfolio shape)
or ``anvil:pub``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


# On-disk filename for the brief. Surfaced as a constant so the layout
# contract has a single source of truth across this module, its tests,
# and downstream consumers (BRIEF parser in sub-deliverable 2 will share
# this literal).
BRIEF_FILENAME = "BRIEF.md"

# YAML frontmatter key that gates the project-brief layout. When this
# key is present AND its value is a non-empty list, the BRIEF is a
# project-level BRIEF (not a per-thread BRIEF) and the project-brief
# layout dispatch is triggered.
DOCUMENTS_FRONTMATTER_KEY = "documents"

# Layout marker strings. Use these constants — not the string literals —
# in downstream consumers so a rename here propagates automatically.
LAYOUT_CLASSIC = "classic"
LAYOUT_PROJECT_BRIEF = "project-brief"

# Compiled regex for version-dir naming: <stem>.<N> where N is an
# integer. The stem is captured so we can match it against the parent
# directory's basename when identifying a version dir. The pattern
# anchors the dot-N at the end so e.g. "thread.draft" doesn't match.
_VERSION_DIR_RE = re.compile(r"^(?P<stem>.+)\.(?P<num>\d+)$")

# Frontmatter delimiter — three hyphens on their own line, per the
# standard YAML frontmatter convention (Jekyll / Hugo / pandoc /
# Marp / etc.). The opener is the first non-empty line of the file;
# the closer is the next ``---`` line.
_FRONTMATTER_DELIM = "---"


@dataclass(frozen=True)
class DiscoveryResult:
    """Typed return value from :func:`discover_thread_root`.

    Attributes
    ----------
    thread_root
        The directory that holds (or would hold) the version dirs
        ``<thread_root.name>.N/`` for this thread. Always populated.
        For the classic layout this is ``<portfolio>/<thread>/``; for
        the project-brief layout this is ``<project>/<slug>/``.
    layout
        Either :data:`LAYOUT_CLASSIC` or :data:`LAYOUT_PROJECT_BRIEF`.
        Downstream consumers dispatch on this value to decide whether
        to look for a per-thread BRIEF (classic) or a project-level
        BRIEF (project-brief).
    project_root
        For the project-brief layout, the directory containing the
        project BRIEF (``<project>/``). ``None`` for the classic layout.
    slug
        The thread's slug as it appears in the project BRIEF's
        ``documents:`` list (project-brief layout) or as the thread
        directory's basename (classic layout). Always populated; matches
        ``thread_root.name`` in both layouts.
    """

    thread_root: Path
    layout: str
    project_root: Optional[Path]
    slug: str


# ---------------------------------------------------------------------------
# YAML frontmatter helpers
# ---------------------------------------------------------------------------


def _extract_frontmatter(text: str) -> Optional[dict]:
    """Extract the YAML frontmatter from ``text`` and return it as a dict.

    Returns ``None`` when the text has no frontmatter, the frontmatter
    is malformed, or the parsed value isn't a dict. This module is
    intentionally **tolerant** — the layout-dispatch gate degrades to
    classic when the frontmatter is unparseable, matching the
    absence-tolerant convention shared by ``anvil_config.py`` and
    ``refs_resolver.py``.
    """
    # The opener must be the first non-empty line. Leading blank lines
    # and BOM are tolerated, mirroring how most frontmatter consumers
    # (pandoc, Jekyll, Marp) parse the marker.
    lines = text.splitlines()
    # Strip a leading UTF-8 BOM if present on the first line.
    if lines and lines[0].startswith("﻿"):
        lines[0] = lines[0][1:]

    # Find first non-empty line; must be the delimiter.
    first_idx = 0
    while first_idx < len(lines) and lines[first_idx].strip() == "":
        first_idx += 1
    if first_idx >= len(lines):
        return None
    if lines[first_idx].strip() != _FRONTMATTER_DELIM:
        return None

    # Find the closing delimiter starting from the line after the opener.
    body_start = first_idx + 1
    close_idx = None
    for i in range(body_start, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            close_idx = i
            break
    if close_idx is None:
        return None

    yaml_text = "\n".join(lines[body_start:close_idx])
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def has_project_brief(directory: Path) -> bool:
    """Return True when ``<directory>/BRIEF.md`` is a project-level BRIEF.

    A BRIEF qualifies as **project-level** when:

    1. ``<directory>/BRIEF.md`` exists and is a file.
    2. Its YAML frontmatter parses to a dict.
    3. The frontmatter contains a ``documents:`` key whose value is a
       **non-empty list**.

    Returns False for every other shape (missing BRIEF, no frontmatter,
    malformed YAML, ``documents:`` absent, ``documents:`` empty list,
    ``documents:`` non-list value). This is the layout-precedence gate:
    the project-brief layout wins only when ``documents:`` is non-empty,
    per the resolution of Open Question #6 from the curator analysis.

    The function does NOT validate the per-entry schema of the
    ``documents:`` list — that's sub-deliverable 2 (#285). It only
    checks "non-empty list". A list containing entries that fail later
    schema validation still triggers project-brief layout dispatch; the
    BRIEF parser will surface the schema errors downstream.

    Parameters
    ----------
    directory
        Candidate project root.

    Returns
    -------
    bool
        True iff ``directory`` is a project root carrying a non-empty
        documents list.
    """
    if not directory.is_dir():
        return False
    brief = directory / BRIEF_FILENAME
    if not brief.is_file():
        return False
    try:
        text = brief.read_text(encoding="utf-8")
    except OSError:
        return False
    fm = _extract_frontmatter(text)
    if fm is None:
        return False
    docs = fm.get(DOCUMENTS_FRONTMATTER_KEY)
    if not isinstance(docs, list):
        return False
    return len(docs) > 0


def _project_brief_lists_slug(project_dir: Path, slug: str) -> bool:
    """Return True when ``<project_dir>/BRIEF.md``'s ``documents:`` lists ``slug``.

    Each entry in the ``documents:`` list is checked for a ``slug:``
    field matching ``slug``. The check is intentionally lenient on the
    surrounding entry shape — a string entry equal to ``slug`` also
    matches (forward-compat with a shorthand form). The full per-entry
    schema (artifact_type, target_length, etc.) is sub-deliverable 2;
    this helper only needs to recognize "is this slug in the list".

    Returns False when:

    - ``project_dir`` is not a project root (no project BRIEF), OR
    - the documents list is empty, OR
    - no entry's ``slug:`` matches ``slug``.
    """
    if not has_project_brief(project_dir):
        return False
    brief = project_dir / BRIEF_FILENAME
    try:
        text = brief.read_text(encoding="utf-8")
    except OSError:
        return False
    fm = _extract_frontmatter(text)
    if fm is None:
        return False
    docs = fm.get(DOCUMENTS_FRONTMATTER_KEY)
    if not isinstance(docs, list):
        return False
    for entry in docs:
        if isinstance(entry, dict):
            if entry.get("slug") == slug:
                return True
        elif isinstance(entry, str):
            if entry == slug:
                return True
    return False


# ---------------------------------------------------------------------------
# Directory-shape predicates
# ---------------------------------------------------------------------------


def _is_version_dir(directory: Path) -> bool:
    """Return True when ``directory`` is a version dir ``<parent>.<N>``.

    A version dir's basename must match ``<parent.name>.<N>`` for some
    non-negative integer ``N``. This is the on-disk convention codified
    across every memo / proposal / pub thread.
    """
    match = _VERSION_DIR_RE.match(directory.name)
    if match is None:
        return False
    return match.group("stem") == directory.parent.name


def _contains_version_dirs(directory: Path) -> bool:
    """Return True when ``directory`` contains any ``<directory.name>.<N>/`` subdir."""
    if not directory.is_dir():
        return False
    try:
        children = list(directory.iterdir())
    except OSError:
        return False
    for child in children:
        if not child.is_dir():
            continue
        match = _VERSION_DIR_RE.match(child.name)
        if match is None:
            continue
        if match.group("stem") == directory.name:
            return True
    return False


# ---------------------------------------------------------------------------
# Layout resolution
# ---------------------------------------------------------------------------


def _resolve_layout(thread_root: Path) -> DiscoveryResult:
    """Build a :class:`DiscoveryResult` for a confirmed ``thread_root``.

    Applies the layout-precedence rule: project-brief wins when the
    parent directory has a project BRIEF whose ``documents:`` list
    includes this thread's slug. Otherwise classic.

    The slug-in-documents check (not just "parent has project BRIEF")
    is load-bearing: a project BRIEF with a ``documents:`` list that
    happens to NOT name this slug means this thread is a stray
    (perhaps a classic thread that landed inside a project dir by
    mistake, or a thread that hasn't been added to the project BRIEF
    yet). The conservative choice is to treat such a thread as
    classic — it's not formally part of the project from the BRIEF's
    perspective.
    """
    slug = thread_root.name
    parent = thread_root.parent
    if _project_brief_lists_slug(parent, slug):
        return DiscoveryResult(
            thread_root=thread_root,
            layout=LAYOUT_PROJECT_BRIEF,
            project_root=parent,
            slug=slug,
        )
    return DiscoveryResult(
        thread_root=thread_root,
        layout=LAYOUT_CLASSIC,
        project_root=None,
        slug=slug,
    )


# ---------------------------------------------------------------------------
# Public discovery entry point
# ---------------------------------------------------------------------------


def discover_thread_root(path: Path) -> Optional[DiscoveryResult]:
    """Walk upward from ``path`` and return the enclosing thread root.

    Recognizes both the classic siblings-under-portfolio layout and the
    project-as-thread-root layout per the dual-layout discovery
    contract documented in this module's docstring.

    The walk terminates at the first thread root encountered. The
    layout marker on the returned result indicates which on-disk shape
    matched.

    Parameters
    ----------
    path
        Any path under a thread or project. May be a file (e.g. a memo
        body inside a version dir), a directory (a version dir, a
        thread root, a project root), or even a non-existent path
        whose parent components exist (the walk uses ``Path``
        arithmetic and consults the filesystem only at each candidate
        directory).

    Returns
    -------
    Optional[DiscoveryResult]
        ``None`` when no thread root is identifiable — the walk
        reached the filesystem root without finding either a version
        dir pattern or a project BRIEF that contextualizes ``path``.
        Otherwise a typed result carrying the thread root, layout,
        project root (project-brief layout only), and slug.

    Algorithm
    ---------
    See module docstring for the full walk-up algorithm. Summary:

    1. Normalize ``path`` to a directory (use ``.parent`` if file).
    2. Walk upward, examining each candidate directory ``D``:

       - If ``D`` is a version dir (``<parent>.<N>``), the thread
         root is ``D.parent``.
       - Else if ``D`` contains version dirs (``<D.name>.<N>``), the
         thread root is ``D``.
       - Else if ``D`` is a project root (has a project BRIEF), and
         the original ``path`` lives inside ``D/<slug>/`` for some
         slug, the thread root is ``D/<slug>/``.

    3. Stop at the first match, or at the filesystem root.

    Layout precedence (Open Question #6 resolution): the project-brief
    layout wins when the parent of a thread root has a project BRIEF
    whose ``documents:`` list names this thread's slug. Otherwise
    classic.
    """
    # Normalize to a directory. A non-existent path is tolerated; the
    # walk uses Path arithmetic and only consults the filesystem at
    # each candidate.
    p = Path(path)
    try:
        # Use ``.absolute()`` rather than ``.resolve()`` so we don't
        # collapse symlinks the caller deliberately set up — the
        # discovery walk is logical (operates on the path the caller
        # passed), not physical.
        original = p.absolute()
    except OSError:
        original = p

    current = original if original.is_dir() else original.parent

    # The walk-up terminates when ``current == current.parent`` (the
    # filesystem root). ``Path.parents`` would also work, but the
    # explicit loop makes the termination condition load-bearing-
    # readable for the test author chasing edge cases.
    visited: set = set()
    while True:
        # Defensive guard against pathological loops (resolved paths
        # never loop, but a caller passing a logical path with ``..``
        # could in principle).
        key = str(current)
        if key in visited:
            return None
        visited.add(key)

        # (a) Version-dir check: ``current`` is a version dir.
        if _is_version_dir(current):
            thread_root = current.parent
            return _resolve_layout(thread_root)

        # (b) Thread-root check: ``current`` contains version dirs.
        if _contains_version_dirs(current):
            return _resolve_layout(current)

        # (c) Project-root check: ``current`` is a project root and
        #     the original path lives inside one of its slug subdirs.
        if has_project_brief(current):
            # Determine which slug the original path was inside. The
            # first path component between ``current`` and ``original``
            # is the slug candidate.
            try:
                rel = original.relative_to(current)
            except ValueError:
                rel = None
            if rel is not None and rel.parts:
                slug = rel.parts[0]
                thread_root = current / slug
                if _project_brief_lists_slug(current, slug):
                    return DiscoveryResult(
                        thread_root=thread_root,
                        layout=LAYOUT_PROJECT_BRIEF,
                        project_root=current,
                        slug=slug,
                    )
            # We're at a project root but couldn't tie ``original`` to
            # a listed slug — either the path is the project root
            # itself, or it's in an unlisted subdir. Treat as not-a-
            # thread (return None rather than guessing a slug).
            return None

        # Stop at the filesystem root.
        if current.parent == current:
            return None
        current = current.parent


__all__ = [
    "BRIEF_FILENAME",
    "DOCUMENTS_FRONTMATTER_KEY",
    "DiscoveryResult",
    "LAYOUT_CLASSIC",
    "LAYOUT_PROJECT_BRIEF",
    "discover_thread_root",
    "has_project_brief",
]
