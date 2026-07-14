"""Doc-coverage guard for the paper skill's adoption of the local-corpus
claim-provenance contract (issue #612; contract shipped in #597/PR #605,
essay-side precedent in #611/PR #614).

The canonical contract lives in ``anvil/lib/snippets/provenance.md`` — the
command files reference it, they do NOT re-specify it (the identical
pattern as the essay adoption in ``test_essay_provenance_doc.py`` and the
``git_sync.md`` adoption in ``test_paper_git_sync_doc.py``). This file pins
the paper-skill adoption so the conditional corpus-provenance steps can't
silently drift out of a command file in a later edit:

- ``paper-draft.md`` step 3b — drafter writes ``provenance.md`` before the
  LaTeX body, records ``metadata.corpus_dirs_resolved``.
- ``paper-review.md`` step 4d — reviewer back-checks 5–10 rows/pass and
  emits the ``provenance_back_check`` block; step 6 gains the
  fabrication-class critical flags.
- ``paper-audit.md`` step 5b — the exhaustive five-way ``kind:
  tool_evidence`` audit over a SEPARATE ``<thread>.{N}.corpus-audit/``
  sidecar with the ``provenance_summary`` six-counter roll-up.
- ``paper-revise.md`` step 8b — reviser copies ``provenance.md`` forward
  into each new version dir.

All four carry a documented byte-identical branch when ``corpus:`` is
absent. The rubric total (/44) and advance threshold (35) are unchanged
(no new dimension). Zero lib changes.

Per the per-skill test filename convention (#58 — distinct filenames
across skills, ``__init__.py`` chains in every test dir), this file is
named ``test_paper_provenance_doc.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
COMMANDS = REPO_ROOT / "anvil" / "skills" / "paper" / "commands"
SNIPPET = REPO_ROOT / "anvil" / "lib" / "snippets" / "provenance.md"

# The 4 write-bearing paper commands adopting the provenance contract (the
# curation widened the issue-body's three to four — paper-revise carries
# the map forward so the second audit pass has a map to verify).
WRITE_BEARING_COMMANDS = [
    "paper-draft.md",
    "paper-review.md",
    "paper-audit.md",
    "paper-revise.md",
]

# The three commands that actively invoke the resolver to gate their
# behavior (the drafter writes the map, the reviewer back-checks it, the
# auditor exhaustively verifies it). The reviser reads the resolver's
# result to decide copy-forward but the AC anchors invocation on these.
RESOLVER_COMMANDS = [
    "paper-draft.md",
    "paper-review.md",
    "paper-audit.md",
]

# Read-only / non-executable orchestrator files that MUST NOT adopt the
# contract.
EXEMPT_FILES = [
    "paper.md",
]

# The five-way classification vocabulary (provenance.md §Section 5).
CLASSIFICATION_TOKENS = [
    "VERIFIED",
    "PARAPHRASE_OK",
    "MISMATCH",
    "NOT_FOUND",
    "FABRICATED",
]

# The five fabrication-class CriticalFlag.type strings (§Section 6).
FABRICATION_FLAG_TYPES = [
    "fabricated_quote",
    "fabricated_fact",
    "misattribution_of_substance",
    "anachronism",
    "unattributed_paraphrase",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_snippet_exists():
    """The canonical contract MUST exist (the command files reference it,
    they do not re-specify it — #597/PR #605)."""
    assert SNIPPET.is_file(), (
        "anvil/lib/snippets/provenance.md (the canonical contract) is "
        "missing — the paper commands reference it, not a re-spec"
    )


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_references_provenance_snippet(command: str):
    """Every write-bearing paper command MUST reference the snippet — the
    contract is referenced, never re-specified (issue #612)."""
    text = _read(COMMANDS / command)
    assert "snippets/provenance.md" in text, (
        f"{command} MUST reference anvil/lib/snippets/provenance.md "
        f"(issue #612 — the canonical contract)"
    )


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_mentions_provenance_filename(command: str):
    """All four commands MUST name the per-version ``provenance.md`` map
    file (drafter writes it, reviewer back-checks it, auditor verifies
    it, reviser copies it forward)."""
    text = _read(COMMANDS / command)
    assert "provenance.md" in text, (
        f"{command} MUST name the provenance.md claim map file"
    )


@pytest.mark.parametrize("command", RESOLVER_COMMANDS)
def test_command_invokes_resolver(command: str):
    """The drafter, reviewer, and auditor MUST invoke
    ``resolve_corpus_dirs`` to activate the tier (BRIEF-driven,
    byte-identical when absent)."""
    text = _read(COMMANDS / command)
    assert "resolve_corpus_dirs" in text, (
        f"{command} MUST invoke resolve_corpus_dirs to activate the "
        f"corpus tier (issue #612)"
    )


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_documents_byte_identical_when_absent(command: str):
    """Each command MUST document the no-corpus branch as byte-identical
    to pre-#612 behavior — the activation-when-declared / silence-when-
    absent posture (the essay/voice_grounding adoption precedent)."""
    text = _read(COMMANDS / command)
    assert "byte-identical" in text.lower(), (
        f"{command} MUST document byte-identical behavior when corpus: "
        f"is absent"
    )
    # The inactive branch keys off the absent/null/empty corpus: shapes.
    assert "corpus:" in text, (
        f"{command} MUST name the top-level corpus: BRIEF key whose "
        f"absence deactivates the tier"
    )


def test_draft_writes_map_before_prose_and_records_progress():
    """paper-draft step 3b MUST write provenance.md before the LaTeX body
    and record the resolved dirs in _progress.json so the reviewer and
    auditor can verify the run."""
    text = _read(COMMANDS / "paper-draft.md")
    assert "before the LaTeX body" in text or "before prose" in text, (
        "paper-draft MUST write provenance.md before the LaTeX body "
        "(§Section 2)"
    )
    assert "corpus_dirs_resolved" in text, (
        "paper-draft MUST record metadata.corpus_dirs_resolved when the "
        "tier is active"
    )


def test_review_documents_back_check_sample():
    """paper-review step 4d MUST document the 5–10-row spot-sample
    back-check as kind: judgment findings with quoted evidence."""
    text = _read(COMMANDS / "paper-review.md")
    assert "5–10 rows" in text or "5-10 rows" in text, (
        "paper-review MUST document the 5–10-row per-pass back-check "
        "sample (§Section 3)"
    )
    assert "kind: judgment" in text, (
        "paper-review back-check findings MUST be kind: judgment"
    )


def test_review_documents_provenance_back_check_block():
    """paper-review MUST emit the provenance_back_check _summary.md block
    only when active — the no-`ran:false` convention (activation-when-
    declared / silence-when-absent)."""
    text = _read(COMMANDS / "paper-review.md")
    assert "provenance_back_check" in text, (
        "paper-review MUST document the provenance_back_check _summary.md "
        "block"
    )
    assert "no-`ran:false` convention" in text or "no `{ran: false}`" in text, (
        "paper-review MUST state the block is omitted (no ran:false "
        "entry) when the corpus tier is inactive"
    )


def test_review_documents_fabrication_flags():
    """paper-review step 6 MUST document the five fabrication-class
    critical flags as conditional on the corpus tier, additive."""
    text = _read(COMMANDS / "paper-review.md")
    for flag in FABRICATION_FLAG_TYPES:
        assert flag in text, (
            f"paper-review MUST name the {flag} fabrication-class critical "
            f"flag (§Section 6)"
        )


def test_review_rubric_total_unchanged():
    """The additive flags MUST NOT change the rubric total (/44) or the
    advance threshold (35) — the per-review stamps are unchanged."""
    text = _read(COMMANDS / "paper-review.md")
    assert "rubric_total: 44" in text, (
        "paper-review MUST keep rubric_total: 44 (the fabrication flags "
        "are additive, not a rubric change)"
    )
    assert "advance_threshold: 35" in text, (
        "paper-review MUST keep advance_threshold: 35"
    )
    # Guard against a smuggled 10th dimension row in the scoring table.
    assert "| 10 |" not in text, (
        "paper-review MUST NOT introduce a 10th rubric dimension row — "
        "the fabrication flags are critical flags, not a new dimension"
    )


def test_audit_names_all_classification_tokens():
    """paper-audit step 5b MUST name all five classification tokens
    (§Section 5)."""
    text = _read(COMMANDS / "paper-audit.md")
    for token in CLASSIFICATION_TOKENS:
        assert token in text, (
            f"paper-audit MUST name the {token} classification token "
            f"(§Section 5 five-way vocabulary)"
        )


def test_audit_names_all_fabrication_flag_types():
    """paper-audit step 5b MUST name all five fabrication-class
    CriticalFlag.type strings (§Section 6)."""
    text = _read(COMMANDS / "paper-audit.md")
    for flag in FABRICATION_FLAG_TYPES:
        assert flag in text, (
            f"paper-audit MUST name the {flag} fabrication-class critical "
            f"flag (§Section 6)"
        )


def test_audit_documents_corpus_audit_sibling():
    """paper-audit MUST document the SEPARATE .corpus-audit/ sibling with
    its own staged_sidecar and four-file manifest (§Section 8)."""
    text = _read(COMMANDS / "paper-audit.md")
    assert "corpus-audit" in text, (
        "paper-audit MUST name the <thread>.{N}.corpus-audit/ sibling "
        "(§Section 8 sibling-dir naming)"
    )
    assert "staged_sidecar" in text, (
        "paper-audit MUST open a staged_sidecar for the .corpus-audit/ "
        "dir (SEPARATE from the .audit/ sidecar)"
    )
    assert "final_dir=<thread>.{N}.corpus-audit" in text, (
        "paper-audit MUST target the corpus-audit staged_sidecar at "
        "final_dir=<thread>.{N}.corpus-audit"
    )
    # The four-file manifest.
    for fname in ("_review.json", "_meta.json", "_progress.json", "corpus-audit.md"):
        assert fname in text, (
            f"paper-audit MUST name {fname} in the .corpus-audit/ manifest"
        )


def test_audit_documents_tool_evidence_and_tool_calls():
    """paper-audit's .corpus-audit/_review.json MUST be kind: tool_evidence
    with non-empty tool_calls on every MISMATCH / NOT_FOUND / FABRICATED
    finding (§Section 4)."""
    text = _read(COMMANDS / "paper-audit.md")
    assert "kind: tool_evidence" in text, (
        "paper-audit .corpus-audit/_review.json MUST declare kind: "
        "tool_evidence"
    )
    assert "tool_calls" in text, (
        "paper-audit MUST document non-empty tool_calls on every "
        "MISMATCH / NOT_FOUND / FABRICATED finding"
    )


def test_audit_documents_provenance_summary_counters():
    """paper-audit MUST document metadata.provenance_summary with the six
    counters (§Section 7) in the .corpus-audit/_progress.json."""
    text = _read(COMMANDS / "paper-audit.md")
    assert "provenance_summary" in text, (
        "paper-audit MUST record metadata.provenance_summary (§Section 7)"
    )
    for counter in (
        "total_claims",
        "verified",
        "paraphrase_ok",
        "mismatch",
        "not_found",
        "fabricated",
    ):
        assert counter in text, (
            f"paper-audit provenance_summary MUST carry the {counter} "
            f"counter (§Section 7 six-counter roll-up)"
        )


def test_audit_surfaces_unmapped_claims():
    """paper-audit MUST surface artifact claims with no provenance.md row
    as findings in themselves (§Section 4)."""
    text = _read(COMMANDS / "paper-audit.md")
    assert "no `provenance.md` row is a finding in itself" in text or (
        "unmapped claim" in text
    ), (
        "paper-audit MUST document that an unmapped claim (no provenance.md "
        "row) is a finding in itself (§Section 4)"
    )


def test_revise_copies_provenance_forward():
    """paper-revise step 8b MUST copy provenance.md forward into each new
    version dir, updated to match the revised prose."""
    text = _read(COMMANDS / "paper-revise.md")
    assert "copy it forward" in text.lower() or "copy" in text.lower(), (
        "paper-revise MUST copy provenance.md forward into the new "
        "version dir (§Section 2 reviser discipline)"
    )
    assert "corpus_dirs_resolved" in text, (
        "paper-revise MUST carry forward metadata.corpus_dirs_resolved "
        "in the new _progress.json"
    )


@pytest.mark.parametrize("exempt", EXEMPT_FILES)
def test_read_only_files_are_exempt(exempt: str):
    """Read-only / non-executable orchestrator files MUST NOT adopt the
    contract — paper.md is exempt by definition."""
    text = _read(COMMANDS / exempt)
    assert "snippets/provenance.md" not in text
    assert "resolve_corpus_dirs" not in text


def test_no_lib_changes_scope_guard():
    """Scope guard (issue #612 AC): the provenance adoption is command-
    file only — no lib file mentions the paper-specific progress key or the
    reviewer's back-check block. The contract terms live in the snippet +
    command files, never in the resolver / schema / verdict / cite lib
    modules this issue must NOT touch."""
    for lib_name in (
        "review_schema.py",
        "critics.py",
        "cite.py",
        "project_brief.py",
    ):
        lib_text = _read(REPO_ROOT / "anvil" / "lib" / lib_name)
        for token in ("corpus_dirs_resolved", "provenance_back_check"):
            assert token not in lib_text, (
                f"anvil/lib/{lib_name} MUST NOT reference {token} — issue "
                f"#612 is command-file adoption only, zero lib changes"
            )
