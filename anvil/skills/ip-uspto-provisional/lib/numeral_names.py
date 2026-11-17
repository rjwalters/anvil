"""One-name-per-reference-numeral check for ``anvil:ip-uspto-provisional`` (issue #1500).

The ``ip-uspto-provisional-audit`` Check 3 prose already requires that a
reference numeral mean the same component everywhere ("``12`` cannot mean
'input port' in spec and 'housing' in fig-2"), but as prose for an LLM
auditor a stale element name — especially one wrapped across source lines,
so a one-line search for it finds nothing — is caught only by luck. Two
successive canary audit cycles returned NOT READY for exactly that class of
defect (issue #1500). This module is the deterministic pre-flight/audit
sibling: it collects, for every reference numeral, the element name used
with it in the spec (brief description of the drawings, detailed
description, any numeral index) and in the drawing stub descriptions, and
reports numerals carrying more than one name — with each differing name,
its ``\\anvilpara`` paragraph number, and its section.

Design contract (settled at #1500 curation; do NOT re-litigate)
--------------------------------------------------------------

- **Pure stdlib.** No new Python deps (CLAUDE.md "Add Python deps only when
  subprocess won't do").
- **Whitespace-normalised matching.** LaTeX comments (``%`` to end of line,
  which also elides the newline — the standard continuation idiom) are
  stripped and every run of whitespace collapsed to one space BEFORE any
  matching, so an element name split across two source lines is still seen
  as one name (the exact defect that cost the canary an audit cycle).
- **Heuristic name extraction, advisory by default.** The capture is a
  walk-back from the numeral to the previous segment boundary (punctuation)
  or determiner / preposition / conjunction / predicate word, capped at ~4
  words, lowercased, articles stripped. It is deliberately conservative: a
  legitimate short form ("bridge 10" vs "sense bridge 10") and a shared
  head noun with a differing modifier ("span trim resistor" vs "single
  trim-once span resistor") must NOT block, so two names are inconsistent
  only when neither is a token-suffix of the other AND their head nouns
  differ (singular/plural-tolerant). Consumers wire this in as ``minor``
  advisory in the pre-flight (it never gates pass/fail) and as candidate
  findings the auditor confirms in the audit — a confirmed rename mismatch
  keeps Check 3's existing ``blocker`` severity. NLP/semantic synonym
  matching is explicitly out of scope: a renamed-but-synonymous element is
  reported and the auditor decides.
- **Skill-local first.** Lives in ``ip-uspto-provisional/lib/`` (the
  consumer skill). Promote to ``anvil/lib/`` only if a second skill
  consumes it (the wait-for-second-consumer lib-extraction rule).

The skill directory name is hyphenated (``ip-uspto-provisional``), so this
package is NOT importable via a dotted ``python -m`` path. Invoke by
direct file path (the ip-uspto ``lib/`` precedent):

    python3 anvil/skills/ip-uspto-provisional/lib/numeral_names.py <thread>.{N}
    python3 anvil/skills/ip-uspto-provisional/lib/numeral_names.py <thread>.{N} --json

Exit codes: ``0`` = every numeral carries one consistent name; ``1`` = at
least one numeral carries more than one name; ``2`` = usage/IO error
(e.g. the version dir has no ``spec.tex``). Findings are reported with
paragraph numbers and the differing names (acceptance criterion 3 of
issue #1500); the scripts only report — they never fix (auto-fix is out
of scope).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MAX_NAME_WORDS = 4
"""Longest noun phrase captured around a numeral (curator cap: ~4 words)."""

SENTINEL = "\x00"
"""Segment-boundary token emitted where punctuation (or a digit) separated
words in the source. A name never crosses one: "PTAT current source (44),
ratio resistor (12)" must not smear ``44``'s clause onto ``12``."""

REFNUM_PLACEHOLDER_RE = re.compile(r"\x01(\d+)\x01")
"""Reference-numeral macro in ``spec.tex``, stashed as ``\\x01<N>\\x01`` by
:func:`clean_spec_text` (digit interiors only, so the ``\\refnum{??}``
placeholder shape never becomes a marker — the render-gate owns
placeholders)."""

PARA_MARK_RE = re.compile(r"\x02")
"""``\\anvilpara{`` stashed as ``\\x02`` by :func:`clean_spec_text`; each
occurrence increments the ``[000N]`` paragraph counter."""

