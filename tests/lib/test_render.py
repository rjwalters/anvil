"""Tests for ``anvil.lib.render``.

The renderer is a thin wrapper around subprocess shell-outs. Tests focus on:

- Public API surface: the four functions exist with the documented signatures
  and docstrings.
- Error paths: missing input files, missing binaries, non-zero subprocess
  exits.
- The matplotlib figure walker (the only renderer with no subprocess
  dependency) is tested end-to-end against a fixture directory.

We do NOT run the actual Marp/pdftoppm/pandoc subprocesses in the unit
suite — that would require Node, poppler, and pandoc on every test
machine. Integration-grade rendering tests are out of scope here (the
fixture decks under ``anvil/skills/deck/tests/fixtures/vision/`` exercise
the render path opportunistically when binaries are available, matching
the existing ``test_marp_smoke.py`` discipline).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from anvil.lib import render
from anvil.lib.render import (
    DEFAULT_MARP_CONFIG,
    RenderError,
    check_weasyprint_available,
    render_marp_to_pdf,
    render_matplotlib_figures,
    render_pandoc_to_pdf,
    render_pdf_to_pngs,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def test_module_exports_four_renderers():
    """AC1: the four documented renderer functions are exported."""
    assert callable(render.render_marp_to_pdf)
    assert callable(render.render_pdf_to_pngs)
    assert callable(render.render_pandoc_to_pdf)
    assert callable(render.render_matplotlib_figures)


def test_default_marp_config_path_matches_pin():
    """AC1: the default Marp config path matches the framework pin (#32)."""
    assert DEFAULT_MARP_CONFIG == Path("anvil/lib/marp/config.yml")


def test_each_renderer_has_a_docstring():
    """AC1: each public function has a docstring (per the AC wording)."""
    for fn in (
        render_marp_to_pdf,
        render_pdf_to_pngs,
        render_pandoc_to_pdf,
        render_matplotlib_figures,
    ):
        assert fn.__doc__ is not None and fn.__doc__.strip() != ""


def test_module_docstring_documents_fallback():
    """AC1: pdf2image fallback is documented in the module docstring."""
    assert render.__doc__ is not None
    doc = render.__doc__.lower()
    assert "pdftoppm" in doc
    assert "pdf2image" in doc


# ---------------------------------------------------------------------------
# render_marp_to_pdf — error paths
# ---------------------------------------------------------------------------


def test_marp_missing_source_raises_file_not_found(tmp_path):
    missing = tmp_path / "does-not-exist.md"
    with pytest.raises(FileNotFoundError):
        render_marp_to_pdf(missing, tmp_path / "out.pdf")


def test_marp_missing_binary_raises_render_error(tmp_path, monkeypatch):
    deck_md = tmp_path / "deck.md"
    deck_md.write_text("# Hello\n")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RenderError, match="marp CLI not found"):
        render_marp_to_pdf(deck_md, tmp_path / "out.pdf")


def test_marp_subprocess_nonzero_raises_render_error(tmp_path, monkeypatch):
    deck_md = tmp_path / "deck.md"
    deck_md.write_text("# Hello\n")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/marp")

    fake_completed = subprocess.CompletedProcess(
        args=["marp"], returncode=2, stdout="", stderr="boom"
    )
    monkeypatch.setattr(
        "anvil.lib.render.subprocess.run", lambda *a, **kw: fake_completed
    )
    with pytest.raises(RenderError, match="marp failed.*boom"):
        render_marp_to_pdf(deck_md, tmp_path / "out.pdf")


def test_marp_invokes_config_file_flag(tmp_path, monkeypatch):
    """AC1: render_marp_to_pdf uses --config-file <anvil/lib/marp/config.yml>."""
    deck_md = tmp_path / "deck.md"
    deck_md.write_text("# Hello\n")
    out_pdf = tmp_path / "out.pdf"

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/marp")

    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        captured["kw"] = kw
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr("anvil.lib.render.subprocess.run", fake_run)
    result = render_marp_to_pdf(deck_md, out_pdf)
    assert result == out_pdf
    assert "--config-file" in captured["cmd"]
    idx = captured["cmd"].index("--config-file")
    assert captured["cmd"][idx + 1] == str(DEFAULT_MARP_CONFIG)
    # And: --html and --pdf both present per the deck-design contract.
    assert "--html" in captured["cmd"]
    assert "--pdf" in captured["cmd"]
    assert "--allow-local-files" in captured["cmd"]
    # #620: belt-and-suspenders against marp blocking on stdin in non-TTY
    # contexts — --no-stdin on the argv AND stdin=DEVNULL on the subprocess.
    assert "--no-stdin" in captured["cmd"]
    assert captured["kw"].get("stdin") == subprocess.DEVNULL


