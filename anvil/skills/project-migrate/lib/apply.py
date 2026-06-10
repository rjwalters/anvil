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
from dataclasses import dataclass, field, replace as _dc_replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .detect import Shape
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
    # Count occurrences in the original text before replacing. `str.count`
    # is non-overlapping, which matches `str.replace` semantics.
    count = text.count(old_string)
    new_text = text.replace(old_string, new_string)
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


def _format_iteration_cap_rationale(rationale: str) -> List[str]:
    """Format the iteration_cap_rationale as a YAML literal block scalar.

    The rationale is operator-authored prose (often multi-line per the
    deck-skill `.anvil.json` precedent); a literal block (`|`) preserves
    it verbatim without quote-escaping concerns.
    """
    out: List[str] = ["    iteration_cap_rationale: |"]
    for line in rationale.splitlines() or [""]:
        out.append(f"      {line}".rstrip())
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


def _serialize_document_entry(merge: BriefMergeOp) -> List[str]:
    """Serialize one ``documents:`` entry as YAML lines (no newlines).

    Extracted from :func:`render_project_brief` (issue #406) so the
    surgical-append path (:func:`_append_brief_documents`) emits entries
    byte-identical to the full-render path. Honors the YAML comment
    carriers: ``slug_comment`` on the ``- slug:`` line (enrollment
    provenance) and ``todo_comment`` on the ``artifact_type:`` line
    (the #408 operator-confirmation marker).
    """
    out: List[str] = []
    slug_line = f"  - slug: {merge.slug}"
    if merge.slug_comment:
        slug_line += f"  # {merge.slug_comment}"
    out.append(slug_line)
    artifact_type_line = f"    artifact_type: {merge.artifact_type}"
    if merge.todo_comment:
        artifact_type_line += f"  # {merge.todo_comment}"
    out.append(artifact_type_line)
    if merge.target_length is not None:
        out.append(
            f"    target_length: {_format_target_length(merge.target_length)}"
        )
    if merge.target_length_overrides:
        out.extend(
            _format_target_length_overrides(merge.target_length_overrides)
        )
    if merge.max_iterations is not None and merge.iteration_cap_rationale:
        out.append(f"    max_iterations: {merge.max_iterations}")
        out.extend(
            _format_iteration_cap_rationale(merge.iteration_cap_rationale)
        )
    if merge.rubric_overrides:
        out.extend(_format_rubric_overrides(merge.rubric_overrides))
    return out


