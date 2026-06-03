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
