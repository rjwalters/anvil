# Changelog

## [Unreleased]

### Added
- Initial repository skeleton.
- Vision, design principles, and planned v0 skill catalog in README.
- MIT license.
- Project-level `CLAUDE.md` for AI session context.
- Directory structure for `anvil/{skills,lib,templates,roles}` and `scripts/`.
- Minimal `scripts/version.sh` (manages `CLAUDE.md` version string only; will grow as more version-bearing files appear).

### Status
- Alpha. No installable functionality. No skills yet implemented.

### Next
- Implement v0 skills per the catalog in README.
- Extract framework `lib/` from observed duplication after the first few skill implementations land.
- Implement `scripts/install-anvil.sh`.
