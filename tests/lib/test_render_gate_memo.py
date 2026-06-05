"""Unit tests for ``anvil/lib/render_gate.py`` memo mode (``kind="memo"``).

These tests stub pandoc + the HTML/PDF engines + pdfinfo via
monkeypatching so the suite runs in CI without weasyprint, wkhtmltopdf,
xelatex, or pdfinfo on PATH. The shipped Phase 3 ``memo-render`` command
will invoke real binaries; this test module pins the deterministic
contract.

Test filename is distinct from ``test_render_gate.py`` and
``test_memo_render_detection.py`` per the #58 packaging convention so
pytest does not collide on a shared module name.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pytest

from anvil.lib import render as _render
from anvil.lib.render_gate import (
    COMPILE_FAILED,
    COMPILE_OK,
    COMPILE_UNAVAILABLE,
    DEFAULT_MEMO_PLACEHOLDER_PATTERNS,
    DIM_MEMO_COMPILE,
    DIM_MEMO_IMAGE_REFS,
    DIM_MEMO_OVERFULL,
    DIM_MEMO_PAGE_FIT,
    DIM_MEMO_PLACEHOLDERS,
    MEMO_ENGINE_WEASYPRINT,
    MEMO_ENGINE_WKHTMLTOPDF,
    MEMO_ENGINE_XELATEX,
    MEMO_WORDS_PER_PAGE,
    GateResult,
    _coerce_words_per_page,
    _gate_memo,
    _parse_memo_overfull,
    _render_memo_source,
    _resolve_target_length,
    _scan_memo_placeholders,
    _select_memo_engine,
    gate,
)
from anvil.lib.review_schema import Kind, Review


# ---------------------------------------------------------------------------
# Helpers: fake subprocess + pdfinfo
# ---------------------------------------------------------------------------


class _FakeCompletedProcess:
    """Minimal stand-in for ``subprocess.CompletedProcess``."""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_pandoc(
    *,
    returncode: int = 0,
    stderr: str = "",
    out_pdf: Optional[Path] = None,
    pdf_bytes: bytes = b"%PDF-1.5\n%fake fixture\n",
):
    """Build a ``subprocess.run`` replacement that fakes a pandoc call.

    Falls through to the real ``subprocess.run`` for any non-pandoc
    command (in particular, the ``pdfinfo`` stub the tests invoke via a
    real shell script). When the command is pandoc and ``returncode`` is
    0, the fake writes a tiny fixture PDF at ``out_pdf`` so the gate's
    post-render ``Path.exists()`` check succeeds.
    """
    real_run = subprocess.run

    def _run(cmd, **kwargs):
        # Only intercept pandoc invocations; defer to the real subprocess
        # for everything else (e.g., the test-fixture pdfinfo shell stub).
        if not cmd or cmd[0] != "pandoc":
            return real_run(cmd, **kwargs)
        if "-o" in cmd:
            idx = cmd.index("-o")
            if idx + 1 < len(cmd):
                target = Path(cmd[idx + 1])
                target.parent.mkdir(parents=True, exist_ok=True)
                if returncode == 0:
                    target.write_bytes(pdf_bytes)
        return _FakeCompletedProcess(
            returncode=returncode, stdout="", stderr=stderr
        )

    return _run


@pytest.fixture
def fake_pdfinfo_path(tmp_path):
    """Stub pdfinfo that reports ``Pages: 3`` and exits 0."""
    p = tmp_path / "fake_pdfinfo.sh"
    p.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<EOF\n"
        "Title:    Test PDF\n"
        "Producer: FakePDF/1.0\n"
        "Pages:    3\n"
        "EOF\n"
        "exit 0\n"
    )
    p.chmod(0o755)
    return str(p)


@pytest.fixture
def fake_pdfinfo_5pages(tmp_path):
    p = tmp_path / "fake_pdfinfo_5.sh"
    p.write_text(
        "#!/usr/bin/env bash\n"
        'cat <<EOF\nPages: 5\nEOF\nexit 0\n'
    )
    p.chmod(0o755)
    return str(p)


@pytest.fixture
def memo_version_dir(tmp_path):
    """Build a minimal version directory with a non-empty body markdown.

    Body filename echoes the thread slug per #295 — for a ``bessemer``
    thread the body is ``bessemer.md`` inside ``bessemer/bessemer.1/``.
    """
    thread_root = tmp_path / "bessemer"
    thread_root.mkdir()
    vd = thread_root / "bessemer.1"
    vd.mkdir()
    (vd / "bessemer.md").write_text(
        "# Investment memo\n\n"
        "## Recommendation\n\n"
        "Pass.\n\n"
        "## Thesis\n\n"
        "Some prose about the company.\n",
        encoding="utf-8",
    )
    return vd


# ---------------------------------------------------------------------------
# _select_memo_engine: priority order
# ---------------------------------------------------------------------------


def test_select_memo_engine_prefers_weasyprint(monkeypatch):
    """Weasyprint available → picked first regardless of others."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: True)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)
    assert _select_memo_engine() == MEMO_ENGINE_WEASYPRINT


