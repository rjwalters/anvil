"""Slides-side mirror of ``anvil/skills/deck/tests/test_marp_smoke.py``.

The smoke-test logic (frontmatter parsing, lint assertions, conditional
Marp CLI render) is identical between deck and slides — only the fixture
content differs (talk-flavored theorem + sequence diagram vs. deck-flavored
investor-MathJax + sequence diagram). To prevent drift between the two
sides, this module **does not duplicate the test logic**; instead it loads
the deck-side test module via the same ``importlib.util.spec_from_file_location``
mechanism PR #38 established for ``marp_lint.py``, then re-runs the test
classes against the slides-side fixture.

The deck-side ``test_marp_smoke`` module exposes:

- ``_parse_frontmatter`` — minimal YAML-subset parser (stdlib-only).
- ``TestFixtureFrontmatter`` — asserts ``math: mathjax`` and ``html: true``
  are pinned in the fixture frontmatter.
- ``TestMarpConfigFile`` — asserts ``anvil/lib/marp/config.yml`` exists with
  the load-bearing keys.
- ``TestFixturePassesLint`` — asserts the fixture passes ``slide-content-overflow``.
- ``TestMarpRenders`` — conditional render test (skipped without Marp CLI).

This mirror re-runs each of these against the slides-side fixture by
rebinding the module-level ``_FIXTURE`` constant before unittest discovery.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


# Resolve the canonical deck-side test module by file path. Mirrors the
# pattern in ``anvil/skills/slides/lib/marp_lint.py``.
_HERE = Path(__file__).resolve().parent
_DECK_SMOKE_TEST_PATH = (
    _HERE.parents[1] / "deck" / "tests" / "test_marp_smoke.py"
)

if not _DECK_SMOKE_TEST_PATH.is_file():
    raise ImportError(
        f"anvil:slides test_marp_smoke cannot locate the canonical "
        f"deck-side implementation at {_DECK_SMOKE_TEST_PATH}. The "
        f"slides-side smoke test is a re-export of the deck-side; both "
        f"must be installed."
    )

# Ensure the slides-side ``lib/`` is on ``sys.path`` BEFORE we load the
# deck-side test module. The deck-side module imports ``marp_lint``; when
# loaded under the slides-side test runner we want it to resolve to the
# slides-side re-export, which in turn loads the canonical deck-side
# ``marp_lint`` via the same file-path mechanism. (The slides-side
# ``lib/marp_lint.py`` is itself a re-export per PR #38, so behaviour is
# identical regardless.)
_SLIDES_LIB = _HERE.parent / "lib"
sys.path.insert(0, str(_SLIDES_LIB))

_spec = importlib.util.spec_from_file_location(
    "anvil_deck_test_marp_smoke", _DECK_SMOKE_TEST_PATH
)
if _spec is None or _spec.loader is None:  # pragma: no cover — defensive
    raise ImportError(
        f"anvil:slides test_marp_smoke failed to build an import spec for "
        f"{_DECK_SMOKE_TEST_PATH}."
    )

_deck_module = importlib.util.module_from_spec(_spec)
sys.modules["anvil_deck_test_marp_smoke"] = _deck_module
_spec.loader.exec_module(_deck_module)


# Rebind the fixture path to the slides-side fixture so the inherited test
# classes exercise slides content (theorem statement + sequence diagram)
# rather than deck content (investor-MathJax + sequence diagram).
_SLIDES_FIXTURE = _HERE / "fixtures" / "marp-smoke" / "deck.md"


# Re-export the test classes under the slides namespace. Subclassing with
# an overridden ``_FIXTURE`` would also work, but the deck-side module
# references the fixture at module scope; the cleanest mirror is to
# monkeypatch the module-level constant and re-export the test classes.
_deck_module._FIXTURE = _SLIDES_FIXTURE


TestFixtureFrontmatter = _deck_module.TestFixtureFrontmatter
TestMarpConfigFile = _deck_module.TestMarpConfigFile
TestFixturePassesLint = _deck_module.TestFixturePassesLint
TestMarpRenders = _deck_module.TestMarpRenders
TestMermaidDiagramDoesNotLeakAsRawCode = _deck_module.TestMermaidDiagramDoesNotLeakAsRawCode


class TestSlidesFixtureMatchesPin(unittest.TestCase):
    """Slides-specific assertion: the fixture uses the slides theme.

    A bug here would mean the slides-side fixture accidentally copied the
    deck-side theme reference; this catches drift between the two fixtures.
    """

    def test_fixture_uses_slides_theme(self) -> None:
        fm = _deck_module._parse_frontmatter(_SLIDES_FIXTURE)
        self.assertEqual(
            fm.get("theme"),
            "anvil-slides-theme",
            "slides smoke fixture must use the slides theme; "
            f"got {fm.get('theme')!r}",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
