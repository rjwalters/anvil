"""Regression armor: ``anvil.lib`` must be importable from a fresh install.

Why this test exists
--------------------

``anvil/lib/__init__.py`` eagerly re-exports symbols from ``cite``,
``convergence``, and ``rubric``. Several of those modules depend on
third-party libraries declared as base ``[project] dependencies`` in
``pyproject.toml``:

- ``cite`` and ``review_schema`` (and downstream consumers ``critics``,
  ``vision``) depend on ``pydantic``.
- ``rubric`` does a top-level ``import yaml`` (PyYAML) — the rubric
  loader calls ``yaml.safe_load``. Because ``anvil/lib/__init__.py``
  re-exports ``Rubric`` / ``load_rubric`` / ``discover_venue_rubric``,
  any ``from anvil.lib import ...`` (and anything downstream like
  ``anvil.lib.render_gate``) transitively requires yaml at import time.

If any of these base deps drops out of ``[project] dependencies`` in
``pyproject.toml``, or if ``anvil/lib/__init__.py`` later adds eager
imports of modules with undeclared third-party dependencies, this test
fails immediately.

The test will of course pass on any dev environment that already has the
base deps installed (which is essentially all of them — see issue #106
for pydantic and issue #231 for pyyaml). The real value is documenting
the contract: **``anvil.lib`` must be importable using only what
``pyproject.toml`` declares, with no ambient third-party Python
packages**. The fail mode the test guards against is the silent
regression where a base-dep package is removed from ``pyproject.toml``
(or never added in the first place) and tests stay green because the
dev venv happens to have it transitively.

If you find yourself wanting to relax this test, the right move is
instead to make the offending import lazy in ``anvil/lib/__init__.py``
or to add the missing dep to ``[project] dependencies``.

Related: issue #106 (the pydantic precedent), issue #231 (pyyaml — the
canary reproducer that exposed the missing base-dep declaration).
"""

from __future__ import annotations

import subprocess
import sys


def test_anvil_lib_imports_cleanly() -> None:
    """``import anvil.lib`` must succeed.

    Imports the whole package (not a submodule) so that the eager
    re-exports in ``anvil/lib/__init__.py`` are exercised. If any of
    those re-exports pull in an undeclared third-party dep, this raises
    ``ModuleNotFoundError`` at import time and the test fails.
    """
    import anvil.lib  # noqa: F401  (import-for-side-effect is the point)

    # Spot-check that a few of the eagerly-exported names are actually
    # present. This catches the rarer regression where the package
    # import "succeeds" because somebody silently dropped re-exports.
    assert hasattr(anvil.lib, "cite")
    assert hasattr(anvil.lib, "load_rubric")
    assert hasattr(anvil.lib, "decide_termination")


def test_anvil_lib_rubric_yaml_is_real_module() -> None:
    """``anvil.lib.rubric.yaml`` must be the real PyYAML module.

    Regression armor for issue #231: ``anvil/lib/rubric.py`` has a
    top-level ``import yaml`` (PyYAML's standard module name) and calls
    ``yaml.safe_load``. If ``pyyaml`` ever drops out of base deps —
    either by being removed from ``pyproject.toml`` or by the import
    being shadowed/replaced with a sentinel — this assertion catches it.

    The test imports ``anvil.lib.rubric`` (the loader module, not the
    package) and verifies the bound ``yaml`` symbol exposes the real
    PyYAML API surface (``safe_load`` is the contract the loader uses).
    A bare ``import yaml`` assertion would also pass on a venv that
    happens to have ``yaml`` ambiently installed without pyyaml being
    declared — checking the attribute on the *rubric module's* namespace
    catches the silent-shadowing case too.
    """
    from anvil.lib import rubric as rubric_module

    # The bound `yaml` symbol must be the real module exposing the
    # `safe_load` contract that `load_rubric` depends on.
    assert hasattr(rubric_module, "yaml"), (
        "anvil.lib.rubric.yaml symbol missing — the top-level "
        "`import yaml` in rubric.py was removed or shadowed."
    )
    assert callable(getattr(rubric_module.yaml, "safe_load", None)), (
        "anvil.lib.rubric.yaml does not expose callable safe_load — "
        "the bound `yaml` is not the real PyYAML module."
    )


