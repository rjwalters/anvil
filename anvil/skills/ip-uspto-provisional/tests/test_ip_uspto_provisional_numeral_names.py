"""Tests for the one-name-per-reference-numeral check (issue #1500).

``anvil/skills/ip-uspto-provisional/lib/numeral_names.py`` is the
deterministic sibling behind two wiring points introduced by issue #1500:

- pre-flight **Check 5b** (``ip-uspto-provisional-pre-flight.md``) —
  ``minor`` advisory, never gates pass/fail (the noun-phrase extraction is
  heuristic); and
- audit **Check 3**'s mechanical first pass
  (``ip-uspto-provisional-audit.md``) — reported numerals are candidates
  the auditor confirms; a confirmed rename mismatch keeps Check 3's
  existing ``blocker`` severity.

The behavioral coverage here maps onto the issue's acceptance criteria:
the split-across-source-lines rename from the canary defect is caught with
paragraph numbers and both differing names; the vendored
``acme-widget-prov.1`` example yields no findings (exit 0 — the Champion
note on #1500 required validating the heuristic on it first); and the doc
wiring cannot silently drop (skeleton-test style assertions on both
command docs).

The module filename is deliberately distinct
(``test_ip_uspto_provisional_numeral_names``) per the issue #58
cross-skill collection convention; this tests dir carries no
``__init__.py`` (``ip-uspto-provisional`` is not a valid Python package
name), and the lib module is loaded by file path via ``importlib`` under
a unique module name (the ip-uspto ``lib/`` precedent — the hyphenated
skill dir is not importable).
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILL_ROOT = _HERE.parent
_REPO_ROOT = _HERE.parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from anvil.lib.testing import read_text

_LIB_FILE = _SKILL_ROOT / "lib" / "numeral_names.py"
_LIB_CLI = str(_LIB_FILE)
_MODULE_NAME = "ip_uspto_provisional_numeral_names_lib"
_EXAMPLE_DIR = _SKILL_ROOT / "examples" / "acme-widget-prov" / "acme-widget-prov.1"


def _load_lib():
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _LIB_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


nn = _load_lib()

_read = lambda rel: read_text(_SKILL_ROOT / rel)

_BRIEF_ANCHOR = (
    "\\anvilpara{FIG. 3 is a plan view of a MEMS die showing the placement of the\n"
    "dummy half-bridge adjacent to the sense bridge.}"
)
_STALE_RENAME = (
    "\\anvilpara{FIG. 3 is a plan view of a MEMS die showing the placement of the\n"
    "input\nport \\refnum{20} adjacent to the sense bridge.}"
)


def _scratch_version_dir() -> Path:
    """Copy the vendored example into a temp dir the test may mutate."""
    tmp = Path(tempfile.mkdtemp(prefix="numeral-names-test-")) / "scratch.1"
    shutil.copytree(_EXAMPLE_DIR, tmp)
    return tmp


class TestNamesConsistent(unittest.TestCase):
    """The heuristic consistency relation: what must and must not block."""

    def test_identical_names_consistent(self):
        self.assertTrue(nn.names_consistent(["sense", "bridge"], ["sense", "bridge"]))

    def test_short_form_is_suffix_so_consistent(self):
        # Curator's must-not-block case: "bridge 10" vs "sense bridge 10".
        self.assertTrue(nn.names_consistent(["bridge"], ["sense", "bridge"]))

    def test_differing_modifier_on_shared_head_is_consistent(self):
        # Vendored example real case: [0003] "single trim-once span resistor"
        # vs everywhere-else "span trim resistor".
        self.assertTrue(
            nn.names_consistent(
                ["span", "trim", "resistor"], ["trim-once", "span", "resistor"]
            )
        )

    def test_plural_head_is_consistent(self):
        # Drawing-stub real case: "sources (42)" vs "constant-current source".
        self.assertTrue(nn.names_consistent(["sources"], ["constant-current", "source"]))

    def test_genuine_rename_is_inconsistent(self):
        # The canary defect shape: renamed element, stale name in one place.
        self.assertFalse(nn.names_consistent(["sense", "bridge"], ["input", "port"]))

    def test_different_heads_same_length_inconsistent(self):
        self.assertFalse(nn.names_consistent(["bridge"], ["port"]))


class TestExtraction(unittest.TestCase):
    """Unit-level extraction: comment continuation, wrapping, boundaries."""

    def test_comment_stripping_joins_wrapped_name(self):
        # LaTeX continuation idiom: a trailing % elides the newline.
        text = "\\anvilpara{A single ratio resistor %\n\\refnum{12} sets the gain.}"
        occ = list(nn.iter_spec_occurrences(text))
        self.assertEqual(len(occ), 1)
        numeral, name, paragraph, section = occ[0]
        self.assertEqual(numeral, "12")
        self.assertEqual(name, ["ratio", "resistor"])

    def test_escaped_percent_is_not_a_comment(self):
        kept = nn.strip_latex_comments("a tolerance of 0.05\\,\\% or better")
        self.assertIn("0.05\\,\\%", kept)
        dropped = nn.strip_latex_comments("half % a comment\nrest")
        self.assertNotIn("a comment", dropped)
        self.assertIn("rest", dropped)

    def test_name_split_across_source_lines_is_one_name(self):
        text = "\\anvilpara{The placement of the input\nport \\refnum{20} is shown.}"
        occ = list(nn.iter_spec_occurrences(text))
        self.assertEqual(occ[0][1], ["input", "port"])

    def test_paragraph_numbering_tracks_anvilpara(self):
        text = (
            "\\anvilpara{First paragraph without numerals.}\n"
            "\\anvilpara{Second paragraph names the dummy half-bridge \\refnum{20}.}"
        )
        occ = list(nn.iter_spec_occurrences(text))
        self.assertEqual(occ[0][2], "[0002]")

    def test_section_tracking(self):
        text = (
            "\\detaileddescription\n"
            "\\anvilpara{The sense bridge \\refnum{10} is formed of four piezoresistors.}"
        )
        occ = list(nn.iter_spec_occurrences(text))
        self.assertEqual(occ[0][3], "detailed-description")

    def test_front_matter_before_first_section_macro(self):
        text = "\\anvilpara{The ratio resistor \\refnum{12} sets the gain.}"
        occ = list(nn.iter_spec_occurrences(text))
        self.assertEqual(occ[0][3], "front-matter")

    def test_preposition_boundary_yields_no_capture(self):
        # "increasing the resistance of \refnum{12}" — no name evidence.
        text = "\\anvilpara{Increasing the resistance of \\refnum{12} reduces the slope.}"
        self.assertEqual(list(nn.iter_spec_occurrences(text)), [])

    def test_predicate_boundary_yields_no_capture(self):
        # "then selects \refnum{12}" — a verb, not a noun phrase.
        text = (
            "\\anvilpara{...the cold end of the range, then selects \\refnum{12} "
            "so that the excitation rises.}"
        )
        self.assertEqual(list(nn.iter_spec_occurrences(text)), [])

    def test_numeral_index_shape_captures_forward(self):
        # Numeral at segment start, name after it (numeral-index entry):
        # "\refnum{10} --- sense bridge" captures the name forward.
        text = "\\anvilpara{Index of numerals:\n\\refnum{10} - sense bridge.\n}"
        occ = list(nn.iter_spec_occurrences(text))
        self.assertEqual(occ[0][1], ["sense", "bridge"])

    def test_refnum_placeholder_is_digit_interior_only(self):
        # \refnum{??} (the render-gate placeholder shape) is invisible here.
        text = "\\anvilpara{The bridge \\refnum{??} is shown.}"
        self.assertEqual(list(nn.iter_spec_occurrences(text)), [])

    def test_clause_boundary_keeps_names_separate(self):
        # "PTAT current source \refnum{44}, ratio resistor \refnum{12}" —
        # the comma must stop 44's clause from smearing onto 12.
        text = (
            "\\anvilpara{A PTAT current source \\refnum{44}, ratio resistor "
            "\\refnum{12} sets the slope.}"
        )
        occ = {num: name for num, name, _p, _s in list(nn.iter_spec_occurrences(text))}
        self.assertEqual(occ["44"], ["ptat", "current", "source"])
        self.assertEqual(occ["12"], ["ratio", "resistor"])


class TestVendoredExampleConsistent(unittest.TestCase):
    """Champion note on #1500: the vendored example must NOT false-positive."""

    def test_example_is_consistent(self):
        report = nn.check_numeral_names(_EXAMPLE_DIR)
        self.assertTrue(report["consistent"], msg=nn.format_report(report))
        self.assertEqual(report["conflicting_numerals"], [])

    def test_example_cli_exit_zero(self):
        proc = subprocess.run(
            [sys.executable, _LIB_CLI, str(_EXAMPLE_DIR)], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("OK:", proc.stdout)

    def test_example_covers_all_nine_spec_numerals(self):
        report = nn.check_numeral_names(_EXAMPLE_DIR)
        self.assertGreaterEqual(report["numerals_checked"], 9)
        self.assertGreater(report["occurrences_checked"], 50)


class TestDefectDetection(unittest.TestCase):
    """The issue #1500 canary defect: stale name, wrapped across lines."""

    def setUp(self):
        self._tmp_root = tempfile.TemporaryDirectory(prefix="numeral-names-defect-")
        self.addCleanup(self._tmp_root.cleanup)
        worktree = _scratch_version_dir()
        # Re-root the copy inside this test's temp dir so cleanup is scoped.
        target = Path(self._tmp_root.name) / "scratch.1"
        shutil.move(str(worktree), str(target))
        self.version_dir = target
        spec_path = self.version_dir / "spec.tex"
        text = spec_path.read_text(encoding="utf-8")
        self.assertIn(_BRIEF_ANCHOR, text)
        # Inject the defect: the brief-description paragraph keeps the STALE
        # element name, wrapped across two source lines (so a one-line search
        # for it finds nothing), while everywhere else the numeral 20 names
        # the dummy half-bridge.
        spec_path.write_text(text.replace(_BRIEF_ANCHOR, _STALE_RENAME), encoding="utf-8")

    def test_split_line_rename_is_reported(self):
        report = nn.check_numeral_names(self.version_dir)
        self.assertFalse(report["consistent"])
        by_numeral = {c["numeral"]: c for c in report["conflicting_numerals"]}
        self.assertIn("20", by_numeral)
        names = {e["name"] for e in by_numeral["20"]["names"]}
        self.assertIn("input port", names)
        self.assertIn("dummy half-bridge", names)

    def test_finding_carries_paragraph_and_section(self):
        report = nn.check_numeral_names(self.version_dir)
        conflict = next(c for c in report["conflicting_numerals"] if c["numeral"] == "20")
        stale = next(e for e in conflict["names"] if e["name"] == "input port")
        (loc,) = stale["locations"]
        self.assertEqual(loc["source"], "spec.tex")
        self.assertEqual(loc["section"], "brief-description-of-drawings")
        self.assertRegex(loc["paragraph"], r"^\[\d{4}\]$")

    def test_cli_exit_one_on_conflict(self):
        proc = subprocess.run(
            [sys.executable, _LIB_CLI, str(self.version_dir)], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("CONFLICT: numeral 20", proc.stdout)

    def test_conflicting_entry_json_shape(self):
        report = nn.check_numeral_names(self.version_dir)
        conflict = report["conflicting_numerals"][0]
        self.assertIn("numeral", conflict)
        for entry in conflict["names"]:
            self.assertIn("name", entry)
            self.assertIn("occurrences", entry)
            for loc in entry["locations"]:
                self.assertIn("paragraph", loc)
                self.assertIn("section", loc)
                self.assertIn("source", loc)


class TestDrawingsSide(unittest.TestCase):
    """Drawing-stub participation and graceful no-drawings degradation."""

    def _minimal_dir(self, spec_body: str, drawings: str | None) -> Path:
        root = Path(self._tmp_root.name) / f"minimal.{self._made}"
        self._made += 1
        root.mkdir(parents=True)
        (root / "spec.tex").write_text(spec_body, encoding="utf-8")
        if drawings is not None:
            (root / "drawings").mkdir()
            (root / "drawings" / "drawing-descriptions.md").write_text(
                drawings, encoding="utf-8"
            )
        return root

    def setUp(self):
        self._tmp_root = tempfile.TemporaryDirectory(prefix="numeral-names-drawings-")
        self.addCleanup(self._tmp_root.cleanup)
        self._made = 0

    def test_conflicting_name_in_stub_is_reported(self):
        root = self._minimal_dir(
            "\\anvilpara{The dummy half-bridge \\refnum{20} tracks the offset.}",
            "## FIG. 1 — System diagram\n- Components shown: housing (20).\n",
        )
        report = nn.check_numeral_names(root)
        self.assertFalse(report["consistent"])
        conflict = report["conflicting_numerals"][0]
        self.assertEqual(conflict["numeral"], "20")
        sources = {
            loc["source"]
            for e in conflict["names"]
            for loc in e["locations"]
        }
        self.assertIn("drawings/drawing-descriptions.md", sources)
        figures = {
            loc["paragraph"]
            for e in conflict["names"]
            for loc in e["locations"]
            if loc["source"] == "drawings/drawing-descriptions.md"
        }
        self.assertTrue(any("FIG. 1" in f for f in figures))

    def test_consistent_stub_yields_no_findings(self):
        root = self._minimal_dir(
            "\\anvilpara{The dummy half-bridge \\refnum{20} tracks the offset.}",
            "## FIG. 1 — System diagram\n- Components shown: dummy half-bridge (20).\n",
        )
        report = nn.check_numeral_names(root)
        self.assertTrue(report["consistent"])

    def test_missing_drawings_dir_is_not_an_error(self):
        root = self._minimal_dir(
            "\\anvilpara{The dummy half-bridge \\refnum{20} tracks the offset.}",
            None,
        )
        report = nn.check_numeral_names(root)
        self.assertTrue(report["consistent"])
        self.assertEqual(report["numerals_checked"], 1)

    def test_stub_decimals_do_not_become_numerals(self):
        root = self._minimal_dir(
            "\\anvilpara{The ratio resistor \\refnum{12} sets the slope.}",
            "## FIG. 2 — Schematic (detail of 40); see §4.2.\n- Ratio resistor (12).\n",
        )
        report = nn.check_numeral_names(root)
        self.assertTrue(report["consistent"])
        self.assertEqual(report["numerals_checked"], 1)


class TestCliContract(unittest.TestCase):
    """Exit codes and --json output shape."""

    def setUp(self):
        self._tmp_root = tempfile.TemporaryDirectory(prefix="numeral-names-cli-")
        self.addCleanup(self._tmp_root.cleanup)
        root = Path(self._tmp_root.name) / "empty.1"
        root.mkdir()
        self.empty_dir = root

    def test_missing_spec_is_exit_two(self):
        proc = subprocess.run(
            [sys.executable, _LIB_CLI, str(self.empty_dir)], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("no spec.tex", proc.stderr)

    def test_json_flag_parses_on_example(self):
        proc = subprocess.run(
            [sys.executable, _LIB_CLI, "--json", str(_EXAMPLE_DIR)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["consistent"])
        self.assertEqual(payload["conflicting_numerals"], [])
        self.assertIn("numerals_checked", payload)
        self.assertIn("occurrences_checked", payload)
        self.assertIn("version_dir", payload)


class TestPreflightDocWiring(unittest.TestCase):
    """Pre-flight command doc wires Check 5b (minor, advisory)."""

    REL = "commands/ip-uspto-provisional-pre-flight.md"

    def setUp(self):
        self.text = _read(self.REL)

    def test_check_5b_present(self):
        self.assertIn("Check 5b", self.text)
        self.assertIn("One name per reference numeral", self.text)

    def test_check_5b_advisory_minor_never_gates(self):
        idx = self.text.index("Check 5b")
        block = self.text[idx : idx + 2000]
        self.assertIn("minor", block)
        self.assertIn("advisory", block.lower())
        self.assertIn("NEVER affects pass/fail", block)

    def test_check_5b_delegates_to_the_real_module(self):
        self.assertIn("numeral_names.py", self.text)
        self.assertIn("ip-uspto-provisional/lib/numeral_names.py", self.text)
        self.assertIn("#1500", self.text)

    def test_check_5b_sits_between_check_5_and_check_6(self):
        idx5 = self.text.index("### Check 5 ")
        idx5b = self.text.index("### Check 5b")
        idx6 = self.text.index("### Check 6 ")
        self.assertLess(idx5, idx5b)
        self.assertLess(idx5b, idx6)

    def test_summary_template_has_5b_row(self):
        self.assertIn("| 5b. One name per reference numeral | advisory |", self.text)

    def test_pass_fail_rule_mentions_5b(self):
        self.assertIn(
            "The Check 5b `minor` numeral-name advisories",
            self.text,
        )


class TestAuditDocWiring(unittest.TestCase):
    """Audit command doc wires the Check 3 script pass and Check 9."""

    REL = "commands/ip-uspto-provisional-audit.md"

    def setUp(self):
        self.text = _read(self.REL)

    def test_check_3_runs_the_script(self):
        idx3 = self.text.index("### Check 3")
        idx4 = self.text.index("### Check 4")
        block = self.text[idx3:idx4]
        self.assertIn("numeral_names.py", block)
        self.assertIn("candidate", block.lower())
        self.assertIn("blocker", block)

    def test_check_9_present(self):
        self.assertIn("Check 9", self.text)
        self.assertIn("Related-application term attribution", self.text)

    def test_check_9_skip_when_text_absent(self):
        self.assertIn("n/a (related-application text not supplied)", self.text)
        idx9 = self.text.index("### Check 9")
        block = self.text[idx9 : idx9 + 2500]
        self.assertIn("NEVER a finding", block)
        self.assertIn("no new config key", block)

    def test_check_9_reads_related_application_from_refs(self):
        """Issue #1506: the input is `<thread>/refs/**`, not a BRIEF-recorded path."""
        idx9 = self.text.index("### Check 9")
        block = self.text[idx9 : self.text.index("Determine pass/fail")]
        self.assertIn("<thread>/refs/**", block)
        # No remaining claim that BRIEF.md records the related-application path.
        self.assertNotIn("recorded in `<thread>/BRIEF.md`", block)
        self.assertNotIn("path already recorded", block)
        # The "no new config key" constraint from #1500 is preserved.
        self.assertIn("no new config key", block)

    def test_check_9_states_candidate_identification_and_ambiguity(self):
        idx9 = self.text.index("### Check 9")
        block = self.text[idx9 : self.text.index("Determine pass/fail")]
        self.assertIn("incorporation", block)
        self.assertIn("single unambiguous", block)
        # Absence AND ambiguity both degrade to the n/a row, never a finding.
        self.assertIn("ambiguous", block)
        self.assertIn("empty", block)
        self.assertIn("n/a (related-application text not supplied)", block)

    def test_check_9_notes_bullet_agrees_with_refs_input(self):
        notes = self.text[self.text.index("## Notes for the auditor agent") :]
        self.assertIn("refs/", notes)
        self.assertNotIn("BRIEF.md", notes.split("Check 9")[1].split("\n")[0])

    def test_check_9_ground_truth_inputs_list_refs(self):
        inputs = self.text[self.text.index("## Inputs") : self.text.index("## Outputs")]
        self.assertIn("<thread>/refs/**", inputs)

    def test_check_9_missing_term_is_major(self):
        idx9 = self.text.index("### Check 9")
        block = self.text[idx9 : idx9 + 2500]
        self.assertIn("major", block)
        self.assertIn("case-insensitive", block)

    def test_check_9_sits_after_check_8(self):
        idx8 = self.text.index("### Check 8")
        idx9 = self.text.index("### Check 9")
        idx_passfail = self.text.index("Determine pass/fail")
        self.assertLess(idx8, idx9)
        self.assertLess(idx9, idx_passfail)

    def test_summary_template_has_row_9(self):
        self.assertIn(
            "| 9. Related-application term attribution | n/a (related-application text not supplied) |",
            self.text,
        )

    def test_findings_carry_paragraph_numbers_and_names(self):
        self.assertIn("[000N]", self.text)


if __name__ == "__main__":
    unittest.main()
