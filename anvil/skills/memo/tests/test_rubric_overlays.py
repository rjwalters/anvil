"""Tests for ``anvil/skills/memo/lib/rubric_overlays.py``.

Covers:

- Each of the 5 shipped overlay JSON files loads cleanly via
  :func:`load_overlay` and round-trips its declared artifact_type.
- The investment-memo overlay is identity (all-zero adjustments,
  empty calibration prose).
- :func:`select_overlay_for_thread` resolves correctly for both layouts
  (no project BRIEF → None; project-brief → matching overlay; unlisted slug → None).
- :class:`OverlayLoadError` fires on:
  - missing file
  - invalid JSON
  - schema violation (wrong artifact_type field, unknown dim key, extra
    top-level field via ``extra="forbid"``)
  - filename ↔ declared artifact_type mismatch
- Doc cross-references in SKILL.md, rubric.md, and memo-review.md mention
  the new overlay surface.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Test module path setup mirrors the project_discovery / project_brief
# test files in this directory.
_LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from project_brief import REGISTERED_ARTIFACT_TYPES, ArtifactType  # noqa: E402
from rubric_overlays import (  # noqa: E402
    OVERLAYS_DIR,
    OverlayLoadError,
    RubricOverlay,
    load_overlay,
    select_overlay_for_thread,
)


class TestRegistryShape(unittest.TestCase):
    """The shipped overlay registry covers every registered ArtifactType."""

    def test_one_overlay_file_per_registered_artifact_type(self) -> None:
        shipped = {p.stem for p in OVERLAYS_DIR.glob("*.json")}
        registered = set(REGISTERED_ARTIFACT_TYPES)
        self.assertEqual(
            shipped,
            registered,
            "Every registered ArtifactType must have a shipped overlay JSON; "
            "and the registry must NOT contain orphans for unknown types.",
        )

    def test_all_shipped_overlays_load_without_error(self) -> None:
        for at in ArtifactType:
            with self.subTest(artifact_type=at.value):
                overlay = load_overlay(at)
                self.assertIsInstance(overlay, RubricOverlay)
                self.assertEqual(overlay.artifact_type, at)


class TestInvestmentMemoIdentity(unittest.TestCase):
    """The investment-memo overlay is the canonical identity overlay."""

    def test_investment_memo_is_identity(self) -> None:
        overlay = load_overlay(ArtifactType.INVESTMENT_MEMO)
        self.assertTrue(
            overlay.is_identity(),
            "investment-memo overlay must be identity (zero adjustments, "
            "no calibration prose) to preserve byte-identical v0 behavior "
            "for threads with artifact_type=investment-memo.",
        )

    def test_non_investment_memo_overlays_are_not_identity(self) -> None:
        for at in ArtifactType:
            if at == ArtifactType.INVESTMENT_MEMO:
                continue
            with self.subTest(artifact_type=at.value):
                overlay = load_overlay(at)
                self.assertFalse(
                    overlay.is_identity(),
                    f"{at.value} overlay should make at least one change "
                    "(either a weight adjustment or calibration prose) "
                    "— an identity overlay for a non-investment-memo type "
                    "is almost certainly a bug.",
                )


class TestWeightAdjustments(unittest.TestCase):
    """Per-dim weight adjustments stay within sensible bounds."""

    BASE_WEIGHTS = {
        "dim_1": 5,
        "dim_2": 6,
        "dim_3": 6,
        "dim_4": 6,
        "dim_5": 4,
        "dim_6": 5,
        "dim_7": 4,
        "dim_8": 4,
        "dim_9": 4,
    }

    def test_no_overlay_drives_any_dim_negative(self) -> None:
        for at in ArtifactType:
            overlay = load_overlay(at)
            for dim, delta in overlay.weight_adjustments.items():
                base = self.BASE_WEIGHTS[dim]
                effective = base + delta
                with self.subTest(artifact_type=at.value, dim=dim):
                    self.assertGreaterEqual(
                        effective,
                        0,
                        f"{at.value}/{dim}: base={base} + delta={delta} = "
                        f"{effective}; overlays must not drive a dim below 0.",
                    )

    def test_dim_keys_are_dim_1_through_dim_9(self) -> None:
        valid = {f"dim_{n}" for n in range(1, 10)}
        for at in ArtifactType:
            overlay = load_overlay(at)
            for dim in overlay.weight_adjustments:
                self.assertIn(dim, valid)
            for dim in overlay.calibration_prose:
                self.assertIn(dim, valid)


class TestSelectOverlayForThread(unittest.TestCase):
    """End-to-end selection from a thread dir under a project BRIEF."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_project(
        self, doc_slugs_and_types: list[tuple[str, str]]
    ) -> Path:
        """Create a project with a BRIEF.md listing the given (slug, type) pairs.

        Each thread directory is materialized empty.
        """
        project_root = self.tmp_path / "test-project"
        project_root.mkdir()

        documents_block = "\n".join(
            f"  - slug: {slug}\n    artifact_type: {atype}"
            for slug, atype in doc_slugs_and_types
        )
        brief = (
            "---\n"
            f"project: test-project\n"
            f"audience: [team]\n"
            f"hard_rules: []\n"
            f"documents:\n{documents_block}\n"
            "---\n"
            "\n"
            "Project brief body.\n"
        )
        (project_root / "BRIEF.md").write_text(brief, encoding="utf-8")
        for slug, _ in doc_slugs_and_types:
            (project_root / slug).mkdir()
        return project_root

    def test_position_paper_thread_resolves_to_position_paper_overlay(self) -> None:
        project_root = self._write_project([("latency-wall", "position-paper")])
        thread_dir = project_root / "latency-wall"
        overlay = select_overlay_for_thread(thread_dir)
        self.assertIsNotNone(overlay)
        self.assertEqual(overlay.artifact_type, ArtifactType.POSITION_PAPER)

    def test_investment_memo_thread_resolves_to_identity_overlay(self) -> None:
        project_root = self._write_project(
            [("investment-memo", "investment-memo")]
        )
        thread_dir = project_root / "investment-memo"
        overlay = select_overlay_for_thread(thread_dir)
        self.assertIsNotNone(overlay)
        self.assertTrue(overlay.is_identity())

    def test_thread_without_project_brief_resolves_to_none(self) -> None:
        # A thread with no project BRIEF on the walk-upward path → no
        # overlay selected. Under #295 every thread is expected to live
        # under a project root; a stray thread that does not satisfy
        # that contract returns None here (and is non-discoverable per
        # project_discovery.discover_thread_root).
        thread_root = self.tmp_path / "standalone-thread"
        thread_root.mkdir()
        (thread_root / "standalone-thread.1").mkdir()
        overlay = select_overlay_for_thread(thread_root)
        self.assertIsNone(overlay)

    def test_unlisted_thread_under_project_brief_resolves_to_none(self) -> None:
        # The thread is on disk under a project-BRIEF root but its slug
        # is not in the BRIEF's documents: list.
        project_root = self._write_project([("listed-thread", "investment-memo")])
        unlisted = project_root / "unlisted-thread"
        unlisted.mkdir()
        overlay = select_overlay_for_thread(unlisted)
        self.assertIsNone(overlay)

    def test_explicit_project_dir_override(self) -> None:
        project_root = self._write_project(
            [("vision-doc", "vision-document")]
        )
        thread_dir = project_root / "vision-doc"
        overlay = select_overlay_for_thread(thread_dir, project_dir=project_root)
        self.assertIsNotNone(overlay)
        self.assertEqual(overlay.artifact_type, ArtifactType.VISION_DOCUMENT)