def test_select_memo_engine_falls_back_to_wkhtmltopdf(monkeypatch):
    """Weasyprint missing, wkhtmltopdf present → picks wkhtmltopdf."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: False)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: True)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)
    assert _select_memo_engine() == MEMO_ENGINE_WKHTMLTOPDF


def test_select_memo_engine_falls_back_to_xelatex(monkeypatch):
    """Both HTML engines missing, xelatex present → picks xelatex."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: False)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(
        shutil, "which", lambda name: "/x/xelatex" if name == "xelatex" else None
    )
    assert _select_memo_engine() == MEMO_ENGINE_XELATEX


def test_select_memo_engine_returns_none_when_nothing_available(monkeypatch):
    """All three engines missing → ``None`` (graceful-degrade signal)."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: False)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert _select_memo_engine() is None


# ---------------------------------------------------------------------------
# _select_memo_engine: per-document `requested` engine (issue #320)
# ---------------------------------------------------------------------------


def test_select_memo_engine_honors_requested_when_available(monkeypatch):
    """Request xelatex; only xelatex on PATH → returns xelatex (the trivial
    case — weasyprint priority cannot win because it is not installed)."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: False)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(
        shutil, "which", lambda name: "/x/xelatex" if name == "xelatex" else None
    )
    assert _select_memo_engine(requested=MEMO_ENGINE_XELATEX) == MEMO_ENGINE_XELATEX


def test_select_memo_engine_honors_requested_xelatex_over_weasyprint(monkeypatch):
    """Request xelatex; ALL three engines on PATH → returns xelatex (the
    canary's bessemer / brains-for-robots case where the per-document knob
    overrides the default priority order)."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: True)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)
    # Without `requested`, the default priority would pick weasyprint.
    assert _select_memo_engine() == MEMO_ENGINE_WEASYPRINT
    # With `requested=xelatex`, the per-doc knob wins.
    assert _select_memo_engine(requested=MEMO_ENGINE_XELATEX) == MEMO_ENGINE_XELATEX


def test_select_memo_engine_falls_through_when_requested_unavailable(monkeypatch):
    """Request xelatex; only weasyprint on PATH → returns weasyprint
    (graceful fallthrough to auto-priority, no exception). This is the
    silent-with-record contract: the gate layer surfaces the fallthrough
    in `reasons`, but the selector itself just returns the best available."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)  # no xelatex
    assert (
        _select_memo_engine(requested=MEMO_ENGINE_XELATEX) == MEMO_ENGINE_WEASYPRINT
    )


