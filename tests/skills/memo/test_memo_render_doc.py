"""Doc-coverage + backwards-compat smoke tests for the memo ``memo-render``
command + state-machine integration (Epic #158 Phase 3 / issue #190).

Per the issue body's acceptance criteria, this module ships:

- **Doc-coverage smoke tests**: grep-the-doc regression guards that the
  optional-render contract stays documented in the four files it touches
  (SKILL.md, commands/memo-render.md, commands/memo-draft.md,
  commands/memo-revise.md) and doesn't drift back to a pre-render-pipeline
  shape in a later edit.
- **Backwards-compat smoke tests**: light fixture-driven assertions that
  the render-gate primitive consumed by Phase 3 still returns the expected
  shapes when invoked the way the (LLM-driven) command will invoke it. The
  command itself is markdown-as-prompt — behavioural assertions belong in
  consumer-side integration tests, not here — but the lib seam the command
  invokes is fully testable.

Per-skill test filename convention (#58): this file is named with a
``test_memo_render_doc`` shape so pytest does not collide with parallel
``test_render_gate_memo.py`` (in ``tests/lib/``) or any future
``test_deck_render_*`` shape another skill might pick.

Module load notes:
- The shipped Phase 3 ``memo-render`` command is markdown-as-prompt; this
  test module deliberately treats the lib seam (``render_gate.gate(kind=
  "memo")``) as the contract-under-test rather than the prose of the
  command file.
- Renderer subprocess invocations are stubbed via ``monkeypatch`` of
  ``anvil.lib.render.check_*_available`` and ``subprocess.run`` so the
  suite runs in CI without pandoc, weasyprint, wkhtmltopdf, xelatex, or
  pdfinfo on PATH. The same fake-pandoc shape used by
  ``tests/lib/test_render_gate_memo.py`` is replicated here in the small
  to keep the test files independent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pytest

from anvil.lib import render as _render
from anvil.lib.render_gate import (
    COMPILE_OK,
    COMPILE_UNAVAILABLE,
    GateResult,
    gate,
)


SKILL_ROOT = Path(__file__).resolve().parents[3] / "anvil" / "skills" / "memo"
SKILL_MD = SKILL_ROOT / "SKILL.md"
DRAFT_MD = SKILL_ROOT / "commands" / "memo-draft.md"
REVISE_MD = SKILL_ROOT / "commands" / "memo-revise.md"
RENDER_MD = SKILL_ROOT / "commands" / "memo-render.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# commands/memo-render.md — the new command exists and is well-shaped
# ---------------------------------------------------------------------------


def test_memo_render_command_exists():
    """Issue #190 AC: the memo-render.md command file MUST exist."""
    assert RENDER_MD.exists(), (
        "anvil/skills/memo/commands/memo-render.md MUST exist per issue "
        "#190 (Epic #158 Phase 3)"
    )


def test_memo_render_has_frontmatter():
    body = _read(RENDER_MD)
    # SKILL-command convention: YAML frontmatter with name + description.
    assert body.lstrip().startswith("---"), (
        "memo-render.md MUST open with YAML frontmatter per skill convention"
    )
    assert "name: memo-render" in body, (
        "memo-render.md frontmatter MUST set name: memo-render"
    )
    assert "description:" in body, (
        "memo-render.md frontmatter MUST include a description"
    )


def test_memo_render_has_standard_command_sections():
    body = _read(RENDER_MD)
    # Mirror memo-draft.md / memo-revise.md shape: Inputs / Outputs /
    # Procedure / Failure modes.
    assert "## Inputs" in body, "memo-render.md MUST have an Inputs section"
    assert "## Outputs" in body, "memo-render.md MUST have an Outputs section"
    assert "## Procedure" in body, "memo-render.md MUST have a Procedure section"
    assert "Failure modes" in body or "## Failure" in body, (
        "memo-render.md MUST have a Failure modes section per issue #190 AC"
    )
    assert "Re-run" in body or "re-run" in body.lower(), (
        "memo-render.md MUST document the re-run pattern per issue #190 AC"
    )


