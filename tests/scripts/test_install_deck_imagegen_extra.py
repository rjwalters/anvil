"""Regression test: the generated consumer pyproject declares `deck_imagegen`.

Issue #947: the documented `deck-imagegen` porting-checklist command
(`pip install 'anvil[deck_imagegen]'` / `uv sync --project .anvil --extra
deck_imagegen` — see `anvil/skills/deck/commands/deck-imagegen-onboarding.md`
and `anvil/skills/deck/commands/deck-imagegen-adapter.md`) failed verbatim on
a fresh consumer install: `write_consumer_pyproject`
(`scripts/install-anvil.sh`) only mirrored the `auto_shrink` extra from the
source repo's `pyproject.toml` into the generated `.anvil/pyproject.toml`,
so `deck_imagegen` (declared in the source repo for issue #564) was never
forwarded and `uv sync --extra deck_imagegen` failed with "Extra
`deck-imagegen` is not defined in the project's `optional-dependencies`
table".

This test asserts the generated `.anvil/pyproject.toml` declares a
`deck_imagegen` extra with the same Pillow floor as the source repo's, and
that the pre-existing `auto_shrink` extra is still generated correctly
(guarding against an additive-heredoc-edit clobbering it).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _install_into(target: Path, *, skills: str = "deck") -> subprocess.CompletedProcess[str]:
    args = [
        "bash",
        str(INSTALLER),
        "-y",
        f"--skills={skills}",
        "--no-sync",
        str(target),
    ]
    return subprocess.run(args, capture_output=True, text=True, cwd=REPO_ROOT)


def test_consumer_pyproject_declares_deck_imagegen_extra(tmp_path: Path) -> None:
    target = tmp_path / "consumer"
    target.mkdir()

    result = _install_into(target, skills="deck")
    assert result.returncode == 0, (
        f"install failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    pyproject = target / ".anvil" / "pyproject.toml"
    assert pyproject.is_file(), ".anvil/pyproject.toml not written by installer"

    body = pyproject.read_text()
    assert "[project.optional-dependencies]" in body
    assert "deck_imagegen = [" in body, (
        "deck_imagegen extra missing from generated consumer pyproject — "
        "`uv sync --project .anvil --extra deck_imagegen` would fail with "
        "'Extra `deck-imagegen` is not defined'"
    )
    assert "Pillow>=12.3.0" in body


def test_consumer_pyproject_still_declares_auto_shrink_extra(tmp_path: Path) -> None:
    """Non-regression: adding deck_imagegen must not clobber auto_shrink."""

    target = tmp_path / "consumer"
    target.mkdir()

    result = _install_into(target, skills="deck")
    assert result.returncode == 0, result.stderr

    body = (target / ".anvil" / "pyproject.toml").read_text()
    assert "auto_shrink = [" in body
    assert "numpy>=1.24" in body
