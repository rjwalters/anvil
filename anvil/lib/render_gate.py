"""Deterministic render-gate for paginated Anvil artifacts.

This is the LaTeX-skill analog of ``anvil/lib/marp_lint.py``: a
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

Memo mode (``kind="memo"``)
---------------------------

When invoked with ``kind="memo"``, the gate routes through a separate
five-dimension flow tailored to the ``anvil:memo`` markdown → PDF
rendering pipeline shipped by Epic #158. The five memo checks are:

1. ``memo_compile_success`` — pandoc exited 0, the PDF exists, and the
   page count is positive.
2. ``memo_page_fit`` — rendered page count vs ``target_length.pages``
   (error) or the 400-wpp-converted ``target_length.words`` range
   (warning). Not run when ``target_length`` is absent.
3. ``memo_overfull_check`` — pandoc / weasyprint / wkhtmltopdf stderr
   warnings about lines that don't break cleanly (warning severity;
   graceful-degrades when the renderer emits no such warnings).
4. ``memo_image_refs_exist`` — delegates to
   ``anvil/skills/memo/lib/memo_image_refs.py::lint_memo_image_refs``
   (PR #160) and aggregates findings. Source-side lint already runs at
   review phase; render-gate adds the post-render catch.
5. ``memo_placeholder_scan`` — adapts ``DEFAULT_PLACEHOLDER_PATTERNS``
   for markdown comment syntax (``<!-- TODO -->``, ``[TBD]``,
   ``_TKTKTK_``). Suppression via
   ``<!-- anvil-lint-disable: memo_placeholder_scan -->``.

The memo path also owns ``_render_memo_source`` (the pandoc → weasyprint
OR wkhtmltopdf OR xelatex chain) with engine preflight via the
``check_*_available`` family in ``anvil/lib/render.py`` (added in #168).
Phase 3's ``memo-render`` command wires this into the skill; this module
is the shippable lib primitive without command changes.

Result composition mirrors ``marp_lint.LintResult``: a JSON-serializable
``GateResult`` that captures every finding, plus a typed ``Review``
(``kind=Kind.TOOL_EVIDENCE``) so the gate plugs into the existing
``anvil/lib/critics.py::aggregate`` + ``compute_verdict`` pipeline without
any schema or aggregator change. When the gate fails, the ``Review``
carries one ``CriticalFlag`` per failed dimension, which forces
``Verdict.BLOCK`` downstream.

page_cap calibration
--------------------

The memo gate's ``memo_page_fit`` dimension converts
``target_length.words`` into a rendered-page-count range via a
words-per-page (wpp) proxy. The default is :data:`MEMO_WORDS_PER_PAGE`
(**400 wpp**), which is calibrated for the **mixed-content** memo the
canary's investment-memo example assumes (prose body with occasional
tables). Pure dense-prose memos (no tables) run closer to 500-600 wpp,
while table-heavy memos (financial models, comp tables, sensitivity
matrices) run effectively ~300-350 wpp once the table whitespace is
accounted for — the 400-wpp default is the practical midpoint that
avoids systematically misfiring on table-dense memos.

The override hook is per-thread: callers can pass
``words_per_page=<positive number>`` to :func:`gate` (when
``kind="memo"``) to use a custom conversion factor for the
``target_length.words → page range`` conversion. The ``memo-render``
command reads this from ``<thread>/.anvil.json`` as the
``render_gate.words_per_page`` field (see
``anvil/skills/memo/commands/memo-render.md`` step 4 + the SKILL.md
``.anvil.json`` reference).

Validation: a non-numeric override or one ``<= 0`` is silently
discarded and the default (:data:`MEMO_WORDS_PER_PAGE`) is used,
matching :func:`_resolve_target_length`'s graceful-degrade contract
for malformed inputs. The effective wpp is recorded in the
``memo_page_fit`` finding message so a reviewer can see which
calibration the gate used.

The override only affects the **derived** ``target_length.words →
pages`` path. When ``target_length.pages`` is declared directly, no
conversion happens and the override is a no-op. The word-count proxy
in rubric dim 7 (*Scope discipline*) remains authoritative for
length judgments — ``memo_page_fit`` is the advisory second layer.

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


# -----------------------------------------------------------------------------
# Memo-mode constants (kind="memo")
# -----------------------------------------------------------------------------

# Dimension names for the memo gate. The ``memo_`` prefix keeps them
# distinguishable from the LaTeX-side dimensions so downstream consumers
# can route on the specific failure without ambiguity.
DIM_MEMO_COMPILE = "memo_compile_success"
DIM_MEMO_PAGE_FIT = "memo_page_fit"
DIM_MEMO_OVERFULL = "memo_overfull_check"
DIM_MEMO_IMAGE_REFS = "memo_image_refs_exist"
DIM_MEMO_PLACEHOLDERS = "memo_placeholder_scan"

# Engine names for the memo render chain. Selection priority per architect
# Q1 (Epic #158): weasyprint > wkhtmltopdf > xelatex. Pandoc is the common
# front-end for all three branches.
MEMO_ENGINE_WEASYPRINT = "weasyprint"
MEMO_ENGINE_WKHTMLTOPDF = "wkhtmltopdf"
MEMO_ENGINE_XELATEX = "xelatex"

# Words-per-page proxy used to convert ``target_length.words`` into a
# rendered-page-count range when ``target_length.pages`` is not declared
# explicitly. Mirrors the constant documented in
# ``anvil/skills/memo/SKILL.md`` §"Length targets" and used by the rubric.
MEMO_WORDS_PER_PAGE = 400

# Default placeholder patterns for the memo gate. Adapted from
# ``DEFAULT_PLACEHOLDER_PATTERNS`` for markdown comment syntax and the
# memo-author idioms (``_TKTKTK_`` is the canary's "to come" marker —
# pronounced "tee-kay"). The ``<!--`` / ``-->`` delimiters are not
# matched literally so a TODO outside an HTML comment also fires.
DEFAULT_MEMO_PLACEHOLDER_PATTERNS: tuple[str, ...] = (
    r"<!--\s*TODO[^>]*-->",
    r"<!--\s*TBD[^>]*-->",
    r"<!--\s*FIXME[^>]*-->",
    r"\bTODO\b",
    r"\[TBD\]",
    r"\[TKTKTK\]",
    r"_TKTKTK_",
    r"\bTKTKTK\b",
    r"\(figure\)",
)

# Memo-side lint-disable directive (mirrors marp_lint and memo_image_refs).
# Per-line suppression: same line OR the line directly above.
_MEMO_LINT_DISABLE_RE = re.compile(
    r"<!--\s*anvil-lint-disable:\s*(?P<rules>[a-zA-Z0-9_,\-\s]+?)\s*-->",
)

# weasyprint / wkhtmltopdf surface line-wrap warnings on stderr. The
# patterns below are intentionally loose: any stderr line containing
# "overflow" / "doesn't fit" / "exceeds" / "line is too long" is recorded
# as a memo_overfull warning. Renderers that emit none of these patterns
# (a clean run) produce zero findings — the check graceful-degrades.
_MEMO_OVERFULL_PATTERNS: tuple[str, ...] = (
    r"(?i)overflow(?:s|ed|ing)?\b",
    r"(?i)doesn'?t fit",
    r"(?i)exceeds? (?:the )?(?:page|column|box|line)",
    r"(?i)line (?:is )?too (?:long|wide)",
    r"(?i)content does not fit",
    r"(?i)cannot break",
)
_MEMO_OVERFULL_RES = tuple(re.compile(p) for p in _MEMO_OVERFULL_PATTERNS)

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
        # Stable emission order: LaTeX dimensions first, memo dimensions
        # second. Within each block the order matches the documented gate
        # check order so the JSON shape is reproducible.
        ordered_dims = [
            DIM_PAGE_FIT,
            DIM_OVERFULL,
            DIM_COMPILE,
            DIM_PLACEHOLDERS,
            DIM_MEMO_COMPILE,
            DIM_MEMO_PAGE_FIT,
            DIM_MEMO_OVERFULL,
            DIM_MEMO_IMAGE_REFS,
            DIM_MEMO_PLACEHOLDERS,
        ]
        for dim in ordered_dims:
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
    pdf_path: Optional[Path] = None,
    *,
    kind: str = "latex",
    version_dir: Optional[Path] = None,
    out_pdf: Optional[Path] = None,
    target_length: Optional[dict] = None,
    words_per_page: Optional[int] = None,
    render_engine: Optional[str] = None,
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
    """Run the render gate over a compiled artifact.

    Dispatches by ``kind``:

    - ``kind="latex"`` (default): the four-dimension LaTeX-side gate. The
      historical signature (``pdf_path`` + ``log_path`` + ``source_paths``
      + ``page_cap`` + ``overfull_threshold_pt`` + ``placeholder_patterns``
      + ``pdfinfo_path`` + ``engine`` + ``compile_status`` +
      ``compile_exit_code``) is preserved verbatim.
    - ``kind="memo"``: the five-dimension memo gate (Epic #158 / Phase 2).
      Requires ``version_dir``; ``out_pdf`` defaults to
      ``<version_dir>/memo.pdf``. ``target_length`` is the resolved
      ``{"words": [min, max]}`` or ``{"pages": [min, max]}`` dict (per
      ``SKILL.md`` §Length targets). Optional ``words_per_page`` is the
      per-thread override for the words→pages conversion factor (see
      module docstring §"page_cap calibration"); ``None`` uses
      :data:`MEMO_WORDS_PER_PAGE` (400). Malformed overrides
      (non-numeric or ``<= 0``) silently fall back to the default.
      Optional ``render_engine`` (issue #320) is the per-document
      override resolved from ``BriefDocument.render_engine`` (one of
      ``"weasyprint"``, ``"xelatex"``, ``"wkhtmltopdf"``); when set and
      available on PATH it overrides the auto-priority, otherwise
      falls through gracefully.
      Routes through :func:`_gate_memo` which invokes
      :func:`_render_memo_source` for pandoc + the preferred HTML/PDF
      engine, then runs the five memo-specific checks. See module
      docstring for the full check list.

    Parameters (kind="latex")
    -------------------------
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
    if kind == "memo":
        if version_dir is None:
            raise ValueError(
                "gate(kind='memo') requires version_dir (the "
                "<thread>.{N}/ directory containing <thread>.md)."
            )
        return _gate_memo(
            version_dir=Path(version_dir),
            out_pdf=Path(out_pdf) if out_pdf is not None else None,
            target_length=target_length,
            placeholder_patterns=placeholder_patterns,
            pdfinfo_path=pdfinfo_path,
            words_per_page=words_per_page,
            render_engine=render_engine,
        )
    if kind != "latex":
        raise ValueError(
            f"gate(kind={kind!r}): unsupported kind. "
            "Expected 'latex' (default) or 'memo'."
        )
    if pdf_path is None:
        raise ValueError(
            "gate(kind='latex') requires pdf_path (the compiled PDF)."
        )
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
# Memo-mode internals (kind="memo")
# -----------------------------------------------------------------------------


def _select_memo_engine(requested: Optional[str] = None) -> Optional[str]:
    """Return the preferred memo HTML/PDF engine that is available on PATH.

    Default priority per architect Q1 (Epic #158): ``weasyprint`` >
    ``wkhtmltopdf`` > ``xelatex``. Returns ``None`` when none are
    available — callers surface ``MEMO_RENDERER_REMEDIATION`` in that
    case.

    When ``requested`` is one of the recognized engine names AND that
    engine is available on PATH, it wins over the default priority
    order. When the requested engine is NOT available, the function
    falls through to the default order rather than returning ``None``
    — the "respect the brand pin if you can, but render something
    rather than nothing" contract that matches the broader anvil
    graceful-degrade discipline. The caller can detect a mismatch by
    comparing the returned engine to ``requested``.

    The ``requested`` knob is the integration point for two related
    features:

    - The per-theme ``render_engine`` default from
      ``<consumer>/.anvil/themes/<theme>/theme.yml`` (issue #322).
    - The per-document ``documents[].render_engine`` override from
      the project BRIEF (issue #320).

    Per-document > per-theme > framework default. The caller in
    :func:`_render_memo_source` is responsible for resolving the
    precedence and passing the winning value as ``requested``.

    The optional ``requested`` parameter (issue #320) carries the
    per-document override from ``BriefDocument.render_engine`` (one of
    ``"weasyprint"``, ``"xelatex"``, ``"wkhtmltopdf"``). When set AND the
    requested engine is available on PATH, this function returns the
    requested engine regardless of the default priority order. When the
    requested engine is set but NOT available on PATH, the function
    **gracefully falls through** to the existing auto-priority — it does
    NOT raise (consistent with the graceful-degrade contract called out
    in architect Q7). When ``requested`` is ``None``, behavior is
    identical to the pre-#320 contract: no regression on legacy callers.

    Indirected through :mod:`anvil.lib.render` so monkeypatched
    ``check_*_available`` functions in tests take effect uniformly.
    """
    # Lazy import to avoid a circular dep at module load time and to let
    # tests monkeypatch the checks on the render module.
    from anvil.lib import render as _render

    # Issue #320 + #322: honor a per-thread or per-theme requested engine
    # when both (a) it is one of the known values AND (b) the corresponding
    # binary is available on PATH. Unknown / unavailable requests fall
    # through to the priority order below — no exception. The
    # ``str(...).strip().lower()`` normalization tolerates loose YAML
    # input shapes (whitespace, mixed case) from theme.yml or BRIEF.md.
    if requested:
        req = str(requested).strip().lower()
        if req == MEMO_ENGINE_WEASYPRINT and _render.check_weasyprint_available():
            return MEMO_ENGINE_WEASYPRINT
        if req == MEMO_ENGINE_WKHTMLTOPDF and _render.check_wkhtmltopdf_available():
            return MEMO_ENGINE_WKHTMLTOPDF
        if req == MEMO_ENGINE_XELATEX and shutil.which(MEMO_ENGINE_XELATEX) is not None:
            return MEMO_ENGINE_XELATEX
        # Requested-but-unavailable (or unknown value): fall through.

    if _render.check_weasyprint_available():
        return MEMO_ENGINE_WEASYPRINT
    if _render.check_wkhtmltopdf_available():
        return MEMO_ENGINE_WKHTMLTOPDF
    if shutil.which(MEMO_ENGINE_XELATEX) is not None:
        return MEMO_ENGINE_XELATEX
    return None


def _memo_body_filename(version_dir: Path) -> str:
    """Return the body markdown filename for a memo version directory.

    Body filename echoes the thread slug per the issue #295 project-org
    model lock: the on-disk shape is ``<thread>/<thread>.{N}/<thread>.md``,
    so the body filename is ``<version_dir.parent.name>.md``.
    """
    return f"{version_dir.parent.name}.md"


def _discover_memo_theme_context(
    version_dir: Path,
) -> tuple[Optional[Path], Optional[str], Optional[str]]:
    """Return ``(consumer_root, theme_name, requested_engine)`` for the memo.

    Walks upward from ``version_dir`` to:

    1. Locate the consumer root (the directory containing ``.anvil/``).
    2. Locate the enclosing project root and read its BRIEF.md.
    3. Resolve the project's theme (if any) and load
       ``<consumer>/.anvil/themes/<theme>/theme.yml`` for the
       ``render_engine`` default.

    All three return slots are independently optional — the caller
    handles ``None`` for each gracefully. Discovery never raises; any
    error in BRIEF parsing or theme loading is swallowed and the
    relevant slot returns ``None``. This matches the graceful-degrade
    contract of the existing memo render path.

    Issue #322 (theme primitive) + issue #320 (per-doc render_engine)
    integration point. The per-doc override from #320 is currently
    sourced by the caller of :func:`_render_memo_source`; this helper
    deliberately stops at the theme tier so the two issues don't fight
    over the same code surface.
    """
    consumer_root: Optional[Path] = None
    theme_name: Optional[str] = None
    requested_engine: Optional[str] = None

    # Tier 1: locate consumer root (the directory containing .anvil/).
    try:
        from anvil.lib.theme import find_consumer_root, load_theme

        consumer_root = find_consumer_root(version_dir)
    except Exception:
        # Defensive — theme.py is part of the framework so import should
        # always succeed; this guard exists for future-proofing.
        return (None, None, None)

    # Tier 2: locate project root + read BRIEF for theme: field.
    try:
        # Lazy import: project_discovery lives under the memo skill's
        # lib/ which isn't always on sys.path at module-import time.
        # Reuse the resolution logic from the discovery primitive
        # rather than re-rolling the walk-up.
        import sys

        memo_lib = (
            Path(__file__).parent.parent / "skills" / "memo" / "lib"
        )
        memo_lib_str = str(memo_lib)
        if memo_lib_str not in sys.path:
            sys.path.insert(0, memo_lib_str)

        from project_discovery import discover_thread_root  # type: ignore
        from project_brief import load_project_brief  # type: ignore

        discovery = discover_thread_root(version_dir)
        if discovery is not None:
            brief = load_project_brief(discovery.project_root)
            if brief is not None and brief.theme:
                theme_name = brief.theme
    except Exception:
        # Any BRIEF discovery or parse failure → no theme available;
        # render falls through to framework defaults.
        return (consumer_root, None, None)

    # Tier 3: load theme.yml for render_engine default.
    if theme_name is not None and consumer_root is not None:
        try:
            theme = load_theme(consumer_root, theme_name)
            if theme is not None:
                requested_engine = theme.render_engine
        except Exception:
            requested_engine = None

    return (consumer_root, theme_name, requested_engine)


def _render_memo_source(
    version_dir: Path,
    out_pdf: Path,
    requested_engine: Optional[str] = None,
) -> tuple[str, int, str, str]:
    """Run pandoc → (weasyprint OR wkhtmltopdf OR xelatex) over the
    version dir's body markdown and write ``out_pdf``.

    Body filename echoes the thread slug per #295 — for a
    ``investment-memo/investment-memo.1/`` version dir the body is
    ``investment-memo.md``.

    This is the memo-side analog of :func:`compile_and_gate`'s LaTeX
    invocation: a single deterministic shell-out that the gate then
    inspects. The chain matches the documented pin in
    ``anvil/lib/memo/README.md``: pandoc is the common front-end; the
    HTML-to-PDF leg prefers weasyprint, falls back to wkhtmltopdf, falls
    back to xelatex as the engine-of-last-resort.

    Parameters
    ----------
    version_dir:
        ``<thread>.{N}/`` directory containing ``<thread>.md`` (body
        filename echoes the thread slug per #295).
    out_pdf:
        Output PDF path. Parent directory must exist.
    requested_engine:
        Optional per-document engine override (issue #320). Composed
        with the per-theme ``render_engine`` default from issue #322
        as ``effective_engine = requested_engine or theme_engine``;
        the result is threaded through to :func:`_select_memo_engine`.
        Per-thread wins by short-circuit: when ``requested_engine`` is
        truthy it is used directly; when ``None`` the per-theme default
        from ``theme.yml`` (discovered via
        :func:`_discover_memo_theme_context`) takes over; when both are
        absent, :func:`_select_memo_engine` falls through to the
        framework auto-priority (weasyprint > wkhtmltopdf > xelatex).
        When set and available on PATH, the effective engine is used;
        otherwise auto-priority applies.

    Returns
    -------
    A 4-tuple of ``(compile_status, exit_code, engine_used, stderr)``:

    - ``compile_status``: one of :data:`COMPILE_OK`,
      :data:`COMPILE_FAILED`, :data:`COMPILE_UNAVAILABLE`,
      :data:`COMPILE_SKIPPED`.
    - ``exit_code``: subprocess exit code, or ``-1`` when the engine
      raised before producing one.
    - ``engine_used``: the engine name (``"weasyprint"``,
      ``"wkhtmltopdf"``, ``"xelatex"``, or ``""`` when no engine ran).
    - ``stderr``: captured stderr text from the pandoc invocation
      (used by the overfull-check pass; empty when nothing ran).

    Does NOT raise on engine absence. Returns
    ``(COMPILE_UNAVAILABLE, -1, "", "")`` instead so the caller can
    surface :data:`MEMO_RENDERER_REMEDIATION` without an exception
    handler. This matches the graceful-degrade contract called out in
    architect Q7 (Epic #158).
    """
    # Lazy import — see :func:`_select_memo_engine`.
    from anvil.lib import render as _render

    body_filename = _memo_body_filename(version_dir)
    memo_md = version_dir / body_filename
    if not memo_md.is_file():
        # Missing source — surrogate "failed" outcome so the compile gate
        # fires for the right reason without a Python exception.
        return (COMPILE_FAILED, -1, "", f"{body_filename} not found at {memo_md}")

    if not _render.check_pandoc_available():
        return (COMPILE_UNAVAILABLE, -1, "", "")

    # Issue #322: discover the project's theme context (consumer_root,
    # theme_name, theme-default render_engine). All three slots are
    # optional — when no theme is declared (the canary's existing
    # single-tenant flow), this returns ``(None, None, None)`` and the
    # render path is byte-identical to pre-#322 behavior.
    consumer_root, theme_name, theme_engine = _discover_memo_theme_context(
        version_dir
    )

    # Issue #320 + #322 precedence: per-thread (``requested_engine`` from
    # ``documents[].render_engine``) wins over per-theme
    # (``theme.yml.render_engine``). The ``or`` short-circuit yields the
    # first truthy value, so a per-thread override (when set) wins; when
    # absent (``None``), the per-theme default takes over; when both are
    # absent, ``_select_memo_engine`` falls through to the framework
    # auto-priority (weasyprint > wkhtmltopdf > xelatex).
    effective_engine = requested_engine or theme_engine
    engine = _select_memo_engine(requested=effective_engine)
    if engine is None:
        return (COMPILE_UNAVAILABLE, -1, "", "")

    # Construct the pandoc command. The HTML chain uses --pdf-engine; the
    # xelatex chain uses the same flag (pandoc dispatches internally).
    cmd = [
        "pandoc",
        str(memo_md),
        "-o",
        str(out_pdf),
        f"--pdf-engine={engine}",
    ]
    # Resolve template + stylesheet paths through the theme-aware
    # resolver (issue #322). When no theme is declared or no per-theme
    # override exists for an asset, the resolver returns the framework
    # default — identical to the pre-#322 ``memo_lib / <asset>`` lookup.
    # Lazy import to keep the resolver module out of the load-time
    # circular dep chain with anvil.lib.render.
    import sys as _sys

    _memo_lib_path = (
        Path(__file__).parent.parent / "skills" / "memo" / "lib"
    )
    _memo_lib_str = str(_memo_lib_path)
    if _memo_lib_str not in _sys.path:
        _sys.path.insert(0, _memo_lib_str)
    try:
        from theme_resolver import (  # type: ignore
            MEMO_ASSET_STYLES_CSS,
            MEMO_ASSET_TEMPLATE_HTML,
            MEMO_ASSET_TEMPLATE_TEX,
            resolve_memo_asset,
        )
    except ImportError:
        # Defensive — should never trigger in a sane install; fall back
        # to the framework default lookup.
        resolve_memo_asset = None  # type: ignore[assignment]
        MEMO_ASSET_TEMPLATE_HTML = "template.html"  # type: ignore[assignment]
        MEMO_ASSET_STYLES_CSS = "styles.css"  # type: ignore[assignment]
        MEMO_ASSET_TEMPLATE_TEX = "template.tex"  # type: ignore[assignment]

    memo_lib = Path(_render.__file__).parent / "memo"

    def _resolve(asset_name: str) -> Path:
        if resolve_memo_asset is None:
            return memo_lib / asset_name
        return resolve_memo_asset(
            asset_name,
            consumer_root=consumer_root,
            theme_name=theme_name,
        )

    if engine in (MEMO_ENGINE_WEASYPRINT, MEMO_ENGINE_WKHTMLTOPDF):
        html_template = _resolve(MEMO_ASSET_TEMPLATE_HTML)
        styles_css = _resolve(MEMO_ASSET_STYLES_CSS)
        if html_template.exists():
            cmd.extend(["--template", str(html_template)])
        if styles_css.exists():
            cmd.extend(["--css", str(styles_css)])
        cmd.append("--standalone")
    else:  # xelatex
        tex_template = _resolve(MEMO_ASSET_TEMPLATE_TEX)
        if tex_template.exists():
            cmd.extend(["--template", str(tex_template)])
    # --fail-if-warnings rolls unresolved template variables into the
    # compile gate (per Epic #158 §"Out of v0 gate scope") so the
    # placeholder + image checks don't have to re-derive them.
    cmd.append("--fail-if-warnings")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError) as exc:
        return (COMPILE_FAILED, -1, engine, str(exc))

    status = COMPILE_OK if proc.returncode == 0 else COMPILE_FAILED
    return (status, proc.returncode, engine, proc.stderr or "")


def _parse_memo_overfull(stderr_text: str) -> list[dict]:
    """Return overfull-style warnings parsed from a memo renderer's stderr.

    Each hit: ``{kind, line, raw}``. ``kind`` is always ``"overflow"``;
    the memo gate does not distinguish hbox/vbox the way LaTeX does
    (weasyprint and wkhtmltopdf surface a single "doesn't fit" / "line
    too long" warning class). ``line`` is the stderr line number (1-based)
    so a reviewer can search the captured log.

    Empty list when no patterns match — the check graceful-degrades for
    renderers that emit no such warnings (the common case on a clean
    memo). See :data:`_MEMO_OVERFULL_PATTERNS` for the recognized set.
    """
    if not stderr_text:
        return []
    hits: list[dict] = []
    for lineno, line in enumerate(stderr_text.splitlines(), start=1):
        for regex in _MEMO_OVERFULL_RES:
            if regex.search(line):
                hits.append(
                    {
                        "kind": "overflow",
                        "line": lineno,
                        "raw": line.strip(),
                    }
                )
                break  # one finding per stderr line
    return hits


def _collect_memo_disabled_lines(
    source: str, rule: str = DIM_MEMO_PLACEHOLDERS
) -> set[int]:
    """Return source-line numbers (1-based) on which ``rule`` is suppressed.

    Mirrors ``memo_image_refs._collect_disabled_lines`` so the placeholder
    scan honors the same ``<!-- anvil-lint-disable: ... -->`` directive
    shape: same-line OR the line immediately above. Comma-separated rule
    lists are honored.
    """
    disabled: set[int] = set()
    lines = source.splitlines()
    for i, line in enumerate(lines):
        for m in _MEMO_LINT_DISABLE_RE.finditer(line):
            rules = {r.strip() for r in m.group("rules").split(",") if r.strip()}
            if rule not in rules:
                continue
            disabled.add(i + 1)
            tail = line[m.end():].strip()
            head = line[: m.start()].strip()
            if tail or head:
                # Inline directive — only same-line suppression.
                continue
            # Standalone directive line — suppress the next non-blank,
            # non-directive line.
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                if not next_line.strip():
                    continue
                if _MEMO_LINT_DISABLE_RE.search(next_line):
                    continue
                disabled.add(j + 1)
                break
    return disabled


def _scan_memo_placeholders(
    source: str,
    patterns: tuple[str, ...],
) -> tuple[list[dict], list[dict]]:
    """Scan a memo source for placeholder patterns.

    Returns ``(active_hits, suppressed_hits)``:

    - ``active_hits``: not suppressed by ``<!-- anvil-lint-disable:
      memo_placeholder_scan -->`` — fire as errors.
    - ``suppressed_hits``: matched a pattern but on a disabled line —
      recorded as info-severity findings (mirrors memo_image_refs).

    Each hit: ``{pattern, line, match}``. Suppression and pattern
    semantics match :func:`_collect_memo_disabled_lines` and the
    ``re.compile`` defaults.
    """
    if not patterns:
        return ([], [])
    compiled = [(p, re.compile(p)) for p in patterns]
    disabled = _collect_memo_disabled_lines(source)
    active: list[dict] = []
    suppressed: list[dict] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        # The lint-disable directive itself contains a placeholder-looking
        # comment; skip lines whose only content is a directive so the
        # scan does not flag its own escape hatch.
        stripped = line.strip()
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            if _MEMO_LINT_DISABLE_RE.fullmatch(stripped):
                continue
        for pattern_str, regex in compiled:
            m = regex.search(line)
            if not m:
                continue
            hit = {
                "pattern": pattern_str,
                "line": lineno,
                "match": m.group(0),
            }
            if lineno in disabled:
                suppressed.append(hit)
            else:
                active.append(hit)
    return active, suppressed


def _coerce_words_per_page(value: object) -> Optional[int]:
    """Validate a caller-supplied ``words_per_page`` override.

    Returns the effective ``int`` to use, or ``None`` when the value is
    absent / malformed (in which case the caller falls back to
    :data:`MEMO_WORDS_PER_PAGE`). Accepts ``int`` and ``float``; rejects
    booleans (``isinstance(True, int)`` is the trap), strings,
    ``None``, and non-positive values.

    The graceful-degrade contract matches :func:`_resolve_target_length`
    for malformed ``target_length`` inputs — a bad override never
    raises; the gate continues with the documented default.
    """
    if value is None:
        return None
    # bool is a subclass of int; reject ``True`` / ``False`` explicitly
    # so a "truthy override" doesn't sneak through as 1 wpp.
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value <= 0:
            return None
        # Floats are tolerated (matches the curation's "positive number")
        # but downstream we operate in ints — round to nearest, with a
        # 1-floor so a 0.4 → 0 collapse can't slip past the >0 check.
        coerced = int(value)
        if coerced <= 0:
            return None
        return coerced
    return None


def _resolve_target_length(
    target_length: Optional[dict],
    *,
    words_per_page: Optional[int] = None,
) -> tuple[Optional[tuple[int, int]], Optional[tuple[int, int]], str, int]:
    """Resolve ``target_length`` into
    ``(page_range, word_range, source, effective_wpp)``.

    The ``target_length`` shape mirrors what the drafter writes into
    ``_progress.json.metadata.target_length_resolved`` (per
    ``commands/memo-draft.md`` step 5):

    - ``{"words": [min, max]}`` — word-count range; the gate computes a
      page-count range via the wpp proxy (default 400, overridable via
      ``words_per_page``).
    - ``{"pages": [min, max]}`` — page-count range; the gate uses it
      directly. ``source`` is ``"pages"`` so the gate fires errors
      (vs warnings) per architect Q3. The ``words_per_page`` override
      is a **no-op** on this path (no conversion happens).
    - ``None`` or malformed — returns ``(None, None, "none", <wpp>)``;
      the page-fit check is skipped.

    Parameters
    ----------
    target_length:
        The resolved-target dict from ``_progress.json`` or ``None``.
    words_per_page:
        Optional per-thread override for the words→pages conversion
        factor. ``None`` (the default) uses :data:`MEMO_WORDS_PER_PAGE`.
        Already validated by :func:`_coerce_words_per_page` (the public
        ``gate`` entry coerces before passing through).

    Returns
    -------
    A 4-tuple:

    - ``page_range``: ``(min_pages, max_pages)`` or ``None``.
    - ``word_range``: ``(min_words, max_words)`` or ``None`` (only set
      when ``words`` is the declared shape).
    - ``source``: one of ``"pages"``, ``"words"``, ``"none"``.
    - ``effective_wpp``: the wpp value used for the conversion (the
      override when set, otherwise :data:`MEMO_WORDS_PER_PAGE`). Always
      returned (even when the conversion didn't happen) so the caller
      can surface it in the finding message.
    """
    effective_wpp = (
        words_per_page if words_per_page is not None else MEMO_WORDS_PER_PAGE
    )
    if not isinstance(target_length, dict):
        return (None, None, "none", effective_wpp)
    pages = target_length.get("pages")
    words = target_length.get("words")
    # Reject both-keys-set per the malformed-shape contract documented in
    # SKILL.md §Length targets.
    if pages is not None and words is not None:
        return (None, None, "none", effective_wpp)
    if pages is not None:
        if (
            isinstance(pages, (list, tuple))
            and len(pages) == 2
            and all(isinstance(p, int) and p > 0 for p in pages)
            and pages[0] <= pages[1]
        ):
            return ((int(pages[0]), int(pages[1])), None, "pages", effective_wpp)
        return (None, None, "none", effective_wpp)
    if words is not None:
        if (
            isinstance(words, (list, tuple))
            and len(words) == 2
            and all(isinstance(w, int) and w > 0 for w in words)
            and words[0] <= words[1]
        ):
            min_w, max_w = int(words[0]), int(words[1])
            # wpp proxy → page range. Round to int; the gate's
            # comparison is inclusive both sides so a memo word-count
            # that converts to exactly N pages should pass an [N, N+k]
            # range. ``effective_wpp`` is the override when set,
            # otherwise the 400-wpp default.
            min_pages = max(1, min_w // effective_wpp)
            max_pages = max(1, (max_w + effective_wpp - 1) // effective_wpp)
            return ((min_pages, max_pages), (min_w, max_w), "words", effective_wpp)
    return (None, None, "none", effective_wpp)


def _gate_memo(
    *,
    version_dir: Path,
    out_pdf: Optional[Path],
    target_length: Optional[dict],
    placeholder_patterns: Optional[tuple[str, ...]],
    pdfinfo_path: Optional[str],
    words_per_page: Optional[int] = None,
    render_engine: Optional[str] = None,
) -> GateResult:
    """Five-dimension memo render-gate (kind="memo").

    See the module docstring for the dimension list and severity model.
    The function is structured to mirror the LaTeX gate's "all checks run
    independently, no short-circuit" contract.

    The optional ``render_engine`` parameter (issue #320) carries the
    per-document override forwarded from
    ``BriefDocument.render_engine`` via the public :func:`gate`
    dispatcher. It is plumbed verbatim to
    :func:`_render_memo_source`; the actual honor-or-fallthrough
    decision lives in :func:`_select_memo_engine`. When ``None``, the
    auto-priority order applies (no regression on legacy callers).
    """
    if out_pdf is None:
        # PDF output basename echoes the thread slug per #295 (e.g.
        # ``investment-memo.1/investment-memo.pdf``).
        out_pdf = version_dir / f"{version_dir.parent.name}.pdf"
    out_pdf = Path(out_pdf)

    findings: list[GateFinding] = []
    reasons: list[str] = []
    failed: set[str] = set()

    # --- Step 1: invoke the renderer ---------------------------------------
    compile_status, exit_code, engine_used, stderr_text = _render_memo_source(
        version_dir, out_pdf, requested_engine=render_engine
    )

    # --- Record fallthrough when the requested engine was overridden ------
    # Issue #320: when the caller requested a specific engine but the
    # selector returned a different one (because the requested binary is
    # not on PATH), surface the rationale in reasons so the operator can
    # see why their requested engine wasn't used. This is silent-with-
    # record: not a gate failure, not a finding, just a breadcrumb in
    # ``reasons``.
    if (
        render_engine is not None
        and engine_used
        and engine_used != render_engine
    ):
        reasons.append(
            f"{DIM_MEMO_COMPILE}: requested render_engine={render_engine!r} "
            f"not available on PATH; fell through to {engine_used!r} per "
            f"auto-priority (weasyprint > wkhtmltopdf > xelatex)."
        )

    # --- Check 1: memo_compile_success -------------------------------------
    compile_exit_code: Optional[int] = exit_code if exit_code != -1 else None
    pdf_pages: Optional[int] = None
    if compile_status == COMPILE_UNAVAILABLE:
        # Engine missing — graceful-degrade per architect Q7. Recorded as
        # an info-level reason; the gate does NOT fail the compile dim
        # because we cannot prove the artifact is broken.
        # Lazy import to keep render decoupled from gate at module load.
        from anvil.lib.render import MEMO_RENDERER_REMEDIATION

        reasons.append(
            f"{DIM_MEMO_COMPILE}: pandoc and/or HTML-to-PDF engine not on "
            f"PATH; memo render skipped. {MEMO_RENDERER_REMEDIATION}"
        )
    elif compile_status == COMPILE_FAILED:
        failed.add(DIM_MEMO_COMPILE)
        msg = (
            f"{DIM_MEMO_COMPILE}: pandoc exited "
            f"{exit_code if exit_code != -1 else 'non-zero'}"
            f"{' (engine=' + engine_used + ')' if engine_used else ''}."
        )
        reasons.append(msg)
        findings.append(
            GateFinding(
                gate=DIM_MEMO_COMPILE,
                severity="error",
                message=(
                    f"Memo render failed (exit {exit_code}); engine="
                    f"{engine_used or 'unknown'}. stderr: "
                    f"{stderr_text.strip()[:500] or '(empty)'}"
                ),
                location=str(out_pdf),
            )
        )
    elif compile_status == COMPILE_OK:
        # PDF should now exist; double-check + page count.
        if not out_pdf.exists():
            failed.add(DIM_MEMO_COMPILE)
            msg = (
                f"{DIM_MEMO_COMPILE}: pandoc exited 0 but output PDF was "
                f"not produced at {out_pdf}."
            )
            reasons.append(msg)
            findings.append(
                GateFinding(
                    gate=DIM_MEMO_COMPILE,
                    severity="error",
                    message=f"Expected PDF not found at {out_pdf} after pandoc exit 0.",
                    location=str(out_pdf),
                )
            )
        else:
            pdf_pages = _count_pages_with_pdfinfo(
                out_pdf, pdfinfo_path=pdfinfo_path
            )
            if pdf_pages is not None and pdf_pages <= 0:
                failed.add(DIM_MEMO_COMPILE)
                msg = f"{DIM_MEMO_COMPILE}: PDF reports {pdf_pages} pages."
                reasons.append(msg)
                findings.append(
                    GateFinding(
                        gate=DIM_MEMO_COMPILE,
                        severity="error",
                        message=f"Rendered PDF has {pdf_pages} pages (expected > 0).",
                        location=str(out_pdf),
                    )
                )
            elif pdf_pages is None and _which_pdfinfo(pdfinfo_path) is None:
                # pdfinfo missing — informational reason only; compile dim
                # does NOT fail (the PDF exists, we just can't introspect it).
                reasons.append(
                    f"{DIM_MEMO_COMPILE}: pdfinfo not on PATH; page-count "
                    "check skipped (PDF was produced successfully)."
                )

    # --- Check 2: memo_page_fit --------------------------------------------
    # ``words_per_page`` is already coerced by the public ``gate`` entry
    # (via :func:`_coerce_words_per_page`); when callers invoke ``_gate_memo``
    # directly, we re-coerce here so the validation contract is uniform and
    # a malformed direct-call argument graceful-degrades the same way.
    effective_override = _coerce_words_per_page(words_per_page)
    page_range, word_range, target_source, effective_wpp = _resolve_target_length(
        target_length, words_per_page=effective_override
    )
    if page_range is None:
        if target_source == "none":
            reasons.append(
                f"{DIM_MEMO_PAGE_FIT}: page-fit check skipped (no "
                "target_length declared)."
            )
    elif pdf_pages is None:
        reasons.append(
            f"{DIM_MEMO_PAGE_FIT}: page-fit check skipped (page count "
            "unavailable — see compile dim)."
        )
    else:
        min_pages, max_pages = page_range
        if min_pages <= pdf_pages <= max_pages:
            # In range — informational reason. When the range was
            # derived from word count, surface the effective wpp so the
            # reviewer can see which calibration the gate used (relevant
            # when a per-thread override is in play).
            if target_source == "words":
                reasons.append(
                    f"{DIM_MEMO_PAGE_FIT}: rendered {pdf_pages} pages within "
                    f"target [{min_pages}, {max_pages}] "
                    f"(source={target_source} @ {effective_wpp} wpp)."
                )
            else:
                reasons.append(
                    f"{DIM_MEMO_PAGE_FIT}: rendered {pdf_pages} pages within "
                    f"target [{min_pages}, {max_pages}] (source={target_source})."
                )
        else:
            # Out of range. Severity = error if source="pages" (the
            # author declared the page range explicitly); warning if
            # source="words" (the page range is derived via the
            # 400-wpp proxy and dim 7 word-count is authoritative).
            severity = "error" if target_source == "pages" else "warning"
            failed.add(DIM_MEMO_PAGE_FIT)
            if target_source == "words" and word_range is not None:
                msg = (
                    f"{DIM_MEMO_PAGE_FIT}: rendered {pdf_pages} pages "
                    f"outside derived range [{min_pages}, {max_pages}] "
                    f"(from target_length.words=[{word_range[0]}, "
                    f"{word_range[1]}] @ {effective_wpp} wpp). "
                    "Word-count proxy in dim 7 remains authoritative; "
                    "this is an advisory second-layer warning."
                )
            else:
                msg = (
                    f"{DIM_MEMO_PAGE_FIT}: rendered {pdf_pages} pages "
                    f"outside declared range [{min_pages}, {max_pages}]."
                )
            reasons.append(msg)
            findings.append(
                GateFinding(
                    gate=DIM_MEMO_PAGE_FIT,
                    severity=severity,
                    message=msg.split(": ", 1)[1],
                    location=f"{out_pdf}:pages={pdf_pages}",
                )
            )

    # --- Check 3: memo_overfull_check --------------------------------------
    if not stderr_text:
        # Renderer emitted no stderr — graceful-degrade (the common case
        # on a clean memo). Record as an info reason so the operator
        # sees the check ran.
        reasons.append(
            f"{DIM_MEMO_OVERFULL}: overflow check ran with no stderr "
            "warnings detected."
        )
    else:
        overfull_hits = _parse_memo_overfull(stderr_text)
        if overfull_hits:
            # Warnings (not errors) per architect Q3.
            reasons.append(
                f"{DIM_MEMO_OVERFULL}: {len(overfull_hits)} overflow-style "
                "warning(s) in renderer stderr."
            )
            for hit in overfull_hits:
                findings.append(
                    GateFinding(
                        gate=DIM_MEMO_OVERFULL,
                        severity="warning",
                        message=(
                            f"Renderer warning: {hit['raw'][:200]}"
                        ),
                        location=f"stderr:L{hit['line']}",
                    )
                )

    # --- Check 4: memo_image_refs_exist ------------------------------------
    # Calls into PR #160's lint module (anvil/skills/memo/lib/memo_image_refs.py).
    # The source-side lint runs at review phase; this is the post-render
    # catch (refs that exist but pandoc's resolver flagged, or symlink /
    # case edge cases). Lazy import keeps the lib lookup off the module
    # load path and makes test-side mocking straightforward.
    try:
        from anvil.skills.memo.lib import memo_image_refs as _img_refs

        lint_result = _img_refs.lint_memo_image_refs(version_dir)
        # Body filename echoes the thread slug per #295.
        body_filename = _memo_body_filename(version_dir)
        if lint_result.errors:
            failed.add(DIM_MEMO_IMAGE_REFS)
            reasons.append(
                f"{DIM_MEMO_IMAGE_REFS}: {len(lint_result.errors)} broken "
                "image reference(s) detected (post-render)."
            )
            for err in lint_result.errors:
                findings.append(
                    GateFinding(
                        gate=DIM_MEMO_IMAGE_REFS,
                        severity="error",
                        message=err.message,
                        location=f"{version_dir / body_filename}:L{err.line}",
                    )
                )
        # Surface suppressed (info) hits too so the reviewer sees what
        # was disabled, mirroring marp_lint's pattern.
        for info in lint_result.infos:
            findings.append(
                GateFinding(
                    gate=DIM_MEMO_IMAGE_REFS,
                    severity="info",
                    message=info.message,
                    location=f"{version_dir / body_filename}:L{info.line}",
                )
            )
    except ImportError:
        # Skill-local lint module is not on the import path (e.g., the
        # caller is running anvil/lib/ standalone). Record an info
        # reason; the gate dim does NOT fail because the absence of the
        # check is not evidence of a broken artifact.
        reasons.append(
            f"{DIM_MEMO_IMAGE_REFS}: image-ref lint module not "
            "importable; check skipped."
        )

    # --- Check 5: memo_placeholder_scan ------------------------------------
    # Body filename echoes the thread slug per #295.
    body_filename = _memo_body_filename(version_dir)
    memo_md = version_dir / body_filename
    if not memo_md.is_file():
        reasons.append(
            f"{DIM_MEMO_PLACEHOLDERS}: {body_filename} not found; placeholder "
            "scan skipped."
        )
    else:
        memo_patterns = (
            placeholder_patterns
            if placeholder_patterns is not None
            else DEFAULT_MEMO_PLACEHOLDER_PATTERNS
        )
        memo_source = memo_md.read_text(encoding="utf-8", errors="replace")
        active_hits, suppressed_hits = _scan_memo_placeholders(
            memo_source, memo_patterns
        )
        if active_hits:
            failed.add(DIM_MEMO_PLACEHOLDERS)
            reasons.append(
                f"{DIM_MEMO_PLACEHOLDERS}: {len(active_hits)} placeholder "
                f"hit(s) in {body_filename}."
            )
            for hit in active_hits:
                findings.append(
                    GateFinding(
                        gate=DIM_MEMO_PLACEHOLDERS,
                        severity="error",
                        message=(
                            f"Placeholder pattern {hit['pattern']!r} matched "
                            f"{hit['match']!r}."
                        ),
                        location=f"{memo_md}:L{hit['line']}",
                    )
                )
        # Suppressed → info findings for reviewer visibility.
        for hit in suppressed_hits:
            findings.append(
                GateFinding(
                    gate=DIM_MEMO_PLACEHOLDERS,
                    severity="info",
                    message=(
                        f"Placeholder pattern {hit['pattern']!r} matched "
                        f"{hit['match']!r} (suppressed)."
                    ),
                    location=f"{memo_md}:L{hit['line']}",
                )
            )

    # Build the GateResult. Keep the existing JSON shape (LaTeX-style
    # fields stay) and let the dim names disambiguate downstream
    # consumers. ``overfull_boxes`` is reused for the memo overflow hits
    # so the to_json shape is uniform across kinds.
    overfull_list: list[dict] = []
    for f in findings:
        if f.gate == DIM_MEMO_OVERFULL:
            # Lift back to the dict shape used in the JSON block.
            overfull_list.append({"kind": "overflow", "raw": f.message})
    placeholder_list: list[dict] = []
    for f in findings:
        if f.gate == DIM_MEMO_PLACEHOLDERS and f.severity == "error":
            placeholder_list.append(
                {
                    "pattern": None,
                    "path": str(memo_md),
                    "line": int(f.location.rsplit(":L", 1)[1])
                    if f.location and ":L" in f.location
                    else None,
                    "match": f.message,
                }
            )

    return GateResult(
        pdf_path=str(out_pdf),
        log_path=None,
        pages=pdf_pages,
        page_cap=page_range[1] if page_range is not None else None,
        overfull_boxes=overfull_list,
        overfull_threshold_pt=0.0,  # not meaningful for memo
        compile_status=compile_status,
        compile_exit_code=compile_exit_code,
        placeholders=placeholder_list,
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
    "DEFAULT_MEMO_PLACEHOLDER_PATTERNS",
    "GATE_NAME",
    "DIM_PAGE_FIT",
    "DIM_OVERFULL",
    "DIM_COMPILE",
    "DIM_PLACEHOLDERS",
    "DIM_MEMO_COMPILE",
    "DIM_MEMO_PAGE_FIT",
    "DIM_MEMO_OVERFULL",
    "DIM_MEMO_IMAGE_REFS",
    "DIM_MEMO_PLACEHOLDERS",
    "COMPILE_OK",
    "COMPILE_FAILED",
    "COMPILE_SKIPPED",
    "COMPILE_UNAVAILABLE",
    "MEMO_ENGINE_WEASYPRINT",
    "MEMO_ENGINE_WKHTMLTOPDF",
    "MEMO_ENGINE_XELATEX",
    "MEMO_WORDS_PER_PAGE",
    "GateFinding",
    "GateResult",
    "gate",
    "compile_and_gate",
]
