"""Typed parser for the project-level ``BRIEF.md`` (issue #285).

Sub-deliverable 2 of #283 — the **typed schema reader** that the rubric
overlay selector (#286) and cross-thread reference validator (#287)
build on. Sub-deliverable 1 of #283 (the project-root *discovery*
primitive, #284 / PR #290) ships at
``anvil/skills/memo/lib/project_discovery.py``. Discovery answers "where
is the thread root and which project owns it?"; this module answers
"given a confirmed project root, what does the BRIEF say?".

Single source of truth (issue #296)
-----------------------------------
Issue #296 (the project-org model lock, part B) **retires** the
sibling ``.anvil.json`` file and consolidates every project / per-doc
anvil-config knob into ``BRIEF.md``'s YAML frontmatter. Specifically,
the BRIEF schema now absorbs:

- Per-doc ``target_length`` (already present; the per-version
  override surface ``target_length_overrides`` is new — see
  :class:`BriefDocument`).
- Per-doc ``rubric_overrides`` (calibration suffix per PR #265 —
  formerly the ``rubric_overrides`` block at the top level of
  ``<thread>/.anvil.json``; see :class:`RubricOverrides`).
- :func:`body_filename_for` — the issue #295 slug-echo helper.

The ``anvil_config`` module is gone. Lifecycle commands, lib modules,
and tests that previously read ``<thread>/.anvil.json`` now read
``<project>/BRIEF.md`` via :func:`load_project_brief` (or the strict
variant) and look up the per-doc entry by slug
(``ProjectBrief.document_for_slug(slug)``). The
``rubric_overrides_suffix.py`` module that wires per-dim calibration
into the reviewer continues to operate against a typed
:class:`RubricOverrides` instance — the only change is that the
instance is now sourced from BRIEF.md rather than ``.anvil.json``.

Background — why this exists
----------------------------
The Studio canary surfaced a **project-as-thread-root** layout where a
single project-level ``BRIEF.md`` lives at the project root and
enumerates per-document metadata in its YAML frontmatter::

    <project>/
      BRIEF.md                 ← single project brief; documents: list +
                                  per-doc target_length, target_length_overrides,
                                  and rubric_overrides
      <slug-a>/
        <slug-a>.1/ ...
      <slug-b>/
        <slug-b>.1/ ...
      research/                ← shared evidence pool (already shipped, #281)

The project BRIEF frontmatter shape::

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
        target_length_overrides:
          "1": [8000, 11000]
          "2": [7500, 10500]
        rubric_overrides:
          memo_subtype: synthesis-brief
          dim_1_calibration: "decision-framework — score on framework clarity"
          dim_5_calibration: "defers to underlying market models"
          target_length: { words: [9000, 13000] }
      - slug: latency-wall
        artifact_type: position-paper
        target_length: { words: [5000, 8000] }
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
    ``slug``, ``artifact_type``, optional ``target_length``, optional
    ``target_length_overrides`` (per-version), and optional
    ``rubric_overrides`` (subtype calibration).

``TargetLengthRange``
    Word-count range. Used for both ``BriefDocument.target_length`` and
    the inner ``RubricOverrides.target_length``.

``TargetLengthOverrides``
    Per-version override map. Keys are version numbers (as strings:
    ``"1"``, ``"2"``, …); values are
    ``[min_words, max_words]`` ranges. Mirrors the historical
    ``.anvil.json`` ``target_length.overrides`` shape but lifted to the
    per-doc surface.

``RubricOverrides``
    Pydantic model holding the parsed per-doc ``rubric_overrides``
    block. Optional fields default to ``None`` so callers can check
    presence with ``is not None`` rather than a sentinel string.

``CalibrationOverride``
    Per-dimension override: holds the dimension number (1-9) and the
    calibration prose. Returned by ``RubricOverrides.calibrations``.

``ProjectBrief``
    Pydantic model for the parsed BRIEF. Carries ``project``,
    ``audience``, ``hard_rules``, and ``documents``.

``load_project_brief(project_dir: Path) -> Optional[ProjectBrief]``
    Lenient loader. Returns ``None`` when ``<project_dir>/BRIEF.md``
    does not exist, has no YAML frontmatter, or its frontmatter is
    malformed. Raises ``ValueError`` for schema violations (the BRIEF
    is present but structurally wrong — a typo in ``artifact_type``,
    a duplicate slug, etc.).

``load_project_brief_strict(project_dir: Path) -> ProjectBrief``
    Strict loader. Raises ``FileNotFoundError`` when the BRIEF is
    missing, ``ValueError`` when frontmatter is missing or malformed,
    and propagates the same schema-violation ``ValueError`` as the
    lenient form.

``load_rubric_overrides_for_slug(project_dir: Path, slug: str) ->``
``RubricOverrides``
    Convenience wrapper: read the BRIEF, look up the document by
    ``slug``, and return its ``rubric_overrides`` block (or an empty
    :class:`RubricOverrides` when absent / malformed). This is the
    replacement for the retired
    ``anvil_config.load_rubric_overrides(thread_dir)`` API. The
    contract — empty instance on every absence path, never raise —
    mirrors the prior lenient form exactly.

``body_filename_for(slug: str) -> str``
    Return the body markdown filename for a thread (``f"{slug}.md"``).
    Issue #295's slug-echo convention; the only recognized shape. Lives
    here because it's a one-line helper and ``project_brief.py`` is the
    project-config schema-of-record after the #296 consolidation.

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

Artifact-type enum (Open Question #5 resolution)
------------------------------------------------
**Closed-ended.** Unknown ``artifact_type`` values raise a clear
``ValueError`` listing the registered set. This prevents typos silently
degrading to no-overlay behavior. Adding a new artifact type requires a
code change here (and a matching overlay landing in the file the overlay
selector reads in #286). The seed values are
:data:`REGISTERED_ARTIFACT_TYPES`.

Validation discipline — BRIEF-side is STRICT
--------------------------------------------
The BRIEF parser is intentionally STRICT on schema violations (raises
``ValueError`` with field path + suggested fix). Per-doc metadata is
load-bearing for overlay selection in #286, so a malformed entry must
fail loudly rather than degrading silently. This is the opposite of the
prior ``anvil_config.py`` ``rubric_overrides`` loader, which was
**lenient** (warned + dropped fields) because ``.anvil.json`` was
optional config and the lenient form preserved zero-impact backwards
compat for threads without overrides.

The consolidation under #296 keeps both contracts intact by routing them
to two different entry points:

- :func:`load_project_brief` (and strict variant): full BRIEF parser,
  STRICT on every field.
- :func:`load_rubric_overrides_for_slug`: convenience wrapper, returns
  an empty :class:`RubricOverrides` on every absence path (missing
  BRIEF, missing document, missing ``rubric_overrides`` block).
  Mirrors the prior lenient ``anvil_config.load_rubric_overrides``
  surface exactly.

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

import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

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
# documented in ``anvil/skills/memo/SKILL.md`` §"Length targets".
_WORDS_PER_PAGE = 600

# Memo rubric dimension range. The memo rubric ships 9 dimensions per
# ``anvil/skills/memo/rubric.md``; the ``dim_N_calibration`` key range
# is the closed interval [1, 9]. Other skills' rubrics may differ; if
# this loader is ever promoted to anvil/lib/ the range must be
# parameterized.
MIN_DIM = 1
MAX_DIM = 9

# `dim_N_calibration` is a templated key; the regex below pins the shape.
_DIM_CALIBRATION_RE = re.compile(r"^dim_(\d+)_calibration$")

# Recognized top-level keys inside a ``rubric_overrides:`` block.
# Anything else is preserved verbatim under ``unknown_keys`` (forward-
# compat surface — a future-shipped ``memo_subtype`` enum or a
# "Concision Discipline" knob can land in BRIEF.md ahead of loader
# support without breaking existing consumers).
_KNOWN_RUBRIC_OVERRIDE_KEYS = {"memo_subtype", "target_length"}

# Recognized keys on a ``BriefDocument`` entry. Anything else is a
# schema violation (BRIEF-side is STRICT).
_RECOGNIZED_DOCUMENT_KEYS = {
    "slug",
    "artifact_type",
    "target_length",
    "target_length_overrides",
    "rubric_overrides",
    "render_engine",
    "latex_header_includes",
    "max_iterations",
    "iteration_cap_rationale",
}

# Default iteration cap. The override floor mirrors the deck skill's
# precedent in ``anvil/skills/deck/SKILL.md`` §"Per-thread override
# contract": the cap is a discipline tool, an override may **raise** the
# cap but never **lower** it below the principled default. Set the
# floor in one place so deck and memo agree.
DEFAULT_MAX_ITERATIONS = 4

# Valid values for the ``render_engine`` per-doc knob (issue #320). The
# trio mirrors :data:`anvil.lib.render_gate.MEMO_ENGINE_*` and the
# ``_select_memo_engine`` priority order. The BRIEF parser enforces this
# closed set at parse time; the render-gate's ``_select_memo_engine``
# does the runtime fallthrough when the requested engine is not on PATH.
# Per the parallel issue #322 (theme system) and the scope split agreed
# at curation, **per-document `render_engine` wins**; the per-theme
# default is layered underneath by #322.
_VALID_RENDER_ENGINES = ("weasyprint", "xelatex", "wkhtmltopdf")


# ---------------------------------------------------------------------------
# Typed models
# ---------------------------------------------------------------------------


class TargetLengthRange(BaseModel):
    """Word-count range from a BRIEF document entry's ``target_length`` block.

    Used in two places:

    1. ``BriefDocument.target_length`` — the per-doc default range.
    2. ``RubricOverrides.target_length`` — the subtype-calibration
       override of the per-doc default.

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


