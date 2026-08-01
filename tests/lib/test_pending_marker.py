"""Tests for ``anvil/lib/pending_marker.py`` (issue #842, phase 1 of #841).

Covers the acceptance criteria from the issue:

- Marker detection: well-formed ``[PENDING <source>]``, malformed
  (``[PENDING]`` / ``[PENDING   ]``), and non-matches (lowercase / glued
  tokens like ``[PENDINGFOO]``).
- ``<!-- anvil-lint-disable: pending_marker -->`` suppression (same-line
  and line-above), downgrading a hit to severity ``info``/``nit`` and
  suppressing it from ``CriticalFlag`` emission even under ``--blocking``.
- ``passed()``: only malformed, unsuppressed markers fail the gate;
  well-formed markers never do (tracked, not a defect).
- Advisory mode (default) emits Findings only, never a ``CriticalFlag``.
  ``--blocking`` additionally emits one ``CriticalFlag(type=
  "pending_dependency", ...)`` per unique unsuppressed well-formed
  ``source``.
- The sidecar ``<thread>.{N}.pending/_review.json`` validates against the
  review schema and is discovered by ``critics.discover_critics`` with no
  aggregator change.
- Verdict wiring: a review whose ONLY critical flags are
  ``pending_dependency``-typed never forces ``Verdict.BLOCK`` through
  ``anvil/lib/critics.py::aggregate`` / ``compute_verdict``, but stays
  visible in ``AggregatedReview.critical_flags``; an ordinary critical
  flag co-occurring with a ``pending_dependency`` flag still BLOCKs.
- ``mask_well_formed_markers`` masks well-formed spans (offset-preserving)
  and leaves malformed markers untouched — the render_gate.py Check 6
  carve-out primitive (covered end-to-end in
  ``tests/lib/test_render_gate_memo.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.lib.critics import aggregate, compute_verdict, discover_critics
from anvil.lib.pending_marker import (
    CHECK_NAME,
    MALFORMED_MARKER,
    PENDING_DEPENDENCY_FLAG_TYPE,
    UNRESOLVED_PENDING,
    MARKER_CANDIDATE_RE,
    PendingMarkerHit,
    PendingMarkerResult,
    check_pending_markers,
    check_pending_markers_text,
    main,
    mask_well_formed_markers,
    scan_text,
    write_review_dir,
)
from anvil.lib.review_schema import Review, Verdict
from anvil.lib import convergence as _convergence


def make_version_dir(tmp_path: Path, body: str, slug: str = "acme-report") -> Path:
    """Build a #295-shaped version dir: <slug>/<slug>.1/<slug>.md."""
    version_dir = tmp_path / slug / f"{slug}.1"
    version_dir.mkdir(parents=True)
    (version_dir / f"{slug}.md").write_text(body, encoding="utf-8")
    return version_dir


# ---------------------------------------------------------------------------
# Marker detection
# ---------------------------------------------------------------------------


class TestMarkerDetection:
    def test_well_formed_marker(self) -> None:
        hits = scan_text("Waiting on [PENDING Q3 earnings report] still.\n")
        assert len(hits) == 1
        h = hits[0]
        assert h.well_formed is True
        assert h.source == "Q3 earnings report"
        assert h.line == 1
        assert h.suppressed is False

    def test_malformed_empty_source(self) -> None:
        hits = scan_text("[PENDING]\n")
        assert len(hits) == 1
        assert hits[0].well_formed is False
        assert hits[0].source is None

    def test_malformed_whitespace_only_source(self) -> None:
        hits = scan_text("[PENDING   ]\n")
        assert len(hits) == 1
        assert hits[0].well_formed is False

    def test_lowercase_pending_is_not_a_marker(self) -> None:
        hits = scan_text("[pending some source]\n")
        assert hits == []

    def test_glued_token_is_not_a_marker(self) -> None:
        hits = scan_text("[PENDINGFOO]\n")
        assert hits == []

    def test_multiple_markers_multiple_lines(self) -> None:
        text = (
            "Line one.\n"
            "[PENDING dataset A]\n"
            "Middle.\n"
            "[PENDING dataset B]\n"
        )
        hits = scan_text(text)
        assert [h.source for h in hits] == ["dataset A", "dataset B"]
        assert [h.line for h in hits] == [2, 4]

    def test_source_is_stripped(self) -> None:
        hits = scan_text("[PENDING   dataset with padding   ]\n")
        assert hits[0].source == "dataset with padding"

    def test_no_markers_empty_list(self) -> None:
        assert scan_text("Just prose, nothing pending.\n") == []

    def test_check_pending_markers_text_is_scan_text_alias(self) -> None:
        text = "[PENDING x]\n"
        assert check_pending_markers_text(text) == scan_text(text)


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


