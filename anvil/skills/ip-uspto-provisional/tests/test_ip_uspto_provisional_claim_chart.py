"""Tests for the advisory claim-chart critic (issue #1497).

Two suites in one module (mirroring the ``prior_art_search_wiring``
convention — the command files are prose procedures for an LLM-driven
agent, so their tests are structural/documentation checks, while the
figure-recompute step is real code and gets behavioral unit tests):

- ``TestCommandFile`` / ``TestSkillMd``: structural checks on
  ``commands/ip-uspto-provisional-claim-chart.md`` and its SKILL.md
  wiring — the advisory contract (owns no rubric dimension, sets no
  critical flag, never edits the draft, Limits section present), the
  three-valued cells, the re-read rule, the freeze contract, and the
  five derived lists.
- ``TestDiscoveryInvisibility``: the load-bearing structural guarantee
  — a ``<thread>.{N}.claimchart/`` sibling built to the command's file
  manifest is NOT picked up by ``anvil/lib/critics.py::discover_critics``
  (the sibling deliberately writes neither ``_review.json`` nor the
  ip-uspto legacy triple, so the reviser never aggregates it).
- ``TestFigureRecompute`` / ``TestFigureRecomputeCli``: behavioral unit
  tests for ``anvil/skills/ip-uspto-provisional/lib/figure_recompute.py``
  — reproduces, rounded-input miss, unstated-condition miss,
  figure-differs, no-source, expression safety, malformed ledgers.

The module filename is deliberately distinct
(``test_ip_uspto_provisional_claim_chart``) per the issue #58
cross-skill collection convention; this tests dir carries no
``__init__.py`` (``ip-uspto-provisional`` is not a valid Python
package name).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILL_ROOT = _HERE.parent
_REPO_ROOT = _HERE.parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from anvil.lib.testing import parse_frontmatter as _parse_frontmatter  # noqa: E402
from anvil.lib.testing import read_text

_read = lambda rel: read_text(_SKILL_ROOT / rel)

COMMAND_REL = "commands/ip-uspto-provisional-claim-chart.md"

# The sibling's complete file manifest, exactly as the command's Outputs
# block documents it (the discovery-invisibility contract).
CLAIMCHART_FILES = [
    "cover-note.md",
    "counsel-note.md",
    "chart.md",
    "_meta.json",
    "_progress.json",
]


class TestCommandFile(unittest.TestCase):
    """Structural checks on the advisory claim-chart command file."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(COMMAND_REL)

    def test_file_exists_with_frontmatter(self):
        fm = _parse_frontmatter(self.text)
        self.assertEqual(fm.get("name"), "ip-uspto-provisional-claim-chart")
        self.assertTrue(fm.get("description"))

    def test_advisory_contract_stated(self):
        # Owns NO rubric dimension, sets NO critical flag — the two
        # halves of the advisory posture, stated in the description AND
        # the body.
        lower = self.text.lower()
        self.assertIn("no rubric dimension", lower)
        self.assertIn("no critical flag", lower)
        self.assertIn("advisory", lower)

    def test_never_edits_the_draft(self):
        lower = self.text.lower()
        self.assertIn("never edits the draft", lower)
        # Nor proposes claim language / adds claim seeds.
        self.assertIn("never proposes claim language", lower)
        self.assertIn("never adds claim seeds", lower)

    def test_limits_section_present(self):
        self.assertIn("## Limits", self.text)
        # The three named blind spots.
        lower = self.text.lower()
        self.assertIn("operability", lower)
        self.assertIn("physical-model", lower)
        self.assertIn("prior-art", lower)
        # And the arrangement-list completeness ceiling.
        self.assertIn("completeness of the arrangement list", lower)

    def test_arrangement_tags_from_the_texts_own_words(self):
        for tag in ("built", "measured", "simulated", "computed", "proposed"):
            self.assertIn(tag, self.text.lower())
        self.assertIn("claims-blind", self.text.lower())

    def test_three_valued_cells_and_not_stated_discipline(self):
        for cell in ("`met`", "`not met`", "`not stated`"):
            self.assertIn(cell, self.text)
        # Silence is never counted as not met.
        self.assertIn("never counted as `not met`", self.text)

    def test_reread_before_refuting_rule(self):
        lower = self.text.lower()
        self.assertIn("re-read", lower)
        self.assertIn("never record `not met` from memory", lower)

    def test_derived_lists_all_five(self):
        for needle in (
            "reading on no arrangement",
            "read by no independent",
            "parent chain",
            "absent from the description",
            "exclude every described case",
        ):
            self.assertIn(needle, self.text)

    def test_figure_recompute_delegation_and_classification(self):
        # Delegates to the skill-local script and classifies every miss
        # against its source before reporting.
        lower = self.text.lower()
        self.assertIn("figure_recompute", lower)
        self.assertIn("text-omits-condition", lower)
        self.assertIn("figure-differs-from-source", lower)
        self.assertIn("no-source", lower)
        self.assertIn("import_skill_lib_module", self.text)

    def test_freeze_before_comparison(self):
        self.assertIn("findings_sha256", self.text)
        self.assertIn("findings_frozen_at", self.text)
        # The comparison step happens only AFTER the freeze lands, and
        # never edits the frozen files.
        lower = self.text.lower()
        self.assertIn("only after the freeze lands", lower)
        self.assertIn("frozen files are never edited", lower)

    def test_output_surface_one_page_two_notes(self):
        self.assertIn("counsel-note.md", self.text)
        self.assertIn("cover-note.md", self.text)
        self.assertIn("one-page", self.text.lower())
        # Output goes to the counsel note and cover note ONLY.
        self.assertIn("nothing else", self.text.lower())

    def test_claims_optional_graceful_exit(self):
        lower = self.text.lower()
        self.assertIn("nothing to chart", lower)
        self.assertIn("claims-optional", lower)
        self.assertIn("absence is never a finding", lower)

    def test_atomicity_via_staged_sidecar(self):
        self.assertIn("staged_sidecar", self.text)
        self.assertIn("cleanup_one_staging", self.text)
        self.assertIn("claimchart", self.text)

    def test_discovery_invisibility_documented(self):
        # The command states the filename contract that keeps it out of
        # discover_critics (no _review.json, no legacy triple).
        lower = self.text.lower()
        self.assertIn("discover_critics", lower)
        self.assertIn("no `_review.json`", self.text)
        self.assertIn("no `_summary.md`", self.text)