def render_project_brief(
    plan: Plan, *, existing_text: Optional[str] = None
) -> str:
    """Render the project BRIEF text for ``plan`` (pure — no disk writes).

    Extracted from the apply-time write path (issue #408) so the SAME
    code path serves both the dry-run report (which prints the full
    proposed BRIEF body) and ``--apply`` (which writes it atomically).

    Preserves any existing top-level frontmatter keys (``project``,
    ``audience``, ``hard_rules``) and the body prose. Only the
    ``documents:`` block is regenerated from the plan's ``brief_merge``
    entries.

    Implementation: parse the existing BRIEF (if any) to preserve project
    metadata; build a new YAML frontmatter from scratch with the merged
    documents; emit the body verbatim.

    When no existing BRIEF is present, emits a fresh BRIEF with default
    ``project: <project-dir-name>``, empty ``audience`` and ``hard_rules``,
    and the migration-author note in the body. When the plan is a BARE
    synthesis (``plan.synthesize_brief`` — issue #408), every defaulted
    or inferred frontmatter value additionally carries a
    ``# TODO(operator)`` YAML comment, and the body carries an
    operator-confirmation checklist (body prose survives BRIEF rewrites
    verbatim; YAML comments survive the no-op idempotent path but would
    be dropped by a future non-noop rewrite).
    """
    # Parse the existing BRIEF to extract preserved fields and body.
    preserved: Dict[str, object] = {}
    body = ""
    if existing_text is not None:
        preserved, body = _split_brief_for_rewrite(existing_text)
    project_name = preserved.get("project")
    project_name_preserved = (
        isinstance(project_name, str) and bool(project_name.strip())
    )
    if not project_name_preserved:
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
            # Preserve a pre-existing paired iteration-cap override
            # (issue #382 — written by an earlier migration or by the
            # operator per the memo per-document override contract).
            mi = entry.get("max_iterations")
            rationale = entry.get("iteration_cap_rationale")
            if not isinstance(mi, int) or isinstance(mi, bool):
                mi = None
            if not isinstance(rationale, str) or not rationale.strip():
                rationale = None
            if mi is None or rationale is None:
                mi = None
                rationale = None
            merges.append(
                BriefMergeOp(
                    slug=slug,
                    artifact_type=artifact_type if isinstance(artifact_type, str) else _DEFAULT_ARTIFACT_TYPE,
                    target_length=tl_tuple,
                    target_length_overrides=tlo_map if tlo_map else None,
                    rubric_overrides=ro,
                    max_iterations=mi,
                    iteration_cap_rationale=rationale,
                )
            )
            seen_slugs.add(slug)

    # Now serialize. Under bare synthesis (issue #408), defaulted
    # project-level fields get operator-confirmation TODO comments —
    # YAML comments are invisible to yaml.safe_load and to the
    # no-pyyaml hand parser, so parse behavior is unaffected.
    synthesizing = bool(getattr(plan, "synthesize_brief", False))
    frontmatter_lines: List[str] = []
    project_line = f"project: {project_name}"
    if synthesizing and not project_name_preserved:
        project_line += (
            "  # TODO(operator): confirm — defaulted from directory name"
        )
    frontmatter_lines.append(project_line)
    if audience:
        frontmatter_lines.append("audience:")
        for item in audience:
            frontmatter_lines.append(f"  - {item}")
    elif synthesizing:
        frontmatter_lines.append(
            "audience: []  # TODO(operator): fill in the audience"
        )
    else:
        frontmatter_lines.append("audience: []")
    if hard_rules:
        frontmatter_lines.append("hard_rules:")
        for item in hard_rules:
            frontmatter_lines.append(f"  - {item}")
    elif synthesizing:
        frontmatter_lines.append(
            "hard_rules: []  # TODO(operator): fill in hard rules (if any)"
        )
    else:
        frontmatter_lines.append("hard_rules: []")
    frontmatter_lines.append("documents:")
    for merge in merges:
        frontmatter_lines.extend(_serialize_document_entry(merge))

    # Body: keep existing body verbatim if any; else emit a stub. Under
    # bare synthesis the stub mirrors the TODO list into prose — body
    # prose IS preserved verbatim on a future BRIEF rewrite, whereas
    # the frontmatter YAML comments would be dropped by a non-noop
    # rewrite (the rewrite round-trips frontmatter through a dict).
    if not body.strip():
        if synthesizing:
            checklist: List[str] = [
                "- [ ] Confirm `project:` (defaulted from the directory "
                "name).",
                "- [ ] Fill in `audience:` (left empty by synthesis).",
                "- [ ] Fill in `hard_rules:` (left empty by synthesis).",
            ]
            for doc in plan.documents:
                for item in getattr(doc, "operator_todos", []):
                    checklist.append(f"- [ ] {item}")
            body = (
                "\n# Project BRIEF\n\n"
                f"Project: {project_name}\n\n"
                "*Synthesized by `anvil:project-migrate` from observed "
                "on-disk state (bare version-dir threads — no legacy anvil "
                "config was found to merge from). Every inferred value in "
                "the frontmatter carries a `# TODO(operator)` comment; the "
                "checklist below mirrors them so the confirmations survive "
                "future BRIEF rewrites.*\n\n"
                "## Operator confirmation checklist\n\n"
                + "\n".join(checklist)
                + "\n"
            )
        else:
            body = (
                "\n# Project BRIEF\n\n"
                f"Project: {project_name}\n\n"
                "*Migrated by `anvil:project-migrate`. Operator should review and "
                "edit this BRIEF to add audience, hard_rules, and per-document "
                "context.*\n"
            )

    return (
        "---\n"
        + "\n".join(frontmatter_lines)
        + "\n---\n"
        + body
    )


def _write_project_brief(
    plan: Plan, project_brief_path: Path, *, existing_text: Optional[str]
) -> None:
    """Write the project BRIEF atomically (temp file + rename).

    Thin write wrapper around :func:`render_project_brief` — the text
    construction lives there so the dry-run report and the apply step
    share one code path (issue #408).
    """
    final_text = render_project_brief(plan, existing_text=existing_text)
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
# Enrollment BRIEF write (issue #406) — surgical append, never re-render
# ---------------------------------------------------------------------------


# A top-level YAML frontmatter key: starts at column 0 with an
# identifier followed by ':'. Literal block scalars and list entries are
# indented, so they cannot false-trigger the block boundary.
_TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:")

