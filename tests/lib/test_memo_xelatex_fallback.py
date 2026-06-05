"""Tests for the pandoc-3.x emission compatibility block in
``anvil/lib/memo/template.tex`` (issue #277).

Modern pandoc (>= 3.x) emits LaTeX whose macros (``\\st``, ``\\toprule``,
``\\Verb``, ``\\noalign``, ``\\tightlist``, ...) depend on packages the
shipped minimal xelatex fallback template did not historically load.
Issue #277 documents the canary reproducer (pandoc 3.9.0.2 + MacTeX
xelatex, undefined ``\\st``) and the curator's missing-package list.

This module pins three lanes of regression coverage:

1. **Static ``\\usepackage`` assertion.** Reads ``template.tex`` from
   disk and asserts each required package token plus the two
   ``\\providecommand``/``\\newcounter`` macros are present. Runs in CI
   without pandoc or xelatex installed — its purpose is to catch
   accidental deletion of the compat block during future
   ``template.tex`` edits.

2. **Skip-guarded real-render.** When both ``pandoc`` and ``xelatex``
   are on PATH, the test renders ``tests/lib/fixtures/memo_xelatex/
   repro.md`` (which exercises footnote + table + strikethrough +
   inline code + link + heading + tight list — the full curator
   missing-package matrix) through the real chain and asserts exit 0
   plus a non-empty PDF. Skips with an explicit reason when either
   binary is absent so the CI lane that lacks TeX Live still passes.

3. **Graceful-degrade contract.** Monkeypatches
   ``anvil.lib.render_gate._select_memo_engine`` to return ``"xelatex"``
   and patches ``subprocess.run`` to fake an ``\\st undefined`` pandoc
   stderr; asserts ``_render_memo_source`` returns
   ``(COMPILE_FAILED, 1, "xelatex", <stderr containing 'st undefined'>)``
   — i.e. the renderer surface keeps returning the 4-tuple contract
   even when the LaTeX compile fails. Pins that the compat-preamble
   edit doesn't change ``_render_memo_source``'s graceful-degrade
   contract documented in ``anvil/lib/render_gate.py`` lines 894-911.

Filename ``test_memo_xelatex_fallback.py`` is distinct from
``test_memo_render_detection.py`` and ``test_render_gate_memo.py`` per
the #58 packaging convention so pytest does not collide on a shared
module name across the suite.
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
    MEMO_ENGINE_XELATEX,
    _render_memo_source,
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _template_tex_path() -> Path:
    """Return the absolute path to the shipped ``template.tex``."""
    return Path(_render.__file__).parent / "memo" / "template.tex"


def _repro_fixture_path() -> Path:
    """Return the absolute path to ``repro.md`` (the issue-#277 reproducer)."""
    return (
        Path(__file__).parent
        / "fixtures"
        / "memo_xelatex"
        / "repro.md"
    )


# ---------------------------------------------------------------------------
# Lane 1: Static \usepackage assertion — no binaries needed
# ---------------------------------------------------------------------------


# Packages the pandoc-3.x emission requires the template to load. Each
# entry is a ``\usepackage`` *token* the static scan looks for; the
# ``\IfFileExists``-guarded packages still emit their literal
# ``\usepackage{name}`` substring in the template source so a regex-free
# substring test is sufficient.
_REQUIRED_USEPACKAGE_TOKENS = (
    r"\usepackage{xcolor}",
    r"\usepackage{fancyvrb}",
    r"\usepackage{longtable,booktabs,array}",
    r"\usepackage{calc}",
    r"\usepackage{etoolbox}",
    r"\usepackage{bookmark}",
)


# Conditional / fallback tokens that ship via \IfFileExists guards.
# Each entry is a substring the template must contain so the guarded
# load path is preserved on future edits.
_REQUIRED_GUARDED_TOKENS = (
    r"\IfFileExists{soul.sty}",
    r"\IfFileExists{footnotehyper.sty}",
    r"\IfFileExists{lua-ul.sty}",
    r"\usepackage{footnote}",  # the footnotehyper fallback branch
    r"\usepackage[soul]{lua-ul}",  # the lua-ul soul-emulation branch
)


# Macro fallbacks that keep the document compiling on thin TeX Live
# installs. The compat block ships these *unconditionally* so the
# document is renderable even when ``soul.sty`` or ``footnotehyper.sty``
# are absent.
_REQUIRED_MACRO_TOKENS = (
    r"\providecommand{\st}",      # strikethrough fallback (issue #277)
    r"\providecommand{\tightlist}",  # pandoc tight-list spacing macro
    r"\newcounter{none}",         # backs \noalign{} in unnumbered tables
)


def test_template_loads_pandoc_3x_packages():
    """Static: every ``\\usepackage`` modern pandoc expects is present.

    This is the canary regression — keeps ``template.tex`` from drifting
    back to the minimal preamble shape during future edits. Runs in CI
    without any LaTeX install.
    """
    tex = _template_tex_path()
    assert tex.is_file(), f"template.tex not found at {tex}"
    content = tex.read_text(encoding="utf-8")

    missing = [tok for tok in _REQUIRED_USEPACKAGE_TOKENS if tok not in content]
    assert not missing, (
        f"template.tex is missing required \\usepackage tokens: {missing}. "
        "See issue #277 for the pandoc-3.x emission compatibility set."
    )


def test_template_carries_iffileexists_guards():
    """Static: the ``\\IfFileExists`` guards survive future edits.

    The guards are the graceful-degrade primitive — without them, thin
    TeX Live installs that lack ``soul.sty`` or ``footnotehyper.sty``
    hard-fail at ``\\Undefined control sequence`` rather than producing
    a slightly worse memo. Mirrors the ``check_*_available()``
    precedent in ``anvil/lib/render.py``.
    """
    content = _template_tex_path().read_text(encoding="utf-8")
    missing = [tok for tok in _REQUIRED_GUARDED_TOKENS if tok not in content]
    assert not missing, (
        f"template.tex is missing required \\IfFileExists guards or "
        f"fallback \\usepackage branches: {missing}. These are required "
        "for graceful-degrade on thin TeX Live installs."
    )


def test_template_provides_macro_fallbacks():
    """Static: ``\\providecommand{\\st}``, ``\\tightlist``, and
    ``\\newcounter{none}`` all ship unconditionally.

    These are the macro-level fallbacks. ``\\st`` is the issue-#277
    canary (undefined when ``soul.sty`` is absent); ``\\tightlist`` is
    pandoc's list-spacing macro; ``\\newcounter{none}`` backs the
    ``\\noalign{}`` hooks pandoc 3.x emits for unnumbered tables.
    """
    content = _template_tex_path().read_text(encoding="utf-8")
    missing = [tok for tok in _REQUIRED_MACRO_TOKENS if tok not in content]
    assert not missing, (
        f"template.tex is missing required macro fallbacks: {missing}. "
        "These keep the document compiling on thin TeX Live installs."
    )


def test_template_preserves_minimal_preamble():
    """Static: the original minimal preamble (geometry/fontspec/fancyhdr/
    lastpage/hyperref) is still present alongside the compat block.

    The compat block is *additive*, not a replacement — the existing
    pinned typography/page-layout still anchors the rendered output.
    """
    content = _template_tex_path().read_text(encoding="utf-8")
    for tok in (
        r"\usepackage[margin=0.75in]{geometry}",
        r"\usepackage{fontspec}",
        r"\usepackage{fancyhdr}",
        r"\usepackage{lastpage}",
        r"\usepackage{hyperref}",
    ):
        assert tok in content, (
            f"template.tex lost original minimal-preamble token: {tok}. "
            "The compat block should be additive, not a replacement."
        )


# ---------------------------------------------------------------------------
# Lane 1b: Unicode fallback assertions — issue #309
# ---------------------------------------------------------------------------

# Tokens required for the Unicode symbol fallback block (issue #309).
# newunicodechar maps individual code-points to a DejaVu Sans render path
# so they are not silently dropped when Helvetica lacks coverage.
_REQUIRED_UNICODE_FALLBACK_TOKENS = (
    r"\usepackage{newunicodechar}",
    r"\UnicodeFallback",
    r"\newunicodechar{→}",
    r"\newunicodechar{μ}",
)


def test_template_carries_unicode_fallback_block():
    """Static: the Unicode symbol fallback block ships in ``template.tex``.

    Helvetica lacks coverage for arrows (→ ↑ ↓ ←) and Greek/SI letters
    (μ). Without a ``newunicodechar`` mapping to a fallback font (DejaVu
    Sans), these code-points render as spaces in the PDF — no compile
    error, silent drop. Issue #309 documents the canary reproducer.

    This test asserts:
    - ``\\usepackage{newunicodechar}`` is loaded
    - ``\\UnicodeFallback`` font-family command is declared
    - ``\\newunicodechar{→}`` and ``\\newunicodechar{μ}`` are mapped

    Runs in CI without pandoc or xelatex installed — its purpose is to
    catch accidental deletion of the Unicode fallback block during future
    ``template.tex`` edits.
    """
    tex = _template_tex_path()
    assert tex.is_file(), f"template.tex not found at {tex}"
    content = tex.read_text(encoding="utf-8")

    missing = [tok for tok in _REQUIRED_UNICODE_FALLBACK_TOKENS if tok not in content]
    assert not missing, (
        f"template.tex is missing required Unicode fallback tokens: {missing}. "
        "See issue #309 for the Helvetica-missing-glyph reproducer. "
        "The newunicodechar block maps → and μ (and peers) to DejaVu Sans "
        "so they are not silently dropped in the rendered PDF."
    )


# ---------------------------------------------------------------------------
# Lane 1c: lua-ul guard correctness — issue #305
# ---------------------------------------------------------------------------


def test_template_uses_ifluatex_guard_for_lua_ul():
    r"""The lua-ul guard must use \ifluatex, NOT \ifPDFTeX\else.

    \ifPDFTeX\else causes xelatex to enter the else-branch and attempt
    loading lua-ul.sty, which requires lualatex (issue #305).
    """
    tex = _template_tex_path().read_text(encoding="utf-8")
    assert r"\ifluatex" in tex, (
        r"template.tex must contain \ifluatex for the lua-ul guard"
    )
    assert r"\ifPDFTeX\else" not in tex, (
        r"\ifPDFTeX\else is incorrect for lua-ul — must use \ifluatex"
    )


# ---------------------------------------------------------------------------
# Lane 2: Skip-guarded real-render against the reproducer fixture
# ---------------------------------------------------------------------------


def _xelatex_chain_available() -> bool:
    """Return ``True`` only when both pandoc and xelatex are on PATH."""
    return (
        shutil.which("pandoc") is not None
        and shutil.which("xelatex") is not None
    )


@pytest.mark.skipif(
    not _xelatex_chain_available(),
    reason="xelatex chain unavailable (pandoc or xelatex not on PATH)",
)
def test_repro_fixture_renders_under_real_pandoc_plus_xelatex(tmp_path):
    """Real-chain regression: the issue-#277 reproducer fixture renders
    cleanly under the real pandoc + xelatex chain.

    The reproducer exercises footnote + table + strikethrough + inline
    code + link + heading + tight list — the full curator-identified
    missing-package matrix. With the compat block in place, the chain
    should exit 0 and produce a non-empty PDF.

    Skipped when either binary is absent so the CI lane that lacks
    TeX Live still passes (mirrors the ``_select_memo_engine``
    graceful-degrade contract in ``anvil/lib/render_gate.py``).
    """
    repro = _repro_fixture_path()
    assert repro.is_file(), f"reproducer fixture not found at {repro}"

    out_pdf = tmp_path / "repro.pdf"
    cmd = [
        "pandoc",
        str(repro),
        "--template",
        str(_template_tex_path()),
        "--pdf-engine=xelatex",
        "-o",
        str(out_pdf),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, (
        f"pandoc + xelatex chain failed on the issue-#277 reproducer. "
        f"stderr:\n{proc.stderr}"
    )
    assert out_pdf.exists(), "pandoc returned 0 but no PDF was written"
    assert out_pdf.stat().st_size > 0, "rendered PDF is empty"


# ---------------------------------------------------------------------------
# Lane 3: Graceful-degrade contract — fake xelatex failure, assert
# _render_memo_source still returns the 4-tuple shape.
# ---------------------------------------------------------------------------


class _FakeCompletedProcess:
    """Minimal stand-in for ``subprocess.CompletedProcess``."""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def memo_version_dir(tmp_path):
    """Build a minimal version directory with a non-empty body markdown.

    Body filename echoes the thread slug per #295 — for an ``anvil``
    thread the body is ``anvil.md`` inside ``anvil/anvil.1/``.
    """
    thread = tmp_path / "anvil"
    thread.mkdir()
    vd = thread / "anvil.1"
    vd.mkdir()
    (vd / "anvil.md").write_text(
        "# Investment memo\n\nSome ~~strikethrough~~ prose.\n",
        encoding="utf-8",
    )
    return vd


def test_render_memo_source_graceful_degrade_on_xelatex_failure(
    monkeypatch, memo_version_dir
):
    """When xelatex fails with an ``\\st undefined`` style error,
    ``_render_memo_source`` returns ``(COMPILE_FAILED, exit_code,
    "xelatex", stderr)`` rather than raising.

    This pins the contract documented at ``render_gate.py`` lines
    894-911: the renderer surface always returns the 4-tuple shape so
    the gate can surface ``MEMO_RENDERER_REMEDIATION`` without an
    exception handler. The compat-preamble edit should not change this
    behavior — the graceful-degrade contract is independent of which
    packages the template loads.
    """
    # Force the xelatex branch (the issue-#277 path) regardless of
    # what's on PATH.
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: False)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: "/usr/local/bin/xelatex" if name == "xelatex" else None,
    )

    # Fake a pandoc invocation that fails with the canary stderr from
    # issue #277 (the undefined-\st error message).
    fake_stderr = (
        "Error producing PDF.\n"
        "! Undefined control sequence.\n"
        "l.119 \\textbf{bold}, \\emph{italic}, \\st\n"
    )

    def _fake_run(cmd, **kwargs):
        # Only intercept pandoc; defer to the real call otherwise.
        if cmd and cmd[0] == "pandoc":
            return _FakeCompletedProcess(
                returncode=43, stdout="", stderr=fake_stderr
            )
        return subprocess.run(cmd, **kwargs)  # pragma: no cover

    monkeypatch.setattr(subprocess, "run", _fake_run)

    out_pdf = memo_version_dir / "memo.pdf"
    status, exit_code, engine, stderr = _render_memo_source(
        memo_version_dir, out_pdf
    )

    # Contract assertions: 4-tuple shape preserved on failure path.
    assert status == COMPILE_FAILED
    assert exit_code == 43
    assert engine == MEMO_ENGINE_XELATEX
    assert "Undefined control sequence" in stderr
    assert "\\st" in stderr