def test_marp_honors_explicit_config_override(tmp_path, monkeypatch):
    deck_md = tmp_path / "deck.md"
    deck_md.write_text("# Hello\n")
    custom_config = tmp_path / "custom.yml"
    custom_config.write_text("options: {}\n")

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/marp")
    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr("anvil.lib.render.subprocess.run", fake_run)
    render_marp_to_pdf(deck_md, tmp_path / "out.pdf", config=custom_config)
    idx = captured["cmd"].index("--config-file")
    assert captured["cmd"][idx + 1] == str(custom_config)


# ---------------------------------------------------------------------------
# render_pdf_to_pngs — error paths + sort order
# ---------------------------------------------------------------------------


def test_pdf_to_pngs_missing_input_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        render_pdf_to_pngs(tmp_path / "missing.pdf", tmp_path / "out/")


def test_pdf_to_pngs_no_backend_raises_render_error(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(shutil, "which", lambda name: None)

    # Force the pdf2image import to fail at runtime.
    import sys
    monkeypatch.setitem(sys.modules, "pdf2image", None)

    with pytest.raises(RenderError, match="pdf2image"):
        render_pdf_to_pngs(pdf, tmp_path / "out/")


def test_pdf_to_pngs_pdftoppm_failure_raises_render_error(
    tmp_path, monkeypatch
):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pdftoppm")

    fake_completed = subprocess.CompletedProcess(
        args=["pdftoppm"], returncode=1, stdout="", stderr="syntax error"
    )
    monkeypatch.setattr(
        "anvil.lib.render.subprocess.run", lambda *a, **kw: fake_completed
    )
    with pytest.raises(RenderError, match="pdftoppm failed.*syntax error"):
        render_pdf_to_pngs(pdf, tmp_path / "out/")


def test_pdf_to_pngs_collects_and_sorts_numerically(tmp_path, monkeypatch):
    """The collector sorts page-1, page-2, ..., page-10 numerically.

    Plain string sort would order page-10.png before page-2.png; the
    helper extracts the integer suffix.
    """
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pdftoppm")

    def fake_run(cmd, **kw):
        # Simulate pdftoppm writing pages out of natural-string-sort order.
        for i in [1, 2, 3, 10, 11]:
            (out_dir / f"page-{i}.png").write_bytes(b"\x89PNG")
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr=""
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("anvil.lib.render.subprocess.run", fake_run)
    result = render_pdf_to_pngs(pdf, out_dir)
    names = [p.name for p in result]
    assert names == [
        "page-1.png",
        "page-2.png",
        "page-3.png",
        "page-10.png",
        "page-11.png",
    ]


# ---------------------------------------------------------------------------
# render_pandoc_to_pdf — error paths
# ---------------------------------------------------------------------------


def test_pandoc_missing_source_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        render_pandoc_to_pdf(tmp_path / "missing.md", tmp_path / "out.pdf")


def test_pandoc_missing_binary_raises_render_error(tmp_path, monkeypatch):
    src = tmp_path / "src.md"
    src.write_text("# hi\n")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RenderError, match="pandoc not found"):
        render_pandoc_to_pdf(src, tmp_path / "out.pdf")


def test_pandoc_passes_defaults_when_provided(tmp_path, monkeypatch):
    src = tmp_path / "src.md"
    src.write_text("# hi\n")
    defaults = tmp_path / "defaults.yaml"
    defaults.write_text("from: markdown\n")

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pandoc")
    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr("anvil.lib.render.subprocess.run", fake_run)
    render_pandoc_to_pdf(src, tmp_path / "out.pdf", defaults=defaults)
    assert "--defaults" in captured["cmd"]
    idx = captured["cmd"].index("--defaults")
    assert captured["cmd"][idx + 1] == str(defaults)


# ---------------------------------------------------------------------------
# render_matplotlib_figures — pure walker
# ---------------------------------------------------------------------------


