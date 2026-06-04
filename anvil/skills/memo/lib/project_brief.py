"""Typed parser for the project-level ``BRIEF.md`` (issue #285).

Sub-deliverable 2 of #283 — the **typed schema reader** that the upcoming
rubric overlay selector (#286) and cross-thread reference validator (#287)
build on. Sub-deliverable 1 of #283 (the dual-layout *discovery* primitive,
#284 / PR #290) ships at
``anvil/skills/memo/lib/project_discovery.py``. Discovery answers "where is
the thread root and which layout matches?"; this module answers "given a
confirmed project root, what does the BRIEF say?".

Background — why this exists
----------------------------
The Studio canary surfaced a **project-as-thread-root** layout where a
single project-level ``BRIEF.md`` lives at the project root and
enumerates per-document metadata in its YAML frontmatter::

    <project>/
      BRIEF.md                 ← single project brief with documents: list
      .anvil.json              ← project-level defaults (sub-deliverable 3)
      <slug-a>/
        <slug-a>.1/ ...
      <slug-b>/
        <slug-b>.1/ ...
      research/                ← shared evidence pool (already shipped, #281)

The project BRIEF frontmatter shape (per #283's refinement comment)::

    ---
    project: brains-for-robots
    audience:
      - Sphere internal leadership (primary)
      - VC investors (secondary)
    hard_rules:
      - Avoid speculative claims without an evidence anchor.
      - Cite every number; cite every claim with a defensible mechanism.
    documents:
      - slug: investment-memo
        artifact_type: investment-memo
        target_length: { words: [8000, 11000] }
      - slug: latency-wall
        artifact_type: position-paper
        target_length: { words: [5000, 8000] }
      ...
    ---

    # Free-prose project shared context

This module reads that shape and surfaces it as a typed
:class:`ProjectBrief` with a per-document :class:`BriefDocument` list.

Public API
----------
``ArtifactType``
    Closed-ended enum of registered artifact types. Unknown values raise
    a validation error listing the registered set. Seed values per the
    curator's confirmation: ``investment-memo``, ``position-paper``,
    ``tactical-plan``, ``vision-document``, ``descriptive-thesis``.

``BriefDocument``
    Pydantic model for one entry in the ``documents:`` list. Carries
    ``slug``, ``artifact_type``, and an optional ``target_length`` range.

``ProjectBrief``
    Pydantic model for the parsed BRIEF. Carries ``project``, ``audience``,
    ``hard_rules``, and ``documents``.

``load_project_brief(project_dir: Path) -> Optional[ProjectBrief]``
    Lenient loader. Returns ``None`` when ``<project_dir>/BRIEF.md`` does
    not exist, has no YAML frontmatter, or its frontmatter is malformed.
    Raises ``ValueError`` for schema violations (the BRIEF is present but
    structurally wrong — a typo in ``artifact_type``, a duplicate slug,
    etc.). The "absence → None" / "presence-with-errors → raise" split
    matches the closed PR #282 ``load_body_filename`` /
    ``load_body_filename_strict`` shape.

``load_project_brief_strict(project_dir: Path) -> ProjectBrief``
    Strict loader. Raises ``FileNotFoundError`` when the BRIEF is missing,
    ``ValueError`` when frontmatter is missing or malformed, and propagates
    the same schema-violation ``ValueError`` as the lenient form.

Slug-directory divergence (Open Question #1 resolution)
-------------------------------------------------------
Both loaders accept an optional ``validate_dirs: bool = False`` flag. When
``True``, after parsing the BRIEF the loader walks ``<project_dir>`` for
slug-shaped subdirectories and applies the curator-confirmed asymmetric
rule:

- **Listed-but-missing** (BRIEF entry has no matching ``<project>/<slug>/``
  directory) → **warn but proceed**. A draft hasn't been started yet —
  common case. Surfaced via ``warnings.warn(UserWarning)``; the returned
  ``ProjectBrief`` is unchanged.
- **On-disk-but-unlisted** (``<project>/<slug>/`` exists with version
  dirs but no ``documents:`` entry names it) → **hard error**.
  Configuration drift — load-bearing. The reviewer can't pick a rubric
  overlay for a slug the BRIEF doesn't acknowledge. Raised as
  ``ValueError`` with the offending slug names.

When ``validate_dirs=False`` (default) the divergence check is skipped
entirely. Lifecycle commands that already know which slug they're
operating on (e.g., the reviewer with a thread root in hand) can opt into
the check; pure parser consumers don't need to.

``.anvil.json`` interaction (Open Question #2 resolution)
---------------------------------------------------------
**Deferred to sub-deliverable 3 (#286).** This module is parser-only: it
does not read ``<project>/.anvil.json`` and does not resolve the
project-level config ↔ per-doc BRIEF entry precedence chain. The overlay
selector in #286 owns that wiring.

Artifact-type enum (Open Question #5 resolution)
------------------------------------------------
**Closed-ended.** Unknown ``artifact_type`` values raise a clear
``ValueError`` listing the registered set. This prevents typos silently
degrading to no-overlay behavior. Adding a new artifact type requires a
code change here (and a matching overlay landing in the file the overlay
selector will read in #286). The seed values are
:data:`REGISTERED_ARTIFACT_TYPES`.

No new Python deps
------------------
YAML frontmatter parsing uses ``yaml.safe_load`` (``pyyaml`` is a declared
base dep — fix #268). Validation uses ``pydantic`` (declared base dep). No
new dependencies are introduced.

Skill-local first
-----------------
Lives under ``anvil/skills/memo/lib/`` per the CLAUDE.md "skill-local
first, lib promotion later" pattern. Promotion to ``anvil/lib/`` is queued
for the second-consumer trigger (likely ``anvil:proposal`` if it adopts
the project-BRIEF shape, or ``anvil:pub``).

Relationship to ``project_discovery.py``
----------------------------------------
The discovery primitive (#284) hands back a ``DiscoveryResult`` whose
``project_root`` field is the directory this module's loaders take as
input. The shared on-disk constants — ``BRIEF_FILENAME`` and
``DOCUMENTS_FRONTMATTER_KEY`` — are re-imported from
``project_discovery`` so a rename there propagates here automatically.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import warnings

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Re-use the on-disk constants from the discovery primitive so the
# layout contract has a single source of truth. ``BRIEF_FILENAME`` is
# the on-disk filename; ``DOCUMENTS_FRONTMATTER_KEY`` is the YAML key
# that gates the project-brief layout.
from project_discovery import (
    BRIEF_FILENAME,
    DOCUMENTS_FRONTMATTER_KEY,
)


# The seed list of registered artifact types per the curator's
# confirmation comment on #283. Unknown values are rejected with a
# clear error listing this set — closed-ended enum governance per
# Open Question #5. Adding a new artifact type requires:
#   1. Adding the literal here.
#   2. Landing a matching overlay file (sub-deliverable 3 / #286).
#   3. Documenting the new shape in `anvil/skills/memo/SKILL.md`.
REGISTERED_ARTIFACT_TYPES: Tuple[str, ...] = (
    "investment-memo",
    "position-paper",
    "tactical-plan",
    "vision-document",
    "descriptive-thesis",
)


class ArtifactType(str, Enum):
    """Closed-ended enum of registered artifact types.

    Inheriting from ``str`` lets a ``BriefDocument.artifact_type`` value
    serialize round-trip through JSON / YAML without a custom encoder.
    Unknown values raise ``ValueError`` at parse time — see the
    ``_validate_artifact_type`` helper for the diagnostic shape.

    Members
    -------
    INVESTMENT_MEMO
        The default memo shape. Calibrated for ranked-recommendation
        invest / pass / conditional decisions with a check size.
    POSITION_PAPER
        Argumentative case for a specific viewpoint (e.g., the canary's
        "latency wall" thesis).
    TACTICAL_PLAN
        Execution plan with prioritized actions and ownership.
    VISION_DOCUMENT
        Long-horizon technical or strategic vision.
    DESCRIPTIVE_THESIS
        Descriptive case for a team / market / shape (e.g., the canary's
        "team thesis").
    """

    INVESTMENT_MEMO = "investment-memo"
    POSITION_PAPER = "position-paper"
    TACTICAL_PLAN = "tactical-plan"
    VISION_DOCUMENT = "vision-document"
    DESCRIPTIVE_THESIS = "descriptive-thesis"


# Frontmatter delimiter — three hyphens on their own line, per the
# standard YAML frontmatter convention (Jekyll / Hugo / pandoc / Marp).
# Mirrors the literal used inside ``project_discovery._extract_frontmatter``
# so the two parsers accept exactly the same on-disk shape.
_FRONTMATTER_DELIM = "---"

# Words-per-page conversion factor. Mirrors the 600 wpm proxy
# documented in ``anvil/skills/memo/SKILL.md`` §"Length targets" and
# matches the constant in ``anvil_config.py``. Kept local rather than
# imported so this parser has zero coupling to the rubric_overrides
# code path.
_WORDS_PER_PAGE = 600


# ---------------------------------------------------------------------------
# Typed models
# ---------------------------------------------------------------------------


class TargetLengthRange(BaseModel):
    """Word-count range from a BRIEF document entry's ``target_length`` block.

    Mirrors the shape used by ``anvil_config.TargetLengthRange`` for the
    rubric_overrides surface so a future converger (when sub-deliverable
    3 wires per-doc length targets through the same resolver) can treat
    the two as interchangeable. The two types remain distinct because:

    1. This module is independent of ``anvil_config.py``: depending on
       it would create a dependency-direction issue (project_brief is
       upstream of the overlay selector in #286).
    2. The validation surface (this is YAML, the other is JSON) needs
       its own clean failure messages.

    Both bounds are inclusive integers; ``min_words <= max_words`` is
    enforced. A ``pages`` input is converted at
    :data:`_WORDS_PER_PAGE` (600 wpp) per the SKILL.md convention.

    Attributes
    ----------
    min_words
        Minimum word count (inclusive).
    max_words
        Maximum word count (inclusive). Must be ``>= min_words``.
    source_key
        ``"words"`` or ``"pages"`` — which top-level key the on-disk
        range used. Captured for the audit trail so a reader can see
        whether the BRIEF author wrote in words or in pages.
    """

    model_config = ConfigDict(extra="forbid")

    min_words: int = Field(..., ge=0)
    max_words: int = Field(..., ge=0)
    source_key: str = Field(...)


class BriefDocument(BaseModel):
    """One entry in the project BRIEF's ``documents:`` frontmatter list.

    Attributes
    ----------
    slug
        Document slug. Names the sibling directory under the project
        root (``<project>/<slug>/``) that holds the document's version
        dirs. Required, non-empty, must contain only filesystem-safe
        characters (alphanumerics, hyphens, underscores) — the on-disk
        directory naming convention.
    artifact_type
        Registered artifact type. Drives rubric overlay selection in
        sub-deliverable 3 (#286). Validated against
        :data:`REGISTERED_ARTIFACT_TYPES` — unknown values raise a clear
        error listing the registered set.
    target_length
        Optional word-count range for this document. When set, sub-
        deliverable 3's overlay resolver uses it as the document-level
        length target. When absent, the resolver falls back to the
        rubric overlay's default range.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., min_length=1)
    artifact_type: ArtifactType = Field(...)
    target_length: Optional[TargetLengthRange] = Field(default=None)


class ProjectBrief(BaseModel):
    """The parsed project-level ``BRIEF.md`` frontmatter.

    Attributes
    ----------
    project
        Project name. Required, non-empty. Surfaced for human reference
        (printed in reports, headers, audit logs); not used as a
        filesystem key.
    audience
        Free-string descriptors of the project audience. The BRIEF
        author lists them in priority order (primary first); the
        loader does NOT enforce any ordering convention.
    hard_rules
        Cross-document discipline rules that apply to every document in
        the project. Free strings; the reviewer treats each as a
        critical-check candidate per existing memo-review §"hard rules"
        machinery. Allowed to be empty.
    documents
        Per-document entries. Must be non-empty (a BRIEF with an empty
        documents list does NOT trigger project-brief layout per
        ``project_discovery.has_project_brief`` — this loader only
        accepts BRIEFs that already pass the discovery gate). Slugs are
        guaranteed unique by the parser.
    """

    model_config = ConfigDict(extra="forbid")

    project: str = Field(..., min_length=1)
    audience: List[str] = Field(default_factory=list)
    hard_rules: List[str] = Field(default_factory=list)
    documents: List[BriefDocument] = Field(..., min_length=1)

    def document_for_slug(self, slug: str) -> Optional[BriefDocument]:
        """Return the ``BriefDocument`` whose ``slug`` matches, or ``None``.

        Convenience accessor for the overlay selector (#286): given a
        thread's slug, look up its BRIEF entry to read the
        ``artifact_type`` and ``target_length`` fields.
        """
        for doc in self.documents:
            if doc.slug == slug:
                return doc
        return None


# ---------------------------------------------------------------------------
# YAML frontmatter extraction
# ---------------------------------------------------------------------------


def _extract_frontmatter(text: str) -> Optional[dict]:
    """Extract the YAML frontmatter from ``text`` and return it as a dict.

    Returns ``None`` when the text has no frontmatter or the frontmatter
    is malformed (not a dict, unparseable YAML, no closing delimiter).
    Mirrors ``project_discovery._extract_frontmatter`` byte-for-byte so
    the two parsers stay in sync on the on-disk delimiter convention.
    """
    lines = text.splitlines()
    # Strip a leading UTF-8 BOM if present on the first line.
    if lines and lines[0].startswith("﻿"):
        lines[0] = lines[0][1:]

    # Find first non-empty line; must be the delimiter.
    first_idx = 0
    while first_idx < len(lines) and lines[first_idx].strip() == "":
        first_idx += 1
    if first_idx >= len(lines):
        return None
    if lines[first_idx].strip() != _FRONTMATTER_DELIM:
        return None

    # Find the closing delimiter starting from the line after the opener.
    body_start = first_idx + 1
    close_idx = None
    for i in range(body_start, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            close_idx = i
            break
    if close_idx is None:
        return None

    yaml_text = "\n".join(lines[body_start:close_idx])
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


# ---------------------------------------------------------------------------
# Field normalizers
# ---------------------------------------------------------------------------


def _normalize_string_list(
    value: Any, field_name: str
) -> List[str]:
    """Normalize a list-of-strings frontmatter value.

    YAML's flow / block syntax both surface as Python lists when present.
    A missing key yields an empty list (the field is allowed to be
    empty per the schema). A non-list value raises ``ValueError`` with
    the field path.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(
            f"BRIEF.{field_name} must be a list of strings; got "
            f"{type(value).__name__} — suggested fix: write the value "
            f"as a YAML list (`- item` lines or `[item, item]`)."
        )
    out: List[str] = []
    for i, entry in enumerate(value):
        if not isinstance(entry, str):
            raise ValueError(
                f"BRIEF.{field_name}[{i}] must be a string; got "
                f"{type(entry).__name__}: {entry!r} — suggested fix: "
                f"quote the entry or remove the non-string value."
            )
        out.append(entry)
    return out


def _normalize_target_length(
    raw: Any, field_path: str
) -> Optional[TargetLengthRange]:
    """Convert a raw ``target_length`` dict to a typed ``TargetLengthRange``.

    Returns ``None`` for an absent value (``None``). Raises ``ValueError``
    for any malformed shape — the project BRIEF parser is STRICT on
    document entries (unlike the rubric_overrides loader which warns and
    drops), because per-doc metadata is load-bearing for overlay
    selection in #286.

    Accepts the flat shape only — ``{"words": [min, max]}`` or
    ``{"pages": [min, max]}``. The extended per-version-override shape
    documented in SKILL.md §"Length targets" is NOT accepted at the
    BRIEF level (BRIEF is project-author-written, not per-version).
    """
    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise ValueError(
            f"BRIEF.{field_path} must be a dict; got "
            f"{type(raw).__name__} — suggested fix: use the shape "
            f'`{{ words: [min, max] }}` or `{{ pages: [min, max] }}`.'
        )

    # Reject extended-shape keys explicitly so a copy-paste from the
    # per-version surface produces a clear error rather than silent
    # acceptance.
    forbidden = {"default", "overrides"} & set(raw.keys())
    if forbidden:
        raise ValueError(
            f"BRIEF.{field_path} does not accept extended-shape keys "
            f"{sorted(forbidden)} — per-doc target_length is flat "
            f'(`{{ words: [min, max] }}` or `{{ pages: [min, max] }}`); '
            f"the extended per-version shape lives in `.anvil.json`."
        )

    has_words = "words" in raw
    has_pages = "pages" in raw
    if has_words and has_pages:
        raise ValueError(
            f"BRIEF.{field_path} has both 'words' and 'pages' — "
            f"ambiguous shape; pick exactly one key."
        )
    if not has_words and not has_pages:
        raise ValueError(
            f"BRIEF.{field_path} has neither 'words' nor 'pages' — "
            f"suggested fix: add `words: [min, max]` or `pages: [min, max]`."
        )

    source_key = "words" if has_words else "pages"
    range_value = raw[source_key]

    if not isinstance(range_value, list) or len(range_value) != 2:
        raise ValueError(
            f"BRIEF.{field_path}.{source_key} must be a 2-element list; "
            f"got {range_value!r} — suggested fix: write "
            f"`[{source_key}_min, {source_key}_max]`."
        )

    lo_raw, hi_raw = range_value
    # bool is a subclass of int; reject explicitly so True/False can't
    # masquerade as 1/0 in a length range.
    if (
        isinstance(lo_raw, bool)
        or isinstance(hi_raw, bool)
        or not isinstance(lo_raw, int)
        or not isinstance(hi_raw, int)
    ):
        raise ValueError(
            f"BRIEF.{field_path}.{source_key} must be [int, int]; got "
            f"{range_value!r} — suggested fix: use integer bounds."
        )

    if lo_raw < 0 or hi_raw < 0:
        raise ValueError(
            f"BRIEF.{field_path}.{source_key} must be non-negative; "
            f"got {range_value!r}."
        )

    if lo_raw > hi_raw:
        raise ValueError(
            f"BRIEF.{field_path}.{source_key} requires min <= max; "
            f"got [{lo_raw}, {hi_raw}]."
        )

    if source_key == "pages":
        min_words = lo_raw * _WORDS_PER_PAGE
        max_words = hi_raw * _WORDS_PER_PAGE
    else:
        min_words = lo_raw
        max_words = hi_raw

    return TargetLengthRange(
        min_words=min_words,
        max_words=max_words,
        source_key=source_key,
    )


def _validate_artifact_type(raw: Any, field_path: str) -> ArtifactType:
    """Convert a raw ``artifact_type`` string to the typed enum.

    Closed-ended per Open Question #5: unknown values raise
    ``ValueError`` listing the registered set so a typo produces a
    self-correcting error.
    """
    if not isinstance(raw, str):
        raise ValueError(
            f"BRIEF.{field_path} must be a string; got "
            f"{type(raw).__name__}: {raw!r} — suggested fix: quote "
            f"the value (one of {list(REGISTERED_ARTIFACT_TYPES)})."
        )
    try:
        return ArtifactType(raw)
    except ValueError:
        registered = list(REGISTERED_ARTIFACT_TYPES)
        raise ValueError(
            f"BRIEF.{field_path}: unknown artifact_type {raw!r}. "
            f"Registered values: {registered}. "
            f"Suggested fix: replace with one of the registered values "
            f"or open an issue to register a new artifact type."
        )


def _normalize_documents(raw: Any) -> List[BriefDocument]:
    """Convert the raw ``documents:`` list into typed ``BriefDocument`` entries.

    Validates:

    - ``documents`` is a non-empty list.
    - Each entry is a dict.
    - Each entry has a non-empty string ``slug``.
    - Each entry has a valid ``artifact_type`` (registered enum value).
    - Optional ``target_length`` parses cleanly.
    - Slugs are unique across the list (duplicate raises).
    - No unknown keys on entries (``extra="forbid"`` on
      :class:`BriefDocument`).
    """
    if raw is None:
        raise ValueError(
            "BRIEF.documents is required and must be a non-empty list. "
            "Suggested fix: add a `documents:` frontmatter key with at "
            "least one entry."
        )
    if not isinstance(raw, list):
        raise ValueError(
            f"BRIEF.documents must be a list; got {type(raw).__name__}. "
            f"Suggested fix: write each document as a list entry under "
            f"`documents:`."
        )
    if len(raw) == 0:
        raise ValueError(
            "BRIEF.documents must be a non-empty list. "
            "Suggested fix: add at least one document entry."
        )

    docs: List[BriefDocument] = []
    seen_slugs: Dict[str, int] = {}

    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(
                f"BRIEF.documents[{i}] must be a mapping; got "
                f"{type(entry).__name__}: {entry!r} — suggested fix: "
                f"write the entry with `slug:` and `artifact_type:` keys."
            )

        # Recognized keys; reject anything else (extra='forbid' on the
        # pydantic model would do this automatically, but doing it here
        # produces a richer error message with the field path.)
        recognized = {"slug", "artifact_type", "target_length"}
        unknown = set(entry.keys()) - recognized
        if unknown:
            raise ValueError(
                f"BRIEF.documents[{i}] has unknown keys "
                f"{sorted(unknown)} — recognized keys: "
                f"{sorted(recognized)}. Suggested fix: remove the "
                f"unknown keys or rename to a recognized key."
            )

        slug_raw = entry.get("slug")
        if not isinstance(slug_raw, str) or not slug_raw.strip():
            raise ValueError(
                f"BRIEF.documents[{i}].slug is required and must be a "
                f"non-empty string; got {slug_raw!r}. Suggested fix: "
                f"add a `slug:` key with the document's directory name."
            )
        slug = slug_raw

        if slug in seen_slugs:
            raise ValueError(
                f"BRIEF.documents[{i}].slug {slug!r} duplicates the slug "
                f"at index {seen_slugs[slug]}. Suggested fix: rename one "
                f"of the duplicates — slugs must be unique within the BRIEF."
            )
        seen_slugs[slug] = i

        artifact_type_raw = entry.get("artifact_type")
        if artifact_type_raw is None:
            raise ValueError(
                f"BRIEF.documents[{i}].artifact_type is required. "
                f"Suggested fix: add an `artifact_type:` key with one of "
                f"{list(REGISTERED_ARTIFACT_TYPES)}."
            )
        artifact_type = _validate_artifact_type(
            artifact_type_raw,
            field_path=f"documents[{i}].artifact_type",
        )

        target_length = _normalize_target_length(
            entry.get("target_length"),
            field_path=f"documents[{i}].target_length",
        )

        try:
            doc = BriefDocument(
                slug=slug,
                artifact_type=artifact_type,
                target_length=target_length,
            )
        except ValidationError as exc:
            # Re-raise as ValueError with the field path for a consistent
            # exception surface. (Pydantic's ValidationError is fine for
            # programmatic consumers, but the parser's contract is "raise
            # ValueError with a clear message".)
            raise ValueError(
                f"BRIEF.documents[{i}]: validation failed — {exc}"
            ) from exc

        docs.append(doc)

    return docs


# ---------------------------------------------------------------------------
# Slug-directory divergence validation (Open Question #1 resolution)
# ---------------------------------------------------------------------------


def _on_disk_slug_dirs(project_dir: Path) -> List[str]:
    """Return the list of on-disk directory names that look like thread roots.

    A "thread-root-shaped" subdirectory of ``project_dir`` is one whose
    name appears as the stem of at least one ``<name>.<N>`` version dir
    immediately under it. This matches
    ``project_discovery._contains_version_dirs`` but inlined to avoid a
    circular-import shape (project_discovery is the caller of this
    parser in the wiring layer).

    Sibling directories that exist but have no version dirs (e.g.,
    ``research/``, an empty placeholder, a stray ``.cache/``) are NOT
    treated as thread roots — they're project-level infrastructure or
    pre-draft scaffolding. This narrows the on-disk-vs-BRIEF check to
    "started threads only".
    """
    import re as _re

    version_re = _re.compile(r"^(?P<stem>.+)\.(?P<num>\d+)$")
    out: List[str] = []
    try:
        children = list(project_dir.iterdir())
    except OSError:
        return out

    for child in children:
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            # `.review/`, `.audit/`, `.<critic>/` siblings are review
            # output, not thread roots. Skip.
            continue
        try:
            grandchildren = list(child.iterdir())
        except OSError:
            continue
        for gc in grandchildren:
            if not gc.is_dir():
                continue
            m = version_re.match(gc.name)
            if m is None:
                continue
            if m.group("stem") == child.name:
                out.append(child.name)
                break
    return out


def _validate_slug_directory_divergence(
    brief: ProjectBrief, project_dir: Path
) -> None:
    """Apply the asymmetric slug-directory rule.

    - **Listed-but-missing** → ``warnings.warn(UserWarning)``. The draft
      hasn't started; this is the common case during early project setup.
    - **On-disk-but-unlisted** → ``ValueError``. Configuration drift
      that breaks overlay selection downstream.
    """
    brief_slugs = {doc.slug for doc in brief.documents}
    on_disk = set(_on_disk_slug_dirs(project_dir))

    # Listed-but-missing: warn but proceed.
    missing = sorted(brief_slugs - on_disk)
    if missing:
        warnings.warn(
            f"BRIEF.documents lists slugs with no matching directory under "
            f"{project_dir}: {missing}. A draft may not have been started "
            f"yet — proceeding. (To silence: remove the unstarted entries "
            f"from BRIEF.documents or create the matching directory.)",
            UserWarning,
            stacklevel=3,
        )

    # On-disk-but-unlisted: hard error.
    extra = sorted(on_disk - brief_slugs)
    if extra:
        raise ValueError(
            f"Configuration drift: directories present under {project_dir} "
            f"are not listed in BRIEF.documents: {extra}. Each thread "
            f"root must be acknowledged by the project BRIEF so the "
            f"reviewer can resolve its artifact_type. Suggested fix: add "
            f"matching `documents:` entries for {extra}, or remove the "
            f"directories if they are stale."
        )


# ---------------------------------------------------------------------------
# Parsing entry points (lenient + strict)
# ---------------------------------------------------------------------------


def _parse_brief_body(
    frontmatter: Dict[str, Any], project_dir: Path
) -> ProjectBrief:
    """Parse a frontmatter dict into a :class:`ProjectBrief`.

    Raises ``ValueError`` on any schema violation. Recognized top-level
    keys: ``project``, ``audience``, ``hard_rules``, ``documents``.
    Other keys are ignored (forward-compat surface for project-level
    fields that may land later — e.g., a ``voice:`` block).
    """
    project_raw = frontmatter.get("project")
    if not isinstance(project_raw, str) or not project_raw.strip():
        raise ValueError(
            f"BRIEF.project is required and must be a non-empty string; "
            f"got {project_raw!r} at {project_dir / BRIEF_FILENAME}. "
            f"Suggested fix: add a `project:` key naming the project."
        )

    audience = _normalize_string_list(
        frontmatter.get("audience"), "audience"
    )
    hard_rules = _normalize_string_list(
        frontmatter.get("hard_rules"), "hard_rules"
    )
    documents = _normalize_documents(
        frontmatter.get(DOCUMENTS_FRONTMATTER_KEY)
    )

    try:
        return ProjectBrief(
            project=project_raw,
            audience=audience,
            hard_rules=hard_rules,
            documents=documents,
        )
    except ValidationError as exc:
        raise ValueError(
            f"BRIEF at {project_dir / BRIEF_FILENAME} failed schema "
            f"validation: {exc}"
        ) from exc


def load_project_brief(
    project_dir: Path,
    *,
    validate_dirs: bool = False,
) -> Optional[ProjectBrief]:
    """Lenient loader for ``<project_dir>/BRIEF.md``.

    Absence-tolerant entry point. Returns ``None`` when:

    - ``<project_dir>/BRIEF.md`` does not exist.
    - The file exists but has no YAML frontmatter.
    - The frontmatter is malformed YAML.

    Raises ``ValueError`` when the BRIEF is present and structurally
    wrong:

    - Missing required field (``project``, ``documents``).
    - Wrong type on any field.
    - Unknown ``artifact_type``.
    - Duplicate slug.
    - Empty ``documents`` list.
    - Malformed ``target_length`` shape.

    Parameters
    ----------
    project_dir
        Directory containing the project BRIEF. Typically the
        ``project_root`` field of a
        :class:`project_discovery.DiscoveryResult` for a
        ``LAYOUT_PROJECT_BRIEF`` match.
    validate_dirs
        When True, after parsing, validate the BRIEF's slug list against
        on-disk slug-shaped subdirectories under ``project_dir``. Listed-
        but-missing triggers a ``UserWarning``; on-disk-but-unlisted
        raises ``ValueError``. Default False — pure schema parsing only.

    Returns
    -------
    Optional[ProjectBrief]
        Parsed BRIEF, or ``None`` if no BRIEF is present.

    Raises
    ------
    ValueError
        On any schema violation. The exception message includes the
        offending field path and a suggested fix.
    """
    brief_path = project_dir / BRIEF_FILENAME
    if not brief_path.is_file():
        return None
    try:
        text = brief_path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm = _extract_frontmatter(text)
    if fm is None:
        return None

    brief = _parse_brief_body(fm, project_dir)

    if validate_dirs:
        _validate_slug_directory_divergence(brief, project_dir)

    return brief


def load_project_brief_strict(
    project_dir: Path,
    *,
    validate_dirs: bool = False,
) -> ProjectBrief:
    """Strict loader for ``<project_dir>/BRIEF.md``.

    Raises on every failure mode the lenient form tolerates:

    - ``FileNotFoundError`` if ``<project_dir>/BRIEF.md`` does not exist.
    - ``ValueError`` if the file has no YAML frontmatter or the
      frontmatter is malformed.
    - ``ValueError`` (same as lenient) on schema violations.

    The strict form is what test fixtures use to assert specific
    failure modes; lifecycle commands should usually use the lenient
    :func:`load_project_brief` and check for ``None``.

    Parameters
    ----------
    project_dir
        Directory containing the project BRIEF.
    validate_dirs
        See :func:`load_project_brief`.

    Returns
    -------
    ProjectBrief
        Parsed BRIEF.

    Raises
    ------
    FileNotFoundError
        If ``<project_dir>/BRIEF.md`` is missing.
    ValueError
        On absent frontmatter, malformed YAML, or any schema violation.
    """
    brief_path = project_dir / BRIEF_FILENAME
    if not brief_path.is_file():
        raise FileNotFoundError(
            f"No BRIEF found at {brief_path}. Suggested fix: create a "
            f"`{BRIEF_FILENAME}` file at the project root with the "
            f"`project:`, `audience:`, `hard_rules:`, and `documents:` "
            f"frontmatter keys."
        )
    text = brief_path.read_text(encoding="utf-8")
    fm = _extract_frontmatter(text)
    if fm is None:
        raise ValueError(
            f"BRIEF at {brief_path} has no parseable YAML frontmatter. "
            f"Suggested fix: ensure the file opens with `---` on the "
            f"first non-blank line and closes the frontmatter with a "
            f"matching `---` line."
        )

    brief = _parse_brief_body(fm, project_dir)

    if validate_dirs:
        _validate_slug_directory_divergence(brief, project_dir)

    return brief


__all__ = [
    "ArtifactType",
    "BriefDocument",
    "ProjectBrief",
    "REGISTERED_ARTIFACT_TYPES",
    "TargetLengthRange",
    "load_project_brief",
    "load_project_brief_strict",
]
