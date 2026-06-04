"""Tests for ``anvil.skills.memo.lib.anvil_config.load_body_filename`` (issue #279).

Covers the per-thread ``body_filename`` reader added under issue #279. The
``body_filename`` field is a **top-level** key in ``<thread>/.anvil.json``
(sibling to ``rubric_overrides`` and ``target_length``), NOT nested inside
``rubric_overrides``. The reader has two forms: lenient
(``load_body_filename``) used by the six memo lifecycle commands and strict
(``load_body_filename_strict``) used by this test suite.

Acceptance criteria covered (from issue #279 curator brief):

- AC1: ``load_body_filename(thread_dir) -> str`` returns ``"memo.md"`` when
  key absent/malformed; lenient form warns and degrades, strict form raises.
- AC2: ``body_filename`` must be non-empty string, end in ``.md``, contain
  no ``/`` / ``\\`` / ``..``; violations degrade to ``"memo.md"`` with
  ``UserWarning``.
- AC9: backward-compat — a thread with no ``body_filename`` (or no
  ``.anvil.json``) returns the default ``"memo.md"`` unchanged.
- AC12: no new Python deps; the loader uses ``pathlib`` + ``json`` only
  (existing AC10 test guards ``pyproject.toml``).

Runs under either ``python -m unittest discover anvil/skills/memo/tests/``
or ``pytest anvil/skills/memo/tests/`` per the issue #58 cross-skill
packaging convention.
"""

from __future__ import annotations

import json
import sys
import unittest
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


# The memo skill keeps its lib modules under its own ``lib/`` per the
# CLAUDE.md "skill-local first, lib promotion later" pattern. Add it to
# ``sys.path`` so tests import without a package install step — mirrors
# ``test_anvil_config.py`` exactly.
_HERE = Path(__file__).resolve().parent
_LIB = _HERE.parent / "lib"
sys.path.insert(0, str(_LIB))

from anvil_config import (  # noqa: E402
    DEFAULT_BODY_FILENAME,
    load_body_filename,
    load_body_filename_strict,
)


def _write_anvil_json(thread_dir: Path, payload: Any) -> Path:
    """Write ``payload`` as JSON to ``<thread_dir>/.anvil.json`` and return the path."""
    thread_dir.mkdir(parents=True, exist_ok=True)
    path = thread_dir / ".anvil.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_raw(thread_dir: Path, raw: str) -> Path:
    """Write ``raw`` text to ``<thread_dir>/.anvil.json`` (for malformed-JSON cases)."""
    thread_dir.mkdir(parents=True, exist_ok=True)
    path = thread_dir / ".anvil.json"
    path.write_text(raw, encoding="utf-8")
    return path


class _TmpThreadBase(unittest.TestCase):
    """Mixin: per-test temp dir for the memo thread root."""

    def setUp(self) -> None:
        self._td = TemporaryDirectory()
        self.thread_dir = Path(self._td.name) / "demo-thread"
        self.thread_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._td.cleanup)


# ---------------------------------------------------------------------------
# Default constant
# ---------------------------------------------------------------------------


class TestDefaultConstant(unittest.TestCase):
    """``DEFAULT_BODY_FILENAME`` pins the backward-compat default."""

    def test_default_is_memo_md(self) -> None:
        """The default is ``"memo.md"`` — load-bearing backward-compat contract."""
        self.assertEqual(DEFAULT_BODY_FILENAME, "memo.md")


# ---------------------------------------------------------------------------
# Empty / absent cases — AC1 + AC9 backward-compat
# ---------------------------------------------------------------------------


class TestEmptyCases(_TmpThreadBase):
    """No ``.anvil.json``, no ``body_filename`` key — default returned."""

    def test_missing_anvil_json_returns_default(self) -> None:
        """A thread with no ``.anvil.json`` returns ``"memo.md"`` — AC9 backward-compat."""
        result = load_body_filename(self.thread_dir)
        self.assertEqual(result, "memo.md")

    def test_anvil_json_without_body_filename_returns_default(self) -> None:
        """An ``.anvil.json`` with no ``body_filename`` key returns ``"memo.md"``."""
        _write_anvil_json(
            self.thread_dir,
            {"max_iterations": 4, "rubric_overrides": {"memo_subtype": "x"}},
        )
        result = load_body_filename(self.thread_dir)
        self.assertEqual(result, "memo.md")

    def test_explicit_null_returns_default(self) -> None:
        """``body_filename: null`` is treated like absent — returns default."""
        _write_anvil_json(self.thread_dir, {"body_filename": None})
        result = load_body_filename(self.thread_dir)
        self.assertEqual(result, "memo.md")

    def test_malformed_json_returns_default(self) -> None:
        """Malformed JSON degrades silently to default (mirrors rubric_overrides)."""
        _write_raw(self.thread_dir, "{not valid json")
        result = load_body_filename(self.thread_dir)
        self.assertEqual(result, "memo.md")


# ---------------------------------------------------------------------------
# Happy path — well-formed values returned verbatim
# ---------------------------------------------------------------------------


