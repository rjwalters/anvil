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
    DEFAULT_RHETORIC_RULES,
    EMDASH_MAX_PER_1000_WORDS,
    RULE_KIND_FREQUENCY,
    RULE_KIND_PHRASE,
    RULE_KIND_REGEX,
    RhetoricLintResult,
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
    allowed = {"__future__", "json", "re", "dataclasses", "pathlib", "typing"}
    assert imported <= allowed, f"non-stdlib imports: {imported - allowed}"
    # Belt-and-braces: every import resolves from the stdlib set.
    assert imported - {"__future__"} <= set(sys.stdlib_module_names)


# ---------------------------------------------------------------------------
# Default rule set shape
# ---------------------------------------------------------------------------


def test_default_rules_all_valid_and_conservative_count():
    """Every default validates against the documented schema; ~20-30 rules."""
    for rule in DEFAULT_RHETORIC_RULES:
        normalized, error = _validate_rule(rule)
        assert error is None, error
        assert normalized is not None
    assert 20 <= len(DEFAULT_RHETORIC_RULES) <= 30
    ids = [r["id"] for r in DEFAULT_RHETORIC_RULES]
    assert len(ids) == len(set(ids)), "duplicate default rule ids"


def test_default_set_has_exactly_one_frequency_rule_emdash():
    freq = [
        r for r in DEFAULT_RHETORIC_RULES if r["kind"] == RULE_KIND_FREQUENCY
    ]
    assert len(freq) == 1
    assert freq[0]["pattern"] == "—"
    assert freq[0]["max_per_1000_words"] == EMDASH_MAX_PER_1000_WORDS == 8


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
    """Density on a tiny text is noise, not signal — no finding."""
    text = _words(DEFAULT_FREQUENCY_MIN_WORDS - 10) + " — — — — —"
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

    The em-dash *frequency* rule is asserted separately
    (``test_zero_findings_on_clean_memo_fixture``): the repo's own
    fixture prose is em-dash-dense AI-written text (10-30 per 1000
    words — exactly the tell the rule exists to flag), so it cannot
    serve as the "good prose" baseline for the frequency dimension.
    """
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
            if f.rule_id != "em-dash-density"
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