SECTION_MARK_RE = re.compile(r"\x03([a-z-]+)\x03")
"""Section heading macro stashed as ``\\x03<id>\\x03`` by
:func:`clean_spec_text` (``id`` from :data:`SECTION_NAMES`)."""

DRAWING_NUMERAL_RE = re.compile(r"(?<![\w.\-/])(\d{1,4})(?![\w.\-/])")
"""Bare or parenthesised numeral in a drawing stub description. The
lookarounds exclude decimals (``4.2``, ``0.5``), ranges (``2-4``) and
version-y dotted forms; a bare ``FIG. 1`` heading numeral still matches
but sits at a segment start with a dash after it, so it captures no name
and is skipped."""

ANVILPARA_RE = re.compile(r"\\anvilpara\s*\{")
SECTION_RE = re.compile(
    r"\\(fieldoftheinvention|background|summary|briefdescriptionofdrawings|"
    r"detaileddescription)\b"
)
SECTION_NAMES = {
    "fieldoftheinvention": "field",
    "background": "background",
    "summary": "summary",
    "briefdescriptionofdrawings": "brief-description-of-drawings",
    "detaileddescription": "detailed-description",
}

FIG_HEADING_RE = re.compile(r"^##\s+FIG[^\n]*", re.MULTILINE)
"""Drawing-stub figure heading (``## FIG. 2 — Split-path excitation network``)
in the RAW stub text; each heading starts a per-figure scan section so a
numeral's ``figure`` label is the short heading, never the whole file."""

ARTICLES = {"a", "an", "the", "said"}
"""Articles and patentese article-equivalents — always stripped."""

DETERMINERS = ARTICLES | {
    "same", "each", "every", "this", "that", "these", "those", "such",
    "its", "their", "his", "her", "one", "two", "three", "four", "five",
    "first", "second", "third", "fourth", "fifth", "both", "all", "any",
    "some", "no", "another", "other", "respective", "corresponding",
    "particular", "preferred", "single", "multiple", "several", "certain",
    "given", "whose", "which", "where", "when",
}

PREPOSITIONS = {
    "of", "in", "on", "at", "by", "with", "from", "into", "onto", "to",
    "as", "than", "between", "among", "amongst", "through", "across",
    "against", "during", "for", "per", "via", "within", "without", "over",
    "under", "about", "around", "before", "after", "near", "upon", "toward",
    "towards", "along", "behind", "below", "above", "beside", "despite",
    "except", "inside", "outside", "throughout",
}

CONJUNCTIONS = {
    "and", "or", "nor", "but", "while", "whereas", "plus", "because",
    "since", "although", "though", "yet", "so",
}

PREDICATES = {
    "is", "are", "was", "were", "be", "been", "being", "am",
    "has", "have", "had", "having",
    "comprises", "comprise", "comprised", "comprising",
    "includes", "include", "included", "including",
    "contains", "contain", "contained", "containing",
    "forms", "form", "formed", "forming",
    "selects", "select", "selected", "selecting",
    "choose", "chooses", "chosen", "choosing",
    "adjust", "adjusts", "adjusted", "adjusting",
    "tune", "tunes", "tuned", "tuning",
    "varies", "vary", "varied", "varying",
    "drives", "drive", "driven", "driving",
    "feeds", "feed", "fed", "feeding",
    "sums", "summed",
    "supplies", "supply", "supplied", "supplying",
    "produces", "produce", "produced", "producing",
    "tracks", "track", "tracked",
    "place", "places", "placed",
    "locate", "locates", "located",
    "fabricate", "fabricates", "fabricated",
    "then", "also", "only", "thereby", "therein", "herein",
    "shown", "show", "shows", "referring", "refer", "refers", "referred",
    "see", "seen",
    "call", "calls", "called", "calling",
    "term", "terms", "termed",
    "name", "names", "named",
    "denote", "denotes", "denoted", "denoting",
    "mean", "means", "meant",
    "use", "uses", "used", "using",
    "make", "makes", "made", "making",
    "give", "gives", "given", "giving",
    "take", "takes", "taken", "taking",
    "apply", "applies", "applied",
    "hold", "holds", "held",
    "keep", "keeps", "kept", "keeping",
    "remain", "remains", "remained",
    "begin", "begins", "beginning", "end", "ends", "ended",
}
"""Predicate/function words that terminate a noun-phrase walk in either
direction. Deliberately EXCLUDES words that are nouns inside real element
names — notably ``trim`` / ``span`` ("span trim resistor"), ``sum`` /
``summing`` ("summing node"), ``reference``, ``divider``."""


