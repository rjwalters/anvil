"""Typed loader for ``<thread>/.anvil.json`` ``rubric_overrides`` block + ``body_filename`` key.

This module is the schema-of-record for the *non-investment-memo shape* contract
shipped under issue #233. It is the **sub-issue 1 of 3** deliverable: schema +
reader only. Reviewer integration (sub-issue 2 / #265) and documentation +
worked-example templates (sub-issue 3 / #266) follow in separate PRs.

Issue #279 adds the top-level ``body_filename`` field (sibling to
``rubric_overrides``) so a thread can declare a non-``memo.md`` body filename
(e.g. ``paper.md`` for position papers, ``plan.md`` for execution plans). The
default remains ``memo.md`` for backward compatibility. See
``load_body_filename`` below.

Background — why this exists
----------------------------
``anvil:memo`` ships a single rubric calibrated for investment memos. Two studio
canary threads landed READY at 39/40 via an ad-hoc convention — a section in
``BRIEF.md`` telling the reviewer how to interpret specific dimensions for the
non-standard shape ("Critical reviewer guidance"). The workaround works but is
author-side prose, undocumented, and not part of the anvil contract. Issue #233
codifies the structured form: a ``rubric_overrides`` block in
``<thread>/.anvil.json`` that the reviewer reads directly and applies as
per-dimension calibration commentary.

On-disk shape
-------------
The ``rubric_overrides`` block is **optional**. When absent, the memo skill
behaves exactly as it does today (investment-memo rubric, no calibration
suffixes). When present, it can carry:

- ``memo_subtype`` — free-string label naming the shape
  (e.g. ``"synthesis-brief"``, ``"feedback-memo"``, ``"decision-framework"``).
  Opaque to the loader; intended for human reference and audit-trail.
- ``dim_N_calibration`` — free-string calibration override for memo rubric
  dimension ``N`` (``N`` in 1-9; the memo rubric ships 9 dimensions per
  ``anvil/skills/memo/rubric.md``). The reviewer (sub-issue 2) appends the
  calibration text as a suffix to that dimension's justification so the
  audit trail is transparent.
- ``target_length`` — optional override of the existing top-level
  ``target_length`` field. Same shape as the top-level field (see
  ``anvil/skills/memo/SKILL.md`` §"Length targets"). When set inside
  ``rubric_overrides``, it overrides the top-level value. When absent
  inside ``rubric_overrides``, the top-level value (if any) is unaffected.

Example::

    {
      "max_iterations": 8,
      "rubric_overrides": {
        "memo_subtype": "synthesis-brief",
        "dim_1_calibration": "decision-framework — score on framework clarity + sub-recommendation sharpness, not on single ranked recommendation",
        "dim_5_calibration": "defers to underlying market models — score on integration quality not on fresh sizing",
        "dim_6_calibration": "defers to underlying market models — score on whether financial framing supports positioning",
        "target_length": { "words": [9000, 13000] }
      }
    }

Tolerance and validation
------------------------
The loader follows the precedent set by ``_read_anvil_json`` in
``anvil/lib/rubric.py`` and the ``target_length`` parser in the memo skill:
**parse errors are tolerated, never fatal**. A malformed block degrades to
"no overrides" rather than raising. Specifically:

- A missing ``.anvil.json`` file -> empty overrides.
- A non-dict top-level -> empty overrides.
- A missing or non-dict ``rubric_overrides`` block -> empty overrides.
- A non-string ``memo_subtype`` -> dropped (warning, other fields preserved).
- A non-string ``dim_N_calibration`` value -> dropped (warning, other fields
  preserved).
- A ``dim_N_calibration`` key with ``N`` out of range (not 1-9) or
  non-numeric -> dropped (warning, other fields preserved).
- A malformed ``target_length`` block -> dropped (warning, other fields
  preserved). See ``_normalize_target_length`` for the per-shape rules.
- **Unknown keys** in ``rubric_overrides`` (anything that is not
  ``memo_subtype``, ``dim_N_calibration``, or ``target_length``) are
  preserved verbatim under ``RubricOverrides.unknown_keys`` and surfaced via
  a warning. This is the forward-compat path per AC: a future shipped
  ``memo_subtype`` enum (Option C in #233), a "Concision Discipline" knob, or
  any other key sub-issue 2/3 adds can land in ``.anvil.json`` ahead of
  loader support without breaking existing consumers.

Warnings are emitted via ``warnings.warn`` (category ``UserWarning``) so they
surface in test output and ``-W error`` modes but never block production
reads. Callers that want strict validation can use
``load_rubric_overrides_strict`` instead (raises ``ValueError`` on any
malformed input).

Relationship to existing schema
-------------------------------
- The memo rubric (``anvil/skills/memo/rubric.md``) is **9 dimensions**, not 8.
  The dimension range here (1-9) matches the memo rubric weights exactly.
  Other skills' rubrics may differ; this loader is memo-skill-specific.
- ``target_length`` inside ``rubric_overrides`` shadows the **top-level**
  ``target_length`` in ``.anvil.json``. The resolution helper in the memo
  commands (sub-issue 2) is responsible for the precedence wiring; this
  loader only surfaces both values.
- The existing top-level ``target_length`` semantics (flat shape + extended
  per-version shape, ``words``/``pages`` ranges, 600 words/page conversion)
  are documented in ``anvil/skills/memo/SKILL.md`` §"Length targets". The
  shape inside ``rubric_overrides.target_length`` mirrors the flat shape
  only — per-version overrides remain at the top level. This is a deliberate
  scope decision: ``rubric_overrides`` is the *subtype calibration* surface,
  not the per-version surface.

Public API
----------
``RubricOverrides``
    Pydantic model holding the parsed overrides. Optional fields default to
    ``None`` so callers can check presence with ``is not None`` rather than
    a sentinel string.
``CalibrationOverride``
    Per-dimension override: holds the dimension number (1-9) and the
    calibration prose. Returned by ``RubricOverrides.calibrations``.
``load_rubric_overrides(thread_dir)``
    Read ``<thread_dir>/.anvil.json`` and return a ``RubricOverrides``.
    Malformed input degrades to empty; warnings emitted via
    ``warnings.warn``.
``load_rubric_overrides_strict(thread_dir)``
    Strict variant that raises ``ValueError`` on any malformed input. Used
    by the test suite to assert specific validation behavior; not consumed
    by lifecycle commands.

This module is intentionally **skill-local** under
``anvil/skills/memo/lib/`` per the CLAUDE.md "skill-local first, lib
promotion later" pattern. Promotion to ``anvil/lib/`` is queued for the
second-consumer trigger (likely ``anvil:report`` or ``anvil:pub`` if they
adopt subtype calibration).
"""

