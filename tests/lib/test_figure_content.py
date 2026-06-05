"""Tests for ``anvil/lib/figure_content.py`` (Epic #328 Phase 4, issue #340).

Covers the full acceptance criteria from the #340 issue body:

1. Three-axis scoring rubric (``on_brand``, ``caption_grounding``,
   ``adjacency_grounding``) — schema validity, rubric_id, max_total=15.
2. Fixture with on-brand figure → no on-brand finding; off-brand figure
   (tab10 palette) → on-brand finding emitted.
3. Fixture with accurate caption → no caption finding; misleading caption
   (figure shows X, caption says Y) → caption finding emitted.
4. Fixture with figure supporting adjacent prose → no adjacency finding;
   non-sequitur figure → adjacency finding + ``propose_removal`` suggestion.
5. Cache test: identical PNG content produces no second VLM call.
6. Critical-flag test: caption-vs-figure contradiction fires
   ``critical_figure_misrepresents_claim`` and forces ``Verdict.BLOCK``.
7. Auto-discovery round-trip via ``aggregate`` (mirror Phase 2's pattern).
8. CLI smoke (``python -m anvil.lib.figure_content <fixture_dir>
   [--write-review]``).
9. Graceful-degrade when ``pdftoppm`` is unavailable.

**VLM calls are MOCKED throughout**. The ``callback=`` injection point on
:class:`anvil.lib.vision.VisionCritic` (and propagated through
:func:`anvil.lib.figure_content.critique_version_dir`) bypasses Anthropic
entirely.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest


# Repo-root sys.path injection — this file is two levels deep from the repo
# root (tests/lib/), matching the precedent in ``tests/lib/test_vision.py``.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from anvil.lib.critics import (  # noqa: E402
    aggregate,
    discover_critics,
    load_review,
)
from anvil.lib.figure_content import (  # noqa: E402
    CRITIC_ID,
    CRITICAL_FIGURE_MISREPRESENTS_CLAIM,
    DEFAULT_VLM_BUDGET_PER_FIGURE,
    DIM_ADJACENCY_GROUNDING,
    DIM_CAPTION_GROUNDING,
    DIM_ON_BRAND,
    RUBRIC_ID,
    SIBLING_SUFFIX,
    FigureContentResult,
    FigureRecord,
    FigureVLMCache,
    build_figure_content_prompt,
    check_pdftoppm_available,
    critique_version_dir,
    default_figure_content_rubric,
    discover_figures,
    main,
    write_review_dir,
)
from anvil.lib.review_schema import (  # noqa: E402
    Finding,
    Kind,
    Review,
    Score,
    Verdict,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


# A 1x1 PNG with a single navy pixel (decoded base64 of the smallest valid
# PNG). Tests use distinct bytes per figure to get distinct content hashes.
_PNG_NAVY_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x00\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Distinct bytes for off-brand fixture; bytes differ so SHA hash differs,
# guaranteeing cache miss on second figure.
_PNG_OFFBRAND_1x1 = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50 + b"IEND\xaeB`\x82"


def _make_version_dir(tmpdir: Path, *, slug: str = "primary-memo") -> Path:
    """Build a minimal version dir: ``<tmpdir>/<slug>/<slug>.1/``."""
    project = tmpdir / "project"
    project.mkdir(exist_ok=True)
    thread = project / slug
    thread.mkdir()
    version_dir = thread / f"{slug}.1"
    version_dir.mkdir()
    return version_dir


def _write_figures_dir_png(
    version_dir: Path, name: str, data: bytes = _PNG_NAVY_1x1
) -> Path:
    """Write a PNG under ``<version_dir>/figures/<name>``."""
    figures_dir = version_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    out = figures_dir / name
    out.write_bytes(data)
    return out


def _clean_payload(
    *, on_brand: int = 5, caption: int = 5, adjacency: int = 5
) -> dict:
    """A VLM payload with all three rubric rows scored clean."""
    return {
        "scores": [
            {
                "dimension": DIM_ON_BRAND,
                "score": on_brand,
                "critical": False,
                "justification": "Brand palette throughout.",
                "fix": None,
            },
            {
                "dimension": DIM_CAPTION_GROUNDING,
                "score": caption,
                "critical": False,
                "justification": "Caption matches figure.",
                "fix": None,
            },
            {
                "dimension": DIM_ADJACENCY_GROUNDING,
                "score": adjacency,
                "critical": False,
                "justification": "Figure supports adjacent prose.",
                "fix": None,
            },
        ],
        "findings": [],
        "critical_flags": [],
    }


# ---------------------------------------------------------------------------
# Rubric + constants
# ---------------------------------------------------------------------------


class TestRubric(unittest.TestCase):
    def test_rubric_has_three_dimensions_max_15(self):
        rubric = default_figure_content_rubric()
        self.assertEqual(len(rubric.dimensions), 3)
        self.assertEqual(rubric.max_total(), 15)
        self.assertEqual(rubric.rubric_id, RUBRIC_ID)
        names = [d.name for d in rubric.dimensions]
        self.assertEqual(
            names, [DIM_ON_BRAND, DIM_CAPTION_GROUNDING, DIM_ADJACENCY_GROUNDING]
        )

    def test_each_dimension_is_out_of_5(self):
        rubric = default_figure_content_rubric()
        for d in rubric.dimensions:
            self.assertEqual(d.max, 5)

    def test_critic_id_is_pinned(self):
        self.assertEqual(CRITIC_ID, "figure-content")

    def test_sibling_suffix_matches_critic_id(self):
        # The auto-discovery contract requires the sibling tag to be a
        # single segment (no dots); the trailing dir is then
        # <version_dir>.<SIBLING_SUFFIX>/.
        self.assertEqual(SIBLING_SUFFIX, "figure-content")
        self.assertNotIn(".", SIBLING_SUFFIX)

    def test_critical_flag_constant_is_pinned(self):
        self.assertEqual(
            CRITICAL_FIGURE_MISREPRESENTS_CLAIM,
            "critical_figure_misrepresents_claim",
        )

    def test_default_vlm_budget_is_one(self):
        # The issue body documents the default as "1 VLM call per figure
        # per run". Lock-in test for the conservative cost cap.
        self.assertEqual(DEFAULT_VLM_BUDGET_PER_FIGURE, 1)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


class TestPrompt(unittest.TestCase):
    def test_prompt_mentions_every_rubric_dimension(self):
        prompt = build_figure_content_prompt(
            caption=None, adjacency=None, figure_label="page-1"
        )
        for dim in (DIM_ON_BRAND, DIM_CAPTION_GROUNDING, DIM_ADJACENCY_GROUNDING):
            self.assertIn(dim, prompt)

    def test_prompt_names_critical_flag_taxonomy(self):
        prompt = build_figure_content_prompt(
            caption=None, adjacency=None, figure_label="page-1"
        )
        self.assertIn(CRITICAL_FIGURE_MISREPRESENTS_CLAIM, prompt)

    def test_prompt_includes_caption_when_provided(self):
        prompt = build_figure_content_prompt(
            caption="Revenue tripled in Q3 2024.",
            adjacency=None,
            figure_label="page-1",
        )
        self.assertIn("Revenue tripled in Q3 2024.", prompt)

    def test_prompt_includes_adjacency_when_provided(self):
        prompt = build_figure_content_prompt(
            caption=None,
            adjacency="The chart below demonstrates the inflection point.",
            figure_label="page-1",
        )
        self.assertIn("inflection point", prompt)

    def test_prompt_omits_caption_section_when_none(self):
        prompt = build_figure_content_prompt(
            caption=None, adjacency=None, figure_label="page-1"
        )
        self.assertNotIn("Caption text:", prompt)

    def test_prompt_lists_anvil_navy_in_palette(self):
        # The on-brand scoring axis requires the VLM to see the literal
        # hex values; lock in that ANVIL_NAVY appears in the prompt.
        from anvil.lib.figures.palette import ANVIL_NAVY

        prompt = build_figure_content_prompt(
            caption=None, adjacency=None, figure_label="page-1"
        )
        self.assertIn(ANVIL_NAVY, prompt)


# ---------------------------------------------------------------------------
# Figure discovery
# ---------------------------------------------------------------------------


class TestDiscovery(unittest.TestCase):
    def test_no_figures_returns_empty_records_and_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            records, rendered, reasons = discover_figures(version_dir)
            self.assertEqual(records, [])
            # When no PDF and no figures dir, rendered_artifact is the
            # placeholder so the Review schema still validates.
            self.assertEqual(rendered, "(none)")

    def test_figures_dir_pngs_are_discovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "hero.png", _PNG_NAVY_1x1)
            _write_figures_dir_png(version_dir, "chart.png", _PNG_OFFBRAND_1x1)
            records, rendered, _ = discover_figures(version_dir)
            self.assertEqual(len(records), 2)
            self.assertEqual(rendered, "figures/")
            labels = sorted(r.label for r in records)
            self.assertEqual(
                labels, ["figures/chart.png", "figures/hero.png"]
            )
            # Distinct hashes for distinct bytes.
            hashes = [r.content_hash for r in records]
            self.assertEqual(len(set(hashes)), 2)
            # All records come from figures-dir.
            for r in records:
                self.assertEqual(r.source, "figures-dir")

    def test_svg_sources_are_skipped_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            figures_dir = version_dir / "figures"
            figures_dir.mkdir()
            (figures_dir / "diagram.svg").write_text(
                "<svg><rect/></svg>", encoding="utf-8"
            )
            records, _, reasons = discover_figures(version_dir)
            self.assertEqual(records, [])
            # Top-level reason documents the SVG skip.
            self.assertTrue(any("SVG" in r for r in reasons))

    def test_pdftoppm_unavailable_graceful_degrades(self):
        """When pdftoppm is missing, PDF extraction is skipped with a reason
        and figures/ dir discovery still runs."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            # Drop a fake PDF in the version dir.
            (version_dir / f"{version_dir.parent.name}.pdf").write_bytes(
                b"%PDF-1.4 fake"
            )
            _write_figures_dir_png(version_dir, "hero.png", _PNG_NAVY_1x1)

            with mock.patch(
                "anvil.lib.figure_content.check_pdftoppm_available",
                return_value=False,
            ):
                records, rendered, reasons = discover_figures(version_dir)
            # PDF page extraction skipped.
            self.assertFalse(
                any(r.source == "pdf-page" for r in records),
                "expected no pdf-page records when pdftoppm unavailable",
            )
            # figures/ dir discovery still produces records.
            self.assertTrue(
                any(r.source == "figures-dir" for r in records),
                "figures/ dir discovery must still run",
            )
            # Top-level reason documents the graceful-degrade.
            self.assertTrue(any("pdftoppm" in r for r in reasons))


