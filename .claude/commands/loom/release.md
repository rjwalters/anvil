# Release Manager

You are preparing a release of **Anvil** from the {{workspace}} repository.

## Overview

This skill guides a careful, interactive release process. Every release must:
1. Verify CI is green on main (when CI exists; anvil has none today — see Phase 1)
2. Analyze what changed since the last release
3. Help the user decide the correct semver bump
4. Draft and refine the CHANGELOG entry
5. Update version across both version-bearing files (`CLAUDE.md`, `pyproject.toml`)
6. Commit, tag, and (with confirmation) push
7. Create a GitHub Release with the CHANGELOG entry as the release notes

**Do not rush. Each phase requires user confirmation before proceeding.**

## Phase 1: Pre-flight Checks

Before starting, verify the release is safe to cut:

```bash
# Check CI status on main
gh run list --branch main --limit 5 --json name,conclusion --jq '.[] | "\(.name): \(.conclusion)"'

# Check for open PRs that might need to land first
gh pr list --state open --json number,title --jq '.[] | "#\(.number) \(.title)"'

# Check for uncommitted changes
git status

# Verify the two version-bearing files agree before starting
./scripts/version.sh check
```

Present findings to the user. If CI is failing, stop and fix first. If there are open PRs, ask if they should land before the release. If `./scripts/version.sh check` reports drift, stop and resolve before proceeding (the release flow assumes a clean starting point).

**Note on CI**: anvil has no `.github/workflows/` today, so `gh run list --branch main` will return empty. That is expected and not a failure — the phase still serves as a "user is intentionally cutting from clean main" gate. Proceed if `git status`, the open-PR list, and `./scripts/version.sh check` all look clean.

## Phase 2: Gather Changes

```bash
# Find the last release tag
git tag --sort=-v:refname | head -1

# Show current version
./scripts/version.sh

# List all commits since that tag
git log <last-tag>..HEAD --oneline

# Show the full diff stats
git diff <last-tag>..HEAD --stat
```

