#!/usr/bin/env bash
# check-surface-version-bump.sh - Fail a PR that changes Anvil's installed
# (consumer-visible) surface without either bumping VERSION or declaring an
# explicit no-surface-change marker (issue #1152).
#
# Why this exists: `scripts/install-anvil.sh` copies Anvil's skills, framework
# lib, templates, roles, and agents into every consumer's `.anvil/` +
# `.claude/` + `.agents/` trees at install time -- and NOTHING refreshes those
# copies afterwards short of re-running the installer or
# `.anvil/scripts/resync-installed.sh` (#894). The only mechanical signal a
# consumer has that its installed copies are behind is a VERSION comparison:
# `install-anvil.sh` reads `VERSION` at install time and records it in
# `.anvil/install-metadata.json`, and every downstream "am I current?" check
# (`/repo:update-tools`, fleet drift tooling) diffs against it.
#
# If a PR changes the installed surface without bumping VERSION, that signal
# silently lies. That is exactly the state this repo was in when #1152 was
# filed: `VERSION` read `0.11.0` while `main` was 61 commits past the `v0.11.0`
# tag, so every consumer reported "current" for changes it did not have. This
# is the same failure loom fixed with its `defaults/` gate (loom#5874), and the
# model this script copies: **VERSION on `main` is the release.** Tags and
# GitHub Releases stay manual and occasional; this gate says nothing about them.
#
# Why this is a NEW script rather than a call into the vendored
# `.loom/scripts/check-defaults-version-bump.sh`: that script hardcodes
# `defaults/` (loom's own installed-surface concept, which this repo does not
# have), and it is a vendored copy refreshed wholesale by
# `.loom/scripts/resync-installed.sh` -- an edit there survives until the next
# resync and then vanishes, the same reasoning CLAUDE.md already documents for
# the changelog-discipline and gh-since sections. Once
# `rjwalters/loom#6480` lands (watched paths as an argument), this script can
# become a thin wrapper over the vendored one; the CLI contract below is
# deliberately compatible with it so that swap is mechanical.
#
# This is deliberately NOT trying to force version inflation on every doc typo
# or test-only edit: an explicit marker lets an author declare "this change
# does not alter installed behavior" without a bump.
#
# Usage:
#   check-surface-version-bump.sh --base <ref> [--head <ref>]
#     --base <ref>   Git ref/sha to diff FROM (the PR's base commit, e.g. a
#                    fetched base sha, or origin/main for a local check).
#                    Required.
#     --head <ref>   Git ref/sha to diff TO. Defaults to HEAD.
#   check-surface-version-bump.sh --list-paths   # print the watched surface
#   check-surface-version-bump.sh --help
#
# No-surface-change marker: a PR whose body OR whose HEAD-reachable commit
# messages (between --base and --head) contain the literal string
#     <!-- loom:no-surface-change -->
# is exempt even when the surface changed and VERSION did not. Pass the PR body
# via the PR_BODY environment variable (GitHub Actions:
# `env: PR_BODY: ${{ github.event.pull_request.body }}`); the commit-message
# path needs no extra plumbing beyond --base/--head.
#
# Exit codes:
#   0 - nothing on the watched surface changed in the diff, OR VERSION was also
#       changed, OR the no-surface-change marker is present.
#   1 - the surface changed, VERSION was not bumped, and no marker is present.
#   2 - bad usage (missing/invalid --base or --head).

set -euo pipefail

MARKER='<!-- loom:no-surface-change -->'

# The consumer-visible surface, verified against `scripts/install-anvil.sh`:
#   anvil/lib/                    -> .anvil/anvil/lib/          (SRC_LIB)
#   anvil/skills/<name>/          -> .anvil/skills/<name>/      (per-skill loop)
#   anvil/templates/              -> theme + voice scaffolds    (SRC_STARTER_THEME,
#                                                                SRC_VOICE_DIR)
#   anvil/roles/                  -> .anvil/roles/              (SRC_ROLES, always
#                                                                installed)
#   anvil/agents/                 -> .claude/agents/anvil-*.md  (SRC_AGENTS)
#   anvil/__init__.py             -> .anvil/anvil/__init__.py   (SRC_ANVIL_INIT)
# so the whole `anvil/` tree is watched as one path rather than enumerating
# five siblings that would drift out of date the next time a stage is added.
#
#   scripts/install-anvil.sh      the installer itself: a behavior change here
#                                 changes what a fresh/updated install does even
#                                 when no file under anvil/ moved.
#   scripts/resync-installed.sh   physically copied to
#                                 .anvil/scripts/resync-installed.sh (Stage 8.7,
#                                 #894) -- an installed artifact in its own right.
SURFACE_PATHS=(
  "anvil/"
  "scripts/install-anvil.sh"
  "scripts/resync-installed.sh"
)

