"""Pre-flight lint: shared hard claims between sibling ``deck.md`` and ``memo.md``.

Detects **deck↔memo parity drift** — a load-bearing hard claim that lives in
one artifact but not its sibling. The classic failure mode is a memo revision
that pulls ahead of the deck (or vice versa) on a number / date / acronym
that both artifacts are supposed to share. Each pipeline (`anvil:memo`,
`anvil:deck`) advances on its own cadence under its own critic, so without
this check there is no point in the lifecycle where a shared hard-claim
universe is reconciled — the canary failure mode that surfaced this module.

Canary friction (issue #200)
----------------------------
Studio canary, 2026-06-01 portfolio review/revise pass: Citation Clear was
the first studio venture with both memo and deck pipelines shipped
(memo.3 + deck.3 at 35/40 advance:TRUE). During the revise pass, the
reviser introduced a load-bearing insurer benchmark — "~50–60% completion"
— into memo.4 that deck.3 lacked. **No anvil primitive detected this
drift.** Shared hard claims (FTC $193K / 5-0 / Jan 2025, NYC FY24 26.6%,
SFMTA $126M+ since April 2024, pricing $8.99/$29.99, kill thresholds)
silently drift across independent revision cycles. The studio cohort now
has ~10 threads on both `anvil:memo` and `anvil:deck` — every one is a
future drift surface.

The reference implementation pattern (``Finding`` / ``LintResult`` /
``_LINT_DISABLE_RE`` / ``lint_source`` / ``lint_<artifact>``) is
intentionally mirrored from ``anvil/skills/deck/lib/marp_lint.py`` (and from
the parallel ``anvil/skills/memo/lib/memo_image_refs.py`` mirror) so that
promoting this module to ``anvil/lib/parity.py`` later — once the
memo-side mirror (``anvil/skills/memo/lib/parity_lint.py``) lands as the
second consumer — is a **one-line import-path swap**, per the CLAUDE.md
"skill-local first, lib promotion later" pattern.

Phase A / Phase B (warning vs. error severity)
----------------------------------------------
v0 ships at **`warning` severity** for every parity finding. The lint is
*observational* on first ship: it surfaces drift in `findings.md` and the
operator's next-step list, but does NOT contribute to the
``lint_critical_flag`` and does NOT force ``advance: false``. The
``deck-review`` verdict aggregation (step 12) is byte-identical to a
thread without the parity lint enabled.

Phase B promotion to ``error`` (and therefore ``advance: false``-gating)
is a separate decision deferred 2–4 weeks after Phase A merge, based on
canary consumption signal — does the warning fire reliably on actionable
drift, or is the false-positive volume too high? This Phase A / Phase B
ship-with-falsifiability pattern (single named consumer + bounded
observation window + explicit kill-switch criterion) is the framework's
established negative-result discipline; see ``WORK_LOG.md`` 2026-06-02
(issue #227) for the canonical kill-switch precedent — a Phase A
primitive that did not survive its bounded canary window and was cleanly
retracted. The pattern itself — ship-with-falsifiability, observe,
retract-cleanly — is what carries forward here.

What the lint does (v0)
-----------------------

``lint_deck_memo_parity(deck_version_dir, memo_version_dir) -> LintResult``:

1. **Graceful-skip when no memo sibling.** If ``memo_version_dir`` is
   ``None`` or ``memo_version_dir/memo.md`` does not exist, returns
   ``LintResult(skipped=True, reason="...")`` with no findings. The
   single-pipeline case (most non-Studio consumers, and Studio threads
   where only the deck has shipped) is the common path; the lint is
   intentionally inert there. ``deck-review`` proceeds normally.
2. **Hard-claim extraction.** Apply a small set of conservative regex
   extractors over both bodies (see :data:`EXTRACTORS`):

   - **Money**: ``$XXK/M/B``, decimal prices (``$8.99``, ``$29.99``).
   - **Percentages**: ``26.6%``, ``50–60%`` (en-dash range), ``50-60%``
     (ascii range).
   - **Dates / quarters / FY**: ``Q1 FY24``, ``FY2024``, ``20XX``.
   - **Named months + year**: ``Jan 2025``, ``April 2024``.
   - **ALL-CAPS acronyms** (length 2–6): ``FTC``, ``SFMTA``, ``NYC``,
     ``LOI``. Conservative bound (length 2–6) deliberately rejects prose
     ALL-CAPS (``WHO``, ``DO NOT``, etc.) and over-long token strings.
   - **Unit-bearing integers**: ``8 pilots``, ``50 LOIs``, ``250k
     plants``. The unit vocabulary is small and conservative (see
     :data:`UNIT_VOCABULARY`).

   Each match is captured as a ``(token, line_number)`` pair so the
   diagnostic is grounded.
3. **Set comparison.** Two sets of tokens — one per artifact body —
   are compared by **exact-string equality**. Semantic equivalence
   (``$193K`` vs ``$193,000`` vs ``193 thousand``) is **explicitly
   deferred** to a follow-on issue. v0 surfaces ``only_in_memo`` and
   ``only_in_deck`` lists.
4. **Findings.** One ``Finding`` per token in ``only_in_memo`` or
   ``only_in_deck`` at ``severity="warning"`` (v0 contract).
5. **Escape hatch.** ``<!-- anvil-lint-disable: deck_memo_parity -->``
   on the line of (or immediately above) a deliberately-deck-only or
   deliberately-memo-only claim **downgrades that finding to ``info``**.
   The mechanism mirrors ``marp_lint`` and ``memo_image_refs`` exactly.

What v0 explicitly defers
-------------------------

- **Memo-side mirror** (``anvil/skills/memo/lib/parity_lint.py``):
  follow-on issue after the deck-side proves out.
- **Semantic-equivalence matching** (``$193K`` ↔ ``$193,000``): follow-on
  if the canary surfaces high false-positive volume.
- **Promotion to ``error`` severity** (Phase B): follow-on after 2–4 weeks
  of canary consumption signal.
- **Promotion to ``anvil/lib/parity.py``**: waits for the memo-side
  mirror. This module is shaped to mirror ``marp_lint.py`` (``Finding`` /
  ``LintResult`` / ``_LINT_DISABLE_RE`` / ``lint_source`` /
  ``lint_<artifact>``) so promotion is a one-line import-path swap.
- **Standalone ``/anvil:parity-check <thread>`` command**: not in v0; the
  ``deck-review`` step 5d invocation is the carrier.

Public API
----------
``lint_source(deck_source: str, memo_source: str) -> LintResult``
    Unit-testable core that operates on two in-memory strings. Used by the
    file wrapper and by the unit tests.
``lint_deck_memo_parity(deck_version_dir, memo_version_dir) -> LintResult``
    File wrapper. Discovers the source files inside the version dirs and
    handles the graceful-skip path when no memo sibling exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# Module-level metadata --------------------------------------------------------

#: Rules implemented in this module. Single rule in v0; the same shape (a
#: tuple of rule strings) mirrors ``marp_lint.PORTED_RULES`` and
#: ``memo_image_refs.RULES`` so promotion to ``anvil/lib/parity.py`` keeps
#: the same surface.
RULES: tuple[str, ...] = ("deck_memo_parity",)


# Anvil lint suppression directive. Mirrors ``marp_lint._LINT_DISABLE_RE``
# and ``memo_image_refs._LINT_DISABLE_RE`` exactly so a comma-separated
# rule list (``<!-- anvil-lint-disable: deck_memo_parity, some-other -->``)
# is honored across all three skill-local lints.
_LINT_DISABLE_RE = re.compile(
    r"<!--\s*anvil-lint-disable:\s*(?P<rules>[a-zA-Z0-9_,\-\s]+?)\s*-->",
)


# Result types -----------------------------------------------------------------


@dataclass
class Finding:
    """A single parity-lint hit.

    Field shape mirrors ``marp_lint.Finding`` so a consumer that already
    handles deck findings can handle parity findings without a schema
    fork. ``slide`` is absent here — parity operates on a deck-memo body
    pair, not a single Marp slide list — but ``line``, ``rule``,
    ``severity``, and ``message`` are preserved. Two additional fields
    capture the parity-specific shape:

    - ``token``: the exact extracted token that diverged between the two
      bodies (e.g., ``"~50–60% completion"`` minus the leading qualifier,
      or ``"50–60%"`` from the percentage extractor).
    - ``side``: ``"only_in_memo"`` or ``"only_in_deck"`` — which body
      contained the token that the other did not.
    """

    line: int
    rule: str
    severity: str  # "warning" | "info"  (v0 ships warning-only; info is the suppressed path)
    message: str
    token: str
    side: str  # "only_in_memo" | "only_in_deck"

    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "token": self.token,
            "side": self.side,
        }


@dataclass
class LintResult:
    """Aggregate parity-lint result.

    The ``skipped`` / ``reason`` / ``memo_sibling`` fields support the
    graceful-skip path required by the issue body AC7: when the lint
    cannot run (no memo sibling discoverable), the result still
    serializes a structured ``_summary.md`` block so the operator sees
    WHY the check did not fire.
    """

    warnings: list[Finding] = field(default_factory=list)
    infos: list[Finding] = field(default_factory=list)
    skipped: bool = False
    reason: str | None = None
    memo_sibling: str | None = None  # absolute path to the memo version dir, or None

    # v0 never emits errors — the lint is observational only. The field
    # is kept on the result for shape-parity with ``marp_lint.LintResult``
    # (so a future Phase B promotion to ``error`` severity does not need
    # to change the schema) but is always empty in v0.
    errors: list[Finding] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.errors) + len(self.warnings) + len(self.infos)

    @property
    def only_in_memo(self) -> list[str]:
        """Unique tokens that appeared in memo but not in deck (warnings + infos)."""
        seen: list[str] = []
        for f in self.warnings + self.infos:
            if f.side == "only_in_memo" and f.token not in seen:
                seen.append(f.token)
        return seen

    @property
    def only_in_deck(self) -> list[str]:
        """Unique tokens that appeared in deck but not in memo (warnings + infos)."""
        seen: list[str] = []
        for f in self.warnings + self.infos:
            if f.side == "only_in_deck" and f.token not in seen:
                seen.append(f.token)
        return seen

    def to_summary(self) -> dict:
        """Shape that fits cleanly into the review ``_summary.md`` ``lint`` block.

        Mirrors ``marp_lint.LintResult.to_summary`` and
        ``memo_image_refs.LintResult.to_summary`` with the parity-specific
        ``ran`` / ``memo_sibling`` / ``only_in_memo`` / ``only_in_deck``
        fields added. ``ran: false`` is the graceful-skip shape (no memo
        sibling discovered); ``ran: true`` with zero findings means the
        lint ran and both bodies had a fully-shared hard-claim universe.
        """
        return {
            "ran": not self.skipped,
            "memo_sibling": self.memo_sibling,
            "reason": self.reason,
            "warnings": len(self.warnings),
            "infos": len(self.infos),
            "only_in_memo": self.only_in_memo,
            "only_in_deck": self.only_in_deck,
            "warnings_by_token": [f.to_dict() for f in self.warnings],
            "infos_by_token": [f.to_dict() for f in self.infos],
        }


# Extractors -------------------------------------------------------------------
#
# Each extractor is a compiled regex applied line-by-line to a markdown body.
# The captured *token* is the part that should be exactly-equal across both
# bodies — it deliberately strips surrounding qualifier prose so that, for
# example, "~50–60% completion" extracts as the percentage "50-60%" and
# matches against a deck body that says "see the 50-60% completion benchmark".
#
# v0 is intentionally conservative on extractor scope. False-positive volume
# is the most likely friction mode; we'd rather miss a real drift than fire
# a warning on every prose noun phrase. The unit vocabulary
# (:data:`UNIT_VOCABULARY`) is deliberately narrow for the same reason.


# Money: $193K, $126M, $193.5M, $8.99, $29.99. The leading $ is required.
# Optional thousands separators (``$1,250``) and decimal points. Trailing
# K/M/B (case-insensitive) is the magnitude marker. We **normalize** the
# captured token to uppercase magnitude marker so ``$50m`` and ``$50M``
# compare as equal.
_MONEY_RE = re.compile(
    r"\$\d+(?:,\d{3})*(?:\.\d+)?[KMBkmb]?",
)


# Percentages: 26.6%, 50%, 50-60%, 50–60% (en-dash). Captures the whole
# range. The range form is normalized so ``50–60%`` and ``50-60%`` compare
# as equal (en-dash → ASCII hyphen).
_PERCENT_RE = re.compile(
    r"\d+(?:\.\d+)?(?:\s*[–-]\s*\d+(?:\.\d+)?)?\s*%",
)


# Quarters / FY tags: Q1 FY24, FY2024, FY24. The ``20XX`` bare-year
# extractor is intentionally NOT included here — bare four-digit years
# fire too aggressively on prose (footnote dates, dollar amounts, etc.).
# Calendar years are picked up via the named-month-plus-year extractor
# below.
_QUARTER_FY_RE = re.compile(
    r"\b(?:Q[1-4]\s+)?FY\d{2,4}\b",
)


# Named months + year: Jan 2025, April 2024, September 2023. Both
# 3-letter and full-word month names are accepted. Two-word "Sept 2023"
# vs "September 2023" do NOT normalize together in v0 — the deferred
# semantic-equivalence layer would catch that case.
_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
    "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec",
)
_MONTH_YEAR_RE = re.compile(
    r"\b(?:" + "|".join(_MONTH_NAMES) + r")\s+20\d{2}\b",
)


# ALL-CAPS acronyms (length 2-6): FTC, SFMTA, NYC, LOI, ARR, TAM, FY (FY
# also matched by the quarter regex; that's fine, we de-dupe at the set
# level). Length bound 2-6 rejects prose ALL-CAPS like single-letter "I"
# and over-long shouting. Word boundaries enforce token-ness.
_ACRONYM_RE = re.compile(
    r"\b[A-Z]{2,6}\b",
)


# Unit-bearing integers: 8 pilots, 50 LOIs, 250k plants. The unit
# vocabulary is **deliberately narrow** in v0 — adding to it should be
# canary-driven, not speculative. The leading number captures optional
# thousands separators and an optional "k"/"K"/"M"/"B" magnitude marker.
UNIT_VOCABULARY: tuple[str, ...] = (
    "users", "customers", "LOIs", "LOI", "pilots", "pilot",
    "design partners", "design partner",
    "completion", "completions",
    "reduction", "reductions",
    "plants", "factories",
    "engineers", "engineer",
    "founders", "founder",
    "deals", "deal",
)
# Build the alternation with longer phrases first so ``design partners``
# wins over ``partners`` alone.
_UNIT_ALT = "|".join(sorted(UNIT_VOCABULARY, key=lambda s: -len(s)))
_UNIT_INT_RE = re.compile(
    r"\b\d+(?:,\d{3})*(?:\.\d+)?[KkMmBb]?\s+(?:" + _UNIT_ALT + r")\b",
)


#: Ordered tuple of (rule-label, compiled-regex). Order is informational; the
#: actual lint logic unions all matches into a token set per body.
EXTRACTORS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("money", _MONEY_RE),
    ("percent", _PERCENT_RE),
    ("quarter_fy", _QUARTER_FY_RE),
    ("month_year", _MONTH_YEAR_RE),
    ("acronym", _ACRONYM_RE),
    ("unit_int", _UNIT_INT_RE),
)


# Token normalization ----------------------------------------------------------


def _normalize_token(token: str) -> str:
    """Normalize a captured token so equivalent surface forms compare equal.

    v0 normalization is **deliberately minimal**: just enough to fold the
    common ASCII / Unicode dash variants and to canonicalize whitespace
    inside captured ranges. Semantic equivalence (``$193K`` ↔ ``$193,000``)
    is the deferred normalization layer.

    Concrete rules:

    - Replace en-dash (``\\u2013``) and em-dash (``\\u2014``) with ASCII
      hyphen so ``50–60%`` and ``50-60%`` are the same token.
    - Collapse internal whitespace to a single space so ``Q1  FY24`` and
      ``Q1 FY24`` are the same token.
    - Uppercase trailing magnitude markers on money (``$50m`` → ``$50M``).
    - Strip a trailing period (sentence-end punctuation often sticks to
      the last captured token, e.g., ``FTC.``).
    """
    t = token.strip()
    t = t.replace("–", "-").replace("—", "-")
    t = re.sub(r"\s+", " ", t)
    # Uppercase a trailing money magnitude marker.
    m = re.match(r"^(\$\d+(?:,\d{3})*(?:\.\d+)?)([kmb])$", t)
    if m:
        t = m.group(1) + m.group(2).upper()
    # Strip a trailing period (commonly attached when the token ends a
    # sentence: "the FTC." → "FTC").
    if t.endswith("."):
        t = t[:-1]
    return t


# Token extraction -------------------------------------------------------------


@dataclass
class _Hit:
    """An extracted token + the 1-based line it appeared on."""

    line: int
    token: str
    rule_label: str  # the extractor that produced the match — informational


def _extract_tokens(source: str) -> list[_Hit]:
    """Apply every extractor to ``source`` and return a flat list of hits.

    Each match is captured as a ``_Hit(line=1-based-line, token=normalized,
    rule_label=...)``. Duplicates within the same body are preserved here —
    the caller de-dupes at the set-comparison step. Lint-disable directives
    themselves are scrubbed from the line before extraction (otherwise the
    rule-name inside the comment would appear as an ALL-CAPS acronym match
    in the parity set).
    """
    hits: list[_Hit] = []
    for line_idx, line in enumerate(source.splitlines(), start=1):
        # Scrub any anvil-lint-disable directive from the line so its inner
        # rule name (e.g., ``deck_memo_parity``) does not surface as a hit.
        scrubbed = _LINT_DISABLE_RE.sub("", line)
        for label, pattern in EXTRACTORS:
            for m in pattern.finditer(scrubbed):
                raw = m.group(0)
                token = _normalize_token(raw)
                if not token:
                    continue
                hits.append(_Hit(line=line_idx, token=token, rule_label=label))
    return hits


# Lint-disable handling --------------------------------------------------------


def _collect_disabled_tokens(source: str) -> set[str]:
    """Return the set of normalized tokens whose parity check is suppressed.

    Two placements honored (mirrors ``memo_image_refs._collect_disabled_lines``
    adapted to the parity model):

    1. **Same line**: ``<!-- anvil-lint-disable: deck_memo_parity -->`` on the
       same line as the token suppresses **every token on that line** for the
       parity rule.
    2. **Line above**: a standalone directive on the immediately preceding
       line (only whitespace allowed alongside) suppresses every token on
       the next non-blank, non-directive line.

    Returns the set of **normalized token strings** so the caller can
    downgrade matching findings to ``info`` without re-running the
    extractor for the suppressed lines.
    """
    disabled_lines: set[int] = set()
    lines = source.splitlines()
    for i, line in enumerate(lines):
        for m in _LINT_DISABLE_RE.finditer(line):
            rules = {r.strip() for r in m.group("rules").split(",") if r.strip()}
            if "deck_memo_parity" not in rules:
                continue
            # Same-line: suppress every token on this line.
            disabled_lines.add(i + 1)
            # If the directive is the ONLY content on the line (no leading
            # or trailing non-whitespace), also suppress the next non-blank
            # non-directive line — same shape as memo_image_refs.
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

    # Resolve disabled lines → disabled normalized tokens.
    disabled_tokens: set[str] = set()
    for line_idx, line in enumerate(lines, start=1):
        if line_idx not in disabled_lines:
            continue
        scrubbed = _LINT_DISABLE_RE.sub("", line)
        for _label, pattern in EXTRACTORS:
            for m in pattern.finditer(scrubbed):
                disabled_tokens.add(_normalize_token(m.group(0)))
    return disabled_tokens


# Diagnostic message construction ----------------------------------------------


def _build_message(token: str, side: str, line_no: int) -> str:
    """Compose the human-readable diagnostic for a parity finding.

    ``side`` is either ``"only_in_memo"`` or ``"only_in_deck"``. The
    message names the canary failure mode (the citation-clear insurer
    benchmark) the first time an operator encounters this lint so the
    Phase A → Phase B promotion conversation has a concrete anchor.
    """
    if side == "only_in_memo":
        return (
            f"Hard claim `{token}` appears in memo (line {line_no}) but not "
            f"in the sibling deck. Either reconcile (add to deck on next "
            f"`deck-revise`), document the deliberate omission with "
            f"`<!-- anvil-lint-disable: deck_memo_parity -->`, or accept "
            f"the divergence (warning only in v0). Canary: Citation Clear "
            f"memo.4 introduced a `~50–60% completion` insurer benchmark "
            f"absent from deck.3 — exactly this shape."
        )
    return (
        f"Hard claim `{token}` appears in deck (line {line_no}) but not "
        f"in the sibling memo. Either reconcile (add to memo on next "
        f"`memo-revise`), document the deliberate divergence with "
        f"`<!-- anvil-lint-disable: deck_memo_parity -->`, or accept "
        f"the divergence (warning only in v0)."
    )


# Public API -------------------------------------------------------------------


def lint_source(deck_source: str, memo_source: str) -> LintResult:
    """Run the parity lint over two in-memory body strings.

    This is the unit-testable core; ``lint_deck_memo_parity`` is a thin
    file wrapper that handles the graceful-skip path. Both ``deck_source``
    and ``memo_source`` are required — the caller is responsible for the
    sibling-discovery step and for invoking the skip path when no memo
    sibling exists.

    Returns a :class:`LintResult` with one warning per token in
    ``only_in_memo`` ∪ ``only_in_deck``, downgraded to ``info`` if the
    line carrying the token had ``<!-- anvil-lint-disable: deck_memo_parity -->``
    set (or on the line directly above).
    """
    result = LintResult()

    deck_hits = _extract_tokens(deck_source)
    memo_hits = _extract_tokens(memo_source)

    deck_tokens = {h.token for h in deck_hits}
    memo_tokens = {h.token for h in memo_hits}

    deck_disabled = _collect_disabled_tokens(deck_source)
    memo_disabled = _collect_disabled_tokens(memo_source)

    # only_in_memo: tokens present in memo but absent from deck.
    only_in_memo_tokens = memo_tokens - deck_tokens
    # Track the first line each token appears on for the diagnostic.
    memo_first_line: dict[str, int] = {}
    for h in memo_hits:
        if h.token in only_in_memo_tokens and h.token not in memo_first_line:
            memo_first_line[h.token] = h.line

    for token in sorted(only_in_memo_tokens):
        line_no = memo_first_line.get(token, 0)
        suppressed = token in memo_disabled
        finding = Finding(
            line=line_no,
            rule="deck_memo_parity",
            severity="info" if suppressed else "warning",
            message=_build_message(token, "only_in_memo", line_no),
            token=token,
            side="only_in_memo",
        )
        if suppressed:
            result.infos.append(finding)
        else:
            result.warnings.append(finding)

    # only_in_deck: symmetric — tokens present in deck but absent from memo.
    only_in_deck_tokens = deck_tokens - memo_tokens
    deck_first_line: dict[str, int] = {}
    for h in deck_hits:
        if h.token in only_in_deck_tokens and h.token not in deck_first_line:
            deck_first_line[h.token] = h.line

    for token in sorted(only_in_deck_tokens):
        line_no = deck_first_line.get(token, 0)
        suppressed = token in deck_disabled
        finding = Finding(
            line=line_no,
            rule="deck_memo_parity",
            severity="info" if suppressed else "warning",
            message=_build_message(token, "only_in_deck", line_no),
            token=token,
            side="only_in_deck",
        )
        if suppressed:
            result.infos.append(finding)
        else:
            result.warnings.append(finding)

    return result


def lint_deck_memo_parity(
    deck_version_dir: Path,
    memo_version_dir: Path | None,
) -> LintResult:
    """Run the parity lint against a ``<thread>.{N}/`` deck version dir.

    ``memo_version_dir`` is the sibling memo version directory to compare
    against, or ``None`` when no memo sibling exists (the single-pipeline
    case). The lint **graceful-skips** when ``memo_version_dir`` is
    ``None``, when the deck source is missing, or when the memo source
    inside ``memo_version_dir`` is missing — the absence of either body
    is not a lint error, it's a structural skip recorded in the result.

    Discovery contract (responsibility-split with the caller):
        Sibling-memo-version discovery is the **caller's responsibility**
        in v0 (``deck-review`` step 5d performs the lookup using the
        convention documented in the issue body: highest-version
        ``<thread>.{M}/memo.md`` next to the deck version dir). Centralizing
        that lookup in ``anvil/lib/parity.py`` is part of the promotion
        plan once the memo-side mirror lands.
    """
    if not isinstance(deck_version_dir, Path):
        deck_version_dir = Path(deck_version_dir)
    if memo_version_dir is not None and not isinstance(memo_version_dir, Path):
        memo_version_dir = Path(memo_version_dir)

    if memo_version_dir is None:
        return LintResult(
            skipped=True,
            reason="no memo sibling found at portfolio root; parity check inactive",
            memo_sibling=None,
        )

    deck_path = deck_version_dir / "deck.md"
    # Memo body filename echoes the memo thread slug per the issue #295
    # project-org model lock (``<memo-thread>/<memo-thread>.{N}/<memo-thread>.md``).
    # The memo thread slug is the memo version dir's parent directory name.
    memo_body_filename = f"{memo_version_dir.parent.name}.md"
    memo_path = memo_version_dir / memo_body_filename

    if not deck_path.is_file():
        return LintResult(
            skipped=True,
            reason=f"deck.md not found at {deck_path}",
            memo_sibling=str(memo_version_dir.resolve()),
        )
    if not memo_path.is_file():
        return LintResult(
            skipped=True,
            reason=f"{memo_body_filename} not found at {memo_path}",
            memo_sibling=str(memo_version_dir.resolve()),
        )

    deck_source = deck_path.read_text(encoding="utf-8")
    memo_source = memo_path.read_text(encoding="utf-8")

    result = lint_source(deck_source, memo_source)
    result.memo_sibling = str(memo_version_dir.resolve())
    return result


__all__ = [
    "EXTRACTORS",
    "Finding",
    "LintResult",
    "RULES",
    "UNIT_VOCABULARY",
    "lint_deck_memo_parity",
    "lint_source",
]
