"""Tests for ``anvil/lib/pending_marker.py`` (issue #841).

Covers the acceptance criteria from the issue:

- A documented placeholder convention (``[PENDING <source>]``) with a
  lib-level helper for emitting (``emit_pending_marker``) and detecting
  (``find_pending_markers`` / ``check_pending_markers``) it.
- A well-formed marker is recognized; malformed/near-miss text
  (``[PENDING]``, bare prose use of the word "pending") is NOT flagged.
- Advisory mode emits informational (``nit``-severity) findings and no
  ``CriticalFlag``; ``blocking=True`` emits a flag that forces
  ``Verdict.BLOCK`` through ``compute_verdict`` — the "blocks
  READY/AUDITED" gate.
- The sidecar ``<thread>.{N}.pending/_review.json`` validates against
  the review schema and is discovered by ``critics.discover_critics``
  with no aggregator change.
- Optional ``BRIEF.md`` frontmatter ``pending_sources:`` list surfaces
  as ``expected_sources`` / ``resolved_sources`` for reporting.
- Edge cases: markers inside code fences are masked out; markers in a
  ``.tex`` body work the same as markdown.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.lib.critics import aggregate, compute_verdict, discover_critics
from anvil.lib.pending_marker import (
    CRITICAL_PENDING_MARKER,
    UNRESOLVED_PENDING_MARKER,
    check_pending_markers,
    check_text,
    emit_pending_marker,
    find_pending_markers,
    load_expected_pending_sources,
    main,
    write_review_dir,
)
from anvil.lib.review_schema import Review, Verdict


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


PENDING_BODY = """# Results

The model reaches [PENDING benchmark-run-2024-11] accuracy on the
held-out set, roughly matching the prior baseline.

Component cost is [PENDING: vendor-quote-acme] per unit at the quoted
minimum order quantity.
"""

CLEAN_BODY = """# Results

The model reaches 94.2% accuracy on the held-out set, matching the
prior baseline.

Component cost is $1.42 per unit at the quoted minimum order quantity.
"""

NEAR_MISS_BODY = """# Status

Results are still pending from the vendor.

A decision is PENDING review by the committee.

[PENDING]

[PENDING ]

[TODO: fill in the number]
"""


def make_memo_version_dir(tmp_path: Path, body: str, slug: str = "acme-seed") -> Path:
    """Build a #295-shaped memo version dir: <slug>/<slug>.1/<slug>.md."""
    version_dir = tmp_path / slug / f"{slug}.1"
    version_dir.mkdir(parents=True)
    (version_dir / f"{slug}.md").write_text(body, encoding="utf-8")
    return version_dir


# ---------------------------------------------------------------------------
# AC: well-formed marker detection
# ---------------------------------------------------------------------------


class TestMarkerDetection:
    def test_two_well_formed_markers_detected(self) -> None:
        markers = find_pending_markers(PENDING_BODY)
        assert len(markers) == 2
        sources = sorted(m.source for m in markers)
        assert sources == ["benchmark-run-2024-11", "vendor-quote-acme"]

    def test_line_numbers_recorded(self) -> None:
        markers = find_pending_markers(PENDING_BODY)
        by_source = {m.source: m for m in markers}
        assert by_source["benchmark-run-2024-11"].line == 3
        assert by_source["vendor-quote-acme"].line == 6

    def test_colon_and_space_separator_both_well_formed(self) -> None:
        body = "A is [PENDING alpha] and B is [PENDING: beta].\n"
        markers = find_pending_markers(body)
        assert sorted(m.source for m in markers) == ["alpha", "beta"]

    def test_clean_body_zero_markers(self) -> None:
        assert find_pending_markers(CLEAN_BODY) == []

    def test_check_text_alias(self) -> None:
        assert check_text(PENDING_BODY) == find_pending_markers(PENDING_BODY)


# ---------------------------------------------------------------------------
# AC: malformed / near-miss text is NOT flagged
# ---------------------------------------------------------------------------