BOUNDARY_WORDS = DETERMINERS | PREPOSITIONS | CONJUNCTIONS | PREDICATES


def strip_latex_comments(text: str) -> str:
    """Strip ``%``-to-end-of-line comments, honouring ``\\%`` escapes.

    A comment at end of line also elides the newline (the standard LaTeX
    continuation idiom), so ``proportional-to-absolute-%`` +
    ``temperature (PTAT) leg`` re-joins into one name — the whitespace
    contract that makes a name split across source lines findable.
    """
    return re.sub(r"(?<!\\)%[^\n]*\n?", "", text)


def normalize_whitespace(text: str) -> str:
    """Collapse every run of whitespace (including newlines) to one space."""
    return re.sub(r"\s+", " ", text)


def clean_spec_text(spec_tex: str) -> str:
    """Comment-strip, whitespace-normalise, and de-macro ``spec.tex`` text.

    ``\\refnum{N}`` occurrences are stashed as ``\\x01N\\x01`` markers so the
    macro de-stripping below cannot erase them. Inline math (``$...$``) and
    remaining backslash macros are replaced with spaces so they cannot leak
    tokens into a captured name; the ``\\-`` discretionary hyphen becomes a
    plain hyphen.
    """
    text = strip_latex_comments(spec_tex)
    text = normalize_whitespace(text)
    text = text.replace("\\-", "-")
    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(
        r"\\refnum\s*\{\s*(\d+)\s*\}",
        lambda m: f" \x01{m.group(1)}\x01 ",
        text,
    )
    text = re.sub(r"\\anvilpara\s*\{", " \x02 ", text)
    text = re.sub(
        SECTION_RE,
        lambda m: f" \x03{SECTION_NAMES[m.group(1)]}\x03 ",
        text,
    )
    text = re.sub(r"\\[A-Za-z]+", " ", text)
    text = re.sub(r"\\[^A-Za-z\s]", " ", text)
    return text


def clean_prose_text(text: str) -> str:
    """Whitespace-normalise a drawing-stub markdown body.

    Parenthesised reference numerals — the stub idiom
    (``sense bridge (10)``) — are unwrapped to bare numerals so the
    surrounding parentheses cannot fence the capture off on both sides.
    """
    text = normalize_whitespace(text)
    return re.sub(r"\((\d{1,4})\)", r" \1 ", text)


def _tokenize(text: str) -> list[str]:
    """Segment-aware word tokens of ``text``.

    Punctuation and digit runs become :data:`SENTINEL` tokens (so a
    captured name never crosses a clause boundary), hyphenated compounds
    stay whole (``half-bridge`` is one token), and all other whitespace
    separates words — which is why a name wrapped across source lines
    survives as one token run.
    """
    stripped = re.sub(r"[0-9]+", " ", text)
    stripped = re.sub(r"\x03[a-z-]+\x03", " ", stripped)
    stripped = stripped.replace("\x01", f" {SENTINEL} ")
    stripped = stripped.replace("\x02", " ")
    stripped = re.sub(r"[^\w\s\-]", f" {SENTINEL} ", stripped)
    stripped = re.sub(r"(?<![\w])-(?![\w])", f" {SENTINEL} ", stripped)
    return stripped.split()


def _heads_equal(head_a: str, head_b: str) -> bool:
    """Plural-tolerant head-noun equality (``sources``/``source`` are equal)."""
    if head_a == head_b:
        return True
    for a, b in ((head_a, head_b), (head_b, head_a)):
        if a.endswith("es") and a[:-2] == b:
            return True
        if a.endswith("s") and a[:-1] == b:
            return True
    return False


def names_consistent(tokens_a: list[str], tokens_b: list[str]) -> bool:
    """Heuristic consistency relation between two captured names.

    Two names are inconsistent — the only case reported — when neither
    token list is a suffix of the other AND their head nouns differ
    (singular/plural-tolerant). This keeps a legitimate short form
    ("bridge 10" vs "sense bridge 10") and a differing modifier on a
    shared head ("span trim resistor" vs "single trim-once span
    resistor") from false-blocking, while a genuine rename
    ("sense bridge" vs "input port") still lands.
    """
    if tokens_a == tokens_b:
        return True
    short, long_ = sorted((tokens_a, tokens_b), key=len)
    if long_[-len(short):] == short:
        return True
    return _heads_equal(tokens_a[-1], tokens_b[-1])


