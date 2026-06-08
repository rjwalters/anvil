"""Tests for ``anvil.skills.rubric-rebackport.lib.plan`` (issue #358)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _skill_lib import detect, plan  # noqa: E402
from _rebackport_fixtures import (  # noqa: E402
    build_fully_stamped,
    build_legacy_unstamped,
    build_mixed_skill_portfolio,
    build_partially_stamped,
)

inventory_tree = detect.inventory_tree
KNOWN_RUBRICS = plan.KNOWN_RUBRICS
Mode = plan.Mode
build_plan = plan.build_plan
infer_target_rubric_id = plan.infer_target_rubric_id
lookup_rubric_by_id = plan.lookup_rubric_by_id


class TestStampOnlyPlan(unittest.TestCase):
    def test_legacy_unstamped_plan_emits_all_three_edits(self) -> None:
        with TemporaryDirectory() as td:
            project = build_legacy_unstamped(Path(td))
            inv = inventory_tree(project)
            p = build_plan(inv, mode=Mode.STAMP_ONLY)
            self.assertEqual(len(p.reviews), 1)
            rp = p.reviews[0]
            self.assertFalse(rp.skipped)
            self.assertIsNotNone(rp.rubric)
            self.assertIsNotNone(rp.stamp_meta)
            self.assertIsNotNone(rp.stamp_progress_rows)
            self.assertIsNotNone(rp.summary_block)

    def test_heuristic_inference_memo_40(self) -> None:
        with TemporaryDirectory() as td:
            project = build_legacy_unstamped(Path(td))
            inv = inventory_tree(project)
            p = build_plan(inv, mode=Mode.STAMP_ONLY)
            rp = p.reviews[0]
            self.assertEqual(rp.rubric.id, "anvil-memo-v1-legacy-40")
            self.assertEqual(rp.rubric.total, 40)
            self.assertEqual(rp.rubric.advance_threshold, 32)

    def test_operator_assertion_overrides_heuristic(self) -> None:
        with TemporaryDirectory() as td:
            project = build_legacy_unstamped(Path(td))
            inv = inventory_tree(project)
            p = build_plan(
                inv,
                mode=Mode.STAMP_ONLY,
                legacy_rubric="anvil-memo-v2",
            )
            rp = p.reviews[0]
            self.assertEqual(rp.rubric.id, "anvil-memo-v2")
            self.assertEqual(rp.rubric.total, 44)
            self.assertEqual(rp.rubric.advance_threshold, 35)

    def test_partially_stamped_plan_only_emits_progress_op(self) -> None:
        with TemporaryDirectory() as td:
            project = build_partially_stamped(Path(td))
            inv = inventory_tree(project)
            p = build_plan(inv, mode=Mode.STAMP_ONLY)
            self.assertEqual(len(p.reviews), 1)
            rp = p.reviews[0]
            self.assertIsNone(rp.stamp_meta)
            self.assertIsNotNone(rp.stamp_progress_rows)

    def test_fully_stamped_plan_is_noop(self) -> None:
        with TemporaryDirectory() as td:
            project = build_fully_stamped(Path(td))
            inv = inventory_tree(project)
            p = build_plan(inv, mode=Mode.STAMP_ONLY)
            self.assertEqual(len(p.reviews), 1)
            rp = p.reviews[0]
            self.assertTrue(rp.is_noop)

    def test_skill_filter_skips_offtarget(self) -> None:
        with TemporaryDirectory() as td:
            project = build_mixed_skill_portfolio(Path(td))
            inv = inventory_tree(project)
            p = build_plan(
                inv, mode=Mode.STAMP_ONLY, skill_filter="memo"
            )
            self.assertEqual(len(p.reviews), 2)
            memo_plan = next(
                r for r in p.reviews if r.skill == "memo"
            )
            proposal_plan = next(
                r for r in p.reviews if r.skill == "proposal"
            )
            self.assertFalse(memo_plan.skipped)
            self.assertTrue(proposal_plan.skipped)
            self.assertIn("outside", proposal_plan.skip_reason)


class TestRescorePlan(unittest.TestCase):
    def test_rescore_requires_legacy_rubric(self) -> None:
        with TemporaryDirectory() as td:
            project = build_legacy_unstamped(Path(td))
            inv = inventory_tree(project)
            p = build_plan(inv, mode=Mode.RESCORE)
            rp = p.reviews[0]
            self.assertTrue(rp.skipped)
            self.assertIn("--legacy-rubric", rp.skip_reason)

    def test_rescore_emits_sidecar_spec(self) -> None:
        with TemporaryDirectory() as td:
            project = build_legacy_unstamped(Path(td))
            inv = inventory_tree(project)
            p = build_plan(
                inv,
                mode=Mode.RESCORE,
                legacy_rubric="anvil-memo-v1-legacy-40",
            )
            rp = p.reviews[0]
            self.assertFalse(rp.skipped)
            self.assertIsNotNone(rp.rescore_spec)
            self.assertEqual(
                rp.rescore_spec.target_rubric.id, "anvil-memo-v2"
            )
            expected_name = (
                rp.review_dir.name + ".rescore-anvil-memo-v2"
            )
            self.assertEqual(
                rp.rescore_spec.sidecar_path.name, expected_name
            )

    def test_rescore_noop_when_sidecar_exists(self) -> None:
        with TemporaryDirectory() as td:
            project = build_legacy_unstamped(Path(td))
            inv = inventory_tree(project)
            review_dir = inv.reviews[0].review_dir
            sidecar = (
                review_dir.parent
                / f"{review_dir.name}.rescore-anvil-memo-v2"
            )
            sidecar.mkdir()
            inv = inventory_tree(project)
            p = build_plan(
                inv,
                mode=Mode.RESCORE,
                legacy_rubric="anvil-memo-v1-legacy-40",
            )
            legacy_review_id = inv.reviews[0].review_id
            rp_legacy = next(
                r for r in p.reviews if r.review_id == legacy_review_id
            )
            self.assertIsNone(
                rp_legacy.rescore_spec,
                "rescore should be no-op when sidecar already exists",
            )


class TestRubricCatalog(unittest.TestCase):
    def test_known_rubrics_cover_memo_and_proposal(self) -> None:
        self.assertIn(("memo", 40), KNOWN_RUBRICS)
        self.assertIn(("memo", 44), KNOWN_RUBRICS)
        self.assertIn(("proposal", 40), KNOWN_RUBRICS)
        self.assertIn(("proposal", 44), KNOWN_RUBRICS)

    def test_memo_v2_threshold_is_35(self) -> None:
        ri = KNOWN_RUBRICS[("memo", 44)]
        self.assertEqual(ri.id, "anvil-memo-v2")
        self.assertEqual(ri.advance_threshold, 35)

    def test_memo_v1_legacy_threshold_is_32(self) -> None:
        ri = KNOWN_RUBRICS[("memo", 40)]
        self.assertEqual(ri.id, "anvil-memo-v1-legacy-40")
        self.assertEqual(ri.advance_threshold, 32)

    def test_infer_target_rubric_id_handles_unknown_pair(self) -> None:
        self.assertIsNone(
            infer_target_rubric_id("unknown-skill", 40)
        )
        self.assertIsNone(
            infer_target_rubric_id("memo", 99)
        )
        self.assertIsNone(infer_target_rubric_id("memo", None))

    def test_lookup_rubric_by_id_round_trip(self) -> None:
        ri = lookup_rubric_by_id("anvil-memo-v2")
        self.assertIsNotNone(ri)
        self.assertEqual(ri.total, 44)
        self.assertIsNone(lookup_rubric_by_id("anvil-fake-v99"))


class TestHeuristicMiss(unittest.TestCase):
    def test_no_legacy_rubric_no_total_skips_review(self) -> None:
        """If neither --legacy-rubric nor _meta.rubric_total is set, skip."""
        with TemporaryDirectory() as td:
            project = build_legacy_unstamped(Path(td))
            inv = inventory_tree(project)
            meta_path = inv.reviews[0].meta_path
            data = json.loads(meta_path.read_text())
            data.pop("rubric_total", None)
            meta_path.write_text(json.dumps(data, indent=2) + "\n")
            inv = inventory_tree(project)
            p = build_plan(inv, mode=Mode.STAMP_ONLY)
            rp = p.reviews[0]
            self.assertTrue(rp.skipped)
            self.assertIn("rubric_total", rp.skip_reason)


if __name__ == "__main__":
    unittest.main()