# ---------------------------------------------------------------------------
# AC2: on-brand axis
# ---------------------------------------------------------------------------


class TestOnBrandAxis(unittest.TestCase):
    def test_on_brand_figure_produces_no_on_brand_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "hero.png", _PNG_NAVY_1x1)
            # VLM scores on_brand clean (5/5).
            callback = mock.MagicMock(return_value=_clean_payload())
            result = critique_version_dir(version_dir, callback=callback)
            on_brand_findings = [
                f for f in result.findings if f.dimension == DIM_ON_BRAND
            ]
            self.assertEqual(on_brand_findings, [])

    def test_off_brand_figure_emits_on_brand_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "chart.png", _PNG_OFFBRAND_1x1)
            # VLM scores on_brand low (1/5) and emits a narrative finding.
            payload = _clean_payload(on_brand=1)
            payload["findings"] = [
                {
                    "severity": "major",
                    "dimension": DIM_ON_BRAND,
                    "rationale": "Default tab10 palette; navy is absent.",
                    "suggested_fix": "Apply palette.apply() in the figure script.",
                }
            ]
            callback = mock.MagicMock(return_value=payload)
            result = critique_version_dir(version_dir, callback=callback)
            on_brand_findings = [
                f for f in result.findings if f.dimension == DIM_ON_BRAND
            ]
            self.assertGreaterEqual(len(on_brand_findings), 1)
            self.assertEqual(on_brand_findings[0].severity, "major")


