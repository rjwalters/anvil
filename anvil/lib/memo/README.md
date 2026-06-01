# anvil/lib/memo/

Canonical pinned renderer substrate for `anvil:memo` PDF rendering.

This directory is the framework-level pin for the `anvil:memo` markdown
→ PDF chain. It is the memo-side analog of `anvil/lib/marp/` (the
pinned Marp config shared by `anvil:deck` and `anvil:slides`).

## Status

This is the **Phase 1 substrate** of Epic #158 (the `anvil:memo`
markdown → PDF rendering pipeline). Phase 1 ships the pinned config
files and renderer availability detection. The state machine, the
`memo-render` command, and the reviewer-side rubric wiring land in
Phases 2-4.

Until Phase 3 lands, these files exist for two reasons:

1. They are the **single source of truth** for the chosen typography
   and page-layout pin — when later phases land, they consume these
   files verbatim rather than re-deriving defaults inline.
2. They are referenced by the `MEMO_RENDERER_REMEDIATION` string in
   `anvil/lib/render.py` so the renderer availability check can point
   operators at the right files when an install gap is detected.

## Files

| File | Purpose |
|---|---|
| `styles.css` | Pinned default theme. Helvetica/Arial fallback, 11pt body, 0.75in margins, `@page` rule with footer page numbers. Consumed by the HTML chain (pandoc → weasyprint OR wkhtmltopdf). |
| `template.html` | Pandoc HTML template loading `$title$ / $author$ / $date$` from frontmatter and referencing `styles.css`. Consumed by the HTML chain. |
| `template.tex` | xelatex fallback template. Minimal `\documentclass{article}` with `geometry`, `fancyhdr`, `lastpage`, `hyperref`. Consumed only when neither weasyprint nor wkhtmltopdf is on PATH. |

## The rendering chain

The memo render path, from Phase 3 onward, is:

```
memo.md
  │
  ├── pandoc --template template.html --css styles.css → memo.html
  │       │
  │       ├── weasyprint memo.html memo.pdf   (preferred)
  │       └── wkhtmltopdf memo.html memo.pdf  (fallback)
  │
  └── pandoc --pdf-engine=xelatex --template template.tex → memo.pdf
          (fallback when neither HTML engine is available)
```

### Why this chain (and not some other one)

Each branch addresses a real install constraint observed on the
canary side. The chain was selected by the architect in Epic #158 and
is pinned here so Phase 3's command code is config-not-code.

- **`pandoc` is the common front-end.** It owns frontmatter parsing,
  citation rendering (when memos start using `cite.py`), table
  formatting, and `--metadata` injection. It is already a documented
  Anvil dependency (`anvil/lib/render.py::render_pandoc_to_pdf`); we
  are not adding a new tool, just naming a new path through it.
- **`weasyprint` is the preferred HTML-to-PDF engine.** It is a
  Python package (`pip install weasyprint`), supports the full CSS
  paged-media spec (the `@page` rule + counter(page) used in
  `styles.css`), and produces high-fidelity output. The cost is a
  Python install and a handful of native deps (cairo, pango).
- **`wkhtmltopdf` is the HTML fallback.** It is a standalone binary
  (`brew install --cask wkhtmltopdf` / `apt-get install
  wkhtmltopdf`), supports the bulk of HTML+CSS without the Python
  install, and has slightly different paged-media handling that the
  framework treats as acceptable for memos. Some `@page` rules are
  passed via `--header-* / --footer-*` CLI flags rather than the CSS
  itself — the Phase 3 command code will handle that translation.
- **`xelatex` is the engine-of-last-resort.** It exists for
  environments where the HTML chain is unavailable but TeX Live is
  installed. The output is not pixel-identical to the HTML chain by
  design — the HTML chain owns the canonical typography. The xelatex
  fallback gets you a memo PDF, period.

### Renderer detection

`anvil/lib/render.py` ships three availability checks corresponding
to the three engines in the chain:

```python
from anvil.lib.render import (
    check_pandoc_available,
    check_weasyprint_available,
    check_wkhtmltopdf_available,
    MEMO_RENDERER_REMEDIATION,
)

if not check_pandoc_available():
    raise RenderError(MEMO_RENDERER_REMEDIATION)

if check_weasyprint_available():
    engine = "weasyprint"
elif check_wkhtmltopdf_available():
    engine = "wkhtmltopdf"
elif shutil.which("xelatex"):
    engine = "xelatex"
else:
    raise RenderError(MEMO_RENDERER_REMEDIATION)
```

`MEMO_RENDERER_REMEDIATION` carries the full install story for all four
binaries (pandoc + weasyprint + wkhtmltopdf + xelatex) so the operator
sees one actionable error rather than four sequential ones.

## Override discipline

Consumers who want custom typography, page layout, or LaTeX preamble
override the relevant file under their installed path:

| Override target | Path (consumer repo) |
|---|---|
| Default styles | `<consumer>/.anvil/lib/memo/styles.css` |
| HTML template | `<consumer>/.anvil/lib/memo/template.html` |
| xelatex template | `<consumer>/.anvil/lib/memo/template.tex` |

The install script (`scripts/install-anvil.sh`) copies the framework
defaults to `.anvil/lib/memo/` and respects in-place modifications
under the standard `--force` discipline (see #163). When the consumer
ships a custom `styles.css`, Phase 3's `memo-render` command picks it
up unchanged.

### Maintainer policy on aesthetic PRs

The default theme is **deliberately minimal**:

- System sans-serif fallback (Helvetica / Arial), no `@font-face`.
- 11pt body, 1.45 line-height, 0.75in margins.
- No color, no logos, no background images, no decorative rules.

Aesthetic-tuning PRs against the framework defaults are
**out-of-scope** by maintainer policy. The framework ships a usable,
reproducible default; consumers customize via the override path
above. This mirrors the `anvil/lib/marp/config.yml` discipline (the
shipped Marp themes are also deliberately neutral, with consumer
overrides expected for any branded deck).

Functional bugs in the defaults (an `@page` rule that breaks
weasyprint, a `\setmainfont` line that fails on TeX Live without
Helvetica, a pandoc template variable that doesn't render) ARE
in-scope and should be filed as issues.

## See also

- `anvil/lib/marp/config.yml` — the precedent for a pinned framework
  renderer config with a "why pinned" doc block. Memo's
  `lib/memo/README.md` is modeled on the prose in that file.
- `anvil/lib/render.py` — `check_pandoc_available`,
  `check_weasyprint_available`, `check_wkhtmltopdf_available`, and the
  `MEMO_RENDERER_REMEDIATION` constant.
- Epic #158 — the four-phase plan for the full `anvil:memo` PDF
  rendering pipeline. This file is the Phase 1 substrate.