def test_matplotlib_walker_returns_sorted_pngs(tmp_path):
    figures = tmp_path / "figures"
    figures.mkdir()
    for n in ("c.png", "a.png", "b.png"):
        (figures / n).write_bytes(b"\x89PNG")
    # Add a non-PNG and a hidden file to confirm they are ignored.
    (figures / "skip.svg").write_text("<svg/>")
    (figures / ".hidden.png").write_bytes(b"\x89PNG")

    result = render_matplotlib_figures(figures)
    names = [p.name for p in result]
    # All visible PNGs in sorted order; we don't exclude dot-files by
    # the spec but glob('*.png') gives a deterministic order.
    assert "a.png" in names
    assert "b.png" in names
    assert "c.png" in names
    assert "skip.svg" not in names
    # Sorted alphabetically.
    visible = [n for n in names if not n.startswith(".")]
    assert visible == sorted(visible)


def test_matplotlib_walker_missing_dir_returns_empty(tmp_path):
    assert render_matplotlib_figures(tmp_path / "nope") == []


def test_matplotlib_walker_file_path_returns_empty(tmp_path):
    f = tmp_path / "file.png"
    f.write_bytes(b"\x89PNG")
    assert render_matplotlib_figures(f) == []


# ---------------------------------------------------------------------------
# check_weasyprint_available — smoke-test paths (#308)
# ---------------------------------------------------------------------------


def test_check_weasyprint_available_false_when_not_on_path(monkeypatch):
    """Returns False immediately when shutil.which finds no binary."""
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert check_weasyprint_available() is False


def test_check_weasyprint_available_true_when_version_exits_0(monkeypatch):
    """Returns True when binary is on PATH and --version exits 0."""
    monkeypatch.setattr(
        shutil, "which", lambda name: "/usr/bin/weasyprint" if name == "weasyprint" else None
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        assert check_weasyprint_available() is True
        mock_run.assert_called_once_with(
            ["weasyprint", "--version"], capture_output=True, timeout=5
        )


def test_check_weasyprint_available_false_when_version_exits_43(monkeypatch):
    """Returns False when binary is on PATH but exits non-zero (e.g. missing libgobject)."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/weasyprint")
    mock_result = MagicMock()
    mock_result.returncode = 43
    with patch("subprocess.run", return_value=mock_result):
        assert check_weasyprint_available() is False


def test_check_weasyprint_available_false_on_oserror(monkeypatch):
    """Returns False (not raises) when subprocess.run raises OSError."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/weasyprint")
    with patch("subprocess.run", side_effect=OSError("exec failed")):
        assert check_weasyprint_available() is False


def test_check_weasyprint_available_false_on_timeout(monkeypatch):
    """Returns False (not raises) when the smoke-test times out."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/weasyprint")
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(["weasyprint", "--version"], 5),
    ):
        assert check_weasyprint_available() is False


# ---------------------------------------------------------------------------
# check_xelatex_available
# ---------------------------------------------------------------------------


def test_check_xelatex_available_false(monkeypatch):
    """Returns False when xelatex is not on PATH (shutil.which returns None)."""
    monkeypatch.setattr(shutil, "which", lambda name: None)
    from anvil.lib.render import check_xelatex_available
    assert check_xelatex_available() is False


def test_check_xelatex_available_true(monkeypatch):
    """Returns True when xelatex is on PATH (shutil.which returns a path)."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/xelatex")
    from anvil.lib.render import check_xelatex_available
    assert check_xelatex_available() is True


# ---------------------------------------------------------------------------
# render_mermaid_to_png — wrapper for deck-figures / slides-figures (issue #545)
# ---------------------------------------------------------------------------


def test_render_mermaid_to_png_is_exported() -> None:
    """The wrapper is part of the public API and listed in ``__all__``."""
    from anvil.lib.render import render_mermaid_to_png

    assert callable(render_mermaid_to_png)
    assert "render_mermaid_to_png" in render.__all__
    assert "DEFAULT_MERMAID_THEME" in render.__all__


def test_default_mermaid_theme_path_matches_pin() -> None:
    """The default theme pin resolves under ``anvil/lib/figures/``."""
    from anvil.lib.render import DEFAULT_MERMAID_THEME

    assert DEFAULT_MERMAID_THEME == Path(
        "anvil/lib/figures/mermaid-theme.json"
    )


def test_render_mermaid_to_png_missing_source_raises(tmp_path):
    """A missing ``.mmd`` source must raise ``FileNotFoundError`` before
    the binary check."""
    from anvil.lib.render import render_mermaid_to_png

    with pytest.raises(FileNotFoundError):
        render_mermaid_to_png(tmp_path / "missing.mmd", tmp_path / "out.png")


