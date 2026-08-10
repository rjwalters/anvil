"""Unit tests for ``anvil/lib/rhetoric_lint.py`` (issue #463).

Covers the deterministic rhetoric lint (anti-trope / banned-phrase /
AI-tell pre-flight for rubric dim 9 *Rhetorical economy*):

- the three rule kinds (phrase: case-insensitive + word-boundary;
  regex: compiled with IGNORECASE; frequency: per-1000-words density
  with a ``min_words`` floor);
- scan exclusions (fenced code blocks, HTML comments, inline code);
- per-line suppression (same line + line directly above; suppressed
  hits surface as info);
- consumer rule-set merge semantics (merge, id-collision override,
  ``disable``, malformed-JSON graceful-degrade, severity coercion);
- the conservative-defaults bar: ZERO findings on good prose —
  enforced against the clean-memo fixture (full defaults) and the
  repo's memo-prose corpus (phrase/regex rules; see the corpus test's
  docstring for why the em-dash frequency rule is asserted separately);
- pure-stdlib import discipline (no pydantic, no third-party);
- doc coverage (memo-render.md names the dimension; memo-review.md
  carries the dim 9 advisory-evidence note; the module docstring
  documents the JSON rule schema).

Test filename is distinct per the #58 packaging convention.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from anvil.lib.rhetoric_lint import (
    CONFIG_RULE_ID,
    DEFAULT_FREQUENCY_MIN_WORDS,
    DEFAULT_LONG_SENTENCE_WORD_THRESHOLD,
    DEFAULT_RHETORIC_RULES,
    DEFAULT_SENTENCE_VARIANCE_MIN_CV,
    DEFAULT_SENTENCE_VARIANCE_MIN_SENTENCES,
    EMDASH_MAX_PER_1000_WORDS,
    EMPHASIS_MAX_PER_1000_WORDS,
    LONG_SENTENCE_MAX_PER_1000_WORDS,
    RULE_KIND_FREQUENCY,
    RULE_KIND_LONG_SENTENCE,
    RULE_KIND_PHRASE,
    RULE_KIND_REGEX,
    RULE_KIND_SENTENCE_VARIANCE,
    RhetoricLintResult,
    _collapse_markdown_links,
    _scannable_lines,
    _sentence_word_counts,
    _validate_rule,
    lint_rhetoric,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "anvil" / "lib" / "rhetoric_lint.py"
CLEAN_FIXTURE = Path(__file__).parent / "fixtures" / "rhetoric_clean_memo.md"


def _active(result: RhetoricLintResult):
    """Non-config warning findings (the 'rule fired' set)."""
    return [
        f
        for f in result.findings
        if f.severity == "warning" and f.rule_id != CONFIG_RULE_ID
    ]


# ---------------------------------------------------------------------------
# Pure-stdlib import discipline
# ---------------------------------------------------------------------------


def test_module_is_pure_stdlib():
    """No pydantic, no third-party imports (acceptance criterion)."""
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    allowed = {
        "__future__",
        "json",
        "re",
        "statistics",
        "dataclasses",
        "pathlib",
        "typing",
    }
    assert imported <= allowed, f"non-stdlib imports: {imported - allowed}"
    # Belt-and-braces: every import resolves from the stdlib set.
    assert imported - {"__future__"} <= set(sys.stdlib_module_names)


# ---------------------------------------------------------------------------
# Default rule set shape
# ---------------------------------------------------------------------------


def test_default_rules_all_valid_and_conservative_count():
    """Every default validates against the documented schema; ~20-35 rules."""
    for rule in DEFAULT_RHETORIC_RULES:
        normalized, error = _validate_rule(rule)
        assert error is None, error
        assert normalized is not None
    assert 20 <= len(DEFAULT_RHETORIC_RULES) <= 35
    ids = [r["id"] for r in DEFAULT_RHETORIC_RULES]
    assert len(ids) == len(set(ids)), "duplicate default rule ids"


def test_default_set_frequency_rules_are_emdash_and_emphasis():
    """Two frequency defaults ship: em-dash density and bold-span density
    (issue #745). Both carry a positive ``max_per_1000_words``."""
    freq = {
        r["id"]: r
        for r in DEFAULT_RHETORIC_RULES
        if r["kind"] == RULE_KIND_FREQUENCY
    }
    assert set(freq) == {"em-dash-density", "emphasis-density"}
    assert freq["em-dash-density"]["pattern"] == "—"
    assert (
        freq["em-dash-density"]["max_per_1000_words"]
        == EMDASH_MAX_PER_1000_WORDS
        == 8
    )
    assert freq["emphasis-density"]["pattern"] == r"\*\*[^*]+\*\*"
    assert (
        freq["emphasis-density"]["max_per_1000_words"]
        == EMPHASIS_MAX_PER_1000_WORDS
        == 20
    )


def test_default_rules_serialize_as_json():
    """The in-module dict shape IS the consumer JSON schema."""
    payload = json.dumps({"name": "defaults", "rules": list(DEFAULT_RHETORIC_RULES)})
    assert json.loads(payload)["rules"][0]["id"]


# ---------------------------------------------------------------------------
# Phrase kind: case-insensitive, word-boundary
# ---------------------------------------------------------------------------


def test_phrase_hit_basic():
    result = lint_rhetoric("This outcome is a testament to the team.")
    assert [f.rule_id for f in _active(result)] == ["no-testament-to"]
    assert _active(result)[0].line == 1
    assert _active(result)[0].match == "a testament to"


def test_phrase_case_insensitive():
    result = lint_rhetoric("A TESTAMENT TO grit.\nMultifaceted plans.\n")
    ids = {f.rule_id for f in _active(result)}
    assert ids == {"no-testament-to", "no-multifaceted"}


def test_phrase_word_boundary_no_substring_false_positive():
    """'plethora' must not fire inside a larger word."""
    result = lint_rhetoric("The plethorax measurement device shipped.")
    assert _active(result) == []


def test_regex_inflections_delved_matches_delivery_does_not():
    """No 'delved' false-negative, no 'delivery' false-positive."""
    hit = lint_rhetoric("We delved into the data.")
    assert [f.rule_id for f in _active(hit)] == ["no-delve"]
    clean = lint_rhetoric("Delivery vans deliver deliverables daily.")
    assert _active(clean) == []


def test_phrase_straight_apostrophe_matches_curly():
    result = lint_rhetoric("It’s important to note that margins fell.")
    assert [f.rule_id for f in _active(result)] == ["no-important-to-note"]


# ---------------------------------------------------------------------------
# Regex kind
# ---------------------------------------------------------------------------


def test_regex_kind_matches_inflections():
    result = lint_rhetoric("Rich tapestries of synergy.\nA tapestry of ideas.\n")
    hits = [f for f in _active(result) if f.rule_id == "no-tapestry"]
    assert {f.line for f in hits} == {1, 2}


def test_regex_consumer_rule_applied():
    rules = [
        {
            "id": "no-foo-bar",
            "kind": RULE_KIND_REGEX,
            "pattern": r"\bfoo[- ]bar\b",
            "message": "no foo-bar",
        }
    ]
    result = lint_rhetoric("This foo-bar idiom fires.", extra_rules=rules)
    assert [f.rule_id for f in _active(result)] == ["no-foo-bar"]


# ---------------------------------------------------------------------------
# Frequency kind: per-1000-words density
# ---------------------------------------------------------------------------


def _words(n: int) -> str:
    return ("alpha " * n).strip()


def test_frequency_under_threshold_no_finding():
    text = _words(1000) + "\n" + "— " * 7  # 7/1000 < 8
    assert _active(lint_rhetoric(text)) == []


def test_frequency_at_threshold_no_finding():
    """Threshold is strict: exactly 8/1000 does NOT fire (> 8 does)."""
    text = _words(1000) + "\n" + "— " * 8
    assert _active(lint_rhetoric(text)) == []


def test_frequency_over_threshold_fires_document_level():
    text = _words(1000) + "\n" + "— " * 9
    hits = _active(lint_rhetoric(text))
    assert [f.rule_id for f in hits] == ["em-dash-density"]
    assert hits[0].line is None  # document-level, no line anchor
    assert "9" in hits[0].message and "1000" in hits[0].message


def test_frequency_min_words_floor():
    """Density on a tiny text is noise, not signal — no finding.

    The em-dashes live on line 2 (not the opening prose line) so the
    positional ``no-opening-emdash`` rule stays silent and this test
    isolates the frequency-floor behavior it exists to check.
    """
    text = "Opening line, no dash.\n" + _words(
        DEFAULT_FREQUENCY_MIN_WORDS - 10
    ) + " — — — — —"
    assert _active(lint_rhetoric(text)) == []


def test_frequency_counts_exclude_code_and_comments():
    text = (
        _words(1000)
        + "\n```\n"
        + "— " * 50
        + "\n```\n"
        + "<!-- "
        + "— " * 50
        + " -->\n"
    )
    assert _active(lint_rhetoric(text)) == []


# ---------------------------------------------------------------------------
# emphasis-density (issue #745): bold-span frequency rule
# ---------------------------------------------------------------------------


def _bold_doc(spans: int, total_words: int = 1000) -> str:
    """A ``total_words``-word doc with ``spans`` distinct bold spans.

    Each ``**bN**`` span contributes exactly one word token, so the
    per-1000-words denominator is ``total_words`` regardless of ``spans``.
    """
    plain = ("alpha " * (total_words - spans)).strip()
    bolds = " ".join(f"**b{i}**" for i in range(spans))
    return plain + "\n" + bolds + "\n"


def test_emphasis_density_over_threshold_warns():
    """Acceptance criterion: 30 bold spans / 1000 words warns."""
    hits = _active(lint_rhetoric(_bold_doc(30)))
    assert [f.rule_id for f in hits] == ["emphasis-density"]
    assert hits[0].line is None  # document-level, no line anchor
    # The finding counts bold *spans* (30), not raw ``**`` runs (60), and
    # names the counted unit with the human label, not the raw regex.
    assert "30 occurrence" in hits[0].message
    assert "bold span" in hits[0].message
    assert r"\*\*" not in hits[0].message


def test_emphasis_density_under_threshold_no_finding():
    """Acceptance criterion: 15 bold spans / 1000 words does NOT warn."""
    assert _active(lint_rhetoric(_bold_doc(15))) == []


def test_emphasis_density_disable_via_config():
    res = lint_rhetoric(
        _bold_doc(30), extra_rules={"disable": ["emphasis-density"]}
    )
    assert _active(res) == []


# ---------------------------------------------------------------------------
# no-meta-commentary (issue #745): reviewer-addressed meta-commentary
# ---------------------------------------------------------------------------


def test_meta_commentary_fires_on_self_reference_and_fixed_phrases():
    text = (
        "This memo does not claim victory.\n"
        "The point was argued here.\n"
        "That is out of scope here.\n"
        "It is stated plainly.\n"
    )
    ids = [f.rule_id for f in _active(lint_rhetoric(text))]
    assert ids == ["no-meta-commentary"] * 4


def test_meta_commentary_catches_this_memo_proposes():
    """The memo.8 escape (issue #745): a narrower ad-hoc grep missed
    'this memo proposes'; the shipped rule's verb set includes it."""
    text = "The open-layer structure this memo proposes is sound.\n"
    assert [f.rule_id for f in _active(lint_rhetoric(text))] == [
        "no-meta-commentary"
    ]


def test_meta_commentary_no_false_positive_on_plain_memo_reference():
    assert _active(lint_rhetoric("Send the memo to finance by Friday.\n")) == []


def test_meta_commentary_disable_via_config():
    res = lint_rhetoric(
        "This memo argues X.\n",
        extra_rules={"disable": ["no-meta-commentary"]},
    )
    assert _active(res) == []


# ---------------------------------------------------------------------------
# no-warning-emoji (issue #745): alarm-emoji inflation
# ---------------------------------------------------------------------------


def test_warning_emoji_fires_on_each_marker():
    for ch in ("⚠️", "🚨", "❗"):
        ids = [
            f.rule_id
            for f in _active(lint_rhetoric(f"{ch} This is a kill condition.\n"))
        ]
        assert "no-warning-emoji" in ids, ch


def test_warning_emoji_disable_via_config():
    res = lint_rhetoric(
        "🚨 Alarm.\n", extra_rules={"disable": ["no-warning-emoji"]}
    )
    assert _active(res) == []


# ---------------------------------------------------------------------------
# long-sentence-density (issue #750): syntactic-complexity frequency rule
# ---------------------------------------------------------------------------


def _sentence(word_count: int, start_idx: int = 0) -> str:
    """A naive sentence of ``word_count`` unique alnum tokens, period-terminated."""
    return " ".join(f"w{start_idx + i}" for i in range(word_count)) + "."


def _long_sentence_doc(
    long_count: int, total_words: int = 1000, long_len: int = 45
) -> str:
    """A ``total_words``-word doc with ``long_count`` sentences of
    ``long_len`` words each; the remainder is short (<=5-word) filler
    sentences so no filler sentence itself crosses the long-sentence bar
    and the per-1000-words denominator is exactly ``total_words``."""
    long_words_total = long_count * long_len
    filler_words = total_words - long_words_total
    assert filler_words >= 0
    idx = 0
    sentences: list[str] = []
    remaining = filler_words
    while remaining > 0:
        n = min(5, remaining)
        sentences.append(_sentence(n, idx))
        idx += n
        remaining -= n
    for _ in range(long_count):
        sentences.append(_sentence(long_len, idx))
        idx += long_len
    return " ".join(sentences) + "\n"


def test_default_set_contains_long_sentence_density_rule():
    matches = [
        r for r in DEFAULT_RHETORIC_RULES if r["id"] == "long-sentence-density"
    ]
    assert len(matches) == 1
    assert matches[0]["kind"] == RULE_KIND_LONG_SENTENCE
    assert (
        matches[0]["sentence_word_threshold"]
        == DEFAULT_LONG_SENTENCE_WORD_THRESHOLD
        == 40
    )
    assert (
        matches[0]["max_per_1000_words"] == LONG_SENTENCE_MAX_PER_1000_WORDS == 4
    )


def test_long_sentence_density_over_threshold_fires_document_level():
    """Acceptance criterion: 6 planted 45-word sentences / 1000 words warns."""
    hits = _active(lint_rhetoric(_long_sentence_doc(6)))
    assert [f.rule_id for f in hits] == ["long-sentence-density"]
    assert hits[0].line is None  # document-level, no line anchor
    assert hits[0].match is None
    assert "6 sentence(s) over 40 words" in hits[0].message
    assert "6.0/1000" in hits[0].message


def test_long_sentence_density_under_threshold_no_finding():
    """Acceptance criterion: 2 planted 45-word sentences / 1000 words passes."""
    assert _active(lint_rhetoric(_long_sentence_doc(2))) == []


def test_long_sentence_density_at_threshold_no_finding():
    """Threshold is strict: exactly 4/1000 does NOT fire (> 4 does)."""
    assert _active(lint_rhetoric(_long_sentence_doc(4))) == []


def test_long_sentence_word_boundary_exactly_40_not_long():
    """A sentence of exactly 40 words is at the bar, not over it."""
    text = _long_sentence_doc(6, long_len=40)
    assert _active(lint_rhetoric(text)) == []


def test_long_sentence_word_boundary_41_is_long():
    """41 words crosses the ">40 words" bar."""
    text = _long_sentence_doc(6, long_len=41)
    hits = _active(lint_rhetoric(text))
    assert [f.rule_id for f in hits] == ["long-sentence-density"]


def test_long_sentence_density_min_words_floor():
    """A single long sentence in a 45-word doc is below the 50-word floor."""
    assert _active(lint_rhetoric(_sentence(45))) == []


def test_long_sentence_density_disable_via_config():
    res = lint_rhetoric(
        _long_sentence_doc(6),
        extra_rules={"disable": ["long-sentence-density"]},
    )
    assert _active(res) == []


# ---------------------------------------------------------------------------
# sentence-variance-floor (issue #921): rhythm-uniformity sibling of
# long-sentence-density — fires BELOW a coefficient-of-variation floor
# (inverse polarity of every other density rule in this module).
# ---------------------------------------------------------------------------


def _fixed_length_sentences(count: int, length: int, start_idx: int = 0) -> str:
    """``count`` sentences of exactly ``length`` words each (CV == 0) — the
    pathological flattened-rhythm shape this rule targets."""
    sentences: list[str] = []
    idx = start_idx
    for _ in range(count):
        sentences.append(_sentence(length, idx))
        idx += length
    return " ".join(sentences) + "\n"


def _varied_length_sentences(lengths: list) -> str:
    """Sentences whose lengths follow ``lengths`` — a realistic, irregular
    mix of short/medium/long sentences."""
    sentences: list[str] = []
    idx = 0
    for length in lengths:
        sentences.append(_sentence(length, idx))
        idx += length
    return " ".join(sentences) + "\n"


def test_default_set_contains_sentence_variance_floor_rule():
    matches = [
        r for r in DEFAULT_RHETORIC_RULES if r["id"] == "sentence-variance-floor"
    ]
    assert len(matches) == 1
    assert matches[0]["kind"] == RULE_KIND_SENTENCE_VARIANCE
    assert matches[0]["min_cv"] == DEFAULT_SENTENCE_VARIANCE_MIN_CV == 0.35


def test_sentence_variance_fires_on_uniform_sentence_lengths():
    """Acceptance criterion: identical-length sentences (CV == 0) — the
    'every sentence runs 18-22 words' flattened-rhythm failure mode — warns
    even though no single sentence is long enough to trip long_sentence."""
    text = _fixed_length_sentences(10, 20)
    hits = _active(lint_rhetoric(text))
    assert [f.rule_id for f in hits] == ["sentence-variance-floor"]
    assert hits[0].line is None  # document-level, no line anchor
    assert hits[0].match is None
    assert "coefficient of variation 0.00" in hits[0].message
    assert "floor 0.35" in hits[0].message


def test_sentence_variance_no_finding_on_varied_sentence_lengths():
    """A realistic mix of short/medium/long sentences (CV ~0.59) clears
    the floor — variety, not any particular mean length, is what this
    rule rewards. Lengths are kept <=40 words so the fixture does not
    also cross the unrelated long-sentence-density tail threshold."""
    lengths = [5, 30, 10, 35, 8, 25, 12, 30, 6, 20]
    text = _varied_length_sentences(lengths)
    assert _active(lint_rhetoric(text)) == []


def test_sentence_variance_min_words_floor():
    """Uniform sentences below the shared 50-word floor produce no finding."""
    text = _fixed_length_sentences(6, 5)  # 30 words total
    assert _active(lint_rhetoric(text)) == []


def test_sentence_variance_min_sentences_floor():
    """Uniform sentences that clear min_words but not the min_sentences
    sample-size floor (default 6) produce no finding."""
    text = _fixed_length_sentences(5, 20)  # 100 words, 5 sentences
    assert _active(lint_rhetoric(text)) == []


def test_sentence_variance_degenerate_single_sentence_no_finding():
    """Edge case (issue #921 test plan): a single sentence has stdev zero
    by construction (CV trivially 0), which the min_sentences floor must
    suppress rather than treat as a maximally-uniform document. A lone
    80-word sentence also crosses the unrelated long-sentence-density
    tail threshold at this small a word count, so that sibling rule is
    disabled to isolate the assertion to sentence-variance-floor."""
    res = lint_rhetoric(
        _sentence(80), extra_rules={"disable": ["long-sentence-density"]}
    )
    assert _active(res) == []


def test_sentence_variance_degenerate_two_sentences_no_finding():
    """Edge case (issue #921 test plan): 2 sentences is still below the
    sample-size floor, whatever their CV happens to be."""
    text = _fixed_length_sentences(2, 40)
    assert _active(lint_rhetoric(text)) == []


def test_sentence_variance_disable_via_config():
    text = _fixed_length_sentences(10, 20)
    res = lint_rhetoric(
        text, extra_rules={"disable": ["sentence-variance-floor"]}
    )
    assert _active(res) == []


def test_sentence_variance_excludes_code_and_comments():
    """Uniform 'sentences' inside fenced code / HTML comments do not feed
    the statistic — only the varied body prose is measured."""
    uniform_fenced = ("w " * 20 + ".\n") * 10
    text = (
        _varied_length_sentences([5, 30, 10, 35, 8, 25, 12, 30, 6, 20])
        + "```\n"
        + uniform_fenced
        + "```\n"
        + "<!-- "
        + uniform_fenced
        + " -->\n"
    )
    assert _active(lint_rhetoric(text)) == []


def test_validate_rule_sentence_variance_no_pattern_required():
    normalized, error = _validate_rule(
        {
            "id": "sv",
            "kind": RULE_KIND_SENTENCE_VARIANCE,
            "min_cv": 0.35,
            "message": "m",
        }
    )
    assert error is None, error
    assert normalized is not None
    assert "pattern" not in normalized
    assert normalized["min_sentences"] == DEFAULT_SENTENCE_VARIANCE_MIN_SENTENCES


def test_validate_rule_sentence_variance_requires_min_cv(tmp_path):
    path = _write_rules(
        tmp_path, {"rules": [{"id": "sv", "kind": "sentence_variance"}]}
    )
    result = lint_rhetoric("Plain text.", extra_rules_path=path)
    config = [f for f in result.findings if f.rule_id == CONFIG_RULE_ID]
    assert len(config) == 1
    assert "min_cv" in config[0].message


def test_validate_rule_sentence_variance_invalid_min_cv(tmp_path):
    path = _write_rules(
        tmp_path,
        {"rules": [{"id": "sv", "kind": "sentence_variance", "min_cv": 0}]},
    )
    result = lint_rhetoric("Plain text.", extra_rules_path=path)
    config = [f for f in result.findings if f.rule_id == CONFIG_RULE_ID]
    assert len(config) == 1
    assert "min_cv" in config[0].message


def test_validate_rule_sentence_variance_invalid_min_sentences_falls_back():
    """``min_sentences`` is permissively coerced (like ``min_words``), not
    a hard validation error, when the override is unusable."""
    normalized, error = _validate_rule(
        {
            "id": "sv",
            "kind": RULE_KIND_SENTENCE_VARIANCE,
            "min_cv": 0.35,
            "min_sentences": 1,
        }
    )
    assert error is None, error
    assert normalized["min_sentences"] == DEFAULT_SENTENCE_VARIANCE_MIN_SENTENCES


# ---------------------------------------------------------------------------
# no-grade-tags-in-body (issue #751): internal evidence-grade taxonomy
# leaking into reader-facing prose
# ---------------------------------------------------------------------------


def test_grade_tag_fires_on_each_documented_keyword():
    for tag in (
        "[SOLID]",
        "[DERIVED]",
        "[ASSUMPTION]",
        "[MEDIUM]",
        "[HIGH]",
        "[LOW]",
    ):
        ids = [
            f.rule_id
            for f in _active(lint_rhetoric(f"A claim graded {tag} here.\n"))
        ]
        assert ids == ["no-grade-tags-in-body"], tag


def test_grade_tag_fires_on_elaborated_estimate_tag():
    """The canary's memo.5 §5 instance: a multi-word elaboration after
    the grade keyword, closed by the bracket."""
    text = (
        "...computed at 23.5% more expensive per solved task "
        "([ESTIMATE from SOLID inputs], from an API price and accuracy "
        "table under a conservative nested-accuracy assumption)\n"
    )
    assert [f.rule_id for f in _active(lint_rhetoric(text))] == [
        "no-grade-tags-in-body"
    ]


def test_grade_tag_fires_on_colon_elaborated_medium_tag():
    """The canary's memo.5 §9 risk 7 instance: a colon-elaborated tag
    that even smuggles a drafter-directed instruction into prose."""
    text = (
        "Applied Compute reportedly raised $80M led by Kleiner Perkins "
        "[MEDIUM: vendor research post, not a funding primary; verify "
        "before treating as load-bearing]\n"
    )
    assert [f.rule_id for f in _active(lint_rhetoric(text))] == [
        "no-grade-tags-in-body"
    ]


def test_grade_tag_no_false_positive_on_ordinary_citation_brackets():
    text = (
        "A claim with a citation [1] and another [Smith et al. 2020] "
        "and a source-of-truth pointer [refs/cv.pdf].\n"
    )
    assert _active(lint_rhetoric(text)) == []


def test_grade_tag_sources_block_exempt():
    """A grade tag inside a '## Sources' section is the tag's documented
    home (rubric.md §'Grade-tag leakage (issue #751)') and MUST NOT fire,
    while the same tag shape outside the section still fires."""
    text = (
        "Leaked before the section: [HIGH] risk.\n"
        "\n"
        "## Sources\n"
        "\n"
        "- Founder interview [SOLID] verified directly.\n"
        "- Comp data [DERIVED] from public filings.\n"
        "\n"
        "## Risks\n"
        "\n"
        "Leaked after the section closes: [LOW] confidence.\n"
    )
    hits = [(f.rule_id, f.line) for f in _active(lint_rhetoric(text))]
    assert hits == [
        ("no-grade-tags-in-body", 1),
        ("no-grade-tags-in-body", 10),
    ]


def test_grade_tag_sources_block_exempt_covers_nested_subheading():
    """A '###' sub-heading inside '## Sources' stays inside the section
    (mirrors the migrate.py §Sources boundary rule); only a heading of
    equal-or-shallower depth closes it."""
    text = (
        "## Sources\n"
        "\n"
        "### Founder interviews\n"
        "\n"
        "- [ASSUMPTION] still inside the Sources section.\n"
    )
    assert _active(lint_rhetoric(text)) == []


def test_grade_tag_disable_via_config():
    res = lint_rhetoric(
        "A claim graded [SOLID] here.\n",
        extra_rules={"disable": ["no-grade-tags-in-body"]},
    )
    assert _active(res) == []


def test_long_sentence_density_excludes_code_and_comments():
    """Long "sentences" inside fenced code / HTML comments do not count."""
    fenced_long = "w " * 45 + ".\n"
    text = (
        _long_sentence_doc(0, total_words=1000)
        + "```\n"
        + fenced_long * 10
        + "```\n"
        + "<!-- "
        + fenced_long * 10
        + " -->\n"
    )
    # ``_long_sentence_doc(0, ...)`` is all-filler: ~146 uniform 5-word
    # sentences, a synthetic shape built to exercise the long-sentence
    # tail metric, not representative prose rhythm. It legitimately trips
    # ``sentence-variance-floor`` (CV ~0.0) — scope this test to the rule
    # kind it exercises (issue #921 sibling rule).
    assert _active(
        lint_rhetoric(
            text, extra_rules={"disable": ["sentence-variance-floor"]}
        )
    ) == []


def test_sentence_word_counts_joins_wrapped_lines():
    """A sentence wrapped across two source lines counts once, not twice."""
    text = "This sentence wraps\nacross two lines and ends here."
    counts = _sentence_word_counts(_scannable_lines(text))
    assert counts == [9]


def test_validate_rule_long_sentence_no_pattern_required():
    normalized, error = _validate_rule(
        {
            "id": "ls",
            "kind": RULE_KIND_LONG_SENTENCE,
            "max_per_1000_words": 4,
            "message": "m",
        }
    )
    assert error is None, error
    assert normalized is not None
    assert "pattern" not in normalized
    assert normalized["sentence_word_threshold"] == DEFAULT_LONG_SENTENCE_WORD_THRESHOLD


def test_validate_rule_long_sentence_requires_threshold(tmp_path):
    path = _write_rules(
        tmp_path, {"rules": [{"id": "ls", "kind": "long_sentence"}]}
    )
    result = lint_rhetoric("Plain text.", extra_rules_path=path)
    config = [f for f in result.findings if f.rule_id == CONFIG_RULE_ID]
    assert len(config) == 1
    assert "max_per_1000_words" in config[0].message


def test_validate_rule_long_sentence_invalid_sentence_word_threshold(tmp_path):
    path = _write_rules(
        tmp_path,
        {
            "rules": [
                {
                    "id": "ls",
                    "kind": "long_sentence",
                    "max_per_1000_words": 4,
                    "sentence_word_threshold": 0,
                }
            ]
        },
    )
    result = lint_rhetoric("Plain text.", extra_rules_path=path)
    config = [f for f in result.findings if f.rule_id == CONFIG_RULE_ID]
    assert len(config) == 1
    assert "sentence_word_threshold" in config[0].message


def test_grade_tag_sources_block_exempt_is_opt_in():
    """A consumer rule without ``sources_block_exempt`` set is NOT
    exempted inside a Sources section — the exemption is per-rule, not
    a global scan exclusion."""
    res = lint_rhetoric(
        "## Sources\n\nA plain phrase match should still fire here.\n",
        extra_rules={
            "rules": [
                {
                    "id": "test-always-fires",
                    "kind": "phrase",
                    "pattern": "plain phrase match",
                    "message": "test rule",
                }
            ]
        },
    )
    ids = [f.rule_id for f in _active(res)]
    assert "test-always-fires" in ids


# ---------------------------------------------------------------------------
# Scan exclusions: code fences, HTML comments, inline code
# ---------------------------------------------------------------------------


def test_code_fence_excluded():
    text = "```python\ndelve('a testament to')\n```\nClean prose.\n"
    assert _active(lint_rhetoric(text)) == []


def test_tilde_fence_excluded():
    text = "~~~\nWe delve here.\n~~~\nClean prose.\n"
    assert _active(lint_rhetoric(text)) == []


def test_html_comment_excluded_single_and_multiline():
    text = (
        "Prose. <!-- delve --> More prose.\n"
        "<!-- a testament to\n"
        "multifaceted delve\n"
        "-->\n"
        "Clean closing line.\n"
    )
    assert _active(lint_rhetoric(text)) == []


def test_inline_code_excluded():
    text = "Call `delve()` to traverse; the API name is historical.\n"
    assert _active(lint_rhetoric(text)) == []


def test_line_numbers_preserved_across_exclusions():
    text = "```\ncode\ncode\n```\nWe delve into it.\n"
    hits = _active(lint_rhetoric(text))
    assert [(f.rule_id, f.line) for f in hits] == [("no-delve", 5)]


# ---------------------------------------------------------------------------
# Markdown link collapsing (issue #889): URL path segments must not
# inflate the word-count denominator or the long_sentence word counts.
# ---------------------------------------------------------------------------


def test_collapse_markdown_links_strips_url_keeps_text():
    """``[text](url)`` -> ``text``; the url segment vanishes entirely."""
    scan_lines = _scannable_lines(
        "See [the target spec](https://github.com/2AMLogic/gf180-bandgap/"
        "blob/main/README.md) for details.\n"
    )
    collapsed = _collapse_markdown_links(scan_lines)
    joined = "\n".join(collapsed)
    assert "the target spec" in joined
    assert "github" not in joined
    assert "README" not in joined


def test_collapse_markdown_links_preserves_line_count():
    """Collapsing must not change the number of scan lines (line-anchored
    findings from other rules stay pinned to the right source line)."""
    text = "Line one.\n[a link](https://example.com/x)\nLine three.\n"
    scan_lines = _scannable_lines(text)
    collapsed = _collapse_markdown_links(scan_lines)
    assert len(collapsed) == len(scan_lines)


def test_collapse_markdown_links_handles_hard_wrapped_bracket_text():
    """The exact shape reported in issue #889: bracket text that spans a
    hard line wrap is still collapsed, not left dangling with the URL
    exposed on the second line."""
    text = (
        "gf180-bandgap's [target spec is\n"
        "ratified](https://github.com/2AMLogic/gf180-bandgap/blob/main/"
        "README.md):\n"
        "\n"
        "the design is complete.\n"
    )
    scan_lines = _scannable_lines(text)
    collapsed = _collapse_markdown_links(scan_lines)
    joined = "\n".join(collapsed)
    assert "target spec is" in joined
    assert "ratified" in joined
    assert "github" not in joined
    assert "2AMLogic" not in joined
    # Line count is unchanged — per-line findings (if any landed near
    # the link) still anchor to the original source line.
    assert len(collapsed) == len(scan_lines) == len(text.splitlines())


def test_word_count_identical_raw_vs_url_collapsed():
    """``lint_rhetoric``'s word count matches manually pre-collapsing the
    same link targets — the acceptance criterion's "measured both ways"
    equivalence, now true by construction rather than by double-reporting."""
    raw = (
        "See [the first source](https://example.com/one/two/three) and "
        "[a second source](https://example.com/four/five/six) for "
        "the analysis.\n"
    )
    collapsed_by_hand = (
        "See the first source and a second source for the analysis.\n"
    )
    raw_words = lint_rhetoric(raw).words
    hand_words = lint_rhetoric(collapsed_by_hand).words
    assert raw_words == hand_words


def test_link_dense_body_density_does_not_move_with_link_count():
    """Adding required links to an otherwise-unchanged body must not move
    the long-sentence density metric (issue #889: one revision added
    links to a *shorter* body and the density went up under the old
    raw-markdown tokenizer)."""
    long_sentence = " ".join(f"w{i}" for i in range(45)) + "."
    filler = " ".join(f"f{i}" for i in range(1000 - 45)) + "."
    body_no_links = f"{long_sentence} {filler}\n"
    body_with_links = (
        f"{long_sentence} {filler} See "
        "[source one](https://example.com/aaaa/bbbb/cccc) and "
        "[source two](https://example.com/dddd/eeee/ffff).\n"
    )
    words_no_links = lint_rhetoric(body_no_links).words
    words_with_links = lint_rhetoric(body_with_links).words
    # The added reader-visible prose ("See source one and source two.")
    # legitimately adds six words; the URL segments must not add any.
    assert words_with_links - words_no_links == 6


def test_long_sentence_rule_unaffected_by_link_wrapping_url():
    """A short, well-under-threshold sentence stays under threshold even
    when its only link's URL is long and would have pushed a naive
    per-line word count over 40 words."""
    text = (
        "Short sentence with a link to "
        "[a page](https://example.com/very/long/path/segment/that/would/"
        "inflate/a/naive/word/count/if/counted/as/words/here/too).\n"
    )
    assert _active(lint_rhetoric(text)) == []


# ---------------------------------------------------------------------------
# Suppression: anvil-lint-disable, same line + line above
# ---------------------------------------------------------------------------


def test_suppression_same_line_downgrades_to_info():
    text = "We delve into it. <!-- anvil-lint-disable: memo_rhetoric_lint -->\n"
    result = lint_rhetoric(text)
    assert _active(result) == []
    assert len(result.infos) == 1
    assert result.infos[0].rule_id == "no-delve"
    assert "(suppressed)" in result.infos[0].message


def test_suppression_line_above_downgrades_to_info():
    text = (
        "<!-- anvil-lint-disable: memo_rhetoric_lint -->\n"
        "We delve into it.\n"
        "We delve again.\n"
    )
    result = lint_rhetoric(text)
    # Line 2 suppressed (info); line 3 still fires (warning).
    assert [(f.severity, f.line) for f in result.findings] == [
        ("info", 2),
        ("warning", 3),
    ]


def test_suppression_generic_token_also_honored():
    text = "<!-- anvil-lint-disable: rhetoric_lint -->\nWe delve into it.\n"
    result = lint_rhetoric(text)
    assert _active(result) == []
    assert len(result.infos) == 1


def test_suppression_other_rule_token_does_not_leak():
    text = "<!-- anvil-lint-disable: memo_placeholder_scan -->\nWe delve in.\n"
    result = lint_rhetoric(text)
    assert [f.rule_id for f in _active(result)] == ["no-delve"]


def test_suppression_directive_does_not_self_match():
    """The directive is an HTML comment — excluded from the scan."""
    result = lint_rhetoric("<!-- anvil-lint-disable: memo_rhetoric_lint -->\n")
    assert result.findings == []


# ---------------------------------------------------------------------------
# Consumer rule files: merge + disable + graceful-degrade + coercion
# ---------------------------------------------------------------------------


def _write_rules(tmp_path: Path, payload: object) -> Path:
    p = tmp_path / "rules.json"
    p.write_text(
        payload if isinstance(payload, str) else json.dumps(payload),
        encoding="utf-8",
    )
    return p


def test_consumer_file_merges_with_defaults(tmp_path):
    path = _write_rules(
        tmp_path,
        {
            "name": "consumer",
            "rules": [
                {
                    "id": "no-widget",
                    "kind": RULE_KIND_PHRASE,
                    "pattern": "widgetify",
                    "message": "no widgetify",
                }
            ],
        },
    )
    result = lint_rhetoric(
        "We widgetify and delve.", extra_rules_path=path
    )
    assert {f.rule_id for f in _active(result)} == {"no-widget", "no-delve"}
    assert "no-widget" in result.rules_applied
    assert "no-delve" in result.rules_applied


def test_consumer_disable_removes_default(tmp_path):
    path = _write_rules(tmp_path, {"rules": [], "disable": ["no-delve"]})
    result = lint_rhetoric("We delve deep.", extra_rules_path=path)
    assert _active(result) == []
    assert "no-delve" not in result.rules_applied


def test_consumer_id_collision_overrides_default(tmp_path):
    path = _write_rules(
        tmp_path,
        {
            "rules": [
                {
                    "id": "no-delve",
                    "kind": RULE_KIND_PHRASE,
                    "pattern": "delve",
                    "message": "custom message",
                    "severity": "info",
                }
            ]
        },
    )
    result = lint_rhetoric("We delve deep.", extra_rules_path=path)
    assert _active(result) == []
    assert [f.message for f in result.infos] == ["custom message"]


def test_malformed_json_defaults_only_plus_one_warning(tmp_path):
    path = _write_rules(tmp_path, "{not json")
    result = lint_rhetoric("We delve deep.", extra_rules_path=path)
    config = [f for f in result.findings if f.rule_id == CONFIG_RULE_ID]
    assert len(config) == 1
    assert config[0].severity == "warning"
    assert str(path) in config[0].message
    # Defaults still ran.
    assert [f.rule_id for f in _active(result)] == ["no-delve"]


def test_missing_file_defaults_only_plus_one_warning(tmp_path):
    result = lint_rhetoric(
        "We delve deep.", extra_rules_path=tmp_path / "absent.json"
    )
    config = [f for f in result.findings if f.rule_id == CONFIG_RULE_ID]
    assert len(config) == 1
    assert [f.rule_id for f in _active(result)] == ["no-delve"]


def test_severity_error_coerced_to_warning(tmp_path):
    """Consumers may downgrade to info, never upgrade to error."""
    path = _write_rules(
        tmp_path,
        {
            "rules": [
                {
                    "id": "no-widget",
                    "kind": RULE_KIND_PHRASE,
                    "pattern": "widgetify",
                    "message": "m",
                    "severity": "error",
                }
            ]
        },
    )
    result = lint_rhetoric("We widgetify.", extra_rules_path=path)
    hits = [f for f in result.findings if f.rule_id == "no-widget"]
    assert [f.severity for f in hits] == ["warning"]


def test_invalid_individual_rule_skipped_with_config_finding(tmp_path):
    path = _write_rules(
        tmp_path,
        {
            "rules": [
                {"id": "bad-kind", "kind": "nope", "pattern": "x"},
                {"id": "bad-regex", "kind": "regex", "pattern": "(unclosed"},
                {
                    "id": "good",
                    "kind": RULE_KIND_PHRASE,
                    "pattern": "widgetify",
                    "message": "m",
                },
            ]
        },
    )
    result = lint_rhetoric("We widgetify.", extra_rules_path=path)
    config = [f for f in result.findings if f.rule_id == CONFIG_RULE_ID]
    assert len(config) == 2  # one per invalid rule, named
    assert any("bad-kind" in f.message for f in config)
    assert any("bad-regex" in f.message for f in config)
    assert [f.rule_id for f in _active(result) if f.rule_id == "good"] == ["good"]


def test_frequency_rule_requires_threshold(tmp_path):
    path = _write_rules(
        tmp_path,
        {"rules": [{"id": "f", "kind": "frequency", "pattern": "—"}]},
    )
    result = lint_rhetoric("Plain text.", extra_rules_path=path)
    config = [f for f in result.findings if f.rule_id == CONFIG_RULE_ID]
    assert len(config) == 1
    assert "max_per_1000_words" in config[0].message


def test_defaults_only_identical_with_and_without_declaration():
    """No consumer rules declared → byte-identical defaults-only run."""
    text = "We delve into a rich tapestry of options.\n"
    bare = lint_rhetoric(text)
    explicit = lint_rhetoric(text, extra_rules=None, extra_rules_path=None)
    assert bare.to_json() == explicit.to_json()


# ---------------------------------------------------------------------------
# The conservative-defaults bar (ENFORCED): zero findings on good prose
# ---------------------------------------------------------------------------


def test_zero_findings_on_clean_memo_fixture():
    """FULL defaults (incl. the em-dash frequency rule) on clean prose."""
    result = lint_rhetoric(CLEAN_FIXTURE.read_text(encoding="utf-8"))
    assert result.findings == [], [f.to_dict() for f in result.findings]
    assert result.words > 300  # the fixture is a real memo body, not a stub


def test_zero_phrase_regex_findings_on_repo_memo_corpus():
    """Default phrase/regex rules never fire on the repo's memo prose.

    The curation pinned the bar as "would never fire on the memo worked
    example" (`anvil/skills/memo/examples/`). That directory does not
    exist — the memo skill ships templates + fixture memo bodies
    instead — so this test enforces the bar against every memo-prose
    file in the repo (fixture memo bodies, BRIEF templates) plus the
    other skills' worked examples.

    Six *style-density / self-reference* rules are asserted separately
    rather than against this corpus, for the same reason: the repo's own
    fixture prose is em-dash-dense AI-written text (10-30 em-dashes per
    1000 words, several opening directly on an em-dash), some fixture
    bodies are bold-dense and/or carry multi-clause 40+ word sentences,
    the BRIEF templates carry document-describing commentary ("the
    memo is deliberately non-prescriptive"), and a pair of
    ``scorecard_check`` fixtures are literally a Markdown table of
    per-dimension justification cells rendered as short, near-uniform
    "sentences" (a structural table artifact, not prose rhythm) — each
    is exactly the tell its rule exists to flag, so none can serve as
    the "good prose" baseline. The clean-memo fixture
    (``test_zero_findings_on_clean_memo_fixture``) and the dedicated
    per-rule tests below are the real zero-findings baseline for:

    - ``em-dash-density`` (*frequency*) and ``no-opening-emdash``
      (positional, issue #601);
    - ``emphasis-density`` (*frequency*, bold spans) and
      ``no-meta-commentary`` (issue #745);
    - ``long-sentence-density`` (*long_sentence*, issue #750);
    - ``sentence-variance-floor`` (*sentence_variance*, issue #921).
    """
    style_density_excluded = (
        "em-dash-density",
        "no-opening-emdash",
        "emphasis-density",
        "no-meta-commentary",
        "long-sentence-density",
        "sentence-variance-floor",
    )
    corpus = (
        sorted((REPO_ROOT / "anvil/skills/memo/tests/fixtures").rglob("*.md"))
        + sorted((REPO_ROOT / "anvil/skills/memo/templates").glob("*.example"))
        + sorted((REPO_ROOT / "anvil/skills/proposal/examples").rglob("*.md"))
        + sorted(
            (REPO_ROOT / "anvil/skills/installation/examples").rglob("*.md")
        )
        + sorted((REPO_ROOT / "anvil/skills/ip-uspto/examples").rglob("*.md"))
    )
    assert len(corpus) > 20  # the corpus is real, not an empty glob
    offenders = {}
    for path in corpus:
        result = lint_rhetoric(path.read_text(encoding="utf-8"))
        hits = [
            f.to_dict()
            for f in _active(result)
            if f.rule_id not in style_density_excluded
        ]
        if hits:
            offenders[str(path)] = hits
    assert offenders == {}


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


def test_to_json_shape():
    result = lint_rhetoric("We delve in.\n")
    payload = result.to_json()
    assert payload["lint"] == "rhetoric_lint"
    assert payload["warnings"] == 1
    assert payload["infos"] == 0
    assert isinstance(payload["words"], int)
    assert payload["rules_applied"] == sorted(payload["rules_applied"])
    assert payload["findings"][0] == {
        "rule_id": "no-delve",
        "severity": "warning",
        "message": result.findings[0].message,
        "line": 1,
        "match": "delve",
    }


def test_never_emits_error_severity():
    """Advisory by contract: warning is the severity ceiling."""
    text = "We delve into a rich tapestry. It's important to note this.\n"
    result = lint_rhetoric(text)
    assert result.findings  # sanity
    assert all(f.severity in ("warning", "info") for f in result.findings)


# ---------------------------------------------------------------------------
# Doc coverage (grep-test precedent)
# ---------------------------------------------------------------------------


def test_memo_render_doc_names_the_dimension():
    doc = (
        REPO_ROOT / "anvil/skills/memo/commands/memo-render.md"
    ).read_text(encoding="utf-8")
    assert "memo_rhetoric_lint" in doc
    assert "rhetoric_rules_path" in doc


def test_memo_render_doc_wires_resolve_rhetoric_rules():
    """Issue #468: step 4g documents the full BRIEF-side wiring — the
    resolver is named, the deferral breadcrumb is gone, and the
    missing-file forward-the-path posture is explicit."""
    doc = (
        REPO_ROOT / "anvil/skills/memo/commands/memo-render.md"
    ).read_text(encoding="utf-8")
    assert "resolve_rhetoric_rules" in doc
    assert "omit until" not in doc
    assert "voice.rhetoric_rules" in doc
    # The declared-but-missing posture: forward the joined path so the
    # lint surfaces the broken declaration as a warning finding.
    assert "still pass the path" in doc


def test_memo_review_doc_carries_dim9_note():
    doc = (
        REPO_ROOT / "anvil/skills/memo/commands/memo-review.md"
    ).read_text(encoding="utf-8")
    assert "memo_rhetoric_lint" in doc
    assert "Rhetorical economy" in doc


def test_module_docstring_documents_json_schema():
    import anvil.lib.rhetoric_lint as mod

    doc = mod.__doc__ or ""
    for token in ('"rules"', '"disable"', "max_per_1000_words", "phrase", "regex", "frequency"):
        assert token in doc, f"module docstring missing {token!r}"


# ---------------------------------------------------------------------------
# Positional scope: schema normalization (issue #601)
# ---------------------------------------------------------------------------


def test_validate_rule_scope_first_line():
    """``scope: "first-line"`` normalizes through for phrase/regex kinds."""
    for kind in (RULE_KIND_PHRASE, RULE_KIND_REGEX):
        normalized, error = _validate_rule(
            {
                "id": "x",
                "kind": kind,
                "pattern": "foo",
                "message": "m",
                "scope": "first-line",
            }
        )
        assert error is None, error
        assert normalized is not None
        assert normalized["scope"] == "first-line"


def test_validate_rule_scope_default_body():
    """Absent or unknown ``scope`` coerces to ``"body"``."""
    absent, err1 = _validate_rule(
        {"id": "x", "kind": RULE_KIND_REGEX, "pattern": "foo", "message": "m"}
    )
    assert err1 is None
    assert absent["scope"] == "body"
    unknown, err2 = _validate_rule(
        {
            "id": "x",
            "kind": RULE_KIND_REGEX,
            "pattern": "foo",
            "message": "m",
            "scope": "nonsense",
        }
    )
    assert err2 is None
    assert unknown["scope"] == "body"


def test_validate_rule_frequency_has_no_scope():
    """Frequency rules are document-level: no ``scope`` key is stored."""
    normalized, error = _validate_rule(
        {
            "id": "f",
            "kind": RULE_KIND_FREQUENCY,
            "pattern": "—",
            "max_per_1000_words": 8,
            "message": "m",
            "scope": "first-line",  # ignored for frequency
        }
    )
    assert error is None, error
    assert "scope" not in normalized


# ---------------------------------------------------------------------------
# Positional scope: the no-opening-emdash default rule (issue #601)
# ---------------------------------------------------------------------------


def _opening(result: RhetoricLintResult):
    return [f for f in _active(result) if f.rule_id == "no-opening-emdash"]


def test_default_set_contains_opening_emdash_rule():
    matches = [
        r for r in DEFAULT_RHETORIC_RULES if r["id"] == "no-opening-emdash"
    ]
    assert len(matches) == 1
    assert matches[0]["scope"] == "first-line"
    assert matches[0]["kind"] == RULE_KIND_REGEX


def test_opening_emdash_first_prose_line_fires():
    result = lint_rhetoric("First line — with dash.\n\nSecond line.\n")
    hits = _opening(result)
    assert len(hits) == 1
    assert hits[0].line == 1
    assert hits[0].match == "—"


def test_opening_emdash_non_first_line_no_finding():
    """Same em-dash on line 3 does not fire the positional rule."""
    result = lint_rhetoric("First line clean.\n\nSecond line — with dash.\n")
    assert _opening(result) == []


def test_opening_emdash_skips_heading():
    """An em-dash in a leading heading is not the opening prose line."""
    result = lint_rhetoric("# Heading — title\n\nFirst prose — with dash.\n")
    assert [f.line for f in _opening(result)] == [3]


def test_opening_emdash_skips_front_matter():
    """YAML front-matter is skipped; the first prose line is line 5."""
    result = lint_rhetoric(
        "---\ntitle: Foo — bar\n---\n\nFirst prose — with dash.\n"
    )
    assert [f.line for f in _opening(result)] == [5]


def test_opening_emdash_suppression():
    """A directive on the line above the first prose line downgrades to info."""
    text = (
        "<!-- anvil-lint-disable: memo_rhetoric_lint -->\n"
        "First prose — with dash.\n"
    )
    result = lint_rhetoric(text)
    assert _opening(result) == []
    infos = [f for f in result.infos if f.rule_id == "no-opening-emdash"]
    assert len(infos) == 1
    assert infos[0].line == 2
    assert "(suppressed)" in infos[0].message


def test_opening_emdash_empty_document_no_crash():
    """Empty and front-matter-only documents produce no finding, no crash."""
    assert lint_rhetoric("").findings == []
    fm_only = lint_rhetoric("---\ntitle: Foo\n---\n")
    assert _opening(fm_only) == []


# ---------------------------------------------------------------------------
# Density tightening via id-collision (issue #601)
# ---------------------------------------------------------------------------


def test_consumer_id_collision_density_tightening(tmp_path):
    """A consumer 5/1000 ``em-dash-density`` replaces the 8/1000 default."""
    path = _write_rules(
        tmp_path,
        {
            "rules": [
                {
                    "id": "em-dash-density",
                    "kind": "frequency",
                    "pattern": "—",
                    "max_per_1000_words": 5,
                    "message": "tighter 5/1000",
                }
            ]
        },
    )
    text = _words(1000) + "\n" + "— " * 6  # 6/1000: > 5 but <= 8
    # Framework default (8/1000) does NOT fire at 6/1000.
    assert _active(lint_rhetoric(text)) == []
    # Consumer 5/1000 replaces it and DOES fire.
    hits = _active(lint_rhetoric(text, extra_rules_path=path))
    assert [f.rule_id for f in hits] == ["em-dash-density"]
    assert "tighter 5/1000" in hits[0].message


def test_voice_readme_documents_density_tightening_recipe():
    """Doc coverage: the density-tightening recipe is documented."""
    readme = (
        REPO_ROOT / "anvil/templates/voice/README.md"
    ).read_text(encoding="utf-8")
    assert "em-dash-density" in readme
    assert "max_per_1000_words" in readme