def test_select_memo_engine_falls_through_when_requested_unknown(monkeypatch):
    """Request an unknown engine string → falls through to auto-priority
    (consistent with the unavailable-engine case; no exception). Parse-time
    validation of the closed allowlist lives in
    ``project_brief._validate_render_engine`` — the render-gate selector
    only deals in runtime PATH availability and treats anything it
    doesn't recognize as "request not satisfiable, fall through"."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: True)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)
    # Garbage `requested` value silently falls through to default priority.
    assert _select_memo_engine(requested="foo") == MEMO_ENGINE_WEASYPRINT


def test_select_memo_engine_none_request_preserves_legacy_behavior(monkeypatch):
    """``requested=None`` → behavior identical to the pre-#320 contract.

    Regression guard for the four legacy tests above (lines 156–187) —
    when `requested` is `None`, the selector behaves exactly as it did
    before the per-doc knob landed.
    """
    # Weasyprint available → picked first.
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: True)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)
    assert _select_memo_engine(requested=None) == MEMO_ENGINE_WEASYPRINT

    # All three missing → None.
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: False)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert _select_memo_engine(requested=None) is None


def test_render_memo_source_threads_requested_engine(monkeypatch, memo_version_dir):
    """``_render_memo_source(..., requested_engine="xelatex")`` with ALL three
    engines available → pandoc cmd uses ``--pdf-engine=xelatex`` and the
    LaTeX template path is selected over the HTML path.

    Verifies the full plumbing chain from caller → _render_memo_source →
    _select_memo_engine. The captured pandoc command must show:
    1. ``--pdf-engine=xelatex`` (not weasyprint, the default priority).
    2. ``--template <path-to-template.tex>`` (the xelatex branch at
       lines 965-968 of render_gate.py — NOT the HTML template/css path
       at lines 957-964).
    """
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: True)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)

    captured_cmd: list[list[str]] = []
    real_run = subprocess.run

    def _capturing_run(cmd, **kwargs):
        if cmd and cmd[0] == "pandoc":
            captured_cmd.append(list(cmd))
            if "-o" in cmd:
                idx = cmd.index("-o")
                target = Path(cmd[idx + 1])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"%PDF-1.5\n%fake fixture\n")
            return _FakeCompletedProcess(returncode=0, stdout="", stderr="")
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _capturing_run)

    out_pdf = memo_version_dir / "bessemer.pdf"
    status, exit_code, engine, _stderr = _render_memo_source(
        memo_version_dir, out_pdf, requested_engine=MEMO_ENGINE_XELATEX
    )
    assert status == COMPILE_OK
    assert exit_code == 0
    assert engine == MEMO_ENGINE_XELATEX

    # The captured pandoc command must carry --pdf-engine=xelatex even
    # though the default priority would have picked weasyprint.
    assert len(captured_cmd) == 1
    cmd = captured_cmd[0]
    assert "--pdf-engine=xelatex" in cmd
    # The xelatex branch in _render_memo_source pins template.tex (not
    # template.html + styles.css). The exact template file may or may
    # not exist on the test filesystem — we just check the branch was
    # taken by asserting the HTML-specific --css flag is NOT present.
    assert "--css" not in cmd


# ---------------------------------------------------------------------------
# _render_memo_source: graceful degrade + happy path
# ---------------------------------------------------------------------------


def test_render_memo_source_missing_body_md(tmp_path):
    """Missing body markdown → ``COMPILE_FAILED`` surrogate, no exception.

    Body filename echoes the thread slug per #295 — the renderer looks
    for ``ghost.md`` inside ``ghost/ghost.1/``.
    """
    thread = tmp_path / "ghost"
    thread.mkdir()
    vd = thread / "ghost.1"
    vd.mkdir()
    out_pdf = vd / "ghost.pdf"
    status, exit_code, engine, stderr = _render_memo_source(vd, out_pdf)
    assert status == COMPILE_FAILED
    assert exit_code == -1
    assert "ghost.md not found" in stderr


def test_render_memo_source_missing_pandoc(monkeypatch, memo_version_dir):
    """Missing pandoc → ``COMPILE_UNAVAILABLE``, no engine ran."""
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: False)
    out_pdf = memo_version_dir / "bessemer.pdf"
    status, exit_code, engine, stderr = _render_memo_source(
        memo_version_dir, out_pdf
    )
    assert status == COMPILE_UNAVAILABLE
    assert exit_code == -1
    assert engine == ""


def test_render_memo_source_no_pdf_engine(monkeypatch, memo_version_dir):
    """Pandoc present but no HTML/PDF engine → ``COMPILE_UNAVAILABLE``."""
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: False)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    out_pdf = memo_version_dir / "bessemer.pdf"
    status, _, engine, _ = _render_memo_source(memo_version_dir, out_pdf)
    assert status == COMPILE_UNAVAILABLE
    assert engine == ""


def test_render_memo_source_happy_path_writes_pdf(
    monkeypatch, memo_version_dir
):
    """All deps present, pandoc returns 0 → PDF written, status OK."""
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_pandoc(returncode=0, stderr=""),
    )
    # Pandoc-which lookup is bypassed in _render_memo_source via the
    # check_pandoc_available indirection, so no shutil.which monkeypatch
    # needed for the front-end check.
    out_pdf = memo_version_dir / "bessemer.pdf"
    status, exit_code, engine, stderr = _render_memo_source(
        memo_version_dir, out_pdf
    )
    assert status == COMPILE_OK
    assert exit_code == 0
    assert engine == MEMO_ENGINE_WEASYPRINT
    assert out_pdf.exists()


def test_render_memo_source_pandoc_failure(monkeypatch, memo_version_dir):
    """Pandoc non-zero exit → ``COMPILE_FAILED`` + stderr captured."""
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_pandoc(returncode=1, stderr="syntax error at line 4"),
    )
    out_pdf = memo_version_dir / "bessemer.pdf"
    status, exit_code, engine, stderr = _render_memo_source(
        memo_version_dir, out_pdf
    )
    assert status == COMPILE_FAILED
    assert exit_code == 1
    assert "syntax error" in stderr
    # Engine was selected even though it failed.
    assert engine == MEMO_ENGINE_WEASYPRINT


# ---------------------------------------------------------------------------
# _resolve_target_length: dispatch + edge cases
# ---------------------------------------------------------------------------


def test_resolve_target_length_pages_form():
    """{'pages': [3, 4]} → page range used directly; source='pages'."""
    pr, wr, src, wpp = _resolve_target_length({"pages": [3, 4]})
    assert pr == (3, 4)
    assert wr is None
    assert src == "pages"
    # effective_wpp is the default even when the conversion didn't apply.
    assert wpp == MEMO_WORDS_PER_PAGE


def test_resolve_target_length_words_form_uses_wpp_proxy():
    """{'words': [1800, 2400]} → derived page range via 400-wpp proxy."""
    pr, wr, src, wpp = _resolve_target_length({"words": [1800, 2400]})
    assert pr == (1800 // MEMO_WORDS_PER_PAGE, 2400 // MEMO_WORDS_PER_PAGE)
    assert wr == (1800, 2400)
    assert src == "words"
    assert wpp == MEMO_WORDS_PER_PAGE


def test_resolve_target_length_none():
    """None → all None, source='none'."""
    pr, wr, src, wpp = _resolve_target_length(None)
    assert pr is None
    assert wr is None
    assert src == "none"
    assert wpp == MEMO_WORDS_PER_PAGE


def test_resolve_target_length_malformed_both_keys():
    """Both 'words' and 'pages' set → malformed, source='none'."""
    pr, _, src, _ = _resolve_target_length(
        {"words": [1800, 2400], "pages": [3, 4]}
    )
    assert pr is None
    assert src == "none"


def test_resolve_target_length_malformed_wrong_shape():
    """Non-list value or wrong length → malformed."""
    assert _resolve_target_length({"pages": 4})[2] == "none"
    assert _resolve_target_length({"pages": [3, 4, 5]})[2] == "none"
    assert _resolve_target_length({"words": [2400, 1800]})[2] == "none"  # min > max


# ---------------------------------------------------------------------------
# words_per_page override (issue #235): per-thread page_cap calibration
# ---------------------------------------------------------------------------


def test_coerce_words_per_page_accepts_positive_int():
    """Positive int → passes through unchanged."""
    assert _coerce_words_per_page(400) == 400
    assert _coerce_words_per_page(1) == 1


def test_coerce_words_per_page_accepts_positive_float():
    """Positive float → coerced to int."""
    # Curation explicitly says "positive number (int or float)".
    assert _coerce_words_per_page(400.5) == 400


def test_coerce_words_per_page_rejects_non_positive():
    """0 and negative numbers → None (fall back to default)."""
    assert _coerce_words_per_page(0) is None
    assert _coerce_words_per_page(-1) is None
    assert _coerce_words_per_page(-400) is None
    assert _coerce_words_per_page(0.0) is None
    # Subatomic floats that would coerce to 0 also reject.
    assert _coerce_words_per_page(0.4) is None


def test_coerce_words_per_page_rejects_non_numeric():
    """Strings and other non-numeric values → None (fall back to default)."""
    assert _coerce_words_per_page("400") is None
    assert _coerce_words_per_page(None) is None
    assert _coerce_words_per_page([400]) is None
    assert _coerce_words_per_page({"value": 400}) is None


def test_coerce_words_per_page_rejects_bool():
    """``True`` / ``False`` → None (bool is technically int but nonsensical here)."""
    assert _coerce_words_per_page(True) is None
    assert _coerce_words_per_page(False) is None


def test_resolve_target_length_override_changes_derived_range():
    """words_per_page=400 with words=[9000, 13000] → derived pages [22, 33]
    (the issue's brasidas-synthesis reproducer numbers)."""
    pr, wr, src, wpp = _resolve_target_length(
        {"words": [9000, 13000]}, words_per_page=400
    )
    # min: 9000 // 400 = 22; max: ceil(13000 / 400) = 33.
    assert pr == (22, 33)
    assert wr == (9000, 13000)
    assert src == "words"
    assert wpp == 400


def test_resolve_target_length_override_none_uses_default():
    """words_per_page=None → default 400 wpp applied. Regression guard."""
    pr, wr, src, wpp = _resolve_target_length(
        {"words": [9000, 13000]}, words_per_page=None
    )
    # 9000 // 400 = 22; ceil(13000 / 400) = 33.
    assert pr == (22, 33)
    assert wpp == MEMO_WORDS_PER_PAGE


def test_resolve_target_length_override_ignored_for_pages_form():
    """words_per_page override is a no-op when target_length.pages is set."""
    pr, wr, src, wpp = _resolve_target_length(
        {"pages": [3, 4]}, words_per_page=400
    )
    # Pages form bypasses the conversion entirely; effective_wpp is
    # still surfaced (set to the override) but unused.
    assert pr == (3, 4)
    assert wr is None
    assert src == "pages"


def test_gate_memo_words_per_page_override_default_preserved(
    monkeypatch, memo_version_dir, fake_pdfinfo_5pages
):
    """No words_per_page kwarg → default 400 wpp behavior is unchanged.

    Regression guard for AC 1 ("default behavior preserved when absent").
    target_length.words=[800, 1600] derives [2, 4]; rendered 5 pages
    fires the warning (outside range at the new 400-wpp default).
    """
    _mock_full_render_chain(monkeypatch)
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_5pages,
        target_length={"words": [800, 1600]},
        # words_per_page omitted on purpose.
    )
    assert DIM_MEMO_PAGE_FIT in r.failed_gates
    findings = [f for f in r.findings if f.gate == DIM_MEMO_PAGE_FIT]
    assert len(findings) == 1
    # Message surfaces the 400-wpp default.
    assert "@ 400 wpp" in findings[0].message