def test_render_mermaid_to_png_missing_binary_raises_render_error(
    tmp_path, monkeypatch
):
    """When ``mmdc`` is absent the wrapper raises ``RenderError`` with the
    canonical remediation string."""
    from anvil.lib.render import (
        MMDC_REMEDIATION,
        render_mermaid_to_png,
    )

    src = tmp_path / "flow.mmd"
    src.write_text("flowchart LR\n  A --> B\n", encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RenderError) as excinfo:
        render_mermaid_to_png(src, tmp_path / "out.png")
    # The full install story (npm + Chromium + --no-sandbox) must surface.
    assert "@mermaid-js/mermaid-cli" in str(excinfo.value)
    assert str(excinfo.value) == MMDC_REMEDIATION


def test_render_mermaid_to_png_invokes_canonical_flag_set(tmp_path, monkeypatch):
    """AC: subprocess argv includes the canonical issue-#545 flag set
    (``--scale 2`` plus the pre-existing flags). Mock pattern mirrors
    ``test_deck_mmdc_preflight.py``: stub ``shutil.which`` + capture the
    ``subprocess.run`` argv."""
    from anvil.lib.render import (
        DEFAULT_MERMAID_THEME,
        render_mermaid_to_png,
    )

    src = tmp_path / "flow.mmd"
    src.write_text("flowchart LR\n  A --> B\n", encoding="utf-8")
    out = tmp_path / "flow.png"

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/mmdc")

    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr("anvil.lib.render.subprocess.run", fake_run)
    result = render_mermaid_to_png(src, out)
    assert result == out

    cmd = captured["cmd"]
    # Binary name first.
    assert cmd[0] == "mmdc"
    # Canonical flag set — each flag/value pair must be adjacent.
    for flag, value in (
        ("--input", str(src)),
        ("--output", str(out)),
        ("--width", "1600"),
        ("--height", "900"),
        ("--scale", "2"),
        ("--backgroundColor", "white"),
        ("-c", str(DEFAULT_MERMAID_THEME)),
    ):
        assert flag in cmd, f"argv missing flag {flag!r}; cmd={cmd!r}"
        idx = cmd.index(flag)
        assert cmd[idx + 1] == value, (
            f"flag {flag!r} not followed by expected value {value!r}; "
            f"got {cmd[idx + 1]!r}"
        )


def test_render_mermaid_to_png_honors_explicit_overrides(tmp_path, monkeypatch):
    """Explicit ``width`` / ``height`` / ``scale`` / ``background_color`` /
    ``config`` kwargs override the defaults."""
    from anvil.lib.render import render_mermaid_to_png

    src = tmp_path / "flow.mmd"
    src.write_text("flowchart TB\n  A --> B\n", encoding="utf-8")
    out = tmp_path / "flow.png"
    custom_theme = tmp_path / "custom-theme.json"
    custom_theme.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/mmdc")
    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr("anvil.lib.render.subprocess.run", fake_run)
    render_mermaid_to_png(
        src,
        out,
        width=2000,
        height=1200,
        scale=3,
        background_color="transparent",
        config=custom_theme,
    )

    cmd = captured["cmd"]
    for flag, value in (
        ("--width", "2000"),
        ("--height", "1200"),
        ("--scale", "3"),
        ("--backgroundColor", "transparent"),
        ("-c", str(custom_theme)),
    ):
        idx = cmd.index(flag)
        assert cmd[idx + 1] == value


def test_render_mermaid_to_png_nonzero_exit_raises_render_error(
    tmp_path, monkeypatch
):
    """Non-zero exit from ``mmdc`` raises ``RenderError`` with the captured
    stderr (mirrors the ``marp`` failure path)."""
    from anvil.lib.render import render_mermaid_to_png

    src = tmp_path / "flow.mmd"
    src.write_text("flowchart LR\n  A --> B\n", encoding="utf-8")

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/mmdc")
    fake_completed = subprocess.CompletedProcess(
        args=["mmdc"], returncode=1, stdout="", stderr="boom: chromium crashed"
    )
    monkeypatch.setattr(
        "anvil.lib.render.subprocess.run", lambda *a, **kw: fake_completed
    )
    with pytest.raises(RenderError, match="mmdc failed.*boom"):
        render_mermaid_to_png(src, tmp_path / "out.png")
