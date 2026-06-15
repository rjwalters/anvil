"""Regression tests: installer protects private voice-grounding paths (#577).

Phase B of epic #575. The personal layer of voice grounding
(``VALUES.md``-class stances) is the half a consumer often will NOT want
committed, so anvil makes private grounding a designed, protected posture.
``resolve_voice_docs`` already resolves a gitignored declared doc identically
to a committed one (it never consults git status), so the installer's job is to
**protect** the private path from accidental commit: Stage 7.9 appends the
documented private patterns (``*.local.md`` and ``/.voice/``) to the consumer's
``.gitignore`` idempotently.

The append contract:

  * **Idempotent** — running the installer twice never duplicates an entry.
  * **No-clobber** — unrelated ``.gitignore`` lines are never rewritten or
    reordered; only an append (or a skip) ever happens.
  * **Creates** the ``.gitignore`` if absent.
  * **``--dry-run`` aware** — reports the would-append and writes nothing.
  * Only fires when a voice-consuming skill (``essay`` / ``memo``) is selected.

These tests exercise the installer via ``subprocess`` so the contract is
enforced at the real entry point. Distinct filename per the #58 packaging
convention (sibling to ``test_install_voice_scaffold.py``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

PRIVATE_PATTERNS = ("*.local.md", "/.voice/")


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


def _gitignore_lines(target: Path) -> list[str]:
    gi = target / ".gitignore"
    if not gi.is_file():
        return []
    return [
        line.strip()
        for line in gi.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# ---------------------------------------------------------------------------
# Fresh install appends the private patterns
# ---------------------------------------------------------------------------


def test_fresh_install_appends_private_patterns(tmp_path: Path) -> None:
    """A voice install gitignores both documented private patterns."""
    target = tmp_path / "fresh"
    target.mkdir()

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    lines = _gitignore_lines(target)
    for pat in PRIVATE_PATTERNS:
        assert pat in lines, (
            f"installer did not append private pattern {pat!r} to .gitignore; "
            f"lines={lines}; stdout:\n{result.stdout}"
        )


def test_creates_gitignore_when_absent(tmp_path: Path) -> None:
    """No pre-existing .gitignore → the installer creates it with the patterns."""
    target = tmp_path / "no-gitignore"
    target.mkdir()
    assert not (target / ".gitignore").exists()

    result = _run("--skills=essay", str(target))
    _assert_ok(result)

    assert (target / ".gitignore").is_file(), "installer did not create .gitignore"
    lines = _gitignore_lines(target)
    for pat in PRIVATE_PATTERNS:
        assert pat in lines, f"missing {pat!r} in created .gitignore: {lines}"


def test_no_append_when_no_voice_skill(tmp_path: Path) -> None:
    """No voice-consuming skill → no private patterns appended."""
    target = tmp_path / "no-voice"
    target.mkdir()

    result = _run("--skills=pub", str(target))
    _assert_ok(result)

    lines = _gitignore_lines(target)
    for pat in PRIVATE_PATTERNS:
        assert pat not in lines, (
            f"appended {pat!r} even though no voice skill was selected: {lines}"
        )


# ---------------------------------------------------------------------------
# Idempotency + no-clobber
# ---------------------------------------------------------------------------


def test_reinstall_does_not_duplicate_entries(tmp_path: Path) -> None:
    """Running the installer twice never produces a duplicate gitignore entry."""
    target = tmp_path / "idempotent"
    target.mkdir()

    _assert_ok(_run("--skills=memo", str(target)))
    second = _run("--skills=memo", str(target))
    _assert_ok(second)

    lines = _gitignore_lines(target)
    for pat in PRIVATE_PATTERNS:
        assert lines.count(pat) == 1, (
            f"pattern {pat!r} duplicated after re-install: {lines}"
        )
    # The skip note fires on re-run.
    assert "already ignores" in second.stdout, (
        f"expected the 'already ignores' skip note on re-install; "
        f"got:\n{second.stdout}"
    )


def test_existing_pattern_is_not_duplicated(tmp_path: Path) -> None:
    """A pre-existing `*.local.md` line is reused, never duplicated."""
    target = tmp_path / "preexisting-pattern"
    target.mkdir()
    (target / ".gitignore").write_text(
        "node_modules/\n*.local.md\n", encoding="utf-8"
    )

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    lines = _gitignore_lines(target)
    assert lines.count("*.local.md") == 1, (
        f"pre-existing *.local.md was duplicated: {lines}"
    )
    # The /.voice/ pattern still gets appended (per-pattern coverage check).
    assert "/.voice/" in lines, f"/.voice/ not appended: {lines}"


def test_unrelated_lines_untouched(tmp_path: Path) -> None:
    """Existing unrelated .gitignore lines are preserved verbatim and in order."""
    target = tmp_path / "unrelated"
    target.mkdir()
    original = "# my ignores\nnode_modules/\ndist/\n.env\n"
    (target / ".gitignore").write_text(original, encoding="utf-8")

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    content = (target / ".gitignore").read_text(encoding="utf-8")
    # The original block is preserved verbatim as a prefix (append-only).
    assert content.startswith(original), (
        "installer rewrote or reordered unrelated .gitignore lines; "
        f"content:\n{content}"
    )
    # And the private patterns were appended after it.
    for pat in PRIVATE_PATTERNS:
        assert pat in content, f"missing appended pattern {pat!r}:\n{content}"


def test_append_does_not_join_onto_a_no_newline_file(tmp_path: Path) -> None:
    """A .gitignore with no trailing newline is not joined onto its last line."""
    target = tmp_path / "no-newline"
    target.mkdir()
    # No trailing newline after 'dist/'.
    (target / ".gitignore").write_text("dist/", encoding="utf-8")

    result = _run("--skills=memo", str(target))
    _assert_ok(result)

    lines = _gitignore_lines(target)
    assert "dist/" in lines, f"'dist/' was corrupted by the append: {lines}"
    for pat in PRIVATE_PATTERNS:
        assert pat in lines, f"missing {pat!r}: {lines}"
    # Specifically, the last original line must not have been joined.
    assert "dist/*.local.md" not in lines, (
        "append joined onto the no-newline last line"
    )


# ---------------------------------------------------------------------------
# --dry-run honesty (issue #81)
# ---------------------------------------------------------------------------


def test_dry_run_reports_and_writes_nothing(tmp_path: Path) -> None:
    """`--dry-run` reports the would-append and writes no .gitignore."""
    target = tmp_path / "dry-run"
    target.mkdir()

    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--skills=memo", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    _assert_ok(result)

    assert "[dry-run] append '*.local.md' to .gitignore" in result.stdout, (
        f"expected the dry-run append action line; got:\n{result.stdout}"
    )
    assert not (target / ".gitignore").exists(), (
        "--dry-run wrote a .gitignore to the target"
    )
