"""Integration tests for memo render + theme primitive (#322 Phase A).

Covers the wiring layer between:

- ``anvil.lib.theme`` (Phase A loader + Theme model + find_consumer_root)
- ``anvil.skills.memo.lib.theme_resolver`` (memo asset precedence walker)
- ``anvil.lib.render_gate._select_memo_engine`` (gains ``requested`` param)
- ``anvil.lib.render_gate._render_memo_source`` (consumes theme context
  via the helper ``_discover_memo_theme_context``)

The unit-level tests for each piece live in:

- ``tests/lib/test_theme.py``
- ``anvil/skills/memo/tests/test_theme_resolution.py``
- ``tests/lib/test_render_gate_memo.py`` (existing — unchanged contract)

This file's scope: the **integration** behaviors — engine override
precedence, theme-tier asset wiring into pandoc command line, end-to-end
graceful-degrade when no theme is declared (back-compat guard).

Filename is distinct from existing memo tests per the #58 packaging
convention.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Optional

import pytest

from anvil.lib import render as _render
from anvil.lib.render_gate import (
    COMPILE_OK,
    MEMO_ENGINE_WEASYPRINT,
    MEMO_ENGINE_WKHTMLTOPDF,
    MEMO_ENGINE_XELATEX,
    _discover_memo_theme_context,
    _render_memo_source,
    _select_memo_engine,
)


# ---------------------------------------------------------------------------
# Helpers (mirror tests/lib/test_render_gate_memo.py)
# ---------------------------------------------------------------------------


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _record_pandoc(
    captured: list,
    *,
    returncode: int = 0,
    stderr: str = "",
):
    """A ``subprocess.run`` replacement that captures the pandoc cmd."""
    real_run = subprocess.run

    def _run(cmd, **kwargs):
        if not cmd or cmd[0] != "pandoc":
            return real_run(cmd, **kwargs)
        # Record the command for assertion later.
        captured.append(list(cmd))
        # Write a stub PDF so the gate's downstream checks succeed.
        if "-o" in cmd:
            idx = cmd.index("-o")
            if idx + 1 < len(cmd):
                target = Path(cmd[idx + 1])
                target.parent.mkdir(parents=True, exist_ok=True)
                if returncode == 0:
                    target.write_bytes(b"%PDF-1.5\nfake\n")
        return _FakeCompletedProcess(returncode=returncode, stderr=stderr)

    return _run


def _seed_consumer(root: Path) -> Path:
    """Create the ``.anvil/`` marker so find_consumer_root succeeds."""
    (root / ".anvil").mkdir(parents=True, exist_ok=True)
    return root


def _write_brief(project_dir: Path, theme: Optional[str], slug: str = "memo") -> Path:
    """Write a minimal project BRIEF with optional theme.

    Build the body line by line rather than via ``textwrap.dedent`` —
    the dedent helper doesn't work cleanly with conditionally
    interpolated lines (the common-whitespace rule breaks when the
    interpolated value lacks the surrounding indent).
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    lines = ["---", "project: demo"]
    if theme:
        lines.append(f"theme: {theme}")
    lines.extend(
        [
            "documents:",
            f"  - slug: {slug}",
            "    artifact_type: investment-memo",
            "---",
            "",
            "# Project BRIEF",
            "",
        ]
    )
    body = "\n".join(lines)
    brief = project_dir / "BRIEF.md"
    brief.write_text(body, encoding="utf-8")
    return brief


def _write_theme_yml(consumer: Path, name: str, body: str) -> Path:
    theme_dir = consumer / ".anvil" / "themes" / name
    theme_dir.mkdir(parents=True, exist_ok=True)
    f = theme_dir / "theme.yml"
    f.write_text(body, encoding="utf-8")
    return f


def _write_theme_asset(consumer: Path, name: str, asset: str, body: str) -> Path:
    d = consumer / ".anvil" / "themes" / name / "memo"
    d.mkdir(parents=True, exist_ok=True)
    f = d / asset
    f.write_text(body, encoding="utf-8")
    return f


def _make_thread(consumer: Path, slug: str = "memo") -> Path:
    """Set up consumer/<project>/<slug>/<slug>.1/<slug>.md and return version_dir."""
    project = consumer / "project-root"
    thread = project / slug
    vd = thread / f"{slug}.1"
    vd.mkdir(parents=True)
    (vd / f"{slug}.md").write_text(
        "# Investment memo\n\nBody prose.\n", encoding="utf-8"
    )
    return vd


# ---------------------------------------------------------------------------
# _select_memo_engine — requested override
# ---------------------------------------------------------------------------


