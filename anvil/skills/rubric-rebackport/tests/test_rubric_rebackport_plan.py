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
    build_pub_44_unstamped,
)

inventory_tree = detect.inventory_tree
CURRENT_RUBRIC_BY_SKILL = plan.CURRENT_RUBRIC_BY_SKILL
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

    # ---- Post-#357 /44 (and /45 for ip-uspto) catalog coverage (issue #366) ----

    def test_known_rubrics_cover_44_skills(self) -> None:
        """All 6 post-#357 (skill, total) pairs are in the catalog."""
        for skill, total in [
            ("pub", 44),
            ("report", 44),
            ("deck", 44),
            ("slides", 44),
            ("installation", 44),
            ("ip-uspto", 45),
        ]:
            self.assertIn((skill, total), KNOWN_RUBRICS)

    def test_pub_v2_44_id_and_threshold(self) -> None:
        ri = KNOWN_RUBRICS[("pub", 44)]
        self.assertEqual(ri.id, "anvil-pub-v2")
        self.assertEqual(ri.total, 44)
        self.assertEqual(ri.advance_threshold, 35)

    def test_report_v2_44_id_and_threshold(self) -> None:
        ri = KNOWN_RUBRICS[("report", 44)]
        self.assertEqual(ri.id, "anvil-report-v2")
        self.assertEqual(ri.total, 44)
        self.assertEqual(ri.advance_threshold, 39)

    def test_deck_v2_44_id_and_threshold(self) -> None:
        ri = KNOWN_RUBRICS[("deck", 44)]
        self.assertEqual(ri.id, "anvil-deck-v2")
        self.assertEqual(ri.total, 44)
        self.assertEqual(ri.advance_threshold, 39)

    def test_slides_v2_44_id_and_threshold(self) -> None:
        ri = KNOWN_RUBRICS[("slides", 44)]
        self.assertEqual(ri.id, "anvil-slides-v2")
        self.assertEqual(ri.total, 44)
        self.assertEqual(ri.advance_threshold, 35)

    def test_installation_v2_44_id_and_threshold(self) -> None:
        ri = KNOWN_RUBRICS[("installation", 44)]
        self.assertEqual(ri.id, "anvil-installation-v2")
        self.assertEqual(ri.total, 44)
        self.assertEqual(ri.advance_threshold, 35)

    def test_ip_uspto_v2_45_id_and_threshold(self) -> None:
        # ip-uspto is /45, not /44 — its rubric has an extra dimension.
        ri = KNOWN_RUBRICS[("ip-uspto", 45)]
        self.assertEqual(ri.id, "anvil-ip-uspto-v2")
        self.assertEqual(ri.total, 45)
        self.assertEqual(ri.advance_threshold, 39)

    def test_current_rubric_by_skill_points_at_44_for_migrated_skills(
        self,
    ) -> None:
        """CURRENT_RUBRIC_BY_SKILL must repoint at the post-#357 rubrics."""
        for skill in ("pub", "report", "deck", "slides", "installation"):
            self.assertEqual(
                CURRENT_RUBRIC_BY_SKILL[skill].total,
                44,
                f"`{skill}` current rubric must be /44 post-#357",
            )

    def test_current_rubric_by_skill_points_at_45_for_ip_uspto(self) -> None:
        self.assertEqual(CURRENT_RUBRIC_BY_SKILL["ip-uspto"].total, 45)
        self.assertEqual(
            CURRENT_RUBRIC_BY_SKILL["ip-uspto"].id, "anvil-ip-uspto-v2"
        )

    def test_current_rubric_by_skill_memo_and_proposal_unchanged(self) -> None:
        """Memo + proposal already targeted /44 pre-#366; no regression."""
        self.assertEqual(CURRENT_RUBRIC_BY_SKILL["memo"].total, 44)
        self.assertEqual(CURRENT_RUBRIC_BY_SKILL["proposal"].total, 44)

    def test_legacy_40_rows_retained_for_stamp_only_inference(self) -> None:
        """Adding /44 rows must NOT remove the /40 rows (legacy reviews still need them)."""
        for skill in (
            "pub",
            "report",
            "deck",
            "slides",
            "installation",
            "ip-uspto",
        ):
            self.assertIn(
                (skill, 40),
                KNOWN_RUBRICS,
                f"/40 row for `{skill}` removed — legacy reviews can no "
                "longer auto-infer.",
            )


class TestPub44AutoInference(unittest.TestCase):
    """End-to-end: /44-era pub review with `rubric_total: 44` but no
    `rubric_id` should resolve to `anvil-pub-v2` without `--legacy-rubric`.

    This is the canary failure mode that motivated issue #366: before
    the catalog gained the `("pub", 44)` entry, the planner would skip
    such reviews with a "heuristic miss" note instead of stamping them.
    """

    def test_pub_44_heuristic_inference_resolves_to_v2(self) -> None:
        with TemporaryDirectory() as td:
            project = build_pub_44_unstamped(Path(td))
            inv = inventory_tree(project)
            self.assertEqual(len(inv.reviews), 1)
            self.assertEqual(inv.reviews[0].inferred_skill, "pub")
            p = build_plan(inv, mode=Mode.STAMP_ONLY)
            rp = p.reviews[0]
            self.assertFalse(
                rp.skipped,
                f"Expected stamping plan; got skip with reason: "
                f"{rp.skip_reason}",
            )
            self.assertIsNotNone(rp.rubric)
            self.assertEqual(rp.rubric.id, "anvil-pub-v2")
            self.assertEqual(rp.rubric.total, 44)
            self.assertEqual(rp.rubric.advance_threshold, 35)
            self.assertIsNotNone(rp.stamp_meta)
            self.assertEqual(rp.stamp_meta.rubric_id, "anvil-pub-v2")
            self.assertEqual(rp.stamp_meta.rubric_total, 44)
            self.assertEqual(rp.stamp_meta.advance_threshold, 35)


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