def capture_noun_phrase(tokens_before: list[str]) -> list[str]:
    """Walk back from a numeral, capturing the preceding noun phrase.

    Stops at a segment sentinel (punctuation), a determiner / preposition
    / conjunction / predicate word, or the ~4-word cap. Returns ``[]``
    when there is no name evidence at that occurrence (the walk hits a
    boundary immediately).
    """
    captured: list[str] = []
    for token in reversed(tokens_before):
        if token == SENTINEL:
            break
        low = token.lower()
        if low in BOUNDARY_WORDS:
            break
        captured.append(low)
        if len(captured) >= MAX_NAME_WORDS:
            break
    captured.reverse()
    return captured


def capture_forward_phrase(tokens_after: list[str]) -> list[str]:
    """Capture the noun phrase AFTER a numeral that starts its segment.

    This is the numeral-index shape ("``10 --- sense bridge``"): the
    numeral has nothing before it in its segment, so the name sits after
    it — possibly separated from the numeral by a dash, so leading
    segment sentinels are skipped before the walk. The walk stops at the
    same boundary classes and the same cap. Ordinary prose occurrences —
    which have a before-capture — are never read this way.
    """
    tokens = list(tokens_after)
    while tokens and tokens[0] == SENTINEL:
        tokens.pop(0)
    captured: list[str] = []
    for token in tokens:
        if token == SENTINEL:
            break
        low = token.lower()
        if low in BOUNDARY_WORDS:
            break
        captured.append(low)
        if len(captured) >= MAX_NAME_WORDS:
            break
    return captured


def _capture_around(text: str, start: int, end: int) -> list[str]:
    """Name tokens for one numeral occurrence at ``text[start:end]``.

    Before-capture first; when the numeral starts its segment (nothing
    but a sentinel or nothing at all before it — the numeral-index
    shape), fall back to after-capture.
    """
    prefix_tokens = _tokenize(text[:start])
    name = capture_noun_phrase(prefix_tokens)
    if name:
        return name
    at_segment_start = not prefix_tokens or prefix_tokens[-1] == SENTINEL
    if at_segment_start:
        return capture_forward_phrase(_tokenize(text[end:]))
    return []


def iter_spec_occurrences(spec_tex: str):
    """Yield spec-side occurrences: ``(numeral, name_tokens, paragraph, section)``.

    ``paragraph`` is the 4-digit ``[000N]`` number of the enclosing
    ``\\anvilpara{}`` invocation (paragraph numbering per the pre-flight
    Check 1 contract); ``section`` is one of the five required-section
    ids or ``front-matter`` before the first section heading.
    """
    text = clean_spec_text(spec_tex)
    paragraph_no = 0
    section = "front-matter"
    events = []
    for m in REFNUM_PLACEHOLDER_RE.finditer(text):
        events.append(("numeral", m.start(), m.end(), m.group(1)))
    for m in PARA_MARK_RE.finditer(text):
        events.append(("para", m.start(), m.end(), None))
    for m in SECTION_MARK_RE.finditer(text):
        events.append(("section", m.start(), m.end(), m.group(1)))
    events.sort(key=lambda e: e[1])

    for kind, start, end, payload in events:
        if kind == "para":
            paragraph_no += 1
        elif kind == "section":
            section = payload
        else:
            name = _capture_around(text, start, end)
            if name:
                yield payload, name, f"[{paragraph_no:04d}]", section


def iter_drawing_occurrences(drawings_md: str):
    """Yield drawing-side occurrences: ``(numeral, name_tokens, figure, section)``.

    ``figure`` is the enclosing ``## FIG.`` heading (or ``-`` before the
    first heading); ``section`` is always ``drawings``. Each heading
    starts a fresh scan section so the label stays short and one figure's
    prose never names another figure's numeral.
    """
    headings = list(FIG_HEADING_RE.finditer(drawings_md))
    spans = []
    for i, m in enumerate(headings):
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(drawings_md)
        spans.append((m.group(0).strip(), m.end(), body_end))
    if not spans:
        spans = [("-", 0, len(drawings_md))]

    for figure, body_start, body_end in spans:
        text = clean_prose_text(drawings_md[body_start:body_end])
        for m in DRAWING_NUMERAL_RE.finditer(text):
            name = _capture_around(text, m.start(), m.end())
            if name:
                yield m.group(1), name, figure, "drawings"