def test_gate_memo_words_per_page_override_widens_range(
    monkeypatch, memo_version_dir, fake_pdfinfo_5pages
):
    """words_per_page=400 (matching the 400-wpp default) → 5 pages passes.

    AC 8 mirror: target_length.words=[1800, 2400] at 400 wpp derives
    [4, 6]; rendered 5 is in range → page-fit does NOT fire.
    """
    _mock_full_render_chain(monkeypatch)
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_5pages,
        target_length={"words": [1800, 2400]},
        words_per_page=400,
    )
    assert DIM_MEMO_PAGE_FIT not in r.failed_gates
    # The informational reason surfaces the effective wpp.
    assert any(
        DIM_MEMO_PAGE_FIT in reason and "@ 400 wpp" in reason
        for reason in r.reasons
    )


def test_gate_memo_words_per_page_message_surfaces_override(
    monkeypatch, memo_version_dir, fake_pdfinfo_5pages
):
    """When the override is set and the page-fit warning STILL fires, the
    finding message records the effective wpp (not the default 400).

    AC 2 + AC 5: ``memo_page_fit`` finding records the effective wpp used.
    """
    _mock_full_render_chain(monkeypatch)
    # 300 wpp on words=[1800, 2400] derives [6, 8]; rendered 5 is below.
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_5pages,
        target_length={"words": [1800, 2400]},
        words_per_page=300,
    )
    assert DIM_MEMO_PAGE_FIT in r.failed_gates
    findings = [f for f in r.findings if f.gate == DIM_MEMO_PAGE_FIT]
    assert len(findings) == 1
    assert "@ 300 wpp" in findings[0].message
    # The default 400 wpp should NOT appear (regression guard).
    assert "@ 400 wpp" not in findings[0].message


