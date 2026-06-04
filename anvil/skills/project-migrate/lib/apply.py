"""Plan execution for `anvil:project-migrate` (issue #297).

Takes a :class:`Plan` (from :mod:`plan`) and executes it against the
filesystem. The execution is:

- **Atomic per document** — each ``DocumentPlan`` is snapshotted before
  apply, then either succeeds entirely or rolls back from the snapshot.
- **Git-aware** — when the project is under git, prefer ``git mv`` so
  history follows the renamed files.
- **BRIEF-write last** — the project ``BRIEF.md`` write happens after all
  per-doc applies succeed, using a temp-file + rename so it's atomic.

The apply module is the ONLY module in the skill that mutates disk. All
mutation policy (rollback, atomicity, git integration) lives here.

Public API
----------

- ``ApplyResult`` — typed summary of an apply run.
- ``apply_plan(plan, *, use_git=True)`` — execute a plan.
- ``GitInfo`` / ``_detect_git_repo`` — internal helpers, exposed for tests.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .plan import (
    BriefMergeOp,
    ContentRewrite,
    DocumentPlan,
    Plan,
    Rename,
)


# Subdirectory under the project root used for per-doc snapshots during
# apply. Removed on successful apply. Surfaced as a constant so tests can
# assert against it.
ROLLBACK_SUBDIR = ".anvil-migrate-rollback"

# Sentinel used in BRIEF generation when a `.anvil.json` had no
# artifact_type and no operator override was provided. The default is
# "investment-memo" per ``BriefMergeOp``; operators can edit the BRIEF
# after the migration.
_DEFAULT_ARTIFACT_TYPE = "investment-memo"


@dataclass
class ApplyResult:
    """Typed summary of an apply run.

    Attributes
    ----------
    applied_docs
        Slugs of documents whose apply succeeded.
    failed_docs
        ``(slug, error_message)`` pairs for documents whose apply failed
        and was rolled back.
    brief_written
        True iff the project BRIEF was successfully written.
    git_used
        True iff git_mv was used for the renames.
    notes
        Diagnostic strings — typically the per-doc plan notes plus any
        apply-time observations.
    """

    applied_docs: List[str] = field(default_factory=list)
    failed_docs: List[Tuple[str, str]] = field(default_factory=list)
    brief_written: bool = False
    git_used: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class GitInfo:
    """Git repository metadata for an apply target.

    Attributes
    ----------
    is_git
        True when ``project_dir`` is under git (a `.git/` dir exists at or
        above ``project_dir``).
    repo_root
        The root of the git repo (the dir containing `.git/`). ``None``
        when not under git.
    """

    is_git: bool = False
    repo_root: Optional[Path] = None


def _detect_git_repo(directory: Path) -> GitInfo:
    """Walk upward from ``directory`` looking for a `.git/` parent."""
    current = directory.resolve()
    while True:
        if (current / ".git").exists():
            return GitInfo(is_git=True, repo_root=current)
        parent = current.parent
        if parent == current:
            return GitInfo(is_git=False, repo_root=None)
        current = parent


def _git_mv(source: Path, target: Path, repo_root: Path) -> bool:
    """Run ``git mv source target`` from ``repo_root``. Return True on success."""
    try:
        result = subprocess.run(
            ["git", "mv", str(source), str(target)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _rename(source: Path, target: Path, git_info: GitInfo) -> None:
    """Rename ``source`` → ``target``, preferring ``git mv`` when under git.

    Falls back to ``shutil.move`` on any git error. ``target.parent`` is
    created if it doesn't exist. Raises ``OSError`` on hard failure.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if git_info.is_git and git_info.repo_root is not None:
        if _git_mv(source, target, git_info.repo_root):
            return
    # Fallback: plain rename.
    shutil.move(str(source), str(target))


