"""Quoted-evidence verifier for critic scoring tables (issue #464).

Fifth member of the deterministic-checks family (alongside
``anvil/lib/render_gate.py``, ``anvil/lib/marp_lint.py``,
``anvil/lib/revise_consistency.py``, ``anvil/lib/scorecard_check.py``,
and ``anvil/lib/numeric_consistency.py``). It enforces the
**quoted-evidence discipline** from the draftwell survey: every
per-dimension score in a critic's ``scoring.md`` must cite verbatim
text from the document under review, so a lazy critic cannot emit
plausible-sounding scores ungrounded in the actual draft (the same
failure class the studio canary hit with VLM critics scoring figures
they had not decoded).

The snippet-side contract lives in ``anvil/lib/snippets/rubric.md``
§"Dimension scoring guidance" rule 1: each dimension's justification
embeds at least one verbatim quote from the reviewed body — wrapped in
double quotes, followed by a human-facing location anchor — and a dim
scored at full weight MAY substitute the by-absence marker phrase
``no instance of <X> found`` (absence of defects has no quotable span).
This module is the deterministic verifier for the quote half of that
rule; anchors are judgment-scope and are NOT validated here.

Deterministic subset (pure stdlib — no LLM, no new deps)
--------------------------------------------------------

1. **Table parsing** — reuses
   ``anvil/lib/critics.py::parse_memo_scoring_table`` on the
   ``| # | Dimension | Weight | Score | Justification |`` row shape.
   Rows with a ``null`` / ``n/a`` / ``-`` score are skipped entirely:
   a critic that does not own a dimension (the partial-scorecard rule
   in ``snippets/critics.md``) owes no evidence for it.

2. **Quoted-span extraction** — text inside straight (``"…"``) or
   curly (``“…”``) double quotes within the justification cell.
   Spans shorter than :data:`MIN_QUOTE_CHARS` characters (after
   normalization) are ignored — trivial / idiomatic quoting ("why
   now", "soft target") is not evidence. The cutoff is a heuristic
   module constant, tuned on canary signal.

3. **Matching** — both the span and the body are normalized (curly →
   straight quotes, em/en dashes and ``--`` / ``---`` hyphen runs
   folded to one canonical dash token, markdown emphasis characters
   ``*`` / ``_`` / backticks stripped, whitespace collapsed) and the
   span must appear as a **case-sensitive substring** of the
   normalized body. LaTeX bodies (``main.tex``) are matched against
   the ``.tex`` source verbatim — reviewers read source, so quotes
   must match source (the symmetric dash fold keeps ``--`` / ``---``
   dash markup in ``.tex`` source self-consistent with quotes typed
   either way).

   **Ellipsis elision** (issue #478) is permitted *inside a span*:
   a span containing ``...`` / ``…`` is split on the elision markers
   and matches when every fragment (each ≥ :data:`MIN_QUOTE_CHARS`
   normalized chars — the per-fragment floor that blocks
   ``"the ... market"``-style trivial stitching) appears verbatim in
   the body **in document order** (advancing-cursor match: fragment N
   must start after fragment N−1 ends) **and** all fragments fall
   within :data:`ELISION_WINDOW_CHARS` normalized characters of the
   first fragment's match start (the anti-stitching proximity window —
   two distant real fragments must not stitch into fabricated
   meaning). Fragment matching is greedy-leftmost (each fragment binds
   to its first in-order occurrence; no backtracking retry — a
   documented v1 simplification). A span that matches the body as a
   plain substring (e.g. it quotes a *literal* ellipsis present in the
   body) passes without fragment splitting; leading/trailing ellipses
   degrade to plain single-fragment matching. Elision handling lives
   in :func:`span_matches_body`, NOT in :func:`normalize` — folding
   ellipses in the normalizer would corrupt body text containing
   literal ellipses.

4. **Per-justification classification** (this ordering is
   load-bearing — it tolerates calibration-suffix quotes from
   ``rubric_overrides`` / artifact-type overlays that legitimately
   quote rubric prose, not body text):

   1. ≥1 extracted span matches the body → **pass**.
   2. ``score == weight`` AND the by-absence marker
      (``no instance of <X> found``) is present → **pass**
      (ceiling-by-absence contract).
   3. ≥1 span extracted but NONE matches the body →
      **major finding**: :data:`FABRICATED_EVIDENCE` — the quote does
      not appear verbatim in the reviewed body.
   4. No spans at all → **minor (advisory) finding**:
      :data:`MISSING_EVIDENCE`.

Where findings flow (issue #464 curation)
-----------------------------------------

**No sidecar is written.** Two consumption modes only:

1. **Write-time self-check** (the memo pilot): the reviewer runs this
   verifier against its staging-dir ``scoring.md`` (via ``--scoring``)
   alongside the existing ``scorecard_check`` invocation. Missing-
   evidence findings → the reviewer adds the quote before the sidecar
   lands; fabricated-evidence findings → hard self-check failure: the
   reviewer re-derives the justification from the actual body. Same
   deterministic-correction posture as the scorecard arithmetic gate.
2. **Standalone post-hoc CLI** over legacy review dirs → advisory
   reporting only — never mutates, never gates.

A ``--write-review`` critic-sibling mode (a critic reviewing critics)
is explicitly OUT of scope — the aggregator is untouched.

CLI entry-point
---------------

``python -m anvil.lib.evidence_check <version_dir> [--scoring <path>]``

Without ``--scoring``, discovers every critic-sibling
``<version_dir>.<critic>/scoring.md`` next to the version dir (the
critic-sibling glob per ``snippets/critics.md``); with ``--scoring``,
checks exactly that one file (the reviewer's staging-dir self-check
path). The body file is auto-detected inside the version dir:
``<slug>.md`` (the #295 slug-echo shape) first, then ``main.tex``
(the pub shape) — the same resolution pattern as
``numeric_consistency._body_path``.

Writes a JSON summary to stdout. Exit codes: ``0`` clean, ``1`` one or
more findings, ``2`` invocation error (missing version dir, body file,
or ``--scoring`` file) — the #462/#338/#337 convention.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from anvil.lib.critics import parse_memo_scoring_table


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHECK_NAME = "evidence_check"
"""Check identifier echoed in JSON payloads."""

MIN_QUOTE_CHARS = 15
"""Minimum normalized length for a quoted span to count as evidence.

