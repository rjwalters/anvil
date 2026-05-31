"""Static lint pass that mirrors the marp-vscode `slide-content-overflow` diagnostic.

This module is a Python port of the upstream diagnostic introduced in
marp-team/marp-vscode (see https://github.com/marp-team/marp-vscode/issues/519
and the diagnostic file
`src/diagnostics/preview/slide-content-overflow.ts`). The upstream
implementation is **DOM-based**: it inspects the rendered preview's
`section.scrollHeight > section.clientHeight` and
`section.scrollWidth > section.clientWidth`. That cannot run statically in a
markdown pipeline — so this port re-implements the same conceptual rule
("does the slide content exceed the safe area?") as a deterministic capacity
budget over the markdown source.

Upstream port pin
-----------------
- repo:    marp-team/marp-vscode
- file:    src/diagnostics/preview/slide-content-overflow.ts
- sha:     3b8617431867b68f4241c453ae2c7601a4298aa8
- rule(s): slide-content-overflow  (the only diagnostic ported in this seed)

When upstream evolves (additional diagnostics, refined heuristics in the
runtime DOM tracker, etc.), follow-up work should:

1. Re-fetch the upstream file at a newer SHA.
2. Update the SHA pin above.
3. Add new rules to ``_RULES`` below if they map cleanly onto a static check.

Anvil-specific design choices vs. upstream
------------------------------------------
- **Static, not DOM.** Upstream measures the actual rendered slide;
  this port estimates capacity from the markdown source. As a result, the
  Anvil rule is conservative — it catches the obvious overflow patterns
  (the #24 figure + 4 bullets repro and the #25 `_class: ask` H1 + H2 repro
  exhaustively) but defers borderline cases to the VLM critic in issue #30.
- **Severity mapping is stricter.** Upstream emits ``Warning``; in the Anvil
  pipeline the rule is wired as a review-phase hard-fail (per the curator
  addendum on issue #31). The severity returned by ``lint_deck`` is
  ``"error"`` when the capacity overage is clear, ``"warning"`` when borderline,
  and ``"info"`` only as a suppressed result of the
  ``anvil-lint-disable: slide-content-overflow`` escape hatch.
- **Geometry constants** are pulled from
  ``anvil/skills/deck/assets/anvil-deck.css`` and the equivalent slides
  theme: 16:9, 1280×720, padding 56/72, base font 26px, line-height 1.45.
  These constants live at module scope so a consumer with a custom theme can
  override them via the public API (``lint_deck(path, geometry=...)``).
- **Escape hatch.** A per-slide HTML comment of the form
  ``<!-- anvil-lint-disable: slide-content-overflow -->`` suppresses the
  rule for that one slide; the finding is downgraded to ``info`` so the
  reviser still sees that the slide is dense but ``advance`` is not blocked.

Anvil-specific scope
--------------------
- Only the ``slide-content-overflow`` rule is ported from upstream. The
  ``image-resource``, ``frontmatter-deprecated-syntax``, and other
  marp-vscode rules are not ported (they are either irrelevant to Anvil's
  pipeline or out of scope for this iteration).
- The ``figure-italic-supporting-line-too-long`` rule is **Anvil-original**
  (no marp-vscode upstream). It detects a long italic supporting line
  directly under a standalone figure block — the figure-idiom regression
  documented in issues #100 / #101. Authors fold what would have been three
  bullets into one italic sentence; the sentence wraps to 2-3 rendered lines
  and clips at the slide bottom on 16:9 because italic glyph width is ~5%
  wider than upright body weight and the caption margins eat additional
  vertical space. The threshold (18 words OR 108 characters) is anchored
  against the shipped ``clean_figure_plus_supporting_line.md`` fixture and
  the canary regressions from the post-#68 re-render wave (bower.v2 slides
  7/10, citation-clear.v2 slides 7/8, bibliotype.v2 slide 7 — all 25-32
  words). Severity is ``warning`` (the check is a heuristic for *likely*
  overflow; the upstream-derived ``slide-content-overflow`` rule remains
  the authoritative hard-fail capacity check).
- The ``inline-display-style-dropped`` rule is **Anvil-original** (no
  marp-vscode upstream). It detects inline ``style="...display:(grid|flex|
  inline-grid|inline-flex)..."`` attributes in the deck markdown source.
  Marp renders slide content into a ``<foreignObject>`` element inside an
  SVG and rasterizes via Chromium for the canonical ``--pdf`` output;
  through that path, inline ``display:`` rules are silently dropped — the
  slide compiles cleanly but multi-column layouts flatten to single-column
  stacked output (verified by studio's ikebot.3 canary, 2026-05-30; see
  issue #128). The reliable workaround is a frontmatter ``style: |`` block
  defining a CSS class, then ``<div class="...">`` in the slide body —
  class-based selectors apply via the global stylesheet, which the
  foreignObject path does honor. Severity is ``warning`` (the static check
  catches the source pattern but cannot verify the PDF render; the
  ``deck-vision`` VLM critic is authoritative on actual rendered layout).

Public API
----------
``lint_deck(path) -> LintResult``
    Run the lint over a single ``deck.md`` file. Returns errors/warnings/infos
    keyed to slide number and source line.

Per the curator addendum on issue #31, this module is intentionally placed at
``anvil/skills/deck/lib/marp_lint.py``. When issue #10 lands the framework lib,
this file (and its slides twin) will be promoted to ``anvil/lib/marp_lint.py``
and re-imported from both skills via a one-line import-path swap; no
behavioural rewrite required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# Module-level metadata --------------------------------------------------------

#: Upstream commit SHA the ported diagnostic is derived from.
UPSTREAM_SHA: str = "3b8617431867b68f4241c453ae2c7601a4298aa8"

#: List of rules implemented in this module. ``slide-content-overflow`` is
#: ported from marp-vscode (see ``UPSTREAM_SHA``); ``figure-italic-supporting-
#: line-too-long`` is Anvil-original (derived from #100 / #101 / canary
#: regressions — see module docstring "Anvil-specific scope"). The
#: ``inline-display-style-dropped`` rule is also Anvil-original (derived
#: from issue #128 / studio's ikebot.3 canary — see module docstring).
PORTED_RULES: tuple[str, ...] = (
    "slide-content-overflow",
    "figure-italic-supporting-line-too-long",
    "inline-display-style-dropped",
)


# Slide-geometry model ---------------------------------------------------------


@dataclass(frozen=True)
class Geometry:
    """Slide geometry + content-cost constants used by the capacity model.

    Defaults match ``anvil/skills/deck/assets/anvil-deck.css`` and the slides
    theme. ``line_units_per_slide`` is the **vertical content budget**: the
    number of 1.0-unit body lines that fit in the safe area after subtracting
    padding. Every content element below contributes a fractional or integer
    number of line units; the slide overflows when the sum exceeds the budget.

    A "line unit" is calibrated to one body-text line at 26px/1.45 line-height
    plus its tight inter-paragraph spacing — empirically ~40px of vertical
    advance. The budget is the floor of ``(720 - top_pad - bottom_pad) / 40``,
    which lands at 14 line units for the default 56/56 padding. We round down
    by 1 for safety (the budget is 13 in the model below) because horizontal
    word wrap can spill an extra line, and the upstream rule is conservative
    about false-negatives, not false-positives.
    """

    # Pixel geometry — provided for documentation; capacity is in line units.
    slide_width_px: int = 1280
    slide_height_px: int = 720
    top_padding_px: int = 56
    bottom_padding_px: int = 56
    body_line_height_px: int = 40  # 26px font * 1.45 + half of the 16px p-margin

    # Capacity budget (line units). Errors are emitted only when the overage
    # is at least ``error_threshold_units`` above the budget; otherwise it's a
    # warning. This is the source-level analogue of "scrollHeight exceeds
    # clientHeight by more than a trivial amount" — we don't want to fire on
    # a slide that's one wrapped-bullet over budget.
    capacity_units: float = 13.0
    error_threshold_units: float = 1.5
    warning_threshold_units: float = 0.0  # any overage at all gets a warning

    # Per-element costs, in line units.
    h1_units: float = 3.2   # 56px font × 1.15 + 24px margin ≈ 88px (hero on default;
                            # on `_class: ask` the H1 is 60px and even taller; this
                            # is intentionally conservative so the #25 H2+H1+bullets
                            # repro hits the error threshold)
    h2_units: float = 2.0   # 40px font × 1.2  + 28px margin ≈ 76px ≈ 2.0 lines
    h3_units: float = 1.6   # 28px font × 1.3  + 24px margin ≈ 60px ≈ 1.6 lines
    h4_plus_units: float = 1.3
    body_paragraph_units: float = 1.0       # one wrapped line of body text
    extra_body_wrap_units: float = 1.0      # per ~70-char overflow of a paragraph
    body_paragraph_chars_per_line: int = 70
    bullet_units: float = 1.1               # bullet line + tight spacing
    bullet_continuation_units: float = 0.6  # wrapped bullet continuation
    bullet_chars_per_line: int = 64
    nested_bullet_units: float = 1.0
    code_block_overhead_units: float = 1.6  # padding + margin around <pre>
    code_line_units: float = 0.7            # code lines are denser (smaller font)
    table_header_units: float = 1.6
    table_row_units: float = 1.1
    blockquote_units: float = 1.2
    image_units: float = 7.0                # a full-width PNG eats ~half the slide
    image_small_units: float = 3.0          # if an explicit width hint < 50% is given
    horizontal_rule_units: float = 0.5
    hr_inside_slide_units: float = 0.5
    paragraph_break_units: float = 0.4      # the gap between block elements

    # Anti-pattern penalties applied at slide level after the per-element sum.
    # The H1+H2 combination is a documented overflow source on `_class: ask`
    # slides (issue #25): having both a section tag and a hero headline burns
    # vertical space the slide does not have. We surface this as an extra
    # capacity charge rather than rule out the combination outright (the
    # drafter may use it intentionally on a generous slide).
    h1_plus_h2_penalty_units: float = 1.5

    # `_class: ask` slides use heavier padding (80px vs 56px) per
    # anvil-deck.css, so the safe area is ~96px smaller — about 2.4 line
    # units. We subtract this from capacity rather than from the cost so the
    # finding message still reports the slide's content total honestly.
    ask_class_capacity_penalty_units: float = 2.4

    # Budget for an italic supporting line directly under a standalone figure
    # block (the post-#68 "figure + ONE italic line" idiom — see
    # ``assets/slide-archetypes.md`` "Figure layout idioms"). The two
    # thresholds fire as a logical **OR**: a line longer than EITHER bound
    # is flagged.
    #
    # - 18 words: 18 × ~5 chars + spaces ≈ 108 chars. Anchored against the
    #   shipped ``clean_figure_plus_supporting_line.md`` fixture (originally
    #   17 words / 124 chars; tightened to ≤108 chars in the same PR that
    #   introduced this rule). Catches the bower / citation-clear /
    #   bibliotype canary regressions (25-32 words) with comfortable
    #   headroom.
    # - 108 chars: italic glyphs are ~5% wider than upright body weight; the
    #   ``body_paragraph_chars_per_line = 70`` constant above implies a
    #   two-line wrap kicks in around ~134 italic chars. 108 leaves a ~20%
    #   safety margin (matches the ``capacity_units = 13`` vs raw 14-unit
    #   budget margin elsewhere in this Geometry).
    #
    # A consumer with a wider safe area or smaller body font overrides via
    # the existing ``lint_deck(path, geometry=Geometry(...))`` parameter.
    italic_supporting_line_max_words: int = 18
    italic_supporting_line_max_chars: int = 108


_DEFAULT_GEOMETRY = Geometry()


# Result types -----------------------------------------------------------------


@dataclass
class Finding:
    """A single lint hit. Schema matches AC1 on issue #31."""

    slide: int
    line: int
    rule: str
    severity: str  # "error" | "warning" | "info"
    message: str

    def to_dict(self) -> dict:
        return {
            "slide": self.slide,
            "line": self.line,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class LintResult:
    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    infos: list[Finding] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.errors) + len(self.warnings) + len(self.infos)

    def to_summary(self) -> dict:
        """Shape that fits cleanly into the review ``_summary.md`` ``lint`` block."""
        return {
            "ran": True,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "infos": len(self.infos),
            "errors_by_slide": [f.to_dict() for f in self.errors],
            "warnings_by_slide": [f.to_dict() for f in self.warnings],
        }


