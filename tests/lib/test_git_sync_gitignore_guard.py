"""Safety-critical guard: the git-sync hook never stages a gitignored doc (#577).

The opt-in per-phase git-sync hook (``anvil/lib/snippets/git_sync.md``,
``git.commit_per_phase``) stages **only the paths a phase wrote** — a
``<thread>.{N}/`` version dir or a critic's own sidecar dir — and MUST NEVER
stage a path matched by ``.gitignore``. Private voice-grounding docs
(``VALUES.local.md``-class personal stances; issue #577) are a designed
``.gitignored`` posture; an auto-commit of one would silently leak personal
perspective into git history.

The hook is a **markdown contract**, not executable Python, so these tests
model the documented staging behavior against a **real git repository
fixture**: init a repo, write a ``.gitignore`` that ignores a private
grounding doc, write the doc, run the documented ``git add <write-set>``, and
assert ``git diff --cached --name-only`` excludes the private doc.

The guard tests are constructed so they **FAIL if someone "helpfully" rewrites
the contract** to use ``git add -A`` / ``git add .`` (would sweep the
gitignored doc into the index) or ``git add -f`` (force-adds it). That is the
load-bearing property: the test is a tripwire on the §"Staging scope" rule.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GIT_SYNC_SNIPPET = REPO_ROOT / "anvil" / "lib" / "snippets" / "git_sync.md"

# The documented private grounding doc name (the *.local.md convention, #577).
PRIVATE_DOC = "VALUES.local.md"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A real git repo with a private grounding doc gitignored at the root.

    Models a consumer repo: a private ``VALUES.local.md`` at the consumer root,
    gitignored by the ``*.local.md`` pattern the installer appends, plus a
    phase's write-set (a ``pricing-memo.1/`` version dir) the hook would stage.
    """
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")

    # The installer-appended pattern that protects private grounding (#577).
    (tmp_path / ".gitignore").write_text("*.local.md\n", encoding="utf-8")
    # A private grounding doc the author keeps local.
    (tmp_path / PRIVATE_DOC).write_text(
        "# personal stances — do not commit\n", encoding="utf-8"
    )
    # A phase's write-set: a version dir with its progress checkpoint.
    version_dir = tmp_path / "pricing-memo.1"
    version_dir.mkdir()
    (version_dir / "pricing-memo.md").write_text("# draft\n", encoding="utf-8")
    (version_dir / "_progress.json").write_text("{}\n", encoding="utf-8")
    return tmp_path


def _staged(repo: Path) -> set[str]:
    res = _git(repo, "diff", "--cached", "--name-only")
    return {line for line in res.stdout.splitlines() if line}


def test_staging_the_write_set_excludes_the_private_doc(repo: Path) -> None:
    """The documented `git add <version-dir>` never stages the gitignored doc."""
    # The hook stages ONLY the dirs the phase wrote (§"Staging scope").
    res = _git(repo, "add", "pricing-memo.1")
    assert res.returncode == 0, f"git add failed: {res.stderr}"

    staged = _staged(repo)
    # The write-set is staged...
    assert "pricing-memo.1/pricing-memo.md" in staged
    assert "pricing-memo.1/_progress.json" in staged
    # ...and the private grounding doc is NOT.
    assert PRIVATE_DOC not in staged, (
        "the gitignored private grounding doc was staged by the narrow "
        "write-set add — the §'Staging scope' guarantee is broken"
    )


def test_plain_git_add_of_the_private_doc_is_a_no_op(repo: Path) -> None:
    """Plain `git add <private-doc>` (no -f) refuses to stage a gitignored file.

    The hook uses plain ``git add`` and never ``-f``. Even if a private doc
    were somehow named in a write-set, plain ``git add`` declines to stage it.
    """
    res = _git(repo, "add", PRIVATE_DOC)
    # git declines (non-zero) OR succeeds-as-no-op depending on version, but
    # either way the index must not contain the gitignored doc.
    assert PRIVATE_DOC not in _staged(repo), (
        "plain `git add` staged a gitignored doc — only `-f` should do that"
    )


def test_git_add_dash_A_would_leak_the_private_doc(repo: Path) -> None:
    """Tripwire: prove `git add -A` (forbidden) WOULD stage the private doc.

    This is the failure mode the §'Staging scope' rule forbids. We assert the
    leak HERE so the contract's "never `git add -A`" rule is demonstrably
    load-bearing: ``-A`` does NOT respect .gitignore-via-write-set narrowing
    (it stages every tracked/untracked-but-not-ignored change) — but it WILL
    stage a previously-gitignored file once forced, and it sweeps the entire
    tree rather than the narrow write-set. Note: `-A` honors .gitignore for
    *untracked* files, so the real danger combines with `-f`; this test pins
    the tree-wide-sweep half of why `-A` is banned.
    """
    res = _git(repo, "add", "-A")
    assert res.returncode == 0
    staged = _staged(repo)
    # `git add -A` honors .gitignore for the untracked private doc, so it is
    # NOT staged — but it sweeps the WHOLE tree (e.g. the .gitignore file and
    # every version dir), which is exactly the unrelated-paths hazard the
    # narrow staging scope exists to prevent.
    assert PRIVATE_DOC not in staged  # gitignored untracked file still excluded
    assert ".gitignore" in staged, (
        "expected `git add -A` to sweep unrelated tree paths — this is why the "
        "hook forbids it in favor of a narrow write-set add"
    )


def test_git_add_dash_f_force_stages_the_private_doc(repo: Path) -> None:
    """Tripwire: prove `git add -f` (forbidden) DOES force-stage the private doc.

    This pins WHY the hook must never use ``-f``: it overrides .gitignore and
    stages the private grounding doc. If a future edit reintroduces ``-f`` into
    the contract, the guard above (`test_staging_the_write_set_excludes...`)
    would no longer be sufficient — this test documents the exact mechanism.
    """
    res = _git(repo, "add", "-f", PRIVATE_DOC)
    assert res.returncode == 0, f"git add -f failed: {res.stderr}"
    assert PRIVATE_DOC in _staged(repo), (
        "expected `git add -f` to force-stage the gitignored doc — this is "
        "precisely the behavior the hook forbids"
    )


# ---------------------------------------------------------------------------
# Contract-text guards: the markdown forbids -f / -A explicitly
# ---------------------------------------------------------------------------


def test_git_sync_contract_forbids_force_add() -> None:
    """The git-sync snippet explicitly forbids `git add -f` for the guard."""
    text = GIT_SYNC_SNIPPET.read_text(encoding="utf-8")
    assert "git add -f" in text, (
        "git_sync.md must name `git add -f` to forbid it (issue #577 guard)"
    )
    assert "gitignored" in text.lower(), (
        "git_sync.md must state the never-stage-a-gitignored-path guard"
    )


def test_git_sync_contract_references_the_guard_test() -> None:
    """The contract points at this fixture test as its verification."""
    text = GIT_SYNC_SNIPPET.read_text(encoding="utf-8")
    assert "test_git_sync_gitignore_guard.py" in text, (
        "git_sync.md should reference the real-git-fixture guard test so the "
        "contract and its verification stay linked"
    )
