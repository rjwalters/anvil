"""Tests for the merge-group arm's PR-metadata recovery (issue #1527).

The ``merge_group`` arm of ``.github/workflows/version-bump-gate.yml`` used to
recover BOTH pieces of PR metadata it needs (the marker-bearing PR body and
the target branch) from a single ``commits/{sha}/pulls`` API call, and exited
1 when that call yielded no PR. For a queued commit on a
``gh-readonly-queue/...`` ref the association is unverified (#1527) — if it
does not behave as assumed, one failure mode red-lines every merge group.

The contract pinned here (#1527):

- the target branch comes from the ``merge_group`` event payload itself
  (``base_ref``, a full ref, stripped of ``refs/heads/``), never from the
  API response;
- the commits API is consulted only for the PR body (the
  ``<!-- loom:no-surface-change -->`` marker's home), and an association
  failure degrades to an empty body with a ``::warning::`` — the group is
  still evaluated fail-closed through the gate's normal verdict path
  (empty body finds no marker), not by a metadata-step exit;
- so a group that bumped VERSION (or left the surface untouched) evaluates
  normally even when the association fails; only a group relying on the
  marker is affected.

The behavioral tests execute the resolve step's ``run`` block with the
``${{ ... }}`` expressions substituted the way the runner would, under a
stub ``gh`` whose response the test controls. The payload shape
(``base_ref`` as a full ref) is from GitHub's docs, not traced against a
live ``merge_group`` event — the workflow change carries the same caveat.
Distinct file basename per the #58 cross-skill collision convention.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "version-bump-gate.yml"
STEP_NAME = "Resolve queued PR metadata (merge groups only)"

# What the (simulated) runner would inject for each GitHub expression the
# step references. ``base_ref`` is a full ref per GitHub's documented
# ``merge_group`` payload.
EXPRESSIONS: dict[str, str] = {
    "github.repository": "2AMLogic/anvil",
    "github.event.merge_group.head_sha": "0123456789abcdef0123456789abcdef01234567",
    "github.event.merge_group.base_ref": "refs/heads/main",
    "github.token": "stub-token",
}

EXPR_RE = re.compile(r"\$\{\{\s*([^}]+?)\s*\}\}")


def _resolve_step() -> dict:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = doc["jobs"]["surface-version-bump"]["steps"]
    for step in steps:
        if isinstance(step, dict) and step.get("name") == STEP_NAME:
            return step
    raise AssertionError(f"missing workflow step {STEP_NAME!r}")


def _gate_step() -> dict:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = doc["jobs"]["surface-version-bump"]["steps"]
    for step in steps:
        if isinstance(step, dict) and "./scripts/check-surface-version-bump.sh" in (
            step.get("run") or ""
        ):
            return step
    raise AssertionError("missing the gate invocation step")


def _substitute(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        expr = match.group(1)
        if expr not in EXPRESSIONS:
            raise AssertionError(f"unhandled GitHub expression in step: {expr!r}")
        return EXPRESSIONS[expr]

    return EXPR_RE.sub(repl, text)


def _gh_stub(tmp_path: Path, prs: list[dict] | None) -> Path:
    """A stub ``gh`` on PATH: prints the canned PR list, or fails when None."""
    if prs is not None:
        (tmp_path / "stub_prs.json").write_text(json.dumps(prs), encoding="utf-8")
    script = "\n".join(
        [
            "#!/usr/bin/env bash",
            'echo "$*" >> "$(dirname "$0")/invocations.log"',
            'if [[ -f "${STUB_PRS_FILE:-}" ]]; then cat "$STUB_PRS_FILE"; exit 0; fi',
            "exit 1",
            "",
        ]
    )
    stub = tmp_path / "bin" / "gh"
    stub.parent.mkdir(exist_ok=True)
    stub.write_text(script, encoding="utf-8")
    stub.chmod(0o755)
    return stub


def _run_step(tmp_path: Path, prs: list[dict] | None) -> tuple[int, str, str, str]:
    """Execute the resolve step. Returns (exit_code, gh_calls, GITHUB_ENV, stderr)."""
    step = _resolve_step()
    script = _substitute(step["run"])

    env = dict(os.environ)
    env.pop("GH_TOKEN", None)
    for key, value in step.get("env", {}).items():
        env[key] = _substitute(value)
    stub = _gh_stub(tmp_path, prs)
    env["PATH"] = f"{stub.parent}{os.pathsep}{env['PATH']}"
    if prs is not None:
        env["STUB_PRS_FILE"] = str(tmp_path / "stub_prs.json")

    github_env = tmp_path / "github_env.txt"
    github_env.write_text("", encoding="utf-8")
    env["GITHUB_ENV"] = str(github_env)

    proc = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=60,
    )
    calls = ""
    log = stub.parent / "invocations.log"
    if log.exists():
        calls = log.read_text(encoding="utf-8")
    return proc.returncode, calls, github_env.read_text(encoding="utf-8"), proc.stderr


def _env_value(github_env_text: str, key: str) -> str | None:
    """Read a value out of a GITHUB_ENV file (``key=value`` or heredoc form)."""
    lines = github_env_text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"{key}<<"):
            delim = line[len(f"{key}<<") :].strip()
            collected: list[str] = []
            for tail in lines[i + 1 :]:
                if tail == delim:
                    return "\n".join(collected)
                collected.append(tail)
            raise AssertionError(f"unterminated heredoc for {key} in GITHUB_ENV")
        if line.startswith(f"{key}="):
            return line[len(key) + 1 :]
    return None


def test_tip_follows_the_event_payload_not_the_api(tmp_path: Path) -> None:
    """The tip must come from merge_group.base_ref (#1527).

    The stubbed API deliberately returns a PR whose ``base.ref`` disagrees
    with the event payload: the exported tip must follow the payload, and the
    full-ref ``refs/heads/`` prefix must be stripped.
    """
    prs = [
        {
            "number": 99,
            "body": "irrelevant body",
            "base": {"ref": "wrong-branch"},
        }
    ]
    code, _calls, github_env, _stderr = _run_step(tmp_path, prs)
    assert code == 0, "the resolve step must not fail when the API resolves"
    assert _env_value(github_env, "GATE_TIP_REF") == "origin/main", (
        "tip must be origin/<stripped merge_group.base_ref>, not the API's "
        "base.ref (issue #1527)"
    )


def test_api_failure_degrades_to_an_empty_body(tmp_path: Path) -> None:
    """An unverified-association failure must not red-line the group (#1527).

    Exit 0, keep the tip, export no body, and warn: a marker-relying group
    then fails closed through the gate's normal verdict path instead of a
    metadata-step exit.
    """
    code, calls, github_env, stderr = _run_step(tmp_path, None)
    assert code == 0, (
        "the resolve step must not exit nonzero when the commits API yields "
        "no PR (issue #1527)"
    )
    assert _env_value(github_env, "GATE_TIP_REF") == "origin/main"
    assert _env_value(github_env, "GATE_PR_BODY") is None, (
        "a failed association must not fabricate a PR body"
    )
    assert "::warning::" in stderr, "the degradation must be visible in the log"
    assert "commits/" in calls, "the API is still consulted for the body"


def test_multi_member_bodies_are_joined(tmp_path: Path) -> None:
    """Any group member's body may carry the marker; all bodies are exported."""
    prs = [
        {"number": 30, "body": "first body", "base": {"ref": "main"}},
        {
            "number": 31,
            "body": "second <!-- loom:no-surface-change -->",
            "base": {"ref": "main"},
        },
    ]
    code, calls, github_env, _stderr = _run_step(tmp_path, prs)
    assert code == 0
    assert _env_value(github_env, "GATE_PR_BODY") == (
        "first body\nsecond <!-- loom:no-surface-change -->"
    )
    assert (
        f"repos/2AMLogic/anvil/commits/{EXPRESSIONS['github.event.merge_group.head_sha']}/pulls"
        in calls
    ), "the body must come from the merge-group head commit's PR association"


def test_resolve_step_never_exits_nonzero_on_the_association() -> None:
    """Text pin: the resolve step carries no ``exit 1`` (#1527)."""
    run = _resolve_step()["run"]
    assert "exit 1" not in run, (
        "an association failure must degrade, not red-line the group (#1527)"
    )
    assert "first | .base.ref" not in run, (
        "the tip must not be derived from the API response (#1527)"
    )


def test_tip_source_is_the_stripped_event_payload() -> None:
    """Text pin: base_ref is read from the payload and ``refs/heads/``-stripped."""
    step = _resolve_step()
    run = step["run"]
    assert "refs/heads/}" in run, "the full-ref payload value must be stripped"
    env = step.get("env", {})
    assert any("merge_group.base_ref" in str(v) for v in env.values()), (
        "the payload's base_ref must be plumbed in via step env"
    )


def test_gate_step_keeps_fail_closed_posture() -> None:
    """Text pin: the verdict path is untouched — required tip, script, exit 1."""
    run = _gate_step()["run"]
    assert "GATE_TIP_REF:?" in run, "the gate must still require an exported tip"
    assert "./scripts/check-surface-version-bump.sh" in run
    assert "exit 1" in run, "the unsupported-event fail-closed exit stays"
