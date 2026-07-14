"""Doc-coverage smoke tests for the paper-draft BRIEF bootstrap interview.

Per issue #425 acceptance criteria: cheap "grep-the-doc" regression
guard that the interview-driven BRIEF bootstrap (the greenfield-thread
analog of project-migrate's #408 starter-BRIEF synthesis) stays
documented in the two files it touches (commands/paper-draft.md and
SKILL.md) and that the load-bearing safeguards survive:

- the four mandatory interview topics (venue, thesis/claim, evidence
  inventory, scope);
- the non-interactive fail-fast with the deterministic ``--no-interview``
  opt-out (precedent: report-promote's interactive-prompt vs --ack-file
  split);
- the ``# TODO(operator)`` marker discipline and the no-fabrication
  rule (skipped answers are marked, never invented);
- the ``web_search`` explicit-opt-in-only posture (#424 / PR #437);
- the lifecycle-unchanged contract (no new state, no _progress.json
  schema change) and the project-BRIEF scope exclusion.

These tests assert on substring presence only — they do NOT validate
prose quality or interview behaviour. The command itself is LLM-driven,
so behavioural assertions belong in consumer-side integration tests,
not here.

Per-skill test filename convention (#58): this file carries the
``test_paper_`` prefix so it never collides with doc tests of other
skills.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "anvil" / "skills" / "paper"
SKILL_MD = SKILL_ROOT / "SKILL.md"
DRAFT_MD = SKILL_ROOT / "commands" / "paper-draft.md"
EXAMPLE_BRIEF = SKILL_ROOT / "assets" / "example-brief.md"
PROJECT_MIGRATE_MD = (
    REPO_ROOT
    / "anvil"
    / "skills"
    / "project-migrate"
    / "commands"
    / "project-migrate.md"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# paper-draft.md — interview path (new in #425)
# ---------------------------------------------------------------------------


def test_paper_draft_documents_bootstrap_interview_section():
    body = _read(DRAFT_MD)
    assert "BRIEF bootstrap interview" in body, (
        "paper-draft.md MUST have a 'BRIEF bootstrap interview' section per "
        "issue #425 AC"
    )


def test_paper_draft_step3_branches_on_interactivity():
    body = _read(DRAFT_MD)
    lowered = body.lower()
    assert "interactive" in lowered, (
        "paper-draft.md step 3 MUST branch on interactivity (interview when "
        "interactive, fail-fast when not) per issue #425 AC"
    )
    assert "non-interactive" in lowered, (
        "paper-draft.md MUST document the non-interactive fail-fast branch"
    )
    assert "fail fast" in lowered or "fail-fast" in lowered, (
        "paper-draft.md MUST preserve fail-fast behavior for non-interactive "
        "runs (issue #425 AC)"
    )


def test_paper_draft_documents_no_interview_flag():
    body = _read(DRAFT_MD)
    assert "--no-interview" in body, (
        "paper-draft.md MUST document the deterministic --no-interview opt-out "
        "(issue #425 AC; precedent: report-promote's --ack-file split)"
    )
    assert "report-promote" in body, (
        "paper-draft.md SHOULD cite the report-promote interactive-vs-flag "
        "precedent the --no-interview opt-out mirrors"
    )


def test_paper_draft_documents_four_mandatory_question_topics():
    body = _read(DRAFT_MD)
    lowered = body.lower()
    # The four mandatory interview topics per the curator question set.
    assert "venue" in lowered, (
        "paper-draft.md interview MUST cover the target venue (mandatory topic)"
    )
    assert "thesis" in lowered or "claim" in lowered, (
        "paper-draft.md interview MUST cover the thesis / claim (mandatory topic)"
    )
    assert "evidence inventory" in lowered, (
        "paper-draft.md interview MUST cover the evidence inventory "
        "(mandatory topic)"
    )
    assert "scope" in lowered, (
        "paper-draft.md interview MUST cover scope (audience / length / "
        "double-blind / keywords) (mandatory topic)"
    )


def test_paper_draft_documents_optional_title_authors_question():
    body = _read(DRAFT_MD)
    lowered = body.lower()
    assert "title" in lowered and "author" in lowered, (
        "paper-draft.md interview MUST list title / authors / affiliation as "
        "an optional question (issue #425 curator question set)"
    )


def test_paper_draft_synthesized_brief_requires_venue_and_claim_frontmatter():
    body = _read(DRAFT_MD)
    # The two inputs step 3 declares mandatory must be named as the
    # frontmatter minimum of the synthesized brief.
    assert "`venue` + `claim`" in body or "venue + claim" in body, (
        "paper-draft.md MUST require frontmatter venue + claim at minimum in "
        "the synthesized BRIEF (issue #425 AC)"
    )


def test_paper_draft_synthesized_brief_mirrors_example_brief_shape():
    body = _read(DRAFT_MD)
    assert "example-brief.md" in body, (
        "paper-draft.md MUST point at assets/example-brief.md as the "
        "synthesized-BRIEF shape reference (issue #425 AC)"
    )
    # The example-brief prose section shape must be named.
    assert "Motivation" in body, (
        "paper-draft.md MUST name the Motivation prose section of the "
        "synthesized BRIEF"
    )
    assert "Related work" in body or "Related-work" in body, (
        "paper-draft.md MUST name the related-work hooks section of the "
        "synthesized BRIEF"
    )


def test_paper_draft_documents_todo_operator_markers():
    body = _read(DRAFT_MD)
    assert "# TODO(operator)" in body, (
        "paper-draft.md MUST document the # TODO(operator) marker discipline "
        "for skipped answers (issue #425 AC; #408 project-migrate precedent)"
    )
    assert "project-migrate" in body or "#408" in body, (
        "paper-draft.md SHOULD cite the #408 project-migrate starter-synthesis "
        "precedent for the TODO-marker discipline"
    )


def test_paper_draft_documents_no_fabrication_rule():
    body = _read(DRAFT_MD)
    lowered = body.lower()
    assert "never fabricated" in lowered or "no-fabrication" in lowered or (
        "no fabrication" in lowered
    ), (
        "paper-draft.md MUST document the no-fabrication rule for the interview "
        "(issue #425 AC)"
    )
    assert "MUST NOT invent" in body or "never invent" in body.lower(), (
        "paper-draft.md MUST use normative language: the drafter never invents "
        "evidence, results, or citations to fill interview gaps"
    )


def test_paper_draft_web_search_is_explicit_opt_in_only():
    body = _read(DRAFT_MD)
    assert "web_search" in body, (
        "paper-draft.md interview MUST cover the web-search appetite question "
        "(issue #425 curator question set)"
    )
    lowered = body.lower()
    assert "opt-in" in lowered, (
        "paper-draft.md MUST state web_search is emitted on explicit opt-in "
        "only (preserves the #424/#437 off-by-default posture)"
    )
    assert "omitted otherwise" in lowered or "omit otherwise" in lowered or (
        "the key is omitted" in lowered
    ), (
        "paper-draft.md MUST state the web_search key is omitted when the "
        "author does not opt in (no key, not web_search: false ambiguity)"
    )


def test_paper_draft_fail_fast_message_names_both_remedies():
    body = _read(DRAFT_MD)
    lowered = body.lower()
    # AC: the fail-fast error message names both remedies — write by hand,
    # or re-run interactively.
    assert "by hand" in lowered, (
        "paper-draft.md MUST document remedy (a): write <thread>/BRIEF.md by "
        "hand (issue #425 AC)"
    )
    assert "re-run" in lowered and "interactively" in lowered, (
        "paper-draft.md MUST document remedy (b): re-run paper-draft "
        "interactively for the interview path (issue #425 AC)"
    )


def test_paper_draft_lifecycle_unchanged_after_bootstrap():
    body = _read(DRAFT_MD)
    lowered = body.lower()
    assert "no new state" in lowered, (
        "paper-draft.md MUST state the lifecycle is unchanged post-bootstrap: "
        "no new states (issue #425 AC)"
    )
    assert "_progress.json" in body, (
        "paper-draft.md MUST state there is no _progress.json schema change "
        "(the interview happens before step 4 initializes progress)"
    )


def test_paper_draft_existing_brief_never_interviewed():
    body = _read(DRAFT_MD)
    lowered = body.lower()
    assert "never fires" in lowered or "unchanged" in lowered, (
        "paper-draft.md MUST state the interview never fires when BRIEF.md "
        "exists (issue #425 edge case: existing-brief path is unchanged)"
    )


def test_paper_draft_documents_project_brief_scope_exclusion():
    body = _read(DRAFT_MD)
    # Curator decision 4: no interplay with the post-#295 project-BRIEF
    # documents: entry; enrollment stays project-migrate --enroll territory.
    assert "per-thread" in body.lower(), (
        "paper-draft.md MUST scope the interview to the per-thread BRIEF only"
    )
    assert "--enroll" in body or "project-migrate" in body, (
        "paper-draft.md MUST note project-layout enrollment stays "
        "anvil:project-migrate --enroll territory (issue #425 scope exclusion)"
    )
    assert "documents:" in body, (
        "paper-draft.md MUST explicitly exclude the project-BRIEF documents: "
        "interplay (issue #425 curator decision 4)"
    )


def test_paper_draft_notes_per_thread_brief_has_no_strict_parser():
    body = _read(DRAFT_MD)
    lowered = body.lower()
    assert "no strict parser" in lowered, (
        "paper-draft.md MUST note the per-thread BRIEF has no strict parser "
        "(the strict parser governs the project-level BRIEF only)"
    )


# ---------------------------------------------------------------------------
# SKILL.md — cross-references (issue #425 AC)
# ---------------------------------------------------------------------------


def test_skill_md_artifact_contract_mentions_bootstrap():
    body = _read(SKILL_MD)
    pos = body.find("BRIEF.md ")
    assert pos > -1
    # The artifact-contract BRIEF.md line must mention the interview
    # bootstrap; look in the surrounding diagram block.
    block = body[pos : pos + 500]
    assert "interview" in block.lower(), (
        "paper SKILL.md artifact-contract BRIEF.md line MUST mention the "
        "paper-draft interview bootstrap (issue #425 AC)"
    )


def test_skill_md_command_table_row_mentions_bootstrap():
    body = _read(SKILL_MD)
    row = next(
        (
            line
            for line in body.splitlines()
            if line.startswith("| `paper-draft <thread>`")
        ),
        None,
    )
    assert row is not None, (
        "paper SKILL.md command-dispatch table MUST still have a paper-draft row"
    )
    assert "interview" in row.lower(), (
        "paper SKILL.md paper-draft command-table row MUST mention the BRIEF "
        "bootstrap interview (issue #425 AC)"
    )
    assert "--no-interview" in row, (
        "paper SKILL.md paper-draft command-table row MUST mention the "
        "--no-interview fail-fast opt-out"
    )


def test_skill_md_preserves_web_search_default_off():
    body = _read(SKILL_MD)
    # Backwards-compat guard: the #424 opt-in web-search section survives;
    # the interview must not have changed the default.
    assert "web_search: true" in body, (
        "paper SKILL.md MUST preserve the opt-in web_search section (#424)"
    )
    assert "default `false`" in body, (
        "paper SKILL.md MUST preserve the web_search default-off posture"
    )


def test_skill_md_preserves_lifecycle_line():
    body = _read(SKILL_MD)
    # The pub lifecycle must survive unchanged — the interview is not a
    # phase (issue #425 AC: lifecycle unchanged post-bootstrap).
    assert "draft → review → revise → audit → figures" in body, (
        "paper SKILL.md MUST preserve the unchanged paper lifecycle — the "
        "bootstrap interview MUST NOT be added as a phase (issue #425 AC)"
    )


# ---------------------------------------------------------------------------
# Cross-file guards
# ---------------------------------------------------------------------------


def test_example_brief_reference_still_exists():
    """Guard: the synthesized-BRIEF shape reference lives at
    assets/example-brief.md. If it disappears, the interview docs dangle."""
    assert EXAMPLE_BRIEF.exists(), (
        "anvil/skills/paper/assets/example-brief.md MUST exist as the "
        "synthesized-BRIEF shape reference (issue #425 AC)"
    )
    brief = _read(EXAMPLE_BRIEF)
    # The two mandatory frontmatter keys must be demonstrated by the example.
    assert "venue:" in brief and "claim:" in brief, (
        "example-brief.md MUST demonstrate the venue + claim frontmatter "
        "keys the interview treats as mandatory"
    )


def test_project_migrate_todo_marker_precedent_still_exists():
    """Guard: the #408 starter-synthesis TODO-marker precedent paper-draft.md
    cites lives in project-migrate.md. If it disappears, the docs
    cross-reference dangles."""
    assert PROJECT_MIGRATE_MD.exists(), (
        "anvil/skills/project-migrate/commands/project-migrate.md MUST exist "
        "as the cited #408 precedent"
    )
    assert "# TODO(operator)" in _read(PROJECT_MIGRATE_MD), (
        "project-migrate.md MUST still document the # TODO(operator) marker "
        "discipline paper-draft's interview inherits (issue #425 / #408)"
    )
