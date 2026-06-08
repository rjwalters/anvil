"""Doc-coverage tests for `anvil:rubric-rebackport` (issue #358).

Pin the CLI flag set, mode-dispatch matrix, and per-skill stamping
contracts from SKILL.md and commands/rubric-rebackport.md. These tests
fail when the prose drifts from the implementation.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILL_ROOT = _HERE.parent
sys.path.insert(0, str(_SKILL_ROOT))


COMMAND_FILE = _SKILL_ROOT / "commands" / "rubric-rebackport.md"
SKILL_FILE = _SKILL_ROOT / "SKILL.md"


class TestCommandFlags(unittest.TestCase):
    def setUp(self) -> None:
        self.cmd_text = COMMAND_FILE.read_text(encoding="utf-8")

    def test_documents_apply_flag(self) -> None:
        self.assertIn("--apply", self.cmd_text)

    def test_documents_report_flag(self) -> None:
        self.assertIn("--report", self.cmd_text)

    def test_documents_stamp_only_flag(self) -> None:
        self.assertIn("--stamp-only", self.cmd_text)

    def test_documents_rescore_flag(self) -> None:
        self.assertIn("--rescore", self.cmd_text)

    def test_documents_legacy_rubric_flag(self) -> None:
        self.assertIn("--legacy-rubric", self.cmd_text)

    def test_documents_skill_filter_flag(self) -> None:
        self.assertIn("--skill=", self.cmd_text)


class TestModeDispatchMatrixDocumented(unittest.TestCase):
    def setUp(self) -> None:
        self.cmd_text = COMMAND_FILE.read_text(encoding="utf-8")
        self.skill_text = SKILL_FILE.read_text(encoding="utf-8")

    def test_apply_and_report_mutex_documented(self) -> None:
        self.assertIn("mutually exclusive", self.cmd_text)

    def test_stamp_and_rescore_mutex_documented(self) -> None:
        # Either command file or SKILL.md should declare the mutex.
        text = self.cmd_text + "\n" + self.skill_text
        self.assertTrue(
            "stamp-only` and `--rescore` are mutually exclusive" in text
            or "stamp_only and rescore are mutually exclusive" in text
            or "--rescore` are mutually exclusive" in text
        )

    def test_rescore_requires_legacy_rubric_documented(self) -> None:
        text = self.cmd_text + "\n" + self.skill_text
        self.assertIn("--rescore` requires", text)


class TestDryRunContractDocumented(unittest.TestCase):
    def setUp(self) -> None:
        self.cmd_text = COMMAND_FILE.read_text(encoding="utf-8")

    def test_dry_run_is_default_mode(self) -> None:
        self.assertIn("default", self.cmd_text.lower())
        self.assertIn("dry-run", self.cmd_text.lower())

    def test_idempotence_documented(self) -> None:
        self.assertIn("Idempotence", self.cmd_text)


class TestPerSkillStampingValuesDocumented(unittest.TestCase):
    def setUp(self) -> None:
        self.skill_text = SKILL_FILE.read_text(encoding="utf-8")

    def test_memo_v2_44_35_documented(self) -> None:
        self.assertIn("anvil-memo-v2", self.skill_text)
        self.assertIn("35", self.skill_text)
        self.assertIn("44", self.skill_text)

    def test_memo_legacy_40_32_documented(self) -> None:
        self.assertIn("anvil-memo-v1-legacy-40", self.skill_text)
        self.assertIn("32", self.skill_text)

    def test_rescore_sidecar_naming_convention_documented(self) -> None:
        self.assertIn(".review.rescore-", self.skill_text)


class TestSkillFrontmatter(unittest.TestCase):
    """The frontmatter on SKILL.md must declare the bridge-tool shape."""

    def setUp(self) -> None:
        self.text = SKILL_FILE.read_text(encoding="utf-8")

    def test_skill_name(self) -> None:
        self.assertIn("name: rubric-rebackport", self.text)

    def test_skill_type_is_bridge_tool(self) -> None:
        self.assertIn("type: bridge-tool", self.text)

    def test_user_invocable_is_true(self) -> None:
        self.assertIn("user-invocable: true", self.text)


if __name__ == "__main__":
    unittest.main()
