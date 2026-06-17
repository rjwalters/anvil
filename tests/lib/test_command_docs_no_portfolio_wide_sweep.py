"""Cross-skill doc-guard: no command doc reintroduces the unsafe
portfolio-wide staging sweep in a per-critic entry step (issue #593 / #376).

The 41-site migration (PR #381, issue #376) replaced every per-critic
entry-step ``cleanup_stale_staging(<portfolio_root>)`` call with the
parallel-safe ``cleanup_one_staging(<final_dir>)``. The per-skill
sidecar-atomicity doc-guards (e.g.
``tests/skills/proposal/test_proposal_audit_sidecar_atomicity_doc.py``)
positively assert that each migrated doc names ``cleanup_one_staging``, but
only the memo-review guard forbids the unsafe call shape, and it does so for
a single doc. There is no cross-skill guard that prevents a future doc (or a
"simplification" of an existing one) from reintroducing the portfolio-wide
sweep in a per-critic entry step.

This module closes that gap with a single repo-wide sweep over every command
doc under ``anvil/skills/*/commands/*.md``. ``cleanup_stale_staging`` is the
operator-only portfolio-wide primitive — its documented home is the library
(``anvil/lib/sidecar.py``), the ``anvil/lib/snippets/progress.md`` operator
snippet, the CHANGELOG, and the library/snippet doc-guards. It must NEVER
appear in a per-critic command doc, because a command doc is exactly the
surface an LLM critic reads and executes literally at its entry step (the
mechanism behind the #593 canary repro, where an auditor swept a concurrent
reviewer's in-flight staging dir).

Because no command doc has any legitimate reason to mention the
portfolio-wide sweep, the guard is the simplest possible invariant: the
string ``cleanup_stale_staging`` must be absent from every command doc.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_GLOB = "anvil/skills/*/commands/*.md"

# The unsafe operator-only primitive. Forbidden in per-critic command docs.
UNSAFE_PRIMITIVE = "cleanup_stale_staging"
# The parallel-safe per-critic primitive. Expected wherever a command doc
# documents an entry-step staging sweep.
SAFE_PRIMITIVE = "cleanup_one_staging"


def _command_docs() -> List[Path]:
    docs = sorted(REPO_ROOT.glob(COMMANDS_GLOB))
    assert docs, f"no command docs found under {COMMANDS_GLOB!r}"
    return docs


def _doc_ids() -> List[str]:
    return [
        str(p.relative_to(REPO_ROOT)) for p in _command_docs()
    ]


@pytest.mark.parametrize(
    "doc",
    _command_docs(),
    ids=_doc_ids(),
)
def test_command_doc_does_not_reference_portfolio_wide_sweep(doc: Path):
    """Regression guard (issue #593 / #376): a command doc MUST NOT mention
    the operator-only ``cleanup_stale_staging`` portfolio-wide sweep. That
    primitive sweeps EVERY ``.tmp/`` staging dir under the portfolio root —
    including a concurrent critic's in-flight staging dir — so wiring it into
    a per-critic entry step can destroy a sibling critic's output mid-write.

    Per-critic entry steps MUST use the parallel-safe
    ``cleanup_one_staging(<final_dir>)`` instead.
    """
    text = doc.read_text(encoding="utf-8")
    assert UNSAFE_PRIMITIVE not in text, (
        f"{doc.relative_to(REPO_ROOT)} references the operator-only "
        f"portfolio-wide {UNSAFE_PRIMITIVE!r} sweep. Per-critic entry steps "
        f"must use the parallel-safe {SAFE_PRIMITIVE}(<final_dir>) instead "
        f"(issue #593 / #376) — the portfolio-wide sweep destroys concurrent "
        f"critics' in-flight staging dirs."
    )


def test_no_command_doc_references_portfolio_wide_sweep_aggregate():
    """Aggregate companion to the parametrized guard: collect EVERY
    offending command doc in one pass so a regression that reintroduces the
    unsafe sweep across multiple docs reports all of them at once (rather
    than failing one parametrized case at a time)."""
    offenders = [
        str(doc.relative_to(REPO_ROOT))
        for doc in _command_docs()
        if UNSAFE_PRIMITIVE in doc.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        "command docs must not reference the operator-only "
        f"{UNSAFE_PRIMITIVE!r} sweep (issue #593 / #376); offenders: "
        f"{offenders}"
    )


def test_command_docs_only_reference_the_safe_staging_sweep_primitive():
    """Positive companion: any command doc that documents a staging-cleanup
    sweep at all does so via the parallel-safe ``cleanup_one_staging``, and
    the migrated fan-out command set is non-empty.

    We detect "documents a staging sweep" by the presence of a
    ``..._staging`` cleanup primitive reference — NOT by ``staged_sidecar``
    alone, because bridge tools (e.g. ``project-migrate``) legitimately use
    ``staged_sidecar`` for atomic directory moves without being a per-critic
    fan-out entry step (they have no concurrent-sibling sweep to perform).

    This pins the established migration target so the per-critic fan-out
    pattern can't silently drift back to the unsafe portfolio-wide sweep.
    """
    sweep_docs: List[str] = []
    for doc in _command_docs():
        text = doc.read_text(encoding="utf-8")
        mentions_safe = SAFE_PRIMITIVE in text
        mentions_unsafe = UNSAFE_PRIMITIVE in text
        if not (mentions_safe or mentions_unsafe):
            continue
        sweep_docs.append(str(doc.relative_to(REPO_ROOT)))
        # The forbid-guard above already asserts UNSAFE_PRIMITIVE absence;
        # this companion makes the intent explicit at the per-doc level too.
        assert not mentions_unsafe, (
            f"{doc.relative_to(REPO_ROOT)} references the unsafe "
            f"{UNSAFE_PRIMITIVE!r} sweep instead of {SAFE_PRIMITIVE!r}"
        )
        assert mentions_safe, (
            f"{doc.relative_to(REPO_ROOT)} documents a staging sweep but does "
            f"not name the parallel-safe {SAFE_PRIMITIVE!r} primitive"
        )

    # Sanity floor: the migration shipped to a large command set; if this
    # drops to zero the detection heuristic has silently broken.
    assert len(sweep_docs) >= 40, (
        "expected the migrated per-critic command set to document the safe "
        f"{SAFE_PRIMITIVE!r} sweep; found only {len(sweep_docs)} docs — the "
        "detection heuristic may have broken"
    )
