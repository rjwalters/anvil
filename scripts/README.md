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
2. Copy `anvil/skills/<selected>/` to `<target>/.claude/skills/anvil-<selected>/` (or similar — see open question below)
3. Copy `anvil/roles/` to `<target>/.anvil/roles/`
4. Append an Anvil section to `<target>/CLAUDE.md` (does not overwrite — coexists with any existing Loom section)
5. Skip files the consumer has overridden (override path: `<target>/.anvil/skills/<name>/` shadows the anvil-shipped version)

Open question: skill namespacing on install. Options:
- `.claude/skills/anvil-ip-uspto/` (flat, prefixed name)
- `.claude/skills/anvil/ip-uspto/` (nested)
- `.anvil/skills/ip-uspto/` + claude-side registration via a manifest

To be decided alongside the first install.
