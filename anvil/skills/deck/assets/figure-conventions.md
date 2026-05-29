# matplotlib figure conventions — `anvil:deck`

This file is consumed by `deck-figures` (when it runs `figures/src/*.py` scripts
to render matplotlib charts) and by the `deck-vision` critic (when it scores the
rendered vision dimensions: v3 `axis_legibility`, v4 `palette_adherence`, and v5
`mathtext_artifacts`). It is the **matplotlib** side of the deck asset pipeline.
The **MathJax / mermaid** side — inline `$...$` math and fenced ```mermaid
diagrams in `deck.md` — lives in `assets/marp-renderer.md`. The two cross-
reference each other; neither duplicates the other.

A matplotlib chart in a fundraising deck has to survive two things the source-
only critics never look at: a projector at the back of a conference room, and a
Marp theme it composites onto. The conventions below exist so a chart written by
a drafter and rendered by `deck-figures` reads cleanly in both, and so the
`deck-vision` critic has nothing to flag.

## 1. Dollar signs and mathtext

matplotlib parses `$...$` in **every** text element as math mode (mathtext). A
label written as a plain Python string —

```python
ax.set_title("Oura $11B / Whoop $10.1B")
```

— renders as `Oura 11B/Whoop10.1B`: the dollar signs are swallowed as math
delimiters, and the text between them is set in italic math font with the
inter-letter spacing collapsed. On a financial slide this is not a cosmetic
glitch; the `$` carries the meaning (these are dollar amounts), and dropping it
changes what the slide says.

**Fix: escape every literal `$` as `\$`** in every text element a chart
produces — `set_xlabel`, `set_ylabel`, `set_title`, per-bar annotations,
legend entries, and any tick labels you format yourself. Use a raw f-string so
the backslash reaches matplotlib intact:

```python
label = rf"\${v / 1000:.1f}B"          # -> "$11.0B", literal dollar sign
ax.set_title(rf"Oura \$11B / Whoop \$10.1B")
ax.annotate(rf"\${row.arr_m:.1f}M", (x, y))
ax.set_ylabel(r"Revenue (\$M)")
```

The rule is per-element and per-string: a `$` anywhere in any string handed to
matplotlib needs the escape, including inside an f-string interpolation result.

### Anti-pattern: do NOT disable mathtext globally

The tempting shortcut is to turn math parsing off for the whole figure:

```python
plt.rcParams["text.parse_math"] = False    # DO NOT DO THIS
```

This breaks the log-axis `LogFormatter`. matplotlib's own log-scale tick
formatter emits its tick labels **as mathtext** — `$\mathdefault{10^{1}}$`,
`$\mathdefault{10^{2}}$`, and so on — to get the superscript exponents. With
`text.parse_math = False`, those tick labels stop being interpreted as math and
render as the literal LaTeX source string `$\mathdefault{10^{1}}$` on the axis.
So the global switch trades one rendering bug (swallowed `$` in your own labels)
for a worse one (every log-axis tick printed as raw LaTeX). Escape per-string
with `\$` instead; it is the only approach that leaves the formatter's own
mathtext untouched.

## 2. DPI and figure size

Charts are projected, not read on a laptop. Legibility is a function of
`figsize × dpi`, not DPI alone, so set both:

- **`figsize=(12, 7)`** — the shipped convention for slide-scale charts (wide
  enough to fill a 16:9 content area without the figurer up-scaling a small
  image).
- **200 DPI is the recommended default** for `savefig`. It gives crisp labels at
  projection scale.
- **150 DPI is the hard floor.** Below 150 the `deck-vision` v3 `axis_legibility`
  dimension starts flagging charts as illegible at projection scale. The shipped
  example scripts in `commands/deck-figures.md` and `assets/marp-renderer.md` use
  `dpi=150` — that is the floor, not a target; prefer 200 for new charts.

```python
fig, ax = plt.subplots(figsize=(12, 7), dpi=120)   # display dpi for layout
fig.savefig(OUT, dpi=200, bbox_inches="tight", transparent=True)
```

`bbox_inches="tight"` trims surrounding whitespace so the chart fills the slide
region; it also reduces the chance of label cropping (`deck-vision` v2).

## 3. Palette

Figures should track the Marp theme so a chart does not look pasted-in next to
the slide chrome. **Don't copy hex values by hand** — import the canonical
palette from `anvil/lib/figures/palette.py`, which mirrors
`anvil/skills/deck/assets/anvil-deck.css` `:root` (a drift-detection test keeps
the two in sync, so the imported tokens are never stale).

**The zero-effort default — call `apply()`.** It `plt.style.use`-es the shipped
`anvil.mplstyle`, which sets a navy-first series `prop_cycle`, the brand ink/rule
axis colors, Helvetica font, 200 DPI, and transparent `savefig`. A chart that
just calls `apply()` is on-brand with no per-series color bookkeeping:

```python
from anvil.lib.figures.palette import apply
apply()                       # navy-first prop_cycle, ink/rule axes, 200 DPI, transparent
```

**Explicit per-series colors — import the named tokens** when a chart assigns
colors deliberately (a "hero" series in navy, a secondary series in muted grey):

```python
from anvil.lib.figures.palette import (
    ANVIL_NAVY,    # --anvil-accent #1f4e7a — primary / hero series
    ANVIL_INK,     # --anvil-text   #1a1a1a — labels, ticks, titles, annotations
    ANVIL_MUTED,   # --anvil-muted  #6b6b6b — secondary series, de-emphasized
    ANVIL_RULE,    # --anvil-rule   #d6d6d6 — spines, light gridlines, baselines
    ANVIL_RAMP,    # navy-anchored multi-series ramp (navy first)
)
```

For reference, the tokens map to the deck theme's CSS custom properties:

| Role | Python token | CSS custom property | Hex | matplotlib use |
|---|---|---|---|---|
| Accent | `ANVIL_NAVY` | `--anvil-accent` | `#1f4e7a` | Primary series, emphasis bars, the one "hero" data series |
| Ink / text | `ANVIL_INK` | `--anvil-text` | `#1a1a1a` | Axis labels, tick labels, titles, annotations |
| Muted | `ANVIL_MUTED` | `--anvil-muted` | `#6b6b6b` | Secondary series, gridlines, de-emphasized labels |
| Rule | `ANVIL_RULE` | `--anvil-rule` | `#d6d6d6` | Light gridlines, axis spines, baselines |
| Section bg | `ANVIL_BG_SECTION` | `--anvil-bg-section` | `#f5f5f5` | Fill only if a chart must composite onto a `_class: section` / `_class: appendix` slide instead of staying transparent |