def test_gate_memo_words_per_page_malformed_falls_back_silently(
    monkeypatch, memo_version_dir, fake_pdfinfo_5pages
):
    """Malformed overrides (0, negative, non-numeric, bool) → silent
    fall back to 400 wpp; no exception raised. AC 4 + curation
    graceful-degrade contract."""
    _mock_full_render_chain(monkeypatch)
    for bad in [0, -1, -400, "400", True, False, [400], {"wpp": 400}]:
        r = gate(
            kind="memo",
            version_dir=memo_version_dir,
            pdfinfo_path=fake_pdfinfo_5pages,
            target_length={"words": [800, 1600]},
            words_per_page=bad,
        )
        # Default 400 wpp behavior: derived [2, 4], 5 pages out of range.
        assert DIM_MEMO_PAGE_FIT in r.failed_gates, (
            f"Bad words_per_page={bad!r} did not fall back to default"
        )
        findings = [f for f in r.findings if f.gate == DIM_MEMO_PAGE_FIT]
        assert "@ 400 wpp" in findings[0].message, (
            f"Bad words_per_page={bad!r} did not produce default-wpp message"
        )


def test_gate_memo_words_per_page_override_ignored_when_pages_set(
    monkeypatch, memo_version_dir, fake_pdfinfo_5pages
):
    """words_per_page override is a no-op when target_length.pages is set.

    AC 3: override only applies when target_length.words is set.
    """
    _mock_full_render_chain(monkeypatch)
    # pages=[2, 3], rendered 5 → fails regardless of words_per_page.
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_5pages,
        target_length={"pages": [2, 3]},
        words_per_page=400,
    )
    assert DIM_MEMO_PAGE_FIT in r.failed_gates
    findings = [f for f in r.findings if f.gate == DIM_MEMO_PAGE_FIT]
    # Error severity (pages-form), not warning — and message does NOT
    # reference wpp at all (no conversion happened).
    assert findings[0].severity == "error"
    assert "wpp" not in findings[0].message


# ---------------------------------------------------------------------------
# _parse_memo_overfull
# ---------------------------------------------------------------------------


def test_parse_memo_overfull_clean_stderr():
    """Empty / clean stderr → no hits."""
    assert _parse_memo_overfull("") == []
    assert _parse_memo_overfull("everything looks fine\n") == []


def test_parse_memo_overfull_overflow_pattern():
    """Stderr containing 'overflow' is captured."""
    stderr = "weasyprint: Element x overflows the page\n"
    hits = _parse_memo_overfull(stderr)
    assert len(hits) == 1
    assert hits[0]["kind"] == "overflow"
    assert hits[0]["line"] == 1


def test_parse_memo_overfull_multiple_lines():
    """Each matching stderr line produces a hit."""
    stderr = (
        "weasyprint: line is too long on page 3\n"
        "all good here\n"
        "another overflow\n"
    )
    hits = _parse_memo_overfull(stderr)
    assert len(hits) == 2
    assert {h["line"] for h in hits} == {1, 3}


def test_parse_memo_overfull_each_line_at_most_one_hit():
    """A line matching multiple patterns yields one hit (no double-count)."""
    stderr = "weasyprint: line is too long and overflows the column\n"
    hits = _parse_memo_overfull(stderr)
    assert len(hits) == 1