Heuristic cutoff that skips trivial / idiomatic quoting ("why now",
"soft target"). Ship-as-constant, tune on canary signal (issue #464
risk note). Doubles as the per-fragment floor for ellipsis-elided
spans (issue #478): each elided fragment must independently clear it.
"""

ELISION_WINDOW_CHARS = 500
"""Proximity window for ellipsis-elided spans (issue #478).

All fragments of an elided span must fall within this many normalized
characters of the first fragment's match start — the anti-stitching
constraint that prevents two distant real fragments from being
stitched into fabricated meaning. Ship-as-constant, tune on canary
signal (the MIN_QUOTE_CHARS posture).
"""

# Finding codes (stable identifiers; consumers grep for these).
FABRICATED_EVIDENCE = "fabricated_evidence"
MISSING_EVIDENCE = "missing_evidence"

# Finding severities. Fabricated evidence is a major finding (the gate
# this module exists for); missing evidence is a minor advisory.
SEVERITY_MAJOR = "major"
SEVERITY_MINOR = "minor"

# Ceiling-by-absence marker: a dim scored at full weight MAY substitute
# "no instance of <X> found" for a quote — absence of defects has no
# quotable span. Tolerant of plural ("no instances of ... found") and
# case; the <X> placeholder is bounded to keep the match same-sentence.
_ABSENCE_MARKER_RE = re.compile(
    r"\bno\s+instances?\s+of\s+[^.;|]{1,120}?\bfound\b",
    re.IGNORECASE,
)

# Quoted spans: straight double quotes or curly double quotes. Spans
# never contain a pipe (justifications live in single table cells) or a
# newline.
_QUOTED_SPAN_RES: Tuple[re.Pattern, ...] = (
    re.compile(r'"([^"\n|]+)"'),
    re.compile("“([^“”\n|]+)”"),
)

# Markdown emphasis characters stripped by normalization.
_EMPHASIS_CHARS_RE = re.compile(r"[*_`]")

_CURLY_FOLD = {
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
}

# Dash variants folded to one canonical token by normalization (issue
# #478): em dash, en dash, and 2-3 hyphen runs (`---` matched before
# `--` via the greedy quantifier — order matters). Symmetric folding
# means verbatim em-dash quotes still pass, `--`-typed quotes match
# `—` bodies, and `--scoring`-style literals stay self-consistent
# (both sides fold identically). Single hyphens are NOT folded —
# compound words ("single-customer") are not dashes.
_DASH_FOLD_RE = re.compile(r"—|–|-{2,3}")
_DASH_CANONICAL = "—"

# Elision markers splitting a quoted span into fragments (issue #478):
# ASCII three-or-more dots or the Unicode horizontal ellipsis. Lives
# in span matching, NOT in normalize() — folding ellipses in the
# normalizer would corrupt body text containing literal ellipses.
_ELISION_MARKER_RE = re.compile(r"\.\.\.+|…")


# ---------------------------------------------------------------------------
# Normalization + extraction
# ---------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Normalize text for span-vs-body matching.

    Folds curly quotes to straight, folds dash variants (``—`` / ``–``
    / ``---`` / ``--``) to one canonical dash token (issue #478),
    strips markdown emphasis characters (``*``, ``_``, backticks),
    collapses all whitespace runs to single spaces, and strips. Case
    is preserved — matching is case-sensitive by contract (a quote is
    verbatim or it is not evidence). Ellipses are deliberately NOT
    folded here — elision is span-side semantics handled in
    :func:`span_matches_body`, and folding it here would corrupt body
    text containing literal ellipses.
    """
    for curly, straight in _CURLY_FOLD.items():
        text = text.replace(curly, straight)
    text = _DASH_FOLD_RE.sub(_DASH_CANONICAL, text)
    text = _EMPHASIS_CHARS_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_quoted_spans(text: str) -> List[str]:
    """Extract candidate evidence spans from a justification cell.

    Returns the raw (un-normalized) inner text of every straight- or
    curly-double-quoted span whose **normalized** length is at least
    :data:`MIN_QUOTE_CHARS`. Shorter spans are dropped entirely — they
    neither satisfy nor violate the evidence rule.
    """
    spans: List[str] = []
    for pattern in _QUOTED_SPAN_RES:
        for m in pattern.finditer(text):
            inner = m.group(1)
            if len(normalize(inner)) >= MIN_QUOTE_CHARS:
                spans.append(inner)
    return spans


def has_absence_marker(text: str) -> bool:
    """``True`` when the justification carries the by-absence marker."""
    return bool(_ABSENCE_MARKER_RE.search(text))


def _elided_fragments_match(
    fragments: List[str], normalized_body: str
) -> bool:
    """In-order, windowed match of an elided span's fragments.

    Every fragment must clear the per-fragment :data:`MIN_QUOTE_CHARS`
    floor, appear in the body in document order (advancing cursor:
    fragment N starts after fragment N−1 ends), and end within
    :data:`ELISION_WINDOW_CHARS` of the first fragment's match start.
    Matching is greedy-leftmost: each fragment binds to its first
    in-order occurrence, with no backtracking retry when a later
    occurrence would have satisfied the window — a documented v1
    simplification (issue #478 curation).
    """
    if any(len(f) < MIN_QUOTE_CHARS for f in fragments):
        return False
    cursor = 0
    first_start: Optional[int] = None
    for fragment in fragments:
        idx = normalized_body.find(fragment, cursor)
        if idx == -1:
            return False
        if first_start is None:
            first_start = idx
        elif idx + len(fragment) > first_start + ELISION_WINDOW_CHARS:
            return False
        cursor = idx + len(fragment)
    return True


def span_matches_body(span: str, normalized_body: str) -> bool:
    """Case-sensitive substring match of a normalized span in the body.

    The caller pre-normalizes the body once (via :func:`normalize`) and
    passes it here for each span.

    Ellipsis elision (issue #478): a span that does not match as a
    plain substring but contains ``...`` / ``…`` markers is split into
    fragments, and matches when every fragment is ≥
    :data:`MIN_QUOTE_CHARS`, appears in the body in document order,
    and falls within :data:`ELISION_WINDOW_CHARS` of the first
    fragment's match start (see :func:`_elided_fragments_match`). The
    plain-substring check runs first, so a quote of a *literal* body
    ellipsis still passes verbatim. Leading/trailing ellipses leave a
    single fragment and degrade to plain single-fragment matching
    (no per-fragment floor beyond the extraction-time cutoff).
    """
    normalized_span = normalize(span)
    if normalized_span in normalized_body:
        return True
    fragments = [
        f.strip() for f in _ELISION_MARKER_RE.split(normalized_span)
    ]
    fragments = [f for f in fragments if f]
    if not fragments or fragments == [normalized_span]:
        return False  # no elision markers — plain match already failed
    if len(fragments) == 1:
        # Leading/trailing ellipsis only: plain single-fragment match.
        return fragments[0] in normalized_body
    return _elided_fragments_match(fragments, normalized_body)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class EvidenceFinding:
    """One quoted-evidence finding against a scoring.md justification."""

    code: str          # fabricated_evidence | missing_evidence
    severity: str      # "major" | "minor"
    dimension: str     # rubric dimension name from the table row
    scoring_path: str  # which scoring.md the row came from
    score: Optional[int]
    weight: int
    spans_extracted: int
    message: str

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "dimension": self.dimension,
            "scoring_path": self.scoring_path,
            "score": self.score,
            "weight": self.weight,
            "spans_extracted": self.spans_extracted,
            "message": self.message,
        }


@dataclass
class EvidenceCheckResult:
    """Outcome of one quoted-evidence pass over ≥0 scoring files."""

    version_dir: str
    body_path: str
    scoring_files: List[str] = field(default_factory=list)
    dimensions_checked: int = 0
    findings: List[EvidenceFinding] = field(default_factory=list)

    def passed(self) -> bool:
        """``True`` when zero findings (major or minor) were emitted."""
        return not self.findings

    def to_json(self) -> dict:
        return {
            "check": CHECK_NAME,
            "version_dir": self.version_dir,
            "body_path": self.body_path,
            "scoring_files": self.scoring_files,
            "dimensions_checked": self.dimensions_checked,
            "findings": [f.to_dict() for f in self.findings],
            "pass": self.passed(),
        }


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_justification(
    *,
    dimension: str,
    score: Optional[int],
    weight: int,
    justification: Optional[str],
    normalized_body: str,
    scoring_path: str = "scoring.md",
) -> Optional[EvidenceFinding]:
    """Classify one scoring row. Returns a finding or ``None`` (pass).

    A ``None`` score (the critic does not own the dim) is always a
    pass — the partial-scorecard rule in ``snippets/critics.md``.
    The classification order is documented in the module docstring and
    is load-bearing: a non-matching calibration-suffix quote alongside
    one matching body quote passes via rule 1.
    """
    if score is None:
        return None
    text = justification or ""
    spans = extract_quoted_spans(text)
    # Rule 1: any matching span → pass.
    if any(span_matches_body(s, normalized_body) for s in spans):
        return None
    # Rule 2: ceiling-by-absence → pass.
    if score == weight and has_absence_marker(text):
        return None
    # Rule 3: spans present but none matches the body → major.
    if spans:
        sample = normalize(spans[0])
        if len(sample) > 60:
            sample = sample[:57] + "..."
        return EvidenceFinding(
            code=FABRICATED_EVIDENCE,
            severity=SEVERITY_MAJOR,
            dimension=dimension,
            scoring_path=scoring_path,
            score=score,
            weight=weight,
            spans_extracted=len(spans),
            message=(
                f"dim {dimension!r} (score {score}/{weight}): justification "
                f"quotes {len(spans)} span(s) but NONE appears verbatim in "
                f"the reviewed body — fabricated evidence. First span: "
                f'"{sample}". Re-derive the justification from the actual '
                f"body text."
            ),
        )
    # Rule 4: no spans at all → minor advisory.
    return EvidenceFinding(
        code=MISSING_EVIDENCE,
        severity=SEVERITY_MINOR,
        dimension=dimension,
        scoring_path=scoring_path,
        score=score,
        weight=weight,
        spans_extracted=0,
        message=(
            f"dim {dimension!r} (score {score}/{weight}): justification "
            f"contains no quoted span (≥{MIN_QUOTE_CHARS} chars) from the "
            f"reviewed body"
            + (
                " and no ceiling by-absence marker"
                if score == weight
                else ""
            )
            + ' — add a verbatim quote with a location anchor, e.g. '
            f'("the quoted span" — §2.1)'
            + (
                f", or the marker phrase 'no instance of <X> found' "
                f"(allowed at full weight)."
                if score == weight
                else "."
            )
        ),
    )


def check_scoring_text(
    scoring_text: str,
    body_text: str,
    *,
    scoring_path: str = "scoring.md",
) -> Tuple[List[EvidenceFinding], int]:
    """Run the quoted-evidence check over one scoring.md's text.

    Pure function of the two texts (no filesystem). Returns
    ``(findings, dimensions_checked)`` where ``dimensions_checked``
    counts the non-null-score rows examined.
    """
    normalized_body = normalize(body_text)
    findings: List[EvidenceFinding] = []
    checked = 0
    for row in parse_memo_scoring_table(scoring_text):
        if row.score is None:
            continue
        checked += 1
        finding = classify_justification(
            dimension=row.dimension,
            score=row.score,
            weight=row.max,
            justification=row.justification,
            normalized_body=normalized_body,
            scoring_path=scoring_path,
        )
        if finding is not None:
            findings.append(finding)
    return findings, checked


# ---------------------------------------------------------------------------
# Filesystem entry points
# ---------------------------------------------------------------------------


def _body_path(version_dir: Path) -> Path:
    """Locate the body file inside a version directory.

    Detection order mirrors ``numeric_consistency._body_path``:
    ``<slug>.md`` (the #295 slug-echo shape — the slug is the parent
    dir name), then ``main.tex`` (the pub shape). Raises
    ``FileNotFoundError`` when neither exists.
    """
    slug_md = version_dir / f"{version_dir.parent.name}.md"
    if slug_md.is_file():
        return slug_md
    main_tex = version_dir / "main.tex"
    if main_tex.is_file():
        return main_tex
    raise FileNotFoundError(
        f"evidence_check: no body file found in {version_dir!s} "
        f"(looked for {slug_md.name!r} per the #295 slug-echo convention, "
        f"then 'main.tex')."
    )


def discover_scoring_files(version_dir: Path) -> List[Path]:
    """Discover critic-sibling ``scoring.md`` files for a version dir.

    Matches ``<version_dir>.<critic>/scoring.md`` siblings (the
    critic-sibling shape per ``snippets/critics.md``), sorted by path.
    Leading-dot staging dirs (``.<name>.tmp/``) never match the glob.
    """
    version_dir = Path(version_dir)
    return sorted(version_dir.parent.glob(f"{version_dir.name}.*/scoring.md"))


def check_version_dir(
    version_dir: Path,
    *,
    scoring: Optional[Path] = None,
) -> EvidenceCheckResult:
    """Run the check for a version directory.

    Without ``scoring``, discovers every critic-sibling ``scoring.md``
    via :func:`discover_scoring_files` (zero siblings is a clean pass —
    advisory posture over legacy dirs). With ``scoring``, checks
    exactly that one file (the reviewer's staging-dir self-check path).

    Raises ``FileNotFoundError`` when the version dir, its body file,
    or an explicitly-passed ``scoring`` file is missing.
    """
    version_dir = Path(version_dir).resolve()
    if not version_dir.is_dir():
        raise FileNotFoundError(
            f"evidence_check: version_dir {version_dir!s} does not exist "
            f"or is not a directory."
        )
    body = _body_path(version_dir)
    body_text = body.read_text(encoding="utf-8")

    if scoring is not None:
        scoring = Path(scoring)
        if not scoring.is_file():
            raise FileNotFoundError(
                f"evidence_check: --scoring file {scoring!s} does not exist."
            )
        scoring_files = [scoring]
    else:
        scoring_files = discover_scoring_files(version_dir)

    result = EvidenceCheckResult(
        version_dir=version_dir.name,
        body_path=body.name,
        scoring_files=[str(p) for p in scoring_files],
    )
    for path in scoring_files:
        findings, checked = check_scoring_text(
            path.read_text(encoding="utf-8"),
            body_text,
            scoring_path=str(path),
        )
        result.findings.extend(findings)
        result.dimensions_checked += checked
    return result


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def _build_cli_parser():
    import argparse

    p = argparse.ArgumentParser(
        prog="python -m anvil.lib.evidence_check",
        description=(
            "Quoted-evidence verifier for critic scoring tables: checks "
            "that each scoring.md justification embeds at least one "
            "verbatim quote from the reviewed body (or the 'no instance "
            "of <X> found' by-absence marker at full weight). Advisory — "
            "reports findings, never mutates, never writes a sidecar."
        ),
    )
    p.add_argument(
        "version_dir",
        help="Path to <thread>.{N}/ containing <thread>.md or main.tex.",
    )
    p.add_argument(
        "--scoring",
        metavar="PATH",
        default=None,
        help=(
            "Check exactly this scoring.md instead of discovering "
            "critic-sibling <version_dir>.*/scoring.md files (the "
            "reviewer's staging-dir self-check path)."
        ),
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Returns the process exit code.

    Exit codes:
    - ``0``: clean pass (zero findings — including zero scoring files).
    - ``1``: one or more findings (major fabricated-evidence or minor
      missing-evidence).
    - ``2``: invocation error (missing version_dir, body file, or
      ``--scoring`` file).
    """
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    try:
        result = check_version_dir(
            Path(args.version_dir),
            scoring=Path(args.scoring) if args.scoring else None,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.to_json(), indent=2))
    return 0 if result.passed() else 1


__all__ = [
    "CHECK_NAME",
    "MIN_QUOTE_CHARS",
    "ELISION_WINDOW_CHARS",
    "FABRICATED_EVIDENCE",
    "MISSING_EVIDENCE",
    "SEVERITY_MAJOR",
    "SEVERITY_MINOR",
    "EvidenceFinding",
    "EvidenceCheckResult",
    "normalize",
    "extract_quoted_spans",
    "has_absence_marker",
    "span_matches_body",
    "classify_justification",
    "check_scoring_text",
    "discover_scoring_files",
    "check_version_dir",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
