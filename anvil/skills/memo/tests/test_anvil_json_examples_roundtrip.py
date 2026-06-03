"""Tests that the worked-example ``.anvil.json`` templates round-trip through the typed loader.

Covers issue #266 (sub-issue 3 of #233): documentation + worked-example
templates for the ``rubric_overrides`` mechanism. The two templates shipped
under ``anvil/skills/memo/templates/`` MUST parse cleanly through both the
lenient ``load_rubric_overrides`` and the strict ``load_rubric_overrides_strict``
forms — they are operator-facing copy-and-edit references; a template that
emits warnings or fails strict validation would mislead consumers about the
expected on-disk shape.

The acceptance criterion for this PR is:

  > Templates must round-trip through the typed loader (parse + validation passes).

This test file is the executable form of that AC. It also acts as a
regression anchor: any future change to the loader schema must keep these
templates valid (or update the templates in lockstep).

Filename discipline: per CLAUDE.md §"Test discipline" / issue #58, per-skill
tests use distinct filenames to avoid the pytest filename-collision case.
``test_anvil_config.py`` (sub-issue 1) and
``test_rubric_overrides_suffix_wiring.py`` (sub-issue 2) already exist; this
file adds the worked-example round-trip layer with a fresh name.

Runs under either ``python -m unittest discover anvil/skills/memo/tests/``
or ``pytest anvil/skills/memo/tests/``.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


# Match the sys.path injection pattern from the other memo-skill test files.
# The lib lives under ``anvil/skills/memo/lib/`` per the CLAUDE.md
# "skill-local first, lib promotion later" pattern.
_HERE = Path(__file__).resolve().parent
_LIB = _HERE.parent / "lib"
_TEMPLATES = _HERE.parent / "templates"
sys.path.insert(0, str(_LIB))

from anvil_config import (  # noqa: E402
    CalibrationOverride,
    MAX_DIM,
    MIN_DIM,
    RubricOverrides,
    TargetLengthRange,
    load_rubric_overrides,
    load_rubric_overrides_strict,
)


# The two worked-example templates this test file validates. The names match
# the issue body and the SKILL.md §"Rubric overrides and non-investment-memo
# shapes" worked-example references.
_SYNTHESIS_BRIEF_EXAMPLE = _TEMPLATES / ".anvil.json.synthesis-brief.example"
_FEEDBACK_MEMO_EXAMPLE = _TEMPLATES / ".anvil.json.feedback-memo.example"


def _stage_template_as_anvil_json(template: Path, thread_dir: Path) -> Path:
    """Copy ``template`` to ``<thread_dir>/.anvil.json`` and return the path.

    The templates ship under ``templates/`` with the ``.example`` suffix per
    the same convention as ``BRIEF.fresh.md.example`` /
    ``BRIEF.migration.md.example`` (see SKILL.md §"Defaults and overrides").
    An operator uses them by copying to ``<thread>/.anvil.json`` and editing
    in place; the round-trip test mimics that copy step exactly.
    """
    thread_dir.mkdir(parents=True, exist_ok=True)
    dest = thread_dir / ".anvil.json"
    shutil.copy(str(template), str(dest))
    return dest


class _TmpThreadBase(unittest.TestCase):
    """Mixin: per-test temp dir for the memo thread root."""

    def setUp(self) -> None:
        self._td = TemporaryDirectory()
        self.thread_dir = Path(self._td.name) / "demo-thread"
        self.thread_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._td.cleanup)


# ---------------------------------------------------------------------------
# Template files exist at the documented paths
# ---------------------------------------------------------------------------


class TestTemplatesExist(unittest.TestCase):
    """The two worked-example templates ship at the documented paths.

    A consumer reading SKILL.md §"Rubric overrides and non-investment-memo
    shapes" expects to find both files under ``anvil/skills/memo/templates/``.
    A regression where the file disappears (e.g., renamed during a refactor)
    would silently break the consumer's copy-and-edit flow.
    """

    def test_synthesis_brief_example_exists(self) -> None:
        self.assertTrue(
            _SYNTHESIS_BRIEF_EXAMPLE.is_file(),
            f"missing template: {_SYNTHESIS_BRIEF_EXAMPLE}",
        )

    def test_feedback_memo_example_exists(self) -> None:
        self.assertTrue(
            _FEEDBACK_MEMO_EXAMPLE.is_file(),
            f"missing template: {_FEEDBACK_MEMO_EXAMPLE}",
        )

    def test_templates_are_valid_json(self) -> None:
        """The ``.example`` suffix does not make the file non-JSON.

        Both templates MUST parse as JSON — they are shown verbatim in the
        SKILL.md worked-example sections and are copied as-is to
        ``<thread>/.anvil.json``. A trailing-comma typo or a single-quoted
        string would silently break the consumer's first revise pass.
        """
        for template in (_SYNTHESIS_BRIEF_EXAMPLE, _FEEDBACK_MEMO_EXAMPLE):
            with self.subTest(template=template.name):
                with template.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self.assertIsInstance(data, dict)


# ---------------------------------------------------------------------------
# Lenient loader round-trip (production contract)
# ---------------------------------------------------------------------------


class TestSynthesisBriefRoundtripLenient(_TmpThreadBase):
    """``.anvil.json.synthesis-brief.example`` round-trips through ``load_rubric_overrides``.

    The lenient form is the production contract — every lifecycle command
    uses it. Round-trip here means: copy the template to ``<thread>/.anvil.json``,
    invoke the loader, and assert that the parsed model carries the documented
    fields (memo_subtype, all declared calibrations, target_length).
    """

    def setUp(self) -> None:
        super().setUp()
        _stage_template_as_anvil_json(_SYNTHESIS_BRIEF_EXAMPLE, self.thread_dir)

    def test_loads_without_warnings(self) -> None:
        """No ``UserWarning`` should fire — every key is a recognized field.

        The lenient loader emits ``UserWarning`` for any per-field validation
        failure (unknown key, malformed value, out-of-range dim). A worked
        example that triggers any such warning would be a footgun: operators
        would copy the template and immediately see warnings on first revise.
        """
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(
            [str(w.message) for w in caught],
            [],
            "synthesis-brief template emitted unexpected warnings",
        )
        # Loader returned a parsed model, not the empty fast-path.
        self.assertFalse(result.is_empty)

    def test_memo_subtype_matches_documented_label(self) -> None:
        result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(result.memo_subtype, "synthesis-brief")

    def test_calibrations_cover_documented_dims(self) -> None:
        """The synthesis-brief template calibrates dims 1, 5, 6, 7.

        Per SKILL.md §"Worked example: synthesis-brief", the canary's
        load-bearing recalibrations are dims 1 (recommendation clarity),
        5 (market framing), 6 (financial reasoning), and 7 (scope
        discipline). A regression where one of these drops out would
        misalign the template with the documented worked example.
        """
        result = load_rubric_overrides(self.thread_dir)
        dims = sorted(c.dimension for c in result.calibrations)
        self.assertEqual(dims, [1, 5, 6, 7])

    def test_calibration_text_is_non_empty(self) -> None:
        """Every calibration entry carries non-empty prose.

        The reviewer's suffix mechanism (per ``commands/memo-review.md`` step 5
        §"Rubric overrides — calibration suffixes") appends the verbatim text
        as a justification suffix. An empty-string calibration would produce
        a malformed ``"calibration applied: "`` suffix.
        """
        result = load_rubric_overrides(self.thread_dir)
        for entry in result.calibrations:
            with self.subTest(dim=entry.dimension):
                self.assertTrue(entry.text.strip())

    def test_target_length_resolves_to_documented_range(self) -> None:
        """The synthesis-brief target_length is ``[9000, 13000]`` words.

        This is the canary's declared range (per issue #233 body). Drift
        here would misalign the template with the documented worked example.
        """
        result = load_rubric_overrides(self.thread_dir)
        self.assertIsNotNone(result.target_length)
        assert result.target_length is not None  # for type-checkers
        self.assertEqual(result.target_length.min_words, 9000)
        self.assertEqual(result.target_length.max_words, 13000)
        self.assertEqual(result.target_length.source_key, "words")

    def test_no_unknown_keys(self) -> None:
        """The synthesis-brief template declares only recognized keys.

        Unknown keys land in ``unknown_keys`` and emit a warning — the
        template MUST be clean on this surface so a consumer who copies it
        does not inherit a stale-key warning by default.
        """
        result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(result.unknown_keys, {})


class TestFeedbackMemoRoundtripLenient(_TmpThreadBase):
    """``.anvil.json.feedback-memo.example`` round-trips through ``load_rubric_overrides``.

    Same round-trip shape as the synthesis-brief test class. The feedback-memo
    template calibrates a different dim set (1, 4, 5, 6, 7) reflecting the
    canary's positional-recommendation shape (no "the company", no ask, no
    founder section — the recommendation target is positional, not financial).
    """

    def setUp(self) -> None:
        super().setUp()
        _stage_template_as_anvil_json(_FEEDBACK_MEMO_EXAMPLE, self.thread_dir)

    def test_loads_without_warnings(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(
            [str(w.message) for w in caught],
            [],
            "feedback-memo template emitted unexpected warnings",
        )
        self.assertFalse(result.is_empty)

    def test_memo_subtype_matches_documented_label(self) -> None:
        result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(result.memo_subtype, "feedback-memo")

    def test_calibrations_cover_documented_dims(self) -> None:
        """The feedback-memo template calibrates dims 1, 4, 5, 6, 7.

        Per SKILL.md §"Worked example: feedback-memo", the canary recalibrates
        dim 1 (position clarity vs single ranked recommendation), dim 4 (risk
        honesty: positional vs operational risk), and dims 5/6/7 (secondary
        market/financial framing + forceful-brevity length anchor).
        """
        result = load_rubric_overrides(self.thread_dir)
        dims = sorted(c.dimension for c in result.calibrations)
        self.assertEqual(dims, [1, 4, 5, 6, 7])

    def test_calibration_text_is_non_empty(self) -> None:
        result = load_rubric_overrides(self.thread_dir)
        for entry in result.calibrations:
            with self.subTest(dim=entry.dimension):
                self.assertTrue(entry.text.strip())

    def test_target_length_resolves_to_documented_range(self) -> None:
        """The feedback-memo target_length is ``[4000, 6000]`` words.

        Calibrated from the raytheon-pitch-strategy canary (~5K words). The
        range brackets that midpoint with room for both compression and
        expansion within the forceful-brevity discipline.
        """
        result = load_rubric_overrides(self.thread_dir)
        self.assertIsNotNone(result.target_length)
        assert result.target_length is not None
        self.assertEqual(result.target_length.min_words, 4000)
        self.assertEqual(result.target_length.max_words, 6000)
        self.assertEqual(result.target_length.source_key, "words")

    def test_no_unknown_keys(self) -> None:
        result = load_rubric_overrides(self.thread_dir)
        self.assertEqual(result.unknown_keys, {})


# ---------------------------------------------------------------------------
# Strict loader round-trip (test-suite contract)
# ---------------------------------------------------------------------------


class TestStrictRoundtrip(_TmpThreadBase):
    """Both templates pass the strict loader without raising.

    The strict form raises ``ValueError`` when ANY per-field validation
    warning would have fired under the lenient form. A worked-example
    template that round-trips lenient but fails strict would still be
    valid in production but would mislead future test authors who want to
    use the templates as fixtures for strict-form testing.
    """

    def test_synthesis_brief_strict_roundtrip(self) -> None:
        _stage_template_as_anvil_json(_SYNTHESIS_BRIEF_EXAMPLE, self.thread_dir)
        try:
            result = load_rubric_overrides_strict(self.thread_dir)
        except ValueError as exc:
            self.fail(
                f"synthesis-brief template failed strict validation: {exc}"
            )
        self.assertEqual(result.memo_subtype, "synthesis-brief")

    def test_feedback_memo_strict_roundtrip(self) -> None:
        _stage_template_as_anvil_json(_FEEDBACK_MEMO_EXAMPLE, self.thread_dir)
        try:
            result = load_rubric_overrides_strict(self.thread_dir)
        except ValueError as exc:
            self.fail(
                f"feedback-memo template failed strict validation: {exc}"
            )
        self.assertEqual(result.memo_subtype, "feedback-memo")


# ---------------------------------------------------------------------------
# Cross-template consistency
# ---------------------------------------------------------------------------


class TestTemplateConsistency(_TmpThreadBase):
    """Cross-template invariants the SKILL.md documentation depends on.

    These tests assert structural invariants that are documented in
    SKILL.md §"Rubric overrides and non-investment-memo shapes":

    - Every calibration's dim is within the documented memo-rubric range
      (``[MIN_DIM, MAX_DIM]`` = 1-9).
    - The templates declare ``target_length`` consistent with their
      documented worked-example shape (both also at the top level for the
      drafter / reviser, and inside ``rubric_overrides`` for the audit
      trail — see SKILL.md §"Rubric overrides ... target_length").
    """

    def test_all_calibrations_within_dim_range(self) -> None:
        for label, template in (
            ("synthesis-brief", _SYNTHESIS_BRIEF_EXAMPLE),
            ("feedback-memo", _FEEDBACK_MEMO_EXAMPLE),
        ):
            with self.subTest(template=label):
                _stage_template_as_anvil_json(template, self.thread_dir)
                result = load_rubric_overrides(self.thread_dir)
                for entry in result.calibrations:
                    self.assertGreaterEqual(entry.dimension, MIN_DIM)
                    self.assertLessEqual(entry.dimension, MAX_DIM)
                # Reset for next subtest's stage step.
                (self.thread_dir / ".anvil.json").unlink()

    def test_top_level_and_overrides_target_length_agree(self) -> None:
        """Both templates declare matching ``target_length`` at both levels.

        The templates declare ``target_length`` BOTH at the top level (where
        the drafter / reviser read it per SKILL.md §"Length targets") AND
        inside ``rubric_overrides.target_length`` (where the reviewer's
        ``_summary.md.rubric_overrides.target_length_present`` field surfaces
        it for audit-trail visibility). The two values MUST agree — a
        template that disagreed on the two surfaces would confuse the
        drafter's resolution helper and the reviewer's audit-trail block.
        """
        for label, template in (
            ("synthesis-brief", _SYNTHESIS_BRIEF_EXAMPLE),
            ("feedback-memo", _FEEDBACK_MEMO_EXAMPLE),
        ):
            with self.subTest(template=label):
                with template.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                top = data.get("target_length")
                inner = data.get("rubric_overrides", {}).get("target_length")
                self.assertEqual(
                    top,
                    inner,
                    f"{label}: top-level target_length and "
                    "rubric_overrides.target_length disagree",
                )


if __name__ == "__main__":
    unittest.main()
