"""Frontmatter-schema tests for the v0 Anvil subagent registry.

Issue #377 — pin the field set, the allowed tool names, and the
staging/output extension fields. Reject unknown top-level keys (catches
typos like ``tool`` vs ``tools``).

Distinct from ``test_agent_registry.py`` which is about coverage / drift;
this file is about schema discipline.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "anvil" / "agents"

# Required + optional frontmatter keys for an Anvil agent. Two extensions
# beyond Loom's `name`/`description`/`tools`:
#   - staging_pattern  : consumed by `anvil/lib/sidecar.py`'s
#                        cleanup_one_staging (issue #381) to scope the
#                        per-critic sweep at registration time.
#   - expected_outputs : declared output filenames; documents the sidecar
#                        contract and bypasses the harness Write-heuristic
#                        for known-good targets (issue #375 region).
REQUIRED_KEYS = {"name", "description", "tools", "expected_outputs"}
OPTIONAL_KEYS = {"staging_pattern"}
ALLOWED_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS

# Tool names the v0 agents may carry. `Task` is intentionally excluded —
# v0 fan-out is the operator's job (or, in a future daemon, the daemon's),
# never the agent's. Avoiding `Task` prevents accidental recursive
# subagent dispatch.
ALLOWED_TOOLS = {"Read", "Glob", "Grep", "Bash", "Write", "Edit"}


@pytest.mark.parametrize("agent_path", sorted(AGENTS_DIR.glob("anvil-*.md")))
def test_frontmatter_keys_are_known(agent_path: pathlib.Path) -> None:
    """Catch typos like `tool` instead of `tools` early."""
    text = agent_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3
    meta = yaml.safe_load(parts[1])
    assert isinstance(meta, dict)
    keys = set(meta.keys())
    missing = REQUIRED_KEYS - keys
    extra = keys - ALLOWED_KEYS
    assert not missing, (
        f"{agent_path.name}: missing required keys: {sorted(missing)}"
    )
    assert not extra, (
        f"{agent_path.name}: unknown top-level keys: {sorted(extra)}"
    )


@pytest.mark.parametrize("agent_path", sorted(AGENTS_DIR.glob("anvil-*.md")))
def test_tools_are_in_allowlist(agent_path: pathlib.Path) -> None:
    """Tool names must be in the v0 allowlist (no ``Task``, no typos)."""
    text = agent_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    meta = yaml.safe_load(parts[1])
    tools_str = meta["tools"]
    assert isinstance(tools_str, str)
    tools = [t.strip() for t in tools_str.split(",")]
    for tool in tools:
        assert tool in ALLOWED_TOOLS, (
            f"{agent_path.name}: tool `{tool}` not in v0 allowlist "
            f"{sorted(ALLOWED_TOOLS)}"
        )
    # `Task` is explicitly forbidden — see module docstring.
    assert "Task" not in tools, (
        f"{agent_path.name}: `Task` tool is forbidden in v0 agents "
        "(fan-out is the operator's job, not the agent's)"
    )


@pytest.mark.parametrize("agent_path", sorted(AGENTS_DIR.glob("anvil-*.md")))
def test_expected_outputs_is_list_of_strings(
    agent_path: pathlib.Path,
) -> None:
    """``expected_outputs`` must be a list (possibly empty) of file names."""
    text = agent_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    meta = yaml.safe_load(parts[1])
    assert isinstance(meta["expected_outputs"], list)
    for entry in meta["expected_outputs"]:
        assert isinstance(entry, str) and entry, (
            f"{agent_path.name}: expected_outputs contains non-string or "
            f"empty entry: {entry!r}"
        )
        # No directory traversal, no absolute paths — these are sidecar
        # filenames meant to land directly in the staging dir.
        assert "/" not in entry and not entry.startswith("."), (
            f"{agent_path.name}: expected_outputs entry must be a bare "
            f"filename (no `/`, no leading `.`): {entry!r}"
        )


@pytest.mark.parametrize("agent_path", sorted(AGENTS_DIR.glob("anvil-*.md")))
def test_staging_pattern_when_present_is_well_formed(
    agent_path: pathlib.Path,
) -> None:
    """When ``staging_pattern`` is set it must use the `{thread}`/`{N}` shape.

    Mirrors the cleanup_one_staging contract in ``anvil/lib/sidecar.py``:
    staging dirs are named ``.<thread>.<N>.<phase>.tmp``. The pattern in
    frontmatter uses brace placeholders that a future tooling integration
    can format against a concrete (thread, N) pair.
    """
    text = agent_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    meta = yaml.safe_load(parts[1])
    pattern = meta.get("staging_pattern")
    if pattern is None:
        return  # absent is allowed (drafter/reviser write version dirs)
    assert isinstance(pattern, str)
    assert pattern, (
        f"{agent_path.name}: staging_pattern present but empty"
    )
    # Must use the documented placeholders and end with ``.tmp/``.
    assert "{thread}" in pattern, (
        f"{agent_path.name}: staging_pattern missing `{{thread}}`: {pattern}"
    )
    assert "{N}" in pattern, (
        f"{agent_path.name}: staging_pattern missing `{{N}}`: {pattern}"
    )
    assert pattern.endswith(".tmp/"), (
        f"{agent_path.name}: staging_pattern must end with `.tmp/`: {pattern}"
    )