# Slide parsing ----------------------------------------------------------------


@dataclass
class _Slide:
    index: int          # 1-based slide number
    start_line: int     # 1-based line in the source file
    end_line: int       # 1-based, inclusive
    raw: str            # full slide source including any leading directives
    body: str           # source with leading frontmatter / directive lines stripped


# Matches Marp's slide separator: a `---` on its own line. We use this also as
# the YAML-frontmatter terminator at file head; the first occurrence may be the
# end of frontmatter rather than a slide break.
_SLIDE_BREAK_RE = re.compile(r"^---\s*$", re.MULTILINE)

# Marp per-slide directive comment, e.g.
#   <!-- _class: ask -->
#   <!-- _backgroundColor: black -->
# Also matches anvil's escape-hatch directive.
_DIRECTIVE_COMMENT_RE = re.compile(
    r"^\s*<!--\s*(?P<body>[^>]+?)\s*-->\s*$", re.MULTILINE
)

# Anvil per-slide lint suppression directive.
_LINT_DISABLE_RE = re.compile(
    r"^\s*<!--\s*anvil-lint-disable:\s*(?P<rules>[a-zA-Z0-9_,\-\s]+?)\s*-->\s*$",
    re.MULTILINE,
)


def _split_slides(source: str) -> list[_Slide]:
    """Split a Marp ``deck.md`` source into one record per slide.

    Handles the YAML frontmatter convention: if the file opens with ``---``,
    the next ``---`` is the close of frontmatter, **not** a slide break.
    """
    lines = source.splitlines()
    n = len(lines)

    # Detect frontmatter and find its end.
    start_idx = 0
    if n > 0 and lines[0].strip() == "---":
        # find the matching close
        for j in range(1, n):
            if lines[j].strip() == "---":
                start_idx = j + 1
                break

    # Now slice on subsequent `---` lines (slide breaks).
    slides: list[_Slide] = []
    current_start = start_idx
    slide_num = 0
    i = start_idx
    while i < n:
        if lines[i].strip() == "---":
            # close out the current slide
            slide_num += 1
            raw = "\n".join(lines[current_start:i])
            slides.append(
                _Slide(
                    index=slide_num,
                    start_line=current_start + 1,
                    end_line=i,  # exclusive of the break itself; 1-based
                    raw=raw,
                    body=raw,
                )
            )
            current_start = i + 1
        i += 1

    # tail slide (no trailing `---`)
    if current_start < n:
        slide_num += 1
        raw = "\n".join(lines[current_start:n])
        if raw.strip():
            slides.append(
                _Slide(
                    index=slide_num,
                    start_line=current_start + 1,
                    end_line=n,
                    raw=raw,
                    body=raw,
                )
            )

    # Drop any slides that are pure whitespace / pure directive comments.
    pruned: list[_Slide] = []
    next_num = 1
    for s in slides:
        if _is_effectively_empty(s.raw):
            continue
        pruned.append(
            _Slide(
                index=next_num,
                start_line=s.start_line,
                end_line=s.end_line,
                raw=s.raw,
                body=s.raw,
            )
        )
        next_num += 1
    return pruned