Default matplotlib colors (the `C0`/`C1` tab10 cycle, the default `#1f77b4`
blue) are a `deck-vision` v4 `palette_adherence` finding — calling `apply()` or
setting colors from the tokens above prevents it.

**Consumer theme overrides:** the canonical tokens are sourced from the shipped
`anvil-deck.css`. A consumer who overrides the theme via
`.anvil/skills/deck/templates/<their-theme>.css` should re-read their own
`:root` block and use those values — do not hard-code the shipped palette into a
chart for a deck on a custom theme.

## 4. Transparent backgrounds

Always save with `transparent=True`:

```python
fig.savefig(OUT, dpi=200, bbox_inches="tight", transparent=True)
```

A chart with a baked-in white background drops a white box onto any slide that
isn't pure white, which looks broken. The deck theme uses three different slide
backgrounds (all in `anvil-deck.css` `:root`):

- `--anvil-bg` `#ffffff` — default white content slides.
- `--anvil-bg-section` `#f5f5f5` — `_class: section` and `_class: appendix`
  slides.
- `--anvil-bg-ask` `#1f4e7a` (= the accent navy) — the full-bleed ask slide.

A transparent PNG composites cleanly onto all three. A chart dropped onto the
navy ask slide with an opaque white background is the most visible failure of
this rule.

## 5. Output-path discipline

A matplotlib script lives at `figures/src/<name>.py`, reads its data from a
co-located `figures/src/<name>.csv`, and writes its rendered PNG one directory
up, to `figures/<name>.png`. Derive both paths from `__file__` so the script
runs the same regardless of the working directory `deck-figures` invokes it
from:

```python
SRC = Path(__file__).parent          # figures/src/
OUT = SRC.parent / "<name>.png"      # figures/<name>.png
df  = pd.read_csv(SRC / "<name>.csv")
```

This is what lets `deck-figures` re-render deterministically and idempotently:
it compares the mtime of `figures/<name>.png` against the `.py` script and the
`.csv` data, and skips the render when the PNG is newer than both.

