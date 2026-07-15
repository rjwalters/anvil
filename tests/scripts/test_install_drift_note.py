"""Regression test: ``install-anvil.sh`` drift-detection note on subset installs.

Issue #239: when a consumer re-runs ``install-anvil.sh --skills=<old subset>``
to upgrade an existing install, the installer silently honors the documented
subset and never surfaces that upstream has shipped additional skills. The
documented `--skills=` subset becomes the consumer's canonical upgrade
invocation; the installer never reports the gap between the active selection
and the source-side `ALL_SKILLS[@]` enumeration.

The fix (Option A of the issue body) adds a drift-detection ``note:`` block
to the Stage 11 summary when ``SELECTED_SKILLS`` is a strict subset of
``ALL_SKILLS``::

    note: N anvil skills available beyond your selection:
          <skill1>, <skill2>, ...
    note: to install all available skills, re-run without --skills=
          (recommended for upgrades).

Quiet-path discipline: when no ``--skills=`` flag is passed (or the flag
covers every available skill), the drift note must NOT fire. The signal is
computed from the active selection vs the source enumeration, not from the
manifest's ``installed_skills`` (which exhibits the same staleness as the
docs the drift note is trying to counteract).

The companion fix (Option C) updates the ``ANVIL_POINTER`` line written into
the consumer's CLAUDE.md to mention the no-flag invocation as the canonical
upgrade form, with ``--skills=`` reframed as the subset-pinning escape
hatch.

These tests exercise the installer end-to-end via ``subprocess`` so the
drift-detection contract is enforced at the real entry point a consumer
would hit, mirroring the pattern from ``test_install_skills_validation.py``
(#82) and ``test_install_dry_run_honesty.py`` (#81).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"
SKILLS_DIR = REPO_ROOT / "anvil" / "skills"

DRIFT_NOTE_FRAGMENT = "anvil skills available beyond your selection"
DRIFT_RECOMMEND_FRAGMENT = "re-run without --skills="

# Always-on skills (#728) are unioned into SELECTED_SKILLS after the --skills=
# filter, so they are never part of the "available beyond your selection"
# drift enumeration even under a strict subset. Mirror the installer's
# ALWAYS_ON_SKILLS allowlist here so the missing-skill delta stays exact.
ALWAYS_ON_SKILLS = {"help"}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the installer with ``args`` and capture text stdout+stderr."""

    return subprocess.run(
        ["bash", str(INSTALLER), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _discover_all_skills() -> list[str]:
    """Enumerate the source-side ``ALL_SKILLS[@]`` from the repo layout.

    Mirrors the installer's Stage 4 logic (find ``SKILL.md`` two levels deep
    under ``anvil/skills``) so the test stays in sync as new skills are added
    without needing to be edited.
    """

    assert SKILLS_DIR.is_dir(), f"missing skills dir: {SKILLS_DIR}"
    skills = sorted(
        child.name
        for child in SKILLS_DIR.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    )
    assert skills, f"no skills discovered under {SKILLS_DIR}"
    return skills


def test_skills_subset_emits_drift_note(tmp_path: Path) -> None:
    """A strict-subset selection (``--skills=memo``) emits the drift note.

    Confirms the drift detection fires when the install is a strict subset
    of the source-side ``ALL_SKILLS[@]`` enumeration. The note must include
    the headline literal, name the missing skills (at least ``proposal`` and
    ``deck`` are guaranteed by the v0.1.0 ship set), and recommend the
    no-flag invocation.
    """

    target = tmp_path / "subset-drift-target"
    target.mkdir()

    result = _run("--dry-run", "--skills=memo", str(target))

    assert result.returncode == 0, (
        f"--dry-run --skills=memo should succeed but exited "
        f"{result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert DRIFT_NOTE_FRAGMENT in result.stdout, (
        f"drift note headline {DRIFT_NOTE_FRAGMENT!r} missing from stdout:\n"
        f"{result.stdout}"
    )
    assert DRIFT_RECOMMEND_FRAGMENT in result.stdout, (
        f"drift note recommendation {DRIFT_RECOMMEND_FRAGMENT!r} missing "
        f"from stdout:\n{result.stdout}"
    )
    # The note must enumerate the skills that are NOT in the selection. The
    # v0.1.0 ship set includes proposal/deck; both must appear when only memo
    # is selected.
    assert "proposal" in result.stdout, (
        f"missing-skill 'proposal' absent from drift note; stdout:\n"
        f"{result.stdout}"
    )
    assert "deck" in result.stdout, (
        f"missing-skill 'deck' absent from drift note; stdout:\n"
        f"{result.stdout}"
    )


def test_no_skills_flag_emits_no_drift_note(tmp_path: Path) -> None:
    """No ``--skills=`` flag means no drift note (quiet path stays quiet).

    Pins the discipline that the drift signal is gated on the strict-subset
    condition, not on flag presence. The default invocation already installs
    all skills, so there is no gap to surface and the note must stay silent.
    """

    target = tmp_path / "no-flag-drift-target"
    target.mkdir()

    result = _run("--dry-run", str(target))

    assert result.returncode == 0, (
        f"--dry-run should succeed but exited {result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert DRIFT_NOTE_FRAGMENT not in result.stdout, (
        f"drift note fired on no-flag invocation (quiet path violated); "
        f"stdout:\n{result.stdout}"
    )


def test_skills_equals_all_emits_no_drift_note(tmp_path: Path) -> None:
    """``--skills=<all skills>`` (set equality) emits no drift note.

    The comparison must use set equality between ``SELECTED_SKILLS`` and
    ``ALL_SKILLS``, not flag presence. Discovers the live skill set from the
    repo so the test stays in sync as new skills are added.
    """

    target = tmp_path / "all-explicit-drift-target"
    target.mkdir()

    all_skills = _discover_all_skills()
    skills_flag = "--skills=" + ",".join(all_skills)

    result = _run("--dry-run", skills_flag, str(target))

    assert result.returncode == 0, (
        f"--dry-run {skills_flag} should succeed but exited "
        f"{result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert DRIFT_NOTE_FRAGMENT not in result.stdout, (
        f"drift note fired despite --skills= covering every available skill "
        f"({all_skills!r}); set-equality comparison violated; stdout:\n"
        f"{result.stdout}"
    )


def test_drift_note_lists_missing_skills_alphabetically(tmp_path: Path) -> None:
    """The missing-skill enumeration in the drift note is alpha-sorted.

    Determinism check: regardless of the order the user supplied ``--skills=``
    values, the missing-skill list in the note must come out in alpha order.
    The installer's Stage 4 ``sort -z`` is the source of truth; iterating
    ``ALL_SKILLS`` to build the delta preserves that order, so the assertion
    pins the contract end-to-end.
    """

    target = tmp_path / "alpha-drift-target"
    target.mkdir()

    # Pass skills in non-alpha order to make sure the note's ordering is not
    # influenced by the user's input order.
    result = _run("--dry-run", "--skills=memo,deck", str(target))

    assert result.returncode == 0, (
        f"--dry-run --skills=memo,deck should succeed but exited "
        f"{result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert DRIFT_NOTE_FRAGMENT in result.stdout, (
        f"drift note headline missing; stdout:\n{result.stdout}"
    )

    # Locate the line carrying the missing-skill enumeration. The installer
    # emits it on the line that follows the headline ``available beyond your
    # selection:`` line, prefixed by the standard ``note:`` formatting.
    lines = result.stdout.splitlines()
    headline_idx = None
    for idx, line in enumerate(lines):
        if DRIFT_NOTE_FRAGMENT in line:
            headline_idx = idx
            break
    assert headline_idx is not None, (
        f"could not locate drift-note headline in stdout:\n{result.stdout}"
    )
    assert headline_idx + 1 < len(lines), (
        f"drift-note headline is the last line — no enumeration line:\n"
        f"{result.stdout}"
    )
    enumeration_line = lines[headline_idx + 1]
    # Strip ANSI color codes and the ``note:`` prefix so what's left is the
    # space-separated skill list.
    ansi_re = re.compile(r"\x1b\[[0-9;]*m")
    plain = ansi_re.sub("", enumeration_line).strip()
    # Drop the leading ``note:`` token if present.
    if plain.startswith("note:"):
        plain = plain[len("note:") :].strip()
    listed = plain.split()
    assert listed == sorted(listed), (
        f"missing-skill list is not alpha-sorted; got {listed!r} on line:\n"
        f"{enumeration_line!r}\nfull stdout:\n{result.stdout}"
    )
    # Sanity check: the listed skills must be ALL_SKILLS minus the selected
    # pair {memo, deck} AND minus the always-on carve-out (#728), which is
    # unioned into SELECTED_SKILLS and so never appears as "missing".
    expected_missing = sorted(
        set(_discover_all_skills()) - {"memo", "deck"} - ALWAYS_ON_SKILLS
    )
    assert listed == expected_missing, (
        f"missing-skill list does not match expected delta; got {listed!r}, "
        f"expected {expected_missing!r}; full stdout:\n{result.stdout}"
    )


def test_drift_note_fires_under_dry_run(tmp_path: Path) -> None:
    """``--dry-run`` does not suppress the drift note.

    Explicit pin per the issue body: the drift signal is part of the
    operator UX even on dry-run pre-flight (so an operator can see "you'd
    be missing X skills if you ran this for real" without committing to
    the filesystem mutation).
    """

    target = tmp_path / "dry-run-drift-target"
    target.mkdir()

    result = _run("--dry-run", "--skills=memo", str(target))

    assert result.returncode == 0, (
        f"--dry-run --skills=memo should succeed but exited "
        f"{result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    # Both the drift note and the trailing DRY-RUN warning must coexist —
    # dry-run does not suppress the drift signal.
    assert DRIFT_NOTE_FRAGMENT in result.stdout, (
        f"drift note suppressed under --dry-run; stdout:\n{result.stdout}"
    )
    assert "DRY-RUN: no files were written" in result.stdout, (
        f"missing dry-run warning (sanity check that dry-run actually "
        f"ran); stdout:\n{result.stdout}"
    )


def test_anvil_pointer_mentions_upgrade_pattern() -> None:
    """The ``ANVIL_POINTER`` prose in the installer mentions the upgrade form.

    Option C from issue #239: the additive CLAUDE.md block written into
    consumer repos must steer any future reader toward the no-flag
    invocation as the canonical upgrade form. The exact prose is owned by
    the implementer; the invariant is that ``--skills=`` is reframed as the
    subset-pinning escape hatch (not the upgrade default).

    Lightweight static-source assertion — no subprocess needed.
    """

    text = INSTALLER.read_text(encoding="utf-8")
    pointer_lines = [
        line for line in text.splitlines() if line.startswith("ANVIL_POINTER=")
    ]
    assert len(pointer_lines) == 1, (
        f"expected exactly one ANVIL_POINTER= line in installer; got "
        f"{len(pointer_lines)}: {pointer_lines!r}"
    )
    pointer = pointer_lines[0]
    # The upgrade hint must mention either the no-flag re-run pattern or the
    # subset framing of --skills=. The literal "without `--skills=`" pins the
    # invariant most tightly because that's the prose contract the issue
    # body calls out.
    assert "without `--skills=`" in pointer, (
        f"ANVIL_POINTER does not mention the 'without --skills=' upgrade "
        f"pattern; line:\n{pointer}"
    )
    # And the subset framing must be present so a reader can tell what
    # `--skills=` IS for, post-reframe.
    assert "strict subset" in pointer, (
        f"ANVIL_POINTER does not reframe --skills= as the subset-pinning "
        f"escape hatch; line:\n{pointer}"
    )