def _is_effectively_empty(slide_src: str) -> bool:
    """A slide is empty if every non-blank line is a directive comment."""
    for line in slide_src.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _DIRECTIVE_COMMENT_RE.match(line):
            continue
        return False
    return True


# Capacity model ---------------------------------------------------------------


@dataclass
class _CostBreakdown:
    total_units: float = 0.0
    parts: list[tuple[str, float]] = field(default_factory=list)
    heading_levels: list[int] = field(default_factory=list)

    def add(self, label: str, units: float) -> None:
        self.total_units += units
        self.parts.append((label, units))


# Detect a `_class: ask` directive on the slide.
_CLASS_ASK_RE = re.compile(
    r"^\s*<!--\s*_class:\s*ask\s*-->\s*$", re.MULTILINE
)

# Anchored variant of the image regex: matches a STANDALONE figure block —
# a single `![alt](path)` reference that is the entire line (modulo
# surrounding whitespace). Used as the trigger for the
# ``figure-italic-supporting-line-too-long`` rule, where only a standalone
# figure block (not an inline image in a paragraph) sets up the "figure +
# italic supporting line" idiom.
_STANDALONE_FIGURE_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$")

# Single ``_..._`` or ``*...*`` italic delimiter spanning the WHOLE stripped
# line. The inner character class ``[^_*]`` deliberately rejects
# bold-italic (``**_..._**`` / ``_**...**_``) and adjacent emphasis runs:
# those are content emphasis patterns, not figure supporting lines.
_FULL_LINE_ITALIC_RE = re.compile(
    r"^\s*[_*]([^_*][^_*\n]*?)[_*]\s*$"
)


