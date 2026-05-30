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
    return FIXTURES / "overfull_clean.log"


@pytest.fixture
def overfull_dirty_log() -> Path:
    return FIXTURES / "overfull_dirty.log"


@pytest.fixture
def compile_failure_log() -> Path:
    return FIXTURES / "compile_failure.log"


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