**Never fabricate data.** If the `.csv` a script needs does not exist, the
script should refuse rather than generate placeholder numbers — a fabricated
chart in a fundraising deck is the easiest critical flag to trigger in the audit.
Extract real numbers from the brief into a CSV first; do not inline made-up data.

## 6. Canonical script template

A single minimal script demonstrating all of the above — the `apply()` shared
style (which carries `figsize=(12, 7)`, 200 DPI, `transparent=True`, ink/rule
axes, and the navy-first `prop_cycle`), imported palette tokens, `$`-escaping,
and the `OUT = SRC.parent / "<name>.png"` output path:

```python
#!/usr/bin/env python3
"""figures/src/traction.py — ARR bars, one hero series.

Reads figures/src/traction.csv (columns: quarter, arr_m).
Writes figures/traction.png.
"""
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

# --- shared on-brand style (section 3): navy-first prop_cycle, ink/rule axes,
#     Helvetica font, 200 DPI, transparent savefig, figsize 12x7. ---
from anvil.lib.figures.palette import apply, ANVIL_NAVY, ANVIL_INK
apply()

# --- output-path discipline (section 5) ---
SRC = Path(__file__).parent
OUT = SRC.parent / "traction.png"
df = pd.read_csv(SRC / "traction.csv")   # no data file -> let pandas raise, never fabricate

fig, ax = plt.subplots()                 # figsize/dpi come from apply()

ax.bar(df["quarter"], df["arr_m"], color=ANVIL_NAVY)   # explicit hero series

# --- $-escaping: every literal $ is \$ (section 1) ---
ax.set_title(r"ARR by quarter (\$M)")
ax.set_xlabel("Quarter")
ax.set_ylabel(r"ARR (\$M)")
for x, v in zip(df["quarter"], df["arr_m"]):
    ax.annotate(rf"\${v:.1f}M", (x, v), ha="center", va="bottom", color=ANVIL_INK)

fig.tight_layout()
# --- savefig: 200 DPI + transparent come from apply()'s style ---
fig.savefig(OUT)
```

## 7. What the `deck-vision` critic catches

These conventions exist to prevent the rendered-pixel defects the `deck-vision`
critic scores. This section points at the detection; it does not re-specify it —
see `commands/deck-vision.md` for the dimension definitions:

- **Mathtext artifacts** — `deck-vision` v5 `mathtext_artifacts` flags italic
  letters adjacent to dollar signs and literal LaTeX source on the chart. When a
  swallowed `$` changes the meaning of a financial slide, it escalates to the
  critical flag `mathtext_artifact_breaks_meaning`. Section 1 is the prevention.
- **Off-palette colors** — `deck-vision` v4 `palette_adherence` flags default
  matplotlib colors that don't match the theme palette. Section 3 is the
  prevention.
- **Sub-150-DPI / illegible labels** — `deck-vision` v3 `axis_legibility` flags
  charts whose axis and tick labels are illegible at projection scale. Sections
  2 (DPI/figsize) and 3 (ink color) are the prevention.
- **Label cropping** — `deck-vision` v2 `label_cropping` flags axis labels,
  legends, or annotations truncated by the figure border. `bbox_inches="tight"`
  (section 2) is the prevention.

`deck-design` (rubric dimension 8) owns general image quality — pixelation and
palette *consistency across slides* — but the per-chart mathtext, palette-hex,
and legibility specifics live in `deck-vision`.

## 8. See also

- `assets/marp-renderer.md` — the **mermaid / MathJax** side of the asset
  pipeline (inline `$...$` slide math is independent of the matplotlib `\$`
  escape covered here).
- `commands/deck-figures.md` — the figurer that runs these scripts and renders
  the deck PDF.
- `commands/deck-vision.md` — the vision critic that scores the rendered output
  (the detection counterpart to this prevention doc).
- `anvil/lib/figures/palette.py` — the canonical importable palette tokens
  (`ANVIL_NAVY` etc.) and `apply()` shared style referenced in sections 3 and 6;
  also the shared `anvil.mplstyle` and `mermaid-theme.json`.
- `assets/anvil-deck.css` — `:root` is the cross-format source of truth for the
  palette; `palette.py` mirrors it and a drift test keeps them in sync.