def _rewrite_file(
    file_path: Path, old_string: str, new_string: str
) -> int:
    """Rewrite a file's contents, replacing every ``old_string`` with ``new_string``.

    Returns the number of replacements made. Raises ``OSError`` on read /
    write failure.
    """
    text = file_path.read_text(encoding="utf-8")
    if old_string not in text:
        return 0
    # Count occurrences before replacing so we can return an accurate
    # replacement count.
    new_text = text.replace(old_string, new_string)
    count = (len(text) - len(new_text)) // (len(old_string) - len(new_string)) \
        if len(old_string) != len(new_string) else text.count(old_string)
    if count == 0:
        # Fallback when old_string == new_string length (shouldn't happen
        # in practice for our use case but defend against it).
        count = text.count(old_string)
    file_path.write_text(new_text, encoding="utf-8")
    return count


def _snapshot_doc(doc: DocumentPlan, rollback_root: Path) -> Optional[Path]:
    """Snapshot the source dirs touched by ``doc`` for rollback.

    Returns the rollback path created, or ``None`` when there's nothing to
    snapshot (no-op plan).
    """
    if doc.is_noop:
        return None
    snapshot_dir = rollback_root / doc.slug
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    # Snapshot every source path referenced by a rename, plus the
    # .anvil.json if any.
    sources_to_snapshot: List[Path] = []
    for rename in doc.renames:
        # Some renames reference paths that don't exist yet (intermediate
        # post-rename paths). Snapshot only existing top-level sources.
        if rename.source.exists():
            sources_to_snapshot.append(rename.source)
    if doc.anvil_json_to_delete is not None and doc.anvil_json_to_delete.exists():
        sources_to_snapshot.append(doc.anvil_json_to_delete)

    # Deduplicate by path; prefer the longest path so we don't snapshot
    # both a dir and a file inside it (the dir snapshot covers the file).
    sources_to_snapshot = sorted(set(sources_to_snapshot))

    for src in sources_to_snapshot:
        rel = src.name
        dest = snapshot_dir / rel
        if dest.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dest, symlinks=True)
        else:
            shutil.copy2(src, dest)
    return snapshot_dir


def _restore_doc(doc: DocumentPlan, snapshot_dir: Path) -> None:
    """Roll back ``doc`` by restoring from ``snapshot_dir``.

    Deletes any target paths created by the partial apply, then restores
    each snapshotted source back to its original location.
    """
    # Delete partial targets.
    for rename in doc.renames:
        if rename.target.exists():
            if rename.target.is_dir():
                shutil.rmtree(rename.target, ignore_errors=True)
            else:
                try:
                    rename.target.unlink()
                except OSError:
                    pass
    # Also delete the target_dir if it's empty (we may have created it).
    if doc.target_dir != doc.source_dir and doc.target_dir.exists():
        try:
            doc.target_dir.rmdir()
        except OSError:
            pass

    # Restore sources from snapshot.
    if not snapshot_dir.is_dir():
        return
    for snapshot_entry in snapshot_dir.iterdir():
        # Snapshot lives at <rollback>/<slug>/<basename>. Original path was
        # ``<various-source-dirs>/<basename>`` — we need to know which
        # source dir to restore to. We use the source's parent from the
        # doc plan.
        target_locations = []
        for rename in doc.renames:
            if rename.source.name == snapshot_entry.name:
                target_locations.append(rename.source)
        if doc.anvil_json_to_delete is not None and \
                doc.anvil_json_to_delete.name == snapshot_entry.name:
            target_locations.append(doc.anvil_json_to_delete)
        for restore_to in target_locations:
            if restore_to.exists():
                continue
            restore_to.parent.mkdir(parents=True, exist_ok=True)
            if snapshot_entry.is_dir():
                shutil.copytree(snapshot_entry, restore_to, symlinks=True)
            else:
                shutil.copy2(snapshot_entry, restore_to)