from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


# The memo rubric ships 9 dimensions per anvil/skills/memo/rubric.md. The
# dim_N_calibration key range is the closed interval [1, 9]. Other skills'
# rubrics may differ; if this loader is ever promoted to anvil/lib/ the range
# must be parameterized.
MIN_DIM = 1
MAX_DIM = 9

# Default body filename for memo threads. Backward-compat constant: any thread
# that does not declare `body_filename` in `.anvil.json` (the ~100% common case
# for existing threads) reads and writes `memo.md`. Issue #279 / per-thread
# `body_filename` overrides this for shape-specific naming (e.g. `paper.md`
# for position papers, `plan.md` for execution plans).
DEFAULT_BODY_FILENAME = "memo.md"

# Keys recognized at the top level of `rubric_overrides`. Anything else is
# preserved verbatim under `unknown_keys` with a forward-compat warning.
_KNOWN_KEYS = {"memo_subtype", "target_length"}

# `dim_N_calibration` is a templated key; the regex below pins the shape.
_DIM_CALIBRATION_RE = re.compile(r"^dim_(\d+)_calibration$")


# Single source of truth for the words-per-page conversion. Mirrors the
# 600 wpm proxy documented in SKILL.md §"Length targets". Kept local rather
# than imported so this loader has zero coupling to the existing length-target
# code path; sub-issue 2 (#265) is where the two converge.
_WORDS_PER_PAGE = 600