# ---------------------------------------------------------------------------
# AC3: caption-grounding axis
# ---------------------------------------------------------------------------


class TestCaptionGroundingAxis(unittest.TestCase):
    def test_accurate_caption_produces_no_caption_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "hero.png", _PNG_NAVY_1x1)
            callback = mock.MagicMock(return_value=_clean_payload())
            result = critique_version_dir(
                version_dir,
                callback=callback,
                figure_captions={
                    "figures/hero.png": "Quarterly revenue growth, 2022-2024."
                },
            )
            caption_findings = [
                f for f in result.findings if f.dimension == DIM_CAPTION_GROUNDING
            ]
            self.assertEqual(caption_findings, [])

    def test_misleading_caption_emits_caption_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "chart.png", _PNG_OFFBRAND_1x1)
            payload = _clean_payload(caption=1)
            payload["findings"] = [
                {
                    "severity": "major",
                    "dimension": DIM_CAPTION_GROUNDING,
                    "rationale": (
                        "Caption claims revenue tripled, figure shows flat line."
                    ),
                    "suggested_fix": "Rewrite caption to match figure content.",
                }
            ]
            callback = mock.MagicMock(return_value=payload)
            result = critique_version_dir(
                version_dir,
                callback=callback,
                figure_captions={
                    "figures/chart.png": "Revenue tripled in Q3 2024."
                },
            )
            caption_findings = [
                f for f in result.findings if f.dimension == DIM_CAPTION_GROUNDING
            ]
            self.assertGreaterEqual(len(caption_findings), 1)