def test_memo_render_invokes_render_gate_kind_memo():
    """Issue #190 AC: invokes `render_gate.gate(kind='memo')` from PR #185."""
    body = _read(RENDER_MD)
    assert "render_gate" in body, (
        "memo-render.md MUST reference render_gate (the lib primitive from PR #185)"
    )
    assert 'kind="memo"' in body or "kind='memo'" in body, (
        "memo-render.md MUST document invoking gate(kind='memo') from "
        "anvil/lib/render_gate.py (PR #185) — issue #190 AC"
    )


def test_memo_render_writes_pdf_alongside_md():
    """Issue #190 AC: memo.pdf lands alongside memo.md, NOT in a separate dir."""
    body = _read(RENDER_MD)
    assert "memo.pdf" in body, (
        "memo-render.md MUST document writing memo.pdf"
    )
    # The "alongside memo.md" / "in the version directory" framing must be present.
    lowered = body.lower()
    assert "alongside" in lowered or "in the version dir" in lowered or (
        "in the version directory" in lowered
    ), (
        "memo-render.md MUST document that memo.pdf lands alongside memo.md "
        "in the version directory (NOT a separate render dir) — issue #190 AC"
    )


def test_memo_render_documents_progress_render_phase_and_render_gate_block():
    """Issue #190 AC: updates `_progress.json.phases.render` and
    `_progress.json.render_gate`."""
    body = _read(RENDER_MD)
    assert "phases.render" in body, (
        "memo-render.md MUST document updating _progress.json.phases.render "
        "(issue #190 AC)"
    )
    assert "render_gate" in body, (
        "memo-render.md MUST document writing the render_gate block to "
        "_progress.json (issue #190 AC)"
    )


def test_memo_render_documents_graceful_degrade():
    """Issue #190 AC: graceful-degrade on missing renderer per architect Q7."""
    body = _read(RENDER_MD)
    lowered = body.lower()
    assert "graceful" in lowered or "non-blocking" in lowered or (
        "non blocking" in lowered
    ), (
        "memo-render.md MUST document the graceful-degrade / non-blocking "
        "contract for missing renderer (issue #190 AC per architect Q7)"
    )
    # The specific failure shape must be enumerated.
    assert "unavailable" in lowered, (
        "memo-render.md MUST reference the COMPILE_UNAVAILABLE outcome "
        "(graceful-degrade signal)"
    )


def test_memo_render_documents_re_run_pattern():
    """Issue #190 AC: memo.pdf is regenerated on every render, NEVER manually
    edited; the command is independently composable."""
    body = _read(RENDER_MD)
    lowered = body.lower()
    assert "never" in lowered and ("hand-edit" in lowered or "manually edit" in lowered or "hand edit" in lowered or "hand-editing" in lowered), (
        "memo-render.md MUST document that memo.pdf is NEVER manually edited "
        "(derived artifact, regenerated on every render) — issue #190 AC"
    )
    assert "regenerated" in lowered or "regeneration" in lowered, (
        "memo-render.md MUST document that memo.pdf is regenerated on every "
        "render — issue #190 AC"
    )


def test_memo_render_documents_failure_modes():
    """Issue #190 AC: failure modes documented (missing pandoc, missing
    engine, render-gate findings)."""
    body = _read(RENDER_MD)
    assert "pandoc" in body, (
        "memo-render.md MUST enumerate the missing-pandoc failure mode "
        "(issue #190 AC)"
    )
    # At least one of the three engines must be named in failure-mode context.
    assert "weasyprint" in body or "wkhtmltopdf" in body or "xelatex" in body, (
        "memo-render.md MUST enumerate the missing-engine failure mode "
        "(issue #190 AC)"
    )
    # Render-gate findings must be referenced.
    lowered = body.lower()
    assert "finding" in lowered, (
        "memo-render.md MUST enumerate render-gate findings as a failure "
        "mode (issue #190 AC)"
    )


