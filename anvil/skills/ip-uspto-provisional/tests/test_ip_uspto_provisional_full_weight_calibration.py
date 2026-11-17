"""Doc-contract tests for the #1501 full-weight calibration rule.

Two reviewer runs on two closely related copies of one specification
differed by two points on dimensions 4 and 8 with the same cited minor
findings — one reviewer granted full weight with the minors open, the
other deducted a point per finding. Issue #1501 pins the calibration in
``rubric.md`` (full weight requires zero open findings on that dimension;
any open minor caps it at ``weight - 1``) with a worked example for the
low-weight dim 8, and makes all three critic-writing commands instruct
each scored ``_summary.md`` dimension to carry an ``open_findings`` object
counting that dimension's open findings by severity beside the score, so
two runs can be compared without reading both findings files.

Calibration clarification only: the ``anvil-ip-provisional-v1`` id, the
45-point total, and the >=39 advance threshold are unchanged.

Filename is deliberately distinct per the issue #58 cross-skill
collection convention (no ``__init__.py`` in this tests dir).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SKILL_ROOT.parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from anvil.lib.evidence_check import (  # noqa: E402
    SEVERITY_MAJOR,
    check_summary_text,
    parse_machine_summary_dimensions,
)
from anvil.lib.testing import read_text  # noqa: E402

_read = lambda rel: read_text(_SKILL_ROOT / rel)

_COMMANDS = (
    "commands/ip-uspto-provisional-review.md",
    "commands/ip-uspto-provisional-112.md",
    "commands/ip-uspto-provisional-prior-art.md",
)


class TestRubricStatesTheRule(unittest.TestCase):
    """rubric.md §"Scoring guidance" pins the rule + worked example."""

    def test_rule_paragraph_present(self):
        self.assertIn("Full weight and open findings", _read("rubric.md"))

    def test_rule_is_zero_open_findings_of_any_severity(self):
        # Full weight on a dimension means no open finding of any
        # severity on it in the same review's findings.md.
        self.assertIn(
            "no open finding of any severity", _read("rubric.md")
        )

    def test_open_minor_caps_at_weight_minus_one(self):
        self.assertIn("weight − 1", _read("rubric.md"))

    def test_dim8_worked_example_scores_two_not_three(self):
        # The worked example is the issue's dim-8 terminology case:
        # weight 3 with one open minor ("the controller" ¶[0012] vs
        # "the processing unit" ¶[0031]) scores 2, not 3.
        text = _read("rubric.md")
        self.assertIn('"the controller"', text)
        self.assertIn("¶[0012]", text)
        self.assertIn("2, not 3", text)

    def test_zero_findings_still_reaches_full_weight(self):
        # Edge case from the issue's test plan: a dimension with zero
        # findings still reaches full weight.
        self.assertIn("zero open findings", _read("rubric.md"))

    def test_no_weight_threshold_or_id_change(self):
        text = _read("rubric.md")
        self.assertIn("anvil-ip-provisional-v1", text)
        self.assertIn("**45**", text)
        self.assertIn("**≥39/45**", text)


class TestCommandsRecordOpenFindings(unittest.TestCase):
    """All three critic-writing commands instruct recording open_findings."""

    def test_each_command_mentions_open_findings(self):
        for rel in _COMMANDS:
            with self.subTest(path=rel):
                self.assertIn("`open_findings`", _read(rel))

    def test_each_command_references_the_rubric_rule(self):
        for rel in _COMMANDS:
            with self.subTest(path=rel):
                text = _read(rel)
                self.assertIn("rubric.md", text)
                self.assertIn("Full weight and open findings", text)

    def test_null_dims_carry_no_open_findings(self):
        # Edge case from the issue's test plan: null (un-owned)
        # dimensions carry no open_findings.
        for rel in _COMMANDS:
            with self.subTest(path=rel):
                text = _read(rel).lower()
                self.assertIn("null", text)
                self.assertIn("carry none", text)


class TestEvidenceCheckToleratesOpenFindings(unittest.TestCase):
    """evidence_check parses a dimensions block carrying open_findings.

    The parser reads ``score``/``weight``/``justification`` only; the
    extra key must be ignored — never a crash, never a
    misclassification (acceptance criterion: evidence_check on a
    ``_summary.md`` carrying ``open_findings`` still passes).
    """

    def test_parser_ignores_open_findings_and_classifies_pass(self):
        summary = (
            "## s112\n\n"
            "```json\n"
            "{\n"
            '  "critic": "s112",\n'
            '  "dimensions": {\n'
            '    "1": {"score": 7, "weight": 8,\n'
            '           "open_findings": {"critical": 0, "major": 0, '
            '"minor": 1},\n'
            '           "justification": "“the adaptive bias loop settles '
            'within two reference clocks” — § Detailed Description '
            '¶[0023]"},\n'
            '    "2": null\n'
            "  }\n"
            "}\n"
            "```\n"
        )
        rows = parse_machine_summary_dimensions(summary)
        self.assertEqual(len(rows), 2)
        d1 = next(r for r in rows if r.dimension == "1")
        self.assertEqual(d1.score, 7)
        self.assertEqual(d1.weight, 8)
        d2 = next(r for r in rows if r.dimension == "2")
        self.assertIsNone(d2.score)

        body = (
            "# Spec\n\nthe adaptive bias loop settles within two reference "
            "clocks, then hands off.\n"
        )
        findings, checked = check_summary_text(summary, body)
        self.assertEqual(checked, 1)
        self.assertEqual(
            [f.severity for f in findings], [], f"unexpected findings: {findings}"
        )
        self.assertNotIn(SEVERITY_MAJOR, [f.severity for f in findings])

    def test_full_weight_with_zero_open_findings_by_absence_passes(self):
        summary = (
            "```json\n"
            "{\n"
            '  "dimensions": {\n'
            '    "8": {"score": 3, "weight": 3,\n'
            '           "open_findings": {"critical": 0, "major": 0, '
            '"minor": 0},\n'
            '           "justification": "no instance of a duplicated '
            'component name found"}\n'
            "  }\n"
            "}\n"
            "```\n"
        )
        rows = parse_machine_summary_dimensions(summary)
        self.assertEqual(rows[0].score, 3)
        self.assertEqual(rows[0].weight, 3)
        findings, checked = check_summary_text(summary, "# body\nnothing\n")
        self.assertEqual(checked, 1)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