BASE=""
HEAD="HEAD"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      BASE="${2:-}"
      shift 2
      ;;
    --head)
      HEAD="${2:-}"
      shift 2
      ;;
    --list-paths)
      printf '%s\n' "${SURFACE_PATHS[@]}"
      exit 0
      ;;
    --help|-h)
      # Header block: lines 2..60 (through the exit-code table, stopping before
      # `set -euo pipefail`). Keep in sync if the preamble grows.
      sed -n '2,60p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "check-surface-version-bump: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$BASE" ]]; then
  echo "check-surface-version-bump: --base <ref> is required." >&2
  exit 2
fi

if ! git rev-parse --verify --quiet "${BASE}^{commit}" >/dev/null; then
  echo "check-surface-version-bump: base ref '$BASE' not found (not fetched?)." >&2
  exit 2
fi

if ! git rev-parse --verify --quiet "${HEAD}^{commit}" >/dev/null; then
  echo "check-surface-version-bump: head ref '$HEAD' not found." >&2
  exit 2
fi

# Deliberately a direct two-ref diff, not a merge-base-narrowed one -- this
# script is invoked from CI checkouts that may be shallow, where base and head
# histories need not share enough depth to resolve a merge-base. A direct diff
# answers the question this check actually cares about ("does applying head's
# changes touch the installed surface without touching VERSION") without
# requiring ancestry.
CHANGED_FILES="$(git diff --name-only "$BASE" "$HEAD" -- "${SURFACE_PATHS[@]}" 2>/dev/null || true)"

if [[ -z "$CHANGED_FILES" ]]; then
  echo "check-surface-version-bump: OK — no installed-surface changes in this diff."
  exit 0
fi

VERSION_CHANGED="$(git diff --name-only "$BASE" "$HEAD" -- VERSION 2>/dev/null || true)"

if [[ -n "$VERSION_CHANGED" ]]; then
  echo "check-surface-version-bump: OK — installed surface changed and VERSION was bumped."
  exit 0
fi

# --- no-surface-change marker check -----------------------------------------

if [[ -n "${PR_BODY:-}" ]] && grep -qF "$MARKER" <<<"$PR_BODY"; then
  echo "check-surface-version-bump: OK — no-surface-change marker found in the PR body."
  exit 0
fi

if git log --format=%B "${BASE}..${HEAD}" 2>/dev/null | grep -qF "$MARKER"; then
  echo "check-surface-version-bump: OK — no-surface-change marker found in a commit message."
  exit 0
fi

echo "check-surface-version-bump: FAIL — the installed surface changed without a VERSION bump:" >&2
echo "" >&2
while IFS= read -r changed; do
  echo "  $changed" >&2
done <<<"$CHANGED_FILES"
echo "" >&2
echo "These paths are copied into every consumer's .anvil/ (+ .claude/, .agents/)" >&2
echo "trees by scripts/install-anvil.sh and are NOT refreshed by a git pull." >&2
echo "VERSION is the only mechanical signal a consumer has that its installed" >&2
echo "copies are stale, so a surface change must bump it (at minimum the patch" >&2
echo "component):" >&2
echo "    ./scripts/version.sh bump patch" >&2
echo "" >&2
echo "If this change genuinely does not alter installed behavior (e.g. a" >&2
echo "comment, a skill-local test-only edit, a typo fix), declare that" >&2
echo "explicitly instead of bumping VERSION — add this exact marker to the PR" >&2
echo "body or to a commit message in this PR:" >&2
echo "    $MARKER" >&2
exit 1
