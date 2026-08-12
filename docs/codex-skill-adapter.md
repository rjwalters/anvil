# Codex CLI skill/plugin discovery contract — verified findings

Research spike for #1002 (parent epic #1000, blocks phase 2 implementation
#1003). No runtime code changes. Every claim below cites a specific,
checkable source: an installed-binary command, a live-host filesystem probe
(from the issue's own curator research), or an official
`developers.openai.com` / `github.com/openai/codex` URL fetched during this
spike (2026-08-12).

## 0. Environment check (AC1)

- **This Builder's sandbox does not have a `codex` CLI installed.** `which
  codex`, `codex --version`, and `codex --help` all returned `command not
  found`; `~/.codex/` does not exist. Checked 2026-08-12.
- The issue's own curator research **did** verify a live install on a
  *different* host in this same organization's environment:
  `codex-cli 0.46.0`, confirmed via `codex --version` / `codex --help` /
  `find ~/.codex/skills` / `find ~/.codex/plugins` (see the issue body's
  "Verified corrections" section, dated 2026-08-12). That finding is not
  independently reproducible from this sandbox, so this document treats it
  as corroborating evidence rather than primary evidence, and leans on the
  official docs (§1–§4 below) as primary source. The official-docs content
  is consistent with every filesystem-level claim the curator made from the
  live host (SKILL.md frontmatter shape, `.codex-plugin/plugin.json` path,
  the `"skills"` manifest field) — see the cross-checks inline below.

## 1. Skill directory layout and `SKILL.md` frontmatter contract (AC2, AC3)

Primary source: **`https://developers.openai.com/codex/build-skills`**
(redirects `308` to `https://learn.chatgpt.com/docs/build-skills` — confirmed
via `curl -s -L -o /dev/null -w '%{url_effective} %{http_code}'`, 2026-08-12;
canonical markdown fetched via the documented `.md`-suffix convention at
`https://developers.openai.com/codex/build-skills.md`, HTTP 200, 2026-08-12).

> "A skill is a directory with a `SKILL.md` file plus optional scripts and
> references. The `SKILL.md` file must include `name` and `description`."

Directory shape documented on that page:

```
my-skill/
├── SKILL.md       Required: instructions + metadata
├── scripts/       Optional: executable code
├── references/    Optional: documentation
├── assets/        Optional: templates, resources
└── agents/
    └── openai.yaml  Optional: appearance and dependencies
```

**Verdict on AC3**: Codex's minimal `SKILL.md` frontmatter contract
(`name` + `description`, YAML frontmatter block) is **identical** to Claude
Code's. This matches the curator's live-host finding
(`~/.codex/skills/.system/skill-creator/SKILL.md` frontmatter was
`name` + `description` + optional `metadata:`). Codex additionally supports
an *optional*, skill-local `agents/openai.yaml` for richer metadata (UI
display name/icon/color, `default_prompt`, `policy.allow_implicit_invocation`,
and tool `dependencies`) — none of it required for discovery or for the
minimal frontmatter contract to match Claude's.

## 2. Where Codex scans for skills — repo-local path is `.agents/skills/`, NOT `.codex/skills/` (AC2)

Same source (`build-skills`), section "Where Codex loads local skills":

> "Codex reads skills from repository, user, admin, and system locations.
> For repositories, Codex scans `.agents/skills` in every directory from your
> current working directory up to the repository root."

| Scope | Location | Notes |
|---|---|---|
| `REPO` | `$CWD/.agents/skills` | where you launch Codex |
| `REPO` | `$CWD/../.agents/skills` (repeated up to repo root) | shared-parent-folder skills |
| `REPO` | `$REPO_ROOT/.agents/skills` | root skills for the whole repo |
| `USER` | `$HOME/.agents/skills` | per-user, cross-repo |
| `ADMIN` | `/etc/codex/skills` | machine/container-wide |
| `SYSTEM` | bundled with Codex | e.g. `skill-creator` |

Symlinked skill folders are followed. If two skills share a `name`, Codex
does **not** merge them — both appear in the selector.

**This directly refutes the original issue's blog-sourced hypothesis**
(`.codex/skills/<name>/SKILL.md`) **and confirms** the curator's
WebSearch-sourced correction from upstream issue #16012, which named the
repo-local convention as `.agents/skills/<name>/SKILL.md`. The official docs
are unambiguous and dated as current (fetched live 2026-08-12): **the
repo-local, Anvil-relevant path is `.agents/skills/<name>/SKILL.md` at the
repo root** (the `REPO` / `$REPO_ROOT/.agents/skills` row above is the one
that matters for an installer writing a fixed path once at repo root, since
Anvil consumers won't reliably invoke `codex` from a specific subdirectory).

**Global/personal locations use the identical `.agents/skills` shape**, not a
`.codex`-namespaced one: `$HOME/.agents/skills`. `~/.codex/` is reserved for
Codex's own home-directory config/state (`config.toml`, `AGENTS.md`,
`AGENTS.override.md`, the bundled skill/plugin cache) — it is not itself a
skill-scan root in the documented contract, even though the curator observed
populated `~/.codex/skills/` and `~/.codex/plugins/` directories on the live
host. (Those live-host directories are consistent with being Codex's
*resolved/cached* skill and plugin state — the `SYSTEM` and registry-sourced
`plugin` entries the docs describe — rather than a second author-facing
scan root that competes with `.agents/skills`. The docs never document
`~/.codex/skills/` as an authoring location; `$HOME/.agents/skills` is the
documented `USER`-scope authoring path.)

## 3. No wrapping plugin manifest is required for skill discovery (AC4)

Same source, section "Distribute skills with plugins":

> "Direct skill folders are best for local authoring and repo-scoped
> workflows. If you want to distribute a reusable skill, bundle two or more
> skills together, or ship a skill alongside a connector, package them as a
> plugin."

A bare `<scope>/.agents/skills/<name>/SKILL.md` is independently discovered
by the scan described in §2 — **no `plugin.json`/`.codex-plugin/plugin.json`
is required** for a skill to be discoverable. Plugins are an orthogonal,
optional **distribution** mechanism (installable via ChatGPT's/Codex's shared
plugin directory or a local marketplace), not a discovery prerequisite.

When a plugin *is* used, the manifest shape confirmed by both the official
docs (**`https://developers.openai.com/codex/build-plugins`**, redirects
`308` to `https://learn.chatgpt.com/docs/build-plugins`; `.md` fetched
2026-08-12) and the curator's live-host finding
(`~/.codex/plugins/cache/openai-bundled/visualize/1.0.15/.codex-plugin/plugin.json`)
agree exactly:

```
meeting-follow-up/
├── .codex-plugin/
│   └── plugin.json
└── skills/
    └── meeting-follow-up/
        └── SKILL.md
```

```json
{
  "name": "meeting-follow-up",
  "version": "1.0.0",
  "description": "Turn meeting notes into decisions and next steps",
  "skills": "./skills/"
}
```

The manifest lives at `.codex-plugin/plugin.json` (dot-prefixed subdirectory,
**not** a bare `plugin.json` at the plugin root) — confirming the curator's
correction of the original blog-sourced hypothesis. The richer `interface`
block (`display_name`, `icon_small`/`icon_large`, `brand_color`,
`default_prompt`, `policy`, `dependencies`) the curator saw on the bundled
`openai-bundled/visualize` plugin is documented as **optional
marketplace/UI metadata**, not a minimal-manifest requirement — the docs'
own "minimal plugin" example above omits all of it.

**Verdict on AC4**: a wrapping plugin manifest is required only if Anvil
wants its skills to be *installable/distributable* through Codex's shared
plugin directory or a local marketplace. It is **not** required for a
consumer repo's own `.agents/skills/<name>/SKILL.md` to be discovered by
Codex running inside that repo — which is the adapter's actual job
(register skills that already live in the consumer's checkout, the same way
`write_shim()` registers the Claude shim today).

## 4. `AGENTS.md` is a separate, always-on surface from skill/plugin discovery (AC5)

Primary source: **`https://developers.openai.com/codex/agent-configuration/agents-md`**
(redirects `308` to
`https://learn.chatgpt.com/docs/agent-configuration/agents-md`; `.md` fetched
2026-08-12).

> "Codex reads `AGENTS.md` files before doing any work."

Discovery precedence (distinct algorithm from the skill scan in §2):

1. **Global scope**: `$CODEX_HOME` (default `~/.codex`) — `AGENTS.override.md`
   if present, else `AGENTS.md`. Only the first non-empty file at this level.
2. **Project scope**: walks from the project root (typically the Git root)
   *down* to the current working directory, checking each directory for
   `AGENTS.override.md`, then `AGENTS.md`, then any
   `project_doc_fallback_filenames` entries — at most one file per directory.
3. **Merge order**: concatenated root-down, joined by blank lines; files
   closer to CWD win (they appear later in the combined prompt).
4. Bounded by `project_doc_max_bytes` (32 KiB default).

**Verdict on AC5**: yes — `AGENTS.md` is Codex's only always-on
repo-instruction surface, directly analogous to Claude's root `CLAUDE.md`.
It is populated by an entirely separate discovery pass (directory-walk +
concatenation, no frontmatter, no `name`/`description`) from the skill/plugin
catalog described in §1–§3. Registering an Anvil skill for Codex does **not**
touch `AGENTS.md` content, and conversely nothing in the skill-discovery
contract reads `AGENTS.md`.

## 5. Re-checking the four cited upstream issues (2026-08-12)

The issue body flagged repo-local skill discovery as "actively unsettled
upstream" based on four `openai/codex` issues, with an explicit instruction
to re-check their current state before acting on that framing. Re-checked via
`gh api repos/openai/codex/issues/<n>` on 2026-08-12:

| # | Title | State | Notes |
|---|---|---|---|
| [#22869](https://github.com/openai/codex/issues/22869) | Support project-scoped **personal** skill discovery directories | **open** | Filed 2026-05-15. Its own body already *assumes* `.agents/skills` (both `~/.agents/skills` and "project-local locations") as the existing, shipped mechanism, and requests a narrower addition: a way to point Codex at a **private, uncommitted** directory of personal skills scoped to one project (`[[skills.dir]]`-style config). This is a feature request layered on top of the documented `.agents/skills` contract, not a dispute of it. |
| [#21907](https://github.com/openai/codex/issues/21907) | Support project-level skills discovery from repository workspace | **open** | Filed 2026-05-09 — predates or is unaware of the now-documented `.agents/skills` mechanism (its body proposes `<repo>/.codex/skills/` or `<repo>/.agent/skills/` as candidate paths, i.e. it's asking for the feature the docs now describe as already shipped). Still open; likely stale relative to the shipped `.agents/skills` contract rather than evidence against it, but not confirmed superseded/closed by OpenAI as of this check. |
| [#19672](https://github.com/openai/codex/issues/19672) | Feature request: lazy discovery of nested project skills | **open** | A performance/UX refinement request (avoid eagerly walking every nested dir), not a challenge to the discovery path itself. |
| [#16012](https://github.com/openai/codex/issues/16012) | Repo-local `.agents/skills` skill is not injected into session | **closed** (`state_reason: completed`), closed 2026-03-27 | **Correction to the issue body's framing**: this was closed by the *reporter*, not by a landed PR — thread shows the root cause was the reporter's own bad nested symlink ("Nevermind. It was a bad nested symlink I failed to check deeper in the folder structure."). It is not evidence the `.agents/skills` mechanism was broken-then-fixed; if anything the thread confirms `.agents/skills` was already the real, working mechanism in March 2026 (five months before this spike), consistent with §2 above. |

**Net correction to the issue body**: repo-local skill discovery is **not**
"actively unsettled" as a *contract* — `https://developers.openai.com/codex/build-skills`
documents a specific, dated-current `.agents/skills` scan path in detail (§2).
What *is* genuinely unsettled, per the still-open issues above, are two
narrower things: (a) reliability of the discovery/catalog-injection pipeline
under load (a related, closed-as-duplicate issue,
[#32679](https://github.com/openai/codex/issues/32679), reported valid
`.agents/skills` symlinks being silently omitted from a session's catalog on
Codex CLI 0.144.1 — worth a defensive note for #1003, not a blocker), and
(b) whether *private, uncommitted, project-scoped* personal skill dirs
outside `.agents/skills` will ever be supported (#22869) — not a concern for
Anvil, which always wants its skills committed and repo-visible.

## 6. Recommendation for `install-anvil.sh` (AC6)

`write_shim()` (in `scripts/install-anvil.sh`) currently writes one Claude
registration shim per installed skill at
`<target>/.claude/skills/anvil-<name>/SKILL.md`, pointing back at the
canonical body under `.anvil/skills/<name>/SKILL.md`. The Codex-native
counterpart implementation (tracked separately in #1003) should mirror that
shape using the verified contract above:

1. **Emit a thin per-skill registration file at
   `<target>/.agents/skills/anvil-<name>/SKILL.md`** — same naming
   (`anvil-<name>`) and same thin-shim content pattern as the Claude shim
   (frontmatter `name`/`description` pointing at the canonical body, one-line
   pointer to `.anvil/skills/<name>/SKILL.md`). This is independently
   discoverable by Codex with **no plugin manifest** (§3), matching how the
   Claude shim needs no wrapping manifest either — the two adapters can share
   the same "thin pointer, canonical body stays under `.anvil/`" design.
2. **Do not target `.codex/skills/`** — that path is not part of the
   documented contract (§2); only `.agents/skills/` is scanned.
3. **Do not emit a `.codex-plugin/plugin.json`** in the v1 adapter. Nothing
   in the discovery contract requires it (§3), and a plugin only becomes
   relevant if Anvil later wants push-button installability through Codex's
   shared plugin directory/local marketplace — a distribution decision
   orthogonal to "does Codex see the skill when it's already in my repo,"
   which is all the current adapter epic (#1000) is scoped to solve. If a
   plugin-distribution path is wanted later, it is additive (a new,
   separate manifest + `skills/` tree), not a rework of the v1 adapter.
4. **Leave `AGENTS.md` alone.** It is a wholly separate mechanism (§4) from
   skill registration; the installer's existing `write_guide()` path (which
   writes Anvil's guide content into `.anvil/CLAUDE.md`, consumed by Claude's
   CLAUDE.md-inclusion convention) has no Codex analog to wire up as part of
   *skill* registration — if Anvil ever wants Codex to pick up its guide
   content automatically, that is a distinct, separately-scoped question
   about whether/how to also touch the consumer's root `AGENTS.md`, not
   something #1003 needs to solve.
5. **Uninstall/upgrade symmetry**: whatever cleanup/upgrade logic
   `write_shim()`'s Claude path already has (skip-if-consumer-modified,
   removal on `--uninstall`, etc.) should apply identically to the new
   `.agents/skills/anvil-<name>/` shim path — the two are structurally the
   same kind of thin, regeneratable pointer file.
6. **Defensive note for #1003's test plan**: given §5's `#32679` (skills
   silently dropped from very large repo-scoped catalogs under a context
   budget), if a consumer has many Anvil skills installed, do not assume
   Codex will surface every one of them in the initial catalog — that's a
   Codex-side reliability gap, not something the adapter can fix, but #1003
   should note it rather than be surprised by a flaky manual-verification
   test.

## Sources cited

- `https://developers.openai.com/codex/build-skills` (→ `learn.chatgpt.com/docs/build-skills`), fetched 2026-08-12.
- `https://developers.openai.com/codex/build-plugins` (→ `learn.chatgpt.com/docs/build-plugins`), fetched 2026-08-12.
- `https://developers.openai.com/codex/agent-configuration/agents-md` (→ `learn.chatgpt.com/docs/agent-configuration/agents-md`), fetched 2026-08-12.
- `gh api repos/openai/codex/issues/{22869,21907,19672,16012,32679}`, checked 2026-08-12.
- Issue #1002 body, "Verified corrections" section (curator's live-host `codex-cli 0.46.0` findings, 2026-08-12) — corroborating, not primary, per §0.
- This Builder's own sandbox: `which codex` / `codex --version` / `codex --help` / `ls ~/.codex` — all absent, checked 2026-08-12 (documented in §0 as a negative result, not used as evidence either way).