# ---------------------------------------------------------------------------
# AC4: adjacency-grounding axis
# ---------------------------------------------------------------------------


class TestAdjacencyGroundingAxis(unittest.TestCase):
    def test_supporting_figure_produces_no_adjacency_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "hero.png", _PNG_NAVY_1x1)
            callback = mock.MagicMock(return_value=_clean_payload())
            result = critique_version_dir(
                version_dir,
                callback=callback,
                figure_adjacency={
                    "figures/hero.png": (
                        "The chart below demonstrates quarterly growth."
                    )
                },
            )
            adj_findings = [
                f
                for f in result.findings
                if f.dimension == DIM_ADJACENCY_GROUNDING
            ]
            self.assertEqual(adj_findings, [])

    def test_non_sequitur_figure_emits_adjacency_finding_with_removal_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "chart.png", _PNG_OFFBRAND_1x1)
            payload = _clean_payload(adjacency=0)
            payload["findings"] = [
                {
                    "severity": "major",
                    "dimension": DIM_ADJACENCY_GROUNDING,
                    "rationale": (
                        "Figure is a stock photo; adjacent prose discusses "
                        "revenue."
                    ),
                    "suggested_fix": "Drop the figure or replace with a chart.",
                }
            ]
            callback = mock.MagicMock(return_value=payload)
            result = critique_version_dir(
                version_dir,
                callback=callback,
                figure_adjacency={
                    "figures/chart.png": "Revenue grew 30% in Q3."
                },
            )
            adj_findings = [
                f
                for f in result.findings
                if f.dimension == DIM_ADJACENCY_GROUNDING
            ]
            self.assertGreaterEqual(len(adj_findings), 1)
            # The suggested_fix mentions "drop" or "replace" — the free-form
            # text per the no-schema-delta contract.
            fix_lower = adj_findings[0].suggested_fix.lower()
            self.assertTrue(
                "drop" in fix_lower or "replace" in fix_lower,
                f"adjacency finding suggested_fix should mention drop/replace, "
                f"got: {adj_findings[0].suggested_fix!r}",
            )


# ---------------------------------------------------------------------------
# AC5: VLM cache (content-hash deduplication)
# ---------------------------------------------------------------------------


