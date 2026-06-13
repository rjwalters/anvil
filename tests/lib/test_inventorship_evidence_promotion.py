"""Canonical-path / promotion-identity tests for ``anvil.lib.inventorship_evidence``.

``inventorship_evidence.py`` shipped skill-local under
``anvil/skills/ip-uspto/lib/`` (#445) and was promoted to ``anvil/lib/``
in issue #516 once ``anvil:ip-uspto-provisional``'s inventorship-lite pass
became its second consumer (the wait-for-second-consumer lib-extraction
rule, CLAUDE.md §"Skill-local first, lib promotion later").

The back-compat surface is a **file-path string**, not a Python import
shim: both consumers invoke the module by direct file path (the calling
skill dirs are hyphenated, so command prose references the file path), and
``ip-uspto``'s ``inventorship_interview.py`` loads ``is_vendored_path`` from
the promoted location via ``importlib``. This file is the #382/#393-style
shim-identity regression test (precedent:
``tests/lib/test_rubric_overrides_suffix.py``). It pins:

- the canonical ``anvil.lib.inventorship_evidence`` dotted import path,
- that no stale skill-local copy lingers at the old path,
- that the file-path-load identity (``importlib`` from
  ``anvil/lib/inventorship_evidence.py``) re-exports the same objects as the
  dotted import — the surface ``inventorship_interview.py`` relies on,
- that the command prose + ``ip-uspto/lib/__init__.py`` docstring point at
  the promoted location, not the retired skill-local path.

The full behavioral corpus (git-fixture mining, exit codes, append-only
semantics) continues to run against the promoted location from
``anvil/skills/ip-uspto/tests/test_ip_uspto_inventorship_evidence.py``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import anvil.lib.inventorship_evidence as canonical


_REPO_ROOT = Path(__file__).resolve().parents[2]
_CANONICAL_FILE = _REPO_ROOT / "anvil" / "lib" / "inventorship_evidence.py"
_OLD_SKILL_LOCAL_FILE = (
    _REPO_ROOT / "anvil" / "skills" / "ip-uspto" / "lib" / "inventorship_evidence.py"
)


# ---------------------------------------------------------------------------
# Canonical location (promotion landed)
# ---------------------------------------------------------------------------


def test_canonical_import_path_resolves() -> None:
    # The promoted module is importable via the dotted ``anvil.lib`` path.
    assert hasattr(canonical, "is_vendored_path")
    assert hasattr(canonical, "collect_evidence") or hasattr(canonical, "main")
    assert canonical.CLASSIFICATIONS == (
        "conception",
        "implementation",
        "mixed",
        "unclassified",
    )


def test_module_lives_at_promoted_path() -> None:
    assert _CANONICAL_FILE.is_file()
    # The module actually loaded from ``anvil/lib/``.
    assert Path(canonical.__file__).resolve() == _CANONICAL_FILE


def test_no_stale_skill_local_copy() -> None:
    # The move is a relocation, not a fork: the old skill-local file must be
    # gone so there is exactly one source of truth.
    assert not _OLD_SKILL_LOCAL_FILE.exists()


def test_promoted_module_stays_consumer_agnostic() -> None:
    # The promotion boundary: still stdlib-only, no anvil/pydantic imports
    # (inputs are repo_path + element->paths map; never BRIEF/claims).
    text = _CANONICAL_FILE.read_text(encoding="utf-8")
    for forbidden in ("import pydantic", "from anvil", "import anvil"):
        assert forbidden not in text, forbidden


# ---------------------------------------------------------------------------
# File-path-load identity (the surface inventorship_interview.py relies on)
# ---------------------------------------------------------------------------


def _load_by_file_path():
    name = "_inventorship_evidence_filepath_identity"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _CANONICAL_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_file_path_load_matches_dotted_import() -> None:
    by_path = _load_by_file_path()
    # Same constants / callables whether loaded by dotted import or file
    # path — the file-path invocation is the documented back-compat surface.
    assert by_path.CLASSIFICATIONS == canonical.CLASSIFICATIONS
    assert by_path.ROLES == canonical.ROLES
    assert by_path.VENDOR_FILE_THRESHOLD == canonical.VENDOR_FILE_THRESHOLD
    assert by_path.is_vendored_path("vendor/x.py", ["vendor/"]) is True
    assert by_path.is_vendored_path("src/app.py", ["vendor/"]) is False


def test_interview_module_loads_is_vendored_path_from_promoted_location() -> None:
    # ``ip-uspto``'s interview module loads ``is_vendored_path`` via importlib
    # from the promoted file path. Loading it must succeed (a broken file path
    # would crash at import) and re-export the helper.
    interview_file = (
        _REPO_ROOT
        / "anvil"
        / "skills"
        / "ip-uspto"
        / "lib"
        / "inventorship_interview.py"
    )
    name = "_inventorship_interview_promotion_check"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, interview_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    assert module.is_vendored_path is not None
    assert module.is_vendored_path("vendor/x.py", ["vendor/"]) is True


# ---------------------------------------------------------------------------
# Prose / docstring back-compat surface points at the promoted path
# ---------------------------------------------------------------------------


def test_command_prose_invokes_promoted_path() -> None:
    cmd = (
        _REPO_ROOT
        / "anvil"
        / "skills"
        / "ip-uspto"
        / "commands"
        / "ip-uspto-inventorship.md"
    ).read_text(encoding="utf-8")
    assert "anvil/lib/inventorship_evidence.py" in cmd
    # The retired skill-local invocation path is gone from command prose.
    assert "anvil/skills/ip-uspto/lib/inventorship_evidence.py" not in cmd


def test_ip_uspto_lib_init_documents_promotion() -> None:
    init = (
        _REPO_ROOT
        / "anvil"
        / "skills"
        / "ip-uspto"
        / "lib"
        / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "anvil/lib/inventorship_evidence.py" in init
    assert "#516" in init
