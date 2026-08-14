"""Tests for ``scripts/check-changelog-entry.sh`` (issue #1037).

At the v0.11.0 cut, ``/repo:release``'s merged-work coverage check found the
``[Unreleased]`` section covered ~28 items while the cycle had merged ~50 more
``feat``/``fix``/``security`` PRs with no entry — including two whole new
skills. The convention existed; nothing in the Builder → Judge cycle ever
checked it, so the gap only surfaced at release time as hand reconstruction.

``check-changelog-entry.sh`` is the cheap deterministic pre-flight that closes
that gap, following the exit-code convention of
``.loom/scripts/require-complexity-marker.sh``:

- 0 = has an entry, or a valid exemption
- 1 = missing entry (or a contradicted ``CHANGELOG: yes`` claim)
- 2 = could not evaluate

These tests drive the script's offline mode (``--title`` / ``--body-file`` /
``--files-file``) so nothing here touches the network or ``gh``. Distinct file
basename per the #58 cross-skill collision convention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check-changelog-entry.sh"


def _run(tmp_path: Path, title: str, body: str = "", files: str = "") -> subprocess.CompletedProcess:
    body_file = tmp_path / "body.md"
    files_file = tmp_path / "files.txt"
    body_file.write_text(body, encoding="utf-8")
    files_file.write_text(files, encoding="utf-8")
    return subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--title",
            title,
            "--body-file",
            str(body_file),
            "--files-file",
            str(files_file),
        ],
        capture_output=True,
        text=True,
    )


def test_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert SCRIPT.stat().st_mode & 0o111, "check-changelog-entry.sh must be executable"


# --- exempt types -------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "docs: repo-wide hygiene pass",
        "chore(tooling): update loom 0.18.27 to 0.18.45",
        "test(lib): cover the convergence tie-break",
        "refactor(skills): fold duplicate render helpers into lib",
        "ci: pin the runner image",
    ],
)
def test_non_worthy_types_are_exempt(tmp_path: Path, title: str) -> None:
    """docs/chore/test/refactor/ci PRs need no entry, even with an empty diff."""
    result = _run(tmp_path, title, files="README.md\n")
    assert result.returncode == 0, result.stderr
    assert "EXEMPT" in result.stdout


@pytest.mark.parametrize(
    "title",
    [
        "Update the thing",
        # The live example: PR #1033 merged with a scope-first, type-less title.
        "corpus-provenance: flag claims whose scope exceeds their cited row",
    ],
)
def test_non_conventional_title_is_could_not_classify(tmp_path: Path, title: str) -> None:
    """A type-less title exits 2, not 0.

    Declining to guess is not the same as passing: reporting "exempt" for a
    title with no declared type is exactly how a real feature slips through.
    The conventional-commit title format is separately required by
    ``builder-pr.md`` § "PR Titles"; this check just refuses to launder a
    violation of it into a clean pass.
    """
    result = _run(tmp_path, title, files="anvil/lib/critics.py\n")
    assert result.returncode == 2, result.stdout
    assert "COULD NOT CLASSIFY" in result.stderr


# --- changelog-worthy types ---------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "feat: add the anvil:ip-search skill",
        "fix: version.sh --tag creates annotated tags",
        "security: stop leaking the API key into logs",
        "feat(skills): add the anvil:diff viewer",
        "fix(lib)!: change the review-schema contract",
    ],
)
def test_worthy_types_pass_when_changelog_is_touched(tmp_path: Path, title: str) -> None:
    result = _run(tmp_path, title, files="CHANGELOG.md\nanvil/lib/critics.py\n")
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


@pytest.mark.parametrize(
    "title",
    [
        "feat: add the anvil:ip-search skill",
        "fix: version.sh --tag creates annotated tags",
        "security: stop leaking the API key into logs",
        "feat(skills)!: rewrite the deck rubric",
    ],
)
def test_worthy_types_fail_with_no_entry_and_no_claim(tmp_path: Path, title: str) -> None:
    """The regression this issue is about: a silent skip must exit 1."""
    result = _run(tmp_path, title, files="anvil/skills/paper/SKILL.md\n")
    assert result.returncode == 1, result.stdout
    assert "MISSING" in result.stderr


def test_false_yes_claim_is_the_loud_failure(tmp_path: Path) -> None:
    """`CHANGELOG: yes` with no CHANGELOG.md in the diff is a contradiction.

    Same shape and severity tier as a false ``TDD: yes`` (``judge.md``
    § "Test-First (TDD) Claim Verification").
    """
    result = _run(
        tmp_path,
        "feat: add the anvil:diff viewer",
        body="## Summary\n\nAdds a viewer.\n\nCHANGELOG: yes\n",
        files="anvil/skills/diff/SKILL.md\n",
    )
    assert result.returncode == 1, result.stdout
    assert "claims 'CHANGELOG: yes'" in result.stderr


def test_explicit_no_claim_is_accepted(tmp_path: Path) -> None:
    """An honest `CHANGELOG: no — <reason>` is advisory, never blocking."""
    result = _run(
        tmp_path,
        "fix: correct a stale path in the worked example",
        body="CHANGELOG: no — example-only fix, no user-facing behavior change\n",
        files="anvil/skills/memo/examples/worked/memo.md\n",
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_yes_claim_corroborated_by_the_diff_passes(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        "feat: add the anvil:ip-search skill",
        body="CHANGELOG: yes — new Added entry under [Unreleased]\n",
        files="CHANGELOG.md\nanvil/skills/ip-search/SKILL.md\n",
    )
    assert result.returncode == 0, result.stderr


# --- claim-line parsing -------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "CHANGELOG: no — docs-only",
        "- CHANGELOG: no — docs-only",
        "**CHANGELOG:** no — docs-only",
        "  changelog: no — docs-only",
        "* **CHANGELOG**: no — docs-only",
    ],
)
def test_claim_line_shapes_are_tolerated(tmp_path: Path, line: str) -> None:
    """PR bodies write this line five different ways; all of them count."""
    result = _run(
        tmp_path,
        "fix: something small",
        body=f"## Test Plan\n\nTDD: no — trivial\n{line}\n",
        files="anvil/lib/render.py\n",
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def test_last_claim_wins_over_quoted_prose(tmp_path: Path) -> None:
    """A body that quotes the convention before stating its own claim.

    Mirrors the #4840 fix in ``require-complexity-marker.sh``: an issue/PR that
    *discusses* the marker must not have the example text parsed as its claim.
    """
    body = (
        "This PR adds the convention. Builders write `CHANGELOG: yes` when they\n"
        "added an entry.\n\n"
        "CHANGELOG: no — process/docs change, nothing user-facing to record\n"
    )
    result = _run(tmp_path, "fix: wire up the check", body=body, files="scripts/x.sh\n")
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


# --- could-not-evaluate -------------------------------------------------------


def test_missing_files_argument_exits_2(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--files-file", str(tmp_path / "nope.txt")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stdout


def test_no_arguments_exits_2(tmp_path: Path) -> None:
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 2, result.stdout


def test_help_exits_0(tmp_path: Path) -> None:
    result = subprocess.run(["bash", str(SCRIPT), "--help"], capture_output=True, text=True)
    assert result.returncode == 0


def test_nested_changelog_path_counts(tmp_path: Path) -> None:
    """A CHANGELOG.md at any depth counts; the repo root one is not the only one."""
    result = _run(
        tmp_path,
        "feat: something",
        files="docs/CHANGELOG.md\n",
    )
    assert result.returncode == 0, result.stderr


def test_similarly_named_file_does_not_count(tmp_path: Path) -> None:
    """`CHANGELOG.md.bak` / `CHANGELOG_TEMPLATE.md` must not satisfy the check."""
    result = _run(
        tmp_path,
        "feat: something",
        files="CHANGELOG.md.bak\nCHANGELOG_TEMPLATE.md\n",
    )
    assert result.returncode == 1, result.stdout
