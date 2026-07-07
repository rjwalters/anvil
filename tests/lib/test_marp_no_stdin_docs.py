"""Doc-pin: every literal ``marp … --pdf/--pptx`` render command block in the
deck/slides skills carries ``--no-stdin`` (issue #620).

In non-TTY / agent-driven contexts marp-cli blocks on an open stdin pipe,
printing ``Currently waiting data from stdin stream`` and hanging forever.
``--no-stdin`` makes the documented copy-paste invocations immune. This test
pins the fenced ``bash`` command blocks so a future edit that reintroduces a
stdin-blocking invocation fails fast.

Scope note: only fenced ``bash``/``sh``/``shell`` code blocks that actually
invoke ``marp`` with ``--pdf`` or ``--pptx`` are checked. Prose mentions and
```mermaid fixtures are intentionally excluded — they are not runnable command
blocks.
"""

from __future__ import annotations

import re
from pathlib import Path

# Repo root = three levels up from this file (tests/lib/<file>).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL_ROOTS = [
    _REPO_ROOT / "anvil" / "skills" / "deck",
    _REPO_ROOT / "anvil" / "skills" / "slides",
]

# Fenced code block with its info string, e.g. ```bash … ```.
_FENCE = re.compile(r"```([^\n`]*)\n(.*?)```", re.S)
_SHELL_LANGS = {"bash", "sh", "shell", "console"}


def _shell_marp_render_blocks() -> list[tuple[Path, str]]:
    """Return (path, block_body) for every shell fenced block that invokes
    ``marp`` with ``--pdf`` or ``--pptx``."""
    hits: list[tuple[Path, str]] = []
    for root in _SKILL_ROOTS:
        for md in sorted(root.rglob("*.md")):
            text = md.read_text(encoding="utf-8")
            for info, body in _FENCE.findall(text):
                lang = info.strip().split()[0] if info.strip() else ""
                if lang.lower() not in _SHELL_LANGS:
                    continue
                if re.search(r"\bmarp\b", body) and (
                    "--pdf" in body or "--pptx" in body
                ):
                    hits.append((md, body))
    return hits


def test_marp_render_blocks_pass_no_stdin() -> None:
    """AC4: no documented marp render command block lacks ``--no-stdin``."""
    offenders = [
        str(path.relative_to(_REPO_ROOT))
        for path, body in _shell_marp_render_blocks()
        if "--no-stdin" not in body
    ]
    assert not offenders, (
        "marp render command blocks missing --no-stdin (issue #620): "
        + ", ".join(offenders)
    )


def test_there_are_render_blocks_to_pin() -> None:
    """Guard against the scanner silently matching nothing (e.g. a regex
    regression) and the pin passing vacuously."""
    assert _shell_marp_render_blocks(), (
        "expected at least one documented marp render command block in the "
        "deck/slides skills; scanner found none"
    )
