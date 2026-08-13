"""Regression tests: installer additively merges an Anvil block into AGENTS.md.

Issue #1004 (phase 3 of the #1000 epic, "Make Anvil artifact skills
discoverable in Claude and Codex"). ``scripts/install-anvil.sh`` already
merges an additive, marker-bounded Anvil block into the consumer's root
``CLAUDE.md`` (Stage 8) but never touched ``AGENTS.md`` -- Codex CLI's
equivalent always-on repo-instructions entry point.

This fix adds the identical create / replace-in-place / append merge
mechanics for ``AGENTS.md`` via a generalized ``merge_marker_block()``
helper shared with the CLAUDE.md write, so the two files' Stage 8 writes are
driven by one mechanism rather than two independently hand-maintained
code paths. The runtime-neutral block prose (``ANVIL_POINTER``) is likewise
shared between the two files; only the invocation-adapter line differs
(``/anvil:<skill>`` for Claude Code vs. the ``.agents/skills/anvil-<skill>/``
registration path for Codex CLI) -- see the "CLAUDE.md / AGENTS.md marker +
adapter constants" comment in ``install-anvil.sh`` for the rationale.

Not to be conflated with ``test_install_agents_skill_filter.py``, which
covers a *different* concern despite the similar filename: Stage 7.5's
``--skills=``-scoped copy of ``.claude/agents/anvil-<skill>-<phase>.md``
subagent shims (issue #662). That module predates this one and has nothing
to do with the root ``AGENTS.md`` file this module covers.

These tests run the installer end-to-end via ``subprocess`` (mirroring
``test_install_monorepo_coexistence.py``'s CLAUDE.md merge coverage and
``test_install_codex_shim.py``'s Codex-shim coverage) so the contract is
enforced at the real entry point a consumer hits. Distinct filename per the
#58 packaging convention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install-anvil.sh"

ANVIL_MARK_BEGIN = "<!-- BEGIN ANVIL -->"


def _run_install(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Run the installer non-interactively against ``target``.

    ``--no-sync`` keeps the tests independent of uv availability and fast.
    """

    return subprocess.run(
        ["bash", str(INSTALLER), "-y", "--no-sync", *extra, str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _run_dry_run(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--no-sync", *extra, str(target)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"installer exited non-zero:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Case 1 — no existing AGENTS.md: created with just the marker block.
# ---------------------------------------------------------------------------


def test_agents_md_created_when_absent(tmp_path: Path) -> None:
    target = tmp_path / "agents-md-create-target"
    target.mkdir()

    result = _run_install(target, "--skills=memo")
    _assert_ok(result)

    agents_md = target / "AGENTS.md"
    assert agents_md.is_file(), "AGENTS.md was not created"
    text = agents_md.read_text(encoding="utf-8")
    assert text.count(ANVIL_MARK_BEGIN) == 1
    assert "See `.anvil/CLAUDE.md` for the full guide" in text
    assert ".agents/skills/anvil-<skill>/SKILL.md" in text, (
        "AGENTS.md block is missing the Codex-specific invocation adapter "
        f"line; got:\n{text}"
    )
    # The Claude-specific slash-command syntax must NOT leak into AGENTS.md.
    assert "/anvil:<skill>" not in text, (
        f"Claude slash-command syntax leaked into the Codex-facing AGENTS.md "
        f"block:\n{text}"
    )


# ---------------------------------------------------------------------------
# Case 2 — existing non-Anvil AGENTS.md: additive append, consumer content
# preserved as a byte-prefix.
# ---------------------------------------------------------------------------


def test_agents_md_append_is_additive(tmp_path: Path) -> None:
    target = tmp_path / "agents-md-append-target"
    target.mkdir()
    consumer_body = (
        "# Repo agent notes\n\nExisting consumer instructions that must survive.\n"
    )
    (target / "AGENTS.md").write_text(consumer_body, encoding="utf-8")

    result = _run_install(target, "--skills=memo")
    _assert_ok(result)

    text = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith(consumer_body), (
        "existing AGENTS.md content was not preserved as a byte-prefix of "
        f"the post-install file:\n{text}"
    )
    assert text.count(ANVIL_MARK_BEGIN) == 1


# ---------------------------------------------------------------------------
# Case 3 — existing Anvil block: in-place replace, idempotent re-install.
# ---------------------------------------------------------------------------


def test_agents_md_reinstall_replaces_block_in_place_idempotently(
    tmp_path: Path,
) -> None:
    target = tmp_path / "agents-md-reinstall-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo"))
    agents_md = target / "AGENTS.md"
    snapshot = agents_md.read_bytes()

    result = _run_install(target, "--skills=memo")
    _assert_ok(result)

    after = agents_md.read_bytes()
    assert after == snapshot, (
        "AGENTS.md changed on re-install -- the marker-block in-place "
        "replacement is not idempotent"
    )
    assert after.decode().count(ANVIL_MARK_BEGIN) == 1, (
        "re-install duplicated the Anvil marker block in AGENTS.md"
    )


def test_agents_md_hand_edit_inside_marker_block_is_replaced(
    tmp_path: Path,
) -> None:
    """A consumer hand-edit *inside* the Anvil block in AGENTS.md does not
    survive a re-install -- matching the existing CLAUDE.md behavior (Stage
    8's Case 2 always discards and rewrites the full block content between
    the markers, never diffing/preserving a partial edit inside them)."""

    target = tmp_path / "agents-md-hand-edit-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo"))
    agents_md = target / "AGENTS.md"
    text = agents_md.read_text(encoding="utf-8")
    hand_edited = text.replace(
        ANVIL_MARK_BEGIN, f"{ANVIL_MARK_BEGIN}\n<!-- consumer hand-edit -->"
    )
    agents_md.write_text(hand_edited, encoding="utf-8")

    result = _run_install(target, "--skills=memo")
    _assert_ok(result)

    after = agents_md.read_text(encoding="utf-8")
    assert "<!-- consumer hand-edit -->" not in after, (
        "a hand-edit inside the Anvil marker block survived a re-install -- "
        "this must match CLAUDE.md's existing in-place-replace behavior"
    )
    assert after.count(ANVIL_MARK_BEGIN) == 1


