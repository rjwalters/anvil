"""Index-coverage guards: every lib module and docs note must be indexed (#1481)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_every_lib_module_is_in_lib_readme():
    lib = ROOT / "anvil" / "lib"
    readme = (lib / "README.md").read_text(encoding="utf-8")
    # Anchor to an index-entry line (two-space indent, name, whitespace) so a
    # prose mention or a longer name containing this one (render.py inside
    # latex_render.py) cannot satisfy the guard.
    missing = sorted(
        p.name
        for p in lib.glob("*.py")
        if p.name != "__init__.py"
        and not re.search(rf"^  {re.escape(p.name)}\s", readme, re.M)
    )
    assert not missing, f"anvil/lib/README.md is missing entries for: {missing}"


def test_every_docs_note_is_linked_from_docs_readme():
    docs = ROOT / "docs"
    readme = (docs / "README.md").read_text(encoding="utf-8")
    missing = sorted(
        rel
        for rel in (p.relative_to(docs).as_posix() for p in docs.rglob("*.md"))
        if rel != "README.md" and f"({rel})" not in readme
    )
    assert not missing, f"docs/README.md does not link: {missing}"
