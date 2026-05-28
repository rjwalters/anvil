# scripts/

Operational scripts for anvil maintenance and installation.

## Scripts

| Script | Status | Purpose |
|---|---|---|
| `version.sh` | working | Show / check / set the anvil version across all version-bearing files |
| `install-anvil.sh` | planned | Install anvil into a consumer repo (`./install-anvil.sh /path/to/repo`) |
| `new-skill.sh` | planned | Scaffold a new skill from `anvil/templates/` |

## Install design (planned)

`install-anvil.sh <target-repo>` will:

1. Copy `anvil/lib/` to `<target>/.anvil/lib/`
2. Copy `anvil/skills/<selected>/` to `<target>/.anvil/skills/<selected>/` (canonical location)
3. Create thin Claude registration files at `<target>/.claude/skills/anvil/<selected>/SKILL.md` that point to the canonical location
4. Copy `anvil/roles/` to `<target>/.anvil/roles/`
5. Append an Anvil section to `<target>/CLAUDE.md` (does not overwrite — coexists with any existing Loom section)
6. Skip files the consumer has overridden (override path: `<target>/.anvil/skills/<name>/` shadows the anvil-shipped version)

### Install layout convention (resolved per issue #1)

Anvil-shipped skills land at `.anvil/skills/<name>/` (canonical bodies) with thin registration at `.claude/skills/anvil/<name>/SKILL.md`. This mirrors Loom's `.loom/` separation between framework code and Claude registration, and preserves the override semantics above. See issue #1 for the curator analysis.
