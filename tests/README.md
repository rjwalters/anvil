# tests/

Framework-level test suite. Per-skill tests also live alongside each skill
at `anvil/skills/<skill>/tests/`; the packages here cover the shared
framework surfaces:

```
tests/
  lib/       Framework primitives (review_schema, critics, convergence,
             cite, rubric, render, render_gate, vision, figures, imports).
  scripts/   Install-script + version-drift regression tests
             (install-anvil.sh quoting, dry-run honesty, --skills=
             validation, version.sh drift check).
  agents/    Agent-registry tests (generate-anvil-agents.py idempotence,
             frontmatter schema, tool scope by role, installer wiring).
  skills/    Per-skill test packages, one directory per skill (fixtures +
             regression tests that need the repo-level import path).
```

Run everything from the repo root:

```bash
pytest tests/
```

Every test directory carries an `__init__.py`: per-skill test files use
distinct filenames (the #58 packaging convention), and the `__init__.py`
chains are what keep same-named modules from colliding under pytest.