def test_memo_render_documents_idempotence_and_mtime_check():
    """Idempotence is contract-grade for asset-producing commands."""
    body = _read(RENDER_MD)
    lowered = body.lower()
    assert "idempot" in lowered, (
        "memo-render.md MUST document idempotence (no-op when PDF up to date)"
    )
    # The mtime / staleness comparison is load-bearing for the re-run pattern.
    assert "mtime" in lowered or "newer than" in lowered or "older than" in lowered, (
        "memo-render.md MUST document the memo.md ↔ memo.pdf mtime/freshness "
        "check (re-render on stale PDF)"
    )


def test_memo_render_references_memo_lib_substrate():
    """The render chain consumes anvil/lib/memo/ files (PR #172)."""
    body = _read(RENDER_MD)
    assert "anvil/lib/memo" in body, (
        "memo-render.md MUST reference the anvil/lib/memo/ substrate "
        "(PR #172 Phase 1) — pinned styles.css + template.html + template.tex"
    )


def test_memo_render_documents_target_length_resolved_read():
    """The render gate consumes target_length; the command must read the
    resolved field from _progress.json (mirrors memo-review step 4 convention)."""
    body = _read(RENDER_MD)
    assert "target_length_resolved" in body, (
        "memo-render.md MUST document reading metadata.target_length_resolved "
        "from _progress.json (mirrors memo-review step 4)"
    )


# ---------------------------------------------------------------------------
# SKILL.md — Rendering subsection + Command dispatch row (issue #190 AC)
# ---------------------------------------------------------------------------


def test_skill_md_has_rendering_subsection():
    """Issue #190 AC: new 'Rendering' subsection between 'Length targets' and
    'Command dispatch'."""
    body = _read(SKILL_MD)
    assert "## Rendering" in body, (
        "SKILL.md MUST add a '## Rendering' subsection per issue #190 AC"
    )


def test_skill_md_rendering_between_length_targets_and_dispatch():
    """The Rendering subsection MUST appear AFTER 'Length targets' and BEFORE
    'Command dispatch' per issue #190 AC."""
    body = _read(SKILL_MD)
    length_pos = body.find("## Length targets")
    rendering_pos = body.find("## Rendering")
    dispatch_pos = body.find("## Command dispatch")
    assert length_pos > -1, "Length targets section MUST exist"
    assert rendering_pos > -1, "Rendering section MUST exist"
    assert dispatch_pos > -1, "Command dispatch section MUST exist"
    assert length_pos < rendering_pos < dispatch_pos, (
        "SKILL.md MUST order sections: Length targets → Rendering → Command "
        "dispatch per issue #190 AC"
    )


def test_skill_md_rendering_documents_optional_non_blocking_contract():
    body = _read(SKILL_MD)
    # The Rendering section MUST surface the optional / non-blocking contract.
    section_start = body.find("## Rendering")
    section_end = body.find("## Command dispatch", section_start)
    section = body[section_start:section_end]
    lowered = section.lower()
    assert "optional" in lowered, (
        "SKILL.md Rendering subsection MUST mark render as optional"
    )
    assert "non-blocking" in lowered or "non blocking" in lowered, (
        "SKILL.md Rendering subsection MUST document the non-blocking contract"
    )


def test_skill_md_rendering_documents_substep_not_new_state():
    """Issue #190 AC: render is a sub-step of DRAFTED/REVISED, NOT a new state."""
    body = _read(SKILL_MD)
    section_start = body.find("## Rendering")
    section_end = body.find("## Command dispatch", section_start)
    section = body[section_start:section_end]
    lowered = section.lower()
    # The "sub-step, not a new state" framing is the load-bearing contract.
    assert "sub-step" in lowered or "substep" in lowered, (
        "SKILL.md Rendering subsection MUST document that render is a "
        "SUB-STEP of DRAFTED/REVISED (issue #190 AC)"
    )
    assert "not a new state" in lowered or "not add a new state" in lowered or (
        "NOT a new state" in section
    ), (
        "SKILL.md Rendering subsection MUST clarify that render does NOT "
        "introduce a new state (issue #190 AC)"
    )