class TargetLengthOverrides(BaseModel):
    """Per-version target-length override map for a BRIEF document entry.

    Maps version number (as a string: ``"1"``, ``"2"``, …) to a
    :class:`TargetLengthRange`. The historical ``.anvil.json`` shape was
    ``target_length.overrides.v1`` / ``v2`` / …; the BRIEF-side shape is
    a bare-integer-string key per entry because YAML mappings carry no
    natural ``v`` prefix. Authors who want to be explicit can quote the
    key (``"1"``) — the YAML parser collapses ``1`` and ``"1"`` to the
    same string anyway.

    Example::

        target_length_overrides:
          "1": [8000, 11000]
          "2": [7500, 10500]
          "3": [7000, 10000]

    The same per-version resolution order documented in SKILL.md
    §"Length targets" applies:

    1. If ``target_length_overrides["<N>"]`` is set, use that range.
    2. Else if ``target_length`` is set, use that.
    3. Else, no target — fall back to the implicit judgment.

    The resolver lives in the drafter / reviser code path; this module
    only surfaces the typed dict.

    Attributes
    ----------
    overrides
        Map from version-number string (e.g., ``"1"``) to a
        :class:`TargetLengthRange`. May be empty.
    """

    model_config = ConfigDict(extra="forbid")

    overrides: Dict[str, TargetLengthRange] = Field(default_factory=dict)

    def for_version(self, version: int) -> Optional[TargetLengthRange]:
        """Return the override for ``version`` or ``None``.

        Convenience accessor for the drafter / reviser resolution
        helper. The key on disk is a string (``"1"``, ``"2"``, …) so
        the lookup converts ``version`` to its string form.
        """
        return self.overrides.get(str(version))


class CalibrationOverride(BaseModel):
    """One per-dimension calibration override.

    Returned by ``RubricOverrides.calibrations`` as a list, sorted by
    dimension number. The reviewer iterates this list and appends
    ``"calibration applied: <text>"`` to each affected dimension's
    justification.

    The ``dimension`` field uses the integer 1-9 namespace from the memo
    rubric, NOT a string id — the rubric markdown uses ordinal-prefixed
    dimension labels ("1 Recommendation clarity", ...) but the on-disk
    override key is ``dim_1_calibration`` etc. and a numeric field is the
    most direct mapping.
    """

    model_config = ConfigDict(extra="forbid")

    dimension: int = Field(
        ...,
        ge=MIN_DIM,
        le=MAX_DIM,
        description=(
            "Memo rubric dimension number (1-9 per "
            "``anvil/skills/memo/rubric.md``). The on-disk key is "
            "``dim_<dimension>_calibration``."
        ),
    )
    text: str = Field(
        ...,
        min_length=1,
        description=(
            "Calibration prose to append to the dimension's reviewer "
            "justification. Verbatim text — no rewording, no truncation. "
            "The author's exact wording is the load-bearing audit trail."
        ),
    )