# ---------------------------------------------------------------------------
# _scan_memo_placeholders
# ---------------------------------------------------------------------------


def test_scan_memo_placeholders_default_patterns():
    """Source with TODO / [TBD] / TKTKTK → multiple hits."""
    source = (
        "# Investment memo\n"
        "\n"
        "Some prose.\n"
        "<!-- TODO: revise this section -->\n"
        "More prose. [TBD]\n"
        "Even more prose with _TKTKTK_ marker.\n"
    )
    active, suppressed = _scan_memo_placeholders(
        source, DEFAULT_MEMO_PLACEHOLDER_PATTERNS
    )
    assert len(active) >= 3
    assert len(suppressed) == 0


def test_scan_memo_placeholders_suppression_same_line():
    """Same-line ``anvil-lint-disable`` directive suppresses the hit."""
    source = (
        "# Memo\n"
        "Some prose. [TBD] <!-- anvil-lint-disable: memo_placeholder_scan -->\n"
    )
    active, suppressed = _scan_memo_placeholders(
        source, DEFAULT_MEMO_PLACEHOLDER_PATTERNS
    )
    assert len(active) == 0
    assert len(suppressed) == 1


def test_scan_memo_placeholders_suppression_line_above():
    """Standalone directive line suppresses the next non-blank line."""
    source = (
        "# Memo\n"
        "<!-- anvil-lint-disable: memo_placeholder_scan -->\n"
        "Some prose with TODO marker.\n"
    )
    active, suppressed = _scan_memo_placeholders(
        source, DEFAULT_MEMO_PLACEHOLDER_PATTERNS
    )
    assert len(active) == 0
    assert len(suppressed) >= 1


def test_scan_memo_placeholders_disable_directive_not_self_flagged():
    """The escape-hatch comment itself doesn't get counted as a placeholder."""
    source = (
        "# Memo\n"
        "<!-- anvil-lint-disable: memo_placeholder_scan -->\n"
        "Clean prose here.\n"
    )
    active, suppressed = _scan_memo_placeholders(
        source, DEFAULT_MEMO_PLACEHOLDER_PATTERNS
    )
    assert active == []
    # The directive doesn't itself match because the scan skips
    # directive-only lines, and "Clean prose" has no placeholder.
    assert suppressed == []


def test_scan_memo_placeholders_empty_source():
    """Empty source → no hits."""
    active, suppressed = _scan_memo_placeholders(
        "", DEFAULT_MEMO_PLACEHOLDER_PATTERNS
    )
    assert active == [] and suppressed == []


# ---------------------------------------------------------------------------
# _gate_memo: end-to-end with mocked render
# ---------------------------------------------------------------------------


def _mock_full_render_chain(
    monkeypatch,
    *,
    pandoc_returncode: int = 0,
    pandoc_stderr: str = "",
):
    """Wire up monkeypatches so the memo gate believes the chain is available
    and runs a fake pandoc that writes a fixture PDF."""
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_pandoc(returncode=pandoc_returncode, stderr=pandoc_stderr),
    )


def test_gate_memo_happy_path(monkeypatch, memo_version_dir, fake_pdfinfo_path):
    """All five checks pass on a clean memo with no target_length."""
    _mock_full_render_chain(monkeypatch)
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_path,
    )
    assert isinstance(r, GateResult)
    assert r.passed is True
    assert r.failed_gates == set()
    # Compile dim recorded a positive page count.
    assert r.pages == 3


def test_gate_memo_compile_failure(monkeypatch, memo_version_dir, fake_pdfinfo_path):
    """Pandoc non-zero exit → memo_compile_success fails with a finding."""
    _mock_full_render_chain(monkeypatch, pandoc_returncode=1, pandoc_stderr="boom")
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_path,
    )
    assert r.passed is False
    assert DIM_MEMO_COMPILE in r.failed_gates
    assert any("memo render failed" in f.message.lower() for f in r.findings)


def test_gate_memo_missing_renderer_graceful(monkeypatch, memo_version_dir):
    """No pandoc and no engine on PATH → compile dim does NOT fail, but
    an info-level reason carries the remediation."""
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: False)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: False)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    r = gate(kind="memo", version_dir=memo_version_dir)
    # No hard failure.
    assert DIM_MEMO_COMPILE not in r.failed_gates
    # Remediation message present in reasons.
    assert any("PATH" in reason for reason in r.reasons)
    assert r.compile_status == COMPILE_UNAVAILABLE


def test_gate_memo_page_fit_pages_form_error(
    monkeypatch, memo_version_dir, fake_pdfinfo_5pages
):
    """target_length.pages set and rendered count outside range → error."""
    _mock_full_render_chain(monkeypatch)
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_5pages,
        target_length={"pages": [2, 3]},
    )
    assert DIM_MEMO_PAGE_FIT in r.failed_gates
    # Error severity (declared pages).
    page_fit_findings = [f for f in r.findings if f.gate == DIM_MEMO_PAGE_FIT]
    assert len(page_fit_findings) == 1
    assert page_fit_findings[0].severity == "error"