def test_select_engine_requested_xelatex_picks_xelatex_when_available(monkeypatch):
    """``requested='xelatex'`` wins over the weasyprint default."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: True)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)
    assert _select_memo_engine(requested="xelatex") == MEMO_ENGINE_XELATEX


def test_select_engine_requested_wkhtmltopdf_wins_over_weasyprint(monkeypatch):
    """``requested='wkhtmltopdf'`` picks wkhtmltopdf even with weasyprint available."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: True)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert (
        _select_memo_engine(requested="wkhtmltopdf") == MEMO_ENGINE_WKHTMLTOPDF
    )


def test_select_engine_requested_unavailable_falls_through(monkeypatch):
    """``requested='xelatex'`` but xelatex absent → weasyprint default wins."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert (
        _select_memo_engine(requested="xelatex") == MEMO_ENGINE_WEASYPRINT
    )


def test_select_engine_requested_unrecognized_falls_through(monkeypatch):
    """Unknown engine name → default priority, no raise."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert _select_memo_engine(requested="prince") == MEMO_ENGINE_WEASYPRINT


def test_select_engine_requested_none_matches_pre_322_behavior(monkeypatch):
    """``requested=None`` (the default) matches the pre-#322 contract."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: True)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)
    # Default order = weasyprint > wkhtmltopdf > xelatex.
    assert _select_memo_engine() == MEMO_ENGINE_WEASYPRINT
    assert _select_memo_engine(requested=None) == MEMO_ENGINE_WEASYPRINT


def test_select_engine_case_insensitive_match(monkeypatch):
    """``requested='XELATEX'`` matches the same engine as 'xelatex'."""
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)
    assert _select_memo_engine(requested="XELATEX") == MEMO_ENGINE_XELATEX


# ---------------------------------------------------------------------------
# _discover_memo_theme_context — walks the project chain
# ---------------------------------------------------------------------------


def test_discover_no_consumer_no_theme(tmp_path):
    """No ``.anvil/`` upstream → empty context, byte-identical to pre-#322."""
    # tmp_path has no .anvil/ marker.
    vd = tmp_path / "stray" / "stray.1"
    vd.mkdir(parents=True)
    consumer, theme, engine = _discover_memo_theme_context(vd)
    assert consumer is None
    assert theme is None
    assert engine is None


def test_discover_consumer_no_brief(tmp_path):
    """Consumer found but no project BRIEF → consumer_root only."""
    consumer = _seed_consumer(tmp_path)
    vd = consumer / "stray" / "stray.1"
    vd.mkdir(parents=True)
    c, theme, engine = _discover_memo_theme_context(vd)
    assert c == consumer
    assert theme is None
    assert engine is None


def test_discover_brief_no_theme(tmp_path):
    """BRIEF present but no ``theme:`` field → theme None, engine None."""
    consumer = _seed_consumer(tmp_path)
    project = consumer / "demo"
    _write_brief(project, theme=None)
    vd = _make_thread(consumer)
    # Move the version dir under the project root so discovery finds it.
    moved_vd = project / "memo" / "memo.1"
    moved_vd.mkdir(parents=True)
    (moved_vd / "memo.md").write_text("# Body\n", encoding="utf-8")
    c, theme, engine = _discover_memo_theme_context(moved_vd)
    assert c == consumer
    assert theme is None
    assert engine is None


def test_discover_brief_with_theme_loads_render_engine(tmp_path):
    """BRIEF with theme + theme.yml render_engine → discovery returns engine."""
    consumer = _seed_consumer(tmp_path)
    project = consumer / "demo"
    _write_brief(project, theme="sphere-semi")
    _write_theme_yml(
        consumer,
        "sphere-semi",
        textwrap.dedent(
            """
            accent_color: "#526AE5"
            render_engine: xelatex
            """
        ).strip()
        + "\n",
    )
    moved_vd = project / "memo" / "memo.1"
    moved_vd.mkdir(parents=True)
    (moved_vd / "memo.md").write_text("# Body\n", encoding="utf-8")
    c, theme, engine = _discover_memo_theme_context(moved_vd)
    assert c == consumer
    assert theme == "sphere-semi"
    assert engine == "xelatex"


def test_discover_brief_with_theme_but_no_yaml(tmp_path):
    """BRIEF with theme but no theme.yml → theme name only, no engine."""
    consumer = _seed_consumer(tmp_path)
    project = consumer / "demo"
    _write_brief(project, theme="bare-theme")
    # No theme.yml written, but the theme dir is missing too.
    moved_vd = project / "memo" / "memo.1"
    moved_vd.mkdir(parents=True)
    (moved_vd / "memo.md").write_text("# Body\n", encoding="utf-8")
    c, theme, engine = _discover_memo_theme_context(moved_vd)
    assert c == consumer
    assert theme == "bare-theme"
    assert engine is None


