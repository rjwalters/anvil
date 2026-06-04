"""Tests for ``anvil.skills.memo.lib.anvil_config``.

Covers issue #233 sub-issue 1 (schema + reader). Schema fields and parse
behavior are exercised against synthetic ``.anvil.json`` fixtures written
into ``tmp_path`` per test — no on-disk fixtures because the input shape is
small JSON, easier to read inline than to chase to a fixtures dir.

Sub-issues 2 (#265) and 3 (#266) ship the reviewer integration and the
worked-example templates; this test file is scoped to the schema + reader
behavior only.

Runs under either ``python -m unittest discover anvil/skills/memo/tests/``
or ``pytest anvil/skills/memo/tests/``.
"""

from __future__ import annotations

import json
import sys
import unittest
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict


# The memo skill keeps its lib modules under its own ``lib/`` per the
# CLAUDE.md "skill-local first, lib promotion later" pattern. Add it to
# ``sys.path`` so tests import without a package install step — mirrors
# ``test_memo_image_refs.py`` exactly.
_HERE = Path(__file__).resolve().parent
_LIB = _HERE.parent / "lib"
sys.path.insert(0, str(_LIB))

from anvil_config import (  # noqa: E402
    CalibrationOverride,
    MAX_DIM,
    MIN_DIM,
    RubricOverrides,
    TargetLengthRange,
    body_filename_for,
    load_rubric_overrides,
    load_rubric_overrides_strict,
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
# Empty / absent cases
# ---------------------------------------------------------------------------


class TestEmptyCases(_TmpThreadBase):
    """No ``.anvil.json``, no ``rubric_overrides`` block, empty block."""

    def test_missing_anvil_json_returns_empty_overrides(self) -> None:
        result = load_rubric_overrides(self.thread_dir)
        self.assertIsInstance(result, RubricOverrides)
        self.assertTrue(result.is_empty)
        self.assertIsNone(result.memo_subtype)
        self.assertEqual(result.calibrations, [])
        self.assertIsNone(result.target_length)
        self.assertEqual(result.unknown_keys, {})

    def test_anvil_json_without_rubric_overrides_returns_empty(self) -> None:
        _write_anvil_json(
            self.thread_dir,
            {"max_iterations": 4, "target_length": {"words": [1800, 2400]}},
        )
        result = load_rubric_overrides(self.thread_dir)
        self.assertTrue(result.is_empty)

    def test_empty_rubric_overrides_block_returns_empty(self) -> None:
        _write_anvil_json(self.thread_dir, {"rubric_overrides": {}})
        result = load_rubric_overrides(self.thread_dir)
        self.assertTrue(result.is_empty)

    def test_calibration_for_returns_none_when_empty(self) -> None:
        overrides = RubricOverrides()
        for dim in range(MIN_DIM, MAX_DIM + 1):
            self.assertIsNone(overrides.calibration_for(dim))


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath(_TmpThreadBase):
    """Well-formed ``rubric_overrides`` blocks parse cleanly."""

    def test_full_synthesis_brief_shape(self) -> None:
        """The brasidas-synthesis canary shape (issue #233 worked example)."""
        _write_anvil_json(
            self.thread_dir,
            {
                "max_iterations": 8,
                "rubric_overrides": {
                    "memo_subtype": "synthesis-brief",
                    "dim_1_calibration": "decision-framework — score on framework clarity + sub-recommendation sharpness, not on single ranked recommendation",
                    "dim_5_calibration": "defers to underlying market models — score on integration quality not on fresh sizing",
                    "dim_6_calibration": "defers to underlying market models — score on whether financial framing supports positioning",
                    "dim_7_calibration": "target length 9000-13000 words; score against declared target",
                    "target_length": {"words": [9000, 13000]},
                },
            },
        )
        result = load_rubric_overrides(self.thread_dir)
        self.assertFalse(result.is_empty)
        self.assertEqual(result.memo_subtype, "synthesis-brief")
        self.assertEqual(len(result.calibrations), 4)
        # Sorted by dimension.
        self.assertEqual([c.dimension for c in result.calibrations], [1, 5, 6, 7])
        self.assertIn("decision-framework", result.calibration_for(1))
        self.assertIsNone(result.calibration_for(2))
        self.assertIsNotNone(result.target_length)
        self.assertEqual(result.target_length.min_words, 9000)
        self.assertEqual(result.target_length.max_words, 13000)
        self.assertEqual(result.target_length.source_key, "words")

    def test_pages_conversion_to_words(self) -> None:
        """``pages: [N, M]`` converts at 600 words/page (SKILL.md convention)."""
        _write_anvil_json(
            self.thread_dir,
            {
                "rubric_overrides": {
                    "memo_subtype": "feedback-memo",
                    "target_length": {"pages": [3, 4]},
                }
            },
        )
        result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(result.target_length.min_words, 1800)
        self.assertEqual(result.target_length.max_words, 2400)
        self.assertEqual(result.target_length.source_key, "pages")

    def test_subtype_only(self) -> None:
        """A ``memo_subtype`` with no calibrations and no target_length is valid."""
        _write_anvil_json(
            self.thread_dir,
            {"rubric_overrides": {"memo_subtype": "decision-framework"}},
        )
        result = load_rubric_overrides(self.thread_dir)
        self.assertFalse(result.is_empty)
        self.assertEqual(result.memo_subtype, "decision-framework")
        self.assertEqual(result.calibrations, [])
        self.assertIsNone(result.target_length)

    def test_calibration_only(self) -> None:
        """A single ``dim_N_calibration`` is valid without ``memo_subtype``."""
        _write_anvil_json(
            self.thread_dir,
            {"rubric_overrides": {"dim_7_calibration": "longer is OK"}},
        )
        result = load_rubric_overrides(self.thread_dir)
        self.assertFalse(result.is_empty)
        self.assertIsNone(result.memo_subtype)
        self.assertEqual(result.calibration_for(7), "longer is OK")

    def test_all_nine_dims_accepted(self) -> None:
        """Every dim from 1 through 9 is in range (memo rubric is /44 with 9 dims)."""
        block: Dict[str, Any] = {"rubric_overrides": {}}
        for dim in range(MIN_DIM, MAX_DIM + 1):
            block["rubric_overrides"][f"dim_{dim}_calibration"] = f"dim {dim} note"
        _write_anvil_json(self.thread_dir, block)
        result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(len(result.calibrations), MAX_DIM - MIN_DIM + 1)

    def test_calibration_text_preserved_verbatim(self) -> None:
        """Calibration prose must round-trip exactly — no rewording, no trim.

        The reviewer (sub-issue 2 / #265) attaches this text as the audit
        trail. Any normalization here would silently change the audit trail.
        """
        text = "  decision-framework  —  preserve  whitespace  "
        _write_anvil_json(
            self.thread_dir,
            {"rubric_overrides": {"dim_1_calibration": text}},
        )
        result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(result.calibration_for(1), text)


# ---------------------------------------------------------------------------
# Malformed-block tolerance (lenient form)
# ---------------------------------------------------------------------------


class TestMalformedTolerance(_TmpThreadBase):
    """Malformed values are dropped with a warning; valid siblings preserved."""

    def test_malformed_json_returns_empty(self) -> None:
        _write_raw(self.thread_dir, "{not valid json")
        result = load_rubric_overrides(self.thread_dir)
        self.assertTrue(result.is_empty)

    def test_non_dict_top_level_returns_empty(self) -> None:
        _write_raw(self.thread_dir, '["array", "not", "dict"]')
        result = load_rubric_overrides(self.thread_dir)
        self.assertTrue(result.is_empty)

    def test_non_dict_rubric_overrides_returns_empty(self) -> None:
        _write_anvil_json(
            self.thread_dir, {"rubric_overrides": "should be a dict"}
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = load_rubric_overrides(self.thread_dir)
        self.assertTrue(result.is_empty)
        self.assertTrue(
            any("must be a dict" in str(w.message) for w in caught),
            f"expected dict warning, got {[str(w.message) for w in caught]}",
        )

    def test_non_string_memo_subtype_dropped_others_preserved(self) -> None:
        _write_anvil_json(
            self.thread_dir,
            {
                "rubric_overrides": {
                    "memo_subtype": 42,
                    "dim_1_calibration": "valid",
                }
            },
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = load_rubric_overrides(self.thread_dir)
        self.assertIsNone(result.memo_subtype)
        self.assertEqual(result.calibration_for(1), "valid")
        self.assertTrue(any("memo_subtype" in str(w.message) for w in caught))

    def test_empty_memo_subtype_dropped(self) -> None:
        _write_anvil_json(
            self.thread_dir,
            {"rubric_overrides": {"memo_subtype": "   "}},
        )
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = load_rubric_overrides(self.thread_dir)
        self.assertIsNone(result.memo_subtype)

    def test_out_of_range_dim_dropped(self) -> None:
        _write_anvil_json(
            self.thread_dir,
            {
                "rubric_overrides": {
                    "dim_0_calibration": "out of range low",
                    "dim_10_calibration": "out of range high",
                    "dim_3_calibration": "valid",
                }
            },
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(len(result.calibrations), 1)
        self.assertEqual(result.calibrations[0].dimension, 3)
        msgs = [str(w.message) for w in caught]
        self.assertTrue(any("out of range" in m for m in msgs))

    def test_non_string_calibration_value_dropped(self) -> None:
        _write_anvil_json(
            self.thread_dir,
            {
                "rubric_overrides": {
                    "dim_1_calibration": ["list", "not", "string"],
                    "dim_2_calibration": "valid",
                }
            },
        )
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = load_rubric_overrides(self.thread_dir)
        self.assertIsNone(result.calibration_for(1))
        self.assertEqual(result.calibration_for(2), "valid")

    def test_empty_calibration_string_dropped(self) -> None:
        _write_anvil_json(
            self.thread_dir,
            {"rubric_overrides": {"dim_1_calibration": "   "}},
        )
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(result.calibrations, [])

    def test_duplicate_dim_keeps_first(self) -> None:
        # JSON dicts can't have literal duplicate string keys, but Python's
        # dict construction would silently keep the last. To exercise the
        # "duplicate dimension" branch we hand-build a dict that compresses
        # to one key on disk yet has a colliding regex match.
        # The realistic shape: dim_05_calibration AND dim_5_calibration both
        # parse to dimension 5 — issue this via the parse path directly.
        _write_anvil_json(
            self.thread_dir,
            {
                "rubric_overrides": {
                    "dim_5_calibration": "first wins",
                    "dim_05_calibration": "second is duplicate",
                }
            },
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(len(result.calibrations), 1)
        self.assertEqual(result.calibrations[0].dimension, 5)
        self.assertEqual(result.calibrations[0].text, "first wins")
        msgs = [str(w.message) for w in caught]
        self.assertTrue(any("declared more than once" in m for m in msgs))


# ---------------------------------------------------------------------------
# target_length malformed-input coverage
# ---------------------------------------------------------------------------


class TestTargetLengthValidation(_TmpThreadBase):
    """``rubric_overrides.target_length`` shape validation."""

    def _load_target(self, target_length: Any) -> RubricOverrides:
        _write_anvil_json(
            self.thread_dir,
            {"rubric_overrides": {"target_length": target_length}},
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return load_rubric_overrides(self.thread_dir)

    def test_both_words_and_pages_rejected(self) -> None:
        result = self._load_target({"words": [1800, 2400], "pages": [3, 4]})
        self.assertIsNone(result.target_length)

    def test_neither_words_nor_pages_rejected(self) -> None:
        result = self._load_target({})
        self.assertIsNone(result.target_length)

    def test_non_list_range_rejected(self) -> None:
        result = self._load_target({"words": "1800-2400"})
        self.assertIsNone(result.target_length)

    def test_wrong_length_list_rejected(self) -> None:
        result = self._load_target({"words": [1800]})
        self.assertIsNone(result.target_length)
        result = self._load_target({"words": [1800, 2400, 3000]})
        self.assertIsNone(result.target_length)

    def test_non_int_elements_rejected(self) -> None:
        result = self._load_target({"words": [1800.5, 2400]})
        self.assertIsNone(result.target_length)
        result = self._load_target({"words": ["1800", "2400"]})
        self.assertIsNone(result.target_length)

    def test_bool_elements_rejected(self) -> None:
        # Booleans are an int subclass in Python — guard against True/False
        # being silently accepted as 1/0.
        result = self._load_target({"words": [True, False]})
        self.assertIsNone(result.target_length)

    def test_negative_elements_rejected(self) -> None:
        result = self._load_target({"words": [-100, 1000]})
        self.assertIsNone(result.target_length)

    def test_min_greater_than_max_rejected(self) -> None:
        result = self._load_target({"words": [2400, 1800]})
        self.assertIsNone(result.target_length)

    def test_min_equal_max_accepted(self) -> None:
        result = self._load_target({"words": [2000, 2000]})
        self.assertIsNotNone(result.target_length)
        self.assertEqual(result.target_length.min_words, 2000)
        self.assertEqual(result.target_length.max_words, 2000)

    def test_extended_shape_default_rejected(self) -> None:
        """``rubric_overrides.target_length`` rejects extended-shape ``default`` key.

        Extended (per-version) overrides belong at the top level of
        ``.anvil.json``, not inside ``rubric_overrides``. This is a
        deliberate scope decision documented in the module docstring.
        """
        result = self._load_target(
            {"default": {"words": [1800, 2400]}}
        )
        self.assertIsNone(result.target_length)

    def test_extended_shape_overrides_rejected(self) -> None:
        result = self._load_target(
            {"overrides": {"v1": {"words": [1800, 2400]}}}
        )
        self.assertIsNone(result.target_length)

    def test_non_dict_target_length_rejected(self) -> None:
        result = self._load_target([1800, 2400])
        self.assertIsNone(result.target_length)


# ---------------------------------------------------------------------------
# Unknown-key forward-compat
# ---------------------------------------------------------------------------


class TestUnknownKeyForwardCompat(_TmpThreadBase):
    """Unknown keys preserved verbatim under ``unknown_keys`` with a warning."""

    def test_unknown_key_preserved(self) -> None:
        _write_anvil_json(
            self.thread_dir,
            {
                "rubric_overrides": {
                    "memo_subtype": "synthesis-brief",
                    "concision_discipline": {"penalty_per_word": 0.05},
                    "future_knob": "TBD",
                }
            },
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(result.memo_subtype, "synthesis-brief")
        self.assertEqual(
            result.unknown_keys.get("concision_discipline"),
            {"penalty_per_word": 0.05},
        )
        self.assertEqual(result.unknown_keys.get("future_knob"), "TBD")
        msgs = [str(w.message) for w in caught]
        self.assertTrue(
            any("concision_discipline" in m for m in msgs),
            f"expected unknown-key warning, got {msgs}",
        )

    def test_unknown_key_does_not_make_is_empty_true(self) -> None:
        """A block with only unknown keys still reports ``is_empty == False``.

        This is the load-bearing forward-compat behavior: a future-shipped
        knob is "non-empty overrides" from the caller's perspective even if
        the current loader doesn't know what to do with it.
        """
        _write_anvil_json(
            self.thread_dir,
            {"rubric_overrides": {"future_knob": "active"}},
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = load_rubric_overrides(self.thread_dir)
        self.assertFalse(result.is_empty)


# ---------------------------------------------------------------------------
# Strict variant
# ---------------------------------------------------------------------------


class TestStrictVariant(_TmpThreadBase):
    """``load_rubric_overrides_strict`` raises where the lenient form warns."""

    def test_strict_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_rubric_overrides_strict(self.thread_dir)

    def test_strict_malformed_json_raises(self) -> None:
        _write_raw(self.thread_dir, "{not json")
        with self.assertRaises(json.JSONDecodeError):
            load_rubric_overrides_strict(self.thread_dir)

    def test_strict_non_dict_top_level_raises(self) -> None:
        _write_raw(self.thread_dir, "[1, 2, 3]")
        with self.assertRaises(ValueError):
            load_rubric_overrides_strict(self.thread_dir)

    def test_strict_returns_when_no_rubric_overrides_block(self) -> None:
        _write_anvil_json(self.thread_dir, {"max_iterations": 4})
        result = load_rubric_overrides_strict(self.thread_dir)
        self.assertTrue(result.is_empty)

    def test_strict_raises_on_unknown_key(self) -> None:
        _write_anvil_json(
            self.thread_dir,
            {"rubric_overrides": {"unknown_knob": 42}},
        )
        with self.assertRaises(ValueError) as ctx:
            load_rubric_overrides_strict(self.thread_dir)
        self.assertIn("unknown_knob", str(ctx.exception))

    def test_strict_raises_on_out_of_range_dim(self) -> None:
        _write_anvil_json(
            self.thread_dir,
            {"rubric_overrides": {"dim_0_calibration": "out of range"}},
        )
        with self.assertRaises(ValueError) as ctx:
            load_rubric_overrides_strict(self.thread_dir)
        self.assertIn("out of range", str(ctx.exception))

    def test_strict_passes_on_clean_input(self) -> None:
        _write_anvil_json(
            self.thread_dir,
            {
                "rubric_overrides": {
                    "memo_subtype": "feedback-memo",
                    "dim_1_calibration": "position clarity, not single-recommendation",
                }
            },
        )
        result = load_rubric_overrides_strict(self.thread_dir)
        self.assertEqual(result.memo_subtype, "feedback-memo")
        self.assertEqual(
            result.calibration_for(1),
            "position clarity, not single-recommendation",
        )


# ---------------------------------------------------------------------------
# Schema-level constraint coverage
# ---------------------------------------------------------------------------


class TestSchemaConstraints(unittest.TestCase):
    """Direct model-construction tests — guard the public type surface."""

    def test_calibration_override_rejects_out_of_range(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            CalibrationOverride(dimension=0, text="x")
        with self.assertRaises(ValidationError):
            CalibrationOverride(dimension=10, text="x")

    def test_calibration_override_rejects_empty_text(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            CalibrationOverride(dimension=1, text="")

    def test_target_length_range_rejects_negative(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            TargetLengthRange(min_words=-1, max_words=100, source_key="words")

    def test_rubric_overrides_rejects_extra_fields(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            RubricOverrides(memo_subtype="x", undeclared_field=1)


class TestBodyFilenameFor(unittest.TestCase):
    """Tests for ``body_filename_for`` — the #295 slug-echo helper.

    Body filename echoes the thread slug under issue #295 (project-org
    model lock); there is no override mechanism. This test class pins
    the contract.
    """

    def test_simple_slug_echoes(self) -> None:
        self.assertEqual(body_filename_for("investment-memo"), "investment-memo.md")
        self.assertEqual(body_filename_for("latency-wall"), "latency-wall.md")
        self.assertEqual(body_filename_for("acme-seed"), "acme-seed.md")

    def test_slug_with_underscores_and_digits_echoes(self) -> None:
        self.assertEqual(body_filename_for("q3_thesis_update_2"), "q3_thesis_update_2.md")

    def test_empty_slug_raises(self) -> None:
        with self.assertRaises(ValueError):
            body_filename_for("")

    def test_non_string_slug_raises(self) -> None:
        with self.assertRaises(ValueError):
            body_filename_for(None)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            body_filename_for(42)  # type: ignore[arg-type]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