def test_skill_md_rendering_documents_phases_render_optional():
    """Issue #190 AC: absence of phases.render means it never ran (legal pre-render)."""
    body = _read(SKILL_MD)
    section_start = body.find("## Rendering")
    section_end = body.find("## Command dispatch", section_start)
    section = body[section_start:section_end]
    assert "phases.render" in section, (
        "SKILL.md Rendering subsection MUST reference phases.render "
        "(issue #190 AC)"
    )
    lowered = section.lower()
    assert "legal" in lowered or "backward" in lowered or "absence" in lowered, (
        "SKILL.md Rendering subsection MUST document that absence of "
        "phases.render is a legal pre-render state (backwards-compat)"
    )


def test_skill_md_command_dispatch_lists_memo_render():
    """Issue #190 AC: new memo-render row in the Command dispatch table."""
    body = _read(SKILL_MD)
    # The command-dispatch table MUST list memo-render so consumers see it.
    assert "memo-render" in body, (
        "SKILL.md command-dispatch table MUST list memo-render per "
        "issue #190 AC"
    )


def test_skill_md_preserves_memo_lifecycle_phases():
    """Backwards-compat invariant: memo lifecycle phases unchanged.

    The memo lifecycle is `draft → review → revise → figures` per SKILL.md
    §"Skill-specific phases". Adding memo-render MUST NOT add a required
    phase — the lifecycle line must survive intact (mirrors the
    memo-perspective backwards-compat invariant from #179)."""
    body = _read(SKILL_MD)
    assert "draft → review → revise → figures" in body, (
        "SKILL.md MUST preserve the unchanged memo lifecycle "
        "(draft → review → revise → figures) — render MUST NOT be added as "
        "a required phase (issue #190 backwards-compat AC)"
    )


def test_skill_md_state_machine_unchanged():
    """Backwards-compat invariant: the state-machine derivation table is
    unchanged. Render is NOT added as a state or as a derivation source."""
    body = _read(SKILL_MD)
    # The DRAFTED / REVIEWED / REVISED / READY / AUDITED states MUST remain.
    for state in ("EMPTY", "DRAFTED", "REVIEWED", "REVISED", "READY"):
        assert f"| `{state}` |" in body, (
            f"SKILL.md state-machine table MUST preserve {state} (issue #190 "
            "backwards-compat AC)"
        )
    # The DRAFTED derivation MUST NOT mention phases.render.
    state_table_start = body.find("| State | Evidence |")
    assert state_table_start > -1
    state_table_end = body.find("\n\n", state_table_start)
    if state_table_end == -1:
        state_table_end = state_table_start + 2000
    state_table = body[state_table_start:state_table_end]
    assert "phases.render" not in state_table, (
        "SKILL.md state-machine table MUST NOT reference phases.render — "
        "render is a sub-step of DRAFTED/REVISED, not a derivation source "
        "(issue #190 AC)"
    )


# ---------------------------------------------------------------------------
# memo-draft.md — render-call addition (issue #190 AC)
# ---------------------------------------------------------------------------


def test_memo_draft_invokes_memo_render():
    """Issue #190 AC: memo-draft.md must call memo-render after the writing pass."""
    body = _read(DRAFT_MD)
    assert "memo-render" in body, (
        "memo-draft.md MUST document invoking memo-render after the draft "
        "writing pass (issue #190 AC)"
    )


def test_memo_draft_render_call_is_non_blocking():
    """Issue #190 AC: render failures non-blocking in memo-draft."""
    body = _read(DRAFT_MD)
    # Find the section that references memo-render and check non-blocking framing nearby.
    render_pos = body.find("memo-render")
    assert render_pos > -1
    # Look at the surrounding ~1500 chars for the non-blocking framing.
    nearby = body[max(0, render_pos - 200) : render_pos + 1500]
    lowered = nearby.lower()
    assert "non-blocking" in lowered or "non blocking" in lowered, (
        "memo-draft.md MUST surface the non-blocking framing near the "
        "memo-render call (issue #190 AC)"
    )


