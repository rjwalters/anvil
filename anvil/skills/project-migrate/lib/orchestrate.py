"""Top-level command orchestration for `anvil:project-migrate` (issue #297).

Composes :mod:`detect`, :mod:`plan`, :mod:`apply`, and :mod:`verify` into
the four operator-facing flows:

- **Dry-run** (`/anvil:project-migrate <project>`): detect + plan + report.
- **Apply** (`/anvil:project-migrate <project> --apply`): detect + plan +
  report + apply + verify.
- **Report** (`/anvil:project-migrate <project> --report`): detect + plan
  + report.

The skill's command spec consumes this module's :func:`run` function as
the single entry. The function returns a typed :class:`RunResult` and the
markdown report; the command spec formats stderr / stdout from those.

Design notes
------------

- **One entry point per skill flow.** The command spec stays small (it
  invokes :func:`run` and prints results) because all orchestration logic
  lives here.
- **No side effects in dry-run / report modes.** The execution layer
  refuses to run apply unless the explicit `apply=True` flag is set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .apply import (
    ApplyResult,
    apply_plan,
    render_enroll_brief,
    render_migrate_brief,
)
from .detect import (
    ProjectInventory,
    Shape,
    inventory_project,
    _classify,
)
from .adopt_vn import AdoptVnError, build_adopt_vn_plan
from .enroll import EnrollError, build_enroll_plan
from .plan import (
    BriefMergeOp,
    ContentRewrite,
    DocumentPlan,
    Plan,
    Rename,
    build_plan,
)
from .verify import VerifyResult, verify_migration


@dataclass
class RunResult:
    """Typed summary of a :func:`run` invocation.

    Attributes
    ----------
    project_dir
        Absolute path of the project root.
    shape
        Detected shape.
    plan
        Generated plan (always present, even in dry-run).
    apply_result
        Apply outcome; ``None`` for dry-run / report modes.
    verify_result
        Verify outcome; ``None`` when apply was skipped or failed.
    report
        The markdown report (printed verbatim to stdout by the command).
    success
        True iff the run completed without errors. For dry-run this is
        True when shape is recognized; for apply it's True when every
        document migrated and verify passes.
    """

    project_dir: Path
    shape: Shape
    plan: Plan
    apply_result: Optional[ApplyResult] = None
    verify_result: Optional[VerifyResult] = None
    report: str = ""
    success: bool = False


def _format_plan_report(
    project_dir: Path, shape: Shape, plan: Plan
) -> str:
    """Format the plan as a markdown report."""
    lines: List[str] = []
    lines.append(f"# Project migration: {project_dir.name}")
    lines.append("")
    lines.append(f"**Project root**: `{project_dir}`")
    shape_suffix = ""
    if plan.synthesize_brief:
        # Bare sub-state (issue #408) — same PRE_283_CLASSIC dispatch,
        # but the BRIEF is synthesized from observed state rather than
        # merged from legacy config.
        shape_suffix = " (bare — BRIEF will be synthesized)"
    lines.append(f"**Detected shape**: `{shape.value}`{shape_suffix}")
    lines.append(f"**Documents in plan**: {len(plan.documents)}")
    lines.append("")

    if shape == Shape.UNKNOWN:
        lines.append("## Plan")
        lines.append("")
        lines.append(
            "Could not classify this project as a recognized shape. "
            "Verify the path points at a project root and that the "
            "project carries either a `BRIEF.md` or `<thread>.<N>/` "
            "version dirs."
        )
        lines.append("")
        return "\n".join(lines) + "\n"

    if shape == Shape.FULLY_MIGRATED:
        lines.append("## Plan")
        lines.append("")
        lines.append(
            "Project is already in the fully-migrated shape. "
            "No actions required. Re-running `--apply` is a no-op."
        )
        lines.append("")
        return "\n".join(lines) + "\n"

    lines.append("## Plan")
    lines.append("")

    for doc in plan.documents:
        lines.append(f"### `{doc.slug}`")
        lines.append("")
        if doc.is_noop:
            lines.append("- No actions required (already migrated).")
        else:
            for rename in doc.renames:
                try:
                    src_rel = rename.source.relative_to(project_dir)
                except ValueError:
                    src_rel = rename.source
                try:
                    tgt_rel = rename.target.relative_to(project_dir)
                except ValueError:
                    tgt_rel = rename.target
                lines.append(f"- Rename: `{src_rel}` → `{tgt_rel}`")
            for rewrite in doc.content_rewrites:
                try:
                    file_rel = rewrite.file_path.relative_to(project_dir)
                except ValueError:
                    file_rel = rewrite.file_path
                lines.append(
                    f"- Content rewrite in `{file_rel}`: "
                    f"`{rewrite.old_string}` → `{rewrite.new_string}` "
                    f"({rewrite.occurrences}x)"
                )
            if doc.brief_merge is not None:
                bm = doc.brief_merge
                tl_str = ""
                if bm.target_length is not None:
                    tl_str = (
                        f", target_length=[{bm.target_length[0]}, "
                        f"{bm.target_length[1]}]"
                    )
                ro_str = ""
                if bm.rubric_overrides:
                    ro_keys = ", ".join(sorted(bm.rubric_overrides.keys()))
                    ro_str = f", rubric_overrides={{{ro_keys}}}"
                inferred_str = ""
                if bm.inferred:
                    inferred_str = ", inferred — TODO marker emitted"
                lines.append(
                    f"- BRIEF merge: add `documents:` entry "
                    f"(artifact_type={bm.artifact_type}{tl_str}{ro_str}"
                    f"{inferred_str})"
                )
            if doc.anvil_json_to_delete is not None:
                try:
                    rel = doc.anvil_json_to_delete.relative_to(project_dir)
                except ValueError:
                    rel = doc.anvil_json_to_delete
                lines.append(f"- Delete: `{rel}`")
        lines.append("")

    if plan.extra_anvil_jsons_to_delete:
        lines.append("### Stray `.anvil.json` cleanup")
        lines.append("")
        for path in plan.extra_anvil_jsons_to_delete:
            try:
                rel = path.relative_to(project_dir)
            except ValueError:
                rel = path
            lines.append(f"- Delete: `{rel}`")
        lines.append("")

    # Full proposed BRIEF text (issue #408): rendered through the SAME
    # code path the apply step writes (`render_migrate_brief` — the
    # surgical field-level merge of issue #415 when an existing BRIEF
    # carries a documents block), so the dry-run preview is
    # byte-identical to what `--apply` would write. Read-only — the
    # formatter never touches disk beyond reading the existing BRIEF
    # (the dry-run no-mutation contract holds).
    if not plan.is_noop and any(
        doc.brief_merge is not None for doc in plan.documents
    ):
        existing_text: Optional[str] = None
        if plan.project_brief_path.is_file():
            try:
                existing_text = plan.project_brief_path.read_text(
                    encoding="utf-8"
                )
            except OSError:
                existing_text = None
        rendered, merge_notes = render_migrate_brief(
            plan, existing_text=existing_text
        )
        lines.append("## Proposed `BRIEF.md`")
        lines.append("")
        lines.append("````markdown")
        lines.append(rendered.rstrip("\n"))
        lines.append("````")
        lines.append("")
        for note in merge_notes:
            lines.append(f"- Note: {note}")
        if merge_notes:
            lines.append("")

    lines.append("## Verification preview")
    lines.append("")
    lines.append(
        "After apply, the project would round-trip cleanly through "
        "`discover_thread_root` + `load_project_brief`."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def _format_apply_report(apply_result: ApplyResult) -> str:
    """Format the apply outcome as a markdown report (appended to plan report)."""
    lines: List[str] = []
    lines.append("## Apply")
    lines.append("")
    lines.append(
        f"- Applied: {len(apply_result.applied_docs)} documents "
        f"({', '.join(apply_result.applied_docs) or '(none)'})"
    )
    if apply_result.failed_docs:
        lines.append(
            f"- **Failed**: {len(apply_result.failed_docs)} documents:"
        )
        for slug, err in apply_result.failed_docs:
            lines.append(f"  - `{slug}`: {err}")
    lines.append(f"- BRIEF written: {apply_result.brief_written}")
    lines.append(f"- Git used: {apply_result.git_used}")
    lines.append("")
    return "\n".join(lines) + "\n"


def run(
    project_dir: Path,
    *,
    apply: bool = False,
    report_only: bool = False,
) -> RunResult:
    """Execute the project-migrate flow.

    Parameters
    ----------
    project_dir
        Project root.
    apply
        When True, run the apply step after detection + planning. When
        False (the default), perform a dry-run.
    report_only
        Emit a markdown report and exit. Equivalent to dry-run for
        side-effect purposes but reflects the operator's explicit choice.
        Mutually exclusive with ``apply``.

    Returns
    -------
    A :class:`RunResult` carrying the outcome and the formatted report.

    Raises
    ------
    ValueError
        When ``apply`` and ``report_only`` are both True.
    FileNotFoundError
        When ``project_dir`` does not exist or is not a directory.
    """
    if apply and report_only:
        raise ValueError(
            "apply and report_only are mutually exclusive; pass one or "
            "neither."
        )

    project_dir = Path(project_dir).resolve()
    if not project_dir.is_dir():
        raise FileNotFoundError(
            f"Project directory not found: {project_dir}"
        )

    inv = inventory_project(project_dir)
    shape = _classify(inv)
    plan = build_plan(project_dir, shape=shape, inventory=inv)

    result = RunResult(
        project_dir=project_dir,
        shape=shape,
        plan=plan,
    )

    report = _format_plan_report(project_dir, shape, plan)

    if shape == Shape.UNKNOWN:
        result.report = report
        result.success = False
        return result

    if not apply:
        # Dry-run / report mode — return without mutations.
        result.report = report
        result.success = True
        return result

    # Apply mode.
    apply_result = apply_plan(plan)
    result.apply_result = apply_result
    report += "\n" + _format_apply_report(apply_result)

    # Verify only if apply succeeded.
    if not apply_result.failed_docs:
        verify_result = verify_migration(project_dir)
        result.verify_result = verify_result
        report += "\n" + verify_result.to_report()
        result.success = verify_result.ok
    else:
        result.success = False

    result.report = report
    return result


# ---------------------------------------------------------------------------
# Single-file enrollment (issue #406)
# ---------------------------------------------------------------------------


def _format_enroll_report(plan: Plan) -> str:
    """Format an enrollment plan as a markdown report.

    Includes the FULL proposed BRIEF text — rendered through the same
    ``render_enroll_brief`` code path the apply step writes, so the
    preview is byte-identical to the eventual write (the surgical
    append for an existing BRIEF; the synthesized BRIEF otherwise).
    Read-only: the formatter never touches disk beyond reading the
    existing BRIEF.
    """
    project_dir = plan.project_dir
    lines: List[str] = []
    lines.append(f"# Single-file enrollment: {project_dir.name}")
    lines.append("")
    lines.append(f"**Project root**: `{project_dir}`")
    if plan.brief_mode == "append":
        lines.append(
            "**BRIEF**: existing — extended by surgical append "
            "(every pre-existing byte preserved)"
        )
    else:
        lines.append(
            "**BRIEF**: none found — a minimal project BRIEF will be "
            "synthesized (TODO markers on every inferred value)"
        )
    lines.append(f"**Documents in plan**: {len(plan.documents)}")
    lines.append("")
    lines.append("## Plan")
    lines.append("")

    for doc in plan.documents:
        lines.append(f"### `{doc.slug}`")
        lines.append("")
        for rename in doc.renames:
            try:
                src_rel = rename.source.relative_to(project_dir)
            except ValueError:
                src_rel = rename.source
            try:
                tgt_rel = rename.target.relative_to(project_dir)
            except ValueError:
                tgt_rel = rename.target
            lines.append(f"- Move: `{src_rel}` → `{tgt_rel}`")
        if doc.brief_merge is not None:
            bm = doc.brief_merge
            inferred_str = (
                ", inferred — TODO marker emitted" if bm.inferred else ""
            )
            lines.append(
                f"- BRIEF entry: add `documents:` entry "
                f"(artifact_type={bm.artifact_type}{inferred_str})"
            )
        for note in doc.notes:
            lines.append(f"- Note: {note}")
        lines.append("")

    existing_text: Optional[str] = None
    if plan.project_brief_path.is_file():
        try:
            existing_text = plan.project_brief_path.read_text(
                encoding="utf-8"
            )
        except OSError:
            existing_text = None
    rendered = render_enroll_brief(plan, existing_text=existing_text)
    lines.append("## Proposed `BRIEF.md`")
    lines.append("")
    lines.append("````markdown")
    lines.append(rendered.rstrip("\n"))
    lines.append("````")
    lines.append("")
    return "\n".join(lines) + "\n"


def _verify_enrollment(
    plan: Plan, apply_result: ApplyResult
) -> Tuple[str, bool]:
    """Post-apply verification for an enrollment plan.

    Enrollment's contract is narrower than migrate's whole-project
    shape check: for every APPLIED doc, the target body must exist and
    ``discover_thread_root`` must resolve it (guarded import); the
    BRIEF must have been written and strict-parsed (the apply step
    already rolled it back otherwise).
    """
    lines: List[str] = []
    lines.append("## Enrollment verification")
    lines.append("")
    ok = bool(apply_result.brief_written) and not apply_result.failed_docs

    applied = set(apply_result.applied_docs)
    try:
        from anvil.lib.project_discovery import discover_thread_root
    except ImportError:
        discover_thread_root = None  # type: ignore[assignment]

    for doc in plan.documents:
        if doc.slug not in applied:
            continue
        body = doc.renames[0].target if doc.renames else None
        if body is None or not body.is_file():
            lines.append(f"- `{doc.slug}`: body missing at `{body}` — FAIL")
            ok = False
            continue
        if discover_thread_root is not None:
            result = discover_thread_root(body)
            if result is None or result.slug != doc.slug:
                lines.append(
                    f"- `{doc.slug}`: `discover_thread_root` did not "
                    f"resolve `{body}` — FAIL"
                )
                ok = False
                continue
        lines.append(f"- `{doc.slug}`: enrolled — OK")

    lines.append(
        f"- BRIEF written: {'OK' if apply_result.brief_written else 'FAIL'}"
    )
    lines.append("")
    lines.append(f"**Overall**: {'PASS' if ok else 'FAIL'}")
    return "\n".join(lines) + "\n", ok


def run_enroll(
    files: Sequence[Path],
    *,
    project: Optional[Path] = None,
    slug: Optional[str] = None,
    artifact_type: Optional[str] = None,
    apply: bool = False,
) -> RunResult:
    """Execute the single-file enrollment flow (issue #406).

    Mirrors :func:`run`'s signature shape: ``apply=False`` (the
    universal default in this skill) is a dry-run — detect + plan +
    report, zero mutations.

    Parameters
    ----------
    files
        Loose ``.md`` / ``.tex`` files to enroll (one or a batch). A
        batch enrolls into one project.
    project
        Optional explicit project root (``--project``).
    slug
        Optional explicit slug (``--slug``; single file only, must be
        canonical).
    artifact_type
        Optional explicit artifact type (``--artifact-type``;
        validated against the two-tier #394 registry).
    apply
        When True, execute the plan (per-doc atomicity; BRIEF written
        for the succeeded subset).

    Raises
    ------
    EnrollError
        On any plan-time refusal (slug collision, non-md/tex input,
        already-enrolled input, malformed existing BRIEF, …). Raised
        BEFORE any mutation — the whole batch aborts.
    """
    plan = build_enroll_plan(
        files, project=project, slug=slug, artifact_type=artifact_type
    )

    result = RunResult(
        project_dir=plan.project_dir,
        shape=plan.shape,
        plan=plan,
    )
    report = _format_enroll_report(plan)

    if not apply:
        result.report = report
        result.success = True
        return result

    apply_result = apply_plan(plan)
    result.apply_result = apply_result
    report += "\n" + _format_apply_report(apply_result)

    verify_report, ok = _verify_enrollment(plan, apply_result)
    report += "\n" + verify_report
    result.success = ok
    result.report = report
    return result


# ---------------------------------------------------------------------------
# vN report-dir adoption (issue #432)
# ---------------------------------------------------------------------------


def _format_adopt_vn_report(plan: Plan, source_dir: Path) -> str:
    """Format a vN-adoption plan as a markdown report.

    Includes the FULL proposed BRIEF text — rendered through the same
    ``render_enroll_brief`` code path the apply step writes
    (brief_mode-dispatched: surgical append for an existing BRIEF,
    #408-style synthesis otherwise), so the preview is byte-identical
    to the eventual write. Read-only: the formatter never touches disk
    beyond reading the existing BRIEF.
    """
    project_dir = plan.project_dir
    lines: List[str] = []
    lines.append(f"# vN report-dir adoption: {project_dir.name}")
    lines.append("")
    lines.append(f"**Project root**: `{project_dir}`")
    lines.append(f"**vN family dir**: `{source_dir}`")
    if plan.brief_mode == "append":
        lines.append(
            "**BRIEF**: existing — extended by surgical append "
            "(every pre-existing byte preserved)"
        )
    else:
        lines.append(
            "**BRIEF**: none found — a starter project BRIEF will be "
            "synthesized (TODO markers on every inferred value)"
        )
    lines.append(f"**Documents in plan**: {len(plan.documents)}")
    lines.append("")
    lines.append("## Plan")
    lines.append("")

    if not plan.documents:
        lines.append(
            f"No `v{{N}}` family found under `{source_dir}` — nothing "
            f"to adopt. Re-running --adopt-vn on an adopted tree is a "
            f"no-op."
        )
        lines.append("")
        return "\n".join(lines) + "\n"

    for doc in plan.documents:
        lines.append(f"### `{doc.slug}`")
        lines.append("")
        for rename in doc.renames:
            try:
                src_rel = rename.source.relative_to(project_dir)
            except ValueError:
                src_rel = rename.source
            try:
                tgt_rel = rename.target.relative_to(project_dir)
            except ValueError:
                tgt_rel = rename.target
            lines.append(f"- Rename: `{src_rel}` → `{tgt_rel}`")
        if doc.brief_merge is not None:
            bm = doc.brief_merge
            inferred_str = (
                ", inferred — TODO marker emitted" if bm.inferred else ""
            )
            lines.append(
                f"- BRIEF entry: add `documents:` entry "
                f"(artifact_type={bm.artifact_type}{inferred_str})"
            )
        for note in doc.notes:
            lines.append(f"- Note: {note}")
        lines.append("")

    existing_text: Optional[str] = None
    if plan.project_brief_path.is_file():
        try:
            existing_text = plan.project_brief_path.read_text(
                encoding="utf-8"
            )
        except OSError:
            existing_text = None
    rendered = render_enroll_brief(plan, existing_text=existing_text)
    lines.append("## Proposed `BRIEF.md`")
    lines.append("")
    lines.append("````markdown")
    lines.append(rendered.rstrip("\n"))
    lines.append("````")
    lines.append("")
    return "\n".join(lines) + "\n"


def _verify_adopt_vn(
    plan: Plan, apply_result: ApplyResult
) -> Tuple[str, bool]:
    """Post-apply verification for a vN-adoption plan.

    For the adopted document: every renamed version dir must exist at
    its target and ``discover_thread_root`` must resolve it to the
    adopted slug (the #408 non-renamed-body path — discovery accepts a
    version-dir path directly; guarded import). The BRIEF must have
    been written and strict-parsed (the apply step already rolled it
    back otherwise).
    """
    lines: List[str] = []
    lines.append("## Adoption verification")
    lines.append("")
    ok = bool(apply_result.brief_written) and not apply_result.failed_docs

    applied = set(apply_result.applied_docs)
    try:
        from anvil.lib.project_discovery import discover_thread_root
    except ImportError:
        discover_thread_root = None  # type: ignore[assignment]

    for doc in plan.documents:
        if doc.slug not in applied:
            continue
        version_targets = [
            r.target
            for r in doc.renames
            if r.target.name.startswith(f"{doc.slug}.")
            and r.target.name[len(doc.slug) + 1:].isdigit()
        ]
        doc_ok = True
        for target in version_targets:
            if not target.is_dir():
                lines.append(
                    f"- `{doc.slug}`: version dir missing at "
                    f"`{target}` — FAIL"
                )
                doc_ok = False
                continue
            if discover_thread_root is not None:
                resolved = discover_thread_root(target)
                if resolved is None or resolved.slug != doc.slug:
                    lines.append(
                        f"- `{doc.slug}`: `discover_thread_root` did "
                        f"not resolve `{target}` — FAIL"
                    )
                    doc_ok = False
        if doc_ok:
            lines.append(
                f"- `{doc.slug}`: {len(version_targets)} version dirs "
                f"adopted — OK"
            )
        else:
            ok = False

    lines.append(
        f"- BRIEF written: {'OK' if apply_result.brief_written else 'FAIL'}"
    )
    lines.append("")
    lines.append(f"**Overall**: {'PASS' if ok else 'FAIL'}")
    return "\n".join(lines) + "\n", ok


def run_adopt_vn(
    directory: Path,
    *,
    slug: Optional[str] = None,
    artifact_type: Optional[str] = None,
    apply: bool = False,
) -> RunResult:
    """Execute the vN report-dir adoption flow (issue #432).

    Mirrors :func:`run_enroll`'s signature shape: ``apply=False`` (the
    universal default in this skill) is a dry-run — scan + plan +
    report, zero mutations. A directory with no ``v{N}`` family is a
    successful no-op even under ``--apply`` (idempotence).

    Parameters
    ----------
    directory
        The directory holding the ``v{N}/`` family (e.g.
        ``projects/<proj>/reports/``).
    slug
        Optional explicit slug (``--slug``; must be canonical —
        rejected, never re-sanitized). Defaults to the sanitized
        enclosing-dir name.
    artifact_type
        Optional explicit artifact type (``--artifact-type``;
        validated against the two-tier #394 registry). Defaults to
        inferred ``report`` with a TODO marker.
    apply
        When True, execute the plan (per-doc snapshot atomicity;
        enroll-style BRIEF write with strict post-write validation).

    Raises
    ------
    AdoptVnError
        On any plan-time refusal (minor-versioned oddballs, versioned
        sidecar tags, slug/target collisions, malformed existing
        BRIEF, …). Raised BEFORE any mutation.
    """
    source_dir = Path(directory).resolve()
    plan = build_adopt_vn_plan(
        source_dir, slug=slug, artifact_type=artifact_type
    )

    result = RunResult(
        project_dir=plan.project_dir,
        shape=plan.shape,
        plan=plan,
    )
    report = _format_adopt_vn_report(plan, source_dir)

    if not plan.documents:
        # No vN family — successful no-op, even under --apply.
        result.report = report
        result.success = True
        return result

    if not apply:
        result.report = report
        result.success = True
        return result

    apply_result = apply_plan(plan)
    result.apply_result = apply_result
    report += "\n" + _format_apply_report(apply_result)

    verify_report, ok = _verify_adopt_vn(plan, apply_result)
    report += "\n" + verify_report
    result.success = ok
    result.report = report
    return result


__all__ = [
    "AdoptVnError",
    "EnrollError",
    "RunResult",
    "run",
    "run_adopt_vn",
    "run_enroll",
]