class RubricOverrides(BaseModel):
    """Parsed ``rubric_overrides`` block from a BRIEF document entry.

    All fields are optional. An "empty" instance (every field ``None``)
    is the canonical no-overrides state and is returned by
    :func:`load_rubric_overrides_for_slug` for slugs whose BRIEF entry
    has no ``rubric_overrides`` block (or for projects with no BRIEF
    at all).

    Callers check presence with ``is not None`` on individual fields, or
    use the ``is_empty`` property as a fast-path "did the consumer declare
    any overrides at all" check.
    """

    model_config = ConfigDict(extra="forbid")

    memo_subtype: Optional[str] = Field(
        None,
        description=(
            "Free-string label naming the memo shape. Opaque to the loader; "
            "intended for human reference and audit-trail. Two studio-canary "
            "shapes: ``synthesis-brief`` and ``feedback-memo``."
        ),
    )
    calibrations: List[CalibrationOverride] = Field(
        default_factory=list,
        description=(
            "Per-dimension calibration overrides, sorted by dimension. "
            "Each entry corresponds to a ``dim_<N>_calibration`` key on disk."
        ),
    )
    target_length: Optional[TargetLengthRange] = Field(
        None,
        description=(
            "Optional override of the document's top-level ``target_length``. "
            "When set, the drafter / reviser's resolution helper uses this "
            "value rather than the document's top-level one. Same flat-shape "
            "semantics as the document-level field; per-version overrides "
            "remain at ``target_length_overrides`` (the per-doc surface)."
        ),
    )
    unknown_keys: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Forward-compat passthrough: any keys in ``rubric_overrides`` "
            "that the loader does not recognize land here verbatim. The "
            "BRIEF-side parser raises on unknown keys for the document "
            "entry itself, but ``rubric_overrides`` retains the lenient "
            "forward-compat surface — same as the prior ``.anvil.json`` "
            "shape did — so a future shipped ``memo_subtype`` enum or a "
            "Concision-Discipline knob can land in BRIEF.md ahead of "
            "loader support."
        ),
    )

    @property
    def is_empty(self) -> bool:
        """Return True when no overrides are declared.

        Useful as a fast-path in the reviewer: a doc with ``is_empty`` true
        should produce identical output to a doc with no ``rubric_overrides``
        block at all.
        """
        return (
            self.memo_subtype is None
            and not self.calibrations
            and self.target_length is None
            and not self.unknown_keys
        )

    def calibration_for(self, dimension: int) -> Optional[str]:
        """Return the calibration text for ``dimension`` or ``None``.

        Convenience accessor for the reviewer: ``override.calibration_for(1)``
        returns the calibration prose for memo rubric dim 1, or ``None`` if
        no override is set for that dim.
        """
        for entry in self.calibrations:
            if entry.dimension == dimension:
                return entry.text
        return None


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
        Optional word-count range for this document. When set, the
        drafter / reviser's resolution helper uses it as the document-
        level length target. When absent, the resolver falls back to
        the rubric overlay's default range.
    target_length_overrides
        Optional per-version overrides on top of ``target_length``. Each
        key is a version-number string (e.g., ``"1"``); each value is a
        ``[min, max]`` range. Mirrors the historical
        ``.anvil.json target_length.overrides`` shape (issue #296
        consolidation moved it here).
    rubric_overrides
        Optional :class:`RubricOverrides` block — subtype calibration
        per PR #265 (issue #233). Mirrors the historical
        ``.anvil.json rubric_overrides`` shape (issue #296
        consolidation moved it here).
    render_engine
        Optional per-document override for the memo HTML/PDF engine
        used by ``anvil/lib/render_gate.py``. One of
        ``"weasyprint"``, ``"xelatex"``, or ``"wkhtmltopdf"`` (issue
        #320). When set, ``_select_memo_engine`` honors this request
        if the named binary is on PATH; otherwise it gracefully
        falls through to the existing
        ``weasyprint > wkhtmltopdf > xelatex`` auto-priority. The
        theme-level default knob shipped by parallel issue #322 sits
        *below* this per-doc value in precedence (per-thread >
        per-project > per-theme > framework default).
    latex_header_includes
        Optional per-document preamble extension threaded into pandoc's
        ``header-includes`` slot when the dispatched engine is
        ``xelatex`` (issue #347). Free-form LaTeX text. Used to load
        consumer-specific packages (e.g., ``xcolor``, ``tabularx``) or
        define named colors / custom environments referenced by
        ``{=latex}`` raw blocks in the memo body, *without* requiring
        the operator to maintain a full ``template.tex`` override.

        Engine-scoped by name: pandoc's ``header-includes`` metadata is
        also honored by the HTML chain (``template.html`` has the same
        ``$for(header-includes)$`` slot), so a generic
        ``header_includes`` could surprise an operator who flips
        ``render_engine`` between ``xelatex`` and ``weasyprint``. The
        explicit ``latex_`` prefix makes it visible that the contents
        are xelatex-only — when the dispatched engine is *not*
        xelatex, ``_render_memo_source`` silently skips the include
        and records the skip in the gate's ``reasons`` audit trail.

        The contents are opaque to the parser: any string survives the
        validator. Empty / whitespace-only values are normalized to
        ``None`` so a YAML author can write ``latex_header_includes:``
        with nothing on the right-hand side and get back-compat
        behavior.

        Example (a table-dense memo using ``{=latex}`` blocks)::

            latex_header_includes: |
              \\usepackage{xcolor}
              \\definecolor{green}{HTML}{059669}
              \\definecolor{ink}{HTML}{0f172a}
              \\usepackage{tabularx}
              \\newcolumntype{Y}{>{\\raggedright\\arraybackslash}X}
    max_iterations
        Optional paired-override of the default iteration cap
        (:data:`DEFAULT_MAX_ITERATIONS` = 4) for the review/revise loop
        on this thread (issue #349). When set, the override **may raise
        but not lower** the principled default — values below
        :data:`DEFAULT_MAX_ITERATIONS` are treated as malformed and
        rejected at parse time.

        The override is **paired** with :attr:`iteration_cap_rationale`:
        both keys must be present and well-formed for the override to
        take effect. Setting :attr:`max_iterations` without a non-empty
        :attr:`iteration_cap_rationale` (or vice-versa) is a schema
        violation — the BRIEF parser raises ``ValueError`` with the
        offending field path so the operator can correct the BRIEF
        before any drafter / reviser pass picks up an unjustified
        override.

        The paired-override design mirrors the deck skill's
        ``<thread>/.anvil.json`` contract documented at
        ``anvil/skills/deck/SKILL.md`` §"Per-thread override contract".
        The deck override lives in ``.anvil.json`` (the per-thread
        carrier predating the #296 consolidation); the memo override
        lives here in the project BRIEF (the post-#296 single-source-
        of-truth carrier).

        Semantics are **sticky raise**, NOT single-use: setting
        ``max_iterations: 5`` raises the cap to 5 until the BRIEF is
        edited again. The required rationale — not single-use semantics
        — is what prevents abuse.

        Drafter and reviser commands mirror the resolved value into
        per-version ``_progress.json.metadata.max_iterations`` and
        ``_progress.json.metadata.iteration_cap_rationale`` so each
        version dir carries an audit trail of the cap in effect when it
        was produced. The reviser's BLOCKED notice (see
        ``commands/memo-revise.md`` §"BLOCKED notice") surfaces the
        rationale verbatim when the elevated cap is hit, so the operator
        sees the prior authorization at the moment they need it.
    iteration_cap_rationale
        Required-when-:attr:`max_iterations`-is-set free-prose
        justification for the elevated cap (issue #349). When set,
        documents *why* this thread deserves more revision passes than
        the principled default. The rationale text is what makes the
        override principled and is preserved in BRIEF git history as the
        audit trail.

        Whitespace-only values are normalized to ``None`` at parse time
        — a YAML author can write ``iteration_cap_rationale:`` with
        nothing on the right-hand side, but that field will not
        activate an override (the parser will raise because the paired
        :attr:`max_iterations` is then set without a valid rationale).

        Example (a memo thread surfacing the cap-bound near-miss
        documented in issue #349)::

            documents:
              - slug: aldus
                artifact_type: investment-memo
                max_iterations: 5
                iteration_cap_rationale: |
                  Operator-extended to 5 on 2026-06-08. Reason: v4 verdict
                  34/44 vs floor 35, gap is design-side (slide 7 figsize +
                  slide 4 preamble drop), reviewer identified memo-revise
                  can close it; founder follow-ups for source-side lift
                  (Dims 3/5/6) are tracked separately at issue X.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., min_length=1)
    artifact_type: ArtifactType = Field(...)
    target_length: Optional[TargetLengthRange] = Field(default=None)
    target_length_overrides: Optional[TargetLengthOverrides] = Field(default=None)
    rubric_overrides: Optional[RubricOverrides] = Field(default=None)
    render_engine: Optional[
        Literal["weasyprint", "xelatex", "wkhtmltopdf"]
    ] = Field(default=None)
    latex_header_includes: Optional[str] = Field(default=None)
    max_iterations: Optional[int] = Field(default=None)
    iteration_cap_rationale: Optional[str] = Field(default=None)


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
    theme
        Optional brand-theme name (issue #322). When set, the per-skill
        asset resolvers (template + stylesheet + accent) consult
        ``<consumer>/.anvil/themes/<theme>/`` as a precedence tier
        between the consumer single-tenant override and the framework
        default. Free string — theme names are consumer-defined; no
        enum validation is enforced. A name pointing to a missing theme
        directory is tolerated (the resolver falls through to the next
        tier silently).
    """

    model_config = ConfigDict(extra="forbid")

    project: str = Field(..., min_length=1)
    audience: List[str] = Field(default_factory=list)
    hard_rules: List[str] = Field(default_factory=list)
    documents: List[BriefDocument] = Field(..., min_length=1)
    theme: Optional[str] = Field(default=None)

    def document_for_slug(self, slug: str) -> Optional[BriefDocument]:
        """Return the ``BriefDocument`` whose ``slug`` matches, or ``None``.

        Convenience accessor for the overlay selector (#286) and the
        rubric-overrides reader: given a thread's slug, look up its
        BRIEF entry to read the ``artifact_type``, ``target_length``,
        ``target_length_overrides``, and ``rubric_overrides`` fields.
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


def _normalize_theme(value: Any) -> Optional[str]:
    """Normalize the optional ``theme:`` frontmatter key (issue #322).

    Returns ``None`` when the key is absent, an explicit ``null``, or an
    empty / whitespace-only string. A non-empty string is returned with
    surrounding whitespace stripped. Any other type raises
    ``ValueError`` — the field is strictly a string when present, to
    catch fat-finger errors (``theme: [foo]``, ``theme: 42``).
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(
            f"BRIEF.theme must be a string when set; got "
            f"{type(value).__name__}: {value!r} — suggested fix: "
            f"quote the theme name (`theme: my-brand`) or remove the "
            f"key to fall through to framework defaults."
        )
    stripped = value.strip()
    if not stripped:
        return None
    return stripped


def _normalize_target_length_range(
    raw: Any, field_path: str
) -> TargetLengthRange:
    """Convert a raw ``{words: [...]}`` / ``{pages: [...]}`` to a typed range.

    Raises ``ValueError`` for any malformed shape — the BRIEF parser is
    STRICT (unlike the prior rubric_overrides loader, which warned).

    Accepts the **flat shape** only — ``{"words": [min, max]}`` or
    ``{"pages": [min, max]}``. Extended-shape keys (``default``,
    ``overrides``) are rejected explicitly — the per-version surface
    has moved to ``target_length_overrides`` per the #296
    consolidation.
    """
    if not isinstance(raw, dict):
        raise ValueError(
            f"BRIEF.{field_path} must be a dict; got "
            f"{type(raw).__name__} — suggested fix: use the shape "
            f'`{{ words: [min, max] }}` or `{{ pages: [min, max] }}`.'
        )

    # Reject extended-shape keys explicitly so a copy-paste from the
    # historical .anvil.json shape produces a clear error rather than
    # silent acceptance.
    forbidden = {"default", "overrides"} & set(raw.keys())
    if forbidden:
        raise ValueError(
            f"BRIEF.{field_path} does not accept extended-shape keys "
            f"{sorted(forbidden)} — per-doc target_length is flat "
            f'(`{{ words: [min, max] }}` or `{{ pages: [min, max] }}`); '
            f"per-version overrides live in `target_length_overrides:` "
            f"on the document entry."
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


def _normalize_target_length_overrides(
    raw: Any, field_path: str
) -> Optional[TargetLengthOverrides]:
    """Convert a raw ``target_length_overrides`` dict to a typed model.

    Accepts a dict whose keys are version-number strings (``"1"``,
    ``"2"``, …) and values are ``[min, max]``-style range dicts. Empty
    dict → returns a :class:`TargetLengthOverrides` with empty
    ``overrides``. Absent (``None``) → returns ``None``.

    Raises ``ValueError`` for malformed shape (non-dict, non-integer-
    string key, malformed range).
    """
    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise ValueError(
            f"BRIEF.{field_path} must be a dict; got "
            f"{type(raw).__name__} — suggested fix: write each version "
            f"override on its own line under `target_length_overrides:`."
        )

    overrides: Dict[str, TargetLengthRange] = {}
    for key, value in raw.items():
        # YAML mappings can have int keys; normalize to string and
        # validate the integer-string shape.
        if isinstance(key, bool):
            raise ValueError(
                f"BRIEF.{field_path} key {key!r} is a boolean; version "
                f"keys must be positive integers (e.g., `\"1\"`)."
            )
        if isinstance(key, int):
            key_str = str(key)
        elif isinstance(key, str):
            key_str = key
        else:
            raise ValueError(
                f"BRIEF.{field_path} key must be a string or integer; "
                f"got {type(key).__name__}: {key!r}."
            )
        if not key_str.isdigit() or int(key_str) < 1:
            raise ValueError(
                f"BRIEF.{field_path} key {key_str!r} must be a positive "
                f"integer string (the version number); suggested fix: "
                f'write the key as `"1"`, `"2"`, etc.'
            )
        range_typed = _normalize_target_length_range(
            value, field_path=f"{field_path}[{key_str!r}]"
        )
        overrides[key_str] = range_typed

    return TargetLengthOverrides(overrides=overrides)


def _parse_dim_calibration_key(key: str) -> Optional[int]:
    """Return the dimension number from a ``dim_<N>_calibration`` key, or ``None``."""
    m = _DIM_CALIBRATION_RE.match(key)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _normalize_rubric_overrides(
    raw: Any, field_path: str
) -> Optional[RubricOverrides]:
    """Convert a raw ``rubric_overrides`` dict to a typed model.

    BRIEF-side schema is STRICT on shape errors at the dict level
    (non-dict raises) but tolerant on field-level oddities per the
    forward-compat contract: unknown keys are preserved verbatim under
    ``RubricOverrides.unknown_keys``; the parser warns via
    ``warnings.warn`` but does NOT raise. This is the load-bearing
    backwards-compat surface from the prior ``.anvil.json`` lenient
    loader: a future shipped ``concision_discipline`` knob lands in
    BRIEF.md ahead of loader support without breaking existing
    consumers.

    Per-field validation is STRICT however: a malformed
    ``memo_subtype`` (non-string, empty), a ``dim_N_calibration`` with
    a non-string value, an out-of-range dim number, or a malformed
    ``target_length`` raises ``ValueError`` with the field path. The
    BRIEF-side reader is the schema-of-record now — silent drops would
    confuse the operator.

    Returns ``None`` for an absent value (raw is None). Returns an
    empty :class:`RubricOverrides` for a non-dict or empty dict (with
    appropriate diagnostic when non-dict).
    """
    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise ValueError(
            f"BRIEF.{field_path} must be a dict; got "
            f"{type(raw).__name__} — suggested fix: write the overrides "
            f"as a nested mapping under `rubric_overrides:`."
        )

    memo_subtype: Optional[str] = None
    calibrations: List[CalibrationOverride] = []
    target_length: Optional[TargetLengthRange] = None
    unknown_keys: Dict[str, Any] = {}

    seen_dims: set[int] = set()

    for key, value in raw.items():
        if key == "memo_subtype":
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"BRIEF.{field_path}.memo_subtype must be a non-empty "
                    f"string; got {value!r}."
                )
            memo_subtype = value
            continue

        if key == "target_length":
            target_length = _normalize_target_length_range(
                value, field_path=f"{field_path}.target_length"
            )
            continue

        dim = _parse_dim_calibration_key(key)
        if dim is not None:
            if dim < MIN_DIM or dim > MAX_DIM:
                raise ValueError(
                    f"BRIEF.{field_path}.{key}: dimension {dim} out of "
                    f"range [{MIN_DIM}, {MAX_DIM}]."
                )
            if dim in seen_dims:
                raise ValueError(
                    f"BRIEF.{field_path}.{key}: dimension {dim} "
                    f"declared more than once (canonical form is "
                    f"`dim_{dim}_calibration`)."
                )
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"BRIEF.{field_path}.{key} must be a non-empty "
                    f"string; got {value!r}."
                )
            seen_dims.add(dim)
            calibrations.append(CalibrationOverride(dimension=dim, text=value))
            continue

        # Unknown key — preserve verbatim with a warning so a future
        # shipped key (e.g. concision_discipline) can land in BRIEF.md
        # ahead of loader support without breaking existing consumers.
        unknown_keys[key] = value
        warnings.warn(
            f"BRIEF.{field_path}.{key}: unknown key — preserved verbatim "
            f"under unknown_keys (forward-compat); reviewer will not "
            f"apply it",
            UserWarning,
            stacklevel=4,
        )

    # Sort calibrations by dimension for deterministic iteration order.
    calibrations.sort(key=lambda c: c.dimension)

    return RubricOverrides(
        memo_subtype=memo_subtype,
        calibrations=calibrations,
        target_length=target_length,
        unknown_keys=unknown_keys,
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


def _validate_render_engine(raw: Any, field_path: str) -> Optional[str]:
    """Validate a raw ``render_engine`` value against the closed allowlist.

    Closed-ended per issue #320: unknown values raise ``ValueError`` listing
    the valid trio so a typo produces a self-correcting error. ``None`` is
    valid and short-circuits — the field is optional. The actual runtime
    fallthrough (requested-but-unavailable-on-PATH) is handled in
    :func:`anvil.lib.render_gate._select_memo_engine`, not here — this
    validator only gates parse-time correctness.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(
            f"BRIEF.{field_path} must be a string; got "
            f"{type(raw).__name__}: {raw!r} — suggested fix: quote "
            f"the value (one of {list(_VALID_RENDER_ENGINES)})."
        )
    if raw not in _VALID_RENDER_ENGINES:
        raise ValueError(
            f"BRIEF.{field_path}: unknown render_engine {raw!r}. "
            f"Valid values: {list(_VALID_RENDER_ENGINES)}. "
            f"Suggested fix: replace with one of the valid values "
            f"or omit the key to use the default auto-priority "
            f"(weasyprint > wkhtmltopdf > xelatex)."
        )
    return raw


def _validate_latex_header_includes(raw: Any, field_path: str) -> Optional[str]:
    """Validate a raw ``latex_header_includes`` value (issue #347).

    The contents are opaque LaTeX — the validator only enforces type
    (``str`` or ``None``) and normalizes empty / whitespace-only inputs
    to ``None`` so the BRIEF author can write
    ``latex_header_includes:`` with an empty value and get back-compat
    behavior. Non-string types raise ``ValueError`` with a clear
    field-path message.

    Engine-scoping (xelatex-only) is *not* enforced at parse time — a
    BRIEF may set ``latex_header_includes`` alongside
    ``render_engine: weasyprint`` and the value will be carried
    through. The downstream render path
    (:func:`anvil.lib.render_gate._render_memo_source`) silently skips
    the include when the dispatched engine is not xelatex and records
    the skip in the gate's ``reasons`` audit trail. Parse-time
    enforcement would lock out the legitimate "I render with xelatex
    locally but the field falls through to weasyprint on CI" flow.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(
            f"BRIEF.{field_path} must be a string; got "
            f"{type(raw).__name__}: {raw!r} — suggested fix: write the "
            f"value as a YAML block-literal (``|``) or quoted string of "
            f"LaTeX preamble text."
        )
    if not raw.strip():
        return None
    return raw


def _normalize_iteration_cap_rationale(raw: Any, field_path: str) -> Optional[str]:
    """Normalize a raw ``iteration_cap_rationale`` value (issue #349).

    The rationale is **required when set** — operator must supply a
    non-empty, non-whitespace string to activate the paired override.
    Empty / whitespace-only values normalize to ``None`` so a YAML
    author can write ``iteration_cap_rationale:`` with nothing on the
    right-hand side and get back-compat behavior (the paired field
    :attr:`BriefDocument.max_iterations` will then trigger the paired-
    override validator's "missing rationale" rejection).

    Non-string types raise ``ValueError`` with a clear field-path
    message. The contents themselves are opaque to the parser — any
    non-empty string survives the validator.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(
            f"BRIEF.{field_path} must be a string; got "
            f"{type(raw).__name__}: {raw!r} — suggested fix: write the "
            f"value as a quoted string or YAML block-literal (``|``) "
            f"naming why this thread deserves more revision passes."
        )
    if not raw.strip():
        return None
    return raw


def _validate_max_iterations(raw: Any, field_path: str) -> Optional[int]:
    """Validate a raw ``max_iterations`` value (issue #349).

    The override is sticky-raise: an integer ``>=``
    :data:`DEFAULT_MAX_ITERATIONS` is honored; values below the
    principled default are rejected at parse time. Non-integer types
    are rejected too (booleans masquerading as ``0``/``1`` would
    silently degrade the override to a no-op). ``None`` is valid and
    short-circuits — the field is optional.

    The paired-override contract — that ``max_iterations`` requires a
    non-empty :attr:`BriefDocument.iteration_cap_rationale` — is enforced
    in :func:`_validate_paired_iteration_cap_override` at the document-
    entry level rather than here so the cross-field error message can
    name both fields explicitly.
    """
    if raw is None:
        return None
    # bool is a subclass of int — reject explicitly so True/False can't
    # masquerade as 1/0 in a cap value.
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(
            f"BRIEF.{field_path} must be an integer >= "
            f"{DEFAULT_MAX_ITERATIONS}; got {type(raw).__name__}: "
            f"{raw!r} — suggested fix: write the value as an integer "
            f"(e.g., `max_iterations: 5`)."
        )
    if raw < DEFAULT_MAX_ITERATIONS:
        raise ValueError(
            f"BRIEF.{field_path}: max_iterations ({raw}) must be >= "
            f"{DEFAULT_MAX_ITERATIONS}. The override may raise the cap "
            f"but not lower it below the principled default. Suggested "
            f"fix: set `max_iterations: {DEFAULT_MAX_ITERATIONS}` "
            f"(or higher) or remove the key to fall through to the "
            f"default."
        )
    return raw


def _validate_paired_iteration_cap_override(
    max_iterations: Optional[int],
    iteration_cap_rationale: Optional[str],
    field_path: str,
) -> None:
    """Enforce the paired-override contract for the iteration-cap override.

    The override is **paired**: both ``max_iterations`` and
    ``iteration_cap_rationale`` must be present and well-formed for the
    override to take effect, OR both must be absent. Setting one without
    the other is a schema violation that raises with a field-path
    message naming both keys.

    This is the load-bearing audit-trail contract: an elevated cap
    without a rationale would silently raise the cap without recording
    why. The rationale text — preserved in BRIEF git history — IS the
    audit trail.
    """
    has_cap = max_iterations is not None
    has_rationale = iteration_cap_rationale is not None
    if has_cap and not has_rationale:
        raise ValueError(
            f"BRIEF.{field_path}: max_iterations is set "
            f"({max_iterations}) but iteration_cap_rationale is missing "
            f"or empty. The paired-override contract requires BOTH "
            f"fields to be present and well-formed — the rationale text "
            f"is the audit trail that documents why this thread "
            f"deserves more revision passes. Suggested fix: add a "
            f"non-empty `iteration_cap_rationale:` value explaining why "
            f"the elevated cap is authorized, OR remove the "
            f"`max_iterations:` key to fall through to the default cap "
            f"of {DEFAULT_MAX_ITERATIONS}."
        )
    if has_rationale and not has_cap:
        raise ValueError(
            f"BRIEF.{field_path}: iteration_cap_rationale is set but "
            f"max_iterations is missing. The paired-override contract "
            f"requires BOTH fields to be present and well-formed. "
            f"Suggested fix: add `max_iterations: <N>` (integer "
            f">= {DEFAULT_MAX_ITERATIONS}) naming the elevated cap, OR "
            f"remove the `iteration_cap_rationale:` key."
        )


def _normalize_documents(raw: Any) -> List[BriefDocument]:
    """Convert the raw ``documents:`` list into typed ``BriefDocument`` entries.

    Validates:

    - ``documents`` is a non-empty list.
    - Each entry is a dict.
    - Each entry has a non-empty string ``slug``.
    - Each entry has a valid ``artifact_type`` (registered enum value).
    - Optional ``target_length`` parses cleanly.
    - Optional ``target_length_overrides`` parses cleanly.
    - Optional ``rubric_overrides`` parses cleanly.
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

        unknown = set(entry.keys()) - _RECOGNIZED_DOCUMENT_KEYS
        if unknown:
            raise ValueError(
                f"BRIEF.documents[{i}] has unknown keys "
                f"{sorted(unknown)} — recognized keys: "
                f"{sorted(_RECOGNIZED_DOCUMENT_KEYS)}. Suggested fix: "
                f"remove the unknown keys or rename to a recognized key."
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

        raw_tl = entry.get("target_length")
        target_length = (
            _normalize_target_length_range(
                raw_tl, field_path=f"documents[{i}].target_length"
            )
            if raw_tl is not None
            else None
        )

        target_length_overrides = _normalize_target_length_overrides(
            entry.get("target_length_overrides"),
            field_path=f"documents[{i}].target_length_overrides",
        )

        rubric_overrides = _normalize_rubric_overrides(
            entry.get("rubric_overrides"),
            field_path=f"documents[{i}].rubric_overrides",
        )

        render_engine = _validate_render_engine(
            entry.get("render_engine"),
            field_path=f"documents[{i}].render_engine",
        )

        latex_header_includes = _validate_latex_header_includes(
            entry.get("latex_header_includes"),
            field_path=f"documents[{i}].latex_header_includes",
        )

        max_iterations = _validate_max_iterations(
            entry.get("max_iterations"),
            field_path=f"documents[{i}].max_iterations",
        )

        iteration_cap_rationale = _normalize_iteration_cap_rationale(
            entry.get("iteration_cap_rationale"),
            field_path=f"documents[{i}].iteration_cap_rationale",
        )

        # Paired-override validation runs after the per-field validators
        # so the cross-field error names both keys with already-normalized
        # values (e.g., whitespace-only rationale → None → "missing").
        _validate_paired_iteration_cap_override(
            max_iterations,
            iteration_cap_rationale,
            field_path=f"documents[{i}]",
        )

        try:
            doc = BriefDocument(
                slug=slug,
                artifact_type=artifact_type,
                target_length=target_length,
                target_length_overrides=target_length_overrides,
                rubric_overrides=rubric_overrides,
                render_engine=render_engine,
                latex_header_includes=latex_header_includes,
                max_iterations=max_iterations,
                iteration_cap_rationale=iteration_cap_rationale,
            )
        except ValidationError as exc:
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
    version_re = re.compile(r"^(?P<stem>.+)\.(?P<num>\d+)$")
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
    keys: ``project``, ``audience``, ``hard_rules``, ``documents``,
    ``theme``. Other keys are ignored (forward-compat surface for
    project-level fields that may land later — e.g., a ``voice:``
    block).
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
    theme = _normalize_theme(frontmatter.get("theme"))

    try:
        return ProjectBrief(
            project=project_raw,
            audience=audience,
            hard_rules=hard_rules,
            documents=documents,
            theme=theme,
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
    - Malformed ``target_length`` / ``target_length_overrides`` /
      ``rubric_overrides`` shape.

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


# ---------------------------------------------------------------------------
# Rubric-overrides convenience API (replaces anvil_config.load_rubric_overrides)
# ---------------------------------------------------------------------------


def load_rubric_overrides_for_slug(
    project_dir: Path, slug: str
) -> RubricOverrides:
    """Return the ``rubric_overrides`` for ``slug`` from ``<project_dir>/BRIEF.md``.

    Lenient convenience wrapper. Returns an empty
    :class:`RubricOverrides` for every absence path:

    - ``<project_dir>/BRIEF.md`` does not exist.
    - The BRIEF has no YAML frontmatter or the frontmatter is malformed.
    - The BRIEF parses but has no entry for ``slug``.
    - The matching entry has no ``rubric_overrides:`` block.

    Raises ``ValueError`` only on a structurally invalid BRIEF (the
    same conditions as :func:`load_project_brief`). This is the
    replacement for the retired
    ``anvil_config.load_rubric_overrides(thread_dir)`` API; the
    ``empty-on-absence`` contract is preserved exactly so the reviewer
    integration in ``rubric_overrides_suffix.py`` continues to work
    unchanged.

    Parameters
    ----------
    project_dir
        The project root (the directory containing ``BRIEF.md``). For
        threads under the project layout, this is the parent of the
        thread directory: ``thread_dir.parent``.
    slug
        The document slug (the name of the thread directory under the
        project root).

    Returns
    -------
    RubricOverrides
        Parsed overrides. Use ``RubricOverrides.is_empty`` to fast-path
        the no-overrides case.
    """
    try:
        brief = load_project_brief(project_dir)
    except ValueError:
        # The BRIEF exists but is structurally invalid. The lenient
        # contract says "degrade to empty"; propagating a ValueError
        # here would break the reviewer's pre-#296 zero-impact
        # behavior for legacy threads. So we swallow.
        return RubricOverrides()
    if brief is None:
        return RubricOverrides()

    doc = brief.document_for_slug(slug)
    if doc is None or doc.rubric_overrides is None:
        return RubricOverrides()
    return doc.rubric_overrides


# ---------------------------------------------------------------------------
# Body-filename helper (issue #295)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Thread-level BRIEF.md helpers (issue #348)
# ---------------------------------------------------------------------------
#
# The thread-level ``<thread>/BRIEF.md`` is a SEPARATE on-disk surface from the
# project-level ``<project>/BRIEF.md`` parsed above. The thread-level BRIEF
# is intentionally **freeform prose** with optional YAML frontmatter — it
# documents the drafter's context (company / sector / stage / check_size)
# and the operator's recommendation posture. Recognized informal frontmatter
# keys are documented in ``anvil/skills/memo/commands/memo-draft.md`` step 3:
# ``company``, ``sector``, ``stage``, ``check_size``, and
# ``recommendation_target`` (one of ``invest`` / ``pass`` / ``conditional`` /
# ``undecided``).
#
# These keys are **purely informational passthrough** for most consumers; the
# drafter reads them into context but no structural module parses them.
# Issue #348 promotes the one structurally-load-bearing key —
# ``recommendation_target`` — into a typed signal so the reviewer can
# calibrate dim 1 (Recommendation clarity) appropriately when the operator
# explicitly declared the thread is in pre-decision mode
# (``recommendation_target: undecided``).
#
# The helper is intentionally **lenient** — every absence path returns
# ``None`` so callers can branch on ``is None`` without try/except. The
# contract mirrors :func:`load_rubric_overrides_for_slug` for the
# project-level surface.

# Closed set of recognized ``recommendation_target`` values.
# The closed set is the contract: typos like ``Undecided`` (capitalized),
# ``tbd``, ``?``, ``maybe`` are NOT recognized and resolve to ``None``
# (the reviewer falls back to the legacy dim 1 calibration — same behavior
# as a thread with no BRIEF). This prevents the structured-field surface
# from silently accepting noise.
_RECOGNIZED_RECOMMENDATION_TARGETS = ("invest", "pass", "conditional", "undecided")


def load_recommendation_target(
    thread_dir: Path,
) -> Optional[Literal["invest", "pass", "conditional", "undecided"]]:
    """Read ``recommendation_target`` from a thread-level ``BRIEF.md``.

    Issue #348 promotes the informal-but-documented ``recommendation_target``
    frontmatter key (per ``memo-draft.md`` step 3 and
    ``templates/BRIEF.fresh.md.example``) into a typed signal that the
    reviewer can calibrate dim 1 (Recommendation clarity) against.

    Parameters
    ----------
    thread_dir
        The thread root directory (the directory holding ``BRIEF.md`` for
        the thread, e.g., ``<project>/<slug>/``). NOT a version directory.

    Returns
    -------
    Optional[Literal["invest", "pass", "conditional", "undecided"]]
        The verbatim ``recommendation_target`` value when present and in the
        closed set. ``None`` for every absence / malformed path:

        - ``<thread_dir>/BRIEF.md`` does not exist.
        - The file exists but has no YAML frontmatter (no opening ``---``
          delimiter, missing closing delimiter, malformed YAML).
        - The frontmatter is a parseable dict but contains no
          ``recommendation_target`` key.
        - The frontmatter value is not in the closed set
          (``invest`` / ``pass`` / ``conditional`` / ``undecided``) — e.g.,
          ``Undecided`` (capitalized), ``tbd``, ``maybe``, ``?``, an integer,
          a list, a null. The reviewer falls back to byte-identical
          pre-#348 behavior for these noise values.

    Notes
    -----
    Lenient by design — never raises. The contract mirrors
    :func:`load_rubric_overrides_for_slug`'s "empty / None on every absence
    path" lenient form so the reviewer's zero-impact backwards-compat is
    preserved exactly for any thread that pre-dates this helper or that
    chose not to set the field.

    The thread-level BRIEF is a SEPARATE surface from the project-level
    BRIEF parsed by :func:`load_project_brief`. The two share frontmatter
    extraction primitive (:func:`_extract_frontmatter`) but the schema
    contracts are distinct: project-level BRIEF is STRICT (typo in
    ``artifact_type`` raises); thread-level BRIEF is FREEFORM PROSE with
    informal frontmatter. This helper extracts only the one structured
    field; everything else is passed through to the drafter as
    informational context.
    """
    if not isinstance(thread_dir, Path):
        # Defensive: callers may inadvertently pass a string. The helper is
        # documented to take a Path; convert rather than raise to preserve
        # the lenient contract.
        try:
            thread_dir = Path(thread_dir)
        except Exception:
            return None

    brief_path = thread_dir / BRIEF_FILENAME
    if not brief_path.is_file():
        return None

    try:
        text = brief_path.read_text(encoding="utf-8")
    except OSError:
        return None

    fm = _extract_frontmatter(text)
    if fm is None:
        return None

    value = fm.get("recommendation_target")
    # Closed-set membership check. Anything not on the recognized list —
    # including booleans, ints, lists, dicts, None, and string typos —
    # falls through to None per the lenient contract.
    if isinstance(value, str) and value in _RECOGNIZED_RECOMMENDATION_TARGETS:
        return value  # type: ignore[return-value]
    return None


def body_filename_for(slug: str) -> str:
    """Return the body markdown filename for a memo thread.

    Issue #295 (project-org model lock) pins the body filename
    convention: every version directory's body markdown **echoes the
    thread slug** as ``<slug>.md`` (e.g. ``investment-memo.1/`` carries
    ``investment-memo.md``, ``latency-wall.1/`` carries
    ``latency-wall.md``). This is the only recognized shape; there is
    no override mechanism.

    This helper is the single source of truth so a future shape change
    (vanishingly unlikely under the slug-echo contract) lands in one
    place. Lifecycle commands and lib modules that need to read or
    write the body file should call this helper rather than hard-coding
    ``f"{slug}.md"`` inline.

    Lives in ``project_brief.py`` after the issue #296 consolidation
    (its prior home, ``anvil_config.py``, was retired). The helper is a
    one-line ``f"{slug}.md"`` wrapper; placing it next to the project-
    config schema keeps every project / per-doc convention in one
    place.

    Parameters
    ----------
    slug
        The thread slug (the directory name under the project root that
        holds the thread's version dirs). Non-empty string required.

    Returns
    -------
    str
        ``f"{slug}.md"`` verbatim. Caller is responsible for combining
        with the version dir path (e.g. ``version_dir / body_filename_for(slug)``).
    """
    if not isinstance(slug, str) or not slug:
        raise ValueError(
            f"body_filename_for(slug) requires a non-empty string; "
            f"got {slug!r}"
        )
    return f"{slug}.md"


__all__ = [
    "ArtifactType",
    "BriefDocument",
    "CalibrationOverride",
    "DEFAULT_MAX_ITERATIONS",
    "MAX_DIM",
    "MIN_DIM",
    "ProjectBrief",
    "REGISTERED_ARTIFACT_TYPES",
    "RubricOverrides",
    "TargetLengthOverrides",
    "TargetLengthRange",
    "body_filename_for",
    "load_project_brief",
    "load_project_brief_strict",
    "load_recommendation_target",
    "load_rubric_overrides_for_slug",
]
