r"""Doc-coverage guard for the datasheet-review single-file-content-read
"documented safe" note (issue #653, follow-up to #643).

Unlike ``installation`` / ``proposal`` — which ship a first-class
``\input{figures/<name>.tex}`` TikZ-standalone convention that inlines figure
content into the body, so their reviewers wire ``resolve_tex_inputs`` — the
datasheet body references EVERY figure class via
``\includegraphics{figures/<name>.pdf}`` (block diagram, typical-application
schematic, package outline — see ``datasheet.tex.j2``). The TikZ standalones
and matplotlib charts are pre-rendered to PDF by ``datasheet-figures.md`` and
included as image files; there is NO in-body ``\input``-ed TikZ chain. So the
single-file read of ``datasheet.tex`` is not a blind spot for this skill.

This module pins that the datasheet reviewer does NOT wire the resolver
(the honest fix for a ``\includegraphics``-only body is a documented-safe
note, not resolver wiring) AND that its step 4a render-gate call now passes
``extra_source_paths=[]`` explicitly for documentation symmetry.

Per the per-skill test filename convention (#58), this file is named
``test_datasheet_review_single_file_safe_doc.py`` to avoid collision.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_DOC = (
    REPO_ROOT
    / "anvil"
    / "skills"
    / "datasheet"
    / "commands"
    / "datasheet-review.md"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_documented_safe_note_present() -> None:
    """Issue #653: the content-read step carries an explicit 'documented-safe'
    note explaining the single-file read is not a blind spot."""
    body = _read(REVIEW_DOC)
    assert "documented-safe" in body.lower() or "documented safe" in body.lower(), (
        "datasheet-review.md MUST carry an explicit documented-safe note at "
        "the content-read step (issue #653)"
    )
    assert "includegraphics" in body, (
        "datasheet-review.md's documented-safe note MUST explain the body is "
        "\\includegraphics-referenced (no in-body \\input TikZ chain) — "
        "issue #653"
    )
    # It must contrast against installation/proposal's real \input convention.
    assert "installation" in body and "proposal" in body, (
        "datasheet-review.md MUST contrast the datasheet shape against the "
        "installation/proposal \\input convention (issue #653)"
    )


def test_datasheet_does_not_wire_the_resolver() -> None:
    r"""Issue #653: datasheet is \includegraphics-only — the honest fix is a
    documented-safe note, NOT wiring resolve_tex_inputs into the reviewer's
    own content read. Guard against a future blanket rollout mis-wiring it."""
    body = _read(REVIEW_DOC)
    # The reviewer must NOT instruct itself to resolve the \input tree the way
    # installation/proposal do. It MAY mention resolve_tex_inputs only to
    # explain the verifier-side generic handling — but never as a step-3/4
    # content-read instruction.
    assert "recursively resolve every `\\input`" not in body, (
        "datasheet-review.md MUST NOT wire resolve_tex_inputs as a content-"
        "read instruction — it is \\includegraphics-only (issue #653)"
    )


def test_step4a_render_gate_passes_empty_extra_source_paths() -> None:
    """Issue #653: the step 4a render-gate call passes extra_source_paths=[]
    explicitly (previously it passed no such argument at all)."""
    body = _read(REVIEW_DOC)
    assert "extra_source_paths=[]" in body, (
        "datasheet-review.md step 4a MUST pass extra_source_paths=[] "
        "explicitly for documentation symmetry (issue #653)"
    )


def test_verifier_side_generic_handling_acknowledged() -> None:
    r"""Issue #653: the note acknowledges the verifier side
    (``check_version_dir`` / ``FIXED_BODY_NAMES``) still generically handles
    any ``.tex`` body, so a hypothetical future ``\input`` child still
    validates — the single-file note is not a functional gap."""
    body = _read(REVIEW_DOC)
    assert "check_version_dir" in body or "evidence_check" in body, (
        "datasheet-review.md's documented-safe note SHOULD acknowledge the "
        "verifier-side generic .tex handling (issue #653)"
    )
    assert "FIXED_BODY_NAMES" in body or "resolve_tex_inputs" in body, (
        "datasheet-review.md's documented-safe note SHOULD name the generic "
        "verifier-side .tex expansion mechanism (issue #653)"
    )