class TestHappyPath(_TmpThreadBase):
    """Well-formed body filenames are returned verbatim."""

    def test_paper_md(self) -> None:
        """``paper.md`` — the latency-wall canary shape."""
        _write_anvil_json(self.thread_dir, {"body_filename": "paper.md"})
        self.assertEqual(load_body_filename(self.thread_dir), "paper.md")

    def test_plan_md(self) -> None:
        """``plan.md`` — the execution-plan canary shape."""
        _write_anvil_json(self.thread_dir, {"body_filename": "plan.md"})
        self.assertEqual(load_body_filename(self.thread_dir), "plan.md")

    def test_thesis_md(self) -> None:
        """``thesis.md`` — the team-thesis canary shape."""
        _write_anvil_json(self.thread_dir, {"body_filename": "thesis.md"})
        self.assertEqual(load_body_filename(self.thread_dir), "thesis.md")

    def test_vision_md(self) -> None:
        """``vision.md`` — the technical-vision canary shape."""
        _write_anvil_json(self.thread_dir, {"body_filename": "vision.md"})
        self.assertEqual(load_body_filename(self.thread_dir), "vision.md")

    def test_explicit_memo_md(self) -> None:
        """Explicit ``body_filename: "memo.md"`` is byte-identical to default."""
        _write_anvil_json(self.thread_dir, {"body_filename": "memo.md"})
        self.assertEqual(load_body_filename(self.thread_dir), "memo.md")

    def test_coexists_with_rubric_overrides(self) -> None:
        """``body_filename`` is a peer of ``rubric_overrides`` at the top level."""
        _write_anvil_json(
            self.thread_dir,
            {
                "max_iterations": 8,
                "body_filename": "paper.md",
                "rubric_overrides": {
                    "memo_subtype": "latency-wall",
                    "dim_1_calibration": "position paper — score on positional clarity",
                },
            },
        )
        # body_filename loaded correctly...
        self.assertEqual(load_body_filename(self.thread_dir), "paper.md")
        # ...and rubric_overrides remain undisturbed (sanity check the
        # two readers don't step on each other).
        from anvil_config import load_rubric_overrides  # noqa: E402
        overrides = load_rubric_overrides(self.thread_dir)
        self.assertEqual(overrides.memo_subtype, "latency-wall")


# ---------------------------------------------------------------------------
# Validation rules (AC2) — malformed input degrades to default + warns
# ---------------------------------------------------------------------------


class TestValidation(_TmpThreadBase):
    """Lenient form: malformed values degrade to default with UserWarning."""

    def _assert_default_with_warning(self, body_filename: Any, expected_phrase: str) -> None:
        """Helper: assert lenient form returns default + emits a warning."""
        _write_anvil_json(self.thread_dir, {"body_filename": body_filename})
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = load_body_filename(self.thread_dir)
        self.assertEqual(result, "memo.md")
        msgs = [str(w.message) for w in caught]
        self.assertTrue(
            any(expected_phrase in m for m in msgs),
            f"expected warning containing {expected_phrase!r}, got {msgs}",
        )

    def test_non_string_int_rejected(self) -> None:
        self._assert_default_with_warning(42, "must be a string")

    def test_non_string_list_rejected(self) -> None:
        self._assert_default_with_warning(["paper.md"], "must be a string")

    def test_non_string_dict_rejected(self) -> None:
        self._assert_default_with_warning({"name": "paper.md"}, "must be a string")

    def test_non_string_bool_rejected(self) -> None:
        # bool is not str — caught by the isinstance check.
        self._assert_default_with_warning(True, "must be a string")

    def test_empty_string_rejected(self) -> None:
        self._assert_default_with_warning("", "must be a non-empty string")

    def test_whitespace_only_rejected(self) -> None:
        self._assert_default_with_warning("   ", "must be a non-empty string")

    def test_forward_slash_rejected(self) -> None:
        self._assert_default_with_warning("subdir/paper.md", "must not contain '/'")

    def test_backslash_rejected(self) -> None:
        self._assert_default_with_warning("subdir\\paper.md", "must not contain '/'")

    def test_absolute_path_rejected(self) -> None:
        self._assert_default_with_warning("/etc/passwd", "must not contain '/'")

    def test_dot_dot_traversal_rejected(self) -> None:
        # `..paper.md` doesn't contain a `/`, but the `..` substring triggers
        # the anti-traversal guard.
        self._assert_default_with_warning("..paper.md", "must not contain '..'")

    def test_dot_dot_in_middle_rejected(self) -> None:
        self._assert_default_with_warning("paper..md", "must not contain '..'")

    def test_missing_md_suffix_rejected(self) -> None:
        self._assert_default_with_warning("paper", "must end in '.md'")

    def test_wrong_extension_rejected(self) -> None:
        self._assert_default_with_warning("paper.txt", "must end in '.md'")

    def test_pdf_extension_rejected(self) -> None:
        # A reader who copy-pastes the PDF filename instead of the source
        # filename sees a clear warning.
        self._assert_default_with_warning("paper.pdf", "must end in '.md'")

    def test_md_in_middle_rejected(self) -> None:
        # `.md` must be the suffix, not anywhere in the string.
        self._assert_default_with_warning("paper.md.bak", "must end in '.md'")


