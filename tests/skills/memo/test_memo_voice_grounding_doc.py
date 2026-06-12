"""Doc-coverage tests for the voice/persona grounding-docs contract (issue #461).

The contract spans five documentation surfaces plus the snippet; these
grep-tests pin the coverage so future drift is caught early (the
#348 ``test_memo_recommendation_target_doc.py`` precedent):

1. `anvil/lib/snippets/voice_grounding.md` — the framework contract:
   four-doc taxonomy, drafter exemplar-quoting, corpus-quote-required
   deduction rule, convergence-with-Claude check, anti-stance critical-
   flag routing, #463 deferral note.
2. `anvil/skills/memo/commands/memo-review.md` — step 4l load, the dim
   8 triggered suffix (verbatim), the composition order, and the
   `_summary.md.voice_grounding` block.
3. `anvil/skills/memo/commands/memo-draft.md` — the step 5e advisory
   load + the `_progress.json.metadata.voice_exemplars` record.
4. `anvil/skills/memo/commands/memo-revise.md` — the read-and-preserve
   cross-reference.
5. `anvil/skills/memo/rubric.md` — §"Dim 8 — voice-grounding
   calibration".

Per the #58 packaging convention, this filename is unique across
`tests/skills/*/`.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "anvil" / "skills" / "memo"
SNIPPET = REPO_ROOT / "anvil" / "lib" / "snippets" / "voice_grounding.md"
RUBRIC = SKILL_ROOT / "rubric.md"
SKILL_MD = SKILL_ROOT / "SKILL.md"
DRAFT_COMMAND = SKILL_ROOT / "commands" / "memo-draft.md"
REVIEW_COMMAND = SKILL_ROOT / "commands" / "memo-review.md"
REVISE_COMMAND = SKILL_ROOT / "commands" / "memo-revise.md"

# The verbatim triggered suffix from the curation decision (#461 D3).
VOICE_SUFFIX = (
    "voice grounding active — dim 8 scored against "
    "<resolved values/style_guide paths>; voice deductions must quote "
    "corpus exemplars"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _norm(p: Path) -> str:
    """Whitespace-normalized body — phrase checks must tolerate the
    markdown line-wrapping of prose files."""
    return " ".join(p.read_text(encoding="utf-8").split())


# ---------------------------------------------------------------------------
# Snippet — anvil/lib/snippets/voice_grounding.md
# ---------------------------------------------------------------------------


def test_snippet_exists() -> None:
    assert SNIPPET.is_file(), (
        "anvil/lib/snippets/voice_grounding.md MUST exist — it is the "
        "framework-level voice grounding contract (issue #461)"
    )


def test_snippet_names_all_four_doc_types() -> None:
    body = _norm(SNIPPET)
    for key in ("style_guide", "vocabulary", "values", "corpus"):
        assert key in body, (
            f"voice_grounding.md MUST name the `{key}` doc type — the "
            f"four-doc taxonomy is the core of the contract (issue #461)"
        )


def test_snippet_documents_drafter_exemplar_quoting() -> None:
    body = _norm(SNIPPET)
    assert "voice_exemplars" in body, (
        "voice_grounding.md MUST document the drafter recording consulted "
        "exemplar paths in _progress.json (metadata.voice_exemplars)"
    )
    assert "3–5" in body or "3-5" in body, (
        "voice_grounding.md MUST document the 3–5 voice-matched, "
        "topically-adjacent exemplar selection rule"
    )


def test_snippet_documents_load_order() -> None:
    body = _norm(SNIPPET)
    assert "values → style_guide → vocabulary" in body, (
        "voice_grounding.md MUST document the drafter load order "
        "(values → style_guide → vocabulary → corpus exemplars)"
    )


def test_snippet_documents_corpus_quote_rule() -> None:
    body = _norm(SNIPPET)
    assert "MUST quote a corpus passage" in body, (
        "voice_grounding.md MUST carry the corpus-quote-required deduction "
        "rule — vague voice feedback is insufficient (issue #461)"
    )


def test_snippet_documents_convergence_with_claude_check() -> None:
    body = _norm(SNIPPET)
    assert "would I, the AI, also write this sentence?" in body, (
        "voice_grounding.md MUST carry the convergence-with-Claude "
        "adversarial check verbatim (the consumer's biggest meta-failure "
        "mode)"
    )
    assert "scrutinize harder, never defend" in body, (
        "voice_grounding.md MUST carry the 'scrutinize harder, never "
        "defend' posture for converged passages"
    )


def test_snippet_documents_anti_stance_critical_flag_routing() -> None:
    body = _norm(SNIPPET)
    assert "critical-flag candidate" in body, (
        "voice_grounding.md MUST route anti-stance violations through the "
        "existing critical-flag machinery (not a new flag category)"
    )
    assert "not a new flag category" in body


def test_snippet_documents_463_deferral() -> None:
    body = _norm(SNIPPET)
    assert "#463" in body or "issue #463" in body, (
        "voice_grounding.md MUST defer deterministic vocabulary screening "
        "to the rhetoric lint (issue #463)"
    )
    assert "em-dash" in body, (
        "voice_grounding.md MUST name em-dash frequency analysis as part "
        "of the deferred deterministic surface"
    )


def test_snippet_documents_activation_pattern() -> None:
    body = _norm(SNIPPET)
    assert "byte-identical" in body, (
        "voice_grounding.md MUST document the no-block → byte-identical "
        "activation pattern (#428/#452)"
    )
    assert "major" in body, (
        "voice_grounding.md MUST document the declared-but-missing → "
        "major-finding posture (customer_context.py precedent)"
    )


def test_snippet_documents_resolution_order() -> None:
    body = _norm(SNIPPET)
    assert "project root first" in body.lower() or "project-root first" in body.lower(), (
        "voice_grounding.md MUST document project-root-first, "
        "consumer-root-second path resolution"
    )
    assert "find_consumer_root" in body


# ---------------------------------------------------------------------------
# memo-review.md
# ---------------------------------------------------------------------------


def test_review_references_snippet_and_resolver() -> None:
    body = _norm(REVIEW_COMMAND)
    assert "anvil/lib/snippets/voice_grounding.md" in body, (
        "memo-review.md MUST reference the voice_grounding snippet"
    )
    assert "resolve_voice_docs" in body, (
        "memo-review.md MUST invoke "
        "anvil/lib/project_brief.py::resolve_voice_docs"
    )
    assert "4l." in body, (
        "memo-review.md MUST add the voice-doc load as step 4l (after the "
        "4k numeric-consistency check)"
    )


def test_review_carries_verbatim_suffix() -> None:
    body = _norm(REVIEW_COMMAND)
    assert VOICE_SUFFIX in body, (
        "memo-review.md MUST document the verbatim dim 8 triggered suffix "
        "from the #461 curation decision"
    )


def test_review_documents_composition_order() -> None:
    body = _norm(REVIEW_COMMAND)
    assert (
        "base reviewer-prose justification → artifact-type overlay suffix "
        "(if any, step 4i) → triggered voice-grounding suffix (this "
        "sub-step) → per-doc `dim_8_calibration` suffix" in body
    ), (
        "memo-review.md MUST document the #348 composition order: base → "
        "overlay → voice suffix → per-doc dim_8_calibration last"
    )


def test_review_documents_summary_block() -> None:
    body = _norm(REVIEW_COMMAND)
    assert '"voice_grounding"' in body, (
        "memo-review.md step 9 MUST document the _summary.md "
        "voice_grounding block"
    )
    assert "exemplars_quoted" in body and "docs_loaded" in body, (
        "memo-review.md MUST document the {ran, docs_loaded, "
        "exemplars_quoted} block shape"
    )


def test_review_documents_no_ran_false_convention() -> None:
    body = _norm(REVIEW_COMMAND)
    assert "the block is NOT emitted at all" in body, (
        "memo-review.md MUST document that an inactive voice tier emits NO "
        "voice_grounding block (not a ran:false entry) — the "
        "customer-context activation convention"
    )


def test_review_documents_missing_doc_major_finding() -> None:
    body = _norm(REVIEW_COMMAND)
    assert "**`major` finding in `comments.md`**" in body, (
        "memo-review.md MUST record declared-but-missing voice docs as "
        "major findings while keeping the tier active"
    )


# ---------------------------------------------------------------------------
# memo-draft.md
# ---------------------------------------------------------------------------


def test_draft_references_exemplar_record() -> None:
    body = _norm(DRAFT_COMMAND)
    assert "voice_exemplars" in body, (
        "memo-draft.md MUST document the "
        "_progress.json.metadata.voice_exemplars record (issue #461)"
    )
    assert "resolve_voice_docs" in body
    assert "anvil/lib/snippets/voice_grounding.md" in body


def test_draft_documents_load_order_and_selection() -> None:
    body = _norm(DRAFT_COMMAND)
    assert "values → style_guide → vocabulary → corpus exemplars" in body, (
        "memo-draft.md MUST document the drafter load order"
    )
    assert "3–5 corpus exemplars" in body, (
        "memo-draft.md MUST document the 3–5 exemplar selection rule"
    )


# ---------------------------------------------------------------------------
# memo-revise.md
# ---------------------------------------------------------------------------


def test_revise_cross_references_voice_docs() -> None:
    body = _norm(REVISE_COMMAND)
    assert "resolve_voice_docs" in body, (
        "memo-revise.md MUST cross-reference reading the voice docs when "
        "the tier is active (issue #461)"
    )
    assert "preserve voice signatures" in body, (
        "memo-revise.md MUST instruct the reviser to preserve voice "
        "signatures the reviewer flagged as working"
    )


# ---------------------------------------------------------------------------
# rubric.md + SKILL.md
# ---------------------------------------------------------------------------


def test_rubric_documents_dim8_calibration_section() -> None:
    body = _norm(RUBRIC)
    assert "## Dim 8 — voice-grounding calibration" in body, (
        "rubric.md MUST have a §'Dim 8 — voice-grounding calibration' "
        "section (issue #461)"
    )
    assert VOICE_SUFFIX in body, (
        "rubric.md MUST document the verbatim triggered suffix"
    )
    assert "does NOT add a tenth dimension" in body or "NOT add a tenth dim" in body, (
        "rubric.md MUST document that the calibration keeps /44 stable "
        "(no tenth dim)"
    )


def test_rubric_dim8_documents_backwards_compat() -> None:
    body = _read(RUBRIC)
    section = body.split("## Dim 8 — voice-grounding calibration", 1)[1]
    section = section.split("\n## ", 1)[0]
    assert "byte-identical" in section, (
        "the rubric's dim 8 voice section MUST document the "
        "byte-identical-when-absent contract"
    )


def test_skill_md_documents_voice_block() -> None:
    body = _norm(SKILL_MD)
    assert "voice:" in body and "Voice grounding" in body, (
        "SKILL.md MUST document the project BRIEF voice: block"
    )
    assert "anvil/lib/snippets/voice_grounding.md" in body, (
        "SKILL.md MUST reference the framework snippet"
    )