# Detect inline ``style="...display:(grid|flex|inline-grid|inline-flex)..."``
# (and the single-quoted variant). Used by the
# ``inline-display-style-dropped`` rule. The pattern accepts optional
# whitespace around the ``:`` and is case-insensitive so it catches
# ``DISPLAY:Grid`` etc. The value is captured for the diagnostic message.
_INLINE_DISPLAY_STYLE_DQ_RE = re.compile(
    r"""style\s*=\s*"[^"]*?display\s*:\s*(?P<value>inline-grid|inline-flex|grid|flex)\b[^"]*"
    """,
    re.IGNORECASE | re.VERBOSE,
)
_INLINE_DISPLAY_STYLE_SQ_RE = re.compile(
    r"""style\s*=\s*'[^']*?display\s*:\s*(?P<value>inline-grid|inline-flex|grid|flex)\b[^']*'
    """,
    re.IGNORECASE | re.VERBOSE,
)

_FENCED_OPEN_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_IMAGE_WITH_SIZE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*?)(?:\s+w[:= ](?P<width>\d+(?:%|px)?))?[^\]]*\]"
)
_HR_RE = re.compile(r"^\s*(\*\s*){3,}\s*$|^\s*(-\s*){3,}\s*$|^\s*(_\s*){3,}\s*$")
_BLOCKQUOTE_RE = re.compile(r"^\s*>")
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")


