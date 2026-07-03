"""Doc-coverage guard for the essay skill's adoption of the local-corpus
claim-provenance contract (issue #611; contract shipped in #597/PR #605).

The canonical contract lives in ``anvil/lib/snippets/provenance.md`` — the
command files reference it, they do NOT re-specify it (the identical
pattern as the ``voice_grounding.md`` adoption across the essay
commands). This file pins the essay-skill adoption so the conditional
corpus-provenance steps can't silently drift out of a command file in a
later edit:

- ``essay-draft.md`` step 3c — drafter writes ``provenance.md`` before
  prose, records ``metadata.corpus_dirs_resolved``.
- ``essay-review.md`` step 4c — reviewer back-checks 5–10 rows/pass and
  emits the ``provenance_back_check`` block; step 7 gains the
  fabrication-class critical flags 9–13.
- ``essay-revise.md`` step 5 — reviser copies ``provenance.md`` forward
  into each new version dir.

All three carry a documented byte-identical branch when ``corpus:`` is
absent. The rubric total (/44) and advance threshold (35) are unchanged.

Per the per-skill test filename convention (#58 — distinct filenames
across skills, ``__init__.py`` chains in every test dir), this file is
named ``test_essay_provenance_doc.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
COMMANDS = REPO_ROOT / "anvil" / "skills" / "essay" / "commands"
SNIPPET = REPO_ROOT / "anvil" / "lib" / "snippets" / "provenance.md"

# The 3 write-bearing essay commands adopting the provenance contract
# (the v1 command set is draft/review/revise/status only; essay.md is a
# read-only orchestrator and exempt by definition).
WRITE_BEARING_COMMANDS = [
    "essay-draft.md",
    "essay-review.md",
    "essay-revise.md",
]

# The two commands that actively invoke the resolver to gate their
# behavior (the drafter writes the map; the reviewer back-checks it).
RESOLVER_COMMANDS = [
    "essay-draft.md",
    "essay-review.md",
]

# Read-only / non-executable files that MUST NOT adopt the contract.
EXEMPT_FILES = [
    "essay.md",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_snippet_exists():
    """The canonical contract MUST exist (the command files reference it,
    they do not re-specify it — #597/PR #605)."""
    assert SNIPPET.is_file(), (
        "anvil/lib/snippets/provenance.md (the canonical contract) is "
        "missing — the essay commands reference it, not a re-spec"
    )


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_references_provenance_snippet(command: str):
    """Every write-bearing essay command MUST reference the snippet — the
    contract is referenced, never re-specified (issue #611)."""
    text = _read(COMMANDS / command)
    assert "snippets/provenance.md" in text, (
        f"{command} MUST reference anvil/lib/snippets/provenance.md "
        f"(issue #611 — the canonical contract)"
    )


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_mentions_provenance_filename(command: str):
    """All three commands MUST name the per-version ``provenance.md``
    map file (drafter writes it, reviewer back-checks it, reviser copies
    it forward)."""
    text = _read(COMMANDS / command)
    assert "provenance.md" in text, (
        f"{command} MUST name the provenance.md claim map file"
    )


@pytest.mark.parametrize("command", RESOLVER_COMMANDS)
def test_command_invokes_resolver(command: str):
    """The drafter and reviewer MUST invoke ``resolve_corpus_dirs`` to
    activate the tier (BRIEF-driven, byte-identical when absent)."""
    text = _read(COMMANDS / command)
    assert "resolve_corpus_dirs" in text, (
        f"{command} MUST invoke resolve_corpus_dirs to activate the "
        f"corpus tier (issue #611)"
    )


@pytest.mark.parametrize("command", WRITE_BEARING_COMMANDS)
def test_command_documents_byte_identical_when_absent(command: str):
    """Each command MUST document the no-corpus branch as byte-identical
    to pre-#611 behavior — the activation-when-declared / silence-when-
    absent posture (the voice_grounding.md adoption precedent)."""
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
    """essay-draft MUST write provenance.md before prose and record the
    resolved dirs in _progress.json so the reviewer can verify the run."""
    text = _read(COMMANDS / "essay-draft.md")
    assert "before prose" in text, (
        "essay-draft MUST write provenance.md before prose (§Section 2)"
    )
    assert "corpus_dirs_resolved" in text, (
        "essay-draft MUST record metadata.corpus_dirs_resolved when the "
        "tier is active"
    )


def test_review_documents_back_check_sample():
    """essay-review step 4c MUST document the 5–10-row spot-sample
    back-check as kind: judgment findings with quoted evidence."""
    text = _read(COMMANDS / "essay-review.md")
    assert "5–10 rows" in text or "5-10 rows" in text, (
        "essay-review MUST document the 5–10-row per-pass back-check "
        "sample (§Section 3)"
    )
    assert "kind: judgment" in text, (
        "essay-review back-check findings MUST be kind: judgment"
    )


def test_review_documents_provenance_back_check_block():
    """essay-review MUST emit the provenance_back_check _summary.md block
    only when active — the no-`ran:false` convention (same as the voice
    grounding block)."""
    text = _read(COMMANDS / "essay-review.md")
    assert "provenance_back_check" in text, (
        "essay-review MUST document the provenance_back_check _summary.md "
        "block"
    )
    assert "no-`ran:false` convention" in text or "no `{ran: false}`" in text, (
        "essay-review MUST state the block is omitted (no ran:false "
        "entry) when the corpus tier is inactive"
    )


def test_review_documents_fabrication_flags():
    """essay-review step 7 MUST document the five fabrication-class
    critical flags (9–13) as conditional on the corpus tier, additive."""
    text = _read(COMMANDS / "essay-review.md")
    for flag in (
        "fabricated_quote",
        "fabricated_fact",
        "misattribution_of_substance",
        "anachronism",
        "unattributed_paraphrase",
    ):
        assert flag in text, (
            f"essay-review MUST name the {flag} fabrication-class critical "
            f"flag (§Section 6, flags 9–13)"
        )
    assert "flags 9–13" in text or "flags 9-13" in text, (
        "essay-review MUST label the fabrication-class flags as 9–13"
    )


def test_review_rubric_total_unchanged():
    """The additive flags MUST NOT change the rubric total (/44) or the
    advance threshold (35) — the per-review stamps are unchanged."""
    text = _read(COMMANDS / "essay-review.md")
    assert "rubric_total: 44" in text, (
        "essay-review MUST keep rubric_total: 44 (the fabrication flags "
        "are additive, not a rubric change)"
    )
    assert "advance_threshold: 35" in text, (
        "essay-review MUST keep advance_threshold: 35"
    )
    # Guard against a smuggled 10th dimension row in the scoring table.
    assert "| 10 |" not in text, (
        "essay-review MUST NOT introduce a 10th rubric dimension row — "
        "the fabrication flags are critical flags, not a new dimension"
    )


def test_review_bounds_substance_to_provenance_tier():
    """essay-review MUST bound substance verification to the provenance
    tier (flag 12), NOT the voice-identity Misattribution flag 8."""
    text = _read(COMMANDS / "essay-review.md")
    assert "misattribution_of_substance" in text, (
        "essay-review MUST name misattribution_of_substance as the "
        "substance-level flag (distinct from flag 8's voice identity)"
    )
    # The NOT-do note must contrast the two misattribution surfaces.
    assert "voice-identity" in text, (
        "essay-review MUST distinguish the voice-identity Misattribution "
        "flag 8 from substance-level misattribution"
    )


def test_revise_copies_provenance_forward():
    """essay-revise step 5 MUST copy provenance.md forward into each new
    version dir, updated to match the revised prose."""
    text = _read(COMMANDS / "essay-revise.md")
    assert "Copy it forward" in text or "copy it forward" in text.lower(), (
        "essay-revise MUST copy provenance.md forward into the new "
        "version dir (§Section 2 reviser discipline)"
    )
    assert "corpus_dirs_resolved" in text, (
        "essay-revise MUST carry forward metadata.corpus_dirs_resolved "
        "in the new _progress.json"
    )


@pytest.mark.parametrize("exempt", EXEMPT_FILES)
def test_read_only_files_are_exempt(exempt: str):
    """Read-only / non-executable files MUST NOT adopt the contract —
    the orchestrator is exempt by definition."""
    text = _read(COMMANDS / exempt)
    assert "snippets/provenance.md" not in text
    assert "resolve_corpus_dirs" not in text


def test_no_lib_changes_scope_guard():
    """Scope guard (issue #611 AC): the provenance adoption is command-
    file only — no lib file mentions the essay-specific progress key.
    The contract terms live in the snippet + command files, never in the
    resolver / schema / verdict lib modules edited by this issue."""
    for lib_name in (
        "review_schema.py",
        "critics.py",
    ):
        lib_text = _read(REPO_ROOT / "anvil" / "lib" / lib_name)
        assert "corpus_dirs_resolved" not in lib_text, (
            f"anvil/lib/{lib_name} MUST NOT reference corpus_dirs_resolved "
            f"— issue #611 is command-file adoption only, zero lib changes"
        )