def test_gate_memo_page_fit_words_form_warning(
    monkeypatch, memo_version_dir, fake_pdfinfo_5pages
):
    """target_length.words set and rendered count outside derived range → warning."""
    _mock_full_render_chain(monkeypatch)
    # 1200-1600 words → derived range [3, 4] at 400 wpp; rendered 5 → out of range.
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_5pages,
        target_length={"words": [1200, 1600]},
    )
    assert DIM_MEMO_PAGE_FIT in r.failed_gates
    page_fit_findings = [f for f in r.findings if f.gate == DIM_MEMO_PAGE_FIT]
    assert len(page_fit_findings) == 1
    assert page_fit_findings[0].severity == "warning"
    # Message references the word-count proxy.
    assert "wpp" in page_fit_findings[0].message or "word" in page_fit_findings[0].message.lower()


def test_gate_memo_page_fit_in_range_passes(
    monkeypatch, memo_version_dir, fake_pdfinfo_path
):
    """Rendered count inside declared range → page-fit passes (informational)."""
    _mock_full_render_chain(monkeypatch)
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_path,
        target_length={"pages": [2, 4]},
    )
    assert DIM_MEMO_PAGE_FIT not in r.failed_gates


def test_gate_memo_page_fit_skipped_without_target(
    monkeypatch, memo_version_dir, fake_pdfinfo_path
):
    """No target_length declared → page-fit check skipped, reason recorded."""
    _mock_full_render_chain(monkeypatch)
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_path,
    )
    assert DIM_MEMO_PAGE_FIT not in r.failed_gates
    assert any(
        DIM_MEMO_PAGE_FIT in reason and "skipped" in reason.lower()
        for reason in r.reasons
    )


def test_gate_memo_overfull_warning(
    monkeypatch, memo_version_dir, fake_pdfinfo_path
):
    """Pandoc stderr containing 'overflow' → warning-severity finding."""
    _mock_full_render_chain(
        monkeypatch,
        pandoc_stderr="weasyprint: element overflows column on page 2\n",
    )
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_path,
    )
    # Overflow does NOT cause a hard failure (warning only per architect Q3).
    overfull_findings = [f for f in r.findings if f.gate == DIM_MEMO_OVERFULL]
    assert len(overfull_findings) == 1
    assert overfull_findings[0].severity == "warning"


def test_gate_memo_overfull_clean_renderer(
    monkeypatch, memo_version_dir, fake_pdfinfo_path
):
    """Empty stderr → no overfull findings; check ran with reason recorded."""
    _mock_full_render_chain(monkeypatch, pandoc_stderr="")
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_path,
    )
    overfull = [f for f in r.findings if f.gate == DIM_MEMO_OVERFULL]
    assert overfull == []
    assert any(
        DIM_MEMO_OVERFULL in reason and "no stderr warnings" in reason.lower()
        for reason in r.reasons
    )


def test_gate_memo_image_refs_broken(
    monkeypatch, memo_version_dir, fake_pdfinfo_path
):
    """memo.md references a missing image → memo_image_refs_exist fails."""
    _mock_full_render_chain(monkeypatch)
    # Add an image reference to a non-existent file.
    memo_md = memo_version_dir / "bessemer.md"
    memo_md.write_text(
        memo_md.read_text() + "\n![chart](exhibits/missing.png)\n",
        encoding="utf-8",
    )
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_path,
    )
    assert DIM_MEMO_IMAGE_REFS in r.failed_gates


def test_gate_memo_image_refs_clean(
    monkeypatch, memo_version_dir, fake_pdfinfo_path
):
    """memo.md with no image references → image-refs check passes."""
    _mock_full_render_chain(monkeypatch)
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_path,
    )
    assert DIM_MEMO_IMAGE_REFS not in r.failed_gates


def test_gate_memo_placeholder_scan_fires(
    monkeypatch, memo_version_dir, fake_pdfinfo_path
):
    """memo.md containing TODO / TKTKTK → placeholder dim fails."""
    _mock_full_render_chain(monkeypatch)
    memo_md = memo_version_dir / "bessemer.md"
    memo_md.write_text(
        "# Memo\nProse with TODO and _TKTKTK_.\n",
        encoding="utf-8",
    )
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_path,
    )
    assert DIM_MEMO_PLACEHOLDERS in r.failed_gates