class CalibrationOverride(BaseModel):
    """One per-dimension calibration override.

    Returned by ``RubricOverrides.calibrations`` as a list, sorted by
    dimension number. The reviewer (sub-issue 2 / #265) iterates this list
    and appends ``"calibration applied: <text>"`` to each affected
    dimension's justification.

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


class TargetLengthRange(BaseModel):
    """One word-count range derived from a ``rubric_overrides.target_length`` block.

    Mirrors the resolved ``(min_words, max_words)`` shape produced by the
    existing memo length-target resolver, but kept as a typed value here so
    callers can distinguish "no target set" (``None``) from "target set to
    [0, 0]" (a valid, if unusual, range).

    Both bounds are inclusive integers; ``min_words <= max_words`` is
    enforced. A ``pages`` input is converted at 600 words/page per the
    SKILL.md §"Length targets" convention.
    """

    model_config = ConfigDict(extra="forbid")

    min_words: int = Field(
        ...,
        ge=0,
        description="Minimum word count (inclusive).",
    )
    max_words: int = Field(
        ...,
        ge=0,
        description="Maximum word count (inclusive). Must be >= min_words.",
    )
    source_key: str = Field(
        ...,
        description=(
            "Which top-level key (``words`` or ``pages``) the on-disk "
            "range used. Captured for the audit trail so a reader can see "
            "whether the author wrote in words or in pages."
        ),
    )


class RubricOverrides(BaseModel):
    """Parsed ``rubric_overrides`` block from ``<thread>/.anvil.json``.

    All fields are optional. An "empty" instance (every field ``None``) is
    the canonical no-overrides state and is returned by
    ``load_rubric_overrides`` for threads with no ``.anvil.json``, no
    ``rubric_overrides`` block, or a malformed block.

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
            "Optional override of the top-level ``target_length``. When "
            "set, sub-issue 2's resolution helper uses this value rather "
            "than the top-level one. Same flat-shape semantics as the "
            "top-level field; per-version overrides are NOT supported here."
        ),
    )
    unknown_keys: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Forward-compat passthrough: any keys in ``rubric_overrides`` "
            "that the loader does not recognize land here verbatim. A "
            "warning is emitted on read so the operator notices, but the "
            "load does not fail. This lets a future shipped ``memo_subtype`` "
            "enum or a Concision-Discipline knob land in ``.anvil.json`` "
            "ahead of loader support."
        ),
    )

    @property
    def is_empty(self) -> bool:
        """Return True when no overrides are declared.

        Useful as a fast-path in the reviewer: a memo with ``is_empty`` true
        should produce identical output to a memo with no ``rubric_overrides``
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _ParseContext:
    """Accumulator for the parse pass.

    Separates the parse logic from the warning surface so the strict variant
    can convert warnings to ``ValueError`` at the boundary instead of
    plumbing a "raise on warn" flag through every helper.
    """

    warnings: List[str]

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def _read_anvil_json(thread_dir: Path) -> Dict[str, Any]:
    """Read ``<thread_dir>/.anvil.json`` and return parsed dict (or ``{}``).

    Mirrors the precedent in ``anvil/lib/rubric.py`` — a missing file, a
    JSON parse error, an OS error, or a non-dict top-level all degrade to
    an empty dict. The strict variant (``_read_anvil_json_strict``) raises
    on every failure mode; production callers should always use this lenient
    form.
    """
    anvil_json = thread_dir / ".anvil.json"
    if not anvil_json.is_file():
        return {}
    try:
        with anvil_json.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _read_anvil_json_strict(thread_dir: Path) -> Dict[str, Any]:
    """Strict variant of ``_read_anvil_json`` used by ``load_rubric_overrides_strict``.

    Raises ``FileNotFoundError`` when the file is missing,
    ``json.JSONDecodeError`` on malformed JSON, and ``ValueError`` on a
    non-dict top-level. The strict variant exists to back the test suite's
    fixtures-for-validation contract; lifecycle commands use the lenient form.
    """
    anvil_json = thread_dir / ".anvil.json"
    if not anvil_json.is_file():
        raise FileNotFoundError(f".anvil.json not found at {anvil_json}")
    with anvil_json.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(
            f".anvil.json top-level must be a JSON object at {anvil_json}; "
            f"got {type(data).__name__}"
        )
    return data


def _normalize_target_length(
    raw: Any, ctx: _ParseContext
) -> Optional[TargetLengthRange]:
    """Convert a raw ``target_length`` dict to a typed ``TargetLengthRange``.

    Accepts the **flat shape** only — ``{"words": [min, max]}`` or
    ``{"pages": [min, max]}``. The extended per-version-override shape
    documented in SKILL.md §"Length targets" is NOT accepted here:
    ``rubric_overrides.target_length`` is the *subtype* surface, not the
    per-version surface. A consumer who needs per-version overrides keeps
    them at the top level of ``.anvil.json``.

    Returns ``None`` (with a warning) on any of:
    - non-dict input
    - dict with neither ``words`` nor ``pages``
    - dict with both ``words`` AND ``pages`` (ambiguous)
    - dict with extended-shape keys (``default``, ``overrides``)
    - range value that is not a 2-element list of non-negative integers
    - range with ``min > max``
    """
    if not isinstance(raw, dict):
        ctx.warn(
            f"rubric_overrides.target_length must be a dict; got {type(raw).__name__} — dropped"
        )
        return None

    # Reject extended-shape keys explicitly so a consumer who copy-pastes a
    # top-level target_length block sees a clear warning rather than silent
    # acceptance of the wrong shape.
    forbidden = {"default", "overrides"} & set(raw.keys())
    if forbidden:
        ctx.warn(
            "rubric_overrides.target_length does not accept extended-shape "
            f"keys {sorted(forbidden)} — use flat shape "
            '{"words": [min, max]} or {"pages": [min, max]}; dropped'
        )
        return None

    has_words = "words" in raw
    has_pages = "pages" in raw
    if has_words and has_pages:
        ctx.warn(
            "rubric_overrides.target_length has both 'words' and 'pages' — "
            "ambiguous shape; dropped"
        )
        return None
    if not has_words and not has_pages:
        ctx.warn(
            "rubric_overrides.target_length has neither 'words' nor 'pages' — "
            "no range to apply; dropped"
        )
        return None

    source_key = "words" if has_words else "pages"
    range_value = raw[source_key]

    if not isinstance(range_value, list) or len(range_value) != 2:
        ctx.warn(
            f"rubric_overrides.target_length.{source_key} must be a 2-element "
            f"list; got {range_value!r} — dropped"
        )
        return None

    lo_raw, hi_raw = range_value
    # Reject booleans (Python's bool is an int subclass; we don't want True/False here)
    # and non-integer types.
    if (
        isinstance(lo_raw, bool)
        or isinstance(hi_raw, bool)
        or not isinstance(lo_raw, int)
        or not isinstance(hi_raw, int)
    ):
        ctx.warn(
            f"rubric_overrides.target_length.{source_key} must be "
            f"[int, int]; got {range_value!r} — dropped"
        )
        return None

    if lo_raw < 0 or hi_raw < 0:
        ctx.warn(
            f"rubric_overrides.target_length.{source_key} must be non-negative; "
            f"got {range_value!r} — dropped"
        )
        return None

    if lo_raw > hi_raw:
        ctx.warn(
            f"rubric_overrides.target_length.{source_key} requires min <= max; "
            f"got [{lo_raw}, {hi_raw}] — dropped"
        )
        return None

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


def _parse_dim_calibration_key(key: str) -> Optional[int]:
    """Return the dimension number from a ``dim_<N>_calibration`` key, or ``None``."""
    m = _DIM_CALIBRATION_RE.match(key)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _parse_rubric_overrides(
    raw: Any, ctx: _ParseContext
) -> RubricOverrides:
    """Core parse pass over the ``rubric_overrides`` dict.

    Returns an empty ``RubricOverrides`` (with warnings on ``ctx``) when the
    input is not a dict. Otherwise walks the keys, dispatches each to the
    right typed slot, and returns the assembled model.
    """
    if not isinstance(raw, dict):
        ctx.warn(
            f"rubric_overrides must be a dict; got {type(raw).__name__} — using empty overrides"
        )
        return RubricOverrides()

    memo_subtype: Optional[str] = None
    calibrations: List[CalibrationOverride] = []
    target_length: Optional[TargetLengthRange] = None
    unknown_keys: Dict[str, Any] = {}

    # Track which dim numbers we've seen so a duplicate emits a warning rather
    # than silently producing two entries.
    seen_dims: set[int] = set()

    for key, value in raw.items():
        if key == "memo_subtype":
            if isinstance(value, str) and value.strip():
                memo_subtype = value
            else:
                ctx.warn(
                    f"rubric_overrides.memo_subtype must be a non-empty string; "
                    f"got {value!r} — dropped"
                )
            continue

        if key == "target_length":
            target_length = _normalize_target_length(value, ctx)
            continue

        dim = _parse_dim_calibration_key(key)
        if dim is not None:
            if dim < MIN_DIM or dim > MAX_DIM:
                ctx.warn(
                    f"rubric_overrides.{key}: dimension {dim} out of range "
                    f"[{MIN_DIM}, {MAX_DIM}] — dropped"
                )
                continue
            if dim in seen_dims:
                ctx.warn(
                    f"rubric_overrides.{key}: dimension {dim} declared more "
                    f"than once — keeping first occurrence"
                )
                continue
            if not isinstance(value, str) or not value.strip():
                ctx.warn(
                    f"rubric_overrides.{key} must be a non-empty string; "
                    f"got {value!r} — dropped"
                )
                continue
            seen_dims.add(dim)
            calibrations.append(CalibrationOverride(dimension=dim, text=value))
            continue

        # Unknown key — preserve verbatim with a warning so a future shipped
        # key (e.g. concision_discipline) can land in .anvil.json ahead of
        # loader support without breaking existing consumers.
        unknown_keys[key] = value
        ctx.warn(
            f"rubric_overrides.{key}: unknown key — preserved verbatim under "
            f"unknown_keys (forward-compat); reviewer will not apply it"
        )

    # Sort calibrations by dimension for deterministic iteration order.
    calibrations.sort(key=lambda c: c.dimension)

    return RubricOverrides(
        memo_subtype=memo_subtype,
        calibrations=calibrations,
        target_length=target_length,
        unknown_keys=unknown_keys,
    )


def _emit_warnings(messages: List[str]) -> None:
    """Re-emit accumulated parse warnings via ``warnings.warn``.

    Each message becomes a ``UserWarning`` so callers running under
    ``-W error::UserWarning`` get a hard failure on any tolerated-but-noisy
    input. Production callers see the message in stderr (or test capture).
    """
    for msg in messages:
        warnings.warn(msg, UserWarning, stacklevel=2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_rubric_overrides(thread_dir: Path) -> RubricOverrides:
    """Load and return the ``rubric_overrides`` block for a memo thread.

    Reads ``<thread_dir>/.anvil.json``. Returns an empty ``RubricOverrides``
    when the file is missing, malformed, or has no ``rubric_overrides`` block.
    Emits ``UserWarning`` for any per-field validation failure (malformed
    value, out-of-range dim, unknown key) — the field is dropped (or
    preserved under ``unknown_keys``) and the rest of the block is returned.

    This is the **lenient** form used by lifecycle commands. The strict form
    (``load_rubric_overrides_strict``) raises on any malformed input and is
    used by the test suite to assert specific validation behavior.

    Parameters
    ----------
    thread_dir
        The memo thread root (the directory containing ``BRIEF.md`` and the
        ``.anvil.json`` file, NOT a version subdirectory like ``thread.1/``).

    Returns
    -------
    RubricOverrides
        Parsed overrides. Use ``RubricOverrides.is_empty`` to fast-path the
        no-overrides case.
    """
    data = _read_anvil_json(thread_dir)
    raw = data.get("rubric_overrides")
    if raw is None:
        return RubricOverrides()

    ctx = _ParseContext(warnings=[])
    parsed = _parse_rubric_overrides(raw, ctx)
    _emit_warnings(ctx.warnings)
    return parsed


def load_rubric_overrides_strict(thread_dir: Path) -> RubricOverrides:
    """Strict variant of ``load_rubric_overrides``.

    Raises ``FileNotFoundError`` when ``<thread_dir>/.anvil.json`` is missing,
    ``json.JSONDecodeError`` on malformed JSON, and ``ValueError`` on any
    per-field validation failure (the failure message includes the full list
    of warnings the lenient form would have emitted).

    This is the form the test suite uses to assert that specific malformed
    inputs produce specific diagnostic messages. Lifecycle commands MUST NOT
    use this form — they use the lenient ``load_rubric_overrides`` so a
    consumer typo in ``.anvil.json`` never breaks the lifecycle.
    """
    data = _read_anvil_json_strict(thread_dir)
    raw = data.get("rubric_overrides")
    if raw is None:
        return RubricOverrides()

    ctx = _ParseContext(warnings=[])
    parsed = _parse_rubric_overrides(raw, ctx)
    if ctx.warnings:
        joined = "\n  - ".join(ctx.warnings)
        raise ValueError(
            f"rubric_overrides validation failed at {thread_dir / '.anvil.json'}:\n  - {joined}"
        )
    return parsed


# ---------------------------------------------------------------------------
# body_filename loader (issue #279)
# ---------------------------------------------------------------------------


def _validate_body_filename(value: Any, ctx: _ParseContext) -> Optional[str]:
    """Validate a candidate ``body_filename`` value; return verbatim or ``None``.

    The validation rules (per issue #279 curator brief):

    - Must be a non-empty string (after strip).
    - Must NOT contain ``/`` or ``\\`` (anti-path-traversal — body filenames
      are version-dir-local, not paths).
    - Must NOT contain ``..`` (anti-path-traversal complement).
    - Must end in ``.md`` (the renderer and placeholder-scan paths assume
      markdown source).

    Violations append a warning to ``ctx`` and return ``None`` so the caller
    falls back to :data:`DEFAULT_BODY_FILENAME`. The validation discipline
    mirrors ``_normalize_target_length`` — lenient and graceful, never fatal.
    """
    if not isinstance(value, str):
        ctx.warn(
            f"body_filename must be a string; got {type(value).__name__} — "
            f"using default {DEFAULT_BODY_FILENAME!r}"
        )
        return None
    if not value.strip():
        ctx.warn(
            f"body_filename must be a non-empty string; got {value!r} — "
            f"using default {DEFAULT_BODY_FILENAME!r}"
        )
        return None
    if "/" in value or "\\" in value:
        ctx.warn(
            f"body_filename must not contain '/' or '\\\\' (must be a "
            f"version-dir-local filename, not a path); got {value!r} — "
            f"using default {DEFAULT_BODY_FILENAME!r}"
        )
        return None
    if ".." in value:
        ctx.warn(
            f"body_filename must not contain '..' (anti-path-traversal); "
            f"got {value!r} — using default {DEFAULT_BODY_FILENAME!r}"
        )
        return None
    if not value.endswith(".md"):
        ctx.warn(
            f"body_filename must end in '.md' (renderer + placeholder scan "
            f"assume markdown); got {value!r} — using default "
            f"{DEFAULT_BODY_FILENAME!r}"
        )
        return None
    return value


def load_body_filename(thread_dir: Path) -> str:
    """Load the per-thread ``body_filename`` for a memo thread.

    Reads ``<thread_dir>/.anvil.json`` and returns the validated
    ``body_filename`` value, or :data:`DEFAULT_BODY_FILENAME` (``"memo.md"``)
    when:

    - ``.anvil.json`` is missing.
    - ``.anvil.json`` exists but has no ``body_filename`` key.
    - ``body_filename`` is a non-string, empty string, contains ``/`` /
      ``\\`` / ``..``, or does not end in ``.md``.

    This is the **lenient** form used by lifecycle commands. A consumer typo
    in ``.anvil.json`` never breaks the lifecycle — the loader emits a
    ``UserWarning`` and degrades to the default. The strict form
    (:func:`load_body_filename_strict`) raises on the same conditions and is
    used by the test suite to assert specific validation behavior.

    The ``body_filename`` field is a **top-level** key in ``.anvil.json``
    (sibling to ``rubric_overrides`` and ``target_length``), NOT nested
    inside ``rubric_overrides``. The body filename is a per-thread
    structural choice independent of rubric calibration; keeping them
    orthogonal preserves the principle that ``rubric_overrides`` is the
    *scoring* surface and ``body_filename`` is the *output-naming* surface.

    Example ``.anvil.json``::

        {
          "max_iterations": 8,
          "body_filename": "paper.md",
          "rubric_overrides": { "memo_subtype": "latency-wall" }
        }

    Parameters
    ----------
    thread_dir
        The memo thread root (the directory containing ``BRIEF.md`` and the
        ``.anvil.json`` file, NOT a version subdirectory like
        ``thread.1/``).

    Returns
    -------
    str
        The validated body filename (e.g. ``"paper.md"``, ``"plan.md"``),
        or :data:`DEFAULT_BODY_FILENAME` (``"memo.md"``) when the key is
        absent, malformed, or fails validation.
    """
    data = _read_anvil_json(thread_dir)
    raw = data.get("body_filename")
    if raw is None:
        return DEFAULT_BODY_FILENAME

    ctx = _ParseContext(warnings=[])
    validated = _validate_body_filename(raw, ctx)
    _emit_warnings(ctx.warnings)
    if validated is None:
        return DEFAULT_BODY_FILENAME
    return validated


def load_body_filename_strict(thread_dir: Path) -> str:
    """Strict variant of :func:`load_body_filename`.

    Raises ``FileNotFoundError`` when ``<thread_dir>/.anvil.json`` is missing,
    ``json.JSONDecodeError`` on malformed JSON, ``ValueError`` on a non-dict
    top-level, and ``ValueError`` on any ``body_filename`` validation
    failure (with the full validation message in the exception).

    When ``body_filename`` is absent from a present, well-formed
    ``.anvil.json``, returns :data:`DEFAULT_BODY_FILENAME` (this is not a
    validation failure — absence is the expected backward-compat shape).

    This is the form the test suite uses to assert that specific malformed
    inputs produce specific diagnostic messages. Lifecycle commands MUST
    NOT use this form — they use the lenient :func:`load_body_filename` so
    a consumer typo in ``.anvil.json`` never breaks the lifecycle.
    """
    data = _read_anvil_json_strict(thread_dir)
    raw = data.get("body_filename")
    if raw is None:
        return DEFAULT_BODY_FILENAME

    ctx = _ParseContext(warnings=[])
    validated = _validate_body_filename(raw, ctx)
    if ctx.warnings:
        joined = "\n  - ".join(ctx.warnings)
        raise ValueError(
            f"body_filename validation failed at {thread_dir / '.anvil.json'}:\n  - {joined}"
        )
    # validated is non-None when ctx.warnings is empty — every validation
    # path that returns None also appends to ctx.warnings. Belt-and-suspenders.
    assert validated is not None
    return validated


__all__ = [
    "CalibrationOverride",
    "DEFAULT_BODY_FILENAME",
    "MAX_DIM",
    "MIN_DIM",
    "RubricOverrides",
    "TargetLengthRange",
    "load_body_filename",
    "load_body_filename_strict",
    "load_rubric_overrides",
    "load_rubric_overrides_strict",
]
