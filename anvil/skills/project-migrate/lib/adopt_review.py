"""Single-file ``review.md`` → critic-sibling content conversion (issue #454).

Phase 3a of the issue #432 foreign-grammar adoption arc (Phase 1 =
``--adopt-vn``, PR #439; Phase 2 = ``--adopt-family``, issue #440). Phases
1 and 2 make foreign version-dir and critic-sibling **names** canonical;
this phase is the deferred **content** step: converting a foreign critic
sibling's single-file prose ``review.md`` into a payload
``anvil/lib/critics.py::discover_critics`` can recognize.

Honest scope: STUB conversion, NOT prose→score extraction
---------------------------------------------------------

The binding curation decision (issue #454, 2026-06-12): foreign
single-file ``review.md`` payloads (sphere ``.enablement`` / ``.s101`` /
``.fto`` / ``.critic`` / ``.audit2`` / ``.pre_flight`` siblings) were
**never scored on any anvil rubric**. There is no per-dimension table, no
``Total: X/Y``, no ``advance: true|false`` to parse. Synthesizing /44
scores from foreign prose would be **fabrication**, and a deterministic
pass cannot do it honestly. An LLM rescoring pass is exactly
``rubric-rebackport --rescore``'s territory, which is explicitly scoped
out (it targets *anvil-shaped* legacy reviews — its heuristics key on a
known ``rubric_total`` foreign reviews lack).

So this mode does the minimal honest thing: for each sidecar dir holding
ONLY ``review.md`` (failing ``critics._has_recognizable_review``), write a
canonical ``_review.json`` that is **recognizable-but-explicitly-unscored**
(empty ``scores``/``findings``/``critical_flags``; null
``total``/``threshold``/``verdict``; ``unscored: True``) plus a sibling
``_meta.json`` foreign-provenance marker, while preserving the original
``review.md`` **byte-identical**. NO LLM call. NO score synthesis.

Phase 3b (optional operator-driven LLM rescore — turning the stub into a
real scored review) is **deferred to a separate issue**; this module never
attempts it.

Design notes
------------

- **Pure planner — no mutations.** :func:`build_adopt_review_plan` reads
  the tree but never writes. The dry-run-by-default contract (the
  universal invariant in this skill) depends on it. Mutations live in
  :func:`apply_adopt_review_plan`, gated behind ``--apply``.
- **Standalone on adopted trees (single responsibility).** This mode does
  NOT chain after ``--adopt-family``; it runs on a tree whose names are
  already canonical (``<slug>/<slug>.{N}/`` with ``<slug>.{N}.<tag>``
  siblings). Composition is via two operator runs. It touches NO
  ``BRIEF.md`` — it is purely a critic-sibling content conversion.
- **Verbatim preservation.** ``review.md`` is copied into the staging dir
  byte-for-byte; the stub is purely additive (``_review.json`` +
  ``_meta.json`` written *beside* it). The original is never mutated.
- **Atomic, crash-safe writes via** :mod:`anvil.lib.sidecar`. Each
  conversion stages a full replacement of the sidecar dir
  (``review.md`` copy + the two new files) into a leading-dot ``.tmp``
  staging dir, then swaps it into place atomically — the existing dir is
  moved aside first (``staged_sidecar`` refuses a pre-existing target),
  the staging dir renamed in, and the moved-aside dir removed. On any
  mid-write failure the original dir is restored untouched.
- **Idempotence.** A sidecar that already carries ``_review.json``
  (a prior conversion, or a real review) passes
  ``_has_recognizable_review`` and is skipped — re-running yields an
  empty (no-op) plan.

Public API
----------

- ``AdoptReviewError`` — typed plan-time / apply-time refusal.
- ``StubConversion`` — one planned sidecar conversion.
- ``AdoptReviewPlan`` — the (possibly empty) batch of conversions.
- ``build_adopt_review_plan(directory)`` — pure planner.
- ``apply_adopt_review_plan(plan)`` — execute (``--apply`` only).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from anvil.lib.critics import (
    CANONICAL_REVIEW_FILENAME,
    _has_recognizable_review,
    _infer_critic_id,
    _infer_version_dir,
)
from anvil.lib.review_schema import Kind, Review
from anvil.lib.sidecar import cleanup_one_staging, staged_sidecar

from .detect import _VERSION_DIR_RE


class AdoptReviewError(ValueError):
    """Plan-time or apply-time conversion refusal."""


# The single-file payload filename the foreign critic siblings carry. This
# is the ONLY recognized prose payload for stub conversion — a sidecar
# holding a differently-named prose file is left untouched (reported as a
# skip) rather than guessed at.
FOREIGN_REVIEW_FILENAME = "review.md"

# The foreign-provenance sidecar marker filename. Distinct from the
# legacy ip-uspto ``_meta.json`` triple member: this marker is paired with
# a canonical ``_review.json`` (the unscored stub), so it never triggers
# the legacy ip-uspto adapter (which requires ``_summary.md`` +
# ``findings.md`` + ``_meta.json`` ALL present and NO ``_review.json``).
PROVENANCE_FILENAME = "_meta.json"

# The provenance-marker contract (issue #454 curation comment). Stamped
# verbatim onto every converted sidecar's ``_meta.json`` so a downstream
# reader can distinguish an unscored-foreign stub from a real review.
PROVENANCE_SOURCE = "foreign-adopted"
PROVENANCE_ADOPTED_BY = "anvil:project-migrate#454"


# A ``<slug>.<N>.<tag>`` critic sidecar under an adopted tree. The version
# stem ``<slug>.<N>`` must itself end in ``.<digits>`` (the canonical
# version-dir grammar) and the tag is a single dot-free segment (the
# ``discover_critics`` single-segment tag rule).
def _split_sidecar_name(name: str) -> Optional[tuple]:
    """Return ``(version_dir_name, tag)`` for a ``<slug>.<N>.<tag>`` dir.

    Returns ``None`` when ``name`` is not a critic-sibling shape: the
    trailing tag must be a single dot-free segment AND the remaining stem
    must be a canonical ``<slug>.<N>`` version dir (ending in
    ``.<digits>``). This is the same shape ``discover_critics`` enumerates
    — we mirror it so the planner only converts dirs discovery WOULD see
    once a ``_review.json`` lands.
    """
    head, sep, tag = name.rpartition(".")
    if not sep or not head or not tag:
        return None
    if "." not in head:
        # ``<head>`` would have to be ``<slug>.<N>``; a single segment is
        # not a version dir.
        return None
    if _VERSION_DIR_RE.match(head) is None:
        return None
    return head, tag


@dataclass
class StubConversion:
    """One planned sidecar stub conversion.

    Attributes
    ----------
    sidecar_dir
        The existing ``<slug>.<N>.<tag>/`` directory holding only
        ``review.md`` (the conversion target).
    version_dir
        The version-dir name this critic reviews (e.g. ``brasidas-c.7``),
        inferred from the sidecar name. Echoed into the stub's
        ``version_dir`` field.
    critic_id
        The trailing tag (e.g. ``enablement``), inferred from the sidecar
        name. Echoed into the stub's ``critic_id`` field.
    review_filename
        The verbatim-preserved prose filename (always
        :data:`FOREIGN_REVIEW_FILENAME`). Recorded as PRESERVED, never as
        a rename source.
    """

    sidecar_dir: Path
    version_dir: str
    critic_id: str
    review_filename: str = FOREIGN_REVIEW_FILENAME


@dataclass
class AdoptReviewPlan:
    """The (possibly empty) batch of stub conversions for one tree.

    Attributes
    ----------
    directory
        The adopted-tree root the plan was built for.
    conversions
        One :class:`StubConversion` per ``review.md``-only sidecar found.
        Empty when the tree has none (idempotent no-op).
    skipped
        Sidecar dir names left untouched with the reason: already
        recognizable (``_review.json`` present), or holding a prose
        payload that is not ``review.md``. Reported, never converted.
    """

    directory: Path
    conversions: List[StubConversion] = field(default_factory=list)
    skipped: List[tuple] = field(default_factory=list)

    @property
    def is_noop(self) -> bool:
        return not self.conversions


def _scan_adopted_tree(directory: Path) -> List[Path]:
    """Return every ``<slug>.<N>.<tag>/`` sidecar dir under ``directory``.

    Walks the adopted tree: ``<directory>/<slug>/`` thread roots, each
    holding ``<slug>.<N>/`` version dirs and their ``<slug>.<N>.<tag>/``
    critic siblings (the Phase-2 output shape). Also tolerates the
    flat layout (siblings directly under ``directory``) so the mode works
    on a directly-passed thread root too. Returns sidecar dirs only —
    version dirs and bodies are never returned.
    """
    sidecars: List[Path] = []
    seen: set = set()

    def _collect(parent: Path) -> None:
        try:
            children = sorted(parent.iterdir())
        except OSError:
            return
        for child in children:
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue  # staging dirs / dotfiles
            if _split_sidecar_name(child.name) is not None:
                rp = child.resolve()
                if rp not in seen:
                    seen.add(rp)
                    sidecars.append(child)

    # Flat: sidecars directly under the passed directory (thread-root case).
    _collect(directory)
    # Nested: <directory>/<slug>/<slug>.N.tag (project-root case).
    try:
        top = sorted(directory.iterdir())
    except OSError:
        top = []
    for child in top:
        if child.is_dir() and not child.name.startswith("."):
            _collect(child)

    sidecars.sort(key=lambda p: str(p.resolve()))
    return sidecars


def build_adopt_review_plan(directory: Path) -> AdoptReviewPlan:
    """Build a stub-conversion :class:`AdoptReviewPlan` for ``directory``.

    Pure planner (no mutations). Scans an already-adopted tree for critic
    sidecar dirs that hold ONLY a single-file ``review.md`` payload —
    those that fail ``critics._has_recognizable_review`` and so stay
    invisible to ``discover_critics`` (the #346 additive contract).

    A directory with no such sidecar yields an EMPTY plan
    (``plan.is_noop``) — re-running on a tree where every sidecar already
    carries ``_review.json`` is a no-op, not an error.

    Parameters
    ----------
    directory
        An adopted-tree root (project root or a single thread root). Names
        are assumed already canonical — this mode runs AFTER
        ``--adopt-family`` / ``--adopt-vn``.

    Raises
    ------
    AdoptReviewError
        When ``directory`` does not exist or is not a directory.
    """
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise AdoptReviewError(
            f"--adopt-review target {directory} does not exist or is not "
            f"a directory."
        )

    plan = AdoptReviewPlan(directory=directory)

    for sidecar in _scan_adopted_tree(directory):
        # Idempotence + real-review safety: a sidecar that already passes
        # discovery (carries `_review.json` or a complete legacy triple)
        # is never touched.
        if _has_recognizable_review(sidecar):
            plan.skipped.append(
                (sidecar.name, "already recognizable (_review.json present)")
            )
            continue
        review_md = sidecar / FOREIGN_REVIEW_FILENAME
        if not review_md.is_file():
            # A sidecar with neither a recognizable payload nor the
            # expected `review.md` prose — left untouched (we never guess
            # a differently-named prose file).
            plan.skipped.append(
                (sidecar.name, f"no {FOREIGN_REVIEW_FILENAME} payload")
            )
            continue
        plan.conversions.append(
            StubConversion(
                sidecar_dir=sidecar,
                version_dir=_infer_version_dir(sidecar),
                critic_id=_infer_critic_id(sidecar),
            )
        )

    return plan


def build_stub_review(conv: StubConversion) -> Review:
    """Build the honest unscored-foreign stub :class:`Review` for ``conv``.

    Empty ``scores``/``findings``/``critical_flags``; null
    ``total``/``threshold``/``verdict``; ``unscored=True``. NO fabricated
    dimensions. Validates against ``review_schema`` (the ``unscored=True``
    carve-out is the only thing that lets ``scores`` be empty).
    """
    return Review(
        schema_version="1",
        kind=Kind.JUDGMENT,
        version_dir=conv.version_dir,
        critic_id=conv.critic_id,
        scores=[],
        findings=[],
        critical_flags=[],
        total=None,
        threshold=None,
        verdict=None,
        unscored=True,
    )


def build_provenance_marker(conv: StubConversion) -> dict:
    """Build the ``_meta.json`` foreign-provenance marker for ``conv``.

    The exact shape pinned by the issue #454 curation comment — a reader
    distinguishes an unscored-foreign stub from a real review by this
    marker (``source: foreign-adopted``, ``unscored: true``).
    """
    return {
        "source": PROVENANCE_SOURCE,
        "unscored": True,
        "origin_filename": conv.review_filename,
        "adopted_by": PROVENANCE_ADOPTED_BY,
    }


@dataclass
class AdoptReviewApplyResult:
    """Typed outcome of :func:`apply_adopt_review_plan`.

    Attributes
    ----------
    converted
        Sidecar dir names successfully converted (stub written).
    failed
        ``(sidecar_name, error)`` for any conversion that failed; its dir
        was restored byte-identical.
    """

    converted: List[str] = field(default_factory=list)
    failed: List[tuple] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed


def apply_adopt_review_plan(plan: AdoptReviewPlan) -> AdoptReviewApplyResult:
    """Execute a stub-conversion plan (``--apply`` only).

    Each conversion is per-sidecar atomic and verbatim-preserving:

    1. Stage a full replacement dir (leading-dot ``.tmp`` sibling) via
       :func:`anvil.lib.sidecar.staged_sidecar`: copy ``review.md`` into
       the staging dir byte-for-byte, then write ``_review.json`` (the
       stub) and ``_meta.json`` (the provenance marker).
    2. Atomically swap: move the existing sidecar dir aside to a
       leading-dot ``.bak`` sibling (``staged_sidecar`` refuses a
       pre-existing final target), let the context manager rename the
       staging dir into place, then remove the moved-aside backup.
    3. On any failure, the moved-aside original is restored untouched and
       the staging dir is swept; the conversion is recorded as failed.

    Failures in one sidecar do not affect already-converted siblings.
    """
    result = AdoptReviewApplyResult()

    for conv in plan.conversions:
        sidecar = conv.sidecar_dir
        backup = sidecar.parent / f".{sidecar.name}.bak"
        try:
            _convert_one(conv, backup)
            result.converted.append(sidecar.name)
        except BaseException as exc:  # noqa: BLE001 — isolate per sidecar
            # Restore the moved-aside original if the swap left it aside.
            if backup.exists() and not sidecar.exists():
                backup.rename(sidecar)
            elif backup.exists():
                # Both present (failure after rename-in but before backup
                # removal is impossible — that path can't raise — but be
                # defensive): drop the stale backup, keep the live dir.
                shutil.rmtree(backup)
            cleanup_one_staging(sidecar)
            result.failed.append((sidecar.name, str(exc)))

    return result


def _convert_one(conv: StubConversion, backup: Path) -> None:
    """Atomically replace ``conv.sidecar_dir`` with the stub-bearing dir.

    Raises on any failure; the caller restores from ``backup``.
    """
    sidecar = conv.sidecar_dir
    stub = build_stub_review(conv)
    marker = build_provenance_marker(conv)

    # Clear any stale staging from a prior interrupted attempt (parallel-
    # safe: targets only THIS sidecar's staging path).
    cleanup_one_staging(sidecar)

    # Move the live dir aside so the atomic-rename target is free. Every
    # original file travels along in `backup` — the conversion is purely
    # additive and `review.md` (plus anything else already present) is
    # preserved byte-identical.
    if backup.exists():
        shutil.rmtree(backup)
    sidecar.rename(backup)

    try:
        with staged_sidecar(
            final_dir=sidecar,
            required_files=[
                conv.review_filename,
                CANONICAL_REVIEW_FILENAME,
                PROVENANCE_FILENAME,
            ],
        ) as staging:
            # Re-materialize every original file byte-for-byte (verbatim
            # preservation), then layer the two additive files on top.
            for entry in sorted(backup.iterdir()):
                if entry.is_dir():
                    shutil.copytree(entry, staging / entry.name)
                else:
                    shutil.copy2(entry, staging / entry.name)
            (staging / CANONICAL_REVIEW_FILENAME).write_text(
                stub.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
            (staging / PROVENANCE_FILENAME).write_text(
                json.dumps(marker, indent=2) + "\n", encoding="utf-8"
            )
    except BaseException:
        # Staging failed or the rename-in raised: the live dir is still
        # aside at `backup`. Re-raise so the caller restores it.
        raise

    # Swap succeeded — drop the moved-aside original.
    shutil.rmtree(backup)


__all__ = [
    "AdoptReviewApplyResult",
    "AdoptReviewError",
    "AdoptReviewPlan",
    "StubConversion",
    "apply_adopt_review_plan",
    "build_adopt_review_plan",
    "build_provenance_marker",
    "build_stub_review",
    "FOREIGN_REVIEW_FILENAME",
    "PROVENANCE_FILENAME",
]