class TestVLMCache(unittest.TestCase):
    def test_identical_png_content_produces_no_second_vlm_call(self):
        """The content-hash cache must deduplicate identical bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            # Two distinct files with identical bytes — same content_hash.
            _write_figures_dir_png(version_dir, "hero-a.png", _PNG_NAVY_1x1)
            _write_figures_dir_png(version_dir, "hero-b.png", _PNG_NAVY_1x1)
            callback = mock.MagicMock(return_value=_clean_payload())
            result = critique_version_dir(version_dir, callback=callback)
            # Two figures discovered, but only one VLM call (the second
            # hits the cache).
            self.assertEqual(len(result.figures), 2)
            self.assertEqual(callback.call_count, 1)
            self.assertEqual(result.vlm_calls, 1)
            self.assertEqual(result.cache_hits, 1)

    def test_distinct_content_triggers_distinct_vlm_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "a.png", _PNG_NAVY_1x1)
            _write_figures_dir_png(version_dir, "b.png", _PNG_OFFBRAND_1x1)
            callback = mock.MagicMock(return_value=_clean_payload())
            result = critique_version_dir(version_dir, callback=callback)
            self.assertEqual(callback.call_count, 2)
            self.assertEqual(result.vlm_calls, 2)
            self.assertEqual(result.cache_hits, 0)

    def test_external_cache_lives_across_calls(self):
        """A caller-provided cache persists across critique_version_dir calls."""
        cache = FigureVLMCache()
        callback = mock.MagicMock(return_value=_clean_payload())
        with tempfile.TemporaryDirectory() as tmp:
            v1 = _make_version_dir(Path(tmp), slug="memo-a")
            v2 = _make_version_dir(Path(tmp), slug="memo-b")
            _write_figures_dir_png(v1, "shared.png", _PNG_NAVY_1x1)
            _write_figures_dir_png(v2, "shared.png", _PNG_NAVY_1x1)
            critique_version_dir(v1, callback=callback, cache=cache)
            critique_version_dir(v2, callback=callback, cache=cache)
            # Identical bytes across two version dirs → one VLM call total.
            self.assertEqual(callback.call_count, 1)

    def test_cache_len_and_contains(self):
        cache = FigureVLMCache()
        self.assertEqual(len(cache), 0)
        self.assertFalse("deadbeef" in cache)
        cache.put("deadbeef", {"scores": []})
        self.assertEqual(len(cache), 1)
        self.assertTrue("deadbeef" in cache)
        self.assertEqual(cache.get("deadbeef"), {"scores": []})
        self.assertIsNone(cache.get("missing"))


# ---------------------------------------------------------------------------
# AC6: critical flag — caption-vs-figure contradiction
# ---------------------------------------------------------------------------


class TestCriticalFlag(unittest.TestCase):
    def test_critical_flag_fires_on_contradiction(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "chart.png", _PNG_OFFBRAND_1x1)
            payload = _clean_payload(caption=0)
            payload["critical_flags"] = [
                {
                    "type": CRITICAL_FIGURE_MISREPRESENTS_CLAIM,
                    "justification": (
                        "Caption claims revenue tripled in Q3; chart shows "
                        "flat line. Direct contradiction."
                    ),
                }
            ]
            callback = mock.MagicMock(return_value=payload)
            result = critique_version_dir(
                version_dir,
                callback=callback,
                figure_captions={
                    "figures/chart.png": "Revenue tripled in Q3 2024."
                },
            )
            self.assertEqual(len(result.critical_flags), 1)
            self.assertEqual(
                result.critical_flags[0].type,
                CRITICAL_FIGURE_MISREPRESENTS_CLAIM,
            )
            # Critical flag forces Verdict.BLOCK at aggregation.
            review = result.to_review()
            from anvil.lib.critics import aggregate, compute_verdict

            agg = aggregate([review])
            self.assertEqual(compute_verdict(agg), Verdict.BLOCK)


# ---------------------------------------------------------------------------
# Review shape / schema compliance
# ---------------------------------------------------------------------------


class TestReviewShape(unittest.TestCase):
    def test_to_review_emits_kind_vision_with_rendered_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "hero.png", _PNG_NAVY_1x1)
            callback = mock.MagicMock(return_value=_clean_payload())
            result = critique_version_dir(version_dir, callback=callback)
            review = result.to_review()
            self.assertEqual(review.kind, Kind.VISION)
            # rendered_artifact must be set per the schema validator at
            # review_schema.py:371.
            self.assertIsNotNone(review.rendered_artifact)
            self.assertEqual(review.rendered_artifact, "figures/")
            self.assertEqual(review.critic_id, CRITIC_ID)
            self.assertEqual(review.rubric, RUBRIC_ID)
            # Three rubric rows, rolled-up scores.
            self.assertEqual(len(review.scores), 3)
            dims = {s.dimension for s in review.scores}
            self.assertEqual(
                dims,
                {DIM_ON_BRAND, DIM_CAPTION_GROUNDING, DIM_ADJACENCY_GROUNDING},
            )

    def test_review_round_trips_through_model_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "hero.png", _PNG_NAVY_1x1)
            callback = mock.MagicMock(return_value=_clean_payload())
            result = critique_version_dir(version_dir, callback=callback)
            review = result.to_review()
            text = review.model_dump_json()
            parsed = Review.model_validate(json.loads(text))
            self.assertEqual(parsed.kind, Kind.VISION)
            self.assertEqual(parsed.rendered_artifact, "figures/")

    def test_empty_critique_review_has_null_scored_rubric(self):
        """When no figures are critiqued, each rubric row is null-scored."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            # No figures, no PDF.
            result = critique_version_dir(
                version_dir, callback=mock.MagicMock()
            )
            review = result.to_review()
            self.assertEqual(len(review.scores), 3)
            for s in review.scores:
                self.assertIsNone(s.score)
            self.assertEqual(review.total, 0)

    def test_schema_delta_did_not_creep(self):
        """The Phase 4 settle holds: no action/target_anchor/proposed_content
        fields on Finding. Lock-in test mirroring the Phase 2 / Phase 3
        regression guards."""
        from anvil.lib.review_schema import Finding

        forbidden = {"action", "target_anchor", "proposed_content"}
        actual_fields = set(Finding.model_fields.keys())
        leaked = forbidden & actual_fields
        self.assertEqual(
            leaked,
            set(),
            f"Phase 4 must not introduce a schema delta on Finding; leaked: "
            f"{leaked}",
        )