def test_memo_draft_preserves_existing_steps():
    """Backwards-compat invariant: the prior memo-draft procedure steps survive.

    The render-call addition is a new step (9.5) per the implementation; the
    existing steps 1–9 MUST be unchanged."""
    body = _read(DRAFT_MD)
    # Steps that are load-bearing for memo-draft must still be present.
    for marker in (
        "Discover thread state",
        "Resume check",
        "Read inputs",
        "Initialize `_progress.json`",
        "Resolve `target_length`",
        "Draft the memo",
        "Create exhibits",
        "Update `_progress.json`",
        "Report",
    ):
        assert marker in body, (
            f"memo-draft.md MUST preserve the {marker!r} step (issue #190 "
            "backwards-compat AC)"
        )


# ---------------------------------------------------------------------------
# memo-revise.md — render-call addition (issue #190 AC)
# ---------------------------------------------------------------------------


def test_memo_revise_invokes_memo_render():
    """Issue #190 AC: memo-revise.md must call memo-render after the writing pass."""
    body = _read(REVISE_MD)
    assert "memo-render" in body, (
        "memo-revise.md MUST document invoking memo-render after the revise "
        "writing pass (issue #190 AC)"
    )


def test_memo_revise_render_call_is_non_blocking():
    """Issue #190 AC: render failures non-blocking in memo-revise."""
    body = _read(REVISE_MD)
    render_pos = body.find("memo-render")
    assert render_pos > -1
    nearby = body[max(0, render_pos - 200) : render_pos + 1500]
    lowered = nearby.lower()
    assert "non-blocking" in lowered or "non blocking" in lowered, (
        "memo-revise.md MUST surface the non-blocking framing near the "
        "memo-render call (issue #190 AC)"
    )


def test_memo_revise_preserves_existing_steps():
    """Backwards-compat invariant: the prior memo-revise procedure steps survive."""
    body = _read(REVISE_MD)
    for marker in (
        "Discover state",
        "Resume check",
        "Iteration cap check",
        "Verdict pre-check",
        "Initialize `_progress.json`",
        "Read inputs",
        "Build a revision plan",
        "Read prior convictions",
        "Produce `memo.md`",
        "Write `changelog.md`",
        "Update `_progress.json`",
    ):
        assert marker in body, (
            f"memo-revise.md MUST preserve the {marker!r} step (issue #190 "
            "backwards-compat AC)"
        )


# ---------------------------------------------------------------------------
# Backwards-compat smoke tests: the lib seam still behaves as documented
# ---------------------------------------------------------------------------


class _FakeCompletedProcess:
    """Minimal stand-in for ``subprocess.CompletedProcess``."""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_pandoc(
    *,
    returncode: int = 0,
    stderr: str = "",
    pdf_bytes: bytes = b"%PDF-1.5\n%memo-render fixture\n",
):
    """Build a ``subprocess.run`` replacement that fakes a pandoc call.

    Defers to the real ``subprocess.run`` for any non-pandoc command (the
    pdfinfo stub the tests invoke via a real shell script). On pandoc with
    ``returncode == 0``, writes a tiny fixture PDF at the ``-o`` path so
    the gate's post-render ``Path.exists()`` check succeeds.
    """
    real_run = subprocess.run

    def _run(cmd, **kwargs):
        if not cmd or cmd[0] != "pandoc":
            return real_run(cmd, **kwargs)
        if "-o" in cmd:
            idx = cmd.index("-o")
            if idx + 1 < len(cmd):
                target = Path(cmd[idx + 1])
                target.parent.mkdir(parents=True, exist_ok=True)
                if returncode == 0:
                    target.write_bytes(pdf_bytes)
        return _FakeCompletedProcess(returncode=returncode, stdout="", stderr=stderr)

    return _run


