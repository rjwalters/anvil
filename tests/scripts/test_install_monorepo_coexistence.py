"""Regression test: installing anvil into a crowded monorepo root is safe.

Issue #409: the next adoption target is a monorepo that already has its own
root ``pyproject.toml`` + ``uv.lock``, a ``.loom/`` installation, a
``package.json``/pnpm setup, a Makefile, and a substantive root
``CLAUDE.md`` (including a Loom marker block). The installer SHOULD be safe
here by design:

  * the only root-level file the installer writes is ``CLAUDE.md``
    (``merge_claude_md()``, Stage 8) — root ``pyproject.toml``, ``uv.lock``,
    ``.loom/``, ``package.json`` are never read or written;
  * ``.anvil/`` is fully self-contained with its own ``pyproject.toml``
    (``uv sync --project .anvil`` resolves independently of the monorepo's
    own uv project);
  * ``.claude/skills/`` shims are per-skill directories
    (``.claude/skills/anvil-<skill>/``) and ``.claude/agents/`` copies are
    per-file pattern-matched on ``anvil-*.md`` (Stage 7.5, issue #377) — so
    pre-existing non-anvil entries survive.

No test pinned any of this against a crowded root before. This module
builds the crowded fixture once (module scope — installs are slow-ish and
every assertion reads the same post-install tree), captures pre-install
bytes of every consumer-owned file, and asserts byte-identity after
install, after re-install (idempotency), and after ``uv sync``.

One documented subtlety (NOT a bug): the Case 3 CLAUDE.md append reads the
existing file via ``$(cat ...)``, and command substitution strips ALL
trailing newlines — so a consumer CLAUDE.md ending in multiple blank lines
is normalized to exactly one ``\\n\\n`` separator before the anvil block.
The primary fixture therefore ends with exactly one trailing newline (true
byte-prefix preservation), and a separate test pins the normalization
behavior for the trailing-blank-lines case so a future change to it is a
deliberate decision rather than an accident.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

ANVIL_MARK_BEGIN = "<!-- BEGIN ANVIL -->"
LOOM_BLOCK = (
    "<!-- BEGIN LOOM -->\n"
    "This repository uses Loom for AI-powered development orchestration.\n"
    "<!-- END LOOM -->"
)

# Consumer CLAUDE.md fixture. Ends with exactly ONE trailing newline so the
# Case 3 append path preserves it as a byte-prefix (see module docstring for
# why multiple trailing newlines would be normalized, not preserved).
CONSUMER_CLAUDE_MD = (
    "# Monorepo Guide\n"
    "\n"
    "Substantive consumer instructions that must survive an anvil install.\n"
    "\n"
    f"{LOOM_BLOCK}\n"
    "\n"
    "## Build\n"
    "\n"
    "Run `make build`.\n"
)

CONSUMER_PYPROJECT = (
    "[project]\n"
    'name = "monorepo"\n'
    'version = "1.2.3"\n'
    'dependencies = ["requests"]\n'
)

CONSUMER_UV_LOCK = "# sentinel uv.lock -- installer must never touch this\n"
CONSUMER_LOOM_CONFIG = '{"sentinel": "loom config -- installer must never touch this"}\n'
CONSUMER_PACKAGE_JSON = '{"name": "monorepo", "private": true}\n'
CONSUMER_MAKEFILE = "build:\n\t@echo building monorepo\n"
CONSUMER_SKILL_MD = "# some-other-skill\n\nPre-existing non-anvil skill shim.\n"
CONSUMER_LOOM_AGENT = "# loom-builder\n\nPre-existing Loom agent registration.\n"


class Monorepo(NamedTuple):
    target: Path
    before: Dict[str, bytes]  # path-relative-to-target -> pre-install bytes


def _uv_present() -> bool:
    return shutil.which("uv") is not None


def _install_into(target: Path) -> subprocess.CompletedProcess[str]:
    """Run the installer against ``target`` (memo only, no uv sync).

    ``--no-sync`` keeps the install itself deterministic; the one test that
    needs a venv runs ``uv sync`` explicitly (gated on uv being on PATH).
    """

    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--skills=memo", "--no-sync", str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _build_crowded_root(target: Path) -> Dict[str, bytes]:
    """Populate ``target`` as a crowded monorepo root; return pre-install bytes."""

    files = {
        "pyproject.toml": CONSUMER_PYPROJECT,
        "uv.lock": CONSUMER_UV_LOCK,
        ".loom/config.json": CONSUMER_LOOM_CONFIG,
        "package.json": CONSUMER_PACKAGE_JSON,
        "Makefile": CONSUMER_MAKEFILE,
        "CLAUDE.md": CONSUMER_CLAUDE_MD,
        ".claude/skills/some-other-skill/SKILL.md": CONSUMER_SKILL_MD,
        ".claude/agents/loom-builder.md": CONSUMER_LOOM_AGENT,
    }
    before: Dict[str, bytes] = {}
    for rel, content in files.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        before[rel] = path.read_bytes()
    # A .git dir silences the not-a-git-repo note; the installer proceeds
    # either way, but the adoption target IS a git repo, so model that.
    (target / ".git").mkdir()
    return before


@pytest.fixture(scope="module")
def monorepo(tmp_path_factory: pytest.TempPathFactory) -> Monorepo:
    """Crowded consumer root with anvil installed into it (install #1)."""

    target = tmp_path_factory.mktemp("monorepo") / "consumer"
    target.mkdir()
    before = _build_crowded_root(target)

    result = _install_into(target)
    assert result.returncode == 0, (
        f"install into crowded root failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
    return Monorepo(target=target, before=before)


# ---------------------------------------------------------------------------
# Case 1 — root project files untouched
# ---------------------------------------------------------------------------


def test_root_project_files_untouched(monorepo: Monorepo) -> None:
    """Root pyproject.toml / uv.lock / .loom/ / package.json / Makefile are
    byte-identical post-install — the installer's only root-file write is
    CLAUDE.md (install-anvil.sh Stage 8)."""

    for rel in ("pyproject.toml", "uv.lock", ".loom/config.json", "package.json", "Makefile"):
        after = (monorepo.target / rel).read_bytes()
        assert after == monorepo.before[rel], (
            f"installer modified consumer-owned root file {rel!r}"
        )


# ---------------------------------------------------------------------------
# Case 2 — CLAUDE.md additive append (Case 3 path in merge_claude_md)
# ---------------------------------------------------------------------------


def test_claude_md_append_is_additive(monorepo: Monorepo) -> None:
    """Existing CLAUDE.md content (incl. the Loom block) is a byte-prefix of
    the post-install file, with exactly one anvil marker block appended."""

    after = (monorepo.target / "CLAUDE.md").read_bytes()
    before = monorepo.before["CLAUDE.md"]

    assert after.startswith(before), (
        "existing CLAUDE.md content was not byte-preserved as a prefix of "
        "the post-install file (fixture ends in exactly one newline, so the "
        "Case 3 trailing-newline normalization cannot explain this)"
    )
    text = after.decode()
    assert text.count(ANVIL_MARK_BEGIN) == 1, (
        f"expected exactly one anvil marker block, found "
        f"{text.count(ANVIL_MARK_BEGIN)}"
    )
    assert LOOM_BLOCK in text, "pre-existing Loom marker block was not preserved verbatim"


# ---------------------------------------------------------------------------
# Case 5 — .claude/ preservation (per-skill shims, per-file agents)
# ---------------------------------------------------------------------------


def test_claude_dir_preexisting_entries_preserved(monorepo: Monorepo) -> None:
    """Non-anvil skills/agents under .claude/ survive; anvil entries coexist."""

    for rel in (
        ".claude/skills/some-other-skill/SKILL.md",
        ".claude/agents/loom-builder.md",
    ):
        after = (monorepo.target / rel).read_bytes()
        assert after == monorepo.before[rel], (
            f"installer modified pre-existing non-anvil entry {rel!r}"
        )

    # Anvil's own footprint landed alongside, namespaced.
    assert (monorepo.target / ".claude/skills/anvil-memo/SKILL.md").is_file(), (
        "anvil-memo skill shim missing — install did not land alongside "
        "pre-existing .claude/skills entries"
    )
    anvil_agents = sorted(
        (monorepo.target / ".claude/agents").glob("anvil-*.md")
    )
    assert anvil_agents, (
        ".claude/agents has no anvil-*.md entries post-install (Stage 7.5)"
    )


# ---------------------------------------------------------------------------
# Case 3 — re-install idempotency (Case 2 path in merge_claude_md)
# ---------------------------------------------------------------------------


def test_reinstall_is_idempotent(monorepo: Monorepo) -> None:
    """A second install replaces the anvil CLAUDE.md block in place — no
    duplicate section — and still leaves consumer-owned root files alone.

    NOTE: this test mutates the shared fixture by re-running the installer.
    That is the point — every other assertion in this module must also hold
    after a re-install, and re-install is contractually a no-op for the
    files they check.
    """

    claude_md = monorepo.target / "CLAUDE.md"
    snapshot = claude_md.read_bytes()

    result = _install_into(monorepo.target)
    assert result.returncode == 0, (
        f"re-install failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    after = claude_md.read_bytes()
    assert after == snapshot, (
        "CLAUDE.md changed on re-install — the marker-block in-place "
        "replacement (merge_claude_md Case 2) is not idempotent"
    )
    assert after.decode().count(ANVIL_MARK_BEGIN) == 1, (
        "re-install duplicated the anvil marker block"
    )

    for rel in ("pyproject.toml", "uv.lock", ".loom/config.json", "package.json"):
        assert (monorepo.target / rel).read_bytes() == monorepo.before[rel], (
            f"re-install modified consumer-owned root file {rel!r}"
        )


# ---------------------------------------------------------------------------
# Case 4 — .anvil/ is uv-self-contained; sync leaves the root lock alone
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _uv_present(), reason="uv not on PATH")
def test_anvil_uv_sync_independent_of_root_project(monorepo: Monorepo) -> None:
    """``uv sync --project .anvil`` from the consumer root succeeds and does
    NOT resolve against (or rewrite) the monorepo's own uv.lock.

    The fixture's root uv.lock is a sentinel, not a valid lockfile — if uv
    ever consulted the root project during the .anvil sync, this would fail
    loudly or rewrite the sentinel; both are regressions.
    """

    assert (monorepo.target / ".anvil/pyproject.toml").is_file(), (
        ".anvil/pyproject.toml missing — .anvil is not uv-self-contained"
    )

    sync = subprocess.run(
        ["uv", "sync", "--project", ".anvil"],
        capture_output=True,
        text=True,
        cwd=monorepo.target,
    )
    assert sync.returncode == 0, (
        f"uv sync --project .anvil failed from crowded consumer root:\n"
        f"--- stdout ---\n{sync.stdout}\n--- stderr ---\n{sync.stderr}"
    )
    assert (monorepo.target / "uv.lock").read_bytes() == monorepo.before["uv.lock"], (
        "root uv.lock changed during `uv sync --project .anvil` — the anvil "
        "venv must be independent of the monorepo's own uv project"
    )


# ---------------------------------------------------------------------------
# Documented normalization: trailing blank lines in consumer CLAUDE.md
# ---------------------------------------------------------------------------


def test_claude_md_trailing_blank_lines_are_normalized_not_lost(
    tmp_path: Path,
) -> None:
    """Pin the Case 3 trailing-newline normalization (a behavior, not a bug).

    ``merge_claude_md()`` Case 3 reads the existing file via ``$(cat ...)``;
    command substitution strips ALL trailing newlines, so a consumer
    CLAUDE.md ending in multiple blank lines is rewritten as
    ``<content-stripped-of-trailing-newlines>\\n\\n<anvil block>\\n``. The
    *content* is fully preserved; only the trailing-blank-line run collapses
    to the single separating blank line. A naive whole-file byte-prefix
    assertion would fail here for a non-bug reason — this test documents
    exactly what IS guaranteed.
    """

    target = tmp_path / "consumer"
    target.mkdir()
    body = "# Consumer\n\nContent before trailing blank lines."
    (target / "CLAUDE.md").write_text(body + "\n\n\n\n")

    result = _install_into(target)
    assert result.returncode == 0, result.stderr

    text = (target / "CLAUDE.md").read_text()
    assert text.startswith(body + "\n\n" + ANVIL_MARK_BEGIN), (
        "expected trailing blank lines to normalize to exactly one "
        f"separating blank line before the anvil block; got:\n{text!r}"
    )
    assert text.count(ANVIL_MARK_BEGIN) == 1
