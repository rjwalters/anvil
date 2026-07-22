"""Regression tests: installer seeds a root-``.gitignore`` rule for the
regenerable vision render intermediates (issue #738).

The four vision critics (``paper``, ``report``, ``deck``, ``slides``) render
per-page/per-slide PNGs INTO their committed critic sibling dir —
``<thread>.{N}.vision/pages/`` (paper, report) or ``<thread>.{N}.vision/slides/``
(deck, slides). Unlike every other critic sibling (``.review``/``.audit``, which
carry only ~8 KB of markdown/JSON), the vision sibling co-locates megabytes of
PNGs that are pure output of ``render_pdf_to_pngs(pdf, out_dir, dpi)`` from a
regenerable PDF — nothing in them is canonical. A consumer who ``git add``s the
whole ``*.vision/`` dir during a hygiene pass pulls in the bloat (the geode-fem
repro: 6.5 MB of ``pages/*.png`` alongside an 8 KB manifest).

Stage 7.10 (issue #738) appends two globs to the consumer **root** ``.gitignore``
via the same ``append_to_gitignore_idempotent()`` helper used by the Stage 7.9
voice-grounding append:

  * ``**/*.vision/pages/``  — paper/report (flat sibling layout)
  * ``**/*.vision/slides/`` — deck/slides (nested ``<thread>/…`` layout)

The leading ``**`` matches both layouts and wherever the consumer runs the skill.

The write contract (mirrors Stage 7.9):

  * **Skill-gated** — fires only when at least one of ``paper``/``report``/
    ``deck``/``slides`` is in ``--skills=`` (unlike the unconditional Stage 8.6
    ``.anvil/.gitignore`` write).
  * **Idempotent** — a re-install never duplicates the lines; an existing
    covering line is detected and skipped with an honest note.
  * **Distinct ``do_action``** — ``--dry-run`` shows the append and writes
    nothing.
  * **Root ``.gitignore``** — the PNGs live outside ``.anvil/`` (wherever the
    consumer runs the skill, e.g. ``papers/…``), so the append targets
    ``$TARGET/.gitignore``, not the ``.anvil/.gitignore`` of Stage 8.6.

These tests exercise the installer via ``subprocess`` so the contract is enforced
at the real entry point. Distinct filename per the #58 packaging convention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

VISION_PATTERNS = ("**/*.vision/pages/", "**/*.vision/slides/")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"installer exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def _gitignore_lines(gi: Path) -> list[str]:
    if not gi.is_file():
        return []
    return [
        line.strip()
        for line in gi.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# ---------------------------------------------------------------------------
# A vision-capable skill selection seeds both globs in the root .gitignore
# ---------------------------------------------------------------------------


def test_vision_skill_seeds_both_globs(tmp_path: Path) -> None:
    """``--skills=paper`` appends both vision globs to the root ``.gitignore``."""
    target = tmp_path / "vision"
    target.mkdir()

    result = _run("--skills=paper", str(target))
    _assert_ok(result)

    gi = target / ".gitignore"
    assert gi.is_file(), (
        f"installer did not create a root .gitignore for a vision skill; "
        f"stdout:\n{result.stdout}"
    )
    lines = _gitignore_lines(gi)
    for pat in VISION_PATTERNS:
        assert pat in lines, f"missing vision glob {pat!r} in root .gitignore: {lines}"


def test_all_vision_skills_seed_the_globs(tmp_path: Path) -> None:
    """Every vision-capable skill (paper/report/deck/slides) triggers the append."""
    for skill in ("paper", "report", "deck", "slides"):
        target = tmp_path / skill
        target.mkdir()

        result = _run(f"--skills={skill}", str(target))
        _assert_ok(result)

        lines = _gitignore_lines(target / ".gitignore")
        for pat in VISION_PATTERNS:
            assert pat in lines, (
                f"--skills={skill}: missing vision glob {pat!r}: {lines}"
            )


# ---------------------------------------------------------------------------
# Idempotent re-install adds no duplicate lines
# ---------------------------------------------------------------------------


def test_reinstall_adds_no_duplicate_globs(tmp_path: Path) -> None:
    """A second install must not duplicate the vision globs (idempotent append)."""
    target = tmp_path / "reinstall"
    target.mkdir()

    _assert_ok(_run("--skills=paper", str(target)))
    gi = target / ".gitignore"
    first_lines = _gitignore_lines(gi)

    second = _run("--skills=paper", str(target))
    _assert_ok(second)
    second_lines = _gitignore_lines(gi)

    for pat in VISION_PATTERNS:
        assert first_lines.count(pat) == 1, (
            f"first install should write {pat!r} exactly once: {first_lines}"
        )
        assert second_lines.count(pat) == 1, (
            f"re-install duplicated {pat!r}: {second_lines}"
        )
    # The skip note fires on the re-run (honest reporting).
    assert "already ignores" in second.stdout, (
        f"expected an 'already ignores' skip note on re-install; got:\n{second.stdout}"
    )


# ---------------------------------------------------------------------------
# A non-vision skill selection does not seed the globs
# ---------------------------------------------------------------------------


def test_non_vision_skill_does_not_seed_globs(tmp_path: Path) -> None:
    """``--skills=memo`` (non-vision) must NOT append the vision globs.

    ``memo`` is voice-consuming, so Stage 7.9 may write a root ``.gitignore``
    with the voice patterns — but the vision globs must be absent because Stage
    7.10 is gated on a vision-capable skill.
    """
    target = tmp_path / "non-vision"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    lines = _gitignore_lines(target / ".gitignore")
    for pat in VISION_PATTERNS:
        assert pat not in lines, (
            f"vision glob {pat!r} leaked into a non-vision (memo) install: {lines}"
        )


# ---------------------------------------------------------------------------
# --dry-run honesty
# ---------------------------------------------------------------------------


def test_dry_run_reports_and_writes_nothing(tmp_path: Path) -> None:
    """``--dry-run`` reports the append action and writes no root ``.gitignore``."""
    target = tmp_path / "dry-run"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--skills=paper", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(result)

    assert "**/*.vision/pages/" in result.stdout, (
        f"expected the dry-run vision-glob append action; got:\n{result.stdout}"
    )
    assert not (target / ".gitignore").exists(), (
        "--dry-run wrote a root .gitignore to the target"
    )


# ---------------------------------------------------------------------------
# A pre-existing covering line is respected (no re-append, honest skip note)
# ---------------------------------------------------------------------------


def test_pre_existing_covering_line_is_respected(tmp_path: Path) -> None:
    """A consumer .gitignore that already covers a glob is not re-appended."""
    target = tmp_path / "pre-existing"
    target.mkdir()

    gi = target / ".gitignore"
    gi.write_text("# my rules\n**/*.vision/pages/\n", encoding="utf-8")

    result = _run("--skills=paper", str(target))
    _assert_ok(result)

    lines = _gitignore_lines(gi)
    assert lines.count("**/*.vision/pages/") == 1, (
        f"pre-existing pages/ glob was duplicated: {lines}"
    )
    # slides/ was not present, so it should have been appended.
    assert "**/*.vision/slides/" in lines, (
        f"the not-yet-present slides/ glob should have been appended: {lines}"
    )