class TestSuppression:
    def test_same_line_suppression(self) -> None:
        text = (
            "Prose. [PENDING dataset] "
            "<!-- anvil-lint-disable: pending_marker -->\n"
        )
        hits = scan_text(text)
        assert len(hits) == 1
        assert hits[0].suppressed is True

    def test_line_above_suppression(self) -> None:
        text = (
            "<!-- anvil-lint-disable: pending_marker -->\n"
            "[PENDING dataset]\n"
        )
        hits = scan_text(text)
        assert len(hits) == 1
        assert hits[0].suppressed is True

    def test_suppression_applies_to_malformed_too(self) -> None:
        text = "[PENDING] <!-- anvil-lint-disable: pending_marker -->\n"
        hits = scan_text(text)
        assert hits[0].well_formed is False
        assert hits[0].suppressed is True

    def test_unrelated_rule_does_not_suppress(self) -> None:
        text = "[PENDING dataset] <!-- anvil-lint-disable: numeric_consistency -->\n"
        hits = scan_text(text)
        assert hits[0].suppressed is False

    def test_comma_separated_rules(self) -> None:
        text = (
            "[PENDING dataset] "
            "<!-- anvil-lint-disable: numeric_consistency, pending_marker -->\n"
        )
        hits = scan_text(text)
        assert hits[0].suppressed is True


# ---------------------------------------------------------------------------
# passed() — only malformed, unsuppressed markers gate
# ---------------------------------------------------------------------------


class TestPassed:
    def test_well_formed_only_passes(self, tmp_path: Path) -> None:
        vd = make_version_dir(tmp_path, "[PENDING dataset A]\n")
        result = check_pending_markers(vd)
        assert result.passed() is True

    def test_malformed_fails(self, tmp_path: Path) -> None:
        vd = make_version_dir(tmp_path, "[PENDING]\n")
        result = check_pending_markers(vd)
        assert result.passed() is False

    def test_suppressed_malformed_passes(self, tmp_path: Path) -> None:
        vd = make_version_dir(
            tmp_path,
            "[PENDING] <!-- anvil-lint-disable: pending_marker -->\n",
        )
        result = check_pending_markers(vd)
        assert result.passed() is True

    def test_clean_document_passes(self, tmp_path: Path) -> None:
        vd = make_version_dir(tmp_path, "Nothing pending here.\n")
        result = check_pending_markers(vd)
        assert result.passed() is True
        assert result.hits == []

    def test_mixed_well_formed_and_malformed(self, tmp_path: Path) -> None:
        vd = make_version_dir(
            tmp_path,
            "[PENDING dataset A]\n[PENDING]\n",
        )
        result = check_pending_markers(vd)
        assert result.passed() is False
        assert len(result.well_formed_hits) == 1
        assert len(result.malformed_hits) == 1


# ---------------------------------------------------------------------------
# unresolved_sources()
# ---------------------------------------------------------------------------


def test_unresolved_sources_excludes_suppressed_and_malformed() -> None:
    text = (
        "[PENDING A]\n"
        "[PENDING B] <!-- anvil-lint-disable: pending_marker -->\n"
        "[PENDING]\n"
    )
    result = PendingMarkerResult(
        version_dir="t.1", body_path="t.md", hits=scan_text(text)
    )
    assert result.unresolved_sources() == ["A"]


# ---------------------------------------------------------------------------
# to_review — advisory vs blocking
# ---------------------------------------------------------------------------


