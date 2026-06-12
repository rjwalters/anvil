"""Tests for the ``anvil:memo`` PDF render-chain availability checks in
``anvil.lib.render``.

This module is the test counterpart to Phase 1 of Epic #158 (the
`anvil:memo` markdown → PDF rendering pipeline). The Phase 1 substrate
ships:

- ``anvil/lib/memo/`` directory with ``styles.css``, ``template.html``,
  ``template.tex``, and a ``README.md`` documenting the override
  discipline.
- Three new ``check_*_available()`` helpers in ``anvil/lib/render.py``:
  ``check_pandoc_available``, ``check_weasyprint_available``,
  ``check_wkhtmltopdf_available``.
- A ``MEMO_RENDERER_REMEDIATION`` constant carrying the install story
  for pandoc, weasyprint, wkhtmltopdf, and xelatex.

The tests focus on:

1. The three availability checks are exported and callable.
2. Each check correctly delegates to ``shutil.which`` (verified by
   monkeypatching).
3. The remediation constant mentions all four engines so an operator
   sees one actionable install story rather than four sequential ones.
4. Graceful-skip semantics: when nothing is on PATH, every check
   returns ``False`` (the caller, not the check, decides whether to
   raise — mirrors the #102 auto-shrink pattern).
5. The substrate files under ``anvil/lib/memo/`` exist on disk so
   ``MEMO_RENDERER_REMEDIATION``'s "see anvil/lib/memo/README.md"
   reference resolves.

The filename ``test_memo_render_detection.py`` is distinct from the
existing ``test_render.py`` so the per-skill packaging convention in
#58 holds (no pytest filename collisions across the suite).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from anvil.lib import render
from anvil.lib.render import (
    MEMO_RENDERER_REMEDIATION,
    check_pandoc_available,
    check_weasyprint_available,
    check_wkhtmltopdf_available,
)


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------


def test_module_exports_three_memo_chain_checks():
    """The three new availability checks are importable from the module."""
    assert callable(render.check_pandoc_available)
    assert callable(render.check_weasyprint_available)
    assert callable(render.check_wkhtmltopdf_available)


def test_module_exports_memo_remediation_constant():
    """The remediation constant is importable from the module."""
    assert isinstance(render.MEMO_RENDERER_REMEDIATION, str)
    assert len(render.MEMO_RENDERER_REMEDIATION) > 0


def test_each_check_has_a_docstring():
    """Each new function has a docstring (matches existing render.py
    discipline).
    """
    for fn in (
        check_pandoc_available,
        check_weasyprint_available,
        check_wkhtmltopdf_available,
    ):
        assert fn.__doc__ is not None and fn.__doc__.strip() != ""


def test_all_includes_new_symbols():
    """The new public names are listed in ``__all__`` so ``from
    anvil.lib.render import *`` exposes them.
    """
    assert "MEMO_RENDERER_REMEDIATION" in render.__all__
    assert "check_pandoc_available" in render.__all__
    assert "check_weasyprint_available" in render.__all__
    assert "check_wkhtmltopdf_available" in render.__all__


# ---------------------------------------------------------------------------
# Availability checks — delegation to shutil.which
# ---------------------------------------------------------------------------


def test_check_pandoc_returns_true_when_on_path(monkeypatch):
    """``check_pandoc_available`` returns ``True`` when ``shutil.which``
    finds ``pandoc``.
    """
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: "/usr/local/bin/pandoc" if name == "pandoc" else None,
    )
    assert check_pandoc_available() is True


def test_check_pandoc_returns_false_when_absent(monkeypatch):
    """``check_pandoc_available`` returns ``False`` when ``shutil.which``
    returns ``None``.
    """
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert check_pandoc_available() is False


def test_check_weasyprint_returns_true_when_on_path(monkeypatch):
    """``check_weasyprint_available`` returns ``True`` when
    ``shutil.which`` finds ``weasyprint``.
    """
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: "/usr/local/bin/weasyprint"
        if name == "weasyprint"
        else None,
    )
    assert check_weasyprint_available() is True


def test_check_weasyprint_returns_false_when_absent(monkeypatch):
    """``check_weasyprint_available`` returns ``False`` when
    ``shutil.which`` returns ``None``.
    """
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert check_weasyprint_available() is False


def test_check_wkhtmltopdf_returns_true_when_on_path(monkeypatch):
    """``check_wkhtmltopdf_available`` returns ``True`` when
    ``shutil.which`` finds ``wkhtmltopdf``.
    """
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: "/usr/local/bin/wkhtmltopdf"
        if name == "wkhtmltopdf"
        else None,
    )
    assert check_wkhtmltopdf_available() is True


def test_check_wkhtmltopdf_returns_false_when_absent(monkeypatch):
    """``check_wkhtmltopdf_available`` returns ``False`` when
    ``shutil.which`` returns ``None``.
    """
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert check_wkhtmltopdf_available() is False


def test_each_check_returns_bool_type(monkeypatch):
    """Every check returns an actual ``bool``, not a truthy value (path
    string) leaking through. This matters because the documented contract
    says ``bool``; callers branch on ``if check_*_available()`` and a
    string would silently still work but break ``is True`` / ``is False``
    assertions in downstream tests.
    """
    monkeypatch.setattr(shutil, "which", lambda name: "/some/path/" + name)
    for fn in (
        check_pandoc_available,
        check_weasyprint_available,
        check_wkhtmltopdf_available,
    ):
        result = fn()
        assert isinstance(result, bool), (
            f"{fn.__name__} returned {type(result).__name__}, expected bool"
        )


# ---------------------------------------------------------------------------
# Graceful-skip semantics — nothing on PATH
# ---------------------------------------------------------------------------


def test_all_three_checks_false_when_nothing_on_path(monkeypatch):
    """When NOTHING is on PATH (a fresh CI container with no install),
    all three checks return ``False`` and NEITHER raises. The caller
    decides whether to raise based on the combined boolean — mirrors the
    auto-shrink graceful-skip pattern (#102).
    """
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert check_pandoc_available() is False
    assert check_weasyprint_available() is False
    assert check_wkhtmltopdf_available() is False


def test_checks_only_query_their_own_binary(monkeypatch):
    """Each check queries ``shutil.which`` for exactly the right binary
    name. A bug where ``check_weasyprint_available`` accidentally queried
    ``pandoc`` would be silent in production (both might be installed),
    so we pin the name explicitly.
    """
    queried: list[str] = []

    def fake_which(name: str):
        queried.append(name)
        return None

    monkeypatch.setattr(shutil, "which", fake_which)
    check_pandoc_available()
    check_weasyprint_available()
    check_wkhtmltopdf_available()
    assert queried == ["pandoc", "weasyprint", "wkhtmltopdf"]


# ---------------------------------------------------------------------------
# MEMO_RENDERER_REMEDIATION — install story
# ---------------------------------------------------------------------------


def test_remediation_mentions_all_four_engines():
    """The remediation string covers pandoc, weasyprint, wkhtmltopdf, and
    xelatex. An operator hitting this error should see one install story,
    not four sequential errors.
    """
    text = MEMO_RENDERER_REMEDIATION.lower()
    assert "pandoc" in text
    assert "weasyprint" in text
    assert "wkhtmltopdf" in text
    assert "xelatex" in text


def test_remediation_mentions_both_install_managers():
    """The remediation string carries both macOS (``brew``) and
    Debian/Ubuntu (``apt-get``) install instructions, matching the
    existing remediation precedents (``PDFJAM_REMEDIATION``,
    ``MMDC_REMEDIATION``).
    """
    text = MEMO_RENDERER_REMEDIATION
    assert "brew" in text
    assert "apt-get" in text


def test_remediation_points_at_lib_memo_readme():
    """The remediation string references ``anvil/lib/memo/README.md`` so
    operators can read the full chain rationale. This pin keeps the
    install story and the design rationale physically linked.
    """
    assert "anvil/lib/memo/README.md" in MEMO_RENDERER_REMEDIATION


def test_remediation_distinguishes_preferred_and_fallback():
    """The string makes it clear weasyprint is preferred and the others
    are fallbacks. An operator picking one engine should be able to read
    the string and choose without consulting the README.
    """
    text = MEMO_RENDERER_REMEDIATION.lower()
    assert "preferred" in text
    assert "fallback" in text


# ---------------------------------------------------------------------------
# Substrate files on disk
# ---------------------------------------------------------------------------


@pytest.fixture
def memo_lib_dir() -> Path:
    """Path to the ``anvil/lib/memo/`` substrate dir (relative to repo root).

    Tests resolve this from the rendered module path so they pass both in
    the dev tree (``anvil/lib/memo/``) and against an installed consumer
    repo (``.anvil/lib/memo/``).
    """
    return Path(render.__file__).parent / "memo"


def test_lib_memo_directory_exists(memo_lib_dir: Path):
    """The Phase 1 substrate dir exists alongside ``anvil/lib/marp/``."""
    assert memo_lib_dir.exists(), f"missing dir: {memo_lib_dir}"
    assert memo_lib_dir.is_dir()


def test_lib_memo_ships_styles_css(memo_lib_dir: Path):
    """``styles.css`` ships with the pinned default theme."""
    css = memo_lib_dir / "styles.css"
    assert css.exists(), f"missing pinned theme: {css}"
    text = css.read_text(encoding="utf-8")
    # Sanity-check the pinned values called out in the issue body.
    assert "@page" in text
    assert "11pt" in text  # 11pt body
    assert "0.75in" in text  # 0.75in margins
    # The page-number footer is mentioned (either as counter(page) or as a
    # bottom-center @page rule).
    assert "counter(page)" in text


def test_lib_memo_ships_pandoc_html_template(memo_lib_dir: Path):
    """``template.html`` ships with the pandoc variables referenced.

    Stylesheet delivery is via pandoc ``--css`` (see
    ``anvil/lib/render_gate.py``), which populates the ``css`` template
    variable — so the template MUST carry the standard pandoc
    ``$for(css)$ … $endfor$`` link loop. Without it the ``--css`` flag
    is silently dropped and every HTML-chain memo render produces an
    unstyled PDF (issue #470, a regression introduced by #331).
    """
    html = memo_lib_dir / "template.html"
    assert html.exists(), f"missing pandoc HTML template: {html}"
    text = html.read_text(encoding="utf-8")
    # Pandoc variables consumed.
    assert "$title$" in text
    assert "$author$" in text
    assert "$date$" in text
    assert "$body$" in text
    # The --css insertion loop (issue #470): without ``$for(css)$`` the
    # pandoc --css flag has no insertion point and is silently ignored.
    assert "$for(css)$" in text, (
        "template.html is missing the pandoc ``$for(css)$`` loop — the "
        "--css flag passed by render_gate.py is silently dropped and "
        "HTML-chain memo renders ship unstyled (issue #470)."
    )
    assert 'href="$css$"' in text, (
        "template.html must emit the stylesheet link via the ``$css$`` "
        "template variable (issue #470)."
    )


def test_lib_memo_template_html_avoids_bare_stylesheet_link(
    memo_lib_dir: Path,
) -> None:
    """A hardcoded-href ``<link rel="stylesheet">`` must not return.

    A literal ``<link rel="stylesheet" href="styles.css" />`` inside
    the template body is resolved by weasyprint against the input
    HTML's effective base URL — which when pandoc invokes the template
    ends up being the CWD pandoc ran from (the consumer repo root).
    That fetch fails with a stderr ``ERROR: Failed to load
    stylesheet`` and would be promoted to a hard error by the
    ``--fail-if-warnings`` invariant in ``anvil/lib/render_gate.py``.
    See issue #319.

    The ONE permitted link shape is the pandoc-variable form
    ``href="$css$"`` inside the ``$for(css)$`` loop (issue #470):
    pandoc substitutes the value of the ``--css`` flag there, and
    ``render_gate.py`` passes an absolute path — so the #319
    base-URL-resolution failure mode never applies. Any other
    ``<link rel="stylesheet">`` (a hardcoded href) is still forbidden.

    This is the inverse-shape regression guard modeled on
    ``tests/skills/memo/test_memo_styles_page_size_doc.py::
    test_styles_css_page_block_avoids_bare_letter_keyword`` — the
    "this shape must NOT appear" pattern, narrowed per #470 to allow
    exactly the variable-substituted form.
    """
    html = memo_lib_dir / "template.html"
    text = html.read_text(encoding="utf-8")
    # Match ``<link rel="stylesheet"`` with single or double quotes and
    # optional whitespace. Strip the HTML comment header first so the
    # documentation block (which legitimately mentions the pandoc
    # ``--css`` invocation) does not trip the guard.
    body = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    link_tags = re.findall(
        r"""<link\s+[^>]*rel\s*=\s*["']stylesheet["'][^>]*>""",
        body,
        flags=re.IGNORECASE,
    )
    for tag in link_tags:
        href = re.search(r"""href\s*=\s*["']([^"']*)["']""", tag)
        assert href is not None and href.group(1) == "$css$", (
            f"template.html contains a stylesheet link with a "
            f"hardcoded href: {tag!r}. weasyprint resolves a relative "
            f"href against pandoc's CWD (the consumer repo root), "
            f"failing the fetch and conflicting with the absolute "
            f"``--css`` path that render_gate.py already passes "
            f"(issue #319). The only permitted form is "
            f"``href=\"$css$\"`` inside the ``$for(css)$`` loop "
            f"(issue #470)."
        )


def test_lib_memo_ships_xelatex_template(memo_lib_dir: Path):
    """``template.tex`` ships as the xelatex fallback."""
    tex = memo_lib_dir / "template.tex"
    assert tex.exists(), f"missing xelatex template: {tex}"
    text = tex.read_text(encoding="utf-8")
    # Minimal LaTeX scaffolding markers.
    assert r"\documentclass" in text
    assert r"\begin{document}" in text
    assert r"\end{document}" in text
    # Pandoc-template variables.
    assert "$body$" in text


def test_lib_memo_ships_readme(memo_lib_dir: Path):
    """``README.md`` documents the override discipline and "why pinned".

    Modeled on the prose in ``anvil/lib/marp/config.yml``'s doc block per
    the architect's note in #168.
    """
    readme = memo_lib_dir / "README.md"
    assert readme.exists(), f"missing README: {readme}"
    text = readme.read_text(encoding="utf-8").lower()
    # The two load-bearing sections called out in the issue body.
    assert "override" in text
    assert "pinned" in text or "pin" in text
    # The three engines documented.
    assert "weasyprint" in text
    assert "wkhtmltopdf" in text
    assert "xelatex" in text