# ---------------------------------------------------------------------------
# AC7: auto-discovery round-trip via aggregate
# ---------------------------------------------------------------------------


class TestAutoDiscovery(unittest.TestCase):
    def test_sibling_dir_discovered_and_aggregated(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "hero.png", _PNG_NAVY_1x1)
            callback = mock.MagicMock(return_value=_clean_payload())
            result = critique_version_dir(version_dir, callback=callback)
            out = write_review_dir(version_dir, result)
            # The sibling dir exists with the expected name.
            sibling = version_dir.parent / f"{version_dir.name}.{SIBLING_SUFFIX}"
            self.assertTrue(sibling.is_dir())
            self.assertEqual(out, sibling / "_review.json")
            self.assertTrue(out.is_file())

            # Auto-discovery picks it up.
            siblings = discover_critics(version_dir)
            self.assertIn(sibling, siblings)

            # load_review parses it cleanly.
            review = load_review(sibling)
            self.assertEqual(review.kind, Kind.VISION)
            self.assertEqual(review.critic_id, CRITIC_ID)

            # aggregate merges without raising.
            agg = aggregate([review])
            self.assertEqual(agg.critic_ids, [CRITIC_ID])

    def test_aggregate_with_judgment_sibling_short_circuits_on_critical(self):
        """A figure-content review with a critical flag, aggregated alongside
        a clean judgment review, forces Verdict.BLOCK."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "chart.png", _PNG_OFFBRAND_1x1)
            payload = _clean_payload()
            payload["critical_flags"] = [
                {
                    "type": CRITICAL_FIGURE_MISREPRESENTS_CLAIM,
                    "justification": "Direct contradiction.",
                }
            ]
            callback = mock.MagicMock(return_value=payload)
            result = critique_version_dir(version_dir, callback=callback)
            fc_review = result.to_review()

            # Sibling judgment review with full score and no critical flags.
            judgment_review = Review(
                schema_version="1",
                kind=Kind.JUDGMENT,
                version_dir=version_dir.name,
                critic_id="review",
                scores=[
                    Score(
                        dimension="some_dim",
                        score=5,
                        max=5,
                        justification="clean",
                    )
                ],
                threshold=5,
            )
            from anvil.lib.critics import aggregate, compute_verdict

            agg = aggregate([judgment_review, fc_review])
            self.assertEqual(compute_verdict(agg), Verdict.BLOCK)


# ---------------------------------------------------------------------------
# Scores aggregate across multiple figures
# ---------------------------------------------------------------------------


class TestScoreAggregation(unittest.TestCase):
    def test_per_figure_scores_average_to_rubric_rolled_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "a.png", _PNG_NAVY_1x1)
            _write_figures_dir_png(version_dir, "b.png", _PNG_OFFBRAND_1x1)
            # First figure scores 5 / 5 / 5; second scores 1 / 3 / 5.
            payloads = [
                _clean_payload(),
                _clean_payload(on_brand=1, caption=3, adjacency=5),
            ]
            callback = mock.MagicMock(side_effect=payloads)
            result = critique_version_dir(version_dir, callback=callback)
            review = result.to_review()
            scores_by_dim = {s.dimension: s.score for s in review.scores}
            # Means: (5+1)/2=3 ; (5+3)/2=4 ; (5+5)/2=5.
            self.assertEqual(scores_by_dim[DIM_ON_BRAND], 3)
            self.assertEqual(scores_by_dim[DIM_CAPTION_GROUNDING], 4)
            self.assertEqual(scores_by_dim[DIM_ADJACENCY_GROUNDING], 5)
            self.assertEqual(review.total, 12)


# ---------------------------------------------------------------------------
# AC8: CLI smoke
# ---------------------------------------------------------------------------


class TestCLI(unittest.TestCase):
    def test_cli_exit_2_on_missing_version_dir(self):
        rc = main(["/path/does/not/exist"])
        self.assertEqual(rc, 2)

    def test_cli_exit_0_on_clean_pass(self, capsys=None):
        """When no figures are present, the critic runs clean (no findings,
        no critical flags) — exit code 0."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            # No figures, no PDF — clean pass.
            rc = main([str(version_dir)])
            self.assertEqual(rc, 0)

    def test_cli_write_review_creates_sibling(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            rc = main([str(version_dir), "--write-review"])
            self.assertEqual(rc, 0)
            sibling = (
                version_dir.parent / f"{version_dir.name}.{SIBLING_SUFFIX}"
            )
            self.assertTrue(sibling.is_dir())
            self.assertTrue((sibling / "_review.json").is_file())


# ---------------------------------------------------------------------------
# Top-level reasons (graceful-degrade signals)
# ---------------------------------------------------------------------------


class TestReasons(unittest.TestCase):
    def test_empty_version_dir_produces_no_figures_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            callback = mock.MagicMock()
            result = critique_version_dir(version_dir, callback=callback)
            self.assertTrue(
                any("no figures" in r.lower() for r in result.reasons)
            )
            callback.assert_not_called()

    def test_to_json_includes_all_top_level_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "hero.png", _PNG_NAVY_1x1)
            callback = mock.MagicMock(return_value=_clean_payload())
            result = critique_version_dir(version_dir, callback=callback)
            j = result.to_json()
            for key in (
                "critic",
                "version_dir",
                "rendered_artifact",
                "figures",
                "findings",
                "critical_flags",
                "reasons",
                "vlm_calls",
                "cache_hits",
                "pass",
            ):
                self.assertIn(key, j)
            self.assertEqual(j["critic"], CRITIC_ID)


