"""Migration plan generation for `anvil:project-migrate` (issue #297).

Takes a :class:`ProjectInventory` (from :mod:`detect`) and produces a
:class:`Plan` listing the per-document migration steps. The plan is the
single intermediate artifact between detection and apply — dry-run prints
it; apply executes it.

Design notes
------------

- **Pure planner — no mutations.** Like the detector, this module reads
  files but never writes. The dry-run contract depends on this: plan
  generation can run without touching disk.
- **One plan per project.** The plan groups per-document operations into a
  single object so the apply step has a single iteration target. Each
  ``DocumentPlan`` is independently applyable, which is the atomicity
  contract.
- **Content rewrites are explicit.** Cross-thread reference rewriting is
  recorded as ``ContentRewrite`` entries — the apply step does not need to
  re-scan files; it consumes the recorded rewrites directly. This keeps
  the plan reviewable: the operator can see in the dry-run output exactly
  which strings will be substituted in which files.

Public API
----------

- ``ContentRewrite`` — one in-file substitution.
- ``Rename`` — one filesystem rename (source → target).
- ``BriefMergeOp`` — one ``documents:`` entry to write into the project
  BRIEF.
- ``DocumentPlan`` — per-document plan.
- ``Plan`` — top-level plan covering the whole project.
- ``build_plan(project_dir, shape, inventory=None)`` — top-level entry.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .detect import (
    ANVIL_JSON_FILENAME,
    BRIEF_FILENAME,
    ProjectInventory,
    Shape,
    ThreadInventory,
    _SKILL_FIXED_BODY_FILENAMES,
    inventory_project,
)


# Cross-thread reference pattern. Looks for ``<stem>.<N>`` tokens that
# match a known stem on the project, so we can rewrite them to
# ``<slug>.<N>``.
def _cross_thread_ref_re(stems: List[str]) -> re.Pattern:
    """Build a regex matching any of the known stem.N tokens.

    Used to find cross-thread references in body markdown that need
    rewriting after the directory rename. We anchor with ``\\b`` on both
    sides so partial matches inside other tokens are excluded.
    """
    if not stems:
        # An impossible pattern that matches nothing.
        return re.compile(r"(?!.*)")
    escaped = "|".join(re.escape(stem) for stem in stems)
    return re.compile(rf"\b({escaped})\.(\d+)\b")


@dataclass
class ContentRewrite:
    """One in-file substitution.

    Attributes
    ----------
    file_path
        Absolute path to the file that will be rewritten. The path is the
        TARGET path (where the file will be after renames) so the apply
        step can sequence renames first, content rewrites second.
    old_string
        The literal string to find. Single occurrence per ``ContentRewrite``
        — multi-occurrence rewrites are recorded as multiple entries.
    new_string
        The literal replacement.
    occurrences
        Count of occurrences expected (for the report). Apply uses this to
        sanity-check the rewrite landed cleanly.
    """

    file_path: Path
    old_string: str
    new_string: str
    occurrences: int = 1


@dataclass
class Rename:
    """One filesystem rename (source → target).

    The plan emits renames in dependency order: a rename of ``A/B`` happens
    before a rename of ``A/B/C`` (so the inner path is correct after the
    outer rename). The apply step trusts the order.
    """

    source: Path
    target: Path


@dataclass
class BriefMergeOp:
    """One ``documents:`` entry to add or update in the project BRIEF.

    The apply step collects every ``BriefMergeOp`` across the plan, builds
    the final ``documents:`` list, and writes the project BRIEF in a
    single atomic step at the end.

    Attributes
    ----------
    slug
        The slug for this document.
    artifact_type
        Registered artifact type per ``project_brief.REGISTERED_ARTIFACT_TYPES``.
        Defaults to ``"investment-memo"`` (the most common shape) — operator
        can edit the BRIEF after migration if the type is wrong.
    target_length
        Optional ``[min_words, max_words]`` carried from a `.anvil.json`.
    target_length_overrides
        Optional per-version override map carried from a `.anvil.json`.
    rubric_overrides
        Optional rubric overrides block carried from a `.anvil.json`.
    """

    slug: str
    artifact_type: str = "investment-memo"
    target_length: Optional[Tuple[int, int]] = None
    target_length_overrides: Optional[Dict[str, Tuple[int, int]]] = None
    rubric_overrides: Optional[dict] = None


@dataclass
class DocumentPlan:
    """Per-document migration plan.

    Atomic unit of the apply step. If applying this plan fails, the apply
    step rolls back THIS plan only.
    """

    slug: str
    source_dir: Path
    target_dir: Path
    renames: List[Rename] = field(default_factory=list)
    content_rewrites: List[ContentRewrite] = field(default_factory=list)
    brief_merge: Optional[BriefMergeOp] = None
    anvil_json_to_delete: Optional[Path] = None
    notes: List[str] = field(default_factory=list)

    @property
    def is_noop(self) -> bool:
        """Return True when this plan is a no-op (the doc is already migrated)."""
        return (
            not self.renames
            and not self.content_rewrites
            and self.brief_merge is None
            and self.anvil_json_to_delete is None
        )


@dataclass
class Plan:
    """Top-level project migration plan.

    The plan composes per-document plans, the project-BRIEF write op, and
    a list of ``.anvil.json`` paths to delete after the per-doc applies.
    """

    project_dir: Path
    shape: Shape
    documents: List[DocumentPlan] = field(default_factory=list)
    project_brief_path: Path = field(init=False)
    # Slugs that appear in the existing project BRIEF but have no on-disk
    # thread (the planner leaves them in place; operator decides).
    preexisting_brief_slugs: List[str] = field(default_factory=list)
    extra_anvil_jsons_to_delete: List[Path] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.project_brief_path = self.project_dir / BRIEF_FILENAME

    @property
    def is_noop(self) -> bool:
        """Return True when the entire plan is a no-op (fully migrated already)."""
        return all(doc.is_noop for doc in self.documents) and (
            not self.extra_anvil_jsons_to_delete
        )


def _read_anvil_json(path: Path) -> dict:
    """Read a ``.anvil.json`` file; return an empty dict on any failure.

    Lenient: a malformed `.anvil.json` is recorded as a note rather than
    blocking the migration. The operator can fix the BRIEF after the fact.
    """
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, json.JSONDecodeError):
        return {}


def _extract_target_length(
    anvil_data: dict,
) -> Tuple[Optional[Tuple[int, int]], Optional[Dict[str, Tuple[int, int]]]]:
    """Pull target_length from a `.anvil.json` shape.

    Handles both flat (`target_length: {words: [...]}`) and extended
    (`target_length: {default: {...}, overrides: {...}}`) forms. Returns a
    pair of (flat-range, overrides-map) where either may be ``None``.
    """
    tl = anvil_data.get("target_length")
    if not isinstance(tl, dict):
        return None, None

    flat: Optional[Tuple[int, int]] = None
    overrides: Optional[Dict[str, Tuple[int, int]]] = None

    # Flat form: {"words": [min, max]} or {"pages": [min, max]}.
    if "words" in tl:
        rng = tl["words"]
        if isinstance(rng, list) and len(rng) == 2:
            try:
                flat = (int(rng[0]), int(rng[1]))
            except (TypeError, ValueError):
                pass
    elif "pages" in tl:
        rng = tl["pages"]
        if isinstance(rng, list) and len(rng) == 2:
            try:
                # Convert pages → words (600 wpp per SKILL.md convention).
                flat = (int(rng[0]) * 600, int(rng[1]) * 600)
            except (TypeError, ValueError):
                pass

    # Extended form: {"default": {...}, "overrides": {...}}.
    if "default" in tl and isinstance(tl["default"], dict):
        if "words" in tl["default"]:
            rng = tl["default"]["words"]
            if isinstance(rng, list) and len(rng) == 2:
                try:
                    flat = (int(rng[0]), int(rng[1]))
                except (TypeError, ValueError):
                    pass

    if "overrides" in tl and isinstance(tl["overrides"], dict):
        ov: Dict[str, Tuple[int, int]] = {}
        for key, val in tl["overrides"].items():
            # Normalize ``v1`` / ``v2`` / ``1`` / ``"1"`` to bare integer-string.
            if isinstance(key, str) and key.startswith("v"):
                norm_key = key[1:]
            else:
                norm_key = str(key)
            if not norm_key.isdigit():
                continue
            if isinstance(val, dict) and "words" in val:
                rng = val["words"]
                if isinstance(rng, list) and len(rng) == 2:
                    try:
                        ov[norm_key] = (int(rng[0]), int(rng[1]))
                    except (TypeError, ValueError):
                        pass
            elif isinstance(val, list) and len(val) == 2:
                try:
                    ov[norm_key] = (int(val[0]), int(val[1]))
                except (TypeError, ValueError):
                    pass
        if ov:
            overrides = ov

    return flat, overrides


def _extract_rubric_overrides(anvil_data: dict) -> Optional[dict]:
    """Pull ``rubric_overrides`` from a `.anvil.json` payload.

    Returns the dict verbatim — the BRIEF parser handles validation
    downstream. ``None`` when the key is absent or not a dict.
    """
    ro = anvil_data.get("rubric_overrides")
    if isinstance(ro, dict) and ro:
        return ro
    return None


def _find_cross_thread_refs(
    body_path: Path,
    stems_to_rewrite: Dict[str, str],
) -> List[Tuple[str, str, int]]:
    """Find cross-thread refs in ``body_path`` to rewrite.

    ``stems_to_rewrite`` maps OLD stem → NEW stem. Returns a list of
    ``(old_token, new_token, count)`` tuples for each distinct token found.

    Example: with ``stems_to_rewrite={"memo": "investment-memo"}``, a body
    containing ``"see memo.7 §3"`` returns ``[("memo.7", "investment-memo.7", 1)]``.
    """
    if not body_path.is_file():
        return []
    try:
        text = body_path.read_text(encoding="utf-8")
    except OSError:
        return []
    if not stems_to_rewrite:
        return []
    pattern = _cross_thread_ref_re(list(stems_to_rewrite.keys()))
    counts: Dict[str, Tuple[str, int]] = {}
    for match in pattern.finditer(text):
        old_stem = match.group(1)
        version_n = match.group(2)
        new_stem = stems_to_rewrite[old_stem]
        old_token = f"{old_stem}.{version_n}"
        new_token = f"{new_stem}.{version_n}"
        if old_token == new_token:
            continue
        prior = counts.get(old_token)
        if prior is None:
            counts[old_token] = (new_token, 1)
        else:
            counts[old_token] = (prior[0], prior[1] + 1)
    return [(old, new, count) for old, (new, count) in counts.items()]


def _plan_fully_migrated_doc(
    thread: ThreadInventory,
) -> DocumentPlan:
    """Return a no-op DocumentPlan for an already-migrated thread."""
    return DocumentPlan(
        slug=thread.slug,
        source_dir=thread.parent_dir,
        target_dir=thread.parent_dir,
        notes=[f"{thread.slug}: already migrated; no-op"],
    )


def _plan_post_283_doc(
    inv: ProjectInventory,
    thread: ThreadInventory,
    stems_to_rewrite: Dict[str, str],
) -> DocumentPlan:
    """Build a plan for a thread under POST_283_ANVIL_JSON shape.

    The thread already lives at ``<project>/<slug>/<slug>.N/`` — the
    parent dir is correct. What may need fixing:

    - Body filename is ``memo.md`` → rename to ``<slug>.md``.
    - A ``.anvil.json`` exists → merge into project BRIEF, delete file.
    - Cross-thread refs use old stems → rewrite.
    """
    plan = DocumentPlan(
        slug=thread.slug,
        source_dir=thread.parent_dir,
        target_dir=thread.parent_dir,
    )

    target_body = f"{thread.slug}.md"
    body_renames_planned: List[Path] = []
    for version_dir in thread.version_dirs:
        for body_filename in _SKILL_FIXED_BODY_FILENAMES:
            if body_filename == target_body:
                continue
            src = version_dir / body_filename
            if src.is_file():
                target = version_dir / target_body
                plan.renames.append(Rename(source=src, target=target))
                body_renames_planned.append(target)
                plan.notes.append(
                    f"Rename body: {src.relative_to(inv.project_dir)} → "
                    f"{target.relative_to(inv.project_dir)}"
                )

    # Cross-thread refs in the renamed bodies (and existing <slug>.md bodies).
    for version_dir in thread.version_dirs:
        candidates: List[Path] = []
        # Already-correct body filename — scan in place.
        existing = version_dir / target_body
        if existing.is_file():
            candidates.append(existing)
        # Bodies we're about to rename in — read from source, but the rewrite
        # is recorded against the target path (the apply step renames first).
        for body_filename in _SKILL_FIXED_BODY_FILENAMES:
            if body_filename == target_body:
                continue
            src = version_dir / body_filename
            if src.is_file():
                # Read content from source; record target path for rewrite.
                target = version_dir / target_body
                refs = _find_cross_thread_refs(src, stems_to_rewrite)
                for old, new, count in refs:
                    plan.content_rewrites.append(
                        ContentRewrite(
                            file_path=target,
                            old_string=old,
                            new_string=new,
                            occurrences=count,
                        )
                    )
                continue
        for body in candidates:
            refs = _find_cross_thread_refs(body, stems_to_rewrite)
            for old, new, count in refs:
                plan.content_rewrites.append(
                    ContentRewrite(
                        file_path=body,
                        old_string=old,
                        new_string=new,
                        occurrences=count,
                    )
                )

    # Anvil JSON → BRIEF merge.
    if thread.anvil_json_path is not None:
        data = _read_anvil_json(thread.anvil_json_path)
        target_length, overrides = _extract_target_length(data)
        rubric_overrides = _extract_rubric_overrides(data)
        plan.brief_merge = BriefMergeOp(
            slug=thread.slug,
            target_length=target_length,
            target_length_overrides=overrides,
            rubric_overrides=rubric_overrides,
        )
        plan.anvil_json_to_delete = thread.anvil_json_path
        plan.notes.append(
            f"Merge {thread.anvil_json_path.relative_to(inv.project_dir)} into BRIEF; "
            f"delete after merge."
        )
    else:
        # No .anvil.json — still emit a BriefMergeOp so the BRIEF entry exists
        # if the project BRIEF currently lacks it. The actual merge step
        # checks the existing entry to avoid clobbering operator-set fields.
        plan.brief_merge = BriefMergeOp(slug=thread.slug)

    return plan


def _plan_pre_283_doc(
    inv: ProjectInventory,
    thread: ThreadInventory,
    stems_to_rewrite: Dict[str, str],
) -> DocumentPlan:
    """Build a plan for a thread under PRE_283_CLASSIC shape.

    The thread's version dirs are directly under the project root (no
    ``<slug>/`` parent). Steps:

    1. Create the ``<slug>/`` parent (implicit — happens during rename).
    2. Rename each ``<stem>.N/`` → ``<slug>/<slug>.N/``.
    3. Rename body files inside (``memo.md`` → ``<slug>.md``).
    4. Cross-thread refs use old stems → rewrite.
    5. ``.anvil.json`` at project root (if it claims this thread) → merge
       into BRIEF.
    """
    plan = DocumentPlan(
        slug=thread.slug,
        source_dir=thread.parent_dir,
        target_dir=inv.project_dir / thread.slug,
    )

    target_body = f"{thread.slug}.md"

    # Plan renames for each version dir. The stem may differ from the
    # slug (the canary case is stem="memo", slug=<project-name>); we use
    # the version dir's actual N from its name.
    version_re = re.compile(r"^(?P<stem>.+)\.(?P<num>\d+)$")
    for version_dir in thread.version_dirs:
        m = version_re.match(version_dir.name)
        if m is None:
            continue
        n = m.group("num")
        # Target: <project>/<slug>/<slug>.N/
        target_version_dir = plan.target_dir / f"{thread.slug}.{n}"
        plan.renames.append(
            Rename(source=version_dir, target=target_version_dir)
        )
        plan.notes.append(
            f"Rename version dir: "
            f"{version_dir.relative_to(inv.project_dir)} → "
            f"{target_version_dir.relative_to(inv.project_dir)}"
        )

        # Inside each renamed version dir, rename the body file.
        for body_filename in _SKILL_FIXED_BODY_FILENAMES:
            if body_filename == target_body:
                continue
            src_body = version_dir / body_filename
            if src_body.is_file():
                # Target paths are AFTER the version-dir rename.
                target_body_path = target_version_dir / target_body
                src_body_at_target = target_version_dir / body_filename
                plan.renames.append(
                    Rename(
                        source=src_body_at_target,
                        target=target_body_path,
                    )
                )
                plan.notes.append(
                    f"Rename body: "
                    f"{src_body.relative_to(inv.project_dir)} → "
                    f"{target_body_path.relative_to(inv.project_dir)}"
                )
                # Cross-thread refs scanned from current source path; the
                # rewrite is recorded against the FINAL target body path.
                refs = _find_cross_thread_refs(src_body, stems_to_rewrite)
                for old, new, count in refs:
                    plan.content_rewrites.append(
                        ContentRewrite(
                            file_path=target_body_path,
                            old_string=old,
                            new_string=new,
                            occurrences=count,
                        )
                    )
        # Also consider critic sibling dirs (<stem>.N.review/, etc.) for
        # rename. We rename them so the discovery walk continues to work.
        for sibling in _iter_critic_siblings(version_dir):
            sibling_name = sibling.name
            # Replace the <stem>.N prefix with <slug>.N.
            prefix = f"{m.group('stem')}.{n}"
            if sibling_name.startswith(f"{prefix}."):
                new_name = f"{thread.slug}.{n}." + sibling_name[len(prefix) + 1:]
                target_sibling = plan.target_dir / new_name
                plan.renames.append(
                    Rename(source=sibling, target=target_sibling)
                )
                plan.notes.append(
                    f"Rename critic sibling: "
                    f"{sibling.relative_to(inv.project_dir)} → "
                    f"{target_sibling.relative_to(inv.project_dir)}"
                )

    # Anvil JSON merge. For pre-#283 the .anvil.json typically lives at
    # the project root (one per project); claim it for this thread when
    # no other thread has.
    root_anvil = inv.project_dir / ANVIL_JSON_FILENAME
    if root_anvil.is_file() and root_anvil in inv.extra_anvil_jsons:
        data = _read_anvil_json(root_anvil)
        target_length, overrides = _extract_target_length(data)
        rubric_overrides = _extract_rubric_overrides(data)
        plan.brief_merge = BriefMergeOp(
            slug=thread.slug,
            target_length=target_length,
            target_length_overrides=overrides,
            rubric_overrides=rubric_overrides,
        )
        plan.anvil_json_to_delete = root_anvil
        plan.notes.append(
            f"Merge {root_anvil.relative_to(inv.project_dir)} into BRIEF; "
            f"delete after merge."
        )
    else:
        plan.brief_merge = BriefMergeOp(slug=thread.slug)

    return plan


def _iter_critic_siblings(version_dir: Path) -> List[Path]:
    """Return list of critic sibling dirs for ``version_dir``.

    A critic sibling has the shape ``<stem>.<N>.<critic>/`` where the
    ``<stem>.<N>`` prefix matches the version dir's basename.
    """
    parent = version_dir.parent
    out: List[Path] = []
    if not parent.is_dir():
        return out
    prefix = version_dir.name + "."
    try:
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            if child.name == version_dir.name:
                continue
            if child.name.startswith(prefix):
                out.append(child)
    except OSError:
        return out
    return out


def build_plan(
    project_dir: Path,
    shape: Optional[Shape] = None,
    inventory: Optional[ProjectInventory] = None,
) -> Plan:
    """Build a :class:`Plan` for ``project_dir``.

    Parameters
    ----------
    project_dir
        Project root.
    shape
        Pre-computed shape; computed via :func:`detect_shape` when omitted.
    inventory
        Pre-computed inventory; computed via :func:`inventory_project`
        when omitted.

    Returns
    -------
    A :class:`Plan` carrying per-document plans. When the project is
    :data:`Shape.FULLY_MIGRATED`, the plan's ``documents`` list contains
    a no-op entry per thread (the apply step then becomes zero-diff).
    """
    project_dir = Path(project_dir).resolve()
    if inventory is None:
        inventory = inventory_project(project_dir)
    if shape is None:
        from .detect import _classify
        shape = _classify(inventory)

    plan = Plan(project_dir=project_dir, shape=shape)

    # Build the stem rewrite map. Used for cross-thread reference rewriting.
    stems_to_rewrite: Dict[str, str] = {}
    for thread in inventory.threads:
        version_re = re.compile(r"^(?P<stem>.+)\.(?P<num>\d+)$")
        for version_dir in thread.version_dirs:
            m = version_re.match(version_dir.name)
            if m is None:
                continue
            stem = m.group("stem")
            if stem != thread.slug:
                stems_to_rewrite[stem] = thread.slug

    # Record existing BRIEF slugs so the planner doesn't drop them on a
    # partial migration.
    if inventory.has_project_brief:
        from .detect import _project_brief_slugs
        plan.preexisting_brief_slugs = _project_brief_slugs(project_dir)

    if shape == Shape.FULLY_MIGRATED:
        for thread in inventory.threads:
            plan.documents.append(_plan_fully_migrated_doc(thread))
        return plan

    if shape == Shape.POST_283_ANVIL_JSON:
        for thread in inventory.threads:
            plan.documents.append(
                _plan_post_283_doc(inventory, thread, stems_to_rewrite)
            )
        # Also delete any extra .anvil.json files.
        plan.extra_anvil_jsons_to_delete.extend(inventory.extra_anvil_jsons)
        return plan

    if shape == Shape.PRE_283_CLASSIC:
        for thread in inventory.threads:
            plan.documents.append(
                _plan_pre_283_doc(inventory, thread, stems_to_rewrite)
            )
        # Pre-#283 had a project-root .anvil.json which gets claimed by
        # the per-doc plan above (the first thread's plan); any remaining
        # extras still get cleaned up here.
        already_claimed = {
            doc.anvil_json_to_delete for doc in plan.documents
            if doc.anvil_json_to_delete is not None
        }
        for extra in inventory.extra_anvil_jsons:
            if extra not in already_claimed:
                plan.extra_anvil_jsons_to_delete.append(extra)
        return plan

    # Shape.UNKNOWN — return an empty plan; caller dispatches the error.
    return plan


__all__ = [
    "BriefMergeOp",
    "ContentRewrite",
    "DocumentPlan",
    "Plan",
    "Rename",
    "build_plan",
]