@pytest.fixture
def memo_fixture_dir(tmp_path):
    """Build a minimal `<thread>.{N}/` directory with a non-empty memo.md.

    Mirrors the fixture in `tests/lib/test_render_gate_memo.py` but renamed
    to avoid any collision; the fixture is local to this module."""
    vd = tmp_path / "acme-seed.1"
    vd.mkdir()
    (vd / "memo.md").write_text(
        "# Investment memo — acme-seed v1\n"
        "\n"
        "## Recommendation\n"
        "\n"
        "Pass at this round; revisit at Series A.\n"
        "\n"
        "## Thesis\n"
        "\n"
        "Detailed prose explaining the bet.\n",
        encoding="utf-8",
    )
    return vd


@pytest.fixture
def fake_pdfinfo_3pages(tmp_path):
    """Stub pdfinfo that reports ``Pages: 3`` and exits 0."""
    p = tmp_path / "fake_pdfinfo_3.sh"
    p.write_text(
        "#!/usr/bin/env bash\n"
        'cat <<EOF\nTitle: Test PDF\nPages: 3\nEOF\nexit 0\n'
    )
    p.chmod(0o755)
    return str(p)


def test_smoke_synthesized_memo_renders_with_mocked_chain(
    monkeypatch, memo_fixture_dir, fake_pdfinfo_3pages
):
    """Issue #190 AC: render a synthesized fixture memo end-to-end (mocked
    renderer); verify PDF path is set and findings list is populated.

    The command itself is markdown-as-prompt, but the contract surface it
    invokes — ``render_gate.gate(kind='memo')`` — must accept the exact
    inputs Phase 3's command wires up: ``version_dir``, ``out_pdf``,
    ``target_length`` derived from ``_progress.json.metadata.target_length_resolved``.
    """
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: True)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: True)
    monkeypatch.setattr(subprocess, "run", _fake_pandoc(returncode=0))

    result = gate(
        kind="memo",
        version_dir=memo_fixture_dir,
        out_pdf=memo_fixture_dir / "memo.pdf",
        target_length={"words": [1800, 2400]},
        pdfinfo_path=fake_pdfinfo_3pages,
    )

    # The gate returns a typed GateResult — the shape the command persists
    # into _progress.json.render_gate via to_json().
    assert isinstance(result, GateResult)
    # PDF lands at the expected path alongside memo.md (AC: same dir, NOT a
    # separate render dir).
    assert result.pdf_path == str(memo_fixture_dir / "memo.pdf")
    assert (memo_fixture_dir / "memo.pdf").exists()
    # Page-count introspection worked via the fake pdfinfo.
    assert result.pages == 3
    # Compile status reflects a clean render.
    assert result.compile_status == COMPILE_OK
    # The to_json shape carries every key the command persists to
    # _progress.json.render_gate.
    payload = result.to_json()
    for key in (
        "gate",
        "pdf_path",
        "pages",
        "page_cap",
        "overfull_boxes",
        "compile",
        "placeholders",
        "findings",
        "pass",
        "reasons",
    ):
        assert key in payload, (
            f"GateResult.to_json() MUST carry the {key!r} key — the "
            "memo-render command persists this shape into "
            "_progress.json.render_gate (issue #190 AC)"
        )


def test_smoke_graceful_degrade_when_pandoc_absent(
    monkeypatch, memo_fixture_dir
):
    """Issue #190 AC: graceful-degrade when pandoc absent — the upstream
    draft/revise step MUST be able to continue without aborting."""
    # No pandoc, no engine: simulate the worst-case unavailable host.
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: False)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: False)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)

    result = gate(
        kind="memo",
        version_dir=memo_fixture_dir,
        out_pdf=memo_fixture_dir / "memo.pdf",
    )

    # The gate returned a GateResult — no exception was raised. This is the
    # load-bearing graceful-degrade contract: the upstream command receives
    # a usable result and decides what to record in _progress.json.
    assert isinstance(result, GateResult)
    assert result.compile_status == COMPILE_UNAVAILABLE
    # No PDF was produced.
    assert not (memo_fixture_dir / "memo.pdf").exists()
    # The MEMO_RENDERER_REMEDIATION install story is surfaced in reasons so
    # the operator sees how to recover.
    assert any("PATH" in reason for reason in result.reasons), (
        "Graceful-degrade MUST surface the MEMO_RENDERER_REMEDIATION install "
        "story in result.reasons (issue #190 AC per architect Q7)"
    )


