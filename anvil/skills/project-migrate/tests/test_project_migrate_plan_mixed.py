"""Plan tests for mixed-skill and nested-but-flat shapes (issue #382).

Asserts the planner emits the nesting rename for flat
deck/slides/proposal threads, carries the deck paired iteration-cap
override into the BRIEF merge, and does NOT plan a body rename for
retained body filenames (deck.md / proposal.tex — slug-echo scoped out).

Per the #58 packaging convention this filename is unique across the
``anvil/skills/*/tests/`` tree.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _project_migrate_skill_lib import plan as plan_mod  # noqa: E402
from _fixtures import (  # noqa: E402
    build_aldus_shaped_deck,
    build_mixed_memo_deck_proposal,
)

build_plan = plan_mod.build_plan


class TestAldusShapedDeckPlan(unittest.TestCase):
    def test_nesting_renames_emitted(self) -> None:
        with TemporaryDirectory() as td:
            project = build_aldus_shaped_deck(Path(td))
            plan = build_plan(project)
            self.assertEqual(len(plan.documents), 1)
            doc = plan.documents[0]
            self.assertEqual(doc.slug, "series-a-deck")
            rename_pairs = {
                (r.source.name, str(r.target.relative_to(plan.project_dir)))
                for r in doc.renames
            }
            self.assertIn(
                ("series-a-deck.1", "series-a-deck/series-a-deck.1"),
                rename_pairs,
            )
            self.assertIn(
                ("series-a-deck.2", "series-a-deck/series-a-deck.2"),
                rename_pairs,
            )

    def test_critic_siblings_renamed_alongside(self) -> None:
        with TemporaryDirectory() as td:
            project = build_aldus_shaped_deck(Path(td))
            plan = build_plan(project)
            doc = plan.documents[0]
            targets = {
                str(r.target.relative_to(plan.project_dir))
                for r in doc.renames
            }
            self.assertIn(
                "series-a-deck/series-a-deck.1.review", targets
            )
            self.assertIn(
                "series-a-deck/series-a-deck.2.design", targets
            )

    def test_no_body_rename_for_deck_md(self) -> None:
        """deck.md is retained — no rename targets a deck.md source."""
        with TemporaryDirectory() as td:
            project = build_aldus_shaped_deck(Path(td))
            plan = build_plan(project)
            doc = plan.documents[0]
            body_renames = [
                r for r in doc.renames if r.source.name == "deck.md"
            ]
            self.assertEqual(body_renames, [])
            # And the retained-body decision is surfaced as a note.
            self.assertTrue(
                any("deck.md" in note and "retained" in note
                    for note in doc.notes),
                f"expected a retained-body note; got {doc.notes}",
            )

    def test_thread_root_anvil_json_merged(self) -> None:
        with TemporaryDirectory() as td:
            project = build_aldus_shaped_deck(Path(td))
            plan = build_plan(project)
            doc = plan.documents[0]
            self.assertIsNotNone(doc.brief_merge)
            self.assertEqual(doc.brief_merge.max_iterations, 6)
            self.assertTrue(doc.brief_merge.iteration_cap_rationale)
            self.assertEqual(
                doc.anvil_json_to_delete,
                plan.project_dir / "series-a-deck" / ".anvil.json",
            )

    def test_post_283_mixed_grammar_dispatch(self) -> None:
        """A flat deck thread in a BRIEF-bearing project still gets the
        nesting plan (per-thread dispatch under POST_283)."""
        with TemporaryDirectory() as td:
            project = build_aldus_shaped_deck(
                Path(td), with_project_brief=True
            )
            plan = build_plan(project)
            doc = next(
                d for d in plan.documents if d.slug == "series-a-deck"
            )
            targets = {
                str(r.target.relative_to(plan.project_dir))
                for r in doc.renames
            }
            self.assertIn(
                "series-a-deck/series-a-deck.1", targets
            )


class TestMixedProjectPlan(unittest.TestCase):
    def test_one_document_plan_per_thread(self) -> None:
        with TemporaryDirectory() as td:
            project = build_mixed_memo_deck_proposal(Path(td))
            plan = build_plan(project)
            slugs = sorted(d.slug for d in plan.documents)
            self.assertEqual(
                slugs, ["aldus", "gossamer-lan", "series-a-deck"]
            )

    def test_memo_thread_gets_body_rename(self) -> None:
        with TemporaryDirectory() as td:
            project = build_mixed_memo_deck_proposal(Path(td))
            plan = build_plan(project)
            doc = next(d for d in plan.documents if d.slug == "aldus")
            targets = {
                str(r.target.relative_to(plan.project_dir))
                for r in doc.renames
            }
            self.assertIn("aldus/aldus.1", targets)
            self.assertIn("aldus/aldus.1/aldus.md", targets)

    def test_proposal_thread_nested_without_body_rename(self) -> None:
        with TemporaryDirectory() as td:
            project = build_mixed_memo_deck_proposal(Path(td))
            plan = build_plan(project)
            doc = next(
                d for d in plan.documents if d.slug == "gossamer-lan"
            )
            targets = {
                str(r.target.relative_to(plan.project_dir))
                for r in doc.renames
            }
            self.assertIn("gossamer-lan/gossamer-lan.1", targets)
            self.assertIn("gossamer-lan/gossamer-lan.1.review", targets)
            self.assertIn("gossamer-lan/gossamer-lan.1.audit", targets)
            tex_renames = [
                r for r in doc.renames if r.source.name == "proposal.tex"
            ]
            self.assertEqual(tex_renames, [])

    def test_default_max_iterations_not_carried_without_rationale(
        self,
    ) -> None:
        """A bare max_iterations without rationale would be rejected by
        the strict BRIEF parser — the planner drops it."""
        extract = plan_mod._extract_iteration_cap
        self.assertEqual(extract({"max_iterations": 4}), (None, None))
        self.assertEqual(
            extract({"max_iterations": 6, "iteration_cap_rationale": "  "}),
            (None, None),
        )
        self.assertEqual(
            extract({"max_iterations": 3, "iteration_cap_rationale": "x"}),
            (None, None),
        )
        self.assertEqual(
            extract({"max_iterations": 6, "iteration_cap_rationale": "ok"}),
            (6, "ok"),
        )


if __name__ == "__main__":
    unittest.main()
