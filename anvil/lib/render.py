"""Rendering helpers shared by Anvil vision critics.

This module is the "render-the-artifact-to-pixels" primitive consumed by
``anvil/lib/vision.py`` and per-skill vision critics. It wraps four
external tools as subprocess shell-outs:

- ``marp`` (the Marp CLI) for Markdown deck/slides → PDF.
- ``pdftoppm`` (poppler-utils) for PDF → per-page PNGs. This is the
  primary path; ``pdf2image`` (Python wrapper around the same library) is
  a documented fallback for environments where ``pdftoppm`` is not on
  PATH but the Python wheel is installed.
- ``pandoc`` for prose Markdown (pub/report) → PDF.
- Nothing — for ``render_matplotlib_figures`` which just enumerates an
  already-rendered ``figures/`` directory.

Design notes
------------

1. **Subprocess-only.** No native Python bindings (no PyMuPDF, no
   poppler-python). Skills get a consistent installation story: install
   the system binaries, not a parallel set of Python wheels.
2. **No re-execution of figure generators.** The matplotlib walker
   enumerates PNGs that the skill's ``figures`` command has already
   produced; vision is a critic, not a producer.
3. **Marp config pin.** ``render_marp_to_pdf`` always invokes
   ``marp --config-file anvil/lib/marp/config.yml`` (per #32) so the
   rendered PDF matches what the user actually sees in production.
4. **Domain exceptions.** Each renderer raises ``RenderError`` with the
   captured stderr on non-zero exit so callers can surface the failure
   uniformly. ``RenderError`` is also raised when a required binary is
   missing — the caller should not have to grep ``FileNotFoundError``
   tracebacks.

pdftoppm vs pdf2image
---------------------

The default path uses ``pdftoppm`` directly. It's the upstream tool
shipped by poppler-utils and is already documented as a ``deck-design``
dependency. Output filenames follow pdftoppm's convention: passing
``page`` as the output basename produces ``page-1.png``, ``page-2.png``,
etc. (one-indexed, no zero-padding). ``render_pdf_to_pngs`` re-walks
the directory and returns the sorted list.

The ``pdf2image`` Python wrapper (https://pypi.org/project/pdf2image/)
calls ``pdftoppm`` under the hood. It is documented here as a fallback
for environments where the Python wheel is preferred over a system
package install, but is not used by default — ``pdftoppm`` directly
keeps the dependency set minimal.

If neither is available, ``render_pdf_to_pngs`` raises ``RenderError``
with a message naming both options.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional


# Default Marp config path relative to a repo root. Resolved by the
# caller when invoked from a different cwd.
DEFAULT_MARP_CONFIG = Path("anvil/lib/marp/config.yml")


class RenderError(RuntimeError):
    """A rendering subprocess failed or a required binary is missing."""


# ---------------------------------------------------------------------------
# Marp Markdown → PDF
# ---------------------------------------------------------------------------


def render_marp_to_pdf(
    deck_md: Path,
    out_pdf: Path,
    config: Optional[Path] = None,
) -> Path:
    """Render a Marp Markdown deck to PDF.

    Invokes the ``marp`` CLI with ``--pdf --html
    --config-file <config> --allow-local-files`` so raw HTML, local image
    references, and the pinned Marp options (per #32) all survive into the
    rendered PDF.

    Note: ``--html`` does NOT cause inline ```mermaid fences to render as
    diagrams in the PDF (verified false, issue #65) — those must be
    pre-rendered to PNG via ``mmdc`` (see :func:`check_mmdc_available`).

    Parameters
    ----------
    deck_md:
        Path to the deck source (``deck.md`` or ``slides.md``).
    out_pdf:
        Output PDF path. Parent directory must exist.
    config:
        Optional override for the Marp config file. Defaults to
        ``anvil/lib/marp/config.yml`` per #32. Tests pass an explicit
        path; production callers should pass ``None`` to get the framework
        pin.

    Returns
    -------
    The output PDF path (the same as ``out_pdf``), for caller chaining.

    Raises
    ------
    RenderError
        If ``marp`` is not on PATH, or returns non-zero exit status.
    FileNotFoundError
        If ``deck_md`` does not exist.
    """
    deck_md = Path(deck_md)
    out_pdf = Path(out_pdf)
    if not deck_md.exists():
        raise FileNotFoundError(f"deck source not found: {deck_md}")

    if shutil.which("marp") is None:
        raise RenderError(
            "marp CLI not found on PATH. Install with "
            "`npm install -g @marp-team/marp-cli` or use `npx`."
        )

    config_path = config if config is not None else DEFAULT_MARP_CONFIG

    cmd = [
        "marp",
        str(deck_md),
        "--pdf",
        "--html",
        "--config-file",
        str(config_path),
        "--allow-local-files",
        "--output",
        str(out_pdf),
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RenderError(
            f"marp failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return out_pdf


# ---------------------------------------------------------------------------
# Mermaid (mmdc) preflight
# ---------------------------------------------------------------------------

# Remediation message surfaced when ``mmdc`` is absent. Shared by the
# figurer preflight and any caller that wants to emit a ``[blocker]`` with the
# full install story. ``mmdc`` is REQUIRED for any deck containing a diagram:
# inline ```mermaid fences do NOT render as diagrams in the canonical
# ``marp --pdf`` output (verified, issue #65) — they degrade to raw code — so
# ``mmdc → PNG`` is the only working diagram path for the PDF.
MMDC_REMEDIATION = (
    "mmdc (mermaid-cli) not found on PATH — required to render mermaid "
    "diagrams to PNG. Install with `npm install -g @mermaid-js/mermaid-cli`. "
    "Note: mmdc pulls Puppeteer + a ~300MB+ headless Chromium on first "
    "install. In CI/containers Chromium typically needs --no-sandbox: pass "
    "`mmdc --puppeteerConfigFile <file>` where <file> contains "
    '{"args":["--no-sandbox"]}.'
)


def check_mmdc_available() -> bool:
    """Return ``True`` if the ``mmdc`` (mermaid-cli) binary is on PATH.

    This is the preflight guard the deck/slides figurers run before any
    ``mmdc → PNG`` render. It mirrors the ``shutil.which("marp")`` guard in
    :func:`render_marp_to_pdf` so the figurer can fail fast with a legible
    ``[blocker]`` (see :data:`MMDC_REMEDIATION`) instead of producing a deck
    that references a PNG ``mmdc`` never rendered.

    ``mmdc`` is required for any deck containing a diagram, not a fallback:
    inline ```mermaid fences do not render in the canonical ``marp --pdf``
    output (verified, issue #65). A deck with zero diagrams does not need
    ``mmdc`` and callers should not invoke this preflight in that case.

    Kept binary-presence-only (no Chromium launch) so it is unit-testable
    with a stubbed/monkeypatched ``shutil.which`` and requires no real
    Chromium at test time.
    """
    return shutil.which("mmdc") is not None


def require_mmdc() -> None:
    """Raise :class:`RenderError` with full remediation if ``mmdc`` is absent.

    Convenience wrapper over :func:`check_mmdc_available` for callers that
    prefer the raise-on-missing shape used by :func:`render_marp_to_pdf`'s
    ``marp`` guard.
    """
    if not check_mmdc_available():
        raise RenderError(MMDC_REMEDIATION)


# ---------------------------------------------------------------------------
# pdfjam preflight (OPTIONAL — only needed for slides-handout N-up layouts)
# ---------------------------------------------------------------------------

# Remediation message surfaced when ``pdfjam`` is absent and a handout layout
# that needs it (``--4-up`` or ``--2-up``) is requested. ``pdfjam`` is OPTIONAL
# at the framework level: ``slides-handout --notes-below`` uses Marp's native
# ``--pdf-notes`` mode (one slide per page with notes printed beneath) and
# requires no post-processing. Marp's rendering model is fundamentally
# one-section-per-page; there is no Marp CLI flag (or CSS injection) that
# combines N sections onto a single rendered page, so a post-process step is
# the only N-up path for the ``--4-up`` and ``--2-up`` handout variants.
PDFJAM_REMEDIATION = (
    "pdfjam (TeX Live's pdfjam package) not found on PATH — required only for "
    "`slides-handout --4-up` and `slides-handout --2-up` N-up handout layouts. "
    "Install via `tlmgr install pdfjam` (if TeX Live is already present), "
    "`apt-get install texlive-extra-utils` (Debian/Ubuntu), or "
    "`brew install --cask mactex-no-gui` (macOS). "
    "Note: TeX Live is a multi-GB install; if you do not need N-up handouts "
    "you can use `slides-handout --notes-below` instead, which renders via "
    "Marp's `--pdf-notes` mode and does NOT require pdfjam."
)


def check_pdfjam_available() -> bool:
    """Return ``True`` if the ``pdfjam`` binary is on PATH.

    This is the preflight guard ``slides-handout`` runs before invoking the
    N-up post-process step for ``--4-up`` and ``--2-up`` layouts. It mirrors
    the ``shutil.which("mmdc")`` guard in :func:`check_mmdc_available` so the
    handout exporter can fail fast with a legible ``[blocker]`` (see
    :data:`PDFJAM_REMEDIATION`) instead of producing a one-slide-per-page PDF
    while the user expected a 4-up grid.

    ``pdfjam`` is OPTIONAL, not required: ``slides-handout --notes-below``
    renders via Marp's native ``--pdf-notes`` mode and produces a usable
    leave-behind PDF with zero pdfjam dependency. Callers should not invoke
    this preflight when the requested layout is ``--notes-below``.

    Kept binary-presence-only (no subprocess spawn) so it is unit-testable
    with a stubbed/monkeypatched ``shutil.which`` and requires no real TeX
    Live install at test time.
    """
    return shutil.which("pdfjam") is not None


def require_pdfjam() -> None:
    """Raise :class:`RenderError` with full remediation if ``pdfjam`` is absent.

    Convenience wrapper over :func:`check_pdfjam_available` for callers that
    prefer the raise-on-missing shape used by :func:`render_marp_to_pdf`'s
    ``marp`` guard. The handout exporter calls this only when the requested
    layout is ``--4-up`` or ``--2-up`` — the ``--notes-below`` path renders
    without invoking this guard.
    """
    if not check_pdfjam_available():
        raise RenderError(PDFJAM_REMEDIATION)


# ---------------------------------------------------------------------------
# PDF → per-page PNGs
# ---------------------------------------------------------------------------


def render_pdf_to_pngs(
    pdf: Path,
    out_dir: Path,
    dpi: int = 150,
) -> List[Path]:
    """Convert a PDF to one PNG per page.

    Default path: ``pdftoppm -r <dpi> -png <pdf> <out_dir>/page``, which
    writes ``page-1.png``, ``page-2.png``, ... (one-indexed, no zero-pad).
    Fallback path: ``pdf2image.convert_from_path`` — only attempted when
    ``pdftoppm`` is not available AND the ``pdf2image`` module is
    importable.

    Parameters
    ----------
    pdf:
        Path to the input PDF.
    out_dir:
        Output directory. Created if it does not exist.
    dpi:
        Output resolution. 150 is a sensible default for 1080p-class
        critique; bump to 200+ for fine-grained chart-label legibility
        evaluation.

    Returns
    -------
    Sorted list of PNG paths produced.

    Raises
    ------
    RenderError
        If neither ``pdftoppm`` nor ``pdf2image`` is available, or the
        chosen tool returns non-zero.
    FileNotFoundError
        If the input PDF does not exist.
    """
    pdf = Path(pdf)
    out_dir = Path(out_dir)
    if not pdf.exists():
        raise FileNotFoundError(f"PDF not found: {pdf}")
    out_dir.mkdir(parents=True, exist_ok=True)

    if shutil.which("pdftoppm") is not None:
        # Primary path.
        cmd = [
            "pdftoppm",
            "-r",
            str(dpi),
            "-png",
            str(pdf),
            str(out_dir / "page"),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise RenderError(
                f"pdftoppm failed (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return _collect_page_pngs(out_dir)

    # Fallback: pdf2image (Python wrapper around the same library).
    try:
        from pdf2image import convert_from_path  # type: ignore
    except ImportError as exc:
        raise RenderError(
            "Neither pdftoppm (poppler-utils) nor pdf2image is "
            "available. Install poppler "
            "(`brew install poppler` / `apt-get install poppler-utils`) "
            "or `pip install pdf2image`."
        ) from exc

    images = convert_from_path(str(pdf), dpi=dpi)
    out_paths: List[Path] = []
    for i, image in enumerate(images, start=1):
        path = out_dir / f"page-{i}.png"
        image.save(str(path), "PNG")
        out_paths.append(path)
    return sorted(out_paths)


def _collect_page_pngs(out_dir: Path) -> List[Path]:
    """Sort the page PNGs produced by pdftoppm by page number.

    pdftoppm writes ``page-1.png``, ``page-2.png``, ..., ``page-10.png``.
    Plain string sort would order ``page-10.png`` before ``page-2.png``,
    so we extract the integer suffix.
    """
    pngs = list(out_dir.glob("page-*.png"))

    def _page_num(p: Path) -> int:
        stem = p.stem  # "page-3"
        try:
            return int(stem.rsplit("-", 1)[1])
        except (ValueError, IndexError):
            return -1

    return sorted(pngs, key=_page_num)


# ---------------------------------------------------------------------------
# Pandoc Markdown → PDF (for pub/report)
# ---------------------------------------------------------------------------


def render_pandoc_to_pdf(
    source_md: Path,
    out_pdf: Path,
    defaults: Optional[Path] = None,
) -> Path:
    """Render a prose Markdown document to PDF via pandoc.

    Used by future ``pub-vision`` and ``report-vision`` critics where the
    artifact is a research paper or technical report rather than a deck.
    The Marp path is appropriate for slide artifacts only.

    Parameters
    ----------
    source_md:
        Path to the source Markdown.
    out_pdf:
        Output PDF path. Parent directory must exist.
    defaults:
        Optional path to a pandoc ``defaults.yaml`` file. When ``None``,
        pandoc runs with no flags beyond ``-o``.

    Returns
    -------
    The output PDF path.

    Raises
    ------
    RenderError
        If ``pandoc`` is not on PATH, or returns non-zero exit status.
    FileNotFoundError
        If ``source_md`` does not exist.
    """
    source_md = Path(source_md)
    out_pdf = Path(out_pdf)
    if not source_md.exists():
        raise FileNotFoundError(f"source not found: {source_md}")

    if shutil.which("pandoc") is None:
        raise RenderError(
            "pandoc not found on PATH. Install with "
            "`brew install pandoc` (macOS) or `apt-get install pandoc`."
        )

    cmd = ["pandoc", str(source_md), "-o", str(out_pdf)]
    if defaults is not None:
        cmd.extend(["--defaults", str(defaults)])

    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RenderError(
            f"pandoc failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return out_pdf


# ---------------------------------------------------------------------------
# matplotlib figure walker
# ---------------------------------------------------------------------------


def render_matplotlib_figures(figures_dir: Path) -> List[Path]:
    """Enumerate already-rendered PNG figures under ``figures_dir``.

    This is a no-op walker, not a re-renderer. The skill's ``figures``
    command is responsible for executing ``figures/src/*.py`` and writing
    output PNGs; this helper just hands the vision critic a sorted list
    of those PNGs.

    Parameters
    ----------
    figures_dir:
        Path to the figures directory (e.g., ``acme-seed.3/figures/``).
        If the directory does not exist, returns an empty list.

    Returns
    -------
    Sorted list of PNG paths directly under ``figures_dir`` (non-recursive
    for predictability — a critic that wants nested figures should pass
    each subdir explicitly).
    """
    figures_dir = Path(figures_dir)
    if not figures_dir.exists() or not figures_dir.is_dir():
        return []
    return sorted(figures_dir.glob("*.png"))


__all__ = [
    "DEFAULT_MARP_CONFIG",
    "MMDC_REMEDIATION",
    "PDFJAM_REMEDIATION",
    "RenderError",
    "check_mmdc_available",
    "check_pdfjam_available",
    "require_mmdc",
    "require_pdfjam",
    "render_marp_to_pdf",
    "render_pdf_to_pngs",
    "render_pandoc_to_pdf",
    "render_matplotlib_figures",
]
