"""LaTeX → ``anvil:memo`` thread migration (issue #202).

This module ships the implementation behind the ``anvil:memo-migrate`` command:
a one-shot converter that takes a legacy ``memo.tex`` and produces a
``DRAFTED``-state ``anvil:memo`` thread (BRIEF.md + .anvil.json + <thread>.1/
with memo.md + exhibits/ + _progress.json + changelog.md) that re-enters the
standard memo lifecycle.

It exists because Studio's portfolio review surfaced 14 legacy LaTeX threads
that each needed the same hand-rolled migration. The most consequential bug
in those hand migrations was ``\\textasciitilde`` getting silently dropped by
pandoc — which turns an estimation hedge (``~$X``) into an asserted exact
value in financial prose. The migration tool exists to make that bug
impossible to ship.

Design notes
------------

1. **Subprocess-only.** Pandoc and pdftoppm are CLI binaries. No new Python
   dependency is introduced. Mirrors the existing ``check_*_available()``
   family in ``anvil/lib/render.py``.

2. **Skill-local first.** Lives under ``anvil/skills/memo/lib/`` per the
   CLAUDE.md "skill-local first, lib promotion later" pattern (the
   sibling ``memo_image_refs.py`` and ``refs_pdf.py`` are the precedents).
   Promotion to ``anvil/lib/memo/`` is a follow-on only if a second skill
   needs LaTeX migration (unlikely — this is memo-specific).

3. **Pandoc preflight is a HARD FAIL.** Unlike ``memo-render`` which is
   non-blocking by design, ``memo-migrate`` cannot proceed without pandoc.
   When pandoc is absent we raise :class:`MigrateError` carrying the
   ``MEMO_RENDERER_REMEDIATION`` install story (the pandoc-relevant
   subset). The caller (``anvil:memo-migrate`` command-line entry, or a
   test harness) is expected to convert this into a non-zero exit and
   stderr write.

4. **pdftoppm preflight is SOFT.** When pdftoppm is absent, the figure
   conversion step is skipped: the ``![](exhibits/<basename>.png)``
   refs in ``memo.md`` are still emitted (so the operator can run
   ``pdftoppm`` by hand later), but no PNGs are produced. A ``missing
   converter`` note is appended to the changelog.

5. **The load-bearing test (5c).** ``\\textasciitilde`` is explicitly
   substituted to a literal tilde BEFORE pandoc runs. The substitution
   uses a sentinel ASCII string the pandoc layer is guaranteed not to
   touch, then the sentinel is replaced by ``~`` in the post-pandoc
   markdown. This survives pandoc's silent-drop behavior and is the
   single load-bearing safeguard against turning hedged values
   (``~$50K``) into asserted values (``$50K``).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MigrateError(RuntimeError):
    """Raised when the migration cannot proceed.

    The two terminal failure modes are:

    1. **Pandoc absent on PATH.** This is the documented hard-fail
       contract — unlike ``memo-render`` (non-blocking), ``memo-migrate``
       cannot synthesize a markdown body without pandoc.
    2. **Source ``.tex`` missing or unreadable.** A programmer-side error.

    The ``MEMO_RENDERER_REMEDIATION`` install story (pandoc-relevant
    subset) is included in the message when the cause is pandoc absence.
    """


# Pandoc-only install story extracted from ``anvil/lib/render.py``.
# We keep the message skill-local (instead of importing the full
# ``MEMO_RENDERER_REMEDIATION`` from ``anvil.lib.render``) per the
# consumer-install discipline documented on the sibling ``refs_pdf.py``:
# consumer installs land the framework at ``.anvil/`` with no top-level
# ``anvil/`` package on ``sys.path``, so a runtime ``from anvil.lib.render``
# import would dangle. Inlining the pandoc-only subset here also keeps the
# message focused — migrate doesn't need the weasyprint/wkhtmltopdf/xelatex
# branches (those are render-time concerns).
PANDOC_REMEDIATION = (
    "anvil:memo-migrate requires the `pandoc` binary on PATH (see "
    "anvil/lib/render.py MEMO_RENDERER_REMEDIATION for the full memo "
    "render-chain install story). Install via `brew install pandoc` "
    "(macOS) or `apt-get install pandoc` (Debian/Ubuntu); it is the "
    "common front-end for the LaTeX → markdown conversion. "
    "Re-run `anvil:memo-migrate <source.tex>` after installing."
)

# Soft remediation for the optional pdftoppm path. ``pdftoppm`` is a
# poppler-utils binary; the same install line covers both ``pdftoppm``
# and ``pdftotext`` (sibling ``refs_pdf.py`` consumes it).
PDFTOPPM_REMEDIATION = (
    "pdftoppm (poppler-utils) not found on PATH — required only for "
    "the optional figure-conversion path in anvil:memo-migrate. Install "
    "via `brew install poppler` (macOS) or `apt-get install poppler-utils` "
    "(Debian/Ubuntu). The migration proceeds without it; \\includegraphics "
    "refs are still rewritten to exhibits/<basename>.png in memo.md but the "
    "PNGs are not produced — operator can convert by hand after install."
)


# ---------------------------------------------------------------------------
# Preflight helpers (mirror the `check_*_available()` family in render.py)
# ---------------------------------------------------------------------------


def check_pandoc_available() -> bool:
    """Return ``True`` if the ``pandoc`` binary is on PATH.

    Mirrors :func:`anvil.lib.render.check_pandoc_available`. Re-implemented
    skill-locally so the migrate module is import-safe in consumer installs
    (no top-level ``anvil/`` on ``sys.path``). Kept binary-presence-only
    (no subprocess spawn) so it is unit-testable with a monkeypatched
    ``shutil.which`` and requires no real pandoc install at test time.
    """
    return shutil.which("pandoc") is not None


def check_pdftoppm_available() -> bool:
    """Return ``True`` if the ``pdftoppm`` binary is on PATH.

    Optional dependency for the figure-conversion path. When absent the
    migration soft-degrades: ``![](exhibits/<basename>.png)`` refs are
    still emitted in ``memo.md`` but no PNGs are produced. See
    :data:`PDFTOPPM_REMEDIATION` for the operator-facing install story.
    """
    return shutil.which("pdftoppm") is not None


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class MigrationResult:
    """Summary of a single ``memo-migrate`` invocation.

    Returned by :func:`migrate_thread`. Carries enough provenance for the
    command-doc's "Report" step and for the tests to assert against
    individual sub-steps.
    """

    thread_root: Path
    version_dir: Path
    memo_md: Path
    refs_dir: Path
    brief_md: Path
    anvil_json: Path
    exhibits: List[Path] = field(default_factory=list)
    converted_pdfs: List[Path] = field(default_factory=list)
    figure_conversion_skipped: bool = False
    figure_conversion_reason: Optional[str] = None
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Sentinel used to round-trip ``\textasciitilde`` through pandoc safely.
# The sentinel MUST be a string pandoc will not touch under the
# ``markdown_strict`` writer (no markdown-meaningful characters, no
# LaTeX-meaningful characters). ``ANVILTILDE`` is uppercase ASCII letters
# only — pandoc treats it as a plain word.
_TILDE_SENTINEL = "ANVILTILDESENTINEL"

# Sentinel for ``\EUR{}`` and ``\EUR{X}``.
_EUR_SENTINEL = "ANVILEURSENTINEL"

# Default ``max_iterations`` for migration threads. Matches the SKILL.md
# §"State machine" default (``max_iterations: 4``).
_DEFAULT_MAX_ITERATIONS = 4

# Stub BRIEF.md marker — operators search for this text to find the
# unfinished migration brief before the first revise pass. Acceptance
# criterion 7 is explicit: BRIEF.md is a clearly-marked stub, not a
# "done" brief.
_BRIEF_STUB_MARKER = "TODO: migration-brief stub"


# ---------------------------------------------------------------------------
# LaTeX preprocessing
# ---------------------------------------------------------------------------


def _strip_preamble(tex_source: str) -> str:
    """Drop everything before ``\\begin{document}`` and after ``\\end{document}``.

    Per the acceptance-criteria spec: ``Drop everything between
    \\documentclass and \\begin{document} (preamble) and after
    \\end{document}.``

    If neither delimiter is present, returns ``tex_source`` unchanged —
    some LaTeX files in the cohort are body-only fragments without a
    full document scaffold.
    """
    begin_match = re.search(r"\\begin\{document\}", tex_source)
    if begin_match is not None:
        tex_source = tex_source[begin_match.end():]
    end_match = re.search(r"\\end\{document\}", tex_source)
    if end_match is not None:
        tex_source = tex_source[:end_match.start()]
    return tex_source


def _substitute_known_patterns(tex_source: str) -> str:
    """Pre-substitute LaTeX patterns pandoc gets wrong or drops silently.

    The single load-bearing transform is ``\\textasciitilde`` → tilde
    sentinel (sub-issue 5c). Pandoc has been observed to drop this
    command silently under the ``markdown_strict`` writer, which turns
    hedged values (``~$50K``) into asserted values (``$50K``). The
    sentinel is post-substituted to a literal ``~`` AFTER pandoc runs.

    Also handles ``\\EUR{}`` / ``\\EUR{X}`` (the euro symbol command)
    via the same sentinel trick — pandoc's behavior on custom commands
    is inconsistent and a sentinel guarantees round-trip.
    """
    # \textasciitilde — bare form (no braces) AND brace form.
    # Match both ``\textasciitilde`` (alone) and ``\textasciitilde{}``
    # (with empty braces — the LaTeX idiom for "end this command here").
    tex_source = re.sub(
        r"\\textasciitilde(?:\{\})?",
        _TILDE_SENTINEL,
        tex_source,
    )
    # \EUR{X} — replace the LaTeX euro command with sentinel+content.
    # Two forms: \EUR{X} (with arg) and \EUR{} (empty — bare symbol).
    tex_source = re.sub(
        r"\\EUR\{([^}]*)\}",
        lambda m: _EUR_SENTINEL + m.group(1),
        tex_source,
    )
    return tex_source


def _post_substitute_sentinels(md_source: str) -> str:
    """Replace sentinels in the pandoc output with their final markdown.

    See :func:`_substitute_known_patterns` for the substitution direction.
    This is the back half of the round-trip: after pandoc has produced
    the markdown body, walk the sentinels back to their canonical
    markdown form. The tilde sentinel becomes a literal ``~``; the EUR
    sentinel becomes ``€``.
    """
    md_source = md_source.replace(_TILDE_SENTINEL, "~")
    md_source = md_source.replace(_EUR_SENTINEL, "€")  # €
    return md_source


def _rewrite_includegraphics(
    md_source: str,
    figure_refs: List[Tuple[str, str]],
) -> str:
    """Rewrite ``\\includegraphics`` refs to markdown ``![](exhibits/...)`` form.

    Pandoc itself maps ``\\includegraphics{figures/X.pdf}`` to
    ``![image](figures/X.pdf)`` in markdown_strict. This function:

    1. Strips ``figures/`` prefix and rewrites to ``exhibits/<basename>.png``
       (anvil:memo's canonical exhibit dir + format).
    2. Strips the ``image`` alt text pandoc inserts (we prefer empty alt
       text — the surrounding prose carries the caption).
    3. Collects ``(source_pdf_relative_path, target_png_basename)``
       tuples into ``figure_refs`` so the caller can iterate them when
       running the PDF→PNG conversion.

    The implementation is markdown-side rather than LaTeX-side because
    pandoc's image-handling is well-behaved (unlike ``\\textasciitilde``);
    the cohort study found no instances where pandoc silently dropped
    the include.
    """
    # Pandoc emits ``![alt](path)`` or ``![](path)`` depending on whether
    # the LaTeX include had a caption. We accept either shape.
    pattern = re.compile(r"!\[[^\]]*\]\((?P<path>[^\)\s]+)\)")

    def _replace(match: re.Match) -> str:
        src_path = match.group("path")
        # Skip already-rewritten exhibit refs (idempotence) and skip
        # URLs / absolute paths (out of scope for this migration).
        if src_path.startswith(("http://", "https://", "data:", "/")):
            return match.group(0)
        if src_path.startswith("exhibits/"):
            return match.group(0)
        # Compute target basename. Both ``figures/fig1.pdf`` and bare
        # ``fig1.pdf`` produce ``fig1.png``.
        basename = Path(src_path).stem
        target = f"exhibits/{basename}.png"
        figure_refs.append((src_path, basename))
        return f"![]({target})"

    return pattern.sub(_replace, md_source)


def _pair_footnotes(md_source: str) -> str:
    """Walk orphan ``\\footnotemark`` + ``\\footnotetext`` pairs (sub-issue 5d).

    Pandoc renders ``\\footnotemark{}`` and ``\\footnotetext{...}`` as
    independent chunks: a bare ``[^N]`` reference with no body, and a
    raw ``[^N]: <text>`` definition that pandoc may or may not link up.

    The cheap fix: find pairs where the same numeric footnote id appears
    as both a bare ``[^N]`` reference and a ``[^N]:`` definition, and
    leave them alone — pandoc already paired them. The orphan case is
    a ``[^N]`` that has no matching definition; for those we emit a
    placeholder ``[^N]: <missing footnote text>`` block at the end of
    the document so the markdown is well-formed (no broken refs).

    This is the v0-if-cheap variant: it does not try to recover the
    original ``\\footnotetext`` body if pandoc lost it; it surfaces the
    orphan as a TODO for the operator's first revise pass.
    """
    ref_pattern = re.compile(r"\[\^(\d+)\](?!:)")
    def_pattern = re.compile(r"\[\^(\d+)\]:")

    refs = {m.group(1) for m in ref_pattern.finditer(md_source)}
    defs = {m.group(1) for m in def_pattern.finditer(md_source)}
    orphans = sorted(refs - defs, key=int)
    if not orphans:
        return md_source

    placeholder_block = "\n\n".join(
        f"[^{fid}]: TODO: migration recovered orphan footnote — "
        f"verify text against refs/prior-pipeline/v0/memo.tex"
        for fid in orphans
    )
    return md_source.rstrip() + "\n\n" + placeholder_block + "\n"


# ---------------------------------------------------------------------------
# Pandoc invocation
# ---------------------------------------------------------------------------


def _run_pandoc(tex_source: str) -> str:
    """Invoke pandoc to convert LaTeX (string) to markdown_strict.

    Uses ``pandoc -f latex -t markdown_strict`` per the acceptance-criteria
    spec. Passes the source via stdin so we don't need a temp file
    round-trip (the caller's tex_source already includes the sentinel
    substitutions from :func:`_substitute_known_patterns`).

    Raises :class:`MigrateError` on non-zero exit with the captured
    stderr appended.
    """
    if not check_pandoc_available():
        raise MigrateError(PANDOC_REMEDIATION)

    result = subprocess.run(
        ["pandoc", "-f", "latex", "-t", "markdown_strict"],
        input=tex_source,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise MigrateError(
            f"pandoc failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# Figure conversion (PDF → PNG via pdftoppm; 5a single-page rename)
# ---------------------------------------------------------------------------


def _convert_pdf_to_png(
    src_pdf: Path,
    target_basename: str,
    exhibits_dir: Path,
    dpi: int = 150,
) -> Optional[Path]:
    """Convert a single source PDF to ``<target_basename>.png`` in ``exhibits_dir``.

    Uses ``pdftoppm -r <dpi> -png <pdf> <out>/<basename>`` per the
    precedent in :func:`anvil.lib.render.render_pdf_to_pngs`. Returns
    the resulting PNG path or ``None`` if pdftoppm is absent / the
    source PDF is missing.

    Handles the **5a pdftoppm ``-1`` suffix**: ``pdftoppm`` produces
    ``<basename>-1.png`` for single-page PDFs (and ``<basename>-2.png``
    etc. for multi-page). We rename ``<basename>-1.png`` to
    ``<basename>.png`` so the markdown ref (``exhibits/<basename>.png``)
    resolves; for multi-page PDFs we keep page-1 as the canonical
    reference (later pages remain as ``<basename>-2.png``, etc., for
    operator inspection but are not referenced from memo.md).
    """
    if not check_pdftoppm_available():
        return None
    if not src_pdf.exists():
        return None

    exhibits_dir.mkdir(parents=True, exist_ok=True)
    out_stem = exhibits_dir / target_basename
    cmd = [
        "pdftoppm",
        "-r",
        str(dpi),
        "-png",
        str(src_pdf),
        str(out_stem),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        # Soft-degrade: do not raise from here; the caller records a note
        # and the operator can address pdftoppm errors out-of-band.
        return None

    # Apply the 5a -1 suffix rename. pdftoppm emits <basename>-1.png even
    # for single-page input.
    suffixed = exhibits_dir / f"{target_basename}-1.png"
    canonical = exhibits_dir / f"{target_basename}.png"
    if suffixed.exists() and not canonical.exists():
        suffixed.rename(canonical)
        return canonical
    if canonical.exists():
        return canonical
    return None


# ---------------------------------------------------------------------------
# Thread root scaffolding (BRIEF.md, .anvil.json, refs/prior-pipeline/v0/)
# ---------------------------------------------------------------------------


def _load_brief_template(skill_root: Optional[Path]) -> str:
    """Load the BRIEF.migration.md.example template body.

    The template lives at ``anvil/skills/memo/templates/BRIEF.migration.md.example``.
    For consumer installs (where the framework is at ``.anvil/skills/...``)
    the caller is expected to pass ``skill_root`` pointing at the
    installed memo skill directory.

    When the template cannot be found, falls back to a minimal inline
    stub so the migration still produces a usable BRIEF.md. This is the
    graceful-degradation contract: BRIEF.md must exist (acceptance
    criterion 7), but its prose body is operator-edited regardless.
    """
    candidates: List[Path] = []
    if skill_root is not None:
        candidates.append(skill_root / "templates" / "BRIEF.migration.md.example")
    # Fall back to the in-repo path; resolved relative to this file.
    here = Path(__file__).resolve().parent
    candidates.append(here.parent / "templates" / "BRIEF.migration.md.example")

    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def _build_brief_stub(
    source_tex: Path,
    thread_slug: str,
    template_body: str,
) -> str:
    """Produce the BRIEF.md stub body for a migration thread.

    Acceptance criterion 7: BRIEF.md is a clearly-marked stub with
    explicit TODOs the operator must fill — it is NOT a "done" brief.

    The output is structurally faithful to the
    ``BRIEF.migration.md.example`` template (so operators recognize the
    shape and section headings) but every author-judgment field is
    replaced with an explicit ``TODO`` marker. The stub-marker token
    ``TODO: migration-brief stub`` is included at the top so operators
    can grep for unfinished briefs across a portfolio.
    """
    # Use ISO date for traceability — the timestamp answers
    # "when was this migration run?" without inspecting filesystem mtimes.
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    header = (
        f"<!-- {_BRIEF_STUB_MARKER} -->\n"
        f"<!-- Generated by anvil:memo-migrate on {now} -->\n"
        f"<!-- Source: {source_tex} -->\n"
        f"<!-- Operator action: fill in the TODO fields below before "
        f"running `memo-revise`. -->\n"
        "\n"
        "---\n"
        f"company: \"TODO: fill in company name\"\n"
        f"sector: \"TODO: fill in sector\"\n"
        "stage: \"TODO: fill in stage\"\n"
        "check_size: \"TODO: fill in check size\"\n"
        "recommendation_target: undecided\n"
        f"prior_version: v0     # migrated from prior pipeline\n"
        f"this_version: v1      # first anvil:memo version\n"
        "---\n"
        "\n"
        f"# Brief: {thread_slug} — migrated from prior LaTeX pipeline\n"
        "\n"
        f"**TODO**: This is a {_BRIEF_STUB_MARKER}. The operator MUST "
        "fill in the sections below before the first `memo-revise` "
        "pass. The migration tool cannot infer company / sector / "
        "stage / check-size / recommendation-target from the source "
        "LaTeX — those are author-judgment fields.\n"
        "\n"
        "## Source material — read order\n"
        "\n"
        f"1. `refs/prior-pipeline/v0/memo.tex` — the source LaTeX body "
        f"that produced this migration.\n"
        f"2. `refs/prior-pipeline/v0/memo.pdf` — the rendered PDF "
        f"alongside the source (if present).\n"
        "\n"
        "## New content to land in v1 (TODO)\n"
        "\n"
        "- **TODO**: list the v1-specific edits the operator wants "
        "the first revise pass to land. Migration alone produces a "
        "DRAFTED state — the actual v1 content edits happen in "
        "`memo-revise`.\n"
        "\n"
        "## Hard rules carrying forward from prior versions (TODO)\n"
        "\n"
        "- **TODO**: enumerate any rules / conventions from the prior "
        "pipeline that must carry forward (e.g., headcount numbers, "
        "naming conventions, risk-ordering). The reviewer will flag "
        "violations of rules listed here as critical.\n"
    )
    # Append the canonical template body as a reference block so the
    # operator can see the shape of a finished migration brief.
    if template_body:
        header += (
            "\n"
            "---\n"
            "\n"
            "<!-- Reference: the canonical "
            "BRIEF.migration.md.example template follows. Use it as a "
            "shape guide while filling in the TODOs above. -->\n"
            "\n"
            + template_body
        )
    return header


def _build_anvil_json(target_length: Optional[Tuple[int, int]]) -> dict:
    """Produce the ``.anvil.json`` payload for the migrated thread.

    Acceptance criterion 8: the generated ``.anvil.json`` validates
    against the legacy flat shape documented in SKILL.md §"Length
    targets" — specifically ``max_iterations: 4`` (default) and an
    optional ``target_length`` of the form ``{"words": [min, max]}``.

    The flat shape is chosen over the extended shape because migration
    threads start fresh in the anvil:memo lifecycle; per-version
    overrides are a power-user concern the operator can add later.
    """
    payload: dict = {"max_iterations": _DEFAULT_MAX_ITERATIONS}
    if target_length is not None:
        min_w, max_w = target_length
        payload["target_length"] = {"words": [int(min_w), int(max_w)]}
    return payload


def _copy_refs(
    source_tex: Path,
    refs_target_dir: Path,
) -> List[Path]:
    """Copy the original ``memo.tex`` + sibling ``memo.pdf`` to refs/prior-pipeline/v0/.

    Acceptance criterion 6: the original ``memo.tex`` and ``memo.pdf``
    (if present) land at ``<thread>/refs/prior-pipeline/v0/`` so future
    revisions can cite back per the migration-brief contract.

    Also copies any sibling ``figures/`` directory referenced from the
    LaTeX source — the figures are the raw inputs to the PDF→PNG
    conversion step and we want them archived alongside the source
    LaTeX for audit-trail purposes.

    Returns the list of paths actually copied.
    """
    refs_target_dir.mkdir(parents=True, exist_ok=True)
    copied: List[Path] = []

    # Copy memo.tex
    tex_dest = refs_target_dir / "memo.tex"
    shutil.copy2(source_tex, tex_dest)
    copied.append(tex_dest)

    # Copy memo.pdf if present alongside memo.tex
    sibling_pdf = source_tex.parent / (source_tex.stem + ".pdf")
    if sibling_pdf.exists():
        pdf_dest = refs_target_dir / sibling_pdf.name
        shutil.copy2(sibling_pdf, pdf_dest)
        copied.append(pdf_dest)

    # Copy figures/ if present alongside memo.tex
    sibling_figures = source_tex.parent / "figures"
    if sibling_figures.is_dir():
        figures_dest = refs_target_dir / "figures"
        if figures_dest.exists():
            shutil.rmtree(figures_dest)
        shutil.copytree(sibling_figures, figures_dest)
        for fpath in figures_dest.rglob("*"):
            if fpath.is_file():
                copied.append(fpath)

    return copied


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def migrate_thread(
    source_tex: Path,
    portfolio_dir: Path,
    thread_slug: Optional[str] = None,
    target_length: Optional[Tuple[int, int]] = None,
    skill_root: Optional[Path] = None,
) -> MigrationResult:
    """Convert a legacy LaTeX memo into a ``DRAFTED``-state anvil:memo thread.

    This is the single public entrypoint behind the ``anvil:memo-migrate``
    command. See the module docstring for the design rationale and
    ``commands/memo-migrate.md`` for the operator-facing contract.

    Parameters
    ----------
    source_tex:
        Path to the legacy ``memo.tex`` source file.
    portfolio_dir:
        Directory under which the new thread root will be created.
        Typically the consumer's portfolio directory (``./``).
    thread_slug:
        Optional override for the auto-derived thread slug. Defaults to
        the parent-directory name of ``source_tex``.
    target_length:
        Optional ``(min_words, max_words)`` tuple to write into the
        generated ``.anvil.json`` ``target_length`` field. When ``None``
        the field is omitted entirely (operator-default behavior).
    skill_root:
        Optional path to the installed ``anvil:memo`` skill directory
        (carrying ``templates/``). Used to locate the
        ``BRIEF.migration.md.example`` template in consumer installs.
        Falls back to the in-repo path when ``None``.

    Returns
    -------
    A :class:`MigrationResult` summarizing what was produced.

    Raises
    ------
    MigrateError
        When ``pandoc`` is not on PATH (hard fail with
        :data:`PANDOC_REMEDIATION`), when ``source_tex`` does not exist,
        or when pandoc returns non-zero.
    """
    # Pandoc preflight is the FIRST gate — without it nothing else can
    # proceed. We check this BEFORE the source-existence check so an
    # operator who is missing pandoc gets the install story regardless of
    # whether they typed the path correctly.
    if not check_pandoc_available():
        raise MigrateError(PANDOC_REMEDIATION)
    source_tex = Path(source_tex).resolve()
    if not source_tex.exists():
        raise MigrateError(f"Source LaTeX file not found: {source_tex}")

    portfolio_dir = Path(portfolio_dir).resolve()
    if thread_slug is None:
        thread_slug = source_tex.parent.name

    # Build the output skeleton.
    thread_root = portfolio_dir / thread_slug
    version_dir = thread_root / f"{thread_slug}.1"
    refs_dir = thread_root / "refs"
    prior_dir = refs_dir / "prior-pipeline" / "v0"
    exhibits_dir = version_dir / "exhibits"

    thread_root.mkdir(parents=True, exist_ok=True)
    version_dir.mkdir(parents=True, exist_ok=True)
    refs_dir.mkdir(parents=True, exist_ok=True)
    prior_dir.mkdir(parents=True, exist_ok=True)
    exhibits_dir.mkdir(parents=True, exist_ok=True)

    notes: List[str] = []

    # --- Step 1: read + preprocess the LaTeX source.
    tex_source = source_tex.read_text(encoding="utf-8", errors="replace")
    tex_source = _strip_preamble(tex_source)
    tex_source = _substitute_known_patterns(tex_source)

    # --- Step 2: pandoc shell-out.
    md_body = _run_pandoc(tex_source)

    # --- Step 3: post-substitute sentinels (5c is here).
    md_body = _post_substitute_sentinels(md_body)

    # --- Step 4: rewrite \includegraphics refs (collect for the PDF→PNG step).
    figure_refs: List[Tuple[str, str]] = []
    md_body = _rewrite_includegraphics(md_body, figure_refs)

    # --- Step 5: pair orphan footnotes (5d v0-if-cheap).
    md_body = _pair_footnotes(md_body)

    # --- Step 6: write memo.md.
    memo_md = version_dir / "memo.md"
    memo_md.write_text(md_body.lstrip("\n"), encoding="utf-8")

    # --- Step 7: refs preservation (copy memo.tex + memo.pdf + figures/).
    copied_refs = _copy_refs(source_tex, prior_dir)
    notes.append(
        f"Preserved {len(copied_refs)} file(s) at "
        f"{prior_dir.relative_to(thread_root)}/"
    )

    # --- Step 8: figure conversion (PDF → PNG via pdftoppm).
    exhibits: List[Path] = []
    converted_pdfs: List[Path] = []
    figure_conversion_skipped = False
    figure_conversion_reason: Optional[str] = None
    if not check_pdftoppm_available():
        figure_conversion_skipped = True
        figure_conversion_reason = PDFTOPPM_REMEDIATION
        if figure_refs:
            notes.append(
                f"pdftoppm not on PATH — skipped conversion of "
                f"{len(figure_refs)} figure(s). "
                "memo.md refs to exhibits/*.png are emitted but the PNGs "
                "are not produced; install poppler-utils and re-run "
                "figure conversion by hand. See PDFTOPPM_REMEDIATION."
            )
    else:
        for src_rel, basename in figure_refs:
            # Resolve the PDF source. The LaTeX include path is relative
            # to the .tex file's directory, but we ALSO accept the
            # bare-basename case (figures/<name>.pdf or just <name>.pdf).
            candidates = [
                source_tex.parent / src_rel,
                source_tex.parent / "figures" / Path(src_rel).name,
                source_tex.parent / Path(src_rel).name,
            ]
            # Add the archived prior-pipeline copy as a fallback so the
            # conversion still works after the source moved.
            candidates.append(prior_dir / "figures" / Path(src_rel).name)
            for cand in candidates:
                if cand.exists() and cand.suffix.lower() == ".pdf":
                    png = _convert_pdf_to_png(
                        cand,
                        basename,
                        exhibits_dir,
                    )
                    if png is not None:
                        exhibits.append(png)
                        converted_pdfs.append(cand)
                    break

    # --- Step 9: BRIEF.md (stub).
    brief_md = thread_root / "BRIEF.md"
    template_body = _load_brief_template(skill_root)
    brief_md.write_text(
        _build_brief_stub(source_tex, thread_slug, template_body),
        encoding="utf-8",
    )

    # --- Step 10: .anvil.json (flat shape, max_iterations=4, optional
    # target_length).
    anvil_json = thread_root / ".anvil.json"
    anvil_json.write_text(
        json.dumps(_build_anvil_json(target_length), indent=2) + "\n",
        encoding="utf-8",
    )

    # --- Step 11: _progress.json (DRAFTED state derived from draft == done).
    iso_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    progress_payload = {
        "version": 1,
        "thread": thread_slug,
        "phases": {
            "draft": {
                "state": "done",
                "started": iso_now,
                "completed": iso_now,
            },
        },
        "metadata": {
            "iteration": 1,
            "max_iterations": _DEFAULT_MAX_ITERATIONS,
            "migrated_from": str(source_tex),
        },
    }
    progress_path = version_dir / "_progress.json"
    progress_path.write_text(
        json.dumps(progress_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    # --- Step 12: changelog.md (single-line "migrated from <source>").
    changelog_md = version_dir / "changelog.md"
    changelog_lines = [
        f"# Changelog for {thread_slug}.1",
        "",
        f"- Migrated from `{source_tex}` via `anvil:memo-migrate` on {iso_now}.",
        f"- Source preserved at `refs/prior-pipeline/v0/memo.tex` (and "
        f"`memo.pdf` if present).",
    ]
    if figure_refs:
        if figure_conversion_skipped:
            changelog_lines.append(
                f"- {len(figure_refs)} figure ref(s) rewritten to "
                f"`exhibits/*.png`; PDF→PNG conversion skipped (pdftoppm "
                "not on PATH)."
            )
        else:
            changelog_lines.append(
                f"- Converted {len(exhibits)} of {len(figure_refs)} figure "
                "ref(s) from PDF to PNG via pdftoppm at 150 DPI."
            )
    changelog_md.write_text(
        "\n".join(changelog_lines) + "\n",
        encoding="utf-8",
    )

    return MigrationResult(
        thread_root=thread_root,
        version_dir=version_dir,
        memo_md=memo_md,
        refs_dir=refs_dir,
        brief_md=brief_md,
        anvil_json=anvil_json,
        exhibits=exhibits,
        converted_pdfs=converted_pdfs,
        figure_conversion_skipped=figure_conversion_skipped,
        figure_conversion_reason=figure_conversion_reason,
        notes=notes,
    )


__all__ = [
    "MigrateError",
    "MigrationResult",
    "PANDOC_REMEDIATION",
    "PDFTOPPM_REMEDIATION",
    "check_pandoc_available",
    "check_pdftoppm_available",
    "migrate_thread",
]
