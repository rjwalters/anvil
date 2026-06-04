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
from typing import List, Optional

from .apply import ApplyResult, apply_plan
from .detect import (
    ProjectInventory,
    Shape,
    inventory_project,
    _classify,
)
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
    lines.append(f"**Detected shape**: `{shape.value}`")
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
                lines.append(
                    f"- BRIEF merge: add `documents:` entry "
                    f"(artifact_type={bm.artifact_type}{tl_str}{ro_str})"
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


__all__ = ["RunResult", "run"]