class TestMalformedNearMiss:
    def test_prose_use_of_pending_not_flagged(self) -> None:
        markers = find_pending_markers(NEAR_MISS_BODY)
        assert markers == []

    def test_bracket_with_no_source_not_flagged(self) -> None:
        assert find_pending_markers("Placeholder: [PENDING]\n") == []

    def test_bracket_with_only_whitespace_not_flagged(self) -> None:
        assert find_pending_markers("Placeholder: [PENDING ]\n") == []

    def test_lowercase_pending_not_flagged(self) -> None:
        # Case-sensitive by design — "pending" in prose must never match.
        assert find_pending_markers("[pending some-source]\n") == []

    def test_unrelated_bracket_keyword_not_flagged(self) -> None:
        assert find_pending_markers("[TODO: fill in the number]\n") == []


# ---------------------------------------------------------------------------
# AC: emitter helper
# ---------------------------------------------------------------------------


class TestEmitter:
    def test_default_emits_space_form(self) -> None:
        assert emit_pending_marker("benchmark-run") == "[PENDING benchmark-run]"

    def test_colon_form(self) -> None:
        assert emit_pending_marker("vendor-quote", colon=True) == "[PENDING: vendor-quote]"

    def test_emitted_marker_round_trips_through_detector(self) -> None:
        for colon in (False, True):
            marker = emit_pending_marker("round-trip-source", colon=colon)
            found = find_pending_markers(f"Value is {marker} for now.\n")
            assert len(found) == 1
            assert found[0].source == "round-trip-source"

    def test_empty_source_rejected(self) -> None:
        with pytest.raises(ValueError):
            emit_pending_marker("   ")


# ---------------------------------------------------------------------------
# AC: masking (code fences)
# ---------------------------------------------------------------------------


class TestMasking:
    def test_marker_inside_code_fence_masked(self) -> None:
        body = (
            "Use the convention like this:\n\n"
            "```\n"
            "[PENDING example-source]\n"
            "```\n"
        )
        assert find_pending_markers(body) == []

    def test_marker_inside_inline_code_masked(self) -> None:
        body = "The syntax is `[PENDING example-source]` — see the docs.\n"
        assert find_pending_markers(body) == []

    def test_marker_outside_fence_still_detected(self) -> None:
        body = (
            "```\n"
            "[PENDING inside-fence]\n"
            "```\n\n"
            "Actual value: [PENDING outside-fence].\n"
        )
        markers = find_pending_markers(body)
        assert len(markers) == 1
        assert markers[0].source == "outside-fence"

    def test_latex_comment_masks_marker(self) -> None:
        body = "% [PENDING commented-out]\nReal text has [PENDING live-marker].\n"
        markers = find_pending_markers(body, latex=True)
        assert len(markers) == 1
        assert markers[0].source == "live-marker"

    def test_latex_comment_masking_inert_for_markdown(self) -> None:
        # Without latex=True, a "%" prefix does not comment anything out.
        body = "% [PENDING not-a-latex-comment]\n"
        markers = find_pending_markers(body, latex=False)
        assert len(markers) == 1


# ---------------------------------------------------------------------------
# AC: filesystem entry point
# ---------------------------------------------------------------------------


class TestFilesystemEntryPoint:
    def test_check_pending_markers_finds_two(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, PENDING_BODY)
        result = check_pending_markers(version_dir)
        assert not result.passed()
        assert len(result.markers) == 2
        assert result.body_path == "acme-seed.md"
        assert sorted(result.outstanding_sources) == [
            "benchmark-run-2024-11",
            "vendor-quote-acme",
        ]

    def test_clean_result_passes(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, CLEAN_BODY)
        result = check_pending_markers(version_dir)
        assert result.passed()
        assert result.to_json()["markers"] == []
        assert result.to_json()["pass"] is True


# ---------------------------------------------------------------------------
# AC: optional BRIEF.md pending_sources frontmatter
# ---------------------------------------------------------------------------