# ---------------------------------------------------------------------------
# End-to-end: _render_memo_source uses theme assets when declared
# ---------------------------------------------------------------------------


def test_render_uses_theme_styles_when_theme_declared(monkeypatch, tmp_path):
    """When BRIEF declares theme: X and a theme styles.css exists, pandoc's
    --css points to the theme path (not the framework default)."""
    consumer = _seed_consumer(tmp_path)
    project = consumer / "demo"
    _write_brief(project, theme="sphere-semi")
    _write_theme_yml(consumer, "sphere-semi", "accent_color: '#526AE5'\n")
    theme_css = _write_theme_asset(
        consumer,
        "sphere-semi",
        "styles.css",
        "/* sphere-semi brand styles */\n",
    )

    # Set up the version dir under the project root.
    vd = project / "memo" / "memo.1"
    vd.mkdir(parents=True)
    (vd / "memo.md").write_text(
        "# Investment memo\n\n## Body\n\nProse.\n", encoding="utf-8"
    )

    # Wire weasyprint as the chosen engine.
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    captured: list = []
    monkeypatch.setattr(subprocess, "run", _record_pandoc(captured, returncode=0))

    out_pdf = vd / "memo.pdf"
    status, exit_code, engine, stderr = _render_memo_source(vd, out_pdf)

    assert status == COMPILE_OK
    assert exit_code == 0
    assert engine == MEMO_ENGINE_WEASYPRINT
    assert len(captured) == 1
    cmd = captured[0]
    # The captured pandoc command's --css must point at the theme path.
    assert "--css" in cmd
    css_idx = cmd.index("--css")
    css_arg = cmd[css_idx + 1]
    assert css_arg == str(theme_css), (
        f"pandoc --css={css_arg} should equal theme path {theme_css}"
    )


def test_render_without_theme_uses_framework_default(monkeypatch, tmp_path):
    """No theme declared → pandoc --css points at the framework default."""
    consumer = _seed_consumer(tmp_path)
    project = consumer / "demo"
    _write_brief(project, theme=None)

    vd = project / "memo" / "memo.1"
    vd.mkdir(parents=True)
    (vd / "memo.md").write_text("# Body\n", encoding="utf-8")

    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    captured: list = []
    monkeypatch.setattr(subprocess, "run", _record_pandoc(captured, returncode=0))

    out_pdf = vd / "memo.pdf"
    status, exit_code, engine, stderr = _render_memo_source(vd, out_pdf)

    assert status == COMPILE_OK
    assert len(captured) == 1
    cmd = captured[0]
    css_idx = cmd.index("--css")
    css_arg = cmd[css_idx + 1]
    # Default styles.css lives next to anvil/lib/render.py — its parent
    # dir is the anvil/lib/memo directory.
    assert "/memo/styles.css" in css_arg
    assert ".anvil/themes/" not in css_arg


def test_render_with_theme_render_engine_pin_uses_xelatex(monkeypatch, tmp_path):
    """theme.yml with render_engine: xelatex + xelatex on PATH → xelatex used.

    Acceptance criterion from issue #322 body. The theme.yml pin flows
    through ``_discover_memo_theme_context`` → ``_select_memo_engine``.
    """
    consumer = _seed_consumer(tmp_path)
    project = consumer / "demo"
    _write_brief(project, theme="sphere-semi")
    _write_theme_yml(
        consumer,
        "sphere-semi",
        "render_engine: xelatex\n",
    )

    vd = project / "memo" / "memo.1"
    vd.mkdir(parents=True)
    (vd / "memo.md").write_text("# Body\n", encoding="utf-8")

    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    # Both weasyprint and xelatex available — without the theme pin,
    # weasyprint would win. The theme should flip the decision.
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)
    captured: list = []
    monkeypatch.setattr(subprocess, "run", _record_pandoc(captured, returncode=0))

    out_pdf = vd / "memo.pdf"
    status, exit_code, engine, stderr = _render_memo_source(vd, out_pdf)

    assert status == COMPILE_OK
    assert engine == MEMO_ENGINE_XELATEX
    # The pandoc command uses --pdf-engine=xelatex.
    cmd = captured[0]
    assert f"--pdf-engine={MEMO_ENGINE_XELATEX}" in cmd