# ---------------------------------------------------------------------------
# pdftoppm preflight (mirrors check_*_available family)
# ---------------------------------------------------------------------------


class TestPdftoppmAvailable(unittest.TestCase):
    def test_pdftoppm_check_returns_bool(self):
        result = check_pdftoppm_available()
        self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# Doc-coverage (mirrors Phase 2 / Phase 3 doc-coverage suites)
# ---------------------------------------------------------------------------


class TestCommandDocs(unittest.TestCase):
    """Lock-in tests that both command docs ship with the expected
    invariants (CLI shape, sibling-dir name, critical-flag type)."""

    def _read(self, rel: str) -> str:
        return (_REPO_ROOT / rel).read_text(encoding="utf-8")

    def test_memo_command_doc_exists(self):
        text = self._read(
            "anvil/skills/memo/commands/memo-figure-content.md"
        )
        # CLI shape per the coordination contract.
        self.assertIn("python -m anvil.lib.figure_content", text)
        # Sibling-dir convention.
        self.assertIn(".figure-content/", text)
        # Critical-flag name (load-bearing for the verdict shift).
        self.assertIn(CRITICAL_FIGURE_MISREPRESENTS_CLAIM, text)
        # Frontmatter present (name / description).
        self.assertIn("name: memo-figure-content", text)

    def test_report_command_doc_exists(self):
        text = self._read(
            "anvil/skills/report/commands/report-figure-content.md"
        )
        self.assertIn("python -m anvil.lib.figure_content", text)
        self.assertIn(".figure-content/", text)
        self.assertIn(CRITICAL_FIGURE_MISREPRESENTS_CLAIM, text)
        self.assertIn("name: report-figure-content", text)


# ---------------------------------------------------------------------------
# VLM budget cap (no second call beyond budget)
# ---------------------------------------------------------------------------


class TestVLMBudget(unittest.TestCase):
    def test_budget_zero_skips_vlm_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_figures_dir_png(version_dir, "a.png", _PNG_NAVY_1x1)
            callback = mock.MagicMock(return_value=_clean_payload())
            result = critique_version_dir(
                version_dir,
                callback=callback,
                vlm_budget_per_figure=0,
            )
            # Budget exhausted → no VLM call.
            callback.assert_not_called()
            self.assertTrue(
                any("budget" in r.lower() for r in result.reasons)
            )


if __name__ == "__main__":
    unittest.main()
