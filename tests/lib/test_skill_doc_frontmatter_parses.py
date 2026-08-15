"""Cross-skill doc-guard: every shipped command doc's YAML frontmatter
must actually parse (issue #1084).

``anvil/skills/deck/commands/deck-imagegen.md`` shipped with an unquoted
``description:`` value containing a second ``: `` sequence
(`` `imagery_policy: generative-eligible` ``), which ``yaml.safe_load``
misparses as a nested mapping and raises ``ScannerError``. The same class
of bug previously shipped in
``anvil/skills/ip-uspto-provisional/commands/ip-uspto-provisional-vision.md``
(fixed incidentally by PR #1085, the ``anvil/lib/frontmatter.py``
consolidation) — no test caught either occurrence, because
``tests/agents/test_agent_frontmatter_schema.py`` only covers the
*generated* ``anvil/agents/anvil-*.md`` registry, not the skill-local
``commands/*.md`` / ``SKILL.md`` docs that agent generation and tooling
also parse as frontmatter.

This module closes that gap with a single repo-wide sweep, mirroring the
parametrize-plus-aggregate shape of
``test_command_docs_no_portfolio_wide_sweep.py``: every doc under
``anvil/skills/*/commands/*.md`` and every ``anvil/skills/*/SKILL.md``
must open with a ``---`` delimiter, close with a matching ``---``, and
``yaml.safe_load`` its frontmatter body to a ``dict`` without raising.

Known-intentional non-YAML templates (e.g. ``{{PLACEHOLDER}}``-driven
scaffolds under ``templates/``) are out of scope for this sweep — it only
walks ``commands/*.md`` and ``SKILL.md``, neither of which uses that
placeholder convention in its frontmatter block.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_GLOB = "anvil/skills/*/commands/*.md"
SKILL_GLOB = "anvil/skills/*/SKILL.md"

FRONTMATTER_DELIM = "---"


def _docs() -> List[Path]:
    docs = sorted(
        set(REPO_ROOT.glob(COMMANDS_GLOB)) | set(REPO_ROOT.glob(SKILL_GLOB))
    )
    assert docs, (
        f"no docs found under {COMMANDS_GLOB!r} or {SKILL_GLOB!r}"
    )
    return docs


def _doc_ids() -> List[str]:
    return [str(p.relative_to(REPO_ROOT)) for p in _docs()]


def _parse_frontmatter_or_raise(doc: Path) -> dict:
    """Parse ``doc``'s frontmatter block, raising ``AssertionError`` with a
    descriptive message on any failure mode (missing delimiters, YAML
    parse error, or a non-dict result)."""
    text = doc.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = doc.relative_to(REPO_ROOT)

    assert lines and lines[0].strip() == FRONTMATTER_DELIM, (
        f"{rel} does not open with a '{FRONTMATTER_DELIM}' frontmatter "
        "delimiter as its first line"
    )

    close_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIM:
            close_idx = i
            break
    assert close_idx is not None, (
        f"{rel} has an opening '{FRONTMATTER_DELIM}' but no matching "
        "closing delimiter"
    )

    body = "\n".join(lines[1:close_idx])
    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        raise AssertionError(
            f"{rel} frontmatter is not valid YAML: {exc}"
        ) from exc

    assert isinstance(parsed, dict), (
        f"{rel} frontmatter parsed to {type(parsed).__name__}, not a dict "
        f"(value: {parsed!r})"
    )
    return parsed


@pytest.mark.parametrize("doc", _docs(), ids=_doc_ids())
def test_doc_frontmatter_parses_to_dict(doc: Path) -> None:
    """Regression guard (issue #1084): every command/SKILL doc's
    frontmatter block must ``yaml.safe_load`` to a ``dict``. An unquoted
    scalar value containing a second ``: `` sequence (e.g. a
    ``description:`` field quoting a nested ``key: value`` pair) is
    misparsed by YAML as a nested mapping and raises ``ScannerError`` —
    exactly the failure mode this guard prevents from shipping again."""
    _parse_frontmatter_or_raise(doc)


def test_all_doc_frontmatter_parses_aggregate() -> None:
    """Aggregate companion: collect EVERY offending doc in one pass so a
    regression touching multiple files reports them all at once."""
    offenders: List[str] = []
    for doc in _docs():
        try:
            _parse_frontmatter_or_raise(doc)
        except AssertionError as exc:
            offenders.append(f"{doc.relative_to(REPO_ROOT)}: {exc}")
    assert offenders == [], (
        "the following docs have unparseable frontmatter (issue #1084):\n"
        + "\n".join(offenders)
    )