def _apply_document(
    doc: DocumentPlan, git_info: GitInfo, rollback_root: Path
) -> Tuple[bool, Optional[str]]:
    """Apply one ``DocumentPlan``. Returns (success, error_message).

    On any exception, rolls back from the per-doc snapshot and returns
    ``(False, error)``. On success, removes the snapshot and returns
    ``(True, None)``.
    """
    if doc.is_noop:
        return True, None

    snapshot_dir = _snapshot_doc(doc, rollback_root)
    try:
        # Step 1: filesystem renames in declared order.
        for rename in doc.renames:
            if not rename.source.exists():
                # Skip silently — may be an intermediate rename whose source
                # was the target of a previous step.
                continue
            _rename(rename.source, rename.target, git_info)
        # Step 2: content rewrites.
        for rewrite in doc.content_rewrites:
            if not rewrite.file_path.is_file():
                continue
            _rewrite_file(
                rewrite.file_path, rewrite.old_string, rewrite.new_string
            )
        # Step 3: delete .anvil.json after merge (the BRIEF write happens
        # at the project level after every doc applies).
        if doc.anvil_json_to_delete is not None and \
                doc.anvil_json_to_delete.exists():
            try:
                doc.anvil_json_to_delete.unlink()
            except OSError:
                pass
        # Success — remove snapshot.
        if snapshot_dir is not None and snapshot_dir.is_dir():
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        return True, None
    except Exception as exc:
        # Rollback.
        if snapshot_dir is not None:
            try:
                _restore_doc(doc, snapshot_dir)
            except Exception:
                pass  # Best-effort rollback.
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        return False, str(exc)


# ---------------------------------------------------------------------------
# BRIEF write
# ---------------------------------------------------------------------------


def _format_target_length(rng: Tuple[int, int]) -> str:
    """Format a (min, max) words range as the BRIEF YAML form."""
    return f"{{ words: [{rng[0]}, {rng[1]}] }}"


def _format_target_length_overrides(
    overrides: Dict[str, Tuple[int, int]],
) -> List[str]:
    """Format the target_length_overrides block as YAML lines.

    Returns a list of lines with leading whitespace. Caller indents under
    the document entry.
    """
    out: List[str] = ["    target_length_overrides:"]
    for key in sorted(overrides.keys(), key=lambda k: int(k)):
        rng = overrides[key]
        out.append(f"      \"{key}\": [{rng[0]}, {rng[1]}]")
    return out


def _format_rubric_overrides(ro: dict) -> List[str]:
    """Format a rubric_overrides block as YAML lines (indented for BRIEF)."""
    out: List[str] = ["    rubric_overrides:"]
    # Stable iteration order: memo_subtype first, then target_length, then
    # dim_N_calibration in numeric order, then unknown keys alphabetical.
    keys_in_order: List[str] = []
    if "memo_subtype" in ro:
        keys_in_order.append("memo_subtype")
    if "target_length" in ro:
        keys_in_order.append("target_length")
    dim_keys = sorted(
        (k for k in ro.keys() if re.match(r"^dim_\d+_calibration$", k)),
        key=lambda k: int(re.match(r"^dim_(\d+)_calibration$", k).group(1)),
    )
    keys_in_order.extend(dim_keys)
    other = sorted(
        k for k in ro.keys()
        if k not in keys_in_order
    )
    keys_in_order.extend(other)
    for key in keys_in_order:
        val = ro[key]
        if key == "target_length" and isinstance(val, dict) and "words" in val:
            words = val["words"]
            if isinstance(words, list) and len(words) == 2:
                out.append(
                    f"      target_length: {{ words: [{words[0]}, {words[1]}] }}"
                )
                continue
        if isinstance(val, str):
            # Quote strings with potentially-special characters; bare strings
            # otherwise.
            if any(c in val for c in [":", "#", "-"]) or val.startswith('"'):
                escaped = val.replace('"', '\\"')
                out.append(f"      {key}: \"{escaped}\"")
            else:
                out.append(f"      {key}: {val}")
        else:
            # For unknown shapes, JSON-encode the value (YAML is a superset of JSON).
            out.append(f"      {key}: {json.dumps(val)}")
    return out