class TestExpectedPendingSources:
    def test_no_brief_returns_empty(self, tmp_path: Path) -> None:
        thread_dir = tmp_path / "acme-seed"
        thread_dir.mkdir()
        assert load_expected_pending_sources(thread_dir) == []

    def test_brief_with_pending_sources_list(self, tmp_path: Path) -> None:
        thread_dir = tmp_path / "acme-seed"
        thread_dir.mkdir()
        (thread_dir / "BRIEF.md").write_text(
            "---\n"
            "pending_sources:\n"
            "  - benchmark-run-2024-11\n"
            "  - vendor-quote-acme\n"
            "---\n\n"
            "# Free prose\n",
            encoding="utf-8",
        )
        assert load_expected_pending_sources(thread_dir) == [
            "benchmark-run-2024-11",
            "vendor-quote-acme",
        ]

    def test_brief_without_frontmatter_returns_empty(self, tmp_path: Path) -> None:
        thread_dir = tmp_path / "acme-seed"
        thread_dir.mkdir()
        (thread_dir / "BRIEF.md").write_text("# Just prose, no frontmatter\n", encoding="utf-8")
        assert load_expected_pending_sources(thread_dir) == []

    def test_brief_with_other_keys_but_no_pending_sources(self, tmp_path: Path) -> None:
        thread_dir = tmp_path / "acme-seed"
        thread_dir.mkdir()
        (thread_dir / "BRIEF.md").write_text(
            "---\nproject: acme\n---\n\n# Prose\n", encoding="utf-8"
        )
        assert load_expected_pending_sources(thread_dir) == []

    def test_resolved_and_outstanding_partition_expected_sources(self, tmp_path: Path) -> None:
        thread_dir = tmp_path / "acme-seed"
        thread_dir.mkdir()
        (thread_dir / "BRIEF.md").write_text(
            "---\n"
            "pending_sources:\n"
            "  - benchmark-run-2024-11\n"
            "  - vendor-quote-acme\n"
            "  - already-resolved-source\n"
            "---\n",
            encoding="utf-8",
        )
        version_dir = thread_dir / "acme-seed.1"
        version_dir.mkdir()
        (version_dir / "acme-seed.md").write_text(PENDING_BODY, encoding="utf-8")
        result = check_pending_markers(version_dir)
        assert sorted(result.outstanding_sources) == [
            "benchmark-run-2024-11",
            "vendor-quote-acme",
        ]
        assert result.resolved_sources == ["already-resolved-source"]

    def test_explicit_expected_sources_override(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, PENDING_BODY)
        result = check_pending_markers(version_dir, expected_sources=["only-this-one"])
        assert result.expected_sources == ["only-this-one"]
        assert result.resolved_sources == ["only-this-one"]


# ---------------------------------------------------------------------------
# AC: severity wiring — advisory vs blocking
# ---------------------------------------------------------------------------


class TestSeverityWiring:
    def _finding_result(self, tmp_path: Path):
        version_dir = make_memo_version_dir(tmp_path, PENDING_BODY)
        return version_dir, check_pending_markers(version_dir)

    def test_advisory_findings_are_nit_severity_no_penalty(self, tmp_path: Path) -> None:
        version_dir, result = self._finding_result(tmp_path)
        review = result.to_review(version_dir=version_dir.name)
        assert review.critical_flags == []
        assert len(review.findings) == 2
        assert all(f.severity == "nit" for f in review.findings)

    def test_advisory_verdict_not_blocked(self, tmp_path: Path) -> None:
        version_dir, result = self._finding_result(tmp_path)
        review = result.to_review(version_dir=version_dir.name)
        agg = aggregate([review])
        assert compute_verdict(agg, threshold=35) is not Verdict.BLOCK

    def test_blocking_emits_one_flag_and_forces_block(self, tmp_path: Path) -> None:
        version_dir, result = self._finding_result(tmp_path)
        review = result.to_review(version_dir=version_dir.name, blocking=True)
        assert len(review.critical_flags) == 1
        flag = review.critical_flags[0]
        assert flag.type == f"{CRITICAL_PENDING_MARKER}:{UNRESOLVED_PENDING_MARKER}"
        assert "benchmark-run-2024-11" in flag.justification
        assert "vendor-quote-acme" in flag.justification
        agg = aggregate([review])
        assert compute_verdict(agg, threshold=35) is Verdict.BLOCK

    def test_blocking_still_emits_nit_findings_not_upgraded(self, tmp_path: Path) -> None:
        version_dir, result = self._finding_result(tmp_path)
        review = result.to_review(version_dir=version_dir.name, blocking=True)
        assert all(f.severity == "nit" for f in review.findings)

    def test_blocking_on_clean_result_emits_nothing(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, CLEAN_BODY)
        result = check_pending_markers(version_dir)
        review = result.to_review(version_dir=version_dir.name, blocking=True)
        assert review.critical_flags == []
        assert review.findings == []