# ---------------------------------------------------------------------------
# Strict variant (AC1)
# ---------------------------------------------------------------------------


class TestStrictVariant(_TmpThreadBase):
    """``load_body_filename_strict`` raises where the lenient form warns."""

    def test_strict_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_body_filename_strict(self.thread_dir)

    def test_strict_malformed_json_raises(self) -> None:
        _write_raw(self.thread_dir, "{not json")
        with self.assertRaises(json.JSONDecodeError):
            load_body_filename_strict(self.thread_dir)

    def test_strict_non_dict_top_level_raises(self) -> None:
        _write_raw(self.thread_dir, "[1, 2, 3]")
        with self.assertRaises(ValueError):
            load_body_filename_strict(self.thread_dir)

    def test_strict_returns_default_when_key_absent(self) -> None:
        """Absent ``body_filename`` is the documented backward-compat shape, not a validation failure."""
        _write_anvil_json(self.thread_dir, {"max_iterations": 4})
        result = load_body_filename_strict(self.thread_dir)
        self.assertEqual(result, "memo.md")

    def test_strict_raises_on_empty_string(self) -> None:
        _write_anvil_json(self.thread_dir, {"body_filename": ""})
        with self.assertRaises(ValueError) as ctx:
            load_body_filename_strict(self.thread_dir)
        self.assertIn("non-empty", str(ctx.exception))

    def test_strict_raises_on_path_traversal(self) -> None:
        _write_anvil_json(self.thread_dir, {"body_filename": "../passwd.md"})
        with self.assertRaises(ValueError) as ctx:
            load_body_filename_strict(self.thread_dir)
        # The `/` check fires first (`../passwd.md` contains both `/` and `..`).
        msg = str(ctx.exception)
        self.assertTrue("'/'" in msg or "'..'" in msg)

    def test_strict_raises_on_non_md_suffix(self) -> None:
        _write_anvil_json(self.thread_dir, {"body_filename": "paper.txt"})
        with self.assertRaises(ValueError) as ctx:
            load_body_filename_strict(self.thread_dir)
        self.assertIn(".md", str(ctx.exception))

    def test_strict_passes_on_clean_input(self) -> None:
        _write_anvil_json(self.thread_dir, {"body_filename": "paper.md"})
        result = load_body_filename_strict(self.thread_dir)
        self.assertEqual(result, "paper.md")


# ---------------------------------------------------------------------------
# UserWarning emission shape (lenient form)
# ---------------------------------------------------------------------------


class TestWarningEmission(_TmpThreadBase):
    """Warnings are emitted via ``warnings.warn`` with category ``UserWarning``."""

    def test_warning_category_is_user_warning(self) -> None:
        _write_anvil_json(self.thread_dir, {"body_filename": "paper.txt"})
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            load_body_filename(self.thread_dir)
        # Find the body_filename warning specifically (filter out unrelated ones).
        body_fn_warnings = [
            w for w in caught if "body_filename" in str(w.message)
        ]
        self.assertEqual(len(body_fn_warnings), 1)
        self.assertEqual(body_fn_warnings[0].category, UserWarning)


# ---------------------------------------------------------------------------
# AC12: no new Python deps — the loader uses pathlib + json only
# ---------------------------------------------------------------------------


class TestNoNewDeps(unittest.TestCase):
    """The body_filename reader uses pathlib + json only (no third-party imports beyond pydantic).

    The pyproject.toml-level guard lives at
    ``tests/skills/memo/test_memo_migrate.py::test_ac10_no_new_python_deps_in_pyproject``
    (added in PR #267 / #276). This local test sanity-checks that the
    ``anvil_config`` module's imports are confined to pathlib, json,
    warnings, dataclasses, typing, re, and pydantic — the same import set
    PR #267 landed for the ``rubric_overrides`` reader.
    """

    def test_module_imports_only_stdlib_plus_pydantic(self) -> None:
        """Inspect ``anvil_config.py`` source for unexpected imports."""
        anvil_config_path = (
            Path(__file__).resolve().parent.parent / "lib" / "anvil_config.py"
        )
        text = anvil_config_path.read_text(encoding="utf-8")
        # Allowed top-level module names (anything else fails the test).
        allowed = {
            "__future__",
            "json",
            "re",
            "warnings",
            "dataclasses",
            "pathlib",
            "typing",
            "pydantic",
        }
        # Walk every "from X import ..." and "import X" line.
        import re

        # Match `from <module> import ...` and `import <module>` at the line start.
        import_pattern = re.compile(
            r"^(?:from\s+(?P<from_mod>\S+)\s+import|import\s+(?P<imp_mod>\S+))",
            re.MULTILINE,
        )
        for match in import_pattern.finditer(text):
            module = match.group("from_mod") or match.group("imp_mod")
            # Take the top-level package name.
            top_level = module.split(".")[0]
            self.assertIn(
                top_level,
                allowed,
                f"Unexpected import in anvil_config.py: {module!r} "
                f"(top-level: {top_level!r}). Allowed: {sorted(allowed)}",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