Present the user with:
- **Last release**: tag name, date, and version
- **Commits since release**: count and full list
- **Change summary**: categorized by conventional commit prefix (feat, fix, refactor, docs, test, chore)
- **Files changed**: high-level summary of which subsystems were touched (anvil's commits typically scope by skill or by lib primitive, e.g. `feat(deck):`, `fix(lib/critics):`)

If there are zero commits since the last tag, stop and tell the user there's nothing to release.

## Phase 3: Semver Decision

Present a semver analysis. Reference https://semver.org:

### Breaking Changes (MAJOR bump)
Scan for:
- Removed or renamed a public skill (e.g., `anvil:memo`, `anvil:deck`, `anvil:ip-uspto`) — consumers' invocations break
- Changed `_progress.json` schema in a way old version directories can't be read
- Removed or renamed a lib primitive consumers import directly (`anvil.lib.critics`, `anvil.lib.review_schema`, `anvil.lib.figures`)
- Changed the `SKILL.md` frontmatter contract (`name`, `description`, `domain`, `type`, `user-invocable`) so existing skills no longer load
- Changed `_review.json` schema in a backwards-incompatible way

### New Capabilities (MINOR bump)
- New skill added to the catalog (e.g., a new `anvil:<type>`)
- New lib primitive (`anvil/lib/<new-module>.py`)
- New optional extra in `pyproject.toml` (`[project.optional-dependencies]`)
- New shared snippet under `anvil/lib/snippets/`
- New role under `anvil/roles/`

### Bug Fixes / Internal (PATCH bump)
- Bug fixes inside an existing skill that don't change the public contract
- Prompt or rubric wording edits inside a `SKILL.md`
- Documentation updates (README, CLAUDE.md, snippet text)
- Internal refactoring with no API surface change
- Dependency bumps (lower-bound pin adjustments in `pyproject.toml` extras)

Present your recommendation and **ask the user to confirm or override**. Do not proceed until confirmed. You will need the explicit `X.Y.Z` string for Phase 5.

## Phase 4: Draft CHANGELOG

Draft a CHANGELOG entry following the existing format in `CHANGELOG.md`. Study existing entries to match style.

Anvil's `CHANGELOG.md` today contains only the bootstrap `## [Unreleased]` entry (`Added` / `Status` / `Next`). The first real released entry (e.g. `## [0.1.0] - YYYY-MM-DD`) sets the template for everything after it — pay it extra attention.

Key formatting rules:
- Use `## [X.Y.Z] - YYYY-MM-DD` header with today's date
- Start with a `### Summary` paragraph describing the release theme
- Group changes under `### Added`, `### Changed`, `### Fixed`, `### Removed`, `### Renamed` as appropriate
- Reference issue numbers with `(#NNN)` format
- Keep descriptions concise but informative
- Omit empty sections

Present the draft and ask for revisions. Iterate until approved.

## Phase 5: Apply Changes

Once the user approves, apply both the CHANGELOG and the version bump as a single combined release commit, then tag.

Let `<X.Y.Z>` be the explicit version confirmed in Phase 3.

1. **Update `CHANGELOG.md`**: insert the new entry directly below `## [Unreleased]`.
2. **Bump version across both files**:
   ```bash
   ./scripts/version.sh set <X.Y.Z>
   ```
   This rewrites the `Anvil Version` line in `CLAUDE.md` AND the `version = "..."` line in `pyproject.toml` in one shot.
3. **Verify both files now agree at the new version**:
   ```bash
   ./scripts/version.sh check
   ```
   Must exit 0 and print both files at `<X.Y.Z>`.
4. **Commit CHANGELOG + version bump together**:
   ```bash
   git add CHANGELOG.md CLAUDE.md pyproject.toml
   git commit -m "chore: release v<X.Y.Z>"
   ```
5. **Tag**:
   ```bash
   git tag v<X.Y.Z>
   ```

Show the user the resulting commit (`git show HEAD`) and tag (`git tag --list v<X.Y.Z>`) and ask for final confirmation before pushing.

## Phase 6: Push and Release

After final confirmation:

1. **Push commits and tag**:
   ```bash
   git push origin main --tags
   ```

2. **Create the GitHub Release**:
   ```bash
   gh release create v<X.Y.Z> --title "v<X.Y.Z>" --notes-file - <<< "$(changelog excerpt)"
   ```
   Use the CHANGELOG entry as the release notes. This is the canonical announcement of the release; no build artifacts are attached today (anvil ships as source + skill catalog).

**Do not push or create the release without explicit user confirmation.**

## Phase 7: Post-Release Summary

Present a summary:

```
## Release Complete

- Version: v<X.Y.Z>
- Commit: <sha>
- Tag: v<X.Y.Z>
- GitHub Release: created
- CHANGELOG: updated with N items
- Version files: 2 files updated (CLAUDE.md, pyproject.toml)
```

## Important Notes

- **Version script is the single source of truth**: `scripts/version.sh` is the only supported way to bump versions. Never manually edit version numbers in `CLAUDE.md` or `pyproject.toml`; the two files MUST stay in sync and the script is the mechanism that guarantees it. The drift-guard test (`tests/scripts/test_version_drift.py`) backstops this in CI.
- **2 version-bearing files**: `CLAUDE.md` (the `**Anvil Version**:` line) and `pyproject.toml` (the top-level `[project]` `version = "..."` line). Both are updated atomically by `./scripts/version.sh set <X.Y.Z>`.
- **Conventional commits**: This project uses conventional commit prefixes (`feat:`, `fix:`, `chore:`, etc.), often scoped (`feat(deck):`, `fix(lib/critics):`).
- **Branch protection**: Direct pushes to main will show a ruleset bypass warning — this is expected for release commits.
- **Future build artifacts**: anvil has no GitHub Actions workflow today. When binaries or wheel artifacts are added in the future, extend Phase 6 to attach them to the GitHub Release (`gh release create ... <artifact-paths>`) and reintroduce a `Verify build triggered` step in Phase 6. The current flow assumes source-only distribution via the GitHub Release tag.
