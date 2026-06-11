"""Structural smoke tests for the ``anvil:ip-uspto-provisional`` skill.

These tests assert **structural properties** of the shipped skill files
(files exist, frontmatter parses, the rubric declares 9 dimensions summing
to 45 with a >=39 advance threshold under the ``anvil-ip-provisional-v1``
id, the claims-optional posture is stated, every critic-writing command
stamps the issue #346 rubric-version fields and writes via the
staged-sidecar primitive, and the ``anvil:ip-uspto`` SKILL.md caveat
cross-references this sibling skill). They are intentionally NOT
golden-file tests — the skill is a generative authoring skill and prose
varies across runs and models.

Runs under either ``pytest anvil/skills/ip-uspto-provisional/tests/`` or
``python -m unittest discover anvil/skills/ip-uspto-provisional/tests/``.

The module filename is deliberately distinct
(``test_ip_uspto_provisional_skeleton``) per the issue #58 cross-skill
collection convention. Like the other hyphenated skill directories
(``project-migrate``, ``project-scout``), this tests dir carries NO
``__init__.py`` — ``ip-uspto-provisional`` is not a valid Python package
name, so the unique-filename rule (not a package chain) is what prevents
the pytest collection collision here (the ``anvil:ip-uspto`` sibling uses
the same shape).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
_IP_USPTO_ROOT = _SKILL_ROOT.parent / "ip-uspto"

RUBRIC_ID = "anvil-ip-provisional-v1"


def _read(rel: str) -> str:
    return (_SKILL_ROOT / rel).read_text(encoding="utf-8")


def _parse_frontmatter(text: str) -> dict:
    """Parse a leading ``---``-delimited YAML frontmatter block.

    Uses PyYAML when available; falls back to a minimal ``key: value``
    parser so the test does not hard-depend on PyYAML being installed.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}
    block = "\n".join(lines[1:end])
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except Exception:
        result: dict = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"').strip("'")
        return result


class TestFilesExist(unittest.TestCase):
    """The pinned file manifest is present on disk (Phase 1 scope)."""

    EXPECTED = [
        "SKILL.md",
        "rubric.md",
        "README.md",
        "commands/ip-uspto-provisional.md",
        "commands/ip-uspto-provisional-draft.md",
        "commands/ip-uspto-provisional-review.md",
        "commands/ip-uspto-provisional-112.md",
        "commands/ip-uspto-provisional-prior-art.md",
        "commands/ip-uspto-provisional-revise.md",
        "tests/test_ip_uspto_provisional_skeleton.py",
    ]

    def test_manifest_present(self):
        for rel in self.EXPECTED:
            with self.subTest(path=rel):
                self.assertTrue(
                    (_SKILL_ROOT / rel).exists(), f"missing skill file: {rel}"
                )

    def test_deferred_phase2_commands_absent(self):
        # Phase 1 deliberately ships ONLY the convergence loop. The audit /
        # finalize / pre-flight / figures / counsel-memo commands are
        # tracked follow-ups (issue #433 curation) — their accidental
        # presence here would mean scope creep landed un-reviewed.
        for stem in (
            "ip-uspto-provisional-audit",
            "ip-uspto-provisional-finalize",
            "ip-uspto-provisional-pre-flight",
            "ip-uspto-provisional-figures",
            "ip-uspto-provisional-counsel-memo",
        ):
            with self.subTest(command=stem):
                self.assertFalse(
                    (_SKILL_ROOT / "commands" / f"{stem}.md").exists(),
                    f"{stem}.md is deferred Phase 2+ scope",
                )


class TestSkillFrontmatter(unittest.TestCase):
    """SKILL.md frontmatter matches the sibling skills' shape."""

    def test_frontmatter(self):
        fm = _parse_frontmatter(_read("SKILL.md"))
        self.assertEqual(fm.get("name"), "ip-uspto-provisional")
        self.assertEqual(fm.get("domain"), "ip")
        self.assertEqual(fm.get("type"), "skill")
        self.assertIn(fm.get("user-invocable"), (False, "false"))

    def test_cross_references_sibling_skill(self):
        # The provisional is the conversion seed for the non-provisional.
        self.assertIn("anvil:ip-uspto", _read("SKILL.md"))

    def test_sidecar_and_stamping_contracts_referenced(self):
        text = _read("SKILL.md")
        self.assertIn("staged_sidecar", text)
        self.assertIn(RUBRIC_ID, text)
        self.assertIn("machine-summary", text)

    def test_claims_optional_posture_stated(self):
        text = _read("SKILL.md").lower()
        self.assertIn("claims-optional", text)
        self.assertIn("never a finding", text)

    def test_state_machine_through_audited(self):
        # State machine is defined through AUDITED even though the audit
        # command itself is a Phase 2 follow-up.
        text = _read("SKILL.md")
        self.assertIn("AUDITED", text)
        self.assertIn("READY", text)
        # COUNSEL-READY is explicitly deferred, not silently absent.
        self.assertIn("COUNSEL-READY", text)


