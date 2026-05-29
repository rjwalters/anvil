"""Smoke tests for the canonical Marp renderer pin (issue #32).

This module asserts three properties of the smoke fixture at
``tests/fixtures/marp-smoke/deck.md``:

1. The fixture parses as valid YAML frontmatter with ``math: mathjax`` and
   ``html: true`` — i.e., the per-document pin is present.
2. The fixture passes the ``slide-content-overflow`` lint from the deck-side
   ``marp_lint`` module (no errors and no warnings).
3. **Conditional** — when ``marp`` is on ``PATH``, invoking
   ``marp <fixture> --pdf --html --config-file anvil/lib/marp/config.yml
   -o /tmp/...pdf`` exits zero and produces a non-empty PDF. When ``marp``
   is not installed the test is **skipped**, matching the existing
   skill-test discipline (no hard dependency on Node tooling at CI time).

Runs under either ``python -m unittest discover anvil/skills/deck/tests/``
or ``pytest anvil/skills/deck/tests/``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


# Add the deck-side lib to ``sys.path`` so we can import ``marp_lint``.
_HERE = Path(__file__).resolve().parent
_LIB = _HERE.parent / "lib"
sys.path.insert(0, str(_LIB))

from marp_lint import lint_deck  # noqa: E402


_FIXTURE = _HERE / "fixtures" / "marp-smoke" / "deck.md"

# Resolve ``anvil/lib/marp/config.yml`` by walking up from this file. The
# fixture and tests live under ``anvil/skills/deck/tests/``; the lib lives
# under ``anvil/lib/``. Four parents land at the repo root.
_REPO_ROOT = _HERE.parents[3]
_MARP_CONFIG = _REPO_ROOT / "anvil" / "lib" / "marp" / "config.yml"


def _parse_frontmatter(path: Path) -> dict[str, str]:
    """Parse the simple ``key: value`` frontmatter at the top of a Marp file.

    This is a tiny YAML-subset parser — enough to confirm the pin is present
    without bringing PyYAML into the test dependency surface (the existing
    skill-test discipline is Python-stdlib only).
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AssertionError(f"{path}: missing opening frontmatter delimiter")
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    raise AssertionError(f"{path}: missing closing frontmatter delimiter")


class TestFixtureFrontmatter(unittest.TestCase):
    """AC2: the smoke fixture pins ``math: mathjax`` and ``html: true``."""

    def test_fixture_exists(self) -> None:
        self.assertTrue(
            _FIXTURE.is_file(),
            f"smoke fixture missing at {_FIXTURE}",
        )

    def test_math_is_mathjax(self) -> None:
        fm = _parse_frontmatter(_FIXTURE)
        self.assertEqual(
            fm.get("math"),
            "mathjax",
            f"smoke fixture should pin math: mathjax; got {fm.get('math')!r}",
        )

    def test_html_is_true(self) -> None:
        fm = _parse_frontmatter(_FIXTURE)
        self.assertEqual(
            fm.get("html"),
            "true",
            f"smoke fixture should pin html: true; got {fm.get('html')!r}",
        )


class TestMarpConfigFile(unittest.TestCase):
    """AC1: ``anvil/lib/marp/config.yml`` exists and is non-empty."""

    def test_config_file_exists(self) -> None:
        self.assertTrue(
            _MARP_CONFIG.is_file(),
            f"canonical Marp config missing at {_MARP_CONFIG}",
        )

    def test_config_pins_html_and_local_files(self) -> None:
        text = _MARP_CONFIG.read_text(encoding="utf-8")
        # Lightweight assertions — we only need to confirm the load-bearing
        # keys are present in their pinned shape. Full YAML parsing is left
        # to Marp at CLI time.
        self.assertIn("html: true", text)
        self.assertIn("allowLocalFiles: true", text)
        # The themeSet should reference both shipped themes by name.
        self.assertIn("anvil-deck.css", text)
        self.assertIn("anvil-slides-theme.css", text)


class TestFixturePassesLint(unittest.TestCase):
    """AC9: the smoke fixture passes ``slide-content-overflow`` cleanly.

    The fixture is deliberately spacious — one slide per concern, no figure
    + bullets stacking — so the lint must report no errors and no warnings.
    """

    def test_no_lint_errors_or_warnings(self) -> None:
        result = lint_deck(_FIXTURE)
        self.assertEqual(
            result.errors,
            [],
            f"smoke fixture must pass lint with no errors; got {result.errors}",
        )
        self.assertEqual(
            result.warnings,
            [],
            f"smoke fixture must pass lint with no warnings; got {result.warnings}",
        )


@unittest.skipUnless(
    shutil.which("marp") is not None,
    "marp CLI not on PATH; skipping render smoke test (matches skill-test discipline)",
)
class TestMarpRenders(unittest.TestCase):
    """AC8 (conditional): the fixture renders cleanly under Marp CLI.

    Skipped when ``marp`` is absent so CI behaviour matches the existing
    skill tests (which do not require Node tooling at test time). Locally,
    when Marp is installed, this asserts that the canonical CLI line
    documented in ``assets/marp-renderer.md`` produces a non-empty PDF.
    """

    def test_renders_non_empty_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_pdf = Path(td) / "smoke.pdf"
            cmd = [
                "marp",
                str(_FIXTURE),
                "--pdf",
                "--html",
                "--config-file",
                str(_MARP_CONFIG),
                "--allow-local-files",
                "-o",
                str(out_pdf),
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                proc.returncode,
                0,
                f"marp render failed (rc={proc.returncode}); "
                f"stderr={proc.stderr!r}",
            )
            self.assertTrue(out_pdf.is_file(), "marp produced no output file")
            self.assertGreater(
                out_pdf.stat().st_size,
                0,
                "marp produced an empty PDF",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
