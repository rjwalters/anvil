"""Deterministic pending-dependency marker gate (issue #842, phase 1 of #841).

Fifth member of the deterministic-checks family (alongside
``anvil/lib/render_gate.py``, ``anvil/lib/marp_lint.py``,
``anvil/lib/revise_consistency.py``, and ``anvil/lib/numeric_consistency.py``).
It gives authors a first-class ``[PENDING <source>]`` inline marker for a
**known, tracked** external dependency (a dataset not yet delivered, a
customer quote not yet cleared, a figure waiting on a still-running
experiment) — a placeholder that must stay VISIBLE and gate terminal state
until resolved, but must never be scored as a defect the way a generic
incompleteness marker (``TODO`` / ``[TBD]``) is.

This module ships the primitive only (issue #842 is Phase 1 of 5 under the
parent tracking issue #841): marker detection, an optional ``--blocking``
CLI mode that surfaces unresolved markers as ``CriticalFlag(type=
"pending_dependency", ...)`` entries, a ``_review.json`` sidecar writer, and
``<!-- anvil-lint-disable: pending_marker -->`` suppression. Nothing here is
wired into any skill's ``*-review.md`` / ``*-audit.md`` commands or
terminal-state definition — that is Phase 2-5, one issue per consuming
skill.

Marker syntax
-------------

``[PENDING <source>]`` — a single-line, bracket-delimited marker. ``PENDING``
is matched as a whole word (``\\bPENDING\\b``), uppercase, mirroring the
case-sensitive ``TODO`` / ``TKTKTK`` conventions in
``anvil/lib/render_gate.py``'s ``DEFAULT_MEMO_PLACEHOLDER_PATTERNS`` — a
lowercase ``[pending ...]`` is not recognized as a marker at all (silent,
conservative non-match), and a glued token like ``[PENDINGFOO]`` likewise
never matches (the word-boundary requirement).

- **Well-formed**: ``<source>`` (the text between ``PENDING`` and the
  closing ``]``, trimmed) is non-empty, e.g. ``[PENDING Q3 customer
  interview transcript]``. Well-formed markers are NOT defects — they never
  fail :meth:`PendingMarkerResult.passed` — but ARE tracked: every
  well-formed, unsuppressed marker becomes a ``Finding`` (severity
  ``"minor"``, always) and, under ``--blocking``, also a distinct
  ``CriticalFlag(type="pending_dependency", ...)`` grouped by ``source``
  (issue #842's schema-additive flag type — see
  ``anvil/lib/convergence.py``'s "Pending-dependency discrimination"
  section and ``anvil/lib/critics.py::compute_verdict``: this flag type is
  EXPLICITLY excluded from forcing ``Verdict.BLOCK`` and from dim-score
  deduction).
- **Malformed**: an empty or whitespace-only source, e.g. ``[PENDING]`` or
  ``[PENDING   ]``. This IS a defect (an authoring slip, not a tracked
  dependency) — it becomes a ``Finding`` (severity ``"major"``, active) and
  DOES fail :meth:`PendingMarkerResult.passed`. Malformed markers never
  produce a ``pending_dependency`` ``CriticalFlag`` under ``--blocking``
  (they are not a "known" dependency — there is nothing to track).

Suppression
-----------

``<!-- anvil-lint-disable: pending_marker -->`` on the marker's line or the
line immediately above downgrades EITHER class of finding to severity
``"info"`` (schema ``"nit"``) — recorded but never gating, and never
producing a ``CriticalFlag`` even under ``--blocking``. Mirrors the
``numeric_consistency`` / memo lint-disable convention exactly (same
regex, same same-line-or-line-above placement rule).

Sidecar + discovery contract
----------------------------

``write_review_dir`` writes ``<thread>.{N}.pending/_review.json`` via
``anvil/lib/sidecar.py::staged_sidecar`` (crash-safe atomic rename). The
``.pending`` tag is a single segment, so ``critics.discover_critics`` picks
the sidecar up with **no aggregator change** — same coordination shape as
``.numeric/`` (#462) and ``.hyperlinks/`` (#335).

Placeholder-scan interop (issue #842 scope item 5)
---------------------------------------------------

:func:`mask_well_formed_markers` blanks out well-formed marker spans
(preserving offsets/line numbers, same masking contract as
``numeric_consistency._mask_text``) while leaving malformed markers
untouched. ``anvil/lib/render_gate.py``'s memo placeholder scan (Check 6)
runs the memo source through this mask before pattern-matching, so a
well-formed ``[PENDING <source>]`` marker this primitive explicitly
permits is never double-flagged (and hard-failed on) by the generic
incompleteness-marker scan; a malformed marker stays visible to that scan
(and to any future placeholder pattern) because it IS a defect.

CLI entry-point
----------------

``python -m anvil.lib.pending_marker <version_dir> [--write-review]
[--blocking] [--body PATH]``

Writes a JSON summary to stdout. Exit codes: ``0`` clean (zero malformed
markers, or malformed-but-suppressed only), ``1`` one or more ACTIVE
malformed markers, ``2`` invocation error. The body file is
auto-detected: ``<slug>.md`` (the #295 slug-echo memo shape) first, then
``main.tex`` (the paper/spec/primer shape); ``--body PATH`` overrides
discovery, mirroring ``numeric_consistency``'s override contract exactly.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from anvil.lib.review_schema import CriticalFlag, Finding, Kind, Review, Score
from anvil.lib.sidecar import cleanup_one_staging, staged_sidecar


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CRITIC_ID = "pending"
"""Stable identifier for this critic in ``_review.json.critic_id``."""

CHECK_NAME = "pending_marker"
"""Check identifier echoed in JSON payloads and the suppression rule."""

DIM_PENDING = "pending_marker"
"""Dimension name surfaced on every emitted Finding."""

PENDING_SUFFIX = "pending"
"""Sidecar dir tag: ``<thread>.{N}.pending/``. Single segment so
``critics.discover_critics`` picks it up with no aggregator change."""

# The schema-additive CriticalFlag.type value (issue #842). Mirrors
# anvil.lib.convergence.PENDING_DEPENDENCY_FLAG_TYPE — duplicated as a
# plain string constant here (rather than imported) so this module has no
# hard dependency on anvil.lib.convergence at import time; the two MUST
# agree (enforced by tests/lib/test_pending_marker.py).
PENDING_DEPENDENCY_FLAG_TYPE = "pending_dependency"

# Finding codes (stable identifiers; consumers grep for these).
MALFORMED_MARKER = "malformed_marker"
UNRESOLVED_PENDING = "unresolved_pending"

# Internal severities. "warning"/"major" findings are the active surface;
# "info"/"nit" findings are suppressed hits (recorded, never gating).
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# Suppression directive (shared shape with numeric_consistency / render_gate).
_LINT_DISABLE_RE = re.compile(
    r"<!--\s*anvil-lint-disable:\s*(?P<rules>[a-zA-Z0-9_,\-\s]+?)\s*-->",
)

# The marker candidate: "[PENDING" + word boundary + anything but brackets
# up to the closing "]". The \b after PENDING means "[PENDINGFOO]" never
# matches at all (not a marker — silent, conservative non-match); "[PENDING]"
# and "[PENDING   ]" DO match (rest is empty/whitespace-only -> malformed);
# "[PENDING some text]" matches with rest=" some text" -> well-formed.
MARKER_CANDIDATE_RE = re.compile(r"\[PENDING\b(?P<rest>[^\[\]]*)\]")


# ---------------------------------------------------------------------------
# Masking (for render_gate.py's Check 6 carve-out)
# ---------------------------------------------------------------------------


def mask_well_formed_markers(text: str) -> str:
    """Blank out well-formed ``[PENDING <source>]`` marker spans.

    Every masked character is replaced with a space (newlines are
    preserved) so line numbers and offsets in the masked text map 1:1 to
    ``text`` — the same masking contract as
    ``numeric_consistency._mask_text``. A MALFORMED marker (``[PENDING]``,
    ``[PENDING   ]``) is left UNTOUCHED: it is a genuine authoring defect
    this primitive does not except, so it stays visible to any generic
    placeholder scan.

    Pure function of the text; no filesystem access. The load-bearing
    consumer is ``anvil/lib/render_gate.py``'s memo placeholder scan
    (Check 6) — see the module docstring §"Placeholder-scan interop".
    """

    def blank(m: "re.Match[str]") -> str:
        if not m.group("rest").strip():
            return m.group(0)  # malformed — leave for other checks
        return "".join(c if c == "\n" else " " for c in m.group(0))

    return MARKER_CANDIDATE_RE.sub(blank, text)


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def _suppressed_lines(text: str) -> frozenset:
    """1-based line numbers covered by a ``pending_marker`` lint-disable.

    A directive on line L suppresses markers on line L and line L+1
    (same-line or line-immediately-above placement, per the memo
    lint-disable convention).
    """
    suppressed = set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in _LINT_DISABLE_RE.finditer(line):
            rules = {r.strip() for r in m.group("rules").split(",")}
            if CHECK_NAME in rules:
                suppressed.add(lineno)
                suppressed.add(lineno + 1)
    return frozenset(suppressed)


def _line_of(offset: int, text: str) -> int:
    """1-based line number of ``offset`` in ``text``."""
    return text.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------
# Marker extraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PendingMarkerHit:
    """One extracted ``[PENDING ...]`` marker occurrence."""

    well_formed: bool
    source: Optional[str]  # None for a malformed (empty-source) marker
    raw: str
    line: int
    suppressed: bool = False

    @property
    def severity(self) -> str:
        """Internal severity class: ``SEVERITY_INFO`` when suppressed
        (recorded, never gating), else ``SEVERITY_WARNING`` (active) —
        mirrors ``NumericFinding.severity`` in ``numeric_consistency.py``.
        Distinct from the schema ``Finding.severity`` Literal, which
        additionally discriminates well-formed ("minor") from malformed
        ("major") — see :meth:`PendingMarkerResult.to_review`.
        """
        return SEVERITY_INFO if self.suppressed else SEVERITY_WARNING

    @property
    def code(self) -> str:
        """Stable finding-code identifier (grep-able), mirroring
        ``NumericFinding.code`` in ``numeric_consistency.py``:
        :data:`MALFORMED_MARKER` for a malformed hit, else
        :data:`UNRESOLVED_PENDING` (well-formed — a still-outstanding
        tracked dependency).
        """
        return MALFORMED_MARKER if not self.well_formed else UNRESOLVED_PENDING

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "well_formed": self.well_formed,
            "source": self.source,
            "raw": self.raw,
            "line": self.line,
            "suppressed": self.suppressed,
            "severity": self.severity,
        }


def scan_text(text: str) -> List[PendingMarkerHit]:
    """Extract every ``[PENDING ...]`` marker occurrence from ``text``.

    Pure function of the text (no filesystem access). Well-formed and
    malformed markers are both returned; suppression (per
    ``_suppressed_lines``) is applied per-hit via the ``suppressed`` field.
    """
    suppressed_lines = _suppressed_lines(text)
    hits: List[PendingMarkerHit] = []
    for m in MARKER_CANDIDATE_RE.finditer(text):
        rest = m.group("rest")
        source = rest.strip()
        line = _line_of(m.start(), text)
        is_suppressed = line in suppressed_lines
        if source:
            hits.append(
                PendingMarkerHit(
                    well_formed=True,
                    source=source,
                    raw=m.group(0),
                    line=line,
                    suppressed=is_suppressed,
                )
            )
        else:
            hits.append(
                PendingMarkerHit(
                    well_formed=False,
                    source=None,
                    raw=m.group(0),
                    line=line,
                    suppressed=is_suppressed,
                )
            )
    return hits


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class PendingMarkerResult:
    """Outcome of one ``check_pending_markers`` pass.

    JSON-serializable + ``Review``-emitter. Shape mirrors
    ``NumericConsistencyResult`` so downstream aggregation is uniform
    across the deterministic-checks family.
    """

    version_dir: str
    body_path: str
    hits: List[PendingMarkerHit] = field(default_factory=list)

    @property
    def well_formed_hits(self) -> List[PendingMarkerHit]:
        return [h for h in self.hits if h.well_formed]

    @property
    def malformed_hits(self) -> List[PendingMarkerHit]:
        return [h for h in self.hits if not h.well_formed]

    def unresolved_sources(self) -> List[str]:
        """Source labels of every unsuppressed well-formed marker, in
        first-occurrence order (duplicates preserved — a source cited by
        three markers appears three times). Consumers wanting a unique set
        should wrap this in ``dict.fromkeys(...)`` or ``set(...)``.
        """
        return [
            h.source  # type: ignore[misc]
            for h in self.well_formed_hits
            if not h.suppressed
        ]

    def passed(self) -> bool:
        """``True`` when no ACTIVE (unsuppressed) malformed markers exist.

        Well-formed markers — suppressed or not — NEVER affect ``passed()``:
        an outstanding tracked dependency is not a mechanical defect. Only
        a malformed marker (an authoring slip) fails the gate.
        """
        return not any(
            not h.well_formed and not h.suppressed for h in self.hits
        )

    def to_json(self) -> dict:
        return {
            "check": CHECK_NAME,
            "version_dir": self.version_dir,
            "body_path": self.body_path,
            "markers_found": len(self.hits),
            "well_formed_count": len(self.well_formed_hits),
            "malformed_count": len(self.malformed_hits),
            "hits": [h.to_dict() for h in self.hits],
            "pass": self.passed(),
        }

    def to_critical_flags(self) -> List[CriticalFlag]:
        """One ``CriticalFlag(type="pending_dependency", ...)`` per unique,
        unsuppressed, well-formed marker ``source`` (line numbers of every
        occurrence are listed in the justification).

        Only meaningful under ``blocking=True`` — advisory consumers never
        call this. Suppressed markers never contribute. Malformed markers
        never contribute (they are a defect, not a tracked dependency —
        see the module docstring).
        """
        flags: List[CriticalFlag] = []
        seen: List[str] = []
        for h in self.well_formed_hits:
            if h.suppressed or h.source in seen:
                continue
            seen.append(h.source)  # type: ignore[arg-type]
            lines = sorted(
                x.line
                for x in self.well_formed_hits
                if x.source == h.source and not x.suppressed
            )
            line_list = ", ".join(f"L{n}" for n in lines)
            flags.append(
                CriticalFlag(
                    type=PENDING_DEPENDENCY_FLAG_TYPE,
                    justification=(
                        f"Outstanding pending dependency {h.source!r} "
                        f"(marker [PENDING {h.source}] at {line_list} in "
                        f"{self.body_path})."
                    ),
                    evidence_span=f"{self.body_path}:L{lines[0]}",
                )
            )
        return flags

    def to_review(
        self,
        *,
        version_dir: str,
        critic_id: str = CRITIC_ID,
        blocking: bool = False,
    ) -> Review:
        """Build a typed ``Review`` (``kind=Kind.TOOL_EVIDENCE``).

        Always emits one ``Finding`` per hit: well-formed markers at
        severity ``"minor"`` (advisory tracking, never gating);
        malformed markers at severity ``"major"`` (active defect) unless
        suppressed. Suppressed hits of either class downgrade to
        ``"nit"``.

        ``blocking=True`` additionally emits one ``CriticalFlag`` per
        unique unsuppressed well-formed ``source`` via
        :meth:`to_critical_flags` — schema-additive ``type=
        "pending_dependency"``, explicitly EXCLUDED from forcing
        ``Verdict.BLOCK`` (``anvil/lib/critics.py::compute_verdict`` /
        ``anvil/lib/convergence.py::decide_termination``, issue #842).
        """
        scores = [
            Score(
                dimension=CHECK_NAME,
                score=None,
                max=1,
                justification=(
                    "pending_marker is a deterministic outstanding-"
                    "dependency check; owns no rubric dim."
                ),
            )
        ]
        findings: List[Finding] = []
        for h in self.hits:
            if h.well_formed:
                severity = "nit" if h.suppressed else "minor"
                rationale = (
                    f"Outstanding pending dependency: [PENDING {h.source}] "
                    f"at line {h.line}."
                )
                suggested_fix = (
                    f"Resolve the {h.source!r} dependency and replace the "
                    f"marker with the final content, or leave it in place "
                    f"until the dependency lands."
                )
            else:
                severity = "nit" if h.suppressed else "major"
                rationale = (
                    f"Malformed pending marker at line {h.line}: "
                    f"{h.raw!r} has no source description."
                )
                suggested_fix = (
                    f"Add a source description inside the marker, e.g. "
                    f"[PENDING <source>], or remove the marker if it no "
                    f"longer applies."
                )
            if h.suppressed:
                rationale += (
                    " [suppressed via anvil-lint-disable: pending_marker]"
                )
            findings.append(
                Finding(
                    severity=severity,
                    dimension=DIM_PENDING,
                    evidence_span=f"{self.body_path}:L{h.line}",
                    rationale=rationale,
                    suggested_fix=suggested_fix,
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
            critical_flags=self.to_critical_flags() if blocking else [],
        )


# ---------------------------------------------------------------------------
# Pure-text entry point
# ---------------------------------------------------------------------------


def check_pending_markers_text(text: str) -> List[PendingMarkerHit]:
    """Run the pending-marker scan over body text. Pure function of the text."""
    return scan_text(text)


# ---------------------------------------------------------------------------
# Filesystem entry point
# ---------------------------------------------------------------------------


def _body_path(version_dir: Path, *, body: Optional[Path] = None) -> Path:
    """Locate the body file inside a version directory.

    Detection order: ``<slug>.md`` (the #295 slug-echo memo shape — the
    slug is the parent dir name), then ``main.tex`` (the paper/spec/primer
    shape). Raises ``FileNotFoundError`` when neither exists. Mirrors
    ``numeric_consistency._body_path`` exactly (see that module's
    docstring for the ``--body`` override rationale).
    """
    if body is not None:
        override = Path(body)
        if not override.is_absolute():
            override = version_dir / override
        if not override.is_file():
            raise FileNotFoundError(
                f"pending_marker: --body override {override!s} does not "
                f"exist or is not a file."
            )
        return override
    slug_md = version_dir / f"{version_dir.parent.name}.md"
    if slug_md.is_file():
        return slug_md
    main_tex = version_dir / "main.tex"
    if main_tex.is_file():
        return main_tex
    raise FileNotFoundError(
        f"pending_marker: no body file found in {version_dir!s} (looked "
        f"for {slug_md.name!r} per the #295 slug-echo convention, then "
        f"'main.tex')."
    )


def _record_body_path(version_dir: Path, body: Path) -> str:
    """Portfolio-relative body-path string for the result / sidecar.

    Byte-identical shape to ``numeric_consistency._record_body_path``.
    """
    body = body.resolve()
    version_dir = version_dir.resolve()
    try:
        body.relative_to(version_dir)
        return body.name
    except ValueError:
        pass
    portfolio_root = version_dir.parent.parent
    try:
        return str(body.relative_to(portfolio_root))
    except ValueError:
        return str(body)


def check_pending_markers(
    version_dir: Path, *, body: Optional[Path] = None
) -> PendingMarkerResult:
    """Run the check against a version directory's body file.

    ``body`` overrides body-file discovery (for adopted-in-place legacy
    threads whose entry point isn't ``<slug>.md``/``main.tex``); when
    omitted, discovery mirrors ``numeric_consistency.check_numeric_consistency``
    exactly. Raises ``FileNotFoundError`` when ``version_dir`` does not
    exist, an override path is missing, or no recognizable body file
    exists.
    """
    version_dir = Path(version_dir).resolve()
    if not version_dir.is_dir():
        raise FileNotFoundError(
            f"pending_marker: version_dir {version_dir!s} does not exist "
            f"or is not a directory."
        )
    body_file = _body_path(version_dir, body=body)
    text = body_file.read_text(encoding="utf-8")
    hits = scan_text(text)
    return PendingMarkerResult(
        version_dir=version_dir.name,
        body_path=_record_body_path(version_dir, body_file),
        hits=hits,
    )


def write_review_dir(
    version_dir: Path,
    result: PendingMarkerResult,
    *,
    critic_id: str = CRITIC_ID,
    blocking: bool = False,
) -> Path:
    """Write ``<version_dir>.pending/_review.json`` for auto-discovery.

    Uses ``staged_sidecar`` (issue #350) so the sidecar only ever exists in
    complete form. Because this detector is deterministic and cheaply
    re-runnable, an existing ``<version_dir>.pending/`` from a prior run is
    removed and regenerated — same deterministic-regeneration posture as
    ``numeric_consistency.write_review_dir``. Returns the path to the
    written ``_review.json``.
    """
    version_dir = Path(version_dir)
    final = version_dir.parent / f"{version_dir.name}.{PENDING_SUFFIX}"
    # Per-critic entry-step sweep (parallel-safe; issue #376).
    cleanup_one_staging(final)
    if final.exists():
        shutil.rmtree(final)
    review = result.to_review(
        version_dir=version_dir.name, critic_id=critic_id, blocking=blocking
    )
    with staged_sidecar(final, required_files=["_review.json"]) as staging:
        (staging / "_review.json").write_text(
            json.dumps(review.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
    return final / "_review.json"


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def _build_cli_parser():
    import argparse

    p = argparse.ArgumentParser(
        prog="python -m anvil.lib.pending_marker",
        description=(
            "Deterministic pending-dependency marker check: detects "
            "[PENDING <source>] markers in a version directory's body "
            "file. Well-formed markers are tracked, never scored as a "
            "defect; malformed markers ([PENDING] with no source) are a "
            "defect. Advisory by default (warn-only); --blocking "
            "additionally surfaces unresolved well-formed markers as "
            "CriticalFlag(type='pending_dependency', ...) entries, which "
            "are explicitly excluded from forcing Verdict.BLOCK."
        ),
    )
    p.add_argument(
        "version_dir",
        help="Path to <thread>.{N}/ containing <thread>.md or main.tex.",
    )
    p.add_argument(
        "--write-review",
        action="store_true",
        help=(
            "Also write <version_dir>.pending/_review.json (via "
            "staged_sidecar) for critic-sibling auto-discovery by "
            "aggregate()."
        ),
    )
    p.add_argument(
        "--blocking",
        action="store_true",
        help=(
            "Emit one CriticalFlag(type='pending_dependency', ...) per "
            "unique unsuppressed well-formed marker source. These flags "
            "are visible in AggregatedReview.critical_flags but NEVER "
            "force Verdict.BLOCK (issue #842) — reserved for a future "
            "terminal-state check, not wired into any skill in this "
            "issue."
        ),
    )
    p.add_argument(
        "--body",
        metavar="PATH",
        default=None,
        help=(
            "Override body-file discovery (e.g. for adopted-in-place "
            "legacy threads whose entry point isn't <slug>.md/main.tex). "
            "Relative paths resolve against version_dir; absolute paths "
            "are used as-is. With --write-review, the resolved "
            "portfolio-relative path is recorded in the sidecar."
        ),
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Returns the process exit code.

    Exit codes:
    - ``0``: clean pass (zero malformed markers, or suppressed-only).
    - ``1``: one or more ACTIVE malformed markers.
    - ``2``: invocation error (missing version_dir or body file).
    """
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    try:
        result = check_pending_markers(
            Path(args.version_dir),
            body=Path(args.body) if args.body else None,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.to_json(), indent=2))
    if args.write_review:
        out = write_review_dir(
            Path(args.version_dir), result, blocking=args.blocking
        )
        print(f"wrote {out}", file=sys.stderr)
    return 0 if result.passed() else 1


__all__ = [
    "CRITIC_ID",
    "CHECK_NAME",
    "DIM_PENDING",
    "PENDING_SUFFIX",
    "PENDING_DEPENDENCY_FLAG_TYPE",
    "MALFORMED_MARKER",
    "UNRESOLVED_PENDING",
    "SEVERITY_WARNING",
    "SEVERITY_INFO",
    "MARKER_CANDIDATE_RE",
    "PendingMarkerHit",
    "PendingMarkerResult",
    "mask_well_formed_markers",
    "scan_text",
    "check_pending_markers_text",
    "check_pending_markers",
    "write_review_dir",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
