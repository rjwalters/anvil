"""``anvil:slides`` mirror of ``anvil:deck``'s ``marp_lint`` module.

This is the slides-side import-redirect for the Marp source overflow lint.
The implementation lives in ``anvil/skills/deck/lib/marp_lint.py`` and is the
single source of truth; this module exists so the slides skill can ``from
marp_lint import lint_deck`` without reaching across skill boundaries.

Per the curator addendum on issue #31 (D4):

> ship initially as ``anvil/skills/deck/lib/marp_lint.py`` and
> ``anvil/skills/slides/lib/marp_lint.py`` (either duplicated or with one
> symlink-style "vendor from the other" mechanism). When #10 lands, promote
> to ``anvil/lib/marp_lint.py`` as part of the lib-extraction PR; no
> rewrites required, only an import path swap.

We pick the "vendor from the other" mechanism: this module ``sys.path``-loads
the canonical deck-side ``marp_lint.py`` and re-exports its public names so
no behaviour can drift between deck and slides. The single import-path swap
to ``anvil.lib.marp_lint`` is the only follow-up #10 will need.

Upstream rule pin (re-exported from the deck-side module):

- repo:    marp-team/marp-vscode
- file:    src/diagnostics/preview/slide-content-overflow.ts
- sha:     3b8617431867b68f4241c453ae2c7601a4298aa8
- rule(s): slide-content-overflow

Public API mirrors the deck-side module exactly:

- ``lint_deck(path) -> LintResult``
- ``lint_source(source, *, geometry=None, rules=PORTED_RULES) -> LintResult``
- ``Finding``, ``Geometry``, ``LintResult`` dataclasses.
- ``UPSTREAM_SHA`` and ``PORTED_RULES`` module constants.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


# Resolve the canonical deck-side ``marp_lint`` module by file path so this
# import works no matter where the slides skill is installed (in-tree during
# development, .anvil/skills/slides/ after install) and without requiring the
# ``anvil/`` directory to be importable as a package.
_DECK_MARP_LINT_PATH = (
    Path(__file__).resolve().parents[2] / "deck" / "lib" / "marp_lint.py"
)

if not _DECK_MARP_LINT_PATH.is_file():
    raise ImportError(
        f"anvil:slides marp_lint cannot locate the canonical deck-side "
        f"implementation at {_DECK_MARP_LINT_PATH}. The slides skill's lint "
        f"is a re-export of the deck skill's; both must be installed."
    )

_spec = importlib.util.spec_from_file_location(
    "anvil_deck_marp_lint", _DECK_MARP_LINT_PATH
)
if _spec is None or _spec.loader is None:  # pragma: no cover — defensive
    raise ImportError(
        f"anvil:slides marp_lint failed to build an import spec for "
        f"{_DECK_MARP_LINT_PATH}."
    )

_module = importlib.util.module_from_spec(_spec)
sys.modules["anvil_deck_marp_lint"] = _module
_spec.loader.exec_module(_module)


# Re-export the public API.
Finding = _module.Finding
Geometry = _module.Geometry
LintResult = _module.LintResult
PORTED_RULES = _module.PORTED_RULES
UPSTREAM_SHA = _module.UPSTREAM_SHA
lint_deck = _module.lint_deck
lint_source = _module.lint_source


__all__ = [
    "Finding",
    "Geometry",
    "LintResult",
    "PORTED_RULES",
    "UPSTREAM_SHA",
    "lint_deck",
    "lint_source",
]
