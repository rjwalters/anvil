"""Regression armor: ``anvil.lib`` must be importable from a fresh install.

Why this test exists
--------------------

``anvil/lib/__init__.py`` eagerly re-exports symbols from ``cite``,
``convergence``, and ``rubric``. Several of those modules (notably
``cite`` and ``review_schema``) depend on ``pydantic``. If ``pydantic``
ever drops out of ``[project] dependencies`` in ``pyproject.toml``, or if
``anvil/lib/__init__.py`` later adds eager imports of modules with
undeclared third-party dependencies, this test fails immediately.

The test will of course pass on any dev environment that already has
``pydantic`` installed (which is essentially all of them — see issue
#106). The real value is documenting the contract: **``anvil.lib`` must
be importable using only what ``pyproject.toml`` declares, with no
ambient third-party Python packages**. The fail mode the test guards
against is the silent regression where a base-dep package is removed
from ``pyproject.toml`` (or never added in the first place) and tests
stay green because the dev venv happens to have it transitively.

If you find yourself wanting to relax this test, the right move is
instead to make the offending import lazy in ``anvil/lib/__init__.py``
or to add the missing dep to ``[project] dependencies``.

Related: issue #106 (the bug this test was born to prevent recurring).
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
