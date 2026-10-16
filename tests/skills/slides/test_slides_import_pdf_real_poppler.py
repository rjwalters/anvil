"""Real-poppler test for ``anvil.skills.slides.lib.import_pdf`` (issue #1381).

``anvil/skills/slides/tests/test_import_pdf.py`` stubs poppler at the ``_run``
seam. This module runs the importer against the real ``pdfinfo`` /
``pdftoppm`` / ``pdftotext`` binaries on a PDF generated at test time (no
committed binaries). It is skipped unless ``check_poppler_available()``; a
skip is NOT evidence that the importer behaves correctly with real poppler.

Live verification checklist (human or poppler-equipped CI; not automated here):

1. Run ``slides-import <thread> --pdf <path>`` on a real two-column PDF and
   confirm the text comments are in reading order (column A before column B).
2. Confirm ``figures/slide-NN.png`` naming, including a deck of >= 100 pages
   (three-digit padding).
3. Render the deck with Marp and confirm non-16:9 pages show uncropped under
   ``![bg fit]``.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anvil.skills.slides.lib import import_pdf as ip


def _build_pdf(page_texts: list[str]) -> bytes:
    """Return a minimal valid PDF with one Helvetica text line per page.

    An empty string yields a page with no text (image-only/blank).
    """
    objs: list[bytes] = []
    n = len(page_texts)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    font_obj = 3 + 2 * n
    for i, text in enumerate(page_texts):
        content_obj = 4 + 2 * i
        objs.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 320 180] "
                f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode()
        )
        stream = (
            f"BT /F1 18 Tf 20 90 Td ({text}) Tj ET".encode() if text else b""
        )
        objs.append(
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
        )
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objs) + 1, xref)
    )
    return bytes(out)


@unittest.skipUnless(
    ip.check_poppler_available(),
    "poppler (pdfinfo/pdftoppm/pdftotext) not on PATH; real-poppler check "
    "not run (see module docstring for the live checklist)",
)
class RealPopplerImportTests(unittest.TestCase):
    def _import(self, page_texts: list[str]) -> ip.ImportResult:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        thread = tmp / "deck"
        thread.mkdir()
        pdf = tmp / "in.pdf"
        pdf.write_bytes(_build_pdf(page_texts))
        return ip.import_pdf(thread, pdf)

    def test_png_names_match_slide_name_and_deck_refs(self):
        texts = ["First", "Second", "Third"]
        res = self._import(texts)
        self.assertEqual(res.pages, 3)
        figures = res.version_dir / "figures"
        names = sorted(p.name for p in figures.iterdir())
        expected = [f"{ip._slide_name(i, 3)}.png" for i in (1, 2, 3)]
        self.assertEqual(names, expected)
        deck = (res.version_dir / "deck.md").read_text(encoding="utf-8")
        for name in expected:
            self.assertIn(f"![bg fit](figures/{name})", deck)

    def test_blank_page_warns_no_extractable_text(self):
        res = self._import(["Has text", "", "More text"])
        self.assertEqual(res.warnings, ["page 2 has no extractable text"])
        deck = (res.version_dir / "deck.md").read_text(encoding="utf-8")
        self.assertIn("(no extractable text)", deck)
        self.assertIn("Has text", deck)


if __name__ == "__main__":
    unittest.main()
