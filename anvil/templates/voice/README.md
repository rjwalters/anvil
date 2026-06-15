# anvil/templates/voice/

Starter **voice-grounding** documents — generalized, de-personalized
templates a consumer can drop in and tune, instead of starting from a
blank page. They are the ship-now half of the four-doc voice taxonomy
defined by the voice-grounding contract (issue #461;
`anvil/lib/snippets/voice_grounding.md`).

These are **schema, not content**: they carry the proven *structure* and
the craft rules that generalize across authors, with every
author-specific example replaced by a marked `<!-- replace me -->`
placeholder. They ship no real author's beliefs, domains, or voice.
Treat them as a starting point to tune for your own persona.

## The four-doc taxonomy

A project declares up to four voice artifacts via the optional top-level
`voice:` block in its `BRIEF.md` frontmatter. The reviewer's owned
voice-fidelity dimension and the drafter's register are grounded in the
declared docs (see `anvil/lib/snippets/voice_grounding.md` for the full
drafter / reviewer / reviser contracts).

| Doc | Role | Shipped here? |
|-----|------|---------------|
| **values** | Who the author is — stances, anti-stances, standing, named failure modes | No — deferred to issue #578 (needs schema + the privacy story) |
| **style_guide** | How the author sounds — register, cadence, sentence-shape rules | **Yes** — `STYLE_GUIDE.template.md` |
| **vocabulary** | What the author would never say — AI-tell guidance, frequency discipline (judgment side) | **Yes** — `VOCABULARY.template.md` |
| **corpus** | Proof — published exemplars a reviewer quotes as voice ground truth | No template — see the corpus convention below |

### Templates shipped here

| File | Becomes | Carries |
|------|---------|---------|
| `STYLE_GUIDE.template.md` | `STYLE_GUIDE.md` | 10 sections (voice/tone, structure, word choice, sentence rhythm, paragraph style, figurative language, openings/closings, authenticity checks, anti-tropes table, style philosophy) + the generalizable craft rules: em-dash discipline, thesis-statement-chain avoidance, telegraphic/staccato avoidance, the self-flattering-adjective AI-tell, the "X is not just Y, it is Z" anti-trope |
| `VOCABULARY.template.md` | `VOCABULARY.md` | the "reminder tool, not injection tool" philosophy, the precision-over-novelty test, the gloss pattern, the red-flags list, and the word-category framing (judgment side only — deterministic screening is the rhetoric lint's job) |

### Not scaffolded here (by design)

- **`VALUES.md`** — deferred to issue #578. It needs schema treatment and
  the privacy story (some values content is sensitive), so it is not a
  ship-now template.
- **Private / `.gitignored` grounding** — deferred to issue #577. The
  scaffold path here writes *committed* templates only; it builds no
  auto-gitignore or git-sync machinery.
- **The `vocab` reminder CLI tool** — deferred to issue #579. The
  vocabulary template references such a tool as an *optional, additive*
  note; it does not depend on one.
- **A corpus** — there is nothing to scaffold. The `corpus` sub-key is a
  glob over your own published exemplars (e.g. `writing-corpus/**/*.md`);
  point it at real published work once you have some.

## Tune, don't ship-as-is

Both templates open with a `<!-- ... -->` header explaining that they are
starting points. Before you rely on them:

1. Open each file and fill in every `<!-- replace me -->` placeholder with
   contrast pairs / word categories drawn from *your* domain. The craft
   rules generalize; the examples need to be yours to have teeth.
2. Trim sections that don't fit your form. A style guide that grows past
   a couple of pages stops being read.
3. Add your own recurring tells to the anti-tropes table.

## Declaring them in a project BRIEF.md

Once the docs exist at your consumer root (or a project root), activate
them by declaring the `voice:` block in the project `BRIEF.md`
frontmatter. This reuses the existing grammar
(`anvil/lib/project_brief.py::VoiceDocs` / `resolve_voice_docs`) — there
is no separate config surface:

```yaml
voice:
  style_guide: STYLE_GUIDE.md      # register / cadence rules
  vocabulary: VOCABULARY.md        # AI-tell guidance (judgment side)
  # values:   VALUES.md            # (optional; see issue #578)
  # corpus:   writing-corpus/**/*.md  # (optional glob over published exemplars)
```

Resolution is **project-root first, then consumer root** (the directory
carrying the `.anvil/` install marker). Voice docs are usually
persona-level repo-root artifacts shared across every project in the
consumer repo, so dropping them at the consumer root is the common case;
a project ghostwriting in a different persona can shadow them locally.

A declared-but-missing file does **not** crash — it surfaces as a `major`
review finding directing you to create or fix the file. The point of the
scaffolder (below) is to make the declared file *exist* so that finding
never fires for a fresh adopter.

## Scaffolding into a consumer

`scripts/install-anvil.sh` scaffolds these templates to the **consumer
root** as `STYLE_GUIDE.md` / `VOCABULARY.md` (stripping the `.template`
infix) when a voice-consuming skill (`essay` or `memo`) is among the
selected skills. The stage:

- is **idempotent** — running the installer twice never errors and never
  produces a second copy;
- **never clobbers** an existing grounding doc — if `STYLE_GUIDE.md` (or
  `VOCABULARY.md`) already exists at the consumer root, the installer
  warns and skips that file, **per file** (a custom `STYLE_GUIDE.md`
  does not block `VOCABULARY.md` from scaffolding);
- is **`--dry-run` aware** — it reports the would-scaffold action and
  writes nothing;
- does **not** auto-edit your `BRIEF.md`. The installer prints the exact
  `voice:` YAML snippet to paste, so the wiring stays explicit and a
  hand-authored BRIEF is never rewritten.

Zero-to-active path for a fresh adopter:

1. Run the installer (with `essay` or `memo` selected).
2. Paste the printed `voice:` snippet into your project `BRIEF.md`.
3. Fill in the `<!-- replace me -->` placeholders in the scaffolded docs.