class TestToReview:
    def _result(self, tmp_path: Path) -> PendingMarkerResult:
        vd = make_version_dir(
            tmp_path,
            "[PENDING Q3 earnings report]\n[PENDING]\n",
        )
        return check_pending_markers(vd)

    def test_advisory_emits_findings_no_critical_flags(
        self, tmp_path: Path
    ) -> None:
        result = self._result(tmp_path)
        review = result.to_review(version_dir="acme-report.1")
        assert review.critical_flags == []
        assert len(review.findings) == 2
        severities = sorted(f.severity for f in review.findings)
        assert severities == ["major", "minor"]

    def test_advisory_verdict_not_blocked(self, tmp_path: Path) -> None:
        result = self._result(tmp_path)
        review = result.to_review(version_dir="acme-report.1")
        agg = aggregate([review])
        # No critical_flags at all in advisory mode; the malformed marker's
        # "major" Finding does not itself force BLOCK (Findings never do —
        # only CriticalFlag / Score.critical do).
        assert agg.verdict != Verdict.BLOCK

    def test_blocking_emits_one_flag_per_unique_source(
        self, tmp_path: Path
    ) -> None:
        vd = make_version_dir(
            tmp_path,
            "[PENDING dataset] more prose [PENDING dataset] again.\n",
        )
        result = check_pending_markers(vd)
        review = result.to_review(version_dir="acme-report.1", blocking=True)
        assert len(review.critical_flags) == 1
        assert review.critical_flags[0].type == PENDING_DEPENDENCY_FLAG_TYPE
        assert "dataset" in review.critical_flags[0].justification

    def test_blocking_excludes_suppressed_from_flags(
        self, tmp_path: Path
    ) -> None:
        vd = make_version_dir(
            tmp_path,
            "[PENDING dataset] <!-- anvil-lint-disable: pending_marker -->\n",
        )
        result = check_pending_markers(vd)
        review = result.to_review(version_dir="acme-report.1", blocking=True)
        assert review.critical_flags == []

    def test_blocking_excludes_malformed_from_flags(
        self, tmp_path: Path
    ) -> None:
        vd = make_version_dir(tmp_path, "[PENDING]\n")
        result = check_pending_markers(vd)
        review = result.to_review(version_dir="acme-report.1", blocking=True)
        assert review.critical_flags == []

    def test_review_is_tool_evidence_kind(self, tmp_path: Path) -> None:
        result = self._result(tmp_path)
        review = result.to_review(version_dir="acme-report.1")
        assert review.kind.value == "tool_evidence"
        # kind=tool_evidence requires tool_calls (possibly empty) on every
        # finding — the schema validator enforces this.
        for f in review.findings:
            assert f.tool_calls == []


# ---------------------------------------------------------------------------
# Verdict/convergence wiring — pending_dependency never forces BLOCK
# ---------------------------------------------------------------------------


class TestVerdictWiring:
    def test_pending_dependency_flag_matches_convergence_constant(self) -> None:
        assert (
            PENDING_DEPENDENCY_FLAG_TYPE
            == _convergence.PENDING_DEPENDENCY_FLAG_TYPE
        )

    def test_pending_only_flags_never_block(self, tmp_path: Path) -> None:
        vd = make_version_dir(tmp_path, "[PENDING dataset]\n")
        result = check_pending_markers(vd)
        review = result.to_review(version_dir="acme-report.1", blocking=True)
        from anvil.lib.review_schema import Score

        review2 = Review(
            version_dir="acme-report.1",
            critic_id="review",
            scores=[Score(dimension="d", score=40, max=44)],
            critical_flags=review.critical_flags,
            threshold=35,
        )
        agg = aggregate([review, review2])
        assert agg.verdict == Verdict.ADVANCE
        assert any(
            cf.type == PENDING_DEPENDENCY_FLAG_TYPE for cf in agg.critical_flags
        )

    def test_pending_flag_coexisting_with_ordinary_flag_still_blocks(
        self, tmp_path: Path
    ) -> None:
        from anvil.lib.review_schema import CriticalFlag, Score

        vd = make_version_dir(tmp_path, "[PENDING dataset]\n")
        result = check_pending_markers(vd)
        pending_review = result.to_review(
            version_dir="acme-report.1", blocking=True
        )
        ordinary_review = Review(
            version_dir="acme-report.1",
            critic_id="review",
            scores=[Score(dimension="d", score=40, max=44)],
            critical_flags=[
                CriticalFlag(type="factual_error", justification="x")
            ],
            threshold=35,
        )
        agg = aggregate([pending_review, ordinary_review])
        assert agg.verdict == Verdict.BLOCK

    def test_compute_verdict_single_iteration_pending_only(
        self, tmp_path: Path
    ) -> None:
        from anvil.lib.review_schema import Score

        vd = make_version_dir(tmp_path, "[PENDING dataset]\n")
        result = check_pending_markers(vd)
        review = result.to_review(version_dir="acme-report.1", blocking=True)
        review2 = Review(
            version_dir="acme-report.1",
            critic_id="review",
            scores=[Score(dimension="d", score=20, max=44)],
            critical_flags=review.critical_flags,
            threshold=35,
        )
        agg = aggregate([review, review2])
        assert compute_verdict(agg) == Verdict.REVISE  # below threshold, no BLOCK