# ---------------------------------------------------------------------------
# AC: sidecar write + discovery (no aggregator change)
# ---------------------------------------------------------------------------


class TestSidecar:
    def test_write_review_dir_shape_and_schema(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, PENDING_BODY)
        result = check_pending_markers(version_dir)
        out = write_review_dir(version_dir, result)
        assert out == version_dir.parent / "acme-seed.1.pending" / "_review.json"
        assert out.is_file()
        payload = json.loads(out.read_text(encoding="utf-8"))
        review = Review.model_validate(payload)
        assert review.critic_id == "pending"
        assert review.kind.value == "tool_evidence"

    def test_discovered_by_discover_critics(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, PENDING_BODY)
        result = check_pending_markers(version_dir)
        write_review_dir(version_dir, result)
        critics = discover_critics(version_dir)
        assert version_dir.parent / "acme-seed.1.pending" in critics

    def test_rerun_regenerates_idempotently(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, PENDING_BODY)
        result = check_pending_markers(version_dir)
        first = write_review_dir(version_dir, result)
        second = write_review_dir(version_dir, result, blocking=True)
        assert first == second
        assert second.is_file()
        leftovers = [p for p in version_dir.parent.iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []
        payload = json.loads(second.read_text(encoding="utf-8"))
        assert len(payload["critical_flags"]) == 1


# ---------------------------------------------------------------------------
# AC: CLI entry point
# ---------------------------------------------------------------------------


class TestCli:
    def test_findings_exit_code_and_write_review(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        version_dir = make_memo_version_dir(tmp_path, PENDING_BODY)
        rc = main([str(version_dir), "--write-review"])
        assert rc == 1
        out = capsys.readouterr()
        payload = json.loads(out.out)
        assert payload["check"] == "pending_marker"
        assert len(payload["markers"]) == 2
        sidecar = version_dir.parent / "acme-seed.1.pending" / "_review.json"
        assert sidecar.is_file()

    def test_clean_exit_code_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        version_dir = make_memo_version_dir(tmp_path, CLEAN_BODY)
        rc = main([str(version_dir)])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["pass"] is True

    def test_missing_body_exit_code_two(self, tmp_path: Path) -> None:
        empty = tmp_path / "thread" / "thread.1"
        empty.mkdir(parents=True)
        assert main([str(empty)]) == 2

    def test_missing_version_dir_exit_code_two(self, tmp_path: Path) -> None:
        assert main([str(tmp_path / "nope" / "nope.1")]) == 2

    def test_blocking_flag_writes_flag_into_sidecar(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        version_dir = make_memo_version_dir(tmp_path, PENDING_BODY)
        rc = main([str(version_dir), "--write-review", "--blocking"])
        assert rc == 1
        sidecar = version_dir.parent / "acme-seed.1.pending" / "_review.json"
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert len(payload["critical_flags"]) == 1

    def test_body_override_for_legacy_thread(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        version_dir = tmp_path / "tractatus" / "tractatus.1"
        version_dir.mkdir(parents=True)
        (version_dir / "paper.tex").write_text(
            "Result is [PENDING lean-proof-verification].\n", encoding="utf-8"
        )
        rc = main([str(version_dir), "--body", "paper.tex"])
        assert rc == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["body_path"] == "paper.tex"
        assert len(payload["markers"]) == 1


# ---------------------------------------------------------------------------
# AC: resolving a marker (replacing it with the real value) clears the gate
# ---------------------------------------------------------------------------


class TestResolution:
    def test_replacing_marker_with_real_value_clears_gate(self, tmp_path: Path) -> None:
        version_dir = make_memo_version_dir(tmp_path, PENDING_BODY)
        assert not check_pending_markers(version_dir).passed()
        resolved_body = PENDING_BODY.replace(
            "[PENDING benchmark-run-2024-11]", "94.2%"
        ).replace("[PENDING: vendor-quote-acme]", "$1.42")
        (version_dir / "acme-seed.md").write_text(resolved_body, encoding="utf-8")
        assert check_pending_markers(version_dir).passed()
