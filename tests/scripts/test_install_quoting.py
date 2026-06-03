"""Regression test: ``install-anvil.sh`` must handle paths with shell metacharacters.

Issue #80: seven ``do_action "..." sh -c "..."`` sites in
``scripts/install-anvil.sh`` interpolated ``$TARGET`` / ``$ANVIL_ROOT`` /
``$skill`` into a single-quoted ``sh -c`` body. A legitimate Unix path
containing ``'`` corrupted that body's single-quote pairing in the child
shell, producing::

    sh: -c: line 3: unexpected EOF while looking for matching ``''

The fix replaces every ``sh -c`` site with a bash helper function called
directly through ``do_action`` (which already executes ``"$@"`` correctly);
no child-shell re-parse, paths stay safely bash-quoted end-to-end.

These tests exercise the installer end-to-end via ``subprocess`` so the
regression is caught at the real entry point a consumer would hit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"


def _run_install(target: Path) -> subprocess.CompletedProcess[str]:
    """Run the installer non-interactively against ``target``.

    Captures stdout+stderr as text so test assertions can include the
    installer's own log lines in failure messages.
    """

    return subprocess.run(
        ["bash", str(INSTALLER), "-y", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _assert_install_artifacts(target: Path) -> None:
    """Common post-install structural checks shared by both regression cases.

    Updated for the issue #230 layout: the framework Python ships under
    ``.anvil/anvil/lib`` (importable mirror), with the skill body still at
    ``.anvil/skills/<name>/`` (consumer-override target). The pre-#230
    ``.anvil/lib`` path is no longer the install target.
    """

    assert (target / ".anvil" / "anvil" / "lib").is_dir()
    assert (target / ".anvil" / "anvil" / "__init__.py").is_file()
    assert (target / ".anvil" / "pyproject.toml").is_file()
    assert (target / ".anvil" / "roles").is_dir()
    assert (target / ".anvil" / "skills" / "memo" / "SKILL.md").is_file()
    assert (target / ".anvil" / "install-metadata.json").is_file()
    assert (target / ".claude" / "skills" / "anvil-memo" / "SKILL.md").is_file()
    assert (target / "CLAUDE.md").is_file()


def test_install_succeeds_with_single_quote_in_path(tmp_path: Path) -> None:
    """A target dir whose name contains ``'`` must not break the installer.

    Pre-fix repro on main (commit ec5bd8f)::

        mkdir -p "/tmp/anvil'evil"
        bash scripts/install-anvil.sh -y "/tmp/anvil'evil"
        # > Stage 7: copy selected skills
        # sh: -c: line 3: unexpected EOF while looking for matching ``''
        # sh: -c: line 5: syntax error: unexpected end of file

    Post-fix: install completes with returncode 0 and all artifacts present.
    """

    target = tmp_path / "anvil'evil"
    target.mkdir()

    result = _run_install(target)

    assert result.returncode == 0, (
        f"install failed on quoted path {target!r}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    # The original failure mode printed `unexpected EOF` from the child sh.
    # Catch it explicitly so a future regression with returncode 0 but a
    # corrupted child shell is still flagged.
    assert "unexpected EOF" not in result.stderr
    _assert_install_artifacts(target)


def test_install_succeeds_with_plain_path(tmp_path: Path) -> None:
    """Baseline: the same install on a normal path still works.

    Guards against the refactor regressing the green-path install (the
    sh -c removal must be behaviour-preserving on quirk-free targets).
    """

    target = tmp_path / "plain-target"
    target.mkdir()

    result = _run_install(target)

    assert result.returncode == 0, (
        f"install failed on plain path {target!r}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    _assert_install_artifacts(target)