# The `documents:` key in block form (nothing after the colon except an
# optional trailing comment). An inline form (`documents: [...]`) is not
# appendable and is rejected with a clear error.
_DOCUMENTS_KEY_RE = re.compile(r"^documents:\s*(#.*)?$")

_ENROLLMENT_LOG_HEADER = "## Enrollment log"


def _append_brief_documents(existing_text: str, plan: Plan) -> str:
    """Surgically append ``documents:`` entries to an existing BRIEF text.

    The migrate-mode write path (:func:`render_project_brief`) round-trips
    the frontmatter through a parsed dict, which is LOSSY: it drops
    top-level ``theme:``, per-doc ``render_*`` / ``latex_header_includes``
    keys, every YAML comment (including #408's ``TODO(operator)``
    markers), quoting style, and entry order. Byte-identical preservation
    of operator-authored content is only achievable by raw-text
    insertion — so this function:

    1. Locates the top-level ``documents:`` line in the raw frontmatter.
    2. Finds the end of the ``documents:`` block (the next top-level
       ``key:`` line, or the closing ``---``). Indented content —
       list entries, literal block scalars — cannot false-trigger the
       boundary.
    3. Inserts the new entry lines (serialized via
       :func:`_serialize_document_entry` — the same serializer the
       full-render path uses) at the END of the block. Every other byte
       is untouched.
    4. Appends the plan's enrollment-log lines to the END of the body
       (body prose remains a byte-identical prefix).

    Raises ``ValueError`` when the existing text has no parseable
    frontmatter or no block-form ``documents:`` key — the caller treats
    that as "never modify a BRIEF we can't parse".
    """
    lines = existing_text.splitlines(keepends=True)

    # Locate the frontmatter delimiters.
    first_idx = 0
    while first_idx < len(lines) and lines[first_idx].strip() == "":
        first_idx += 1
    if first_idx >= len(lines) or lines[first_idx].strip() != "---":
        raise ValueError(
            "existing BRIEF has no YAML frontmatter (missing opening "
            "'---'); refusing to append."
        )
    close_idx = None
    for i in range(first_idx + 1, len(lines)):
        if lines[i].strip() == "---":
            close_idx = i
            break
    if close_idx is None:
        raise ValueError(
            "existing BRIEF frontmatter is unterminated (no closing "
            "'---'); refusing to append."
        )

    # Locate the top-level `documents:` block.
    doc_idx = None
    for i in range(first_idx + 1, close_idx):
        if _DOCUMENTS_KEY_RE.match(lines[i]):
            doc_idx = i
            break
    if doc_idx is None:
        raise ValueError(
            "existing BRIEF frontmatter has no block-form `documents:` "
            "key; refusing to append. (An inline `documents: [...]` "
            "list is not appendable — convert it to block form first.)"
        )

    # End of the documents block: the next top-level key, or the
    # closing delimiter.
    end_idx = close_idx
    for i in range(doc_idx + 1, close_idx):
        if _TOP_LEVEL_KEY_RE.match(lines[i]):
            end_idx = i
            break

    # Serialize the new entries — same serializer as the render path.
    entry_lines: List[str] = []
    for doc in plan.documents:
        if doc.brief_merge is None:
            continue
        entry_lines.extend(
            line + "\n" for line in _serialize_document_entry(doc.brief_merge)
        )

    appended = "".join(lines[:end_idx]) + "".join(entry_lines) + "".join(
        lines[end_idx:]
    )
    return _append_enrollment_log(appended, plan)


def _append_enrollment_log(text: str, plan: Plan) -> str:
    """Append the plan's enrollment-log lines to the end of ``text``.

    Body prose survives any future BRIEF re-render verbatim (the
    rewrite path splits it off raw), so the enrollment provenance
    recorded here is durable even though the matching YAML comments
    are not. Appending at the end keeps every pre-existing byte a
    byte-identical prefix of the result.
    """
    log_lines: List[str] = []
    for doc in plan.documents:
        log_lines.extend(getattr(doc, "enrollment_log", []))
    if not log_lines:
        return text
    out = text
    if not out.endswith("\n"):
        out += "\n"
    if _ENROLLMENT_LOG_HEADER not in out:
        out += f"\n{_ENROLLMENT_LOG_HEADER}\n\n"
    out += "\n".join(f"- {line}" for line in log_lines) + "\n"
    return out