def _write_project_brief(
    plan: Plan, project_brief_path: Path, *, existing_text: Optional[str]
) -> None:
    """Write the project BRIEF with the merged documents: list.

    Preserves any existing top-level frontmatter keys (``project``,
    ``audience``, ``hard_rules``) and the body prose. Only the
    ``documents:`` block is regenerated from the plan's ``brief_merge``
    entries.

    Implementation: parse the existing BRIEF (if any) to preserve project
    metadata; build a new YAML frontmatter from scratch with the merged
    documents; emit the body verbatim.

    When no existing BRIEF is present, emits a fresh BRIEF with default
    ``project: <project-dir-name>``, empty ``audience`` and ``hard_rules``,
    and the migration-author note in the body.
    """
    # Parse the existing BRIEF to extract preserved fields and body.
    preserved: Dict[str, object] = {}
    body = ""
    if existing_text is not None:
        preserved, body = _split_brief_for_rewrite(existing_text)
    project_name = preserved.get("project")
    if not isinstance(project_name, str) or not project_name.strip():
        project_name = plan.project_dir.name

    audience = preserved.get("audience") or []
    hard_rules = preserved.get("hard_rules") or []

    # Build documents from plan.brief_merge entries.
    merges: List[BriefMergeOp] = []
    seen_slugs: set = set()
    for doc in plan.documents:
        if doc.brief_merge is None:
            continue
        if doc.brief_merge.slug in seen_slugs:
            continue
        seen_slugs.add(doc.brief_merge.slug)
        merges.append(doc.brief_merge)

    # Preserve any pre-existing BRIEF entries whose slug is NOT in our
    # plan (operator-edited entries the planner doesn't touch).
    existing_docs = preserved.get("documents") or []
    if isinstance(existing_docs, list):
        for entry in existing_docs:
            if not isinstance(entry, dict):
                continue
            slug = entry.get("slug")
            if not isinstance(slug, str) or slug in seen_slugs:
                continue
            # Convert this pre-existing entry to a BriefMergeOp so we
            # preserve its values.
            artifact_type = entry.get("artifact_type", _DEFAULT_ARTIFACT_TYPE)
            tl = entry.get("target_length")
            tl_tuple: Optional[Tuple[int, int]] = None
            if isinstance(tl, dict) and "words" in tl:
                words = tl["words"]
                if isinstance(words, list) and len(words) == 2:
                    try:
                        tl_tuple = (int(words[0]), int(words[1]))
                    except (TypeError, ValueError):
                        pass
            tlo = entry.get("target_length_overrides")
            tlo_map: Optional[Dict[str, Tuple[int, int]]] = None
            if isinstance(tlo, dict):
                tlo_map = {}
                for k, v in tlo.items():
                    if isinstance(v, list) and len(v) == 2:
                        try:
                            tlo_map[str(k)] = (int(v[0]), int(v[1]))
                        except (TypeError, ValueError):
                            pass
            ro = entry.get("rubric_overrides")
            if not isinstance(ro, dict):
                ro = None
            merges.append(
                BriefMergeOp(
                    slug=slug,
                    artifact_type=artifact_type if isinstance(artifact_type, str) else _DEFAULT_ARTIFACT_TYPE,
                    target_length=tl_tuple,
                    target_length_overrides=tlo_map if tlo_map else None,
                    rubric_overrides=ro,
                )
            )
            seen_slugs.add(slug)

    # Now serialize.
    frontmatter_lines: List[str] = []
    frontmatter_lines.append(f"project: {project_name}")
    if audience:
        frontmatter_lines.append("audience:")
        for item in audience:
            frontmatter_lines.append(f"  - {item}")
    else:
        frontmatter_lines.append("audience: []")
    if hard_rules:
        frontmatter_lines.append("hard_rules:")
        for item in hard_rules:
            frontmatter_lines.append(f"  - {item}")
    else:
        frontmatter_lines.append("hard_rules: []")
    frontmatter_lines.append("documents:")
    for merge in merges:
        frontmatter_lines.append(f"  - slug: {merge.slug}")
        frontmatter_lines.append(
            f"    artifact_type: {merge.artifact_type}"
        )
        if merge.target_length is not None:
            frontmatter_lines.append(
                f"    target_length: {_format_target_length(merge.target_length)}"
            )
        if merge.target_length_overrides:
            frontmatter_lines.extend(
                _format_target_length_overrides(merge.target_length_overrides)
            )
        if merge.rubric_overrides:
            frontmatter_lines.extend(
                _format_rubric_overrides(merge.rubric_overrides)
            )

    # Body: keep existing body verbatim if any; else emit a stub.
    if not body.strip():
        body = (
            "\n# Project BRIEF\n\n"
            f"Project: {project_name}\n\n"
            "*Migrated by `anvil:project-migrate`. Operator should review and "
            "edit this BRIEF to add audience, hard_rules, and per-document "
            "context.*\n"
        )

    final_text = (
        "---\n"
        + "\n".join(frontmatter_lines)
        + "\n---\n"
        + body
    )

    # Atomic write: temp file + rename.
    tmp_path = project_brief_path.with_suffix(".md.tmp")
    tmp_path.write_text(final_text, encoding="utf-8")
    os.replace(str(tmp_path), str(project_brief_path))