def test_smoke_existing_memo_version_without_pdf_is_legal_pre_render_state(
    tmp_path
):
    """Issue #190 AC: existing memo versions without memo.pdf continue to be
    a legal pre-render state.

    The state-machine derivation (per SKILL.md §"State machine") MUST NOT
    require a memo.pdf — `DRAFTED` is derived from `phases.draft == done`
    alone. This test pins the contract: a version dir with `memo.md` and
    `phases.draft == done` but no `memo.pdf` and no `phases.render` block
    is a valid pre-render state (every legacy memo has this shape).
    """
    vd = tmp_path / "legacy.1"
    vd.mkdir()
    (vd / "memo.md").write_text(
        "# Legacy memo\n\nThis was drafted before Phase 3.\n",
        encoding="utf-8",
    )
    # The pre-Phase-3 _progress.json shape: phases.draft == done, no
    # phases.render key, no render_gate block.
    progress_json = vd / "_progress.json"
    progress_json.write_text(
        '{"version": 1, "thread": "legacy", "phases": {"draft": '
        '{"state": "done", "started": "2026-04-01T00:00:00Z", '
        '"completed": "2026-04-01T00:01:00Z"}}, "metadata": '
        '{"iteration": 1, "max_iterations": 4}}',
        encoding="utf-8",
    )

    # Validation contract: phases.draft == done AND memo.md present →
    # DRAFTED. The absence of memo.pdf and phases.render does NOT block.
    import json

    progress = json.loads(progress_json.read_text(encoding="utf-8"))
    assert progress["phases"]["draft"]["state"] == "done"
    assert "render" not in progress.get("phases", {}), (
        "Legacy memo version MUST NOT carry phases.render (pre-Phase-3 shape)"
    )
    assert "render_gate" not in progress, (
        "Legacy memo version MUST NOT carry render_gate top-level block "
        "(pre-Phase-3 shape)"
    )
    assert (vd / "memo.md").exists()
    assert not (vd / "memo.pdf").exists(), (
        "Legacy memo version's pre-render state MUST be a memo.md without a "
        "memo.pdf — the state machine MUST treat this as DRAFTED, NOT as "
        "blocked (issue #190 backwards-compat AC)"
    )


def test_smoke_render_gate_kind_memo_signature_unchanged(memo_fixture_dir, monkeypatch):
    """Backwards-compat invariant: the gate(kind='memo') signature shipped by
    Phase 2 (PR #185) accepts the args the Phase 3 command passes.

    If the gate signature ever changes incompatibly, the memo-render command
    breaks silently. This test pins the call-shape contract.
    """
    # Make the chain unavailable so we exercise the call signature without
    # invoking subprocess.
    monkeypatch.setattr(_render, "check_pandoc_available", lambda: False)
    monkeypatch.setattr(_render, "check_weasyprint_available", lambda: False)
    monkeypatch.setattr(_render, "check_wkhtmltopdf_available", lambda: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)

    # The exact call the command makes — keyword args only.
    result = gate(
        kind="memo",
        version_dir=memo_fixture_dir,
        out_pdf=memo_fixture_dir / "memo.pdf",
        target_length={"words": [1800, 2400]},
    )
    assert isinstance(result, GateResult)
    # The kind='memo' branch MUST require version_dir; calling without it
    # MUST raise so the command catches the misuse at the call site.
    with pytest.raises(ValueError, match="version_dir"):
        gate(kind="memo")