# ---------------------------------------------------------------------------
# Sidecar + discovery contract
# ---------------------------------------------------------------------------


class TestSidecarAndDiscovery:
    def test_write_review_dir_shape_and_schema(self, tmp_path: Path) -> None:
        vd = make_version_dir(tmp_path, "[PENDING dataset]\n")
        result = check_pending_markers(vd)
        out = write_review_dir(vd, result)
        assert out.name == "_review.json"
        assert out.parent.name == "acme-report.1.pending"
        payload = json.loads(out.read_text())
        # Round-trips through the typed schema.
        Review.model_validate(payload)

    def test_discovered_by_discover_critics(self, tmp_path: Path) -> None:
        vd = make_version_dir(tmp_path, "[PENDING dataset]\n")
        result = check_pending_markers(vd)
        write_review_dir(vd, result)
        critics = discover_critics(vd)
        assert any(c.name.endswith(".pending") for c in critics)

    def test_rerun_regenerates_idempotently(self, tmp_path: Path) -> None:
        vd = make_version_dir(tmp_path, "[PENDING dataset]\n")
        result = check_pending_markers(vd)
        out1 = write_review_dir(vd, result)
        out2 = write_review_dir(vd, result)
        assert out1 == out2
        assert out2.is_file()


# ---------------------------------------------------------------------------
# mask_well_formed_markers
# ---------------------------------------------------------------------------


class TestMaskWellFormedMarkers:
    def test_masks_well_formed_marker(self) -> None:
        text = "before [PENDING dataset] after"
        masked = mask_well_formed_markers(text)
        assert "[PENDING" not in masked
        assert "dataset" not in masked
        assert "before" in masked and "after" in masked

    def test_preserves_length_and_newlines(self) -> None:
        text = "line1\n[PENDING x]\nline3\n"
        masked = mask_well_formed_markers(text)
        assert len(masked) == len(text)
        assert masked.count("\n") == text.count("\n")

    def test_leaves_malformed_marker_untouched(self) -> None:
        text = "before [PENDING] after"
        masked = mask_well_formed_markers(text)
        assert "[PENDING]" in masked

    def test_leaves_unrelated_text_untouched(self) -> None:
        text = "Nothing pending, but a [TBD] placeholder is here."
        masked = mask_well_formed_markers(text)
        assert masked == text


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


class TestCli:
    def test_clean_exit_code_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        vd = make_version_dir(tmp_path, "[PENDING dataset]\n")
        code = main([str(vd)])
        assert code == 0

    def test_malformed_exit_code_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        vd = make_version_dir(tmp_path, "[PENDING]\n")
        code = main([str(vd)])
        assert code == 1

    def test_missing_version_dir_exit_code_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        code = main([str(tmp_path / "does-not-exist")])
        assert code == 2

    def test_write_review_flag(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        vd = make_version_dir(tmp_path, "[PENDING dataset]\n")
        code = main([str(vd), "--write-review", "--blocking"])
        assert code == 0
        sidecar = vd.parent / f"{vd.name}.pending" / "_review.json"
        assert sidecar.is_file()
        payload = json.loads(sidecar.read_text())
        assert payload["critical_flags"][0]["type"] == PENDING_DEPENDENCY_FLAG_TYPE

    def test_body_override(self, tmp_path: Path) -> None:
        vd = tmp_path / "weird" / "weird.1"
        vd.mkdir(parents=True)
        (vd / "custom.md").write_text("[PENDING dataset]\n")
        code = main([str(vd), "--body", "custom.md"])
        assert code == 0