# ---------------------------------------------------------------------------
# --dry-run reports the plan and writes nothing.
# ---------------------------------------------------------------------------


def test_dry_run_reports_agents_md_plan_and_writes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "agents-md-dryrun-target"
    target.mkdir()

    result = _run_dry_run(target, "--skills=memo")
    _assert_ok(result)

    assert "create AGENTS.md with Anvil marker block" in result.stdout, (
        f"dry-run action line does not advertise the AGENTS.md write; "
        f"got:\n{result.stdout}"
    )
    assert not (target / "AGENTS.md").exists(), (
        "--dry-run wrote AGENTS.md to disk"
    )


def test_dry_run_reports_agents_md_replace_when_block_present(
    tmp_path: Path,
) -> None:
    target = tmp_path / "agents-md-dryrun-replace-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo"))

    result = _run_dry_run(target, "--skills=memo")
    _assert_ok(result)
    assert "replace existing Anvil block in AGENTS.md (in place)" in result.stdout, (
        f"dry-run did not report the in-place-replace plan for an existing "
        f"Anvil block in AGENTS.md; got:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# CLAUDE.md and AGENTS.md share the runtime-neutral pointer prose, differ
# only in the invocation-adapter line.
# ---------------------------------------------------------------------------


def test_claude_and_agents_md_share_pointer_prose_but_not_adapter_line(
    tmp_path: Path,
) -> None:
    target = tmp_path / "claude-agents-parity-target"
    target.mkdir()

    _assert_ok(_run_install(target, "--skills=memo"))

    claude_text = (target / "CLAUDE.md").read_text(encoding="utf-8")
    agents_text = (target / "AGENTS.md").read_text(encoding="utf-8")

    shared_pointer = "See `.anvil/CLAUDE.md` for the full guide"
    assert shared_pointer in claude_text
    assert shared_pointer in agents_text

    assert "/anvil:<skill>" in claude_text
    assert "/anvil:<skill>" not in agents_text
    assert ".agents/skills/anvil-<skill>/SKILL.md" in agents_text
    assert ".agents/skills/anvil-<skill>/SKILL.md" not in claude_text
