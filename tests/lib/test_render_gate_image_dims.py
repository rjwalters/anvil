"""Unit tests for the ``memo_image_dimensions`` render-gate check (issue #395).

Covers the advisory image-dimension/aspect sanity dimension added to
``anvil/lib/render_gate.py``'s memo gate:

- pure-stdlib PNG IHDR / JPEG SOFn header parsing (no PIL, no subprocess);
- check 1 (pixel ceiling), check 1b (extreme aspect), check 2
  (declared-vs-actual via sibling ``src/*.py`` figsize/dpi or PNG pHYs),
  check 3 (content-bbox vs canvas — ``[image_lint]`` optional extra with
  graceful degradation);
- enumeration (body refs ∪ exhibits glob; URL/absolute refs skipped);
- ``image_max_px`` override coercion (the ``words_per_page`` pattern);
- ``<!-- anvil-lint-disable: memo_image_dimensions -->`` suppression;
- advisory severity model (``passed`` unaffected, no CriticalFlag,
  findings present in ``to_json()["findings"]``).

Fixture trick (per the curation notes): the struct+zlib PNG chunk builder
from ``anvil/skills/deck/tests/test_imagegen.py::_make_tiny_png`` is
adapted to parameterize IHDR width/height — for the header checks only
the IHDR matters, so a "16,622 x 5,652" fixture is a few hundred bytes
(declared dims, 1-pixel IDAT). No large files, no PIL at fixture time.

Test filename is distinct from ``test_render_gate.py`` /
``test_render_gate_memo.py`` per the #58 packaging convention.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from anvil.lib import render_gate as rg
from anvil.lib.render_gate import (
    DIM_MEMO_IMAGE_DIMENSIONS,
    MEMO_IMAGE_MAX_PX,
    GateFinding,
    _check_memo_image_dimensions,
    _coerce_image_max_px,
    _enumerate_memo_images,
    _find_figure_source,
    _parse_declared_figure_params,
    _read_image_dimensions,
    _read_jpeg_dimensions,
    _read_png_dimensions,
    _read_png_phys_dpi,
)


# ---------------------------------------------------------------------------
# Fixture builders: tiny PNG/JPEG byte strings with arbitrary declared dims
# ---------------------------------------------------------------------------


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def make_png(width: int, height: int, *, phys_dpi: float | None = None) -> bytes:
    """A structurally-valid PNG declaring ``width x height`` in its IHDR.

    The IDAT is a single 1-pixel scanline regardless of declared dims —
    the header checks never decode pixel data, so a "16,622 x 5,652"
    fixture is a few hundred bytes. Optional ``phys_dpi`` adds a pHYs
    chunk (unit=meter) for the check-2 density path.
    """
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    out = sig + _chunk(b"IHDR", ihdr)
    if phys_dpi is not None:
        ppm = round(phys_dpi / 0.0254)
        out += _chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))
    idat = zlib.compress(bytes([0, 1, 2, 3]))
    return out + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def make_jpeg(width: int, height: int) -> bytes:
    """A minimal JPEG byte string: SOI + APP0 (JFIF) + SOF0 + EOI."""
    soi = b"\xff\xd8"
    app0 = (
        b"\xff\xe0"
        + struct.pack(">H", 16)
        + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    )
    sof0_payload = (
        struct.pack(">BHHB", 8, height, width, 3)
        + b"\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    )
    sof0 = b"\xff\xc0" + struct.pack(">H", 2 + len(sof0_payload)) + sof0_payload
    return soi + app0 + sof0 + b"\xff\xd9"


@pytest.fixture
def memo_version_dir(tmp_path):
    """Minimal ``<thread>/<thread>.{N}/`` version dir with empty exhibits."""
    thread_root = tmp_path / "silicon"
    vd = thread_root / "silicon.1"
    (vd / "exhibits").mkdir(parents=True)
    (vd / "silicon.md").write_text(
        "# Technical vision\n\nProse.\n", encoding="utf-8"
    )
    return vd


def _write_body(version_dir: Path, body: str) -> Path:
    md = version_dir / "silicon.md"
    md.write_text(body, encoding="utf-8")
    return md


def _warnings(findings: list[GateFinding]) -> list[GateFinding]:
    return [f for f in findings if f.severity == "warning"]


def _infos(findings: list[GateFinding]) -> list[GateFinding]:
    return [f for f in findings if f.severity == "info"]


# ---------------------------------------------------------------------------
# stdlib header parsers
# ---------------------------------------------------------------------------


def test_read_png_dimensions_huge_declared_dims():
    """The canary shape: huge IHDR dims in a few-hundred-byte fixture."""
    data = make_png(16622, 5652)
    assert len(data) < 600
    assert _read_png_dimensions(data) == (16622, 5652)


def test_read_png_dimensions_rejects_non_png():
    assert _read_png_dimensions(b"not a png") is None
    assert _read_png_dimensions(b"") is None
    # Valid signature but truncated before the IHDR payload.
    assert _read_png_dimensions(b"\x89PNG\r\n\x1a\n\x00\x00") is None


def test_read_png_dimensions_rejects_zero_dims():
    assert _read_png_dimensions(make_png(0, 100)) is None


def test_read_png_phys_dpi_roundtrip():
    dpi = _read_png_phys_dpi(make_png(100, 100, phys_dpi=150))
    assert dpi is not None
    assert abs(dpi - 150.0) < 1.0


def test_read_png_phys_dpi_absent():
    assert _read_png_phys_dpi(make_png(100, 100)) is None
    assert _read_png_phys_dpi(b"junk") is None


def test_read_jpeg_dimensions_sof0():
    assert _read_jpeg_dimensions(make_jpeg(7000, 900)) == (7000, 900)


def test_read_jpeg_dimensions_rejects_non_jpeg():
    assert _read_jpeg_dimensions(b"GIF89a") is None
    assert _read_jpeg_dimensions(b"") is None
    # SOI only, no SOF.
    assert _read_jpeg_dimensions(b"\xff\xd8\xff\xd9") is None


def test_read_image_dimensions_dispatches_on_extension(tmp_path):
    png = tmp_path / "fig.png"
    png.write_bytes(make_png(2400, 1400))
    jpg = tmp_path / "photo.jpg"
    jpg.write_bytes(make_jpeg(1920, 1080))
    assert _read_image_dimensions(png) == (2400, 1400)
    assert _read_image_dimensions(jpg) == (1920, 1080)


def test_read_image_dimensions_sniffs_unknown_extension(tmp_path):
    blob = tmp_path / "fig.bin"
    blob.write_bytes(make_png(123, 45))
    assert _read_image_dimensions(blob) == (123, 45)


def test_read_image_dimensions_missing_file(tmp_path):
    assert _read_image_dimensions(tmp_path / "nope.png") is None


# ---------------------------------------------------------------------------
# _coerce_image_max_px: the words_per_page coercion table
# ---------------------------------------------------------------------------


def test_coerce_image_max_px_accepts_positive_numbers():
    assert _coerce_image_max_px(6000) == 6000
    assert _coerce_image_max_px(1) == 1
    assert _coerce_image_max_px(8000.5) == 8000


def test_coerce_image_max_px_rejects_non_positive():
    assert _coerce_image_max_px(0) is None
    assert _coerce_image_max_px(-1) is None
    assert _coerce_image_max_px(0.4) is None


def test_coerce_image_max_px_rejects_non_numeric_and_bool():
    assert _coerce_image_max_px("6000") is None
    assert _coerce_image_max_px(None) is None
    assert _coerce_image_max_px([6000]) is None
    assert _coerce_image_max_px(True) is None
    assert _coerce_image_max_px(False) is None


# ---------------------------------------------------------------------------
# Check 1: pixel ceiling
# ---------------------------------------------------------------------------


def test_check1_canary_dims_raise_warning(memo_version_dir):
    """A 16,622 x 5,652 IHDR raises a memo_image_dimensions warning."""
    _write_body(memo_version_dir, "![fig](exhibits/silicon-ladder.png)\n")
    (memo_version_dir / "exhibits" / "silicon-ladder.png").write_bytes(
        make_png(16622, 5652)
    )
    findings, reasons = _check_memo_image_dimensions(memo_version_dir)
    warnings = _warnings(findings)
    assert len(warnings) == 1
    assert warnings[0].gate == DIM_MEMO_IMAGE_DIMENSIONS
    assert "16622x5652" in warnings[0].message
    assert "6000" in warnings[0].message  # effective ceiling in message
    assert any(DIM_MEMO_IMAGE_DIMENSIONS in r and "1 image-dimension" in r for r in reasons)


def test_check1_conformant_dims_pass_clean(memo_version_dir):
    """1800x1125 (corrected canary) and 2400x1400 (style-canonical) pass."""
    _write_body(
        memo_version_dir,
        "![a](exhibits/corrected.png)\n![b](exhibits/canonical.png)\n",
    )
    (memo_version_dir / "exhibits" / "corrected.png").write_bytes(
        make_png(1800, 1125)
    )
    (memo_version_dir / "exhibits" / "canonical.png").write_bytes(
        make_png(2400, 1400)
    )
    findings, _reasons = _check_memo_image_dimensions(memo_version_dir)
    assert _warnings(findings) == []


def test_check1_override_honored(memo_version_dir):
    """A custom image_max_px ceiling flags images the default would pass."""
    _write_body(memo_version_dir, "![a](exhibits/fig.png)\n")
    (memo_version_dir / "exhibits" / "fig.png").write_bytes(make_png(2400, 1400))
    findings, _ = _check_memo_image_dimensions(
        memo_version_dir, image_max_px=2000
    )
    warnings = _warnings(findings)
    assert len(warnings) == 1
    assert "2000" in warnings[0].message


def test_check1_malformed_override_falls_back_to_default(memo_version_dir):
    """Non-numeric / non-positive overrides silently use 6000."""
    _write_body(memo_version_dir, "![a](exhibits/big.png)\n")
    (memo_version_dir / "exhibits" / "big.png").write_bytes(
        make_png(16622, 5652)
    )
    for bad in ("9000", -1, 0, True):
        findings, reasons = _check_memo_image_dimensions(
            memo_version_dir, image_max_px=bad
        )
        warnings = _warnings(findings)
        assert len(warnings) == 1, f"override={bad!r}"
        assert str(MEMO_IMAGE_MAX_PX) in warnings[0].message
        assert any(f"ceiling={MEMO_IMAGE_MAX_PX}" in r for r in reasons)


# ---------------------------------------------------------------------------
# Check 1b: extreme aspect ratio
# ---------------------------------------------------------------------------


def test_check1b_degenerate_strip_raises(memo_version_dir):
    """7000x900 (~7.8:1) trips the aspect check — and also the ceiling."""
    _write_body(memo_version_dir, "![strip](exhibits/strip.png)\n")
    (memo_version_dir / "exhibits" / "strip.png").write_bytes(
        make_png(7000, 900)
    )
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    aspect_hits = [f for f in _warnings(findings) if "aspect ratio" in f.message]
    assert len(aspect_hits) == 1
    assert "7.8:1" in aspect_hits[0].message


def test_check1b_aspect_under_ceiling_only(memo_version_dir):
    """5900x900 (~6.6:1) trips aspect but NOT the pixel ceiling."""
    _write_body(memo_version_dir, "![strip](exhibits/strip.png)\n")
    (memo_version_dir / "exhibits" / "strip.png").write_bytes(
        make_png(5900, 900)
    )
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    warnings = _warnings(findings)
    assert len(warnings) == 1
    assert "aspect ratio" in warnings[0].message


def test_check1b_16_9_passes(memo_version_dir):
    _write_body(memo_version_dir, "![wide](exhibits/wide.jpg)\n")
    (memo_version_dir / "exhibits" / "wide.jpg").write_bytes(
        make_jpeg(1920, 1080)
    )
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    assert _warnings(findings) == []


def test_check1b_portrait_orientation_also_checked(memo_version_dir):
    """Aspect is orientation-agnostic: 900x7000 trips too."""
    _write_body(memo_version_dir, "![tall](exhibits/tall.png)\n")
    (memo_version_dir / "exhibits" / "tall.png").write_bytes(
        make_png(900, 7000)
    )
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    assert any("aspect ratio" in f.message for f in _warnings(findings))


# ---------------------------------------------------------------------------
# Check 2: declared-vs-actual
# ---------------------------------------------------------------------------


_FIG_SRC = (
    "import matplotlib.pyplot as plt\n"
    "fig, ax = plt.subplots(figsize=(12, 7.5))\n"
    "ax.plot([1, 2, 3])\n"
    'fig.savefig("fig.png", dpi=150, bbox_inches="tight")\n'
)


def test_check2_divergent_actual_raises(memo_version_dir):
    """src declares 12x7.5in @ 150dpi (1800x1125); actual is 16622x5652."""
    _write_body(memo_version_dir, "![fig](exhibits/fig.png)\n")
    src_dir = memo_version_dir / "exhibits" / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "fig.py").write_text(_FIG_SRC, encoding="utf-8")
    (memo_version_dir / "exhibits" / "fig.png").write_bytes(
        make_png(16622, 5652)
    )
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    declared_hits = [
        f for f in _warnings(findings) if "declares figsize" in f.message
    ]
    assert len(declared_hits) == 1
    assert "1800x1125" in declared_hits[0].message


def test_check2_matching_actual_passes(memo_version_dir):
    """Same source next to a 1800x1125 image: within 1.5x, no hit."""
    _write_body(memo_version_dir, "![fig](exhibits/fig.png)\n")
    src_dir = memo_version_dir / "exhibits" / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "fig.py").write_text(_FIG_SRC, encoding="utf-8")
    (memo_version_dir / "exhibits" / "fig.png").write_bytes(
        make_png(1800, 1125)
    )
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    assert _warnings(findings) == []


def test_check2_phys_density_path(memo_version_dir):
    """dpi from the PNG pHYs chunk when the source declares only figsize."""
    _write_body(memo_version_dir, "![fig](exhibits/fig.png)\n")
    src_dir = memo_version_dir / "exhibits" / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "fig.py").write_text(
        "fig, ax = plt.subplots(figsize=(12, 7))\n", encoding="utf-8"
    )
    # pHYs declares 200 dpi -> expected 2400x1400; actual diverges > 1.5x.
    (memo_version_dir / "exhibits" / "fig.png").write_bytes(
        make_png(9000, 5000, phys_dpi=200)
    )
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    declared_hits = [
        f for f in _warnings(findings) if "declares figsize" in f.message
    ]
    assert len(declared_hits) == 1


@pytest.mark.parametrize("bbox_deps_available", [True, False])
def test_check2_silent_skip_without_declarative_source(
    memo_version_dir, monkeypatch, bbox_deps_available
):
    """No src/*.py, no pHYs: check 2 never fires (hand-made images).

    Pinned to both `[image_lint]` deps states (#412): when the deps are
    absent, the once-per-run check-3 breadcrumb quotes
    ``IMAGE_LINT_REMEDIATION`` whose text contains "declared"-vs-actual
    wording — that unrelated breadcrumb must not trip the check-2
    silent-skip assertion, so the `declar` scan excludes it.
    """
    from anvil.lib import render as _render

    monkeypatch.setattr(
        _render,
        "check_image_lint_deps_available",
        lambda: bbox_deps_available,
    )
    _write_body(memo_version_dir, "![photo](exhibits/photo.jpg)\n")
    (memo_version_dir / "exhibits" / "photo.jpg").write_bytes(
        make_jpeg(3000, 2000)
    )
    findings, reasons = _check_memo_image_dimensions(memo_version_dir)
    assert _warnings(findings) == []
    # Silent skip: no reason line about the missing declaration either.
    # The check-3 deps breadcrumb ("content-bbox check skipped. ...") is
    # not a check-2 reason — filter it out before the scan.
    check2_reasons = [
        r for r in reasons if "content-bbox check skipped" not in r
    ]
    assert not any("declar" in r.lower() for r in check2_reasons)


def test_find_figure_source_candidate_order(tmp_path):
    img = tmp_path / "exhibits" / "fig.png"
    img.parent.mkdir(parents=True)
    img.write_bytes(make_png(10, 10))
    assert _find_figure_source(img) is None
    flat = tmp_path / "exhibits" / "fig.py"
    flat.write_text("x = 1\n", encoding="utf-8")
    assert _find_figure_source(img) == flat
    src = tmp_path / "exhibits" / "src" / "fig.py"
    src.parent.mkdir()
    src.write_text("x = 1\n", encoding="utf-8")
    assert _find_figure_source(img) == src  # src/ wins over flat


def test_parse_declared_figure_params():
    figsize, dpi = _parse_declared_figure_params(_FIG_SRC)
    assert figsize == (12.0, 7.5)
    assert dpi == 150.0
    assert _parse_declared_figure_params("no declarations") == (None, None)
    # List-form figsize and standalone dpi both parse.
    figsize, dpi = _parse_declared_figure_params(
        "plt.figure(figsize=[10, 4])\nplt.savefig('x.png', dpi=72)"
    )
    assert figsize == (10.0, 4.0)
    assert dpi == 72.0


# ---------------------------------------------------------------------------
# Check 3: content-bbox vs canvas (optional [image_lint] extra)
# ---------------------------------------------------------------------------


def test_check3_sparse_content_raises(memo_version_dir):
    """Content in a 100x80 corner of an 800x600 transparent canvas (~1.7%)."""
    PIL = pytest.importorskip("PIL")  # noqa: F841
    pytest.importorskip("numpy")
    from PIL import Image

    im = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    for x in range(50, 150):
        for y in range(40, 120):
            im.putpixel((x, y), (20, 40, 200, 255))
    _write_body(memo_version_dir, "![fig](exhibits/sparse.png)\n")
    im.save(memo_version_dir / "exhibits" / "sparse.png")

    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    bbox_hits = [f for f in _warnings(findings) if "content bbox" in f.message]
    assert len(bbox_hits) == 1
    assert "tight-bbox" in bbox_hits[0].message


def test_check3_full_canvas_passes(memo_version_dir):
    PIL = pytest.importorskip("PIL")  # noqa: F841
    pytest.importorskip("numpy")
    from PIL import Image

    im = Image.new("RGBA", (800, 600), (255, 255, 255, 255))
    for x in range(40, 760):
        for y in range(30, 570):
            im.putpixel((x, y), (20, 40, 200, 255))
    _write_body(memo_version_dir, "![fig](exhibits/dense.png)\n")
    im.save(memo_version_dir / "exhibits" / "dense.png")

    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    assert _warnings(findings) == []


def test_check3_graceful_degrade_when_deps_missing(memo_version_dir, monkeypatch):
    """PIL/numpy absent: breadcrumb in reasons; checks 1-2 still run."""
    from anvil.lib import render as _render

    monkeypatch.setattr(
        _render, "check_image_lint_deps_available", lambda: False
    )
    _write_body(memo_version_dir, "![big](exhibits/big.png)\n")
    (memo_version_dir / "exhibits" / "big.png").write_bytes(
        make_png(16622, 5652)
    )
    findings, reasons = _check_memo_image_dimensions(memo_version_dir)
    # Check 1 still fired.
    assert len(_warnings(findings)) == 1
    # Breadcrumb recorded with the install story.
    assert any("content-bbox check skipped" in r for r in reasons)
    assert any("image_lint" in r for r in reasons)


def test_check3_skipped_for_over_ceiling_images(memo_version_dir, monkeypatch):
    """Over-ceiling images are never decoded (decompression-bomb guard)."""
    pytest.importorskip("PIL")
    pytest.importorskip("numpy")
    calls: list[Path] = []

    def _spy(path):
        calls.append(path)
        return None

    monkeypatch.setattr(rg, "_image_content_ratio", _spy)
    _write_body(memo_version_dir, "![big](exhibits/big.png)\n")
    (memo_version_dir / "exhibits" / "big.png").write_bytes(
        make_png(16622, 5652)
    )
    _check_memo_image_dimensions(memo_version_dir)
    assert calls == []


def test_image_content_ratio_undecodable_returns_none(tmp_path):
    """A header-only fixture (bogus IDAT) must not raise inside check 3."""
    pytest.importorskip("PIL")
    pytest.importorskip("numpy")
    p = tmp_path / "fake.png"
    p.write_bytes(make_png(2000, 1500))
    assert rg._image_content_ratio(p) is None


# ---------------------------------------------------------------------------
# Enumeration: body refs ∪ exhibits glob; skips
# ---------------------------------------------------------------------------


def test_enumeration_unions_body_refs_and_exhibits_glob(memo_version_dir):
    """Present-but-unreferenced exhibits are checked too (the 'and/or' ask)."""
    _write_body(memo_version_dir, "![ref](exhibits/referenced.png)\n")
    (memo_version_dir / "exhibits" / "referenced.png").write_bytes(
        make_png(100, 100)
    )
    (memo_version_dir / "exhibits" / "orphan.png").write_bytes(
        make_png(16622, 5652)
    )
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    warnings = _warnings(findings)
    assert len(warnings) == 1
    assert "orphan.png" in warnings[0].message


def test_enumeration_skips_urls_and_absolute_paths(memo_version_dir):
    _write_body(
        memo_version_dir,
        "![u](https://example.com/huge.png)\n"
        "![a](/abs/path/huge.png)\n",
    )
    images, breadcrumbs = _enumerate_memo_images(memo_version_dir)
    assert images == {}
    assert breadcrumbs == []


def test_enumeration_svg_breadcrumb(memo_version_dir):
    _write_body(memo_version_dir, "![v](exhibits/diagram.svg)\n")
    (memo_version_dir / "exhibits" / "diagram.svg").write_text(
        "<svg/>", encoding="utf-8"
    )
    _images, breadcrumbs = _enumerate_memo_images(memo_version_dir)
    assert any("SVG" in b for b in breadcrumbs)


def test_enumeration_dedupes_body_ref_and_glob(memo_version_dir):
    """An image both referenced and globbed is checked once (body line wins)."""
    _write_body(memo_version_dir, "![big](exhibits/big.png)\n")
    (memo_version_dir / "exhibits" / "big.png").write_bytes(
        make_png(16622, 5652)
    )
    images, _ = _enumerate_memo_images(memo_version_dir)
    assert len(images) == 1
    assert list(images.values()) == [1]  # body line retained
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    assert len(_warnings(findings)) == 1


def test_no_images_is_silent(memo_version_dir):
    findings, reasons = _check_memo_image_dimensions(memo_version_dir)
    assert findings == []
    assert reasons == []


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def test_suppression_same_line(memo_version_dir):
    _write_body(
        memo_version_dir,
        "![big](exhibits/big.png) "
        "<!-- anvil-lint-disable: memo_image_dimensions -->\n",
    )
    (memo_version_dir / "exhibits" / "big.png").write_bytes(
        make_png(16622, 5652)
    )
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    assert _warnings(findings) == []
    infos = _infos(findings)
    assert len(infos) == 1
    assert "(suppressed)" in infos[0].message


def test_suppression_line_above(memo_version_dir):
    _write_body(
        memo_version_dir,
        "<!-- anvil-lint-disable: memo_image_dimensions -->\n"
        "![big](exhibits/big.png)\n",
    )
    (memo_version_dir / "exhibits" / "big.png").write_bytes(
        make_png(16622, 5652)
    )
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    assert _warnings(findings) == []
    assert len(_infos(findings)) == 1


def test_suppression_does_not_leak_to_other_rules(memo_version_dir):
    """A memo_placeholder_scan disable does NOT suppress image dims."""
    _write_body(
        memo_version_dir,
        "<!-- anvil-lint-disable: memo_placeholder_scan -->\n"
        "![big](exhibits/big.png)\n",
    )
    (memo_version_dir / "exhibits" / "big.png").write_bytes(
        make_png(16622, 5652)
    )
    findings, _ = _check_memo_image_dimensions(memo_version_dir)
    assert len(_warnings(findings)) == 1


# ---------------------------------------------------------------------------
# Gate wiring: advisory severity model
# ---------------------------------------------------------------------------


def _run_gate(memo_version_dir, monkeypatch, **kwargs):
    """Drive _gate_memo with the renderer stubbed unavailable.

    Renderer-unavailable is the cheapest deterministic path: compile
    graceful-degrades, and the image-dimension check (filesystem-only)
    still runs — proving check 5 is independent of the render outcome.
    """
    from anvil.lib import render as _render

    monkeypatch.setattr(_render, "check_pandoc_available", lambda: False)
    return rg.gate(kind="memo", version_dir=memo_version_dir, **kwargs)


def test_gate_findings_advisory_passed_unaffected(memo_version_dir, monkeypatch):
    """Warnings recorded; passed stays True; no CriticalFlag emitted."""
    _write_body(memo_version_dir, "![big](exhibits/big.png)\n")
    (memo_version_dir / "exhibits" / "big.png").write_bytes(
        make_png(16622, 5652)
    )
    result = _run_gate(memo_version_dir, monkeypatch)
    dim_findings = [
        f for f in result.findings if f.gate == DIM_MEMO_IMAGE_DIMENSIONS
    ]
    assert len(dim_findings) >= 1
    assert all(f.severity == "warning" for f in dim_findings)
    assert result.passed is True
    assert DIM_MEMO_IMAGE_DIMENSIONS not in result.failed_gates
    assert result.to_critical_flags() == []
    # Findings flow to _progress.json.render_gate.findings via to_json().
    payload = result.to_json()
    assert any(
        f["gate"] == DIM_MEMO_IMAGE_DIMENSIONS for f in payload["findings"]
    )
    assert payload["pass"] is True


def test_gate_threads_image_max_px(memo_version_dir, monkeypatch):
    """The public gate() dispatcher forwards image_max_px to check 5."""
    _write_body(memo_version_dir, "![fig](exhibits/fig.png)\n")
    (memo_version_dir / "exhibits" / "fig.png").write_bytes(
        make_png(2400, 1400)
    )
    result = _run_gate(memo_version_dir, monkeypatch, image_max_px=2000)
    dim_findings = [
        f for f in result.findings if f.gate == DIM_MEMO_IMAGE_DIMENSIONS
    ]
    assert len(dim_findings) == 1
    assert "2000" in dim_findings[0].message
    assert result.passed is True


def test_gate_clean_images_no_findings(memo_version_dir, monkeypatch):
    _write_body(memo_version_dir, "![fig](exhibits/fig.png)\n")
    (memo_version_dir / "exhibits" / "fig.png").write_bytes(
        make_png(1800, 1125)
    )
    result = _run_gate(memo_version_dir, monkeypatch)
    assert [
        f for f in result.findings if f.gate == DIM_MEMO_IMAGE_DIMENSIONS
    ] == []


def test_ordered_dims_future_proofing():
    """DIM_MEMO_IMAGE_DIMENSIONS emits a flag iff force-failed (promotion)."""
    result = rg.GateResult(
        pdf_path="x.pdf",
        log_path=None,
        pages=None,
        page_cap=None,
        overfull_boxes=[],
        overfull_threshold_pt=0.0,
        compile_status=rg.COMPILE_SKIPPED,
        compile_exit_code=None,
        placeholders=[],
        passed=False,
        reasons=[f"{DIM_MEMO_IMAGE_DIMENSIONS}: forced"],
        failed_gates={DIM_MEMO_IMAGE_DIMENSIONS},
    )
    flags = result.to_critical_flags()
    assert len(flags) == 1
    assert flags[0].type == f"render_gate_{DIM_MEMO_IMAGE_DIMENSIONS}"
