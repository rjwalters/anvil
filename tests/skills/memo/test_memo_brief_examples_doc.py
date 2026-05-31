"""Doc-coverage smoke tests for the memo BRIEF.md example templates.

Per issue #136 acceptance criteria: cheap "grep-the-doc" regression guard
that the two shipped BRIEF.md example shapes (fresh-thread and
migration-from-prior-pipeline) stay on disk and stay referenced from
SKILL.md. This prevents future drift where someone deletes an example
without updating SKILL.md (or vice versa).

These tests assert on file existence and substring presence only — they
do NOT validate prose quality or structure. The example bodies themselves
are evaluated by humans.

Per-skill test filename convention (#58): this file is named with a
``test_memo_`` prefix so it never collides with a similarly-shaped
``test_brief_examples_doc`` another skill might pick.
"""

from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
TEMPLATES_DIR = SKILL_ROOT / "templates"
FRESH_EXAMPLE = TEMPLATES_DIR / "BRIEF.fresh.md.example"
MIGRATION_EXAMPLE = TEMPLATES_DIR / "BRIEF.migration.md.example"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Files exist on disk
# ---------------------------------------------------------------------------


def test_fresh_example_exists():
    assert FRESH_EXAMPLE.is_file(), (
        f"memo skill MUST ship a fresh-thread BRIEF.md example at "
        f"{FRESH_EXAMPLE.relative_to(SKILL_ROOT.parents[1])} (issue #136 AC1)"
    )


def test_migration_example_exists():
    assert MIGRATION_EXAMPLE.is_file(), (
        f"memo skill MUST ship a migration-from-prior-pipeline BRIEF.md "
        f"example at {MIGRATION_EXAMPLE.relative_to(SKILL_ROOT.parents[1])} "
        f"(issue #136 AC2)"
    )


def test_both_examples_are_nonempty():
    # Plausible / decision-useful prose, not stubs. We don't grade the
    # content here, but an empty file is an obvious regression.
    assert FRESH_EXAMPLE.stat().st_size > 500, (
        "fresh-thread BRIEF example must be non-trivial prose, not a stub"
    )
    assert MIGRATION_EXAMPLE.stat().st_size > 500, (
        "migration BRIEF example must be non-trivial prose, not a stub"
    )


# ---------------------------------------------------------------------------
# SKILL.md references both files by name
# ---------------------------------------------------------------------------


def test_skill_md_references_fresh_example():
    body = _read(SKILL_MD)
    assert "BRIEF.fresh.md.example" in body, (
        "SKILL.md MUST reference the fresh-thread BRIEF example by filename "
        "(issue #136 AC4)"
    )


def test_skill_md_references_migration_example():
    body = _read(SKILL_MD)
    assert "BRIEF.migration.md.example" in body, (
        "SKILL.md MUST reference the migration BRIEF example by filename "
        "(issue #136 AC4)"
    )


def test_skill_md_does_not_reference_stale_singular_example():
    # The pre-#136 SKILL.md listed a singular `BRIEF.md.example` that did
    # not exist. Guard against regression to that stale reference.
    body = _read(SKILL_MD)
    # Allow the substring inside the longer filenames, but not as a
    # standalone reference. A simple heuristic: if `BRIEF.md.example`
    # appears, it must be inside one of the two real filenames.
    if "BRIEF.md.example" in body:
        # Strip the real filenames and re-check.
        stripped = body.replace("BRIEF.fresh.md.example", "").replace(
            "BRIEF.migration.md.example", ""
        )
        assert "BRIEF.md.example" not in stripped, (
            "SKILL.md still references the stale singular `BRIEF.md.example` "
            "filename; it should reference both BRIEF.fresh.md.example and "
            "BRIEF.migration.md.example (issue #136)"
        )


# ---------------------------------------------------------------------------
# Example shape sanity — content guidance from issue #136
# ---------------------------------------------------------------------------


def test_fresh_example_has_load_bearing_questions_section():
    # Per #136 content guidance: fresh-thread brief includes a "What the
    # memo must establish" load-bearing-questions checklist.
    body = _read(FRESH_EXAMPLE)
    assert "What the memo must establish" in body, (
        "fresh-thread BRIEF example MUST include the "
        "'What the memo must establish' section (issue #136 content guidance)"
    )


def test_fresh_example_has_undecided_default():
    # Per #136: recommendation_target: undecided is the documented default
    # for fresh threads. The example must demonstrate it.
    body = _read(FRESH_EXAMPLE)
    assert "recommendation_target: undecided" in body, (
        "fresh-thread BRIEF example MUST show recommendation_target: undecided "
        "as the default for new threads (issue #136 content guidance)"
    )


def test_migration_example_has_read_order_section():
    # Per #136 content guidance: migration brief includes a Source material
    # read-order section (this is the key shape that distinguishes it from
    # the fresh-thread brief).
    body = _read(MIGRATION_EXAMPLE)
    assert "read order" in body.lower(), (
        "migration BRIEF example MUST include a 'read order' section "
        "(issue #136 content guidance — this is the key shape difference "
        "from the fresh-thread brief)"
    )


def test_migration_example_has_forward_planning_section():
    # Per #136 content guidance: migration brief includes a "What v(N+1)
    # will tighten" forward-planning placeholder.
    body = _read(MIGRATION_EXAMPLE)
    assert "tighten" in body.lower(), (
        "migration BRIEF example MUST include a 'What v(N+1) will tighten' "
        "forward-planning section (issue #136 content guidance)"
    )
