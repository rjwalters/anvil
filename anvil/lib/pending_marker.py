"""Deterministic pending-measurement placeholder gate (issue #841).

Fifth member of the deterministic-checks family (alongside
``anvil/lib/numeric_consistency.py``, ``anvil/lib/render_gate.py``,
``anvil/lib/marp_lint.py``, and ``anvil/lib/revise_consistency.py``).

The problem
-----------

Drafting an artifact whose load-bearing numbers do not yet exist
(measurement pending, benchmark queued, quote not returned) is a common
situation. Without a supported convention, correct behavior depends on
ad-hoc per-thread prompt discipline hand-written into ``BRIEF.md``
instead of being a first-class skill feature — and critics have no way
to distinguish "number missing because pending" from "number missing
because the drafter was sloppy (or fabricated a value to avoid the
awkward gap)". A deliberately-incomplete draft scores as defective when
it shouldn't, or worse, a drafter fabricates a plausible-looking number
to paper over the gap.

The convention
---------------

A drafter marks a genuinely-outstanding value with a bracketed
placeholder naming its source::

    The model reaches [PENDING benchmark-run-2024-11] accuracy on the
    held-out set.

    Component cost is [PENDING: vendor-quote-acme] per unit at the
    quoted MOQ.

Syntax (see ``anvil/lib/snippets/pending_marker.md`` for the full
convention document): ``[PENDING <source>]`` or ``[PENDING: <source>]``
— the literal, case-sensitive keyword ``PENDING`` immediately after the
opening bracket, then a colon and/or whitespace separator, then a
non-empty ``<source>`` label naming what's pending (a benchmark run id,
a vendor name, "Q3 earnings call", etc.), then the closing bracket. The
uppercase keyword is deliberate — it mirrors the TODO/FIXME convention
so a genuine marker is visually and mechanically unambiguous, and it
means ordinary prose that merely uses the word "pending" (e.g. "results
are pending") is never mistaken for a marker. A near-miss with no
source label (``[PENDING]``, ``[PENDING ]``) is NOT a well-formed
marker and is silently ignored by this detector — it reads as
malformed bracketed text, not as a recognized placeholder, so it gets
neither the "known-incomplete, no penalty" treatment nor the blocking
gate. (The convention document recommends against ever writing a
source-less marker for exactly this reason: it degrades to "an
unexplained bracket" for both a human reader and this tool.)

Deterministic detection (pure regex — no LLM, no new deps)
------------------------------------------------------------

1. **Marker extraction**: every well-formed ``[PENDING <source>]`` /
   ``[PENDING: <source>]`` span in the body, with its line number and
   the extracted ``<source>`` label (whitespace-trimmed).
2. **Masking**: fenced code blocks, inline code spans, and (for
   ``.tex`` bodies) LaTeX comments are masked out before extraction —
   the same discipline as ``numeric_consistency.py`` — so a
   documentation passage that quotes the marker syntax in backticks is
   never mistaken for a live, unresolved marker.
3. **Resolution**: a marker is "unresolved" simply by being present in
   the body. There is no separate resolved/unresolved flag to
   maintain — resolving a pending value means replacing the marker text
   with the real value, at which point the next detector pass finds
   nothing.

Severity wiring: judgment-free, deterministic gate
----------------------------------------------------

Unlike ``numeric_consistency.py`` (which validates *arithmetic*
consistency — a judgment call with a tolerance policy and an LLM
fallback for the nuanced cases), whether a well-formed pending marker
is still present in the body is a **binary, deterministic fact with no
judgment call**. This module therefore emits ``CriticalFlag``s directly
(``to_review(blocking=True)``) rather than staying advisory-only and
routing through an LLM's own critical-flag judgment — the same posture
as ``anvil/skills/paper/lib/artifact_verify.py`` (issue #663), which
also gates on a deterministic pass/fail rather than LLM discretion.
This is the direct fix for the ad-hoc-prompt-discipline problem this
issue exists to close: the gate does not depend on a reviewer
*noticing* the marker text and deciding to write a flag by hand.

Every marker also emits an advisory ``Finding`` at the lowest schema
severity (``"nit"``) regardless of ``blocking`` — a "known-incomplete,
outstanding dependency" note, NOT a defect. Consumers (the paper skill
first; see ``anvil/skills/paper/commands/paper-review.md`` step 4g and
``anvil/skills/paper/rubric.md``) are expected to surface these in
``verdict.md``/``findings.md`` as outstanding dependencies and to
**not** deduct dimension score for a well-formed marker's presence —
the critical flag alone communicates "not done yet"; double-penalizing
via both a blocked verdict AND a lower dimension score punishes the
honest disclosure the convention exists to encourage.

Optional `BRIEF.md` frontmatter: `pending_sources`
-----------------------------------------------------

A thread MAY declare the pending sources it expects to resolve over
its lifetime in `<thread>/BRIEF.md` YAML frontmatter::

    ---
    pending_sources:
      - benchmark-run-2024-11
      - vendor-quote-acme
    ---

:func:`load_expected_pending_sources` reads this (pure-stdlib-first,
same posture as ``anvil/lib/project_detect.py``'s frontmatter reader:
``yaml.safe_load`` when pyyaml is on the path, a minimal hand-rolled
list parser otherwise). This is purely a **reporting aid** — declaring
a source here has NO effect on gating (an undeclared marker still
blocks; a declared-but-never-written source is not itself a defect).
:meth:`PendingMarkerResult.resolved_sources` is the set difference
between the declared list and the sources still found unresolved in
the body, letting a critic report "3 of 5 declared pending sources
resolved; 2 outstanding: vendor-quote-acme, benchmark-run-2024-11" —
the visibility half of the acceptance criteria.

Sidecar + discovery contract
-----------------------------

``write_review_dir`` writes ``<thread>.{N}.pending/_review.json`` via
``anvil/lib/sidecar.py::staged_sidecar`` (crash-safe atomic rename).
The ``.pending`` tag is a single segment, so
``anvil/lib/critics.py::discover_critics`` picks the sidecar up with
**no aggregator change** — same coordination shape as ``.numeric/``
(#462) and ``.hyperlinks/`` (#335). Because the check is deterministic
and cheaply re-runnable, an existing ``<version_dir>.pending/`` sidecar
from a prior pass (e.g. an advisory review-time run) is removed and
regenerated by a later pass (e.g. a blocking audit-time run) — the
same deterministic-regeneration carve-out ``numeric_consistency.py``
documents for its own sidecar.

CLI entry-point
----------------

``python -m anvil.lib.pending_marker <version_dir> [--write-review]
[--blocking] [--body PATH]``

Writes a JSON summary to stdout. Exit codes: ``0`` no unresolved
markers, ``1`` unresolved markers present, ``2`` invocation error. The
body file is auto-detected: ``<slug>.md`` (the #295 slug-echo memo
shape) first, then ``main.tex`` (the paper shape). ``--body PATH``
overrides discovery for adopted-in-place legacy threads.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from anvil.lib.review_schema import (
    CriticalFlag,
    Finding,
    Kind,
    Review,
    Score,
)
from anvil.lib.sidecar import cleanup_one_staging, staged_sidecar

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CRITIC_ID = "pending"
"""Stable identifier for this critic in ``_review.json.critic_id``."""

CHECK_NAME = "pending_marker"
"""Check identifier echoed in JSON payloads."""

DIM_PENDING = "pending_marker"
"""Dimension name surfaced on every emitted Finding."""

PENDING_SUFFIX = "pending"
"""Sidecar dir tag: ``<thread>.{N}.pending/``. Single segment so
``critics.discover_critics`` picks it up with no aggregator change."""

CRITICAL_PENDING_MARKER = "critical_pending_marker"
"""Critical-flag ``type`` prefix (only emitted under ``blocking=True``).
The full type is ``critical_pending_marker:<finding-code>``."""

UNRESOLVED_PENDING_MARKER = "unresolved_pending_marker"
"""The sole finding code this module emits."""

BRIEF_FILENAME = "BRIEF.md"
"""Thread-root brief filename read for the optional ``pending_sources``
frontmatter key."""

_FRONTMATTER_DELIM = "---"


# ---------------------------------------------------------------------------
# Masking (code fences, inline code, LaTeX comments)
# ---------------------------------------------------------------------------

_MASK_PATTERNS: Tuple[re.Pattern, ...] = (
    # Fenced code blocks (``` ... ``` or ~~~ ... ~~~), multi-line.
    re.compile(r"(```|~~~).*?\1", re.DOTALL),
    # Inline code spans.
    re.compile(r"`[^`\n]*`"),
)

# LaTeX-only: unescaped % starts a comment.
_LATEX_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")


def _mask_text(text: str, *, latex: bool = False) -> str:
    """Blank out non-prose regions while preserving offsets/line numbers."""

    def blank(m: "re.Match[str]") -> str:
        return "".join(c if c == "\n" else " " for c in m.group(0))

    masked = text
    for pattern in _MASK_PATTERNS:
        masked = pattern.sub(blank, masked)
    if latex:
        masked = _LATEX_COMMENT_RE.sub(blank, masked)
    return masked


# ---------------------------------------------------------------------------
# Marker extraction
# ---------------------------------------------------------------------------

# Well-formed marker: literal, case-sensitive "PENDING" immediately after
# the opening bracket, then either "<colon><optional ws>" or "<required
# ws>" as separator, then a non-empty source label, then the closing
# bracket. A bare "[PENDING]" or "[PENDING ]" (no source content) does
# NOT match — deliberately treated as malformed, not as a marker.
_PENDING_MARKER_RE = re.compile(
    r"\[PENDING(?:\s*:\s*|\s+)(?P<source>[^\]\n]+?)\s*\]"
)


def _line_of(offset: int, text: str) -> int:
    """1-based line number of ``offset`` in ``text``."""
    return text.count("\n", 0, offset) + 1


@dataclass(frozen=True)
class PendingMarker:
    """One well-formed ``[PENDING <source>]`` marker found in the body."""

    source: str
    raw: str
    line: int
    start: int
    end: int

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "raw": self.raw,
            "line": self.line,
        }


def find_pending_markers(text: str, *, latex: bool = False) -> List[PendingMarker]:
    """Extract every well-formed pending marker from ``text``.

    Pure function of the text (no filesystem). Set ``latex=True`` for
    ``.tex`` bodies (enables the LaTeX ``%``-comment mask).
    """
    masked = _mask_text(text, latex=latex)
    markers: List[PendingMarker] = []
    for m in _PENDING_MARKER_RE.finditer(masked):
        source = m.group("source").strip()
        if not source:
            continue
        markers.append(
            PendingMarker(
                source=source,
                raw=m.group(0).strip(),
                line=_line_of(m.start(), masked),
                start=m.start(),
                end=m.end(),
            )
        )
    return markers


def emit_pending_marker(source: str, *, colon: bool = False) -> str:
    """Render a well-formed marker string for a given source label.

    A small emitter helper (the issue's "lib-level helper for emitting
    and detecting it" acceptance criterion) so drafters/tooling can
    generate a marker programmatically instead of hand-typing the
    syntax. ``colon=True`` renders ``[PENDING: <source>]``; the default
    renders ``[PENDING <source>]``. Both are well-formed and detected
    identically by :func:`find_pending_markers`.
    """
    source = source.strip()
    if not source:
        raise ValueError("emit_pending_marker: source must be non-empty")
    sep = ": " if colon else " "
    return f"[PENDING{sep}{source}]"


# ---------------------------------------------------------------------------
# Optional BRIEF.md frontmatter: pending_sources
# ---------------------------------------------------------------------------


def _extract_frontmatter(text: str) -> Optional[dict]:
    """Extract YAML frontmatter from ``text`` as a dict, or ``None``.

    Pure-stdlib-first: tries ``yaml.safe_load`` when pyyaml is on the
    path, falls back to a minimal hand-rolled list parser (handles only
    a top-level ``pending_sources:`` key followed by ``- <item>``
    lines) when pyyaml is absent. Mirrors
    ``anvil/lib/project_detect.py::_extract_frontmatter``'s posture.
    """
    lines = text.splitlines()
    if lines and lines[0].startswith("﻿"):
        lines[0] = lines[0][1:]
    first_idx = 0
    while first_idx < len(lines) and lines[first_idx].strip() == "":
        first_idx += 1
    if first_idx >= len(lines) or lines[first_idx].strip() != _FRONTMATTER_DELIM:
        return None
    close_idx = None
    for i in range(first_idx + 1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            close_idx = i
            break
    if close_idx is None:
        return None
    yaml_text = "\n".join(lines[first_idx + 1 : close_idx])
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(yaml_text)
    except Exception:
        parsed = _hand_parse_pending_sources(yaml_text)
    if not isinstance(parsed, dict):
        return None
    return parsed


def _hand_parse_pending_sources(yaml_text: str) -> Optional[dict]:
    """Minimal hand-rolled fallback: recognizes only a top-level
    ``pending_sources:`` key followed by ``- <item>`` list lines.
    """
    items: List[str] = []
    in_key = False
    for raw_line in yaml_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("pending_sources:"):
            in_key = True
            continue
        if in_key and re.match(r"^\s*-\s+", line):
            item = re.sub(r"^\s*-\s+", "", line).strip().strip("'\"")
            if item:
                items.append(item)
            continue
        if in_key and re.match(r"^[A-Za-z_]+:", line):
            in_key = False
    if items:
        return {"pending_sources": items}
    return None


def load_expected_pending_sources(thread_dir: Path) -> List[str]:
    """Read the optional ``pending_sources`` frontmatter list from
    ``<thread_dir>/BRIEF.md``.

    Returns ``[]`` when the BRIEF is absent, has no frontmatter, or has
    no (or a malformed) ``pending_sources`` key — tolerant by design,
    since this is a reporting aid, not a gating input.
    """
    brief = Path(thread_dir) / BRIEF_FILENAME
    if not brief.is_file():
        return []
    try:
        text = brief.read_text(encoding="utf-8")
    except OSError:
        return []
    fm = _extract_frontmatter(text)
    if fm is None:
        return []
    raw = fm.get("pending_sources")
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class PendingMarkerResult:
    """Outcome of one ``check_pending_markers`` pass."""

    version_dir: str
    body_path: str
    markers: List[PendingMarker] = field(default_factory=list)
    expected_sources: List[str] = field(default_factory=list)

    @property
    def outstanding_sources(self) -> List[str]:
        """Unique source labels still present in the body, in first-seen order."""
        seen: List[str] = []
        for m in self.markers:
            if m.source not in seen:
                seen.append(m.source)
        return seen

    @property
    def resolved_sources(self) -> List[str]:
        """Declared ``expected_sources`` no longer present as a marker.

        Purely observational (reporting aid) — has no bearing on
        ``passed()``.
        """
        outstanding = set(self.outstanding_sources)
        return [s for s in self.expected_sources if s not in outstanding]

    def passed(self) -> bool:
        """``True`` when no unresolved markers remain."""
        return not self.markers

    def to_json(self) -> dict:
        return {
            "check": CHECK_NAME,
            "version_dir": self.version_dir,
            "body_path": self.body_path,
            "markers": [m.to_dict() for m in self.markers],
            "outstanding_sources": self.outstanding_sources,
            "expected_sources": self.expected_sources,
            "resolved_sources": self.resolved_sources,
            "pass": self.passed(),
        }

    def to_critical_flags(self) -> List[CriticalFlag]:
        """One ``CriticalFlag`` summarizing every unresolved marker.

        Only meaningful under ``blocking=True``. Empty when no markers
        are present.
        """
        if not self.markers:
            return []
        sources = ", ".join(self.outstanding_sources)
        sample = "; ".join(m.raw for m in self.markers[:3])
        more = f" (+{len(self.markers) - 3} more)" if len(self.markers) > 3 else ""
        return [
            CriticalFlag(
                type=f"{CRITICAL_PENDING_MARKER}:{UNRESOLVED_PENDING_MARKER}",
                justification=(
                    f"{len(self.markers)} unresolved pending marker(s) "
                    f"remain in the body (outstanding source(s): {sources}): "
                    f"{sample}{more}. This is an honestly-declared "
                    f"known-incomplete value, not a defect — but the "
                    f"artifact cannot reach READY/AUDITED until every "
                    f"marker is replaced with its real value."
                ),
                evidence_span=f"{self.body_path}:L{self.markers[0].line}",
            )
        ]

    def to_review(
        self,
        *,
        version_dir: str,
        critic_id: str = CRITIC_ID,
        blocking: bool = False,
    ) -> Review:
        """Build a typed ``Review`` (``kind=Kind.TOOL_EVIDENCE``).

        Every marker emits an advisory ``Finding`` at schema severity
        ``"nit"`` (known-incomplete, not a defect) regardless of
        ``blocking``. ``blocking=True`` additionally emits one
        ``CriticalFlag`` (via :meth:`to_critical_flags`) that forces
        ``Verdict.BLOCK`` through ``anvil/lib/critics.py::compute_verdict``.
        """
        scores = [
            Score(
                dimension=CHECK_NAME,
                score=None,
                max=1,
                justification=(
                    "pending-marker detection is a deterministic "
                    "placeholder-presence check; owns no rubric dim."
                ),
            )
        ]
        findings: List[Finding] = []
        for m in self.markers:
            findings.append(
                Finding(
                    severity="nit",
                    dimension=DIM_PENDING,
                    evidence_span=f"{self.body_path}:L{m.line}",
                    rationale=(
                        f"Outstanding pending marker {m.raw!r} — declared "
                        f"as known-incomplete (source: {m.source!r}), not "
                        f"a defect. No dimension score penalty; blocks "
                        f"advancement to READY/AUDITED until resolved."
                    ),
                    suggested_fix=(
                        f"Resolve the pending source {m.source!r} and "
                        f"replace the marker with the real value, or "
                        f"confirm the value is still genuinely pending "
                        f"and leave the marker in place for a later pass."
                    ),
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
# Filesystem entry point
# ---------------------------------------------------------------------------


def _body_path(version_dir: Path, *, body: Optional[Path] = None) -> Path:
    """Locate the body file inside a version directory.

    Detection order: ``<slug>.md`` (the #295 slug-echo shape), then
    ``main.tex`` (the paper shape). Mirrors
    ``anvil/lib/numeric_consistency.py::_body_path``.
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

    Mirrors ``anvil/lib/numeric_consistency.py::_record_body_path``.
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


def check_text(text: str, *, latex: bool = False) -> List[PendingMarker]:
    """Run the pending-marker check over body text (pure function)."""
    return find_pending_markers(text, latex=latex)


def check_pending_markers(
    version_dir: Path,
    *,
    body: Optional[Path] = None,
    expected_sources: Optional[List[str]] = None,
) -> PendingMarkerResult:
    """Run the check against a version directory's body file.

    ``expected_sources`` overrides the declared list (normally sourced
    from :func:`load_expected_pending_sources` against the thread root,
    i.e. ``version_dir.parent``); when omitted, the thread root's
    ``BRIEF.md`` is consulted automatically.
    """
    version_dir = Path(version_dir).resolve()
    if not version_dir.is_dir():
        raise FileNotFoundError(
            f"pending_marker: version_dir {version_dir!s} does not exist "
            f"or is not a directory."
        )
    body_file = _body_path(version_dir, body=body)
    text = body_file.read_text(encoding="utf-8")
    markers = find_pending_markers(text, latex=body_file.suffix == ".tex")
    if expected_sources is None:
        expected_sources = load_expected_pending_sources(version_dir.parent)
    return PendingMarkerResult(
        version_dir=version_dir.name,
        body_path=_record_body_path(version_dir, body_file),
        markers=markers,
        expected_sources=expected_sources,
    )


def write_review_dir(
    version_dir: Path,
    result: PendingMarkerResult,
    *,
    critic_id: str = CRITIC_ID,
    blocking: bool = False,
) -> Path:
    """Write ``<version_dir>.pending/_review.json`` for auto-discovery.

    Uses ``staged_sidecar`` (issue #350) so the sidecar only ever exists
    in complete form. Because this detector is deterministic and
    cheaply re-runnable, an existing ``<version_dir>.pending/`` from a
    prior run (e.g. an advisory review-time pass) is removed and
    regenerated (the same deterministic-regeneration carve-out
    ``numeric_consistency.write_review_dir`` documents) — a later
    blocking audit-time pass supersedes an earlier advisory pass.
    Returns the path to the written ``_review.json``.
    """
    version_dir = Path(version_dir)
    final = version_dir.parent / f"{version_dir.name}.{PENDING_SUFFIX}"
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
            "Deterministic pending-measurement placeholder gate: detects "
            "well-formed [PENDING <source>] markers in a version "
            "directory's body file. Advisory findings always emit; "
            "--blocking additionally emits a CriticalFlag when any "
            "marker remains, forcing Verdict.BLOCK."
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
            "Emit a CriticalFlag when unresolved markers remain (forces "
            "Verdict.BLOCK through compute_verdict). Use at the terminal "
            "gate before READY/AUDITED."
        ),
    )
    p.add_argument(
        "--body",
        metavar="PATH",
        default=None,
        help=(
            "Override body-file discovery (e.g. for adopted-in-place "
            "legacy threads whose entry point isn't <slug>.md/main.tex)."
        ),
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Returns the process exit code.

    Exit codes: ``0`` no unresolved markers, ``1`` unresolved markers
    present, ``2`` invocation error.
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
    "CRITICAL_PENDING_MARKER",
    "UNRESOLVED_PENDING_MARKER",
    "BRIEF_FILENAME",
    "PendingMarker",
    "PendingMarkerResult",
    "find_pending_markers",
    "emit_pending_marker",
    "load_expected_pending_sources",
    "check_text",
    "check_pending_markers",
    "write_review_dir",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
