"""Synthetic PNG fixture generation for the auto-shrink-detector tests.

The detector reads rendered-deck PNGs; we don't need a real Marp render
to test it. We just need PNGs that look (to the corner-sample +
threshold + argmax detector) like a Marp page where the content extends
to a certain bottom-margin fraction.

Each fixture PNG is a white-background 1280x720 image with a single
filled black rectangle whose vertical extent is the "content" area. The
detector should report `bottom_margin_norm ≈ (1 - bottom_y/720)`.

Fixtures (F1-F5; F6 is a classification-only test against
``fixtures/auto_shrink/deck.md`` and needs no PNG generation):

* F1 — Content fills 90% of slide height; not flagged.
* F2 — Content fills 40% of slide height (60% bottom margin); flagged
  against a peer-set of 85%-fill peers (15% bottom margin).
* F3 — A single ``title``-class slide; never flagged because peer count
  is below the threshold.
* F4 — All three peers fill 50% (50% bottom margin). All are above the
  absolute floor but the ratio is 1.0; NONE flagged.
* F5 — Two ``content`` peers at 99% fill (1% bottom margin) and one at
  10% fill (90% bottom margin). The ratio is enormous but the absolute
  floor IS exceeded — this fixture exists primarily to verify the
  reverse: a slide where the ratio is large but absolute is small
  must NOT flag. We construct that by adding the peer triplet
  ``(7%, 9%, 11%)`` bottom margins so the median is 9%, well below
  the 18% floor, and a candidate at ratio 1.5x (13.5% bottom margin)
  still doesn't exceed the floor.

The conftest is loaded by pytest automatically when a test file in
this directory (or above) requests a fixture from it.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# Slide geometry mirrors the deck Marp config: 16:9, 1280x720.
SLIDE_W = 1280
SLIDE_H = 720


def _make_png(out_path: Path, content_bottom_norm: float) -> None:
    """Render a single white-bg PNG with a filled rectangle.

    ``content_bottom_norm`` is the *fill* fraction — i.e., the content
    rectangle extends from y=0 down to y=int(content_bottom_norm * H).
    The resulting ``bottom_margin_norm`` measured by the detector will
    be approximately ``1 - content_bottom_norm``.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (SLIDE_W, SLIDE_H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw a black rectangle spanning the full slide width from the top
    # down to ``content_bottom_y``. Some left/right padding so the
    # column-bbox check doesn't trip over edge pixels.
    content_bottom_y = max(1, int(SLIDE_H * content_bottom_norm))
    draw.rectangle(
        [(40, 40), (SLIDE_W - 40, content_bottom_y)],
        fill=(0, 0, 0),
    )
    img.save(out_path, "PNG")


def _write_deck_md(out_path: Path, class_directives: list[str]) -> None:
    """Write a minimal deck.md whose slide classes match the per-page list."""
    parts = ["---", "marp: true", "theme: anvil-deck", "---", ""]
    for i, cls in enumerate(class_directives, start=1):
        if i > 1:
            parts.append("---")
            parts.append("")
        if cls != "content":
            parts.append(f"<!-- _class: {cls} -->")
            parts.append("")
        parts.append(f"# Slide {i}")
        parts.append("")
    out_path.write_text("\n".join(parts), encoding="utf-8")


@pytest.fixture(scope="session")
def auto_shrink_fixture_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the F1-F5 fixture directories under a session-scoped tmp_path.

    Each F-case gets its own directory:

    ``F1/``  one slide PNG (90% fill) + deck.md with one ``content`` slide.
            Used to assert NO finding for a not-shrunk slide; we add two
            extra 88%/92% peers so the class has the required 3 peers.

    ``F2/``  three slides — two peers at 85% fill (15% bottom margin) and
            one at 40% fill (60% bottom margin); detector should flag
            slide 3.

    ``F3/``  one ``title``-class slide. Detector must record a skipped
            class with reason and emit NO finding.

    ``F4/``  three ``content`` peers, all at 50% fill (50% bottom
            margin). Median 50%, ratio 1.0; absolute exceeds floor but
            ratio doesn't — NONE flagged.

    ``F5/``  three ``content`` peers at 7%/9%/11% bottom-margin
            (i.e., ~93%/91%/89% fills) + one candidate at 13.5%
            bottom margin (86.5% fill). Median is 9%; candidate is
            1.5x median (matches the boundary) but absolute (13.5%)
            is below the 18% floor — NOT flagged.
    """
    root = tmp_path_factory.mktemp("auto_shrink_fixtures")

    def _setup(case_dir: Path, fills: list[float], classes: list[str]) -> None:
        case_dir.mkdir()
        for i, fill in enumerate(fills, start=1):
            _make_png(case_dir / f"page-{i}.png", content_bottom_norm=fill)
        _write_deck_md(case_dir / "deck.md", classes)
        # An empty stub PDF so the detector's existence check passes; the
        # PNGs are pre-rendered in this dir so _ensure_pngs never invokes
        # the real pdftoppm chain.
        (case_dir / "deck.pdf").write_bytes(b"%PDF-stub\n")

    # --- F1: all slides healthy (NOT flagged) ---
    _setup(root / "F1", [0.90, 0.88, 0.92], ["content"] * 3)

    # --- F2: outlier auto-shrunk slide on slide 3 (FLAGGED) ---
    # peers at 85% fill (bm ~15%); slide 3 at 40% fill (bm ~60%).
    _setup(root / "F2", [0.85, 0.85, 0.40], ["content"] * 3)

    # --- F3: singleton title slide (NEVER flagged; recorded as skipped) ---
    # Deliberately use a deeply-shrunk fill (bm ~70%) to prove the
    # singleton-skip rule wins over the absolute-floor rule — a singleton
    # class must never be flagged regardless of its individual margins.
    _setup(root / "F3", [0.30], ["title"])

    # --- F4: all peers equally light (NONE flagged; ratio=1.0) ---
    _setup(root / "F4", [0.50, 0.50, 0.50], ["content"] * 3)

    # --- F5: candidate's ratio AT the boundary but absolute < floor ---
    # Peers at bm 7%, 9%, 11% (median 9%); candidate at bm 13.5%
    # (= 1.5x median, AT the ratio boundary, but 13.5% < 18% absolute
    # floor). Detector must NOT flag — both conditions are required.
    _setup(
        root / "F5",
        [0.93, 0.91, 0.89, 0.865],
        ["content"] * 4,
    )

    return root
