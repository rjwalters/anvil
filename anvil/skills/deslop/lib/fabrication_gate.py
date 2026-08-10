"""Deterministic no-fabrication invariant gate for `anvil:deslop`'s revise
loop (issue #922, spun out of #919's AI-humanizer mining report).

`blader/humanizer` states an explicit no-fabrication invariant: a rewrite
must not contain any fact, name, number, date, quote, or citation absent
from the source text. It checks the invariant with an LLM self-audit
*question* at revise time, not a deterministic gate. `deslop` needs
something stronger: it is explicitly a rewrite tool over prose anvil does
not own the provenance of (website copy, README fragments, pasted text) —
there is no upstream Sources block or evidence-grade taxonomy to fall back
on the way `memo`/`report` have, so an LLM "did I notice anything?"
self-audit is the only safety net without this module.

What this module does
----------------------
A **deterministic** diff between two prose iterations (the iterate loop's
version N and N+1, per `commands/deslop.md` step 3e): extract three
token classes from each —

- **numerals** (money, percentages, bare/unit-bearing numbers, magnitude-
  suffixed figures — a permissive superset, not a semantic classifier);
- **proper nouns** (2+ consecutive Title-Case words — a single
  capitalized word is not flagged, since ordinary sentence-initial
  capitalization would swamp the signal with false positives);
- **citation-shaped tokens** (bracketed numeric refs like ``[12]``, bare
  URLs, and quoted strings).

— and flags any token that appears in N+1 but was absent from **both**
N and every resolved voice-grounding doc's text. This is advisory
evidence (mirrors `rhetoric_lint`'s "advisory by contract" posture: it
never blocks on its own) but it is a **named, deterministic** finding a
critic must address in the next iteration's critique pass — not
something caught only if the LLM happens to notice it in a self-audit
question.

Composes with, does not duplicate, existing infrastructure
------------------------------------------------------------
- **Scan exclusions** (fenced code, HTML comments, inline code) are
  delegated to :func:`anvil.lib.rhetoric_lint._scannable_lines` — the
  exact same exclusion pass `rhetoric_lint` already applies, imported
  directly rather than re-implemented, so a fence/comment/inline-code
  change can never drift out of sync between the two lints.
- **The diff-based "did this revision introduce content that wasn't
  there before?" shape** mirrors `anvil/lib/parity.py`'s deck<->memo
  parity lint (issue #200/#553/#914): extract a token set from each of
  two bodies with a family of conservative regex extractors, compare by
  set difference, emit one `Finding`-shaped result per drifted token,
  and honor the same `<!-- anvil-lint-disable: <rule> -->` escape-hatch
  contract every skill-local lint already uses (`marp_lint` /
  `memo_image_refs` / `rhetoric_lint` / `parity`). This module is a new,
  narrower application of that shape (revise-loop iterations instead of
  deck/memo siblings) — not a generalization of `parity.py` itself,
  since the token universe (numerals/proper-nouns/citations vs.
  money/percent/date/acronym/unit-int) and the "prior iteration" framing
  are both specific to the revise-loop's no-fabrication invariant.

Exception paths (mirrors `blader/humanizer`'s carve-out)
----------------------------------------------------------
`blader/humanizer` documents "swapping a vague claim for a specific one
is allowed only when the specific comes from the source or the user."
Two mechanisms implement that here, both additive:

1. **Voice-grounding docs as a second "source."** `check_no_fabrication`
   accepts `known_texts` — the resolved voice-grounding corpus text
   (values / style_guide / vocabulary / corpus, the #461 load order) —
   and unions its extracted tokens into the known set. A specific detail
   the revision pulled from a resolved voice doc (an author's own
   published figure, a name from their corpus) is legitimate
   specificity, not fabrication.
2. **The `anvil-lint-disable` escape hatch** for explicit operator-
   supplied detail that isn't captured in a voice doc: annotating the
   introduced line with ``<!-- anvil-lint-disable: deslop_no_fabrication
   -->`` downgrades that finding to `severity="info"` (surfaced, not
   silently accepted) — the same suppression contract every other
   skill-local lint uses, not a bespoke mechanism.

Public API
----------
- ``check_no_fabrication(prior_body, new_body, *, known_texts=(),
  rule=RULE_ID) -> FabricationGateResult``
- ``FabricationFinding`` / ``FabricationGateResult`` — mirrors
  ``rhetoric_lint.RhetoricFinding`` / ``RhetoricLintResult`` shape
  (``findings`` list + ``to_json()``), so a caller that already renders
  one lint's JSON block can render this one with the same code path.

Pure stdlib (``re``, ``dataclasses``) plus one import from
``anvil.lib.rhetoric_lint`` for the shared exclusion pass — no new
third-party dependency, matching CLAUDE.md's subprocess-first /
optional-extras philosophy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from anvil.lib.rhetoric_lint import _scannable_lines

# ---------------------------------------------------------------------------
# Token kinds
# ---------------------------------------------------------------------------

KIND_NUMERAL = "numeral"
KIND_PROPER_NOUN = "proper_noun"
KIND_CITATION = "citation"

_KIND_LABELS = {
    KIND_NUMERAL: "numeral",
    KIND_PROPER_NOUN: "proper noun",
    KIND_CITATION: "citation-shaped token",
}

# The rule id honored by the ``anvil-lint-disable`` escape hatch. Distinct
# from ``rhetoric_lint``'s own suppression tokens (``rhetoric_lint`` /
# ``memo_rhetoric_lint``) — this gate is a separate check with its own
# opt-out surface.
RULE_ID = "deslop_no_fabrication"

# Severities. Advisory by contract, same ceiling every skill-local lint
# uses: ``warning`` is the worst case, ``info`` is the suppressed path.
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


# ---------------------------------------------------------------------------
# Extractors (permissive supersets — false-negative-tolerant, not a
# semantic fact-checker; see the module docstring's "What this module
# does" section).
# ---------------------------------------------------------------------------

# Numeral: an optional leading ``$``, a digit run (with optional
# thousands separators and a decimal point), an optional trailing ``%``,
# and an optional magnitude suffix (K/M/B). A negative lookbehind on a
# word character keeps this from firing mid-identifier (``v2`` -> the
# ``2`` is preceded by the word char ``v`` and is excluded), while a
# hyphen-preceded figure (``GPT-4``) still matches — deliberately, since
# a model-number-shaped digit run is exactly the kind of fabricated
# specific this gate exists to catch.
_NUMERAL_RE = re.compile(
    r"(?<!\w)\$?\d+(?:,\d{3})*(?:\.\d+)?%?(?:[KMBkmb](?!\w))?"
)

# Proper noun: 2+ consecutive Title-Case words (optionally hyphenated
# within a word, e.g. ``Jean-Paul``), separated by single spaces. A
# *single* capitalized word is deliberately NOT matched — ordinary
# sentence-initial capitalization would otherwise swamp the signal with
# false positives (see the issue's acceptance criterion: "capitalized
# multi-word sequences").
_TITLE_WORD = r"[A-Z][A-Za-z'’]*(?:-[A-Z][A-Za-z'’]*)*"
_PROPER_NOUN_RE = re.compile(
    r"\b" + _TITLE_WORD + r"(?:\s+" + _TITLE_WORD + r"){1,}\b"
)

# Citation-shaped tokens: bracketed numeric refs, bare URLs, and quoted
# strings (straight or curly double quotes). Length-capped and
# newline-excluded so a stray unmatched quote doesn't swallow the rest
# of the document into one "citation".
_BRACKET_CITATION_RE = re.compile(r"\[\d+\]")
_URL_RE = re.compile(r"https?://\S+")
_QUOTED_RE = re.compile(r'"[^"\n]{1,200}"|“[^”\n]{1,200}”')

_EXTRACTORS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (KIND_NUMERAL, _NUMERAL_RE),
    (KIND_PROPER_NOUN, _PROPER_NOUN_RE),
    (KIND_CITATION, _BRACKET_CITATION_RE),
    (KIND_CITATION, _URL_RE),
    (KIND_CITATION, _QUOTED_RE),
)

# Anvil lint suppression directive — identical shape to
# ``rhetoric_lint._LINT_DISABLE_RE`` / ``parity._LINT_DISABLE_RE`` so a
# comma-separated rule list works uniformly across every skill-local
# lint.
_LINT_DISABLE_RE = re.compile(
    r"<!--\s*anvil-lint-disable:\s*(?P<rules>[a-zA-Z0-9_,\-\s]+?)\s*-->",
)


# ---------------------------------------------------------------------------
# Token normalization
# ---------------------------------------------------------------------------


def _normalize_token(token: str, kind: str) -> str:
    """Normalize a captured token so equivalent surface forms compare equal.

    Deliberately minimal, mirroring ``parity._normalize_token``: collapse
    internal whitespace, uppercase a numeral's trailing magnitude suffix
    (``$50m`` == ``$50M``), and strip a trailing sentence-period that
    commonly sticks to the last captured token.
    """
    t = token.strip()
    t = re.sub(r"\s+", " ", t)
    if kind == KIND_NUMERAL:
        m = re.match(r"^(\$?\d[\d,]*(?:\.\d+)?%?)([kmb])$", t, re.IGNORECASE)
        if m:
            t = m.group(1) + m.group(2).upper()
    if t.endswith(".") and kind != KIND_CITATION:
        t = t[:-1]
    return t


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


@dataclass
class _Hit:
    line: int
    kind: str
    token: str


def _extract_hits(text: str) -> list[_Hit]:
    """Extract every numeral / proper-noun / citation hit from ``text``.

    Runs over :func:`anvil.lib.rhetoric_lint._scannable_lines` (fenced
    code blocks, HTML comments, and inline code spans blanked, line count
    preserved) so a code sample or a suppression directive's own body
    text never fires the gate — the same exclusion scope `rhetoric_lint`
    already uses (issue #922 acceptance criterion).
    """
    scan_lines = _scannable_lines(text)
    hits: list[_Hit] = []
    for lineno, line in enumerate(scan_lines, start=1):
        scrubbed = _LINT_DISABLE_RE.sub("", line)
        for kind, pattern in _EXTRACTORS:
            for m in pattern.finditer(scrubbed):
                token = _normalize_token(m.group(0), kind)
                if not token:
                    continue
                hits.append(_Hit(line=lineno, kind=kind, token=token))
    return hits


def _collect_disabled_tokens(text: str, rule: str) -> set[str]:
    """Normalized tokens whose fabrication finding is suppressed.

    Same two-placement contract as ``parity._collect_disabled_tokens``:
    a same-line directive suppresses every token on that line; a
    standalone directive line suppresses every token on the next
    non-blank, non-directive line. Operates on raw (unscanned) lines —
    same as ``rhetoric_lint._collect_disabled_lines`` — since the
    directive itself lives inside an HTML comment that
    :func:`_extract_hits`'s scan pass would otherwise blank out.
    """
    disabled_lines: set[int] = set()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for m in _LINT_DISABLE_RE.finditer(line):
            rules = {r.strip() for r in m.group("rules").split(",") if r.strip()}
            if rule not in rules:
                continue
            disabled_lines.add(i + 1)
            head = line[: m.start()].strip()
            tail = line[m.end():].strip()
            if head or tail:
                continue
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                if not next_line.strip():
                    continue
                if _LINT_DISABLE_RE.search(next_line):
                    continue
                disabled_lines.add(j + 1)
                break

    disabled_tokens: set[str] = set()
    for line_idx, line in enumerate(lines, start=1):
        if line_idx not in disabled_lines:
            continue
        scrubbed = _LINT_DISABLE_RE.sub("", line)
        for kind, pattern in _EXTRACTORS:
            for m in pattern.finditer(scrubbed):
                token = _normalize_token(m.group(0), kind)
                if token:
                    disabled_tokens.add(token)
    return disabled_tokens


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class FabricationFinding:
    """One introduced-token hit (a token in the new iteration absent from
    the prior iteration and from every resolved voice-grounding doc)."""

    kind: str  # "numeral" | "proper_noun" | "citation"
    token: str
    line: int
    severity: str  # "warning" | "info" (info == suppressed)
    message: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "token": self.token,
            "line": self.line,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class FabricationGateResult:
    """Outcome of one no-fabrication gate pass.

    Mirrors ``rhetoric_lint.RhetoricLintResult`` / ``parity.LintResult``
    shape: a findings list plus ``to_json()``. There is no ``errors``
    bucket — the gate is advisory by contract, same as `rhetoric_lint`
    (see the module docstring); ``warning`` is the severity ceiling.
    """

    findings: list[FabricationFinding] = field(default_factory=list)

    @property
    def warnings(self) -> list[FabricationFinding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARNING]

    @property
    def infos(self) -> list[FabricationFinding]:
        return [f for f in self.findings if f.severity == SEVERITY_INFO]

    @property
    def total(self) -> int:
        return len(self.findings)

    def to_json(self) -> dict:
        return {
            "gate": "fabrication_gate",
            "rule": RULE_ID,
            "warnings": len(self.warnings),
            "infos": len(self.infos),
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Diagnostic message construction
# ---------------------------------------------------------------------------


def _build_message(kind: str, token: str, line_no: int, *, suppressed: bool) -> str:
    label = _KIND_LABELS[kind]
    message = (
        f"Introduced {label} `{token}` (line {line_no}) that is absent from "
        f"the prior iteration and from every resolved voice-grounding doc. "
        f"No-fabrication invariant (issue #922): a revision must not "
        f"introduce a fact, name, number, or citation the source didn't "
        f"carry. If `{token}` legitimately comes from the operator or a "
        f"voice-grounding doc this run didn't resolve, mark it with "
        f"`<!-- anvil-lint-disable: {RULE_ID} -->` on this line (or the "
        f"line directly above) to accept it explicitly; otherwise revert "
        f"to the prior iteration's wording for this claim."
    )
    if suppressed:
        message += " (suppressed)"
    return message


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_no_fabrication(
    prior_body: str,
    new_body: str,
    *,
    known_texts: Sequence[str] = (),
    rule: str = RULE_ID,
) -> FabricationGateResult:
    """Diff ``prior_body`` -> ``new_body`` for introduced numerals /
    proper nouns / citation-shaped tokens (issue #922).

    ``known_texts`` (optional) is any additional corpus whose tokens
    count as "already known" — the resolved voice-grounding docs'
    file contents in `deslop`'s revise loop (see
    ``orchestrate.check_fabrication``). A token appearing in ``new_body``
    but absent from BOTH ``prior_body`` and every string in
    ``known_texts`` is flagged. Order-preserving: findings are sorted by
    normalized token so the result is deterministic across runs.

    A token whose introducing line in ``new_body`` carries
    ``<!-- anvil-lint-disable: <rule> -->`` (same-line or the line
    directly above) is still reported, but downgraded to
    ``severity="info"`` — the escape-hatch contract shared by every
    skill-local lint in this framework (surfaced, not silently
    swallowed).
    """
    prior_hits = _extract_hits(prior_body)
    new_hits = _extract_hits(new_body)

    known_tokens: set[str] = {h.token for h in prior_hits}
    for text in known_texts:
        known_tokens |= {h.token for h in _extract_hits(text)}

    new_first: dict[str, _Hit] = {}
    for h in new_hits:
        new_first.setdefault(h.token, h)

    disabled_tokens = _collect_disabled_tokens(new_body, rule)

    result = FabricationGateResult()
    for token in sorted(t for t in new_first if t not in known_tokens):
        hit = new_first[token]
        suppressed = token in disabled_tokens
        result.findings.append(
            FabricationFinding(
                kind=hit.kind,
                token=token,
                line=hit.line,
                severity=SEVERITY_INFO if suppressed else SEVERITY_WARNING,
                message=_build_message(
                    hit.kind, token, hit.line, suppressed=suppressed
                ),
            )
        )
    return result


__all__ = [
    "KIND_CITATION",
    "KIND_NUMERAL",
    "KIND_PROPER_NOUN",
    "RULE_ID",
    "SEVERITY_INFO",
    "SEVERITY_WARNING",
    "FabricationFinding",
    "FabricationGateResult",
    "check_no_fabrication",
]