def test_numeric_consistency_imports_cleanly() -> None:
    """``anvil.lib.numeric_consistency`` must import with base deps only.

    The numeric-consistency gate (issue #462) is pure stdlib plus the
    ``review_schema`` / ``sidecar`` lib siblings (pydantic is the lone
    base dep it touches transitively). If a third-party import ever
    sneaks into the module, this fails immediately.
    """
    import anvil.lib.numeric_consistency as nc

    assert callable(nc.check_numeric_consistency)
    assert callable(nc.check_text)
    assert callable(nc.write_review_dir)


def test_evidence_check_imports_cleanly() -> None:
    """``anvil.lib.evidence_check`` must import with base deps only.

    The quoted-evidence verifier (issue #464) is pure stdlib plus the
    ``critics`` lib sibling (pydantic is the lone base dep it touches
    transitively via ``review_schema``). If a third-party import ever
    sneaks into the module, this fails immediately.
    """
    import anvil.lib.evidence_check as ec

    assert callable(ec.check_version_dir)
    assert callable(ec.check_scoring_text)
    assert callable(ec.classify_justification)


def test_tex_includes_imports_cleanly() -> None:
    r"""``anvil.lib.tex_includes`` must import with base deps only.

    The ``\input``/``\include`` resolver (issue #643) is pure stdlib —
    no third-party imports. If one ever sneaks in, this fails immediately.
    """
    import anvil.lib.tex_includes as ti

    assert callable(ti.resolve_tex_inputs)
    assert hasattr(ti, "ResolvedTex")


def test_sidecar_dash_m_invocation_is_warning_free() -> None:
    """``python -m anvil.lib.sidecar`` must not emit a ``RuntimeWarning``.

    Regression armor for issue #673. When ``anvil/lib/__init__.py`` eagerly
    ran ``from anvil.lib.sidecar import (...)``, the submodule was registered
    in ``sys.modules`` during package init, so ``runpy`` warned on every
    ``python -m anvil.lib.sidecar`` invocation::

        <frozen runpy>:130: RuntimeWarning: 'anvil.lib.sidecar' found in
        sys.modules after import of package 'anvil.lib', but prior to
        execution of 'anvil.lib.sidecar'; this may result in unpredictable
        behaviour

    The fix makes the re-export lazy via a PEP 562 ``__getattr__`` so the
    submodule stays out of ``sys.modules`` until first attribute access.

    This test runs the ``-m`` shim in a fresh interpreter with
    ``-W error::RuntimeWarning`` so any re-introduced eager sidecar import
    turns the warning into a non-zero exit, and additionally asserts the
    warning text is absent from stderr regardless of exit code.
    """
    proc = subprocess.run(
        [sys.executable, "-W", "error::RuntimeWarning", "-m", "anvil.lib.sidecar", "--help"],
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, (
        "`python -W error::RuntimeWarning -m anvil.lib.sidecar --help` exited "
        f"{proc.returncode} — a RuntimeWarning was likely raised as an error.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "RuntimeWarning" not in proc.stderr, (
        "`python -m anvil.lib.sidecar` emitted a RuntimeWarning on stderr — "
        "an eager `from anvil.lib.sidecar import ...` was likely reintroduced "
        f"in anvil/lib/__init__.py.\nstderr:\n{proc.stderr}"
    )
    assert "found in sys.modules" not in proc.stderr


def test_sidecar_reexports_are_lazy_and_correct() -> None:
    """The sidecar re-exports resolve lazily but identically to the source.

    ``from anvil.lib import staged_sidecar`` (and the other five names) must
    return the *same objects* as ``from anvil.lib.sidecar import ...``, and
    an unrelated unknown attribute must raise a normal ``AttributeError``
    (not silently return ``None``) so ``hasattr()`` / static analysis behave.
    """
    import anvil.lib
    import anvil.lib.sidecar as sidecar_mod

    for name in (
        "STAGING_SUFFIX",
        "SidecarIncompleteError",
        "cleanup_one_staging",
        "cleanup_stale_staging",
        "staged_sidecar",
        "staging_path_for",
    ):
        assert getattr(anvil.lib, name) is getattr(sidecar_mod, name), (
            f"anvil.lib.{name} is not the same object as anvil.lib.sidecar.{name}"
        )
        assert name in anvil.lib.__all__

    try:
        anvil.lib.definitely_not_a_real_attribute  # type: ignore[attr-defined]
    except AttributeError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError(
            "anvil.lib.__getattr__ did not raise AttributeError for an "
            "unknown attribute name"
        )