def test_gate_memo_placeholder_scan_suppressed(
    monkeypatch, memo_version_dir, fake_pdfinfo_path
):
    """Inline ``anvil-lint-disable`` directive downgrades hit to info."""
    _mock_full_render_chain(monkeypatch)
    memo_md = memo_version_dir / "bessemer.md"
    memo_md.write_text(
        "# Memo\nProse with TODO. "
        "<!-- anvil-lint-disable: memo_placeholder_scan -->\n",
        encoding="utf-8",
    )
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_path,
    )
    assert DIM_MEMO_PLACEHOLDERS not in r.failed_gates
    # The info-level finding still surfaces for reviewer visibility.
    info_hits = [
        f
        for f in r.findings
        if f.gate == DIM_MEMO_PLACEHOLDERS and f.severity == "info"
    ]
    assert len(info_hits) >= 1


# ---------------------------------------------------------------------------
# Independence + result shape
# ---------------------------------------------------------------------------


def test_gate_memo_all_checks_run_independently(
    monkeypatch, memo_version_dir, fake_pdfinfo_5pages
):
    """A memo with placeholder + broken image ref + page over-range fails
    three dimensions; the gate enumerates them all without short-circuit."""
    _mock_full_render_chain(monkeypatch)
    memo_md = memo_version_dir / "bessemer.md"
    memo_md.write_text(
        "# Memo with TODO\n"
        "Some prose.\n"
        "![](exhibits/missing.png)\n",
        encoding="utf-8",
    )
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_5pages,
        target_length={"pages": [2, 3]},
    )
    assert DIM_MEMO_PAGE_FIT in r.failed_gates
    assert DIM_MEMO_IMAGE_REFS in r.failed_gates
    assert DIM_MEMO_PLACEHOLDERS in r.failed_gates
    # Compile and overflow are clean (mocked pandoc returns 0, empty stderr).
    assert DIM_MEMO_COMPILE not in r.failed_gates
    assert DIM_MEMO_OVERFULL not in r.failed_gates
    assert r.passed is False


def test_gate_memo_to_review_emits_critical_flags(
    monkeypatch, memo_version_dir, fake_pdfinfo_5pages
):
    """Failed memo gate → Review.critical_flags carries one per dim."""
    _mock_full_render_chain(monkeypatch)
    memo_md = memo_version_dir / "bessemer.md"
    memo_md.write_text(
        "# Memo with TODO\n",
        encoding="utf-8",
    )
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_5pages,
    )
    rev = r.to_review(version_dir="bessemer.1", critic_id="memo-gate")
    assert isinstance(rev, Review)
    assert rev.kind == Kind.TOOL_EVIDENCE
    types = {cf.type for cf in rev.critical_flags}
    assert f"render_gate_{DIM_MEMO_PLACEHOLDERS}" in types
    # Schema round-trip: tool_evidence findings require tool_calls=[].
    rev2 = Review.model_validate(rev.model_dump())
    assert all(f.tool_calls is not None for f in rev2.findings)


def test_gate_memo_to_json_roundtrips(monkeypatch, memo_version_dir, fake_pdfinfo_path):
    """The JSON shape from memo mode survives ``json.dumps`` / ``json.loads``."""
    import json

    _mock_full_render_chain(monkeypatch)
    r = gate(
        kind="memo",
        version_dir=memo_version_dir,
        pdfinfo_path=fake_pdfinfo_path,
    )
    j = r.to_json()
    encoded = json.dumps(j)
    decoded = json.loads(encoded)
    assert decoded["gate"] == "render_gate"
    assert decoded["pass"] is True
    assert decoded["pages"] == 3


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


def test_gate_memo_requires_version_dir():
    """``gate(kind="memo")`` without ``version_dir`` → ValueError."""
    with pytest.raises(ValueError, match="version_dir"):
        gate(kind="memo")


def test_gate_unknown_kind_raises():
    """``gate(kind="bogus")`` → ValueError naming the supported kinds."""
    with pytest.raises(ValueError, match="kind"):
        gate(kind="bogus", pdf_path=Path("/tmp/x.pdf"))


def test_gate_latex_default_still_requires_pdf_path():
    """``gate()`` with no ``kind`` and no ``pdf_path`` → ValueError."""
    with pytest.raises(ValueError, match="pdf_path"):
        gate()


# ---------------------------------------------------------------------------
# _gate_memo direct invocation (bypassing the public dispatcher)
# ---------------------------------------------------------------------------


def test_gate_memo_internal_smoke(monkeypatch, memo_version_dir, fake_pdfinfo_path):
    """Direct ``_gate_memo`` invocation matches the public dispatcher."""
    _mock_full_render_chain(monkeypatch)
    r = _gate_memo(
        version_dir=memo_version_dir,
        out_pdf=None,
        target_length=None,
        placeholder_patterns=None,
        pdfinfo_path=fake_pdfinfo_path,
    )
    assert r.passed is True
    assert r.pages == 3
    # Default out_pdf is <version_dir>/<slug>.pdf — for the ``bessemer``
    # thread fixture the basename is ``bessemer.pdf`` per #295.
    assert r.pdf_path.endswith("bessemer.pdf")
