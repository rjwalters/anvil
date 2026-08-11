"""Structural tests for the opt-in prior-art search step in the provisional.

The mirror of ``test_ip_uspto_prior_art_search_wiring.py``: issue #958 wires
`anvil:ip-search` into BOTH ip skills' lifecycles, and the two must not
drift apart. Behavior lives in
``anvil/skills/ip-search/lib/prior_art_step.py`` (tested by
``test_ip_search_prior_art_step.py``); this module asserts the provisional's
own documents carry the contract, and that the knob does not leak into the
default critic set (``s112`` + friends) or the reviser's
all-configured-critics-present rule.

The module filename is deliberately distinct per the issue #58 cross-skill
collection convention.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILL_ROOT = _HERE.parent
_IP_SEARCH_ROOT = _SKILL_ROOT.parent / "ip-search"

KNOB = "prior_art_search"


def _read(rel: str) -> str:
    return (_SKILL_ROOT / rel).read_text(encoding="utf-8")


class TestPriorArtCommand(unittest.TestCase):
    """commands/ip-uspto-provisional-prior-art.md carries the step-0 contract."""

    def setUp(self):
        self.text = _read("commands/ip-uspto-provisional-prior-art.md")

    def test_step_zero_section_present(self):
        self.assertIn(
            "## Step 0 — optional prior-art search (opt-in, OFF by default)", self.text
        )
        procedure = self.text.split("## Procedure", 1)[1]
        self.assertLess(
            procedure.index("0. **Optional prior-art search**"),
            procedure.index("1. **Discover state"),
        )

    def test_knob_named_and_off_by_default(self):
        self.assertIn(f'{{ "{KNOB}": true }}', self.text)
        self.assertIn("<thread>/.anvil.json", self.text)
        self.assertIn("**Absent ⇒ off.**", self.text)
        self.assertIn("byte-identically to its pre-#958 form", self.text)
        for phrase in ("no corpus query", "no API-key read", "no network call"):
            self.assertIn(phrase, self.text)

    def test_knob_is_a_sibling_of_the_existing_overrides(self):
        self.assertIn("sibling top-level key alongside", self.text)
        self.assertIn("max_iterations", self.text)
        self.assertIn("critics", self.text)

    def test_cli_override_documented_in_both_directions(self):
        self.assertIn("--prior-art-search", self.text)
        self.assertIn("--no-prior-art-search", self.text)

    def test_never_overwrites_and_marks_machine_fetched(self):
        self.assertIn("force=False", self.text)
        self.assertIn("Never overwrites", self.text)
        self.assertIn('source: "anvil:ip-search/<corpus>"', self.text)
        self.assertIn("partition_prior_art", self.text)

    def test_never_blocks_and_preserves_the_null_dim5_path(self):
        self.assertIn("Never blocks", self.text)
        self.assertIn("result.blocking", self.text)
        self.assertIn("no prior art supplied", self.text)
        self.assertIn("Dim 5 `null`", self.text)

    def test_non_scope_boundary_preserved(self):
        self.assertIn("It does **not** perform its own patent search", self.text)
        self.assertIn("The critic itself still performs no search", self.text)
        self.assertIn("owns every dimension-5 judgment", self.text)

    def test_machine_fetched_art_is_scored_like_any_other(self):
        self.assertIn("Step 0 renders no judgment", self.text)
        self.assertIn("provenance, not weight", self.text)

    def test_names_the_step_module_and_loader(self):
        self.assertIn("prior_art_step", self.text)
        self.assertIn("import_skill_lib_module", self.text)
        self.assertIn("run_step", self.text)

    def test_step_module_exists_where_the_command_says_it_does(self):
        self.assertTrue((_IP_SEARCH_ROOT / "lib" / "prior_art_step.py").is_file())


class TestOrchestrator(unittest.TestCase):
    """commands/ip-uspto-provisional.md documents the knob."""

    def setUp(self):
        self.text = _read("commands/ip-uspto-provisional.md")

    def test_config_discovery_documents_the_knob(self):
        block = self.text.split("## Configuration discovery", 1)[1]
        self.assertIn(f'"{KNOB}": true', block)
        self.assertIn("off-by-default", block)
        self.assertIn("byte-identical to a pre-#958 install", block)

    def test_both_critic_dispatch_rows_mention_the_step(self):
        rows = [
            ln
            for ln in self.text.splitlines()
            if ln.startswith(
                ("   | `DRAFTED`", "   | `REVISED` (pre-flight PASSED)")
            )
        ]
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertIn(KNOB, row)


class TestSkillMd(unittest.TestCase):
    """SKILL.md documents the knob without disturbing the critic set."""

    def setUp(self):
        self.text = _read("SKILL.md")

    def test_optional_search_step_section(self):
        self.assertIn("**Optional prior-art search step** (issue #958)", self.text)
        self.assertIn("NOT a critic", self.text)
        self.assertIn("does not join the `critics` array", self.text)

    def test_default_critic_set_unchanged(self):
        # The provisional's default set is review + s112 + priorart; the
        # search step must not appear in it (it writes no sibling, so the
        # reviser would block forever waiting for one).
        self.assertIn("`review + s112 + priorart`", self.text)
        for line in self.text.splitlines():
            if '"critics"' in line:
                self.assertNotIn(KNOB, line)

    def test_thread_layout_and_dispatch_row(self):
        anvil_json_line = next(
            ln for ln in self.text.splitlines() if ln.strip().startswith(".anvil.json")
        )
        self.assertIn(KNOB, anvil_json_line)
        dispatch = next(
            ln
            for ln in self.text.splitlines()
            if ln.startswith("| `ip-uspto-provisional-prior-art")
        )
        self.assertIn("OFF by default", dispatch)
        self.assertIn("never overwrites", dispatch)

    def test_caveat_updated_not_deleted(self):
        self.assertIn(
            "**The prior-art critic does NOT do its own patent search.**", self.text
        )
        self.assertIn("never an attorney clearance search", self.text)


if __name__ == "__main__":
    unittest.main()
