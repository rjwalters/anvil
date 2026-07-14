"""Unit tests for ``anvil/lib/render_gate.py``.

These tests stub the toolchain (pdfinfo + log files) so the suite runs in
CI without LaTeX or poppler. The per-skill integration smoke tests live
under each skill's own ``tests/`` dir and skip when the engine is absent.

Test filename is distinct from other ``tests/lib/test_*`` modules per #58.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.lib.render_gate import (
    COMPILE_FAILED,
    COMPILE_OK,
    COMPILE_SKIPPED,
    COMPILE_UNAVAILABLE,
    DEFAULT_PLACEHOLDER_PATTERNS,
    DIM_COMPILE,
    DIM_EMBEDDED_IMAGES,
    DIM_GLYPH_VERIFICATION,
    DIM_OVERFULL,
    DIM_PAGE_FIT,
    DIM_PLACEHOLDERS,
    GATE_NAME,
    GateFinding,
    GateResult,
    compile_and_gate,
    gate,
)
from anvil.lib.review_schema import Kind, Review


FIXTURES = Path(__file__).parent / "fixtures" / "render_gate"


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def fake_pdfinfo_3pages_path() -> str:
    """Path to a fake pdfinfo executable that always reports 3 pages."""
    p = FIXTURES / "fake_pdfinfo_3pages.sh"
    assert p.exists(), f"missing fixture: {p}"
    return str(p)


@pytest.fixture
def fake_pdfinfo_50pages_path() -> str:
    p = FIXTURES / "fake_pdfinfo_50pages.sh"
    assert p.exists(), f"missing fixture: {p}"
    return str(p)


@pytest.fixture
def empty_pdf(tmp_path) -> Path:
    """A non-empty but content-free file masquerading as a PDF.

    The gate only ever inspects this via pdfinfo (which we stub) or
    ``Path.exists()``; the file's bytes are never parsed by the gate
    itself.
    """
    p = tmp_path / "fake.pdf"
    p.write_bytes(b"%PDF-1.5\n%fake fixture\n")
    return p


@pytest.fixture
def overfull_clean_log() -> Path:
    return FIXTURES / "overfull_clean.txt"


@pytest.fixture
def overfull_dirty_log() -> Path:
    return FIXTURES / "overfull_dirty.txt"


@pytest.fixture
def overfull_sphere_canary_log() -> Path:
    """Sphere-canary regression fixture (issue #572).

    Mirrors the filed-provisional defect's exact shape: 12 ``Overfull
    \\hbox`` + 1 ``Overfull \\vbox``, worst case 83.6pt. The legal
    artifact reached FILING-READY because no audit/finalize-time render
    gate ran; this fixture exists so future threshold drift cannot
    silently re-open the hole.
    """
    return FIXTURES / "overfull_sphere_canary.txt"


@pytest.fixture
def overfull_multipass_log() -> Path:
    """Multi-pass concatenation regression fixture (issue #668).

    Simulates ``pub-audit``'s ``compile-log.txt``: a full
    ``pdflatex → bibtex → pdflatex → pdflatex`` cycle where three of the
    four invocations re-emit the same overfull warnings. 6 unique boxes
    (4 hbox + 2 vbox, all above the 5.0pt default threshold) each appear
    3 times → 18 raw regex matches that must dedupe to 6 hits.
    """
    return FIXTURES / "overfull_multipass.txt"


@pytest.fixture
def overfull_lineless_log() -> Path:
    """Line-less warnings fixture (issue #668 edge case).

    Three distinct overfull warnings whose text lacks an ``at line(s) N``
    span (alignment / ``\\output is active`` variants), so the regex
    line-span group is ``None``. These must NOT collapse into one hit.
    """
    return FIXTURES / "overfull_lineless.txt"


@pytest.fixture
def overfull_same_line_diff_amount_log() -> Path:
    """Same-line, different-amount fixture (issue #668 edge case).

    Two hits at the same source line (88) with different amounts
    (11.2pt, 37.5pt) — the dedupe key is the full ``(line, amount_pt,
    kind)`` tuple, so these are two distinct hits, not one.
    """
    return FIXTURES / "overfull_same_line_diff_amount.txt"


@pytest.fixture
def compile_failure_log() -> Path:
    return FIXTURES / "compile_failure.txt"


@pytest.fixture
def placeholder_source() -> Path:
    return FIXTURES / "placeholder_source.tex"


@pytest.fixture
def clean_source() -> Path:
    return FIXTURES / "clean_source.tex"


# -----------------------------------------------------------------------------
# Page-cap gate
# -----------------------------------------------------------------------------


def test_page_count_at_cap_passes(empty_pdf, fake_pdfinfo_3pages_path):
    """Page count exactly at cap → passes."""
    r = gate(
        empty_pdf,
        page_cap=3,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    assert r.pages == 3
    assert r.page_cap == 3
    assert r.passed is True
    assert DIM_PAGE_FIT not in r.failed_gates


def test_page_count_over_cap_fails(empty_pdf, fake_pdfinfo_3pages_path):
    """Page count over cap → fails with a reason mentioning page count."""
    r = gate(
        empty_pdf,
        page_cap=2,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    assert r.pages == 3
    assert r.passed is False
    assert DIM_PAGE_FIT in r.failed_gates
    assert any(DIM_PAGE_FIT in reason and "3 pages" in reason for reason in r.reasons)


def test_page_cap_none_skips(empty_pdf, fake_pdfinfo_50pages_path):
    """50-page PDF with ``page_cap=None`` passes; pages still recorded."""
    r = gate(
        empty_pdf,
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_50pages_path,
    )
    assert r.pages == 50  # informational
    assert r.page_cap is None
    assert r.passed is True
    assert DIM_PAGE_FIT not in r.failed_gates


# -----------------------------------------------------------------------------
# Overfull-box gate
# -----------------------------------------------------------------------------


def test_overfull_hbox_under_threshold(
    empty_pdf, fake_pdfinfo_3pages_path, overfull_clean_log
):
    """``Overfull \\hbox (3.2pt)`` with threshold 5.0 → no finding."""
    r = gate(
        empty_pdf,
        log_path=overfull_clean_log,
        page_cap=None,
        overfull_threshold_pt=5.0,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    assert r.overfull_boxes == []
    assert DIM_OVERFULL not in r.failed_gates


def test_overfull_hbox_over_threshold(
    empty_pdf, fake_pdfinfo_3pages_path, overfull_dirty_log
):
    """``Overfull \\hbox (12.3pt)`` → one finding, gate fails."""
    r = gate(
        empty_pdf,
        log_path=overfull_dirty_log,
        page_cap=None,
        overfull_threshold_pt=5.0,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    # The dirty log has two over-threshold hits: 12.3pt hbox and 8.7pt vbox.
    # The 3.5pt hbox is below threshold and excluded.
    assert len(r.overfull_boxes) == 2
    assert r.passed is False
    assert DIM_OVERFULL in r.failed_gates
    kinds = {box["kind"] for box in r.overfull_boxes}
    assert kinds == {"hbox", "vbox"}


def test_overfull_vbox_parsing(empty_pdf, fake_pdfinfo_3pages_path, overfull_dirty_log):
    """Vbox lines are parsed alongside hbox lines."""
    r = gate(
        empty_pdf,
        log_path=overfull_dirty_log,
        page_cap=None,
        overfull_threshold_pt=5.0,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    vboxes = [b for b in r.overfull_boxes if b["kind"] == "vbox"]
    assert len(vboxes) == 1
    assert vboxes[0]["amount_pt"] == pytest.approx(8.7)


def test_overfull_line_span_extraction(
    empty_pdf, fake_pdfinfo_3pages_path, overfull_dirty_log
):
    """``at lines 42--45`` is captured into ``line``."""
    r = gate(
        empty_pdf,
        log_path=overfull_dirty_log,
        page_cap=None,
        overfull_threshold_pt=5.0,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    hbox = next(b for b in r.overfull_boxes if b["kind"] == "hbox")
    assert hbox["line"] == 42


def test_overfull_sphere_canary_shape(
    empty_pdf, fake_pdfinfo_3pages_path, overfull_sphere_canary_log
):
    """Sphere-canary regression fixture: 12 hbox + 1 vbox, worst 83.6pt.

    This is the exact defect shape that reached a filed provisional
    (issue #572): the entire review pipeline was text-content-based and
    never inspected the LaTeX log. The gate, given the canary's compile
    log, MUST flag the defect — at the framework default 5.0pt threshold
    (12 of 13 hits survive; the 4.21pt hit is cosmetic) AND at the
    tightened ip-skill 2.0pt threshold (all 13 hits survive). Both must
    produce ``passed=False`` and the ``render_gate_overfull_boxes``
    critical flag the audit + finalize backstop relies on.
    """
    # At the framework default 5.0pt threshold, the 4.21pt hit is
    # cosmetic and the other 12 fire.
    r_default = gate(
        empty_pdf,
        log_path=overfull_sphere_canary_log,
        page_cap=None,
        overfull_threshold_pt=5.0,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    assert len(r_default.overfull_boxes) == 12
    assert r_default.passed is False
    assert DIM_OVERFULL in r_default.failed_gates
    # Worst-case amount is the canary's 83.6pt.
    max_amount = max(b["amount_pt"] for b in r_default.overfull_boxes)
    assert max_amount == pytest.approx(83.6)
    assert max_amount >= 80.0
    # Both hbox and vbox kinds present (12 hbox + 1 vbox total — the
    # vbox is 18.7pt, well above the 5.0pt threshold).
    kinds = {b["kind"] for b in r_default.overfull_boxes}
    assert kinds == {"hbox", "vbox"}
    # The critical flag is the load-bearing signal the audit + finalize
    # backstop reads — verify the typed Review carries it.
    rev = r_default.to_review(version_dir="canary.1", critic_id="render-gate")
    flag_types = {cf.type for cf in rev.critical_flags}
    assert f"render_gate_{DIM_OVERFULL}" in flag_types

    # At the tightened ip-skill 2.0pt threshold (the legal-artifact
    # calibration from issue #572's curated scope), ALL 13 canary hits
    # fire — the 4.21pt hit is no longer cosmetic.
    r_ip = gate(
        empty_pdf,
        log_path=overfull_sphere_canary_log,
        page_cap=None,
        overfull_threshold_pt=2.0,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    assert len(r_ip.overfull_boxes) == 13
    assert r_ip.passed is False
    assert DIM_OVERFULL in r_ip.failed_gates


def test_overfull_multipass_log_deduplicates(
    empty_pdf, fake_pdfinfo_3pages_path, overfull_multipass_log
):
    """Multi-pass log dedupe regression (issue #668): 18 raw hits → 6 unique.

    ``pub-audit`` concatenates the full ``pdflatex → bibtex → pdflatex →
    pdflatex`` cycle into one ``compile-log.txt``; three ``pdflatex``
    passes re-emit the same 6 overfull warnings, so a flat regex scan
    finds 18 matches for 6 real boxes (the exact 18-vs-6 canary from
    tractatus v2). The parser must dedupe by ``(line, amount_pt, kind)``
    down to 6, and ``gate()``'s failure reason must report 6, not 18.
    """
    r = gate(
        empty_pdf,
        log_path=overfull_multipass_log,
        page_cap=None,
        overfull_threshold_pt=5.0,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    # 6 unique boxes despite each appearing 3 times in the concatenated log.
    assert len(r.overfull_boxes) == 6
    # Verdict is presence-based and unaffected: still fails, still flags.
    assert r.passed is False
    assert DIM_OVERFULL in r.failed_gates
    # 4 hbox + 2 vbox after dedupe.
    kinds = [b["kind"] for b in r.overfull_boxes]
    assert kinds.count("hbox") == 4
    assert kinds.count("vbox") == 2
    # First occurrence wins → line/amount reflect the first pass's text.
    lines = sorted(b["line"] for b in r.overfull_boxes)
    assert lines == [42, 77, 118, 203, 260, 331]
    # The reviser-facing reason string reports the deduped count, not 18.
    overfull_reason = next(
        reason for reason in r.reasons if DIM_OVERFULL in reason
    )
    assert "6 overfull box(es)" in overfull_reason
    assert "18 overfull box(es)" not in overfull_reason
    # One GateFinding per unique box (not per raw regex match).
    overfull_findings = [f for f in r.findings if f.gate == DIM_OVERFULL]
    assert len(overfull_findings) == 6


def test_overfull_lineless_hits_not_collapsed(
    empty_pdf, fake_pdfinfo_3pages_path, overfull_lineless_log
):
    """Line-less warnings survive as distinct hits (issue #668 edge case).

    Overfull warnings without an ``at line(s) N`` span capture ``line ==
    None``. The dedupe must NOT collapse all line-less hits into one — a
    genuinely line-less log with several distinct warnings would otherwise
    degenerate to a single entry.
    """
    r = gate(
        empty_pdf,
        log_path=overfull_lineless_log,
        page_cap=None,
        overfull_threshold_pt=5.0,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    # All three distinct line-less warnings survive.
    assert len(r.overfull_boxes) == 3
    assert all(b["line"] is None for b in r.overfull_boxes)
    assert r.passed is False
    assert DIM_OVERFULL in r.failed_gates


def test_overfull_same_line_diff_amount_not_deduped(
    empty_pdf, fake_pdfinfo_3pages_path, overfull_same_line_diff_amount_log
):
    """Same line, different amount → two hits (issue #668 edge case).

    The dedupe key is the full ``(line, amount_pt, kind)`` tuple, not
    ``line`` alone: two hits at line 88 with 11.2pt and 37.5pt are
    distinct and must both survive.
    """
    r = gate(
        empty_pdf,
        log_path=overfull_same_line_diff_amount_log,
        page_cap=None,
        overfull_threshold_pt=5.0,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    assert len(r.overfull_boxes) == 2
    assert {b["line"] for b in r.overfull_boxes} == {88}
    amounts = sorted(b["amount_pt"] for b in r.overfull_boxes)
    assert amounts == pytest.approx([11.2, 37.5])


# -----------------------------------------------------------------------------
# Compile gate
# -----------------------------------------------------------------------------


def test_compile_failure_skips_pdf_gates(
    tmp_path, fake_pdfinfo_3pages_path, compile_failure_log, placeholder_source
):
    """Non-zero compile exit → PDF gates skip cleanly; source placeholders
    still scanned.

    The PDF file does not exist (failed compile). The gate should:
    - set compile_status='failed'
    - record an actionable compile finding
    - NOT crash on the missing PDF; page-fit and overfull checks degrade
    - still scan the source for placeholders.
    """
    missing_pdf = tmp_path / "never_written.pdf"
    assert not missing_pdf.exists()
    r = gate(
        missing_pdf,
        log_path=compile_failure_log,
        source_paths=[placeholder_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        compile_status=COMPILE_FAILED,
        compile_exit_code=1,
    )
    assert r.compile_status == COMPILE_FAILED
    assert r.compile_exit_code == 1
    assert DIM_COMPILE in r.failed_gates
    # Source placeholder gate still ran.
    assert DIM_PLACEHOLDERS in r.failed_gates
    assert any("Undefined control sequence" in f.message for f in r.findings)
    assert r.passed is False


def test_compile_skipped_for_existing_pdf(
    empty_pdf, fake_pdfinfo_3pages_path, overfull_clean_log
):
    """When the caller passes a pre-built PDF and no compile_status, the
    status defaults to COMPILE_SKIPPED and the compile gate does not fail.
    """
    r = gate(
        empty_pdf,
        log_path=overfull_clean_log,
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    assert r.compile_status == COMPILE_SKIPPED
    assert DIM_COMPILE not in r.failed_gates


def test_compile_missing_pdf_no_status(tmp_path):
    """PDF doesn't exist and caller didn't supply compile_status → gate
    treats this as a compile failure (the PDF was supposed to exist)."""
    missing = tmp_path / "ghost.pdf"
    r = gate(missing, page_cap=None)
    assert r.compile_status == COMPILE_FAILED
    assert DIM_COMPILE in r.failed_gates
    assert r.passed is False


# -----------------------------------------------------------------------------
# Placeholder gate
# -----------------------------------------------------------------------------


def test_placeholder_default_patterns(
    empty_pdf, fake_pdfinfo_3pages_path, placeholder_source
):
    """Source containing TODO, [TBD], (figure), .MISSING → multiple hits."""
    r = gate(
        empty_pdf,
        source_paths=[placeholder_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    # Defaults include: TODO, [TBD], (figure), \includegraphics{...MISSING...},
    # and the bare .MISSING token. The fixture has at least one hit per
    # default pattern that maps cleanly.
    patterns_hit = {p["pattern"] for p in r.placeholders}
    assert r"\bTODO\b" in patterns_hit
    assert r"\[TBD\]" in patterns_hit
    assert r"\(figure\)" in patterns_hit
    assert r"\.MISSING\b" in patterns_hit
    assert DIM_PLACEHOLDERS in r.failed_gates
    assert r.passed is False


def test_placeholder_custom_patterns(
    empty_pdf, fake_pdfinfo_3pages_path, placeholder_source
):
    """Caller-supplied extras (ip-uspto style) are honored."""
    custom = DEFAULT_PLACEHOLDER_PATTERNS + (
        r"\\refnum\{\?\?\}",
        r"\\anvilpara\{\}",
    )
    r = gate(
        empty_pdf,
        source_paths=[placeholder_source],
        page_cap=None,
        placeholder_patterns=custom,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    patterns_hit = {p["pattern"] for p in r.placeholders}
    assert r"\\refnum\{\?\?\}" in patterns_hit
    assert r"\\anvilpara\{\}" in patterns_hit


def test_placeholder_clean_source_passes(
    empty_pdf, fake_pdfinfo_3pages_path, clean_source
):
    """Source with no placeholder matches → no findings."""
    r = gate(
        empty_pdf,
        source_paths=[clean_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    assert r.placeholders == []
    assert DIM_PLACEHOLDERS not in r.failed_gates


# -----------------------------------------------------------------------------
# Graceful degradation
# -----------------------------------------------------------------------------


def test_pdfinfo_unavailable_degrades_gracefully(
    empty_pdf, monkeypatch, overfull_clean_log
):
    """No pdfinfo on PATH → pages=None, gate continues with other checks."""
    import shutil

    real_which = shutil.which

    def fake_which(name: str, *args, **kwargs):
        if name == "pdfinfo":
            return None
        return real_which(name, *args, **kwargs)

    monkeypatch.setattr("anvil.lib.render_gate.shutil.which", fake_which)
    r = gate(
        empty_pdf,
        log_path=overfull_clean_log,
        page_cap=10,  # would fail-against if pdfinfo worked
        pdfinfo_path=None,
    )
    assert r.pages is None
    # No page-fit failure (because pages is None, we cannot evaluate).
    assert DIM_PAGE_FIT not in r.failed_gates
    # Remediation message present.
    assert any(
        "poppler" in reason.lower() or "pdfinfo not on path" in reason.lower()
        for reason in r.reasons
    )


def test_log_missing_degrades_gracefully(empty_pdf, fake_pdfinfo_3pages_path, tmp_path):
    """No log file → overfull gate skips with a reason, others still run."""
    nowhere = tmp_path / "ghost.log"
    r = gate(
        empty_pdf,
        log_path=nowhere,
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    assert r.overfull_boxes == []
    assert DIM_OVERFULL not in r.failed_gates
    assert any("compile log not available" in reason for reason in r.reasons)


def test_pandoc_engine_skips_overfull(
    empty_pdf, fake_pdfinfo_3pages_path, overfull_dirty_log
):
    """When engine=='pandoc', overfull gate is skipped with a documented note."""
    r = gate(
        empty_pdf,
        log_path=overfull_dirty_log,
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        engine="pandoc",
    )
    assert r.overfull_boxes == []
    assert DIM_OVERFULL not in r.failed_gates
    assert any("engine is pandoc" in reason for reason in r.reasons)


# -----------------------------------------------------------------------------
# Shape: to_json + to_review
# -----------------------------------------------------------------------------


def test_to_json_shape(empty_pdf, fake_pdfinfo_3pages_path, overfull_clean_log):
    """JSON shape matches the issue body's contract."""
    r = gate(
        empty_pdf,
        log_path=overfull_clean_log,
        page_cap=10,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    j = r.to_json()
    required_keys = {
        "gate",
        "pages",
        "page_cap",
        "overfull_boxes",
        "compile",
        "placeholders",
        "pass",
        "reasons",
    }
    assert required_keys.issubset(j.keys())
    assert j["gate"] == GATE_NAME
    assert isinstance(j["compile"], dict)
    assert "status" in j["compile"] and "exit_code" in j["compile"]
    # JSON-roundtripable.
    encoded = json.dumps(j)
    decoded = json.loads(encoded)
    assert decoded["pass"] is True
    assert decoded["pages"] == 3


def test_to_review_shape_pass(empty_pdf, fake_pdfinfo_3pages_path, overfull_clean_log):
    """Passing gate → Review with kind=TOOL_EVIDENCE, no critical flags."""
    r = gate(
        empty_pdf,
        log_path=overfull_clean_log,
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    rev = r.to_review(version_dir="test.1", critic_id="test-gate")
    assert rev.kind == Kind.TOOL_EVIDENCE
    assert rev.version_dir == "test.1"
    assert rev.critic_id == "test-gate"
    assert rev.critical_flags == []
    # Scorecard is non-empty (schema requires it) but null-scored.
    assert len(rev.scores) >= 1
    assert all(s.score is None for s in rev.scores)
    # Round-trip via the pydantic model_dump → model_validate.
    rev2 = Review.model_validate(rev.model_dump())
    assert rev2.critical_flags == []


def test_to_review_shape_fail(
    empty_pdf, fake_pdfinfo_3pages_path, overfull_dirty_log
):
    """Failing gates → one CriticalFlag per failed gate dimension."""
    r = gate(
        empty_pdf,
        log_path=overfull_dirty_log,
        page_cap=2,  # under the fake 3-page count
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    assert r.passed is False
    rev = r.to_review(version_dir="test.1", critic_id="test-gate")
    types = {cf.type for cf in rev.critical_flags}
    # page-fit and overfull both failed; one CriticalFlag each.
    assert f"render_gate_{DIM_PAGE_FIT}" in types
    assert f"render_gate_{DIM_OVERFULL}" in types
    # Schema round-trip (validates the kind=tool_evidence constraint:
    # findings carry tool_calls=[]).
    rev2 = Review.model_validate(rev.model_dump())
    assert len(rev2.critical_flags) == len(rev.critical_flags)


def test_to_review_tool_evidence_requires_tool_calls(
    empty_pdf, fake_pdfinfo_3pages_path, overfull_dirty_log
):
    """Every Finding on a TOOL_EVIDENCE review has tool_calls (the schema
    enforces this; empty list is permitted)."""
    r = gate(
        empty_pdf,
        log_path=overfull_dirty_log,
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
    )
    rev = r.to_review(version_dir="test.1", critic_id="test-gate")
    assert all(f.tool_calls is not None for f in rev.findings)


# -----------------------------------------------------------------------------
# Independence: all gates run, no short-circuit
# -----------------------------------------------------------------------------


def test_all_gates_run_independently(
    tmp_path, fake_pdfinfo_3pages_path, overfull_dirty_log, placeholder_source
):
    """Fixture failing 3 of 4 gates → ``reasons`` has at least 3 distinct
    gate prefixes (compile + overfull + placeholders); page-fit passes."""
    missing_pdf = tmp_path / "never.pdf"
    r = gate(
        missing_pdf,
        log_path=overfull_dirty_log,
        source_paths=[placeholder_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        # Compile failed (caller-declared); but the gate also tries to read
        # the log file for overfull boxes, and scan the .tex source.
        compile_status=COMPILE_FAILED,
        compile_exit_code=1,
    )
    # The PDF is missing — but log + sources are still parsed.
    assert DIM_COMPILE in r.failed_gates
    assert DIM_OVERFULL in r.failed_gates
    assert DIM_PLACEHOLDERS in r.failed_gates
    # page-fit didn't fail (pages=None because missing PDF; the gate
    # gracefully sets failed=No for the dimension).
    assert DIM_PAGE_FIT not in r.failed_gates
    # reasons has at least 3 distinct gate prefixes.
    prefixes = {r_.split(":", 1)[0] for r_ in r.reasons}
    assert {DIM_COMPILE, DIM_OVERFULL, DIM_PLACEHOLDERS}.issubset(prefixes)


# -----------------------------------------------------------------------------
# compile_and_gate: engine unavailable + smoke
# -----------------------------------------------------------------------------


def test_compile_and_gate_engine_unavailable(tmp_path):
    """When the engine is not on PATH, returns COMPILE_UNAVAILABLE without
    crashing."""
    tex = tmp_path / "foo.tex"
    tex.write_text(r"\documentclass{article}\begin{document}hi\end{document}")
    r = compile_and_gate(tex, engine="this-engine-does-not-exist-anywhere")
    assert r.compile_status == COMPILE_UNAVAILABLE
    # Engine-unavailable does NOT itself flag DIM_COMPILE as failed (we
    # don't want every reviewer-machine without LaTeX to fail every gate);
    # the operator-facing message is in `reasons`.
    assert any(
        "engine not on PATH" in reason or "this-engine-does-not-exist-anywhere" in reason
        for reason in r.reasons
    )


def test_compile_and_gate_real_compile_if_available(tmp_path):
    """Smoke: if xelatex IS on PATH, the gate compiles a minimal .tex and
    reports a real page count. Skipped otherwise."""
    import shutil

    if shutil.which("xelatex") is None or shutil.which("pdfinfo") is None:
        pytest.skip("xelatex / pdfinfo not on PATH; skipping real-compile smoke")
    tex = tmp_path / "hello.tex"
    tex.write_text(
        r"""\documentclass{article}
\begin{document}
Hello, render-gate.
\end{document}
"""
    )
    r = compile_and_gate(tex, engine="xelatex", page_cap=2)
    assert r.compile_status == COMPILE_OK
    assert r.pages == 1
    assert r.passed is True


# -----------------------------------------------------------------------------
# GateResult.to_critical_flags directly
# -----------------------------------------------------------------------------


def test_critical_flag_order_is_stable():
    """``to_critical_flags`` emits dimensions in a stable order: page_fit,
    overfull_boxes, compile, placeholders."""
    res = GateResult(
        pdf_path="x",
        log_path=None,
        pages=None,
        page_cap=None,
        overfull_boxes=[],
        overfull_threshold_pt=5.0,
        compile_status=COMPILE_FAILED,
        compile_exit_code=1,
        placeholders=[],
        findings=[
            GateFinding(gate=DIM_COMPILE, severity="error", message="boom"),
            GateFinding(gate=DIM_PLACEHOLDERS, severity="error", message="TODO"),
            GateFinding(gate=DIM_PAGE_FIT, severity="error", message="overflow"),
        ],
        passed=False,
        reasons=[
            f"{DIM_PAGE_FIT}: too many pages",
            f"{DIM_COMPILE}: exit 1",
            f"{DIM_PLACEHOLDERS}: TODO",
        ],
        failed_gates={DIM_COMPILE, DIM_PLACEHOLDERS, DIM_PAGE_FIT},
    )
    flags = res.to_critical_flags()
    types = [f.type for f in flags]
    assert types == [
        f"render_gate_{DIM_PAGE_FIT}",
        f"render_gate_{DIM_COMPILE}",
        f"render_gate_{DIM_PLACEHOLDERS}",
    ]


# -----------------------------------------------------------------------------
# Glyph verification (issue #692) — source-driven non-ASCII sweep vs pdftotext
# -----------------------------------------------------------------------------


@pytest.fixture
def stix_glyph_drop_source() -> Path:
    """Source body containing ≠ (U+2260) ×3 and × (U+00D7) ×1 (issue #692)."""
    p = FIXTURES / "stix_glyph_drop_source.md"
    assert p.exists(), f"missing fixture: {p}"
    return p


@pytest.fixture
def fake_pdftotext_stix_drop() -> str:
    """Stub pdftotext whose extraction dropped ≠ (STIX Two Text regression)."""
    p = FIXTURES / "fake_pdftotext_stix_drop.sh"
    assert p.exists(), f"missing fixture: {p}"
    return str(p)


@pytest.fixture
def fake_pdftotext_clean() -> str:
    """Stub pdftotext whose extraction preserves every source glyph."""
    p = FIXTURES / "fake_pdftotext_clean.sh"
    assert p.exists(), f"missing fixture: {p}"
    return str(p)


def test_glyph_drop_stix_regression_pin(
    empty_pdf, fake_pdfinfo_3pages_path, stix_glyph_drop_source, fake_pdftotext_stix_drop
):
    """Regression-pin the STIX Two Text ≠ (U+2260) silent glyph drop (#692).

    The source references ≠ three times; the (stubbed) pdftotext extraction
    has it zero times — the exact botho-canary shape where a hardcoded
    allow-list "verified" the known glyphs and shipped a PDF missing ≠. The
    source-driven sweep MUST flag it as an error and fail the gate.
    """
    r = gate(
        empty_pdf,
        source_paths=[stix_glyph_drop_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        pdftotext_path=fake_pdftotext_stix_drop,
        compile_status=COMPILE_SKIPPED,
    )
    assert DIM_GLYPH_VERIFICATION in r.failed_gates
    assert r.passed is False
    glyph_findings = [f for f in r.findings if f.gate == DIM_GLYPH_VERIFICATION]
    assert len(glyph_findings) == 1
    # The finding names the exact dropped codepoint (U+2260), and only it —
    # × (U+00D7) survived, so it must NOT be flagged.
    assert "U+2260" in glyph_findings[0].message
    assert "U+00D7" not in glyph_findings[0].message
    # The typed Review carries the blocking critical flag.
    rev = r.to_review(version_dir="botho.2", critic_id="render-gate")
    flag_types = {cf.type for cf in rev.critical_flags}
    assert f"render_gate_{DIM_GLYPH_VERIFICATION}" in flag_types


def test_glyph_verification_clean_render_passes(
    empty_pdf, fake_pdfinfo_3pages_path, stix_glyph_drop_source, fake_pdftotext_clean
):
    """A clean render (all source non-ASCII survive at >= source count) passes
    the glyph gate with zero findings."""
    r = gate(
        empty_pdf,
        source_paths=[stix_glyph_drop_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        pdftotext_path=fake_pdftotext_clean,
        compile_status=COMPILE_SKIPPED,
    )
    assert DIM_GLYPH_VERIFICATION not in r.failed_gates
    assert not [f for f in r.findings if f.gate == DIM_GLYPH_VERIFICATION]


@pytest.fixture
def nbsp_only_source() -> Path:
    """Source whose only non-ASCII is a stray U+00A0 NBSP (issue #692)."""
    p = FIXTURES / "nbsp_only_source.md"
    assert p.exists(), f"missing fixture: {p}"
    return p


@pytest.fixture
def fake_pdftotext_nbsp_normalized() -> str:
    """Stub pdftotext that normalized the source NBSP to an ASCII space."""
    p = FIXTURES / "fake_pdftotext_nbsp_normalized.sh"
    assert p.exists(), f"missing fixture: {p}"
    return str(p)


@pytest.fixture
def url_only_nonascii_source() -> Path:
    """Source whose non-ASCII lives only in URL targets / comments (issue #692)."""
    p = FIXTURES / "url_only_nonascii_source.md"
    assert p.exists(), f"missing fixture: {p}"
    return p


@pytest.fixture
def fake_pdftotext_url_only() -> str:
    """Stub pdftotext whose body text carries no non-ASCII (URLs not rendered)."""
    p = FIXTURES / "fake_pdftotext_url_only.sh"
    assert p.exists(), f"missing fixture: {p}"
    return str(p)


def test_glyph_verification_nbsp_normalized_passes(
    empty_pdf, fake_pdfinfo_3pages_path, nbsp_only_source, fake_pdftotext_nbsp_normalized
):
    """A stray Unicode NBSP (U+00A0) that pdftotext normalizes to an ASCII space
    must NOT trip the glyph gate (issue #692 false-positive vector 1).

    Whitespace normalization is not the glyph-drop failure mode the sweep
    guards against — Zs-category codepoints are excluded on both sides.
    """
    r = gate(
        empty_pdf,
        source_paths=[nbsp_only_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        pdftotext_path=fake_pdftotext_nbsp_normalized,
        compile_status=COMPILE_SKIPPED,
    )
    assert DIM_GLYPH_VERIFICATION not in r.failed_gates
    assert not [f for f in r.findings if f.gate == DIM_GLYPH_VERIFICATION]


def test_glyph_verification_url_only_nonascii_passes(
    empty_pdf, fake_pdfinfo_3pages_path, url_only_nonascii_source, fake_pdftotext_url_only
):
    """Non-ASCII living only in a link/image URL target, HTML comment, or
    autolink must NOT trip the glyph gate (issue #692 false-positive vector 2).

    Those glyphs are counted in the raw source but never reach the rendered
    body, so the source sweep excludes non-rendered regions before counting.
    """
    r = gate(
        empty_pdf,
        source_paths=[url_only_nonascii_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        pdftotext_path=fake_pdftotext_url_only,
        compile_status=COMPILE_SKIPPED,
    )
    assert DIM_GLYPH_VERIFICATION not in r.failed_gates
    assert not [f for f in r.findings if f.gate == DIM_GLYPH_VERIFICATION]


def test_glyph_verification_skips_gracefully_when_pdftotext_absent(
    empty_pdf, fake_pdfinfo_3pages_path, stix_glyph_drop_source, monkeypatch
):
    """pdftotext absent → glyph check skips (breadcrumb in reasons), does not
    raise, does not fail the gate."""
    # Force pdftotext resolution to miss (no override, which() returns None).
    import anvil.lib.render_gate as rg

    real_which = rg.shutil.which

    def which_no_pdftotext(name):
        return None if name == "pdftotext" else real_which(name)

    monkeypatch.setattr(rg.shutil, "which", which_no_pdftotext)
    r = gate(
        empty_pdf,
        source_paths=[stix_glyph_drop_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        compile_status=COMPILE_SKIPPED,
    )
    assert DIM_GLYPH_VERIFICATION not in r.failed_gates
    assert any(
        r_.startswith(f"{DIM_GLYPH_VERIFICATION}:") and "pdftotext" in r_
        for r_ in r.reasons
    )


# -----------------------------------------------------------------------------
# Embedded-image assertion (issue #692) — body refs vs pdfimages -list
# -----------------------------------------------------------------------------


@pytest.fixture
def two_image_refs_source() -> Path:
    """Body referencing two ``![…](exhibits/…png)`` figures (issue #692)."""
    p = FIXTURES / "two_image_refs_source.md"
    assert p.exists(), f"missing fixture: {p}"
    return p


@pytest.fixture
def fake_pdfimages_zero() -> str:
    """Stub ``pdfimages -list`` reporting ZERO embedded images (botho v2)."""
    p = FIXTURES / "fake_pdfimages_zero.sh"
    assert p.exists(), f"missing fixture: {p}"
    return str(p)


@pytest.fixture
def fake_pdfimages_two() -> str:
    """Stub ``pdfimages -list`` reporting two embedded images."""
    p = FIXTURES / "fake_pdfimages_two.sh"
    assert p.exists(), f"missing fixture: {p}"
    return str(p)


def test_embedded_images_zero_regression_pin(
    empty_pdf, fake_pdfinfo_3pages_path, two_image_refs_source, fake_pdfimages_zero
):
    """Regression-pin the botho v2 zero-embedded-image failure (#692).

    The body references two figures; the (stubbed) ``pdfimages -list`` reports
    zero embedded images — the exact shape where every other gate was green
    (placeholder scan clean, compile clean, glyphs "verified") yet the PDF
    shipped with no figures. The embedded-image assertion MUST fail the gate.
    """
    r = gate(
        empty_pdf,
        source_paths=[two_image_refs_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        pdfimages_path=fake_pdfimages_zero,
        compile_status=COMPILE_SKIPPED,
    )
    assert DIM_EMBEDDED_IMAGES in r.failed_gates
    assert r.passed is False
    embed_findings = [f for f in r.findings if f.gate == DIM_EMBEDDED_IMAGES]
    assert len(embed_findings) == 1
    assert "2" in embed_findings[0].message and "0" in embed_findings[0].message
    rev = r.to_review(version_dir="botho.2", critic_id="render-gate")
    flag_types = {cf.type for cf in rev.critical_flags}
    assert f"render_gate_{DIM_EMBEDDED_IMAGES}" in flag_types


def test_embedded_images_matching_count_passes(
    empty_pdf, fake_pdfinfo_3pages_path, two_image_refs_source, fake_pdfimages_two
):
    """N body refs + N (or more) embedded images passes the gate."""
    r = gate(
        empty_pdf,
        source_paths=[two_image_refs_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        pdfimages_path=fake_pdfimages_two,
        compile_status=COMPILE_SKIPPED,
    )
    assert DIM_EMBEDDED_IMAGES not in r.failed_gates
    assert not [f for f in r.findings if f.gate == DIM_EMBEDDED_IMAGES]


def test_embedded_images_skips_gracefully_when_pdfimages_absent(
    empty_pdf, fake_pdfinfo_3pages_path, two_image_refs_source, monkeypatch
):
    """pdfimages absent → embedded-image check skips (breadcrumb), does not
    fail the gate solely due to missing tooling."""
    import anvil.lib.render_gate as rg

    real_which = rg.shutil.which

    def which_no_pdfimages(name):
        return None if name == "pdfimages" else real_which(name)

    monkeypatch.setattr(rg.shutil, "which", which_no_pdfimages)
    r = gate(
        empty_pdf,
        source_paths=[two_image_refs_source],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        compile_status=COMPILE_SKIPPED,
    )
    assert DIM_EMBEDDED_IMAGES not in r.failed_gates
    assert any(
        r_.startswith(f"{DIM_EMBEDDED_IMAGES}:") and "pdfimages" in r_
        for r_ in r.reasons
    )


def test_embedded_images_check_skipped_when_body_has_no_image_refs(
    empty_pdf, fake_pdfinfo_3pages_path, clean_source_no_refs, fake_pdfimages_zero
):
    """A body with zero ``![…]()`` refs never runs the embedded-image check —
    zero-figure threads must not fail on zero embedded images."""
    r = gate(
        empty_pdf,
        source_paths=[clean_source_no_refs],
        page_cap=None,
        pdfinfo_path=fake_pdfinfo_3pages_path,
        pdfimages_path=fake_pdfimages_zero,
        compile_status=COMPILE_SKIPPED,
    )
    assert DIM_EMBEDDED_IMAGES not in r.failed_gates
    assert not [f for f in r.findings if f.gate == DIM_EMBEDDED_IMAGES]


@pytest.fixture
def clean_source_no_refs(tmp_path) -> Path:
    """A prose body with no image references at all."""
    p = tmp_path / "prose.md"
    p.write_text("# A chapter\n\nAll prose, no figures here.\n", encoding="utf-8")
    return p