def check_numeral_names(version_dir) -> dict:
    """Collect per-numeral names across spec + drawings and report conflicts.

    ``version_dir`` is a ``<thread>.{N}/`` directory containing ``spec.tex``
    and optionally ``drawings/drawing-descriptions.md``. Returns the report
    dict (``consistent``, ``conflicting_numerals`` with each differing name
    and its paragraph/section locations, plus occurrence counts). Raises
    ``FileNotFoundError`` when ``spec.tex`` is absent.
    """
    version_dir = Path(version_dir)
    spec_path = version_dir / "spec.tex"
    if not spec_path.is_file():
        raise FileNotFoundError(f"no spec.tex in {version_dir}")
    drawings_path = version_dir / "drawings" / "drawing-descriptions.md"

    occurrences: dict[str, list[dict]] = {}
    occurrence_count = 0

    for numeral, name, paragraph, section in iter_spec_occurrences(
        spec_path.read_text(encoding="utf-8")
    ):
        occurrences.setdefault(numeral, []).append(
            {"name": " ".join(name), "paragraph": paragraph,
             "section": section, "source": "spec.tex"}
        )
        occurrence_count += 1

    if drawings_path.is_file():
        for numeral, name, figure, section in iter_drawing_occurrences(
            drawings_path.read_text(encoding="utf-8")
        ):
            occurrences.setdefault(numeral, []).append(
                {"name": " ".join(name), "paragraph": figure, "section": section,
                 "source": "drawings/drawing-descriptions.md"}
            )
            occurrence_count += 1

    conflicting = []
    for numeral in sorted(occurrences, key=int):
        entries = occurrences[numeral]
        token_lists = [[w for w in e["name"].split()] for e in entries]
        has_conflict = any(
            not names_consistent(token_lists[i], token_lists[j])
            for i in range(len(token_lists))
            for j in range(i + 1, len(token_lists))
        )
        if not has_conflict:
            continue
        # Cluster occurrences by distinct name for the report.
        distinct: dict[str, list[dict]] = {}
        for entry in entries:
            distinct.setdefault(entry["name"], []).append(
                {k: entry[k] for k in ("paragraph", "section", "source")}
            )
        conflicting.append(
            {
                "numeral": numeral,
                "names": [
                    {"name": name, "occurrences": len(locs), "locations": locs}
                    for name, locs in distinct.items()
                ],
            }
        )

    return {
        "version_dir": str(version_dir),
        "consistent": not conflicting,
        "numerals_checked": len(occurrences),
        "occurrences_checked": occurrence_count,
        "conflicting_numerals": conflicting,
    }


def format_report(report: dict) -> str:
    """Human-readable one-block-per-numeral rendering of a report."""
    lines = [
        f"numeral-names: {report['version_dir']} — "
        f"{report['occurrences_checked']} occurrence(s) across "
        f"{report['numerals_checked']} numeral(s) checked."
    ]
    if report["consistent"]:
        lines.append("OK: every reference numeral carries one consistent name.")
        return "\n".join(lines)
    for conflict in report["conflicting_numerals"]:
        lines.append(
            f"CONFLICT: numeral {conflict['numeral']} carries more than one name:"
        )
        for entry in conflict["names"]:
            locs = "; ".join(
                f"{loc['paragraph']} ({loc['section']}, {loc['source']})"
                for loc in entry["locations"][:6]
            )
            if len(entry["locations"]) > 6:
                locs += f"; … +{len(entry['locations']) - 6} more"
            lines.append(f'  - "{entry["name"]}" ×{entry["occurrences"]} — {locs}')
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "One-name-per-reference-numeral check for an ip-uspto-provisional "
            "version dir (issue #1500). Reports numerals carrying more than "
            "one element name, with paragraph numbers and the differing names."
        )
    )
    parser.add_argument(
        "version_dir",
        help="<thread>.{N}/ directory (spec.tex + optional drawings/drawing-descriptions.md)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="emit the findings as JSON instead of text",
    )
    args = parser.parse_args(argv)

    try:
        report = check_numeral_names(args.version_dir)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))
    return 0 if report["consistent"] else 1


if __name__ == "__main__":
    sys.exit(main())