class TestCommandFrontmatter(unittest.TestCase):
    """Every command file carries a name/description frontmatter block."""

    COMMANDS = {
        "commands/ip-uspto-provisional.md": "ip-uspto-provisional",
        "commands/ip-uspto-provisional-draft.md": "ip-uspto-provisional-draft",
        "commands/ip-uspto-provisional-review.md": "ip-uspto-provisional-review",
        "commands/ip-uspto-provisional-112.md": "ip-uspto-provisional-112",
        "commands/ip-uspto-provisional-prior-art.md": "ip-uspto-provisional-prior-art",
        "commands/ip-uspto-provisional-revise.md": "ip-uspto-provisional-revise",
    }

    def test_command_frontmatter(self):
        for rel, expected_name in self.COMMANDS.items():
            with self.subTest(path=rel):
                fm = _parse_frontmatter(_read(rel))
                self.assertEqual(fm.get("name"), expected_name)
                self.assertTrue(
                    fm.get("description"), f"{rel} missing a description"
                )

    CRITIC_COMMANDS = (
        "commands/ip-uspto-provisional-review.md",
        "commands/ip-uspto-provisional-112.md",
        "commands/ip-uspto-provisional-prior-art.md",
    )

    def test_critic_commands_stamp_rubric_version(self):
        # ALL critic-writing commands stamp rubric_id / rubric_total /
        # advance_threshold per the issue #346 contract and write via the
        # staged-sidecar primitive (issues #350/#376).
        for rel in self.CRITIC_COMMANDS:
            with self.subTest(path=rel):
                text = _read(rel)
                self.assertIn(RUBRIC_ID, text)
                self.assertIn('rubric_total: 45', text)
                self.assertIn('advance_threshold: 39', text)
                self.assertIn("staged_sidecar", text)
                self.assertIn("cleanup_one_staging", text)
                self.assertIn("machine-summary", text)

    def test_revise_aggregates_against_45_and_39(self):
        text = _read("commands/ip-uspto-provisional-revise.md")
        self.assertIn(RUBRIC_ID, text)
        self.assertIn("39/45", text)
        self.assertIn("score_history", text)

    def test_draft_has_no_abstract_and_optional_claim_seed(self):
        text = _read("commands/ip-uspto-provisional-draft.md")
        self.assertIn("claim-seed", text)
        self.assertIn("No abstract", text)
        # The class is reused from the ip-uspto sibling's assets.
        self.assertIn("anvil-uspto.cls", text)
        self.assertIn("anvil/skills/ip-uspto/assets", text)


class TestRubric(unittest.TestCase):
    """rubric.md declares 9 dims summing to 45, >=39, enablement-dominant."""

    def setUp(self):
        self.text = _read("rubric.md")

    def test_nine_dimensions_sum_to_forty_five(self):
        rows = re.findall(
            r"^\|\s*([1-9])\s*\|\s*\*\*[^|]+\*\*\s*\|\s*(\d+)\s*\|",
            self.text,
            flags=re.MULTILINE,
        )
        self.assertEqual(
            len(rows), 9, f"expected 9 dimension rows, found {len(rows)}"
        )
        indices = sorted(int(i) for i, _ in rows)
        self.assertEqual(indices, [1, 2, 3, 4, 5, 6, 7, 8, 9])
        total = sum(int(w) for _, w in rows)
        self.assertEqual(total, 45, f"dimension weights sum to {total}, not 45")

    def test_dim_one_is_enablement_depth_dominant(self):
        # The provisional inversion: dim 1 §112(a) enablement depth carries
        # the dominant weight 8 (vs ip-uspto's flat 5s).
        self.assertTrue(
            re.search(
                r"^\|\s*1\s*\|\s*\*\*§112\(a\) enablement depth\*\*\s*\|\s*8\s*\|",
                self.text,
                flags=re.MULTILINE,
            ),
            "dim 1 must be §112(a) enablement depth at weight 8",
        )

    def test_dim_nine_is_conversion_readiness(self):
        # Replaces ip-uspto's Claim-spec correspondence (inapplicable when
        # claims are optional) per the issue #433 curation.
        self.assertTrue(
            re.search(
                r"^\|\s*9\s*\|\s*\*\*Conversion readiness\*\*\s*\|\s*6\s*\|",
                self.text,
                flags=re.MULTILINE,
            ),
            "dim 9 must be Conversion readiness at weight 6",
        )
        self.assertNotIn("| **Claim-spec correspondence** |", self.text)

    def test_advance_threshold_is_high_band(self):
        # Legal artifact -> the high threshold band (>=39), NOT >=35.
        self.assertTrue(
            re.search(r"(≥\s*39|>=\s*39|\b39/45\b)", self.text),
            "advance threshold of 39 not stated in rubric.md",
        )
        self.assertIsNone(
            re.search(r"threshold to advance[^\n]*35", self.text, re.IGNORECASE),
            "rubric must not declare a 35 advance threshold",
        )

    def test_rubric_id_declared(self):
        self.assertIn(RUBRIC_ID, self.text)

    def test_claims_optional_never_penalized(self):
        lowered = self.text.lower()
        self.assertIn("never a finding", lowered)
        self.assertIn("never a deduction", lowered)
        self.assertIn("never a critical flag", lowered)

    def test_machine_summary_scorecard_kind(self):
        self.assertIn("machine-summary", self.text)

    def test_stamping_fields_in_meta_example(self):
        self.assertIn('"rubric_id": "anvil-ip-provisional-v1"', self.text)
        self.assertIn('"rubric_total": 45', self.text)
        self.assertIn('"advance_threshold": 39', self.text)

    def test_s112_is_load_bearing_owner(self):
        # s112 owns the dominant dimension and may not be subsetted out.
        self.assertIn("load-bearing critic", self.text)
        self.assertIn("may not be subsetted out", self.text)


class TestSiblingCrossReference(unittest.TestCase):
    """The ip-uspto SKILL.md caveat now points at this sibling skill."""

    def test_ip_uspto_caveat_updated(self):
        text = (_IP_USPTO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(
            "ip-uspto-provisional",
            text,
            "anvil/skills/ip-uspto/SKILL.md must cross-reference the "
            "ip-uspto-provisional sibling skill (issue #433)",
        )
        self.assertNotIn(
            "Provisional applications and design patents are out of scope",
            text,
            "the stale provisionals-out-of-scope caveat must be updated",
        )


if __name__ == "__main__":
    unittest.main()