def test_render_with_theme_engine_unavailable_falls_back(monkeypatch, tmp_path):
    """theme.yml render_engine: xelatex but xelatex absent → weasyprint used.

    Tests the graceful-degrade behavior of ``_select_memo_engine`` —
    consumer's brand pin loses to "render something rather than nothing".
    """
    consumer = _seed_consumer(tmp_path)
    project = consumer / "demo"
    _write_brief(project, theme="sphere-semi")
    _write_theme_yml(consumer, "sphere-semi", "render_engine: xelatex\n")

    vd = project / "memo" / "memo.1"
    vd.mkdir(parents=True)
    (vd / "memo.md").write_text("# Body\n", encoding="utf-8")

    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    # xelatex NOT available on PATH.
    monkeypatch.setattr(shutil, "which", lambda name: None)
    captured: list = []
    monkeypatch.setattr(subprocess, "run", _record_pandoc(captured, returncode=0))

    out_pdf = vd / "memo.pdf"
    status, exit_code, engine, stderr = _render_memo_source(vd, out_pdf)

    assert status == COMPILE_OK
    # Fell through to weasyprint despite the theme pin.
    assert engine == MEMO_ENGINE_WEASYPRINT


# ---------------------------------------------------------------------------
# #320 + #322 precedence: per-thread render_engine wins over per-theme
# ---------------------------------------------------------------------------


def test_per_thread_render_engine_wins_over_per_theme(monkeypatch, tmp_path):
    """Per-thread ``documents[].render_engine`` beats theme.yml render_engine.

    Curation pinned the precedence as **per-thread (#320) > per-project >
    per-theme (#322) > framework default**. This test exercises the
    first hop: a memo whose BRIEF declares BOTH a per-thread
    ``render_engine: xelatex`` (issue #320) AND a project ``theme:``
    whose ``theme.yml`` pins ``render_engine: weasyprint`` (issue #322).

    With every binary available on PATH, the per-thread value must win.
    The implementation point under test is the
    ``effective_engine = requested_engine or theme_engine`` short-circuit
    in ``_render_memo_source`` — caller threads the per-thread value
    through as ``requested_engine``; per-theme is the fallback.
    """
    consumer = _seed_consumer(tmp_path)
    project = consumer / "demo"
    _write_brief(project, theme="sphere-semi")
    # Per-theme default: weasyprint.
    _write_theme_yml(consumer, "sphere-semi", "render_engine: weasyprint\n")

    vd = project / "memo" / "memo.1"
    vd.mkdir(parents=True)
    (vd / "memo.md").write_text("# Body\n", encoding="utf-8")

    # Every engine available — without precedence, weasyprint would win.
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: True)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)
    captured: list = []
    monkeypatch.setattr(subprocess, "run", _record_pandoc(captured, returncode=0))

    out_pdf = vd / "memo.pdf"
    # Caller (``_gate_memo`` in production; this test directly) supplies
    # the per-thread override from BriefDocument.render_engine.
    status, exit_code, engine, stderr = _render_memo_source(
        vd, out_pdf, requested_engine="xelatex"
    )

    assert status == COMPILE_OK
    # Per-thread (xelatex) wins over per-theme (weasyprint).
    assert engine == MEMO_ENGINE_XELATEX
    cmd = captured[0]
    assert f"--pdf-engine={MEMO_ENGINE_XELATEX}" in cmd


def test_per_theme_engine_used_when_per_thread_absent(monkeypatch, tmp_path):
    """Without a per-thread override, the per-theme default still applies.

    Companion to ``test_per_thread_render_engine_wins_over_per_theme``:
    asserts that when ``requested_engine`` is ``None`` (no per-thread
    pin), the per-theme value from ``theme.yml`` is honored. Together
    the two tests pin both halves of the
    ``effective_engine = requested_engine or theme_engine`` precedence.
    """
    consumer = _seed_consumer(tmp_path)
    project = consumer / "demo"
    _write_brief(project, theme="sphere-semi")
    _write_theme_yml(consumer, "sphere-semi", "render_engine: xelatex\n")

    vd = project / "memo" / "memo.1"
    vd.mkdir(parents=True)
    (vd / "memo.md").write_text("# Body\n", encoding="utf-8")

    # Every engine available — without the theme pin, weasyprint would win.
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: True)
    monkeypatch.setattr(shutil, "which", lambda name: "/x/" + name)
    captured: list = []
    monkeypatch.setattr(subprocess, "run", _record_pandoc(captured, returncode=0))

    out_pdf = vd / "memo.pdf"
    # No per-thread override; per-theme should fire.
    status, exit_code, engine, stderr = _render_memo_source(vd, out_pdf)

    assert status == COMPILE_OK
    assert engine == MEMO_ENGINE_XELATEX
