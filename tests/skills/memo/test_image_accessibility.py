"""Tests for ``anvil/skills/memo/lib/image_accessibility.py`` (Epic #328 Phase 5).

Per-skill test filename convention (#58): this file is named
``test_image_accessibility.py`` and lives under ``tests/skills/memo/``.

Covers every acceptance criterion documented on issue #341:

1. Fixture with valid alt → no finding.
2. Fixture with missing alt → VLM-mocked, finding emitted with generated
   alt-text in `suggested_fix` text.
3. Fixture with ``alt="image"`` placeholder → inadequate-alt finding.
4. Fixture with sub-10-char alt → inadequate-alt finding.
5. Fixture with broken path (no nearby match) → `propose_removal` finding.
6. Fixture with broken path (nearby match) → `propose_edit` finding with
   closest-match suggestion.
7. VLM cache test: identical image content produces no second VLM call.
8. Auto-discovery: ``<version_dir>.image-accessibility/`` sibling is
   recognized by ``anvil/lib/critics.py::discover_critics``.

VLM calls are MOCKED throughout — no network access.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


# Repo-root sys.path injection — same pattern as test_hyperlink_resolver.py.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from anvil.lib.critics import (  # noqa: E402
    aggregate,
    discover_critics,
    load_review,
)
from anvil.lib.review_schema import (  # noqa: E402
    Kind,
    Review,
)
from anvil.skills.memo.lib.image_accessibility import (  # noqa: E402
    CRITIC_ID,
    DIM_IMAGE_ACCESSIBILITY,
    IMAGE_ACCESSIBILITY_SUFFIX,
    INADEQUATE_ALT_MIN_LENGTH,
    RULE_BROKEN_PATH,
    RULE_INADEQUATE_ALT,
    RULE_MISSING_ALT,
    SEVERITY_BROKEN_PATH,
    SEVERITY_INADEQUATE_ALT,
    SEVERITY_MISSING_ALT,
    AccessibilityFinding,
    ImageAccessibilityResult,
    _cli_main,
    clear_vlm_cache,
    generate_alt_text,
    scan,
    scan_version_dir,
    write_review_dir,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


# A tiny but valid PNG file (1x1 transparent pixel, the smallest possible
# valid PNG by signature). Used as a deterministic stand-in for an image
# the critic can read for content-hashing without invoking real VLM.
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02"
    b"\xfe\xa3\xab\xa6\xa3\x00\x00\x00\x00IEND\xaeB`\x82"
)

# A second tiny PNG with different content so two distinct files
# produce distinct content hashes.
_TINY_PNG_2 = _TINY_PNG[:-12] + b"\xff" + _TINY_PNG[-11:]


def _make_version_dir(tmp_root: Path, slug: str = "memo", n: int = 1) -> Path:
    """Build ``<tmp>/<slug>/<slug>.{n}/`` and return the version dir.

    Mirrors the post-#295 contract (body filename echoes thread slug).
    """
    thread = tmp_root / slug
    version_dir = thread / f"{slug}.{n}"
    version_dir.mkdir(parents=True)
    return version_dir


def _write_body(version_dir: Path, text: str) -> Path:
    """Write the body markdown (slug-echo per #295)."""
    body = version_dir / f"{version_dir.parent.name}.md"
    body.write_text(text, encoding="utf-8")
    return body


def _write_png(path: Path, content: bytes = _TINY_PNG) -> Path:
    """Write a tiny PNG to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# ---------------------------------------------------------------------------
# Module-surface guards
# ---------------------------------------------------------------------------


class TestModuleSurface(unittest.TestCase):
    def test_critic_id_is_image_accessibility(self):
        self.assertEqual(CRITIC_ID, "image-accessibility")

    def test_sibling_suffix_matches_critic_id(self):
        self.assertEqual(IMAGE_ACCESSIBILITY_SUFFIX, "image-accessibility")

    def test_dim_constant(self):
        self.assertEqual(DIM_IMAGE_ACCESSIBILITY, "image_accessibility")

    def test_severity_ladder_per_issue(self):
        """Severity mapping mirrors the issue body table."""
        self.assertEqual(SEVERITY_MISSING_ALT, "major")
        self.assertEqual(SEVERITY_INADEQUATE_ALT, "minor")
        self.assertEqual(SEVERITY_BROKEN_PATH, "major")

    def test_inadequate_threshold_is_ten(self):
        """Sub-10-char rule per the issue body."""
        self.assertEqual(INADEQUATE_ALT_MIN_LENGTH, 10)

    def test_rule_names_present(self):
        """Three distinct suppression-directive rule names are exposed."""
        self.assertEqual(
            RULE_MISSING_ALT, "memo_image_accessibility_missing_alt"
        )
        self.assertEqual(
            RULE_INADEQUATE_ALT, "memo_image_accessibility_inadequate_alt"
        )
        self.assertEqual(
            RULE_BROKEN_PATH, "memo_image_accessibility_broken_path"
        )


# ---------------------------------------------------------------------------
# AC1: Valid alt → no finding
# ---------------------------------------------------------------------------


class TestValidAltProducesNoFinding(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_markdown_descriptive_alt_passes(self):
        """A descriptive alt-text on ``![alt](path)`` produces zero findings."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "exhibits/fig-1.png")
            _write_body(
                version_dir,
                "# Memo\n\n"
                "![Revenue by quarter for FY24](exhibits/fig-1.png)\n",
            )
            result = scan_version_dir(version_dir)
            self.assertTrue(result.passed())
            self.assertEqual(result.findings, [])

    def test_html_descriptive_alt_passes(self):
        """An ``<img>`` with descriptive alt= produces zero findings."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "exhibits/fig-1.png")
            _write_body(
                version_dir,
                "# Memo\n\n"
                '<img src="exhibits/fig-1.png" '
                'alt="Revenue by quarter for FY24" />\n',
            )
            result = scan_version_dir(version_dir)
            self.assertTrue(result.passed())

    def test_no_image_refs_at_all_is_clean(self):
        """A memo with zero image references emits zero findings."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_body(version_dir, "# Memo\n\nPlain prose only.\n")
            result = scan_version_dir(version_dir)
            self.assertTrue(result.passed())
            self.assertEqual(result.refs_scanned, 0)


# ---------------------------------------------------------------------------
# AC2: Missing alt → finding emitted with VLM candidate in suggested_fix
# ---------------------------------------------------------------------------


class TestMissingAltWithMockedVLM(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_markdown_empty_alt_emits_missing_finding(self):
        """``![](path)`` with empty alt produces a missing-alt finding."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, "# Memo\n\n![](fig.png)\n")

            callback = mock.Mock(return_value="A scatter plot of FY24 revenue.")
            result = scan_version_dir(version_dir, vlm_callback=callback)

            self.assertFalse(result.passed())
            self.assertEqual(len(result.findings), 1)
            af = result.findings[0]
            self.assertEqual(af.defect, "missing_alt")
            self.assertEqual(af.severity, SEVERITY_MISSING_ALT)
            self.assertEqual(af.syntax, "markdown")
            # Candidate from the VLM lands in suggested_fix.
            self.assertIn("scatter plot", af.suggested_fix)
            self.assertEqual(af.candidate_alt, "A scatter plot of FY24 revenue.")
            self.assertTrue(af.vlm_invoked)
            callback.assert_called_once()

    def test_html_no_alt_attribute_emits_missing_finding(self):
        """``<img src=...>`` with no alt attribute emits a missing-alt finding."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, '# Memo\n\n<img src="fig.png" />\n')

            callback = mock.Mock(return_value="A bar chart.")
            result = scan_version_dir(version_dir, vlm_callback=callback)

            self.assertEqual(len(result.findings), 1)
            af = result.findings[0]
            self.assertEqual(af.defect, "missing_alt")
            self.assertEqual(af.syntax, "html")
            self.assertEqual(af.alt, None)  # absent attribute → None

    def test_html_empty_alt_attribute_emits_missing_finding(self):
        """``<img alt="">`` emits a missing-alt finding (alt is empty)."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(
                version_dir, '# Memo\n\n<img src="fig.png" alt="" />\n'
            )

            result = scan_version_dir(version_dir)

            self.assertEqual(len(result.findings), 1)
            af = result.findings[0]
            self.assertEqual(af.defect, "missing_alt")
            self.assertEqual(af.alt, "")  # explicit empty string

    def test_missing_alt_without_callback_uses_template_fallback(self):
        """No VLM callback → finding still emitted; deterministic template used."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, "# Memo\n\n![](fig.png)\n")

            result = scan_version_dir(version_dir)  # no callback

            self.assertEqual(len(result.findings), 1)
            af = result.findings[0]
            self.assertEqual(af.defect, "missing_alt")
            self.assertIsNone(af.candidate_alt)
            self.assertFalse(af.vlm_invoked)
            # The deterministic template text is in suggested_fix.
            self.assertIn("one-sentence description", af.suggested_fix)


# ---------------------------------------------------------------------------
# AC3: alt="image" placeholder → inadequate-alt finding
# ---------------------------------------------------------------------------


class TestPlaceholderAltEmitsInadequate(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_literal_image_placeholder_fires(self):
        """``alt="image"`` is a literal placeholder."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, "# Memo\n\n![image](fig.png)\n")

            result = scan_version_dir(version_dir)

            self.assertEqual(len(result.findings), 1)
            af = result.findings[0]
            self.assertEqual(af.defect, "inadequate_alt")
            self.assertEqual(af.severity, SEVERITY_INADEQUATE_ALT)
            self.assertEqual(af.alt, "image")

    def test_literal_figure_placeholder_fires(self):
        """``alt="figure"`` fires."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, "# Memo\n\n![figure](fig.png)\n")
            result = scan_version_dir(version_dir)
            self.assertEqual(len(result.findings), 1)
            self.assertEqual(result.findings[0].defect, "inadequate_alt")

    def test_literal_chart_placeholder_fires(self):
        """``alt="chart"`` fires."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, "# Memo\n\n![chart](fig.png)\n")
            result = scan_version_dir(version_dir)
            self.assertEqual(len(result.findings), 1)
            self.assertEqual(result.findings[0].defect, "inadequate_alt")

    def test_screenshot_alone_fires_but_with_subject_does_not(self):
        """``alt="screenshot"`` fires; ``alt="screenshot of the dashboard"`` passes."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")

            # Alone → fires.
            _write_body(version_dir, "# Memo\n\n![screenshot](fig.png)\n")
            result = scan_version_dir(version_dir)
            self.assertEqual(len(result.findings), 1)
            self.assertEqual(result.findings[0].defect, "inadequate_alt")

            # With subject → passes.
            _write_body(
                version_dir,
                "# Memo\n\n![screenshot of the production OAuth flow](fig.png)\n",
            )
            result = scan_version_dir(version_dir)
            self.assertTrue(result.passed())

    def test_case_insensitive_placeholder_detection(self):
        """``alt="Image"`` (any case) fires."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, "# Memo\n\n![IMAGE](fig.png)\n")
            result = scan_version_dir(version_dir)
            self.assertEqual(len(result.findings), 1)
            self.assertEqual(result.findings[0].defect, "inadequate_alt")

    def test_inadequate_with_vlm_includes_candidate_in_fix(self):
        """VLM regeneration on inadequate alt lands in suggested_fix."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, "# Memo\n\n![chart](fig.png)\n")

            callback = mock.Mock(
                return_value="A line chart of customer growth over Q1-Q4."
            )
            result = scan_version_dir(version_dir, vlm_callback=callback)

            self.assertEqual(len(result.findings), 1)
            af = result.findings[0]
            self.assertEqual(af.defect, "inadequate_alt")
            self.assertIn("line chart", af.suggested_fix)
            callback.assert_called_once()


# ---------------------------------------------------------------------------
# AC4: Sub-10-char alt → inadequate-alt finding
# ---------------------------------------------------------------------------


class TestSubTenCharAltEmitsInadequate(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_short_alt_under_10_chars_fires(self):
        """A 5-character non-descriptive alt fires inadequate."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, "# Memo\n\n![chart](fig.png)\n")
            result = scan_version_dir(version_dir)
            self.assertEqual(len(result.findings), 1)
            self.assertEqual(result.findings[0].defect, "inadequate_alt")

    def test_borderline_10_char_alt_passes(self):
        """A 10-character alt is at the boundary — NOT inadequate."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, "# Memo\n\n![ABCDEFGHIJ](fig.png)\n")
            result = scan_version_dir(version_dir)
            self.assertTrue(result.passed())

    def test_trailing_punctuation_stripped_for_length_check(self):
        """``alt="quick.."`` (7 chars after strip) fires sub-10-char."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, "# Memo\n\n![quick..](fig.png)\n")
            result = scan_version_dir(version_dir)
            self.assertEqual(len(result.findings), 1)
            self.assertEqual(result.findings[0].defect, "inadequate_alt")


# ---------------------------------------------------------------------------
# AC5: Broken path (no nearby match) → propose_removal finding
# ---------------------------------------------------------------------------


class TestBrokenPathWithoutNearbyMatch(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_broken_path_no_nearby_emits_propose_removal(self):
        """Ref to nonexistent file with no similar nearby file → propose_removal."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            # No image file at all.
            _write_body(
                version_dir,
                "# Memo\n\n![chart of revenue](exhibits/totally-absent.png)\n",
            )
            result = scan_version_dir(version_dir)

            self.assertEqual(len(result.findings), 1)
            af = result.findings[0]
            self.assertEqual(af.defect, "broken_path")
            self.assertEqual(af.severity, SEVERITY_BROKEN_PATH)
            self.assertIsNone(af.closest_path)
            self.assertIn("propose_removal", af.suggested_fix)

    def test_broken_path_takes_priority_over_inadequate_alt(self):
        """When BOTH broken path AND inadequate alt would fire, broken-path wins."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            # File missing AND alt is "chart" (would be inadequate).
            _write_body(version_dir, "# Memo\n\n![chart](missing.png)\n")
            result = scan_version_dir(version_dir)
            # Exactly one finding emitted — the broken-path class.
            self.assertEqual(len(result.findings), 1)
            self.assertEqual(result.findings[0].defect, "broken_path")


# ---------------------------------------------------------------------------
# AC6: Broken path (nearby match) → propose_edit with closest-match suggestion
# ---------------------------------------------------------------------------


class TestBrokenPathWithNearbyMatch(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_cp_r_footgun_shape_suggests_root_filename(self):
        """``exhibits/foo.png`` missing but ``foo.png`` exists at root → closest-match."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            # File at root, ref into subdir — the cp -r footgun shape.
            _write_png(version_dir / "fig-revenue.png")
            _write_body(
                version_dir,
                "# Memo\n\n![Revenue chart](exhibits/fig-revenue.png)\n",
            )
            result = scan_version_dir(version_dir)

            self.assertEqual(len(result.findings), 1)
            af = result.findings[0]
            self.assertEqual(af.defect, "broken_path")
            self.assertEqual(af.closest_path, "fig-revenue.png")
            self.assertIn("propose_edit", af.suggested_fix)
            self.assertIn("fig-revenue.png", af.suggested_fix)

    def test_typo_in_filename_suggests_real_filename(self):
        """A near-name typo gets the real filename as suggestion."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "exhibits/revenue-fy24.png")
            _write_body(
                version_dir,
                "# Memo\n\n![Revenue chart](exhibits/revenue-fy42.png)\n",
            )
            result = scan_version_dir(version_dir)

            self.assertEqual(len(result.findings), 1)
            af = result.findings[0]
            self.assertEqual(af.defect, "broken_path")
            self.assertIn("revenue-fy24.png", af.closest_path or "")
            self.assertIn("propose_edit", af.suggested_fix)


# ---------------------------------------------------------------------------
# AC7: VLM cache test — identical image content produces no second VLM call
# ---------------------------------------------------------------------------


class TestVLMCacheDeduplication(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_identical_image_content_invokes_vlm_once(self):
        """Two refs to image files with identical bytes → one VLM call."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            # Two files, identical bytes.
            _write_png(version_dir / "fig-1.png", content=_TINY_PNG)
            _write_png(version_dir / "fig-2.png", content=_TINY_PNG)
            _write_body(
                version_dir,
                "# Memo\n\n"
                "![](fig-1.png)\n\n"
                "![](fig-2.png)\n",
            )

            callback = mock.Mock(return_value="A description of the image.")
            result = scan_version_dir(version_dir, vlm_callback=callback)

            # Both refs surface findings.
            self.assertEqual(len(result.findings), 2)
            # The VLM callback was invoked only ONCE (the second call
            # hit the content-hash cache).
            self.assertEqual(callback.call_count, 1)
            # The cache_hits counter records the dedup.
            self.assertEqual(result.vlm_calls, 1)
            self.assertEqual(result.vlm_cache_hits, 1)
            # BOTH findings have the same candidate (one from VLM, one from cache).
            self.assertEqual(
                result.findings[0].candidate_alt,
                result.findings[1].candidate_alt,
            )

    def test_distinct_image_content_invokes_vlm_twice(self):
        """Two refs to image files with distinct bytes → two VLM calls."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig-1.png", content=_TINY_PNG)
            _write_png(version_dir / "fig-2.png", content=_TINY_PNG_2)
            _write_body(
                version_dir,
                "# Memo\n\n"
                "![](fig-1.png)\n\n"
                "![](fig-2.png)\n",
            )

            # Return distinct candidates per call so the test asserts
            # call uniqueness rather than cache hit.
            responses = ["First chart description.", "Second chart description."]
            callback = mock.Mock(side_effect=responses)
            result = scan_version_dir(version_dir, vlm_callback=callback)

            self.assertEqual(callback.call_count, 2)
            self.assertEqual(result.vlm_calls, 2)
            self.assertEqual(result.vlm_cache_hits, 0)

    def test_generate_alt_text_caches_by_content_hash(self):
        """Direct ``generate_alt_text`` invocation honors the in-process cache."""
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "fig.png"
            _write_png(image_path)

            callback = mock.Mock(return_value="A descriptive alt.")
            # First call: miss → callback invoked.
            first = generate_alt_text(image_path, callback=callback)
            # Second call: hit → callback NOT invoked again.
            second = generate_alt_text(image_path, callback=callback)

            self.assertEqual(first, "A descriptive alt.")
            self.assertEqual(second, "A descriptive alt.")
            self.assertEqual(callback.call_count, 1)

    def test_clear_cache_resets_state(self):
        """``clear_vlm_cache`` empties the in-process cache."""
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "fig.png"
            _write_png(image_path)

            callback = mock.Mock(return_value="alt-text")
            generate_alt_text(image_path, callback=callback)
            self.assertEqual(callback.call_count, 1)

            clear_vlm_cache()
            generate_alt_text(image_path, callback=callback)
            # After clear, the second call invokes the callback again.
            self.assertEqual(callback.call_count, 2)


# ---------------------------------------------------------------------------
# AC8: Auto-discovery — <version_dir>.image-accessibility/ is recognized
# ---------------------------------------------------------------------------


class TestAutoDiscovery(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_aggregate_picks_up_image_accessibility_sibling(self):
        """The standard ``discover_critics`` finds the new sibling type."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_body(version_dir, "# Memo\n\n![](missing.png)\n")

            result = scan_version_dir(version_dir)
            sibling_path = write_review_dir(version_dir, result)

            # The sibling exists at the expected location.
            self.assertTrue(sibling_path.exists())
            expected_dir = (
                version_dir.parent
                / f"{version_dir.name}.{IMAGE_ACCESSIBILITY_SUFFIX}"
            )
            self.assertEqual(sibling_path.parent, expected_dir)

            # discover_critics picks it up.
            discovered = discover_critics(version_dir)
            self.assertIn(expected_dir, discovered)

            # The review round-trips through load_review + aggregate.
            loaded = load_review(expected_dir)
            self.assertEqual(loaded.kind, Kind.TOOL_EVIDENCE)
            self.assertEqual(loaded.critic_id, CRITIC_ID)
            self.assertEqual(len(loaded.findings), 1)

            # Aggregation merges the findings cleanly.
            agg = aggregate([loaded])
            self.assertEqual(len(agg.findings), 1)
            # No critical flags (a11y is advisory in v0).
            self.assertEqual(agg.critical_flags, [])

    def test_review_validates_against_schema_with_tool_calls(self):
        """``Review`` round-trips with ``tool_calls`` on every finding.

        Schema-discipline regression: ``Kind.TOOL_EVIDENCE`` requires
        ``tool_calls`` on every Finding. The image-accessibility critic
        emits tool_calls=[] on broken-path findings (no tool invocation)
        and a one-entry list on missing/inadequate-alt findings (the
        VLM call site, even when not actually invoked).
        """
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_body(
                version_dir,
                "# Memo\n\n"
                "![](missing-a.png)\n\n"  # missing alt + broken path
                "![chart](missing-b.png)\n",  # inadequate + broken
            )
            result = scan_version_dir(version_dir)
            review = result.to_review(version_dir=version_dir.name)

            # Both findings are broken_path (priority over alt class).
            self.assertEqual(len(review.findings), 2)
            for f in review.findings:
                self.assertIsNotNone(f.tool_calls)
                # broken_path → empty list.
                self.assertEqual(f.tool_calls, [])

            # Re-load through the typed validator to confirm the schema
            # accepts this Review shape.
            roundtrip = Review.model_validate_json(review.model_dump_json())
            self.assertEqual(roundtrip.kind, Kind.TOOL_EVIDENCE)


# ---------------------------------------------------------------------------
# Suppression directives — <!-- anvil-lint-disable -->
# ---------------------------------------------------------------------------


class TestSuppressionDirective(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_missing_alt_suppression_same_line(self):
        """Same-line disable directive suppresses missing-alt finding."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(
                version_dir,
                "# Memo\n\n"
                "![](fig.png) <!-- anvil-lint-disable: "
                "memo_image_accessibility_missing_alt -->\n",
            )
            result = scan_version_dir(version_dir)
            self.assertTrue(result.passed())

    def test_inadequate_alt_suppression_line_above(self):
        """Standalone disable directive on the line above suppresses."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(
                version_dir,
                "# Memo\n\n"
                "<!-- anvil-lint-disable: memo_image_accessibility_inadequate_alt -->\n"
                "![chart](fig.png)\n",
            )
            result = scan_version_dir(version_dir)
            self.assertTrue(result.passed())

    def test_broken_path_suppression(self):
        """Disable directive on broken-path also works."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_body(
                version_dir,
                "# Memo\n\n"
                "![placeholder](coming-soon.png) <!-- anvil-lint-disable: "
                "memo_image_accessibility_broken_path -->\n",
            )
            result = scan_version_dir(version_dir)
            self.assertTrue(result.passed())


# ---------------------------------------------------------------------------
# Skipped paths (URLs, absolute)
# ---------------------------------------------------------------------------


class TestSkippedPaths(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_url_refs_are_skipped(self):
        """``![alt](https://...)`` is out of scope (URL)."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_body(
                version_dir,
                "# Memo\n\n![](https://example.com/fig.png)\n",
            )
            result = scan_version_dir(version_dir)
            self.assertTrue(result.passed())
            self.assertEqual(result.refs_scanned, 0)

    def test_absolute_paths_are_skipped(self):
        """``![alt](/abs/path.png)`` is out of scope (absolute)."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_body(
                version_dir, "# Memo\n\n![](/abs/path.png)\n"
            )
            result = scan_version_dir(version_dir)
            self.assertTrue(result.passed())
            self.assertEqual(result.refs_scanned, 0)


# ---------------------------------------------------------------------------
# Result types — to_json / to_review shape
# ---------------------------------------------------------------------------


class TestResultSerialization(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_to_json_carries_expected_keys(self):
        """``to_json`` payload has the documented top-level keys."""
        r = ImageAccessibilityResult(
            findings=[
                AccessibilityFinding(
                    defect="missing_alt",
                    syntax="markdown",
                    line=3,
                    path="fig.png",
                    severity="major",
                    alt="",
                    candidate_alt="Generated alt.",
                    closest_path=None,
                    rationale="r",
                    suggested_fix="fix",
                    vlm_invoked=True,
                )
            ],
            body_path="memo.md",
            refs_scanned=1,
            vlm_calls=1,
            vlm_cache_hits=0,
            model="claude-test-model",
        )
        data = r.to_json()
        for key in (
            "critic",
            "body_path",
            "refs_scanned",
            "vlm_calls",
            "vlm_cache_hits",
            "model",
            "findings",
            "total_findings",
            "pass",
        ):
            self.assertIn(key, data)
        self.assertEqual(data["critic"], "image-accessibility")
        self.assertFalse(data["pass"])
        self.assertEqual(data["total_findings"], 1)

    def test_to_review_has_no_critical_flags(self):
        """A11y is advisory — no critical flags emitted regardless of findings."""
        r = ImageAccessibilityResult(
            findings=[
                AccessibilityFinding(
                    defect="missing_alt",
                    syntax="markdown",
                    line=3,
                    path="fig.png",
                    severity="major",
                    alt="",
                    candidate_alt=None,
                    closest_path=None,
                    rationale="r",
                    suggested_fix="fix",
                    vlm_invoked=False,
                )
            ],
            body_path="memo.md",
        )
        review = r.to_review(version_dir="memo.1")
        self.assertEqual(review.critical_flags, [])
        self.assertEqual(review.kind, Kind.TOOL_EVIDENCE)
        self.assertEqual(review.critic_id, CRITIC_ID)
        # Single null-scored row per the convention.
        self.assertEqual(len(review.scores), 1)
        self.assertIsNone(review.scores[0].score)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


class TestCLI(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_cli_main_clean_exits_zero(self):
        """No findings → exit code 0."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(
                version_dir,
                "# Memo\n\n![A descriptive alt for the chart](fig.png)\n",
            )
            rc = _cli_main([str(version_dir)])
            self.assertEqual(rc, 0)

    def test_cli_main_findings_exit_one(self):
        """Any finding → exit code 1."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_body(version_dir, "# Memo\n\n![](missing.png)\n")
            rc = _cli_main([str(version_dir)])
            self.assertEqual(rc, 1)

    def test_cli_main_missing_version_dir_exits_two(self):
        """Nonexistent version_dir → exit code 2."""
        rc = _cli_main(["/nonexistent/path/that/does/not/exist"])
        self.assertEqual(rc, 2)

    def test_cli_main_write_review_creates_sibling(self):
        """``--write-review`` writes the sibling dir."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_body(version_dir, "# Memo\n\n![](missing.png)\n")
            rc = _cli_main([str(version_dir), "--write-review"])
            self.assertEqual(rc, 1)
            sibling = (
                version_dir.parent
                / f"{version_dir.name}.{IMAGE_ACCESSIBILITY_SUFFIX}"
            )
            self.assertTrue((sibling / "_review.json").is_file())
            self.assertTrue((sibling / "_findings.json").is_file())

            # The typed review on disk validates against the schema.
            review = Review.model_validate_json(
                (sibling / "_review.json").read_text()
            )
            self.assertEqual(review.kind, Kind.TOOL_EVIDENCE)

    def test_cli_default_does_not_create_sibling(self):
        """No ``--write-review`` → no sibling dir created."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_body(version_dir, "# Memo\n\n![](missing.png)\n")
            rc = _cli_main([str(version_dir)])
            self.assertEqual(rc, 1)
            sibling = (
                version_dir.parent
                / f"{version_dir.name}.{IMAGE_ACCESSIBILITY_SUFFIX}"
            )
            self.assertFalse(sibling.exists())


# ---------------------------------------------------------------------------
# Graceful-degrade — missing body file
# ---------------------------------------------------------------------------


class TestGracefulDegrade(unittest.TestCase):
    def setUp(self):
        clear_vlm_cache()

    def test_missing_body_returns_empty_result(self):
        """A version dir with no body.md returns an empty result (no raise)."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            # No body file.
            result = scan_version_dir(version_dir)
            self.assertEqual(result.findings, [])
            self.assertIsNone(result.body_path)

    def test_vlm_callback_raises_does_not_abort_scan(self):
        """A raising VLM callback degrades to the template fallback."""
        with tempfile.TemporaryDirectory() as tmp:
            version_dir = _make_version_dir(Path(tmp))
            _write_png(version_dir / "fig.png")
            _write_body(version_dir, "# Memo\n\n![](fig.png)\n")

            def bad_callback(image_path, prompt):
                raise RuntimeError("VLM service down")

            result = scan_version_dir(version_dir, vlm_callback=bad_callback)

            # Finding still surfaces — just with the template suggested_fix.
            self.assertEqual(len(result.findings), 1)
            af = result.findings[0]
            self.assertEqual(af.defect, "missing_alt")
            self.assertIsNone(af.candidate_alt)


if __name__ == "__main__":
    unittest.main()
