"""Thread-level ``BRIEF.md`` reader for the proposal skill (issue #356, #840, #1092).

This module ships two load-bearing helpers:

- :func:`load_recommendation_target` — re-exported from
  ``anvil.lib.project_brief`` (issue #1092; see "Consolidation history"
  below). Reads the informal-but-now-documented ``recommendation_target``
  frontmatter key from a thread's ``<thread>/BRIEF.md`` and resolves it
  to a typed signal the reviewer can dispatch on. Proposal calibrates
  the resolved value at dim 8 (Open decisions) scoring time — see
  ``anvil/skills/proposal/rubric.md`` §"Dim 8 —
  `recommendation_target: undecided` calibration" for the rationale
  and the calibration prose (that calibration logic is NOT part of the
  helper itself; it lives in the skill's rubric/review command).
- :func:`load_cost_basis` (issue #840) — reads the ``cost_basis``
  frontmatter key (``quoted`` / ``estimated`` / ``none``) and resolves
  it to a typed signal the drafter, reviewer, and auditor dispatch on
  for the priced-table contract and dim 6 (Cost credibility) scoring.
  Not every proposal is a hardware system with vendor-sourceable BOM
  lines (e.g. a partnership/integration proposal) — ``cost_basis``
  makes that axis explicit and orthogonal to ``customer_kind`` (an
  ``internal`` build spec still answers to a budget with priced lines
  that may or may not be vendor-sourced). This helper remains
  proposal-only and is NOT part of the #1092 consolidation.

Consolidation history (issue #1092)
------------------------------------

Issue #356 originally shipped ``load_recommendation_target`` skill-local
per ``CLAUDE.md`` §"Working on this repo" — *"Skill-local first, lib
promotion later. New primitives ship under ``anvil/skills/<skill>/lib/``
until duplication is observed across skills."* At the time, memo's copy
(PR #351) was also skill-local, so proposal mirroring it locally was the
right call per that rule.

Commit ``dba8ba1`` (#382, same day as #356/#364) then promoted memo's
*entire* ``project_brief.py`` — including ``load_recommendation_target``
— wholesale into ``anvil/lib/project_brief.py`` (memo's skill-local file
became a ``from anvil.lib.project_brief import *`` shim). That move
never touched proposal's already-diverged copy, so proposal kept
carrying a byte-identical duplicate of a helper that was no longer
skill-local anywhere. Issue #1092 closes that gap: the reader function
is now imported from the shared module (mirroring memo's shim pattern),
re-exported here via ``__all__`` so every existing proposal call site
(``from project_brief import load_recommendation_target``) keeps
resolving unchanged. ``load_cost_basis`` and ``BRIEF_FILENAME`` are
untouched — ``load_cost_basis`` is genuinely proposal-only, and
``BRIEF_FILENAME`` remains mirrored locally (see below) since it backs
that proposal-only helper.

Why ``BRIEF_FILENAME`` stays mirrored, not imported
-----------------------------------------------------

``BRIEF_FILENAME`` is kept verbatim from
``anvil/skills/memo/lib/project_discovery.BRIEF_FILENAME`` so a future
change to that constant is a pure, deliberate move rather than a silent
cross-skill coupling. It backs :func:`load_cost_basis` — the one helper
in this module that remains skill-local — so importing it from
``anvil.lib.project_brief`` alongside ``load_recommendation_target``
would not shrink the file further; it is kept as a local constant.

Lenient contract
----------------

Both :func:`load_recommendation_target` and :func:`load_cost_basis`
**never raise**. Every absence / malformed path resolves to ``None``.
This preserves byte-identical pre-#356 / pre-#840 behavior for every
thread that does not declare the respective frontmatter key — the
reviewer's dim 8 / dim 6 scoring falls through to the standard
calibration documented in the ``rubric.md`` table.

The closed set
--------------

``load_recommendation_target``'s closed set (``invest`` / ``pass`` /
``conditional`` / ``undecided``) is documented and enforced in
``anvil/lib/project_brief.py``; this module no longer duplicates the
membership list. ``load_cost_basis``'s closed set (``quoted`` /
``estimated`` / ``none``) is proposal-local (see
``_RECOGNIZED_COST_BASES`` below). Typos and out-of-set values are NOT
recognized and resolve to ``None`` (the reviewer falls back to the
legacy calibration — same behavior as a thread with no BRIEF). This
prevents the structured-field surface from silently accepting noise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from anvil.lib.frontmatter import extract_frontmatter as _extract_frontmatter
from anvil.lib.project_brief import load_recommendation_target


# On-disk BRIEF filename. Kept verbatim from
# ``anvil/skills/memo/lib/project_discovery.BRIEF_FILENAME`` so a future
# lib promotion is a pure move. Mirrored here (not imported) because the
# proposal skill MUST NOT take an import dependency on memo internals —
# the two skills coexist as siblings. (``_extract_frontmatter`` above is
# a framework-lib primitive, not a memo-skill internal, so importing it
# from ``anvil.lib.frontmatter`` per issue #1075 does not violate this.)
# Backs :func:`load_cost_basis` below — the one reader that remains
# skill-local post-#1092.
BRIEF_FILENAME = "BRIEF.md"

# The closed set for `cost_basis` (issue #840). `quoted` is the default and
# is byte-identical to pre-#840 behavior (vendor-sourced priced BOM);
# `estimated` signals unsourced internal engineering estimates; `none`
# signals no hardware BOM / no vendor quotes exist for this proposal at all.
_RECOGNIZED_COST_BASES = ("quoted", "estimated", "none")


__all__ = [
    "BRIEF_FILENAME",
    "load_recommendation_target",
    "load_cost_basis",
]


# ``_extract_frontmatter`` used to be defined here (a local copy mirroring
# memo's); it is now the shared ``anvil/lib/frontmatter.py::extract_frontmatter``
# primitive (issue #1075), imported above and aliased to the historical
# private name so every call site in this module is unchanged.

# ``load_recommendation_target`` used to be defined here (a local copy
# mirroring memo's, which was itself promoted under #382); it is now the
# shared ``anvil/lib/project_brief.py::load_recommendation_target``
# primitive (issue #1092), imported above and re-exported via ``__all__``
# so every existing proposal call site is unchanged. See the module
# docstring's "Consolidation history" section for the full rationale.


def load_cost_basis(
    thread_dir: Path,
) -> Optional[Literal["quoted", "estimated", "none"]]:
    """Read ``cost_basis`` from a thread-level ``BRIEF.md`` (issue #840).

    Not every buildable-system proposal is a hardware system with
    vendor-sourceable BOM lines — a partnership/integration proposal (a
    data-backed challenge to another company, say) has no hardware BOM
    and no vendor quotes at all. Pre-#840, the skill's template, rubric,
    and audit all assumed a priced, vendor-sourced BOM unconditionally
    (the Gossamer LAN worked example's shape), leaving a non-hardware
    proposal with two bad options: manufacture hardware-shaped line
    items to satisfy the template, or omit mandated sections and take a
    structural hit.

    ``cost_basis`` makes the missing axis explicit: **whether priced
    claims have external sources at all** — orthogonal to
    ``customer_kind`` (an ``internal`` build spec still answers to a
    budget with priced lines that may or may not be vendor-sourced).

    Parameters
    ----------
    thread_dir
        The thread root directory (the directory holding ``BRIEF.md``
        for the thread, e.g., ``<project>/<slug>/``). NOT a version
        directory.

    Returns
    -------
    Optional[Literal["quoted", "estimated", "none"]]
        The verbatim ``cost_basis`` value when present and in the
        closed set:

        - ``"quoted"`` — priced lines are (or should be) sourced
          against vendor quotes / datasheets / planning ranges. This is
          the default reading when the key is absent — byte-identical
          to pre-#840 behavior.
        - ``"estimated"`` — priced lines are unsourced internal
          engineering-effort estimates; the template emits estimate-
          labelled captions and dim 6 (Cost credibility) calibrates on
          estimate-basis consistency rather than vendor sourceability.
        - ``"none"`` — there is no hardware BOM and no vendor quotes at
          all; the template drops the priced-table requirement and
          commercial terms move to Open Decisions.

        ``None`` for every absence / malformed path:

        - ``<thread_dir>/BRIEF.md`` does not exist.
        - The file exists but has no YAML frontmatter (no opening
          ``---`` delimiter, missing closing delimiter, malformed
          YAML).
        - The frontmatter is a parseable dict but contains no
          ``cost_basis`` key.
        - The frontmatter value is not in the closed set (``quoted`` /
          ``estimated`` / ``none``) — e.g., ``Quoted`` (capitalized),
          ``vendor``, an integer, a list, a null. Callers fall back to
          byte-identical pre-#840 behavior (the same as ``"quoted"``)
          for these noise values.

    Notes
    -----
    Lenient by design — never raises. The contract mirrors
    :func:`load_recommendation_target` exactly: every absence /
    malformed path resolves to ``None``, preserving byte-identical
    pre-#840 behavior for any thread that does not declare
    ``cost_basis``.
    """
    if not isinstance(thread_dir, Path):
        # Defensive: callers may inadvertently pass a string. The helper is
        # documented to take a Path; convert rather than raise to preserve
        # the lenient contract.
        try:
            thread_dir = Path(thread_dir)
        except Exception:
            return None

    brief_path = thread_dir / BRIEF_FILENAME
    if not brief_path.is_file():
        return None

    try:
        text = brief_path.read_text(encoding="utf-8")
    except OSError:
        return None

    fm = _extract_frontmatter(text)
    if fm is None:
        return None

    value = fm.get("cost_basis")
    # Closed-set membership check. Anything not on the recognized list —
    # including booleans, ints, lists, dicts, None, and string typos —
    # falls through to None per the lenient contract.
    if isinstance(value, str) and value in _RECOGNIZED_COST_BASES:
        return value  # type: ignore[return-value]
    return None
