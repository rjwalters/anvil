# Anvil

**AI-powered artifact creation using filesystem versioning as the coordination layer.**

Anvil orchestrates iterative drafting, review, and revision of long-form artifacts — investment memos, patent applications, research papers, pitch decks, technical reports. Each artifact lives in an immutable versioned directory; review passes write to read-only sibling directories; revisions consume both and produce the next version. The version history *is* the audit trail.

**Status:** Alpha. Skeleton only — no installable functionality yet. v0 skills are being implemented.

**Sibling project:** [Loom](https://github.com/rjwalters/loom) does this for code (issues, PRs, forge coordination). Anvil does this for prose-and-graphics artifacts (filesystem coordination, no forge required). Both can be installed in the same repository.

## Planned v0 skill catalog

| Skill | Artifact type |
|---|---|
| `anvil:ip-uspto` | USPTO patent applications |
| `anvil:memo` | Investment memos, internal documents |
| `anvil:pub` | Research papers (LaTeX) |
| `anvil:deck` | Pitch decks (Markdown + Marp) |
| `anvil:slides` | Talk / conference slides (Markdown + Marp) |
| `anvil:report` | Technical reports |

## Design principles

1. **Filesystem as substrate.** Versioned directories (`{thread}.{N}/`) are immutable. Sibling directories (`{thread}.{N}.review/`, `.audit/`, `.critic/`, ...) hold read-only critic output. Revisions read both and write `{N+1}/`.
2. **Scored review rubric.** 8 weighted dimensions, /40 total, ≥32 to advance (35 for legal/customer-facing artifacts). Critical flag short-circuits.
3. **Checkpointing.** `_progress.json` per version directory tracks phase state; long phases skip on resume; validation is by file existence, not flag.
4. **State machine.** `EMPTY → DRAFTED → REVIEWED → REVISED → … → READY → AUDITED`.
5. **Separation of concerns.** Review is read-only. Revision is separate. Audit is a distinct fact-check phase. Figure generation is its own role.
6. **N parallel critics, one reviser.** Multiple critic siblings (`.review/`, `.audit/`, `.critic/`, `.s101/`, ...) feed a single reviser pass — this is a first-class primitive, not a special case.
7. **Forge-optional.** Anvil works on a single laptop with no GitHub account. A forge can be added for collaboration but is not required.
8. **Opinionated defaults, override liberally.** Anvil-shipped skills are starting points. Consumers are expected to extend them with project-specific voice, rubrics, and asset generators via `.anvil/skills/<name>/` in the consumer repo.
9. **Skill identity = artifact identity.** Anvil ships one skill per standardized artifact type (pitch deck, talk slides, investment memo, patent application, research paper, technical report), not parameterized meta-skills with `--type` flags. When two skills share infrastructure (renderer, asset pipeline, scoring logic), the sharing lives in `anvil/lib/`, not by collapsing the skills.

## Installation

Not yet wired up. See [CHANGELOG.md](CHANGELOG.md) for status.

**Optional Python extras.** Anvil's core ships subprocess-only (no Python deps). Advanced detectors that need a third-party library are exposed as opt-in extras:

```bash
uv pip install -e .[auto_shrink]   # enables the anvil:deck silent-Marp-auto-shrink lint (#102)
```

When an extra isn't installed, the corresponding check gracefully skips and the surrounding command (e.g. `deck-review`) proceeds normally with a clear remediation message in its output.

## Repository layout

```
anvil/
  skills/        Per-artifact-type skills (ip-uspto, memo, deck, pub, ...)
  lib/           Framework code (state machine, rubric, version layout, progress)
  templates/     SKILL.md and rubric scaffolds
  roles/         Generic roles (drafter, reviewer, reviser, auditor, critic, figurer)
scripts/
  install-anvil.sh   Install anvil into a target repo (planned)
  version.sh         Version management across files
```

## License

MIT