def _estimate_slide_cost(slide: _Slide, geo: Geometry) -> _CostBreakdown:
    """Estimate the slide's vertical-line-unit cost from its markdown source."""
    breakdown = _CostBreakdown()
    lines = slide.body.splitlines()
    i = 0
    n = len(lines)
    in_fence = False
    fence_open_line = ""
    just_added_paragraph_break = False
    seen_first_block = False

    while i < n:
        raw_line = lines[i]
        stripped = raw_line.strip()

        # Skip directive comments (and the lint-disable comment).
        if _DIRECTIVE_COMMENT_RE.match(raw_line):
            i += 1
            continue

        # Track fenced code blocks (don't try to interpret their contents).
        if not in_fence and _FENCED_OPEN_RE.match(raw_line):
            in_fence = True
            fence_open_line = raw_line.strip()[:3]
            j = i + 1
            code_lines = 0
            while j < n:
                if lines[j].strip().startswith(fence_open_line):
                    break
                code_lines += 1
                j += 1
            breakdown.add(
                f"code-block({code_lines} lines)",
                geo.code_block_overhead_units + code_lines * geo.code_line_units,
            )
            i = j + 1
            in_fence = False
            seen_first_block = True
            just_added_paragraph_break = False
            continue

        # Blank line: paragraph break (small cost between adjacent blocks).
        if not stripped:
            if seen_first_block and not just_added_paragraph_break:
                breakdown.add("paragraph-break", geo.paragraph_break_units)
                just_added_paragraph_break = True
            i += 1
            continue

        # Heading.
        m_heading = _HEADING_RE.match(raw_line)
        if m_heading:
            level = len(m_heading.group(1))
            cost = (
                geo.h1_units
                if level == 1
                else geo.h2_units
                if level == 2
                else geo.h3_units
                if level == 3
                else geo.h4_plus_units
            )
            breakdown.add(f"h{level}", cost)
            breakdown.heading_levels.append(level)
            i += 1
            seen_first_block = True
            just_added_paragraph_break = False
            continue

        # Horizontal rule inside a slide.
        if _HR_RE.match(raw_line):
            breakdown.add("hr", geo.hr_inside_slide_units)
            i += 1
            seen_first_block = True
            just_added_paragraph_break = False
            continue

        # Blockquote (single-line).
        if _BLOCKQUOTE_RE.match(raw_line):
            breakdown.add("blockquote", geo.blockquote_units)
            i += 1
            seen_first_block = True
            just_added_paragraph_break = False
            continue

        # Tables.
        if _TABLE_ROW_RE.match(raw_line):
            # consume table block
            row_count = 0
            j = i
            saw_separator = False
            while j < n and _TABLE_ROW_RE.match(lines[j]):
                if _TABLE_SEP_RE.match(lines[j]):
                    saw_separator = True
                else:
                    row_count += 1
                j += 1
            if saw_separator and row_count >= 1:
                # one header + (row_count - 1) body rows
                breakdown.add(
                    f"table({row_count} rows)",
                    geo.table_header_units + max(0, row_count - 1) * geo.table_row_units,
                )
            else:
                breakdown.add(
                    f"table-like({row_count})",
                    row_count * geo.table_row_units,
                )
            i = j
            seen_first_block = True
            just_added_paragraph_break = False
            continue

        # Bullet.
        m_bullet = _BULLET_RE.match(raw_line)
        if m_bullet:
            indent = len(m_bullet.group(1))
            text = m_bullet.group(3)
            unit = geo.bullet_units if indent < 2 else geo.nested_bullet_units
            # Account for wrap.
            wraps = max(0, (len(text) - 1) // geo.bullet_chars_per_line)
            breakdown.add(
                f"bullet({len(text)}c{'+wrap' if wraps else ''})",
                unit + wraps * geo.bullet_continuation_units,
            )
            i += 1
            seen_first_block = True
            just_added_paragraph_break = False
            continue

        # Image (standalone block — image on its own paragraph).
        if _IMAGE_RE.search(raw_line) and len(raw_line.strip()) < 250:
            # If a `w:` or width hint indicates the image is < 50% width, use small cost.
            m_size = _IMAGE_WITH_SIZE_RE.search(raw_line)
            small = False
            if m_size and m_size.group("width"):
                w = m_size.group("width")
                if w.endswith("%"):
                    try:
                        pct = int(w[:-1])
                        small = pct < 50
                    except ValueError:
                        pass
                elif w.endswith("px"):
                    try:
                        px = int(w[:-2])
                        small = px < (geo.slide_width_px // 2)
                    except ValueError:
                        pass
            breakdown.add(
                "image-small" if small else "image",
                geo.image_small_units if small else geo.image_units,
            )
            i += 1
            seen_first_block = True
            just_added_paragraph_break = False
            continue

        # Body paragraph — accumulate consecutive non-block lines.
        para_lines: list[str] = []
        while i < n:
            line = lines[i]
            stripped_line = line.strip()
            if not stripped_line:
                break
            if (
                _HEADING_RE.match(line)
                or _BULLET_RE.match(line)
                or _HR_RE.match(line)
                or _BLOCKQUOTE_RE.match(line)
                or _TABLE_ROW_RE.match(line)
                or _FENCED_OPEN_RE.match(line)
                or _DIRECTIVE_COMMENT_RE.match(line)
            ):
                break
            # Standalone image line was handled above; mixed-text-with-image
            # paragraphs count as paragraph + image.
            para_lines.append(line)
            i += 1
        if para_lines:
            joined = " ".join(s.strip() for s in para_lines)
            chars = len(joined)
            wraps = max(
                0, (chars - 1) // geo.body_paragraph_chars_per_line
            )
            inline_image = bool(_IMAGE_RE.search(joined))
            cost = geo.body_paragraph_units + wraps * geo.extra_body_wrap_units
            if inline_image:
                cost += geo.image_small_units
                breakdown.add(
                    f"paragraph({chars}c+inline-image)",
                    cost,
                )
            else:
                breakdown.add(f"paragraph({chars}c)", cost)
            seen_first_block = True
            just_added_paragraph_break = False
            continue

        # Fallback: count as one body line.
        breakdown.add("misc", 1.0)
        i += 1
        seen_first_block = True
        just_added_paragraph_break = False

    return breakdown


# figure-italic-supporting-line-too-long check --------------------------------


def _check_italic_supporting_lines(
    slide: _Slide, geo: Geometry, suppressed: bool
) -> list[Finding]:
    """Detect long italic supporting lines directly under a standalone figure.

    Implements the rule documented in the module docstring's "Anvil-specific
    scope" section. State machine, per slide:

    1. Scan ``slide.body`` lines. Skip blank and directive-comment lines.
    2. **Trigger**: a line matching ``_STANDALONE_FIGURE_RE`` (a single
       ``![alt](path)`` reference that IS the line, modulo whitespace).
    3. **Advance** past blank and directive-comment lines.
    4. **Italic accumulator**: if the next non-blank, non-directive line
       matches ``_FULL_LINE_ITALIC_RE`` (single ``_..._`` or ``*...*``
       spanning the whole stripped line, bold-italic explicitly rejected),
       enter italic-block state. Continue accumulating consecutive italic
       lines (soft-wrap support) until a blank, non-italic, directive, or
       end-of-slide closes the block.
    5. **Measure**: word count = ``len(inner.split())``; char count =
       ``len(inner)`` of the inner text with the italic delimiters stripped
       (delimiters don't render and shouldn't be counted).
    6. **Flag** if ``words > geo.italic_supporting_line_max_words`` OR
       ``chars > geo.italic_supporting_line_max_chars``. Emit a ``warning``
       with ``rule="figure-italic-supporting-line-too-long"`` (downgraded
       to ``info`` if the per-slide ``anvil-lint-disable`` directive is set
       for this rule).
    7. After any close (flagged or not), continue scanning for the next
       figure trigger within the same slide. A slide with two figures gets
       two independent checks.
    """
    findings: list[Finding] = []
    body_lines = slide.body.splitlines()
    n = len(body_lines)
    i = 0

    while i < n:
        line = body_lines[i]
        stripped = line.strip()

        # Skip blanks and directive comments while hunting for a trigger.
        if not stripped or _DIRECTIVE_COMMENT_RE.match(line):
            i += 1
            continue

        # Look for the trigger: a standalone figure block.
        if not _STANDALONE_FIGURE_RE.match(line):
            i += 1
            continue

        # Trigger found. Advance past blanks and directive lines.
        j = i + 1
        while j < n:
            stripped_j = body_lines[j].strip()
            if not stripped_j or _DIRECTIVE_COMMENT_RE.match(body_lines[j]):
                j += 1
                continue
            break

        # j is now at the next non-blank, non-directive line (or past end).
        if j >= n:
            break

        # Is it an italic line? If not, no italic-block to measure — go back
        # to scanning for the next trigger from the next line.
        first_italic_match = _FULL_LINE_ITALIC_RE.match(body_lines[j])
        if not first_italic_match:
            i = j + 1
            continue

        # Italic accumulator: consume consecutive italic lines (soft-wrap)
        # until a blank, non-italic, directive, or end-of-slide.
        block_start = j
        inner_parts: list[str] = [first_italic_match.group(1).strip()]
        k = j + 1
        while k < n:
            line_k = body_lines[k]
            stripped_k = line_k.strip()
            if not stripped_k:
                break
            if _DIRECTIVE_COMMENT_RE.match(line_k):
                break
            m_k = _FULL_LINE_ITALIC_RE.match(line_k)
            if not m_k:
                break
            inner_parts.append(m_k.group(1).strip())
            k += 1

        # Measure across the accumulated block. Delimiters are excluded
        # because they don't render.
        inner_text = " ".join(p for p in inner_parts if p)
        words = len(inner_text.split())
        chars = len(inner_text)

        over_words = words > geo.italic_supporting_line_max_words
        over_chars = chars > geo.italic_supporting_line_max_chars
        if over_words or over_chars:
            # Compose the message (per AC1 / the curator's example phrasing).
            message = (
                f"Italic supporting line under figure is {words} words / "
                f"{chars} chars; budget is "
                f"≤{geo.italic_supporting_line_max_words} words / "
                f"≤{geo.italic_supporting_line_max_chars} chars. "
                "Likely wraps to 2+ lines and clips at slide bottom on 16:9 "
                "(italic glyphs run ~5% wider than upright body weight)."
            )
            findings.append(
                Finding(
                    slide=slide.index,
                    # 1-based file-level line, computed via the same
                    # convention as slide-content-overflow: slide.start_line
                    # is the 1-based first-line of the slide; block_start is
                    # the 0-based offset within slide.body of the italic
                    # block's first line.
                    line=slide.start_line + block_start,
                    rule="figure-italic-supporting-line-too-long",
                    severity="info" if suppressed else "warning",
                    message=message,
                )
            )

        # Continue scanning from the line after the italic block — a slide
        # with two figures gets two independent checks.
        i = k
        continue

    return findings


# inline-display-style-dropped check ------------------------------------------


def _check_inline_display_styles(
    slide: _Slide, suppressed: bool
) -> list[Finding]:
    """Detect inline ``style="...display:(grid|flex|...)..."`` attributes.

    Marp renders slide content into a ``<foreignObject>`` element inside an
    SVG and rasterizes via Chromium for ``--pdf`` output. Inline
    ``display: grid`` / ``display: flex`` rules are silently dropped through
    that path — the slide compiles cleanly but the layout flattens to a
    single column in the rendered PDF (verified, issue #128). The reliable
    workaround is a frontmatter ``style: |`` block defining a CSS class,
    referenced from ``<div class="...">`` in the slide body.

    The check is a simple regex scan over the slide body line-by-line; one
    finding is emitted per matching line. Fenced code blocks are excluded
    (a ``style="display:grid"`` inside a markdown code fence is documentation,
    not a render bug).

    Suppressed findings downgrade to ``info`` (same protocol as the other
    Anvil-original rules).
    """
    findings: list[Finding] = []
    body_lines = slide.body.splitlines()
    n = len(body_lines)
    i = 0
    in_fence = False
    fence_open_line = ""

    while i < n:
        line = body_lines[i]
        stripped = line.strip()

        # Track fenced code blocks (don't flag inline styles inside them).
        if not in_fence and _FENCED_OPEN_RE.match(line):
            in_fence = True
            fence_open_line = stripped[:3]
            i += 1
            continue
        if in_fence:
            if stripped.startswith(fence_open_line):
                in_fence = False
            i += 1
            continue

        # Try double-quoted then single-quoted.
        m = _INLINE_DISPLAY_STYLE_DQ_RE.search(line)
        if not m:
            m = _INLINE_DISPLAY_STYLE_SQ_RE.search(line)
        if m:
            value = m.group("value").lower()
            message = (
                f"Inline `style=\"...display:{value}...\"` is silently "
                "dropped by Marp's foreignObject SVG render path — the "
                "slide will compile cleanly but flatten to single-column "
                "stacked output in the PDF (issue #128). Move the rule "
                "into the deck frontmatter `style: |` block as a CSS class "
                "and apply it via `<div class=\"...\">`; class-based "
                "selectors are honored through the foreignObject path. "
                "See `marp-renderer.md` \"Layout patterns\" for the "
                "worked example."
            )
            findings.append(
                Finding(
                    slide=slide.index,
                    line=slide.start_line + i,
                    rule="inline-display-style-dropped",
                    severity="info" if suppressed else "warning",
                    message=message,
                )
            )
        i += 1

    return findings


# Public API -------------------------------------------------------------------


def lint_source(
    source: str,
    *,
    geometry: Geometry | None = None,
    rules: tuple[str, ...] = PORTED_RULES,
) -> LintResult:
    """Run the lint over an in-memory Marp markdown source string.

    This is the unit-testable core; ``lint_deck`` is a thin file wrapper.
    """
    geo = geometry or _DEFAULT_GEOMETRY
    result = LintResult()
    run_overflow = "slide-content-overflow" in rules
    run_italic = "figure-italic-supporting-line-too-long" in rules
    run_inline_display = "inline-display-style-dropped" in rules
    if not (run_overflow or run_italic or run_inline_display):
        return result

    slides = _split_slides(source)
    for slide in slides:
        # Escape hatch — collected once per slide; each rule asks the set.
        disabled_rules = _collect_disabled_rules(slide.raw)

        # --- figure-italic-supporting-line-too-long ----------------------
        # Run this first because it does not depend on the capacity model.
        # Suppressed findings downgrade to ``info`` (same protocol as the
        # overflow rule's escape hatch).
        if run_italic:
            italic_suppressed = (
                "figure-italic-supporting-line-too-long" in disabled_rules
            )
            for finding in _check_italic_supporting_lines(
                slide, geo, italic_suppressed
            ):
                if finding.severity == "info":
                    result.infos.append(finding)
                else:
                    result.warnings.append(finding)

        # --- inline-display-style-dropped --------------------------------
        # Pure regex scan; independent of the capacity model. Suppressed
        # findings downgrade to ``info``.
        if run_inline_display:
            inline_suppressed = (
                "inline-display-style-dropped" in disabled_rules
            )
            for finding in _check_inline_display_styles(slide, inline_suppressed):
                if finding.severity == "info":
                    result.infos.append(finding)
                else:
                    result.warnings.append(finding)

        if not run_overflow:
            continue

        suppressed = "slide-content-overflow" in disabled_rules

        breakdown = _estimate_slide_cost(slide, geo)

        # Anti-pattern penalty: H1 + H2 on the same slide (#25 repro).
        heading_set = set(breakdown.heading_levels)
        if 1 in heading_set and 2 in heading_set:
            breakdown.add("h1+h2-anti-pattern", geo.h1_plus_h2_penalty_units)

        # `_class: ask` capacity reduction (heavier padding per anvil-deck.css).
        slide_capacity = geo.capacity_units
        is_ask_slide = bool(_CLASS_ASK_RE.search(slide.raw))
        if is_ask_slide:
            slide_capacity -= geo.ask_class_capacity_penalty_units

        overage = breakdown.total_units - slide_capacity

        if overage <= geo.warning_threshold_units:
            continue

        # Build a human-readable message.
        top_costs = sorted(breakdown.parts, key=lambda p: -p[1])[:3]
        cost_summary = ", ".join(f"{label}={units:.1f}u" for label, units in top_costs)
        capacity_note = (
            f" (ask-slide capacity {slide_capacity:.1f}u)"
            if is_ask_slide
            else ""
        )
        message = (
            f"Slide exceeds estimated vertical capacity by "
            f"~{overage:.1f} line-units "
            f"(estimated {breakdown.total_units:.1f}u vs. capacity {slide_capacity:.1f}u). "
            f"Top costs: {cost_summary}.{capacity_note}"
        )

        finding = Finding(
            slide=slide.index,
            line=slide.start_line,
            rule="slide-content-overflow",
            severity="info" if suppressed else (
                "error" if overage >= geo.error_threshold_units else "warning"
            ),
            message=message,
        )
        if suppressed:
            result.infos.append(finding)
        elif finding.severity == "error":
            result.errors.append(finding)
        else:
            result.warnings.append(finding)

    return result


def _collect_disabled_rules(slide_src: str) -> set[str]:
    rules: set[str] = set()
    for m in _LINT_DISABLE_RE.finditer(slide_src):
        for raw in m.group("rules").split(","):
            r = raw.strip()
            if r:
                rules.add(r)
    return rules


def lint_deck(path: Path, *, geometry: Geometry | None = None) -> LintResult:
    """Run the lint against a Marp ``deck.md`` file on disk.

    Per AC1 on issue #31. Pass a custom ``geometry`` to override the default
    16:9 / 1280×720 / anvil-deck.css constants.
    """
    if not isinstance(path, Path):
        path = Path(path)
    source = path.read_text(encoding="utf-8")
    return lint_source(source, geometry=geometry)


__all__ = [
    "Finding",
    "Geometry",
    "LintResult",
    "PORTED_RULES",
    "UPSTREAM_SHA",
    "lint_deck",
    "lint_source",
]
