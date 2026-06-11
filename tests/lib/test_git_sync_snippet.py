"""Snippet-content smoke tests for the per-phase git commit/sync hook
contract (issue #426).

Per the issue #426 test plan: cheap "grep-the-doc" tests (precedent:
``tests/lib/test_snippet_contents.py``, #29) that the load-bearing
strings of the opt-in git-sync contract stay in
``anvil/lib/snippets/git_sync.md`` and its index/scaffold consumers, and
don't drift in a later prose edit.

These tests assert on substring presence only — they do NOT validate
prose quality or structure.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SNIPPET = REPO_ROOT / "anvil" / "lib" / "snippets" / "git_sync.md"
LIB_README = REPO_ROOT / "anvil" / "lib" / "README.md"
SKILL_TEMPLATE = REPO_ROOT / "anvil" / "templates" / "SKILL.md"
CONSUMER_README = REPO_ROOT / "README.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# git_sync.md (new)
# ---------------------------------------------------------------------------


def test_git_sync_snippet_exists():
    assert SNIPPET.exists(), (
        "anvil/lib/snippets/git_sync.md MUST exist per issue #426 AC1"
    )


def test_git_sync_snippet_names_config_locus():
    body = _read(SNIPPET)
    assert ".anvil/config.json" in body, (
        "git_sync.md MUST name the repo-level .anvil/config.json knob locus"
    )


def test_git_sync_snippet_names_both_knobs():
    body = _read(SNIPPET)
    assert "commit_per_phase" in body, (
        "git_sync.md MUST name the git.commit_per_phase knob"
    )
    assert "push" in body, (
        "git_sync.md MUST name the separate git.push sub-knob"
    )


def test_git_sync_snippet_documents_commit_message_shape():
    body = _read(SNIPPET)
    assert "anvil(<skill>/<phase>):" in body, (
        "git_sync.md MUST document the structured commit-message shape "
        "anvil(<skill>/<phase>): <thread>.{N} [<resulting-state>]"
    )
    assert "<thread>.{N}" in body
    assert "[<resulting-state>]" in body or "[<state>]" in body


def test_git_sync_snippet_is_default_off():
    body = _read(SNIPPET).lower()
    assert "default" in body, "git_sync.md MUST state the default"
    assert "off" in body, "git_sync.md MUST state the hook is off by default"
    assert "absent" in body, (
        "git_sync.md MUST state that an absent config means the knob is off"
    )


def test_git_sync_snippet_documents_warn_and_continue():
    """Git failures MUST NOT fail the phase — warn-and-continue is the
    load-bearing failure rule (issue #426 design decision 4)."""
    body = _read(SNIPPET).lower()
    assert "warn" in body
    assert "continue" in body
    assert "source of truth" in body, (
        "git_sync.md MUST state artifact-on-disk is the source of truth"
    )


def test_git_sync_snippet_documents_staging_scope():
    """Stage only the dirs the phase wrote — never git add -A."""
    body = _read(SNIPPET)
    assert "git add -A" in body, (
        "git_sync.md MUST explicitly forbid `git add -A`"
    )


def test_git_sync_snippet_documents_ordering_contract():
    """The hook fires after the _progress.json done write and after the
    #350 staged-sidecar atomic rename."""
    body = _read(SNIPPET)
    assert "_progress.json" in body
    assert "#350" in body
    assert "sidecar" in body
    assert "rename" in body


def test_git_sync_snippet_documents_read_only_exemption():
    body = _read(SNIPPET)
    assert "Read-only" in body or "read-only" in body, (
        "git_sync.md MUST exempt read-only commands from the contract"
    )
    assert "project-scout" in body


def test_git_sync_snippet_does_not_overload_install_metadata():
    """install-metadata.json stays provenance-only (curated decision 1)."""
    body = _read(SNIPPET)
    assert "install-metadata.json" in body
    assert "provenance" in body


def test_git_sync_snippet_notes_brief_override_out_of_scope():
    """A per-project BRIEF override is a possible future extension,
    explicitly out of scope for v1."""
    body = _read(SNIPPET)
    assert "BRIEF" in body
    assert "out of scope" in body


# ---------------------------------------------------------------------------
# anvil/lib/README.md index
# ---------------------------------------------------------------------------


def test_lib_readme_indexes_git_sync_snippet():
    body = _read(LIB_README)
    assert "git_sync.md" in body, (
        "anvil/lib/README.md MUST index the git_sync.md snippet "
        "(issue #426 AC2)"
    )
    assert "commit_per_phase" in body


# ---------------------------------------------------------------------------
# templates/SKILL.md scaffold note
# ---------------------------------------------------------------------------


def test_skill_template_carries_git_sync_convention():
    body = _read(SKILL_TEMPLATE)
    assert "snippets/git_sync.md" in body, (
        "templates/SKILL.md MUST cross-reference snippets/git_sync.md so "
        "new skills inherit the convention (issue #426 affected files)"
    )
    assert "commit_per_phase" in body


# ---------------------------------------------------------------------------
# consumer-facing README.md note
# ---------------------------------------------------------------------------


def test_consumer_readme_has_external_orchestrator_note():
    body = _read(CONSUMER_README)
    assert "external orchestrator" in body, (
        "README.md MUST carry the 'running under an external orchestrator' "
        "consumer note (issue #426 AC6)"
    )
    assert "commit_per_phase" in body
    assert ".anvil/config.json" in body