def render_enroll_brief(
    plan: Plan, *, existing_text: Optional[str] = None
) -> str:
    """Render the BRIEF text for an enrollment plan (pure — no writes).

    Dispatches on ``plan.brief_mode``:

    - ``"append"`` — surgical textual append into ``existing_text``
      (which MUST be provided): pre-existing frontmatter and body are
      byte-identical prefixes of the result.
    - ``"render"`` — no project BRIEF exists yet; a fresh one is
      synthesized via :func:`render_project_brief` (the #408 code path,
      including the TODO-marker discipline when
      ``plan.synthesize_brief`` is set), with the enrollment log
      appended to the body.

    Shared by the dry-run report (full proposed-BRIEF preview) and the
    apply step, so the preview is byte-identical to the eventual write.
    """
    if plan.brief_mode == "append":
        if existing_text is None:
            raise ValueError(
                "brief_mode='append' requires the existing BRIEF text."
            )
        return _append_brief_documents(existing_text, plan)
    rendered = render_project_brief(plan, existing_text=existing_text)
    return _append_enrollment_log(rendered, plan)


def _validate_brief_strict_post_write(
    project_dir: Path,
) -> Tuple[bool, Optional[str]]:
    """Strict-parse the just-written BRIEF (issue #406 safety net).

    Returns ``(ok, error_message)``. When ``anvil.lib`` is not
    importable (a partial install layout), validation is skipped and
    the write is trusted — the renderer emits only schema-valid shapes.
    Listed-but-missing warnings from ``validate_dirs`` are suppressed
    (a pre-existing unstarted entry is not an enrollment failure).
    """
    try:
        from anvil.lib.project_brief import load_project_brief_strict
    except ImportError:
        return True, None
    import warnings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            load_project_brief_strict(project_dir, validate_dirs=True)
    except (ValueError, FileNotFoundError) as exc:
        return False, str(exc)
    return True, None


def _write_enroll_brief(plan: Plan, result: ApplyResult) -> None:
    """Write the BRIEF for an enrollment plan (succeeded subset only).

    Divergence from migrate mode, specified by issue #406: migrate
    skips the BRIEF write entirely when ANY doc failed; enroll writes
    BRIEF entries for the SUCCEEDED subset — otherwise succeeded files
    are moved-but-unlisted and strict ``validate_dirs`` parsing of the
    project fails. Per-doc apply failures were already rolled back by
    the snapshot machinery, so the failed files remain loose and
    re-enrollable.

    Post-write, the BRIEF is strict-parsed (``validate_dirs=True``); on
    failure the previous text is restored (or the new file removed) and
    the error is surfaced — never leave behind a BRIEF we can't parse.
    """
    succeeded = set(result.applied_docs)
    docs = [
        doc
        for doc in plan.documents
        if doc.slug in succeeded and doc.brief_merge is not None
    ]
    if not docs:
        return

    sub_plan = _dc_replace(plan, documents=docs)

    existing_text: Optional[str] = None
    if plan.project_brief_path.is_file():
        try:
            existing_text = plan.project_brief_path.read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            result.notes.append(f"BRIEF read failed: {exc}")
            return

    try:
        final_text = render_enroll_brief(sub_plan, existing_text=existing_text)
    except ValueError as exc:
        result.notes.append(f"BRIEF append failed: {exc}")
        return

    tmp_path = plan.project_brief_path.with_suffix(".md.tmp")
    try:
        tmp_path.write_text(final_text, encoding="utf-8")
        os.replace(str(tmp_path), str(plan.project_brief_path))
    except OSError as exc:
        result.notes.append(f"BRIEF write failed: {exc}")
        return

    ok, err = _validate_brief_strict_post_write(plan.project_dir)
    if not ok:
        # Restore the pre-write state — never leave an unparseable BRIEF.
        try:
            if existing_text is not None:
                plan.project_brief_path.write_text(
                    existing_text, encoding="utf-8"
                )
            else:
                plan.project_brief_path.unlink()
        except OSError:
            pass
        result.notes.append(
            f"BRIEF write rolled back: post-write strict validation "
            f"failed: {err}"
        )
        return

    result.brief_written = True


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

    # Write the project BRIEF.
    #
    # Enrollment plans (issue #406) diverge from migrate mode: the BRIEF
    # is written for the SUCCEEDED subset even when other docs failed
    # (failed docs were rolled back to loose files; succeeded files are
    # moved and MUST be listed or strict validate_dirs parsing breaks).
    if plan.shape == Shape.ENROLL:
        _write_enroll_brief(plan, result)
        return result

    # Migrate mode — only if every doc applied successfully AND the
    # plan has brief_merge entries to record.
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
    "render_enroll_brief",
    "render_project_brief",
]
