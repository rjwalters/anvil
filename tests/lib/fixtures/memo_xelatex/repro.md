---
title: "Pandoc 3.x xelatex compat reproducer"
author: "Anvil framework tests"
date: "2026-06-03"
---

# Reproducer for issue #277

This fixture exercises every markdown construct pandoc 3.x emits LaTeX
for that the shipped `template.tex` historically failed on. Each section
below maps to a row in the curator's missing-package table.

## Inline styling and strikethrough (triggers `\st`, requires `soul` / `lua-ul`)

This paragraph has \textbf{bold}, \emph{italic}, ~~strikethrough~~, and
an [inline link to anvil](https://github.com/rjwalters/anvil) all in one
line. Plus an `inline code span` (triggers `\Verb` from `fancyvrb`).

## Footnote (triggers `footnotehyper` / `footnote` interaction with hyperref)

This sentence carries a footnote.[^1]

[^1]: Footnotes interact with `hyperref` via `footnotehyper`; older
    pandoc emitted plain `\footnote`, modern pandoc emits
    `\footnote{...}` inside `\footnotehyper` context.

## Code block (triggers `xcolor` for highlight macros)

```python
def hello() -> str:
    return "world"
```

## Table (triggers `longtable`, `booktabs`, `array`, `calc`, `etoolbox`, `\newcounter{none}`)

| Engine     | Role             | Notes                          |
|------------|------------------|--------------------------------|
| weasyprint | Preferred        | Best CSS paged-media fidelity  |
| wkhtmltopdf| Fallback         | Standalone binary, no Python   |
| xelatex    | Engine-of-last-resort | TeX Live, this file's target |

## Tight list (triggers `\tightlist`)

- one
- two
- three

## Heading (triggers `bookmark` interaction with hyperref)

The heading on this line itself produces the `\bookmark` emission that
breaks the minimal template when `bookmark.sty` isn't loaded.