class TestSkillMd(unittest.TestCase):
    """The command is wired into SKILL.md's dispatch table and layout."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read("SKILL.md")

    def test_command_table_row(self):
        self.assertIn("`ip-uspto-provisional-claim-chart <thread>`", self.text)
        self.assertIn("advisory, non-gating", self.text)

    def test_layout_line(self):
        self.assertIn("<thread>.1.claimchart/", self.text)

    def test_never_in_configured_critic_set(self):
        self.assertIn("never in the configured critic set", self.text)
        self.assertIn("`claimchart`", self.text)

    def test_default_critic_set_unchanged(self):
        # The default set stays review + s112 + priorart.
        self.assertIn("review + s112 + priorart", self.text)


class TestDiscoveryInvisibility(unittest.TestCase):
    """A claimchart sibling is invisible to critic discovery by filename."""

    def _build(self, root: Path, tag: str, files):
        version = root / "acme-widget-prov.1"
        version.mkdir(parents=True, exist_ok=True)
        sibling = root / f"acme-widget-prov.1.{tag}"
        sibling.mkdir()
        for name in files:
            (sibling / name).write_text("placeholder", encoding="utf-8")
        return version, sibling

    def test_claimchart_sibling_not_discovered(self):
        from anvil.lib.critics import discover_critics

        with tempfile.TemporaryDirectory() as tmp:
            version, claimchart = self._build(
                Path(tmp), "claimchart", CLAIMCHART_FILES
            )
            discovered = discover_critics(version)
            self.assertNotIn(claimchart, discovered)
            self.assertEqual(discovered, [])

    def test_critic_shapes_still_discovered(self):
        # Contrast guard: the shapes discover_critics matches on
        # (_review.json, ip-uspto legacy triple) ARE discovered — the
        # invisibility above comes from the filenames, not from a broken
        # discovery under test.
        from anvil.lib.critics import discover_critics

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version, review = self._build(
                root, "review", ["_summary.md", "findings.md", "_meta.json"]
            )
            _, canonical = self._build(root, "s112", ["_review.json"])
            discovered = discover_critics(version)
            self.assertIn(review, discovered)
            self.assertIn(canonical, discovered)


class TestFigureRecompute(unittest.TestCase):
    """Behavioral unit tests for lib/figure_recompute.py."""

    @classmethod
    def setUpClass(cls):
        from anvil.lib.skill_lib_loader import import_skill_lib_module

        cls.fr = import_skill_lib_module(
            "ip-uspto-provisional",
            _SKILL_ROOT / "lib",
            "figure_recompute",
        )

    def _classify(self, entry):
        return self.fr.classify_entry(entry)

    def test_figure_reproduces_exact(self):
        result = self._classify(
            {
                "id": "eff",
                "printed_value": 50.0,
                "expression": "a / b * 100",
                "inputs": {"a": 5.0, "b": 10.0},
            }
        )
        self.assertEqual(result["status"], "reproduced")
        self.assertEqual(result["computed_value"], 50.0)

    def test_figure_reproduces_within_tolerance(self):
        result = self._classify(
            {
                "id": "eff",
                "printed_value": 38.2,
                "expression": "a / b * 100",
                "inputs": {"a": 41.6, "b": 109.0},
                "tolerance": 0.05,
            }
        )
        self.assertEqual(result["status"], "reproduced")

    def test_rounded_input_miss_is_text_omits_condition(self):
        # The trial's benign case: the printed figure is faithful to its
        # cited source, but the printed inputs lack the precision to
        # reproduce it — a text-precision gap, not a figure error.
        result = self._classify(
            {
                "id": "eff",
                "printed_value": 38.2,
                "expression": "a / b * 100",
                "inputs": {"a": 41.6, "b": 109.0},
                "tolerance": 0.01,
                "source": {
                    "kind": "lab-sheet",
                    "location": "refs/nb3 p.12",
                    "value": 38.2,
                },
            }
        )
        self.assertEqual(result["status"], "miss")
        self.assertEqual(result["class"], "text-omits-condition")
        self.assertIn("rounded input", result["note"])

    def test_unstated_condition_miss(self):
        result = self._classify(
            {
                "id": "yield",
                "printed_value": 41.0,
                "unstated_inputs": ["ambient temperature"],
            }
        )
        self.assertEqual(result["status"], "miss")
        self.assertEqual(result["class"], "text-omits-condition")
        self.assertIn("ambient temperature", result["note"])

    def test_expression_name_not_stated_is_text_omits_condition(self):
        # The expression references an input the text never states.
        result = self._classify(
            {
                "id": "x",
                "printed_value": 3.0,
                "expression": "x + 1",
                "inputs": {"y": 2},
            }
        )
        self.assertEqual(result["status"], "miss")
        self.assertEqual(result["class"], "text-omits-condition")

    def test_recompute_mismatch_is_figure_differs(self):
        result = self._classify(
            {
                "id": "eff",
                "printed_value": 38.2,
                "expression": "a / b * 100",
                "inputs": {"a": 41.6, "b": 109.0},
                "tolerance": 0.001,
            }
        )
        self.assertEqual(result["status"], "miss")
        self.assertEqual(result["class"], "figure-differs-from-source")

    def test_source_only_paths(self):
        reproduced = self._classify(
            {
                "id": "t",
                "printed_value": 12.5,
                "source": {"kind": "table", "value": 12.5},
            }
        )
        self.assertEqual(reproduced["status"], "reproduced")
        differs = self._classify(
            {
                "id": "t",
                "printed_value": 12.5,
                "source": {"kind": "table", "value": 12.9},
            }
        )
        self.assertEqual(differs["status"], "miss")
        self.assertEqual(differs["class"], "figure-differs-from-source")

    def test_no_source(self):
        result = self._classify({"id": "orphan", "printed_value": 99.9})
        self.assertEqual(result["status"], "miss")
        self.assertEqual(result["class"], "no-source")

    def test_expression_sandbox_rejects_calls_and_attributes(self):
        for hostile in (
            "__import__('os').system('true')",
            "open.__self__",
            "a.__class__",
            "[1, 2][0]",
            "a < b",
        ):
            with self.subTest(expression=hostile):
                with self.assertRaises(self.fr.ExpressionError):
                    self.fr.evaluate_expression(hostile, {"a": 1, "b": 2})
                # And via classify_entry: a rejected expression is a
                # classified miss, never an execution.
                result = self._classify(
                    {
                        "id": "h",
                        "printed_value": 1.0,
                        "expression": hostile,
                        "inputs": {"a": 1, "b": 2},
                    }
                )
                self.assertEqual(result["status"], "miss")
                self.assertEqual(result["class"], "text-omits-condition")

    def test_relative_tolerance(self):
        result = self._classify(
            {
                "id": "big",
                "printed_value": 1_000_000.0,
                "expression": "a * 10",
                "inputs": {"a": 100_000.0},
                "relative_tolerance": 1e-9,
            }
        )
        self.assertEqual(result["status"], "reproduced")

    def test_malformed_entries_raise_ledger_error(self):
        for bad in (
            {"printed_value": 1.0},  # no id
            {"id": "x"},  # no printed_value
            {"id": "x", "printed_value": "38"},  # non-numeric
            {"id": "x", "printed_value": 1.0, "inputs": [1, 2]},  # not an object
            {"id": "x", "printed_value": 1.0, "unstated_inputs": "temp"},  # not a list
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(self.fr.LedgerError):
                    self.fr.classify_entry(bad)

    def test_ledger_summary_counts(self):
        ledger = {
            "figures": [
                {"id": "ok", "printed_value": 2.0, "expression": "1 + 1"},
                {"id": "gap", "printed_value": 1.0, "unstated_inputs": ["T"]},
                {"id": "orphan", "printed_value": 1.0},
            ]
        }
        report = self.fr.recompute_ledger(ledger)
        self.assertEqual(report["summary"]["total"], 3)
        self.assertEqual(report["summary"]["reproduced"], 1)
        self.assertEqual(report["summary"]["miss"], 2)
        self.assertEqual(report["summary"]["text-omits-condition"], 1)
        self.assertEqual(report["summary"]["no-source"], 1)

    def test_ledger_requires_figures_list(self):
        with self.assertRaises(self.fr.LedgerError):
            self.fr.recompute_ledger({"nope": True})


class TestFigureRecomputeCli(unittest.TestCase):
    """The CLI form documented in the command file works bare (stdlib-only)."""

    @classmethod
    def setUpClass(cls):
        cls.module_path = _SKILL_ROOT / "lib" / "figure_recompute.py"
        # Imported through the loader for main(); the module is also
        # directly runnable (stdlib-only), which the command file
        # documents as the Python-less session path.
        from anvil.lib.skill_lib_loader import import_skill_lib_module

        cls.fr = import_skill_lib_module(
            "ip-uspto-provisional", _SKILL_ROOT / "lib", "figure_recompute"
        )

    def test_main_report_and_zero_exit_on_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "figures": [
                            {"id": "g", "printed_value": 1.0, "unstated_inputs": ["T"]}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            rc = self.fr.main([str(ledger_path)])
            self.assertEqual(rc, 0)  # a miss is a finding, not an error

    def test_main_json_output(self):
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "figures": [
                            {"id": "ok", "printed_value": 4.0, "expression": "2 * 2"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.fr.main([str(ledger_path), "--json"])
            self.assertEqual(rc, 0)
            report = json.loads(buf.getvalue())
            self.assertEqual(report["summary"]["reproduced"], 1)

    def test_main_invocation_error_is_two(self):
        self.assertEqual(self.fr.main([]), 2)
        self.assertEqual(self.fr.main(["/nonexistent/ledger.json"]), 2)

    def test_module_runs_bare_as_a_script(self):
        # The command file documents `python … figure_recompute.py
        # <ledger.json>` as the CLI path; prove the module has no
        # third-party imports by executing it standalone in a clean
        # interpreter (no anvil on sys.path).
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "figures": [
                            {"id": "ok", "printed_value": 4.0, "expression": "2 * 2"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(self.module_path), str(ledger_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("reproduced", proc.stdout)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
