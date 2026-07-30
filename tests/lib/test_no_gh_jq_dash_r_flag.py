"""Doc-guard: no Loom command doc invokes ``gh ... --jq -r '<expr>'`` (issues
#788, #789, #790, #791).

``gh``'s ``--jq`` flag accepts exactly one argument (the jq expression). The
common shell habit of pairing it with ``-r`` (as one would with the standalone
``jq`` binary, where ``-r`` means "raw output") is invalid ``gh`` syntax: ``-r``
is consumed as the ``--jq`` argument itself, and the real jq expression becomes
a stray positional argument, so the invocation fails outright:

```
$ gh pr view 763 --json mergeable --jq -r '.mergeable'
accepts at most 1 arg(s), received 2
```

``gh``'s ``--jq`` already returns raw/unquoted output for scalar selectors
(``.mergeable``, ``.state``, ``.title``, etc.), so the fix is simply to drop
the invalid ``-r`` flag — never to re-add quoting/escaping.

Because several of these agent-doc bash snippets swallow the error via
``2>&1`` / ``2>/dev/null`` / ``|| echo ""`` redirects, the resulting shell
variable silently ends up empty or containing the literal error text instead
of the intended value — so downstream branch logic (mergeable checks, blocked-
dependency checks, PR/issue title lookups) can silently take the wrong path.

PR #791 fixed the two sites introduced by PR #787 (the ``LAST_MARKER``
size-limit-notice guard). Issue #790 fixed the 11 pre-existing sites this
repo-wide sweep found across ``champion-pr-merge.md`` (9 sites) and
``champion-reference.md`` (2 sites); no other ``.claude/commands/loom/*.md``
doc carried the pattern. This guard pins that outcome so the invalid
``--jq -r`` shape cannot silently reappear in any Loom command doc.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_GLOB = ".claude/commands/loom/*.md"

# Matches `--jq` immediately followed (allowing intervening whitespace) by a
# `-r` flag as its own token — the invalid gh invocation shape. Deliberately
# NOT anchored to a specific jq expression, so it catches every call site
# regardless of the selector used.
FORBIDDEN_PATTERN = re.compile(r"--jq\s+-r\b")


def _command_docs() -> List[Path]:
    docs = sorted(REPO_ROOT.glob(COMMANDS_GLOB))
    assert docs, f"no command docs found under {COMMANDS_GLOB!r}"
    return docs


def _doc_ids() -> List[str]:
    return [str(p.relative_to(REPO_ROOT)) for p in _command_docs()]


@pytest.mark.parametrize("doc", _command_docs(), ids=_doc_ids())
def test_command_doc_does_not_use_invalid_gh_jq_dash_r_flag(doc: Path):
    """Regression guard (issues #788, #789, #790, #791): a Loom command doc
    MUST NOT invoke ``gh ... --jq -r '<expr>'``. ``--jq`` accepts exactly one
    argument, so ``-r`` is consumed as that argument and the real jq
    expression becomes a stray positional, making the invocation fail with
    "accepts at most 1 arg(s), received 2". Drop the invalid ``-r`` flag —
    ``gh``'s ``--jq`` already returns raw output for scalar selectors.
    """
    text = doc.read_text(encoding="utf-8")
    match = FORBIDDEN_PATTERN.search(text)
    if match is not None:
        raise AssertionError(
            f"{doc.relative_to(REPO_ROOT)} invokes the invalid 'gh ... --jq "
            f"-r <expr>' shape ({match.group(0)!r}). --jq accepts exactly "
            "one argument; drop '-r' (gh's --jq already returns raw output "
            "for scalar selectors) — issues #788/#789/#790/#791."
        )


def test_no_command_doc_uses_invalid_gh_jq_dash_r_flag_aggregate():
    """Aggregate companion: collect EVERY offending doc + line in one pass so
    a multi-site regression reports all offenders at once."""
    offenders: List[str] = []
    for doc in _command_docs():
        text = doc.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_PATTERN.search(line):
                offenders.append(f"{doc.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert offenders == [], (
        "Loom command docs must not invoke the invalid 'gh ... --jq -r "
        "<expr>' shape (issues #788, #789, #790, #791); gh's --jq accepts "
        f"exactly one argument. Offenders:\n" + "\n".join(offenders)
    )