class TestLoadOverlayErrors(unittest.TestCase):
    """OverlayLoadError covers every load-time failure mode."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _load_from_path(self, overlay_path: Path) -> RubricOverlay:
        """Bypass OVERLAYS_DIR by writing into the real dir under a test name
        and cleaning up. We test the real load path here.
        """
        raise NotImplementedError  # placeholder — tests below use real OVERLAYS_DIR

    def test_missing_overlay_file_raises(self) -> None:
        # Construct a fake ArtifactType-like by patching OVERLAYS_DIR via
        # a monkeypatched helper would be heavy; we trust the production
        # path that exists (one file per registered type). To simulate
        # missing-file, temporarily move one aside.
        target = OVERLAYS_DIR / "position-paper.json"
        backup = OVERLAYS_DIR / "position-paper.json.bak"
        target.rename(backup)
        try:
            with self.assertRaises(OverlayLoadError) as ctx:
                load_overlay(ArtifactType.POSITION_PAPER)
            self.assertIn("No overlay file found", str(ctx.exception))
            self.assertIn("position-paper", str(ctx.exception))
        finally:
            backup.rename(target)

    def test_invalid_json_raises(self) -> None:
        target = OVERLAYS_DIR / "tactical-plan.json"
        original = target.read_text(encoding="utf-8")
        target.write_text("{ not valid json", encoding="utf-8")
        try:
            with self.assertRaises(OverlayLoadError) as ctx:
                load_overlay(ArtifactType.TACTICAL_PLAN)
            self.assertIn("invalid JSON", str(ctx.exception))
        finally:
            target.write_text(original, encoding="utf-8")

    def test_unknown_dim_key_in_weight_adjustments_raises(self) -> None:
        target = OVERLAYS_DIR / "vision-document.json"
        original = target.read_text(encoding="utf-8")
        # Inject an unknown dim key.
        bad = json.loads(original)
        bad["weight_adjustments"]["dim_99"] = -1
        target.write_text(json.dumps(bad), encoding="utf-8")
        try:
            with self.assertRaises(OverlayLoadError) as ctx:
                load_overlay(ArtifactType.VISION_DOCUMENT)
            self.assertIn("dim_99", str(ctx.exception))
            self.assertIn("weight_adjustments", str(ctx.exception))
        finally:
            target.write_text(original, encoding="utf-8")

    def test_filename_mismatch_raises(self) -> None:
        # Write an overlay JSON whose declared artifact_type doesn't match
        # the filename we ask for. The mismatch check fires after Pydantic
        # validates the JSON content.
        target = OVERLAYS_DIR / "descriptive-thesis.json"
        original = target.read_text(encoding="utf-8")
        bad = json.loads(original)
        bad["artifact_type"] = "position-paper"
        target.write_text(json.dumps(bad), encoding="utf-8")
        try:
            with self.assertRaises(OverlayLoadError) as ctx:
                load_overlay(ArtifactType.DESCRIPTIVE_THESIS)
            self.assertIn("filename mismatch", str(ctx.exception))
        finally:
            target.write_text(original, encoding="utf-8")

    def test_extra_top_level_field_raises(self) -> None:
        target = OVERLAYS_DIR / "investment-memo.json"
        original = target.read_text(encoding="utf-8")
        bad = json.loads(original)
        bad["unexpected_field"] = 42
        target.write_text(json.dumps(bad), encoding="utf-8")
        try:
            with self.assertRaises(OverlayLoadError) as ctx:
                load_overlay(ArtifactType.INVESTMENT_MEMO)
            self.assertIn("schema error", str(ctx.exception))
        finally:
            target.write_text(original, encoding="utf-8")


class TestDocCanonicalReferences(unittest.TestCase):
    """The rubric overlay surface is documented in SKILL.md, rubric.md, and memo-review.md."""

    SKILL_ROOT = Path(__file__).resolve().parent.parent

    def test_skill_md_documents_overlay_system(self) -> None:
        body = (self.SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("rubric_overlays", body)

    def test_rubric_md_documents_overlay_system(self) -> None:
        body = (self.SKILL_ROOT / "rubric.md").read_text(encoding="utf-8")
        self.assertIn("rubric_overlays", body)

    def test_memo_review_command_invokes_overlay_selection(self) -> None:
        body = (self.SKILL_ROOT / "commands" / "memo-review.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("select_overlay_for_thread", body)


if __name__ == "__main__":
    unittest.main()
