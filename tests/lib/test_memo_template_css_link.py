"""Functional regression tests for the ``anvil:memo`` HTML template's
``--css`` insertion loop (issue #470).

Issue #470: ``anvil/lib/memo/template.html`` accepted ``--metadata`` and
``header-includes`` but had no ``$for(css)$`` loop, so pandoc's ``--css``
flag — the documented stylesheet-delivery mechanism used by both
``anvil/lib/memo/README.md`` and ``anvil/lib/render_gate.py`` (which
passes the absolute path to ``styles.css``) — was silently dropped.
Every HTML-chain memo render (weasyprint / wkhtmltopdf) produced an
unstyled PDF with no diagnostic. The regression shipped in PR #331,
which removed the hardcoded relative ``<link>`` on the (incorrect)
premise from #319 that ``--css`` alone styled the output.

These tests mechanize the issue's own repro: run the documented pandoc
invocation against a tmp memo + tmp stylesheet and assert the emitted
HTML carries exactly one ``<link rel="stylesheet">`` whose href is the
exact absolute path passed via ``--css``. Absolute-path assertion
matters: ``render_gate.py`` passes ``str(styles_css)`` absolute, which
is what keeps weasyprint's base-URL resolution failure (#319) from
recurring.

Tests skip gracefully when pandoc is not on PATH, following the
``check_*_available()`` graceful-degradation precedent (#102).

The filename ``test_memo_template_css_link.py`` is distinct from every
other test module per the #58 packaging convention.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from anvil.lib import render
from anvil.lib.render import check_pandoc_available

pytestmark = pytest.mark.skipif(
    not check_pandoc_available(),
    reason="pandoc not on PATH (graceful-degradation skip, see #102)",
)


TEMPLATE_HTML = Path(render.__file__).parent / "memo" / "template.html"

MEMO_MD = """\
# Test

This should be **styled**.
"""

STYLES_CSS = """\
body { color: red; font-family: Courier; }
h1 { color: blue; }
"""


def _render_html(tmp_path: Path, extra_args: list[str]) -> str:
    """Run the documented pandoc invocation and return the output HTML."""
    memo_md = tmp_path / "memo.md"
    memo_md.write_text(MEMO_MD, encoding="utf-8")
    out_html = tmp_path / "memo.html"
    cmd = [
        "pandoc",
        str(memo_md),
        "--template",
        str(TEMPLATE_HTML),
        *extra_args,
        "--standalone",
        "-o",
        str(out_html),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"pandoc failed ({result.returncode}): {result.stderr}"
    )
    return out_html.read_text(encoding="utf-8")


def _stylesheet_hrefs(html: str) -> list[str]:
    """Extract the href of every ``<link rel="stylesheet">`` tag."""
    hrefs: list[str] = []
    for tag in re.findall(
        r"""<link\s+[^>]*rel\s*=\s*["']stylesheet["'][^>]*>""",
        html,
        flags=re.IGNORECASE,
    ):
        match = re.search(r"""href\s*=\s*["']([^"']*)["']""", tag)
        if match:
            hrefs.append(match.group(1))
    return hrefs


def test_css_flag_emits_exactly_one_stylesheet_link(tmp_path: Path):
    """The documented invocation (``--css <abs path>``) emits exactly one
    stylesheet link carrying the exact path that was passed.

    This is issue #470's repro, mechanized: before the fix the output
    HTML contained zero stylesheet references and the render appeared
    to succeed.
    """
    styles_css = tmp_path / "styles.css"
    styles_css.write_text(STYLES_CSS, encoding="utf-8")
    css_path = str(styles_css.resolve())

    html = _render_html(tmp_path, ["--css", css_path])
    hrefs = _stylesheet_hrefs(html)
    assert hrefs == [css_path], (
        f"expected exactly one stylesheet link with href={css_path!r} "
        f"(the path passed via --css), got {hrefs!r}. The template's "
        f"$for(css)$ loop is the sole insertion point — without it the "
        f"--css flag is silently dropped (issue #470)."
    )


def test_css_link_href_is_the_absolute_path_passed(tmp_path: Path):
    """The emitted href is the absolute path verbatim — NOT a relative
    rewrite. ``render_gate.py`` passes ``str(styles_css)`` absolute, and
    the absolute href is what keeps weasyprint's base-URL resolution
    failure mode (#319 ``Failed to load stylesheet``) from recurring.
    """
    styles_css = tmp_path / "styles.css"
    styles_css.write_text(STYLES_CSS, encoding="utf-8")
    css_path = str(styles_css.resolve())

    html = _render_html(tmp_path, ["--css", css_path])
    hrefs = _stylesheet_hrefs(html)
    assert len(hrefs) == 1
    assert Path(hrefs[0]).is_absolute(), (
        f"stylesheet href {hrefs[0]!r} is not absolute — weasyprint "
        f"would resolve it against the input HTML's base URL and fail "
        f"the fetch (issue #319)."
    )


def test_no_css_flag_emits_no_stylesheet_link(tmp_path: Path):
    """Without ``--css`` the ``$for(css)$`` loop emits nothing — no
    half-formed or hardcoded link sneaks in (the #319 protection in
    functional form).
    """
    html = _render_html(tmp_path, [])
    hrefs = _stylesheet_hrefs(html)
    assert hrefs == [], (
        f"expected no stylesheet links when --css is omitted, got "
        f"{hrefs!r} — a hardcoded href has crept back into the "
        f"template (issue #319)."
    )
