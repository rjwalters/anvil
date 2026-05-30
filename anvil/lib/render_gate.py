"""Deterministic render-gate for paginated Anvil artifacts.

This is the LaTeX-skill analog of ``anvil/skills/deck/lib/marp_lint.py``: a
cheap, deterministic pre-flight gate over a compiled PDF (and its compile
log + sources) that runs *before* the expensive content review. It checks
four properties:

1. **Page fit** — page count of the PDF against an optional cap (skill-set,
   per-thread overridable via ``.anvil.json``). When ``page_cap`` is ``None``
   the check is skipped (a first-class no-op — the common case).
2. **Overfull boxes** — greps the LaTeX log for ``Overfull \\hbox`` /
   ``Overfull \\vbox`` advisories whose numeric amount exceeds
   ``overfull_threshold_pt`` (default ``5.0pt``).
3. **Compile success** — non-zero engine exit OR missing output PDF.
4. **Placeholders** — scans source files for ``TODO`` / ``[TBD]`` /
   ``(figure)`` / missing-include patterns, with per-skill extras.

Result composition mirrors ``marp_lint.LintResult``: a JSON-serializable
``GateResult`` that captures every finding, plus a typed ``Review``
(``kind=Kind.TOOL_EVIDENCE``) so the gate plugs into the existing
``anvil/lib/critics.py::aggregate`` + ``compute_verdict`` pipeline without
any schema or aggregator change. When the gate fails, the ``Review``
carries one ``CriticalFlag`` per failed dimension, which forces
``Verdict.BLOCK`` downstream.

Graceful degradation
--------------------

The gate degrades cleanly when toolchain pieces are missing:

- ``pdfinfo`` (poppler-utils) absent → page-fit check sets ``pages=None``
  and the gate continues with the other checks. Reasons include a
  remediation line (``brew install poppler`` / ``apt-get install
  poppler-utils``). This mirrors the ``pdftoppm`` pattern in
  ``anvil/lib/render.py``.
- Compile log absent → overfull check sets ``overfull_boxes=[]`` with a
  note in ``reasons``; the other checks still run.
- PDF missing entirely → page-fit and overfull checks skip; placeholder
  scan over the source still runs.

All four checks are **independent**: ``passed=False`` enumerates every
failed gate in ``reasons`` (no short-circuit). This is the same shape as
``marp_lint``.

Public API
----------

- ``gate(pdf_path, ...)`` — run the gate over an already-compiled PDF.
- ``compile_and_gate(tex_path, ...)`` — invoke the LaTeX engine, capture
  the log, then run the gate over the produced PDF. Used by the skills
  whose pipeline doesn't otherwise compile (installation, proposal) and as
  a fallback for the others when called before audit/finalize.
- ``GateResult`` — JSON-serializable result with ``to_json()`` (the issue
  body's ``{gate, pages, page_cap, overfull_boxes, compile, placeholders,
  pass, reasons}`` shape) and ``to_review(version_dir, critic_id)`` (the
  typed ``Review`` consumed by the critics aggregator).
- ``DEFAULT_PLACEHOLDER_PATTERNS`` — the default placeholder regex tuple;
  skills can extend via the ``placeholder_patterns`` arg.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from anvil.lib.review_schema import (
    CriticalFlag,
    Finding,
    Kind,
    Review,
    Score,
)


# Default placeholder patterns. Skills can extend via the placeholder_patterns
# arg of ``gate``/``compile_and_gate``.
DEFAULT_PLACEHOLDER_PATTERNS: tuple[str, ...] = (
    r"\bTODO\b",
    r"\[TBD\]",
    r"\(figure\)",
    r"\\includegraphics\{[^}]*\.MISSING[^}]*\}",
    r"\.MISSING\b",
)


# Gate names used in findings/reasons and the JSON payload. These match the
# four checks the issue body enumerates.
GATE_NAME = "render_gate"
DIM_PAGE_FIT = "page_fit"
DIM_OVERFULL = "overfull_boxes"
DIM_COMPILE = "compile"
DIM_PLACEHOLDERS = "placeholders"

# Compile status values. ``ok`` and ``failed`` are the LaTeX-invoked outcomes;
# ``skipped`` means the caller did not run a compile (i.e. ``gate`` was given
# a pre-built PDF); ``unavailable`` means the requested engine was not on
# PATH.
COMPILE_OK = "ok"
COMPILE_FAILED = "failed"
COMPILE_SKIPPED = "skipped"
COMPILE_UNAVAILABLE = "unavailable"

# Pandoc has no ``Overfull`` semantics — when the engine is pandoc, the
# overfull-box check is a documented no-op (recorded in reasons).
PANDOC_ENGINE = "pandoc"

# Regex for ``Overfull \hbox (12.3pt too wide) ...`` and the vbox / too-high
# variant. The amount group is captured as a float string. We also capture
# the line span (``at lines NN--MM``) when present.
_OVERFULL_RE = re.compile(
    r"Overfull\s+\\(?P<kind>[hv])box\s+\(\s*(?P<amount>\d+(?:\.\d+)?)pt\s+too\s+(?:wide|high)\s*\)"
    r"(?:[^\n]*?at\s+lines?\s+(?P<line_start>\d+)(?:--(?P<line_end>\d+))?)?",
    re.IGNORECASE,
)

# Regex for the last-N LaTeX error lines (``! ...``). Used to surface engine
# error context when compile fails.
_LATEX_ERROR_RE = re.compile(r"^!.*$", re.MULTILINE)


# -----------------------------------------------------------------------------
# Result types
# -----------------------------------------------------------------------------


@dataclass
class GateFinding:
    """One render-gate hit. Mirrors the shape of ``marp_lint.Finding``."""

    gate: str       # one of DIM_PAGE_FIT / DIM_OVERFULL / DIM_COMPILE / DIM_PLACEHOLDERS
    severity: str   # "error" | "warning" | "info"
    message: str
    location: Optional[str] = None  # e.g. "paper.pdf:page=12" or "spec.tex:L142"

    def to_dict(self) -> dict:
        return {
            "gate": self.gate,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
        }


@dataclass
class GateResult:
    """Outcome of one render-gate pass. JSON-serializable + Review-emitter.

    The JSON shape matches the issue body's contract:
    ``{gate, pages, page_cap, overfull_boxes, compile, placeholders, pass,
    reasons}``. The typed ``Review`` emitted by ``to_review`` carries one
    ``CriticalFlag`` per failed gate dimension, which forces
    ``Verdict.BLOCK`` in the aggregator without any schema change.
    """

    pdf_path: str
    log_path: Optional[str]
    pages: Optional[int]
    page_cap: Optional[int]
    overfull_boxes: list[dict]
    overfull_threshold_pt: float
    compile_status: str
    compile_exit_code: Optional[int]
    placeholders: list[dict]
    findings: list[GateFinding] = field(default_factory=list)
    passed: bool = True
    reasons: list[str] = field(default_factory=list)
    # Internal: which gate dimensions failed. Drives to_review's CriticalFlag
    # emission and to_json's per-dimension status.
    failed_gates: set[str] = field(default_factory=set)

    def to_json(self) -> dict:
        """Emit the JSON shape called out in the issue body.

        Keys: ``gate``, ``pages``, ``page_cap``, ``overfull_boxes``,
        ``compile``, ``placeholders``, ``pass``, ``reasons``. ``compile``
        is an object ``{status, exit_code}``.
        """
        return {
            "gate": GATE_NAME,
            "pdf_path": self.pdf_path,
            "log_path": self.log_path,
            "pages": self.pages,
            "page_cap": self.page_cap,
            "overfull_boxes": list(self.overfull_boxes),
            "overfull_threshold_pt": self.overfull_threshold_pt,
            "compile": {
                "status": self.compile_status,
                "exit_code": self.compile_exit_code,
            },
            "placeholders": list(self.placeholders),
            "findings": [f.to_dict() for f in self.findings],
            "pass": self.passed,
            "reasons": list(self.reasons),
        }

    def to_critical_flags(self) -> list[CriticalFlag]:
        """One ``CriticalFlag`` per failed gate dimension.

        Empty list when ``passed=True``. The flag ``type`` follows the
        ``render_gate_<dim>`` convention so downstream consumers can route on
        the specific failure (e.g., a compile failure is operationally
        distinct from a placeholder hit).
        """
        flags: list[CriticalFlag] = []
        if not self.failed_gates:
            return flags
        for dim in [DIM_PAGE_FIT, DIM_OVERFULL, DIM_COMPILE, DIM_PLACEHOLDERS]:
            if dim not in self.failed_gates:
                continue
            justification = "; ".join(
                r for r in self.reasons if r.startswith(f"{dim}:")
            ) or f"{dim} gate failed"
            flags.append(
                CriticalFlag(
                    type=f"render_gate_{dim}",
                    justification=justification,
                )
            )
        return flags

    def to_review(self, *, version_dir: str, critic_id: str) -> Review:
        """Build a typed ``Review`` (``kind=Kind.TOOL_EVIDENCE``) for the
        critics aggregator.

        The review carries:
        - a one-row scorecard with ``score=None`` (the gate owns no rubric
          dimension; it is a pre-flight pass/fail), so ``aggregate`` treats
          this critic as null-everywhere for scoring purposes.
        - one ``CriticalFlag`` per failed gate dimension (via
          ``to_critical_flags``), which forces ``Verdict.BLOCK`` in
          ``compute_verdict``.
        - one ``Finding`` per recorded ``GateFinding`` (with the gate name
          as the dimension and the message as both rationale + suggested
          fix).
        - ``tool_calls=[]`` on every finding to satisfy the
          ``Kind.TOOL_EVIDENCE`` schema requirement (``tool_calls`` must be
          a list, not ``None``, when ``kind=tool_evidence``).
        """
        # A single null-scored dim so ``scores`` is non-empty (the schema
        # requires it) but contributes nothing to the aggregated total.
        scores = [
            Score(
                dimension=GATE_NAME,
                score=None,
                max=1,
                justification="render-gate is pre-flight pass/fail; owns no rubric dim.",
            )
        ]
        findings: list[Finding] = []
        for gf in self.findings:
            findings.append(
                Finding(
                    severity="blocker" if gf.severity == "error" else "minor",
                    dimension=gf.gate,
                    evidence_span=gf.location,
                    rationale=gf.message,
                    suggested_fix=gf.message,
                    tool_calls=[],
                )
            )
        return Review(
            schema_version="1",
            kind=Kind.TOOL_EVIDENCE,
            version_dir=version_dir,
            critic_id=critic_id,
            scores=scores,
            findings=findings,
            critical_flags=self.to_critical_flags(),
        )


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _which_pdfinfo(override: Optional[str]) -> Optional[str]:
    """Resolve the ``pdfinfo`` executable path, honoring the override."""
    if override is not None:
        return override
    return shutil.which("pdfinfo")


def _count_pages_with_pdfinfo(
    pdf_path: Path, *, pdfinfo_path: Optional[str] = None
) -> Optional[int]:
    """Return the page count of a PDF via ``pdfinfo``, or ``None`` if
    unavailable / unparsable.

    Surfaces ``None`` rather than raising — the gate is supposed to degrade
    cleanly when poppler is absent (same pattern as ``render.py`` does with
    ``pdftoppm`` falling back to ``pdf2image``).
    """
    exe = _which_pdfinfo(pdfinfo_path)
    if exe is None:
        return None
    if not pdf_path.exists():
        return None
    try:
        proc = subprocess.run(
            [exe, str(pdf_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return None
    if proc.returncode != 0:
        return None
    # pdfinfo prints lines like "Pages:           42"
    for line in proc.stdout.splitlines():
        if line.lower().startswith("pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except (ValueError, IndexError):
                return None
    return None


def _parse_overfull_boxes(log_text: str, threshold_pt: float) -> list[dict]:
    """Return the list of overfull-box hits exceeding ``threshold_pt``.

    Each entry: ``{kind, amount_pt, line, raw}``. Threshold is strictly
    greater than: a 5.0pt-over-threshold-5.0 box is NOT reported (matches
    typical LaTeX overfull tolerance — exactly-at-threshold boxes are
    cosmetic).
    """
    hits: list[dict] = []
    for m in _OVERFULL_RE.finditer(log_text):
        amount = float(m.group("amount"))
        if amount <= threshold_pt:
            continue
        line_start = m.group("line_start")
        hits.append(
            {
                "kind": f"{m.group('kind').lower()}box",
                "amount_pt": amount,
                "line": int(line_start) if line_start else None,
                "raw": m.group(0).strip(),
            }
        )
    return hits


def _scan_placeholders(
    source_paths: Iterable[Path],
    patterns: tuple[str, ...],
) -> list[dict]:
    """Grep each ``source_path`` for any of ``patterns``.

    Each match: ``{pattern, path, line, match}``. Files that fail to read
    (binary, missing) are silently skipped — the gate's job is to surface
    matches, not to fail on a malformed input.
    """
    if not patterns:
        return []
    compiled = [(p, re.compile(p)) for p in patterns]
    hits: list[dict] = []
    for path in source_paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern_str, regex in compiled:
                m = regex.search(line)
                if m:
                    hits.append(
                        {
                            "pattern": pattern_str,
                            "path": str(path),
                            "line": lineno,
                            "match": m.group(0),
                        }
                    )
    return hits


def _extract_engine_errors(log_text: str, max_lines: int = 10) -> list[str]:
    """Return the last ``max_lines`` lines starting with ``!`` (LaTeX errors)."""
    matches = _LATEX_ERROR_RE.findall(log_text)
    if not matches:
        return []
    return [m.strip() for m in matches[-max_lines:]]


# -----------------------------------------------------------------------------
# Public API: gate()
# -----------------------------------------------------------------------------


def gate(
    pdf_path: Path,
    *,
    log_path: Optional[Path] = None,
    source_paths: Optional[list[Path]] = None,
    page_cap: Optional[int] = None,
    overfull_threshold_pt: float = 5.0,
    placeholder_patterns: Optional[tuple[str, ...]] = None,
    pdfinfo_path: Optional[str] = None,
    engine: Optional[str] = None,
    compile_status: Optional[str] = None,
    compile_exit_code: Optional[int] = None,
) -> GateResult:
    """Run the four-dimension render gate over a compiled PDF.

    Parameters
    ----------
    pdf_path:
        Path to the compiled PDF. May or may not exist; a missing PDF
        skips the PDF-dependent checks gracefully.
    log_path:
        Optional path to the LaTeX/engine log file. When ``None`` (or the
        file is missing), the overfull check is skipped with a note in
        ``reasons``.
    source_paths:
        List of source files (``.tex`` / ``.md``) to grep for placeholders.
        When ``None`` or empty, the placeholder check is skipped.
    page_cap:
        Hard cap on page count. ``None`` (the common case) skips the
        page-fit check — the actual page count is still recorded in
        ``GateResult.pages`` for informational purposes.
    overfull_threshold_pt:
        Overfull-box tolerance in points. Boxes with amount strictly
        greater than this threshold fail. Default ``5.0``.
    placeholder_patterns:
        Tuple of regex patterns. When ``None``, uses
        ``DEFAULT_PLACEHOLDER_PATTERNS``. When the caller wants to
        *extend* the defaults (e.g. ip-uspto's ``\\refnum{??}``), pass
        ``DEFAULT_PLACEHOLDER_PATTERNS + ("...",)``.
    pdfinfo_path:
        Override for the ``pdfinfo`` executable path (testability).
    engine:
        Optional engine label echoed into reasons (e.g., ``"pandoc"``).
        When ``engine == "pandoc"`` the overfull-box check is skipped
        with a documented note (pandoc has no ``Overfull`` semantics).
    compile_status, compile_exit_code:
        Caller-supplied compile outcome. When the caller has already
        compiled (or this is a pre-built PDF), pass these to populate the
        ``compile`` JSON block. When both are ``None`` the gate assumes
        ``COMPILE_SKIPPED`` (the PDF was prepared elsewhere).

    All four checks run independently — no short-circuit. ``passed``
    reflects the AND of the gates that did NOT skip.
    """
    pdf_path = Path(pdf_path)
    log_p = Path(log_path) if log_path is not None else None
    sources = [Path(s) for s in (source_paths or [])]
    placeholder_patterns = (
        placeholder_patterns
        if placeholder_patterns is not None
        else DEFAULT_PLACEHOLDER_PATTERNS
    )

    findings: list[GateFinding] = []
    reasons: list[str] = []
    failed: set[str] = set()

    # --- Compile status -----------------------------------------------------
    if compile_status is None:
        # Caller didn't run a compile; assume the PDF was prepared upstream.
        # If the PDF is missing, we record a compile failure surrogate so
        # the gate fails for the right reason.
        if pdf_path.exists():
            compile_status_eff = COMPILE_SKIPPED
        else:
            compile_status_eff = COMPILE_FAILED
            compile_exit_code = compile_exit_code if compile_exit_code is not None else -1
            failed.add(DIM_COMPILE)
            msg = f"{DIM_COMPILE}: PDF not produced ({pdf_path} missing)"
            reasons.append(msg)
            findings.append(
                GateFinding(
                    gate=DIM_COMPILE,
                    severity="error",
                    message=f"Expected PDF not found at {pdf_path}.",
                    location=str(pdf_path),
                )
            )
    else:
        compile_status_eff = compile_status
        if compile_status == COMPILE_FAILED:
            failed.add(DIM_COMPILE)
            msg = (
                f"{DIM_COMPILE}: engine exited "
                f"{compile_exit_code if compile_exit_code is not None else 'non-zero'}."
            )
            reasons.append(msg)
            findings.append(
                GateFinding(
                    gate=DIM_COMPILE,
                    severity="error",
                    message=(
                        f"Compile failed (exit "
                        f"{compile_exit_code if compile_exit_code is not None else '?'}); "
                        f"see log at {log_p}."
                        if log_p is not None
                        else f"Compile failed (exit "
                        f"{compile_exit_code if compile_exit_code is not None else '?'})."
                    ),
                    location=str(log_p) if log_p else str(pdf_path),
                )
            )
            # Pull the last few engine error lines into the findings stream.
            if log_p is not None and log_p.exists():
                try:
                    log_text = log_p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    log_text = ""
                for err in _extract_engine_errors(log_text):
                    findings.append(
                        GateFinding(
                            gate=DIM_COMPILE,
                            severity="error",
                            message=err,
                            location=str(log_p),
                        )
                    )
        elif compile_status == COMPILE_UNAVAILABLE:
            # The engine isn't installed. We don't *fail* the compile gate
            # (the gate cannot prove the artifact is broken), but we DO
            # record an actionable reason so the operator knows to install
            # the toolchain. Failing closed would block reviews on every
            # machine without LaTeX; failing open keeps the rest of the
            # pipeline usable.
            reasons.append(
                f"{DIM_COMPILE}: engine not on PATH; compile skipped. "
                "Install the engine (e.g., `brew install --cask mactex` / "
                "`apt-get install texlive-xetex`)."
            )

    # --- Page fit -----------------------------------------------------------
    page_count: Optional[int] = None
    if pdf_path.exists():
        page_count = _count_pages_with_pdfinfo(
            pdf_path, pdfinfo_path=pdfinfo_path
        )
        if page_count is None and _which_pdfinfo(pdfinfo_path) is None:
            reasons.append(
                f"{DIM_PAGE_FIT}: page-fit check skipped: pdfinfo not on PATH "
                "(install poppler-utils: `brew install poppler` / "
                "`apt-get install poppler-utils`)."
            )
        elif page_count is None:
            reasons.append(
                f"{DIM_PAGE_FIT}: pdfinfo returned non-zero or unparsable output."
            )
    if page_cap is not None and page_count is not None:
        if page_count > page_cap:
            failed.add(DIM_PAGE_FIT)
            msg = (
                f"{DIM_PAGE_FIT}: PDF has {page_count} pages, exceeding "
                f"cap of {page_cap}."
            )
            reasons.append(msg)
            findings.append(
                GateFinding(
                    gate=DIM_PAGE_FIT,
                    severity="error",
                    message=msg.split(": ", 1)[1],
                    location=f"{pdf_path}:pages={page_count}",
                )
            )

    # --- Overfull boxes -----------------------------------------------------
    overfull: list[dict] = []
    if engine == PANDOC_ENGINE:
        reasons.append(
            f"{DIM_OVERFULL}: overfull-box check skipped: engine is pandoc "
            "(no `Overfull` semantics in pandoc/CSS output)."
        )
    elif log_p is None or not log_p.exists():
        reasons.append(
            f"{DIM_OVERFULL}: overfull-box check skipped: compile log not "
            "available."
        )
    else:
        try:
            log_text = log_p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            log_text = ""
        overfull = _parse_overfull_boxes(log_text, overfull_threshold_pt)
        if overfull:
            failed.add(DIM_OVERFULL)
            reasons.append(
                f"{DIM_OVERFULL}: {len(overfull)} overfull box(es) over "
                f"{overfull_threshold_pt}pt threshold."
            )
            for box in overfull:
                line_note = f"L{box['line']}" if box["line"] else "L?"
                findings.append(
                    GateFinding(
                        gate=DIM_OVERFULL,
                        severity="error",
                        message=(
                            f"Overfull \\{box['kind']} "
                            f"({box['amount_pt']:.1f}pt over) at {line_note}."
                        ),
                        location=f"{log_p}:{line_note}",
                    )
                )

    # --- Placeholders -------------------------------------------------------
    placeholders: list[dict] = []
    if sources:
        placeholders = _scan_placeholders(sources, placeholder_patterns)
        if placeholders:
            failed.add(DIM_PLACEHOLDERS)
            reasons.append(
                f"{DIM_PLACEHOLDERS}: {len(placeholders)} placeholder hit(s) "
                "across source files."
            )
            for hit in placeholders:
                findings.append(
                    GateFinding(
                        gate=DIM_PLACEHOLDERS,
                        severity="error",
                        message=(
                            f"Placeholder pattern {hit['pattern']!r} matched "
                            f"{hit['match']!r}."
                        ),
                        location=f"{hit['path']}:L{hit['line']}",
                    )
                )

    return GateResult(
        pdf_path=str(pdf_path),
        log_path=str(log_p) if log_p else None,
        pages=page_count,
        page_cap=page_cap,
        overfull_boxes=overfull,
        overfull_threshold_pt=overfull_threshold_pt,
        compile_status=compile_status_eff,
        compile_exit_code=compile_exit_code,
        placeholders=placeholders,
        findings=findings,
        passed=not failed,
        reasons=reasons,
        failed_gates=failed,
    )


# -----------------------------------------------------------------------------
# Public API: compile_and_gate()
# -----------------------------------------------------------------------------


def compile_and_gate(
    tex_path: Path,
    *,
    engine: str = "xelatex",
    page_cap: Optional[int] = None,
    overfull_threshold_pt: float = 5.0,
    placeholder_patterns: Optional[tuple[str, ...]] = None,
    extra_source_paths: Optional[list[Path]] = None,
    output_dir: Optional[Path] = None,
    pdfinfo_path: Optional[str] = None,
) -> GateResult:
    """Compile ``tex_path`` with ``engine``, capture the log, then run the
    gate over the produced PDF.

    Used by skills whose pipeline doesn't otherwise compile (installation,
    proposal) and as a fallback for the others when the gate runs before
    audit/finalize. The compile is **single-pass** by default — enough to
    catch syntax errors and overfull boxes. Skills that need a full
    multi-pass compile (e.g., ``pub`` needs ``pdflatex && bibtex &&
    pdflatex && pdflatex`` for citations) should run that compile in their
    audit step and then call ``gate(...)`` against the produced PDF +
    log; this helper is the "first pass / no upstream compile" path.

    On engine-not-on-PATH, returns a ``GateResult`` with
    ``compile_status="unavailable"`` (the page-fit / overfull /
    placeholder checks then run against any pre-existing PDF + log if
    they happen to exist, or skip gracefully).

    Parameters
    ----------
    tex_path:
        Source ``.tex`` to compile.
    engine:
        ``"xelatex"`` (default) / ``"pdflatex"`` / ``"pandoc"``. When
        ``"pandoc"`` the overfull-box check is skipped (no semantics).
    page_cap, overfull_threshold_pt, placeholder_patterns, pdfinfo_path:
        Passed through to ``gate``.
    extra_source_paths:
        Additional source files to scan for placeholders (in addition to
        ``tex_path`` itself). Useful when the artifact has a multi-file
        source (e.g., ``main.tex`` + included chapter files).
    output_dir:
        Directory the engine should write output to. Defaults to
        ``tex_path.parent``.

    Returns
    -------
    GateResult
        With ``compile_status``, ``compile_exit_code``, and the four
        gate-check outcomes populated. ``passed=False`` if any gate
        failed; ``True`` otherwise.
    """
    tex_path = Path(tex_path)
    out_dir = Path(output_dir) if output_dir is not None else tex_path.parent
    sources = [tex_path] + [Path(p) for p in (extra_source_paths or [])]

    # Conventional output layout: PDF and log next to the .tex, named after
    # the .tex stem. xelatex/pdflatex honor -output-directory; pandoc takes
    # an explicit -o.
    pdf_path = out_dir / f"{tex_path.stem}.pdf"
    log_path = out_dir / f"{tex_path.stem}.log"

    if shutil.which(engine) is None:
        # Engine unavailable. Gate against whatever the filesystem already
        # has (pre-existing PDF + log), with COMPILE_UNAVAILABLE recorded.
        return gate(
            pdf_path=pdf_path,
            log_path=log_path if log_path.exists() else None,
            source_paths=sources,
            page_cap=page_cap,
            overfull_threshold_pt=overfull_threshold_pt,
            placeholder_patterns=placeholder_patterns,
            pdfinfo_path=pdfinfo_path,
            engine=engine,
            compile_status=COMPILE_UNAVAILABLE,
            compile_exit_code=None,
        )

    # Run the engine. For LaTeX, use -interaction=nonstopmode so a syntax
    # error doesn't hang; for pandoc, the -o flag determines output.
    if engine == PANDOC_ENGINE:
        cmd = [engine, str(tex_path), "-o", str(pdf_path)]
    else:
        cmd = [
            engine,
            "-interaction=nonstopmode",
            "-output-directory",
            str(out_dir),
            str(tex_path),
        ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(out_dir),
        )
        exit_code = proc.returncode
        compile_status = COMPILE_OK if exit_code == 0 else COMPILE_FAILED
        # Pandoc doesn't write a .log; capture stderr as the log so the
        # gate's compile-failure path can show context.
        if engine == PANDOC_ENGINE and (proc.stderr or proc.stdout):
            log_path.write_text(
                (proc.stderr or "") + ("\n" if proc.stderr and proc.stdout else "") + (proc.stdout or ""),
                encoding="utf-8",
            )
    except (OSError, FileNotFoundError):
        exit_code = -1
        compile_status = COMPILE_FAILED

    return gate(
        pdf_path=pdf_path,
        log_path=log_path if log_path.exists() else None,
        source_paths=sources,
        page_cap=page_cap,
        overfull_threshold_pt=overfull_threshold_pt,
        placeholder_patterns=placeholder_patterns,
        pdfinfo_path=pdfinfo_path,
        engine=engine,
        compile_status=compile_status,
        compile_exit_code=exit_code,
    )


__all__ = [
    "DEFAULT_PLACEHOLDER_PATTERNS",
    "GATE_NAME",
    "DIM_PAGE_FIT",
    "DIM_OVERFULL",
    "DIM_COMPILE",
    "DIM_PLACEHOLDERS",
    "COMPILE_OK",
    "COMPILE_FAILED",
    "COMPILE_SKIPPED",
    "COMPILE_UNAVAILABLE",
    "GateFinding",
    "GateResult",
    "gate",
    "compile_and_gate",
]