def _split_brief_for_rewrite(text: str) -> Tuple[Dict[str, object], str]:
    """Return (parsed_frontmatter_dict, body_after_frontmatter).

    Used when rewriting an existing BRIEF so the body and preserved fields
    survive. Falls back to ``({}, original_text)`` when no frontmatter is
    present.
    """
    lines = text.splitlines(keepends=True)
    if not lines:
        return {}, text
    # Find opening delimiter.
    first_idx = 0
    while first_idx < len(lines) and lines[first_idx].strip() == "":
        first_idx += 1
    if first_idx >= len(lines) or lines[first_idx].strip() != "---":
        return {}, text
    close_idx = None
    for i in range(first_idx + 1, len(lines)):
        if lines[i].strip() == "---":
            close_idx = i
            break
    if close_idx is None:
        return {}, text

    yaml_text = "".join(lines[first_idx + 1:close_idx])
    body = "".join(lines[close_idx + 1:])
    try:
        import yaml  # type: ignore
        parsed = yaml.safe_load(yaml_text)
        if not isinstance(parsed, dict):
            parsed = {}
    except Exception:
        parsed = {}
    return parsed, body


# ---------------------------------------------------------------------------
# Top-level apply
# ---------------------------------------------------------------------------


def apply_plan(plan: Plan, *, use_git: bool = True) -> ApplyResult:
    """Execute ``plan`` against the filesystem.

    Parameters
    ----------
    plan
        The plan to execute.
    use_git
        When True (default), prefer ``git mv`` for renames if the project
        is under git. Set False to force plain ``shutil.move`` (used by
        tests).

    Returns
    -------
    An :class:`ApplyResult` summarizing the outcome.
    """
    result = ApplyResult()

    if plan.is_noop:
        # No-op plan — apply succeeds trivially.
        # Still check whether the project BRIEF needs to be touched; for
        # a fully-migrated plan with documents present, the BRIEF is
        # already correct and we do not rewrite (to preserve byte-identity
        # of the idempotence test).
        for doc in plan.documents:
            result.applied_docs.append(doc.slug)
            result.notes.extend(doc.notes)
        return result

    git_info = _detect_git_repo(plan.project_dir) if use_git else GitInfo()
    result.git_used = git_info.is_git

    rollback_root = plan.project_dir / ROLLBACK_SUBDIR
    rollback_root.mkdir(parents=True, exist_ok=True)

    # Apply each document plan in turn.
    for doc in plan.documents:
        success, err = _apply_document(doc, git_info, rollback_root)
        if success:
            result.applied_docs.append(doc.slug)
            result.notes.extend(doc.notes)
        else:
            result.failed_docs.append((doc.slug, err or "unknown error"))

    # Clean up rollback root if empty.
    try:
        if rollback_root.is_dir() and not any(rollback_root.iterdir()):
            rollback_root.rmdir()
    except OSError:
        pass

    # Delete any extra .anvil.json files.
    for path in plan.extra_anvil_jsons_to_delete:
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass

    # Write the project BRIEF — only if at least one doc applied
    # successfully OR the plan has brief_merge entries to record.
    if not result.failed_docs and any(
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
        try:
            _write_project_brief(
                plan, plan.project_brief_path, existing_text=existing_text
            )
            result.brief_written = True
        except OSError as exc:
            result.notes.append(f"BRIEF write failed: {exc}")

    return result


__all__ = [
    "ApplyResult",
    "GitInfo",
    "ROLLBACK_SUBDIR",
    "apply_plan",
]
