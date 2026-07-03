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
| **values** | Who the author is — stances, anti-stances, standing, named failure modes | **Yes** — `VALUES.template.md` (private by default — scaffolds to `VALUES.local.md`) |
| **style_guide** | How the author sounds — register, cadence, sentence-shape rules | **Yes** — `STYLE_GUIDE.template.md` |
| **vocabulary** | What the author would never say — AI-tell guidance, frequency discipline (judgment side) | **Yes** — `VOCABULARY.template.md` |
| **corpus** | Proof — published exemplars a reviewer quotes as voice ground truth | No template — see the corpus convention below |

### Templates shipped here

| File | Becomes | Carries |
|------|---------|---------|
| `STYLE_GUIDE.template.md` | `STYLE_GUIDE.md` | 10 sections (voice/tone, structure, word choice, sentence rhythm, paragraph style, figurative language, openings/closings, authenticity checks, anti-tropes table, style philosophy) + the generalizable craft rules: em-dash discipline, thesis-statement-chain avoidance, telegraphic/staccato avoidance, the self-flattering-adjective AI-tell, the "X is not just Y, it is Z" anti-trope |
| `VOCABULARY.template.md` | `VOCABULARY.md` | the "reminder tool, not injection tool" philosophy, the precision-over-novelty test, the gloss pattern, the red-flags list, and the word-category framing (judgment side only — deterministic screening is the rhetoric lint's job) |
| `VALUES.template.md` | `VALUES.local.md` (**private**) | the six proven sections — Audience (+ a one-line register test), Stances (each pinned to a corpus exemplar), Anti-stances (drift tells, cross-linked to the rhetoric lint), Standing (firsthand vs. reference-level + the "would your audience call you on this?" check), Voice signatures (the reviser preserves these), and cross-dimensional Failure modes (cross-linked to the example-coherence / numeric-consistency gates). Ships **schema, not content** — every stance/anti-stance/standing slot is a `<!-- replace me -->` placeholder; no real author beliefs ship |

### Private by default: `VALUES.local.md`

`VALUES.template.md` is the one template that carries **first-person
stances, anti-stances, and standing** — the half of voice grounding most
authors do NOT want committed into a shared or public repo. It therefore
scaffolds **private by default**: the installer copies it to
`VALUES.local.md` (not a committed `VALUES.md`), and the `*.local.md`
.gitignore line the scaffolder already adds (issue #577) keeps it out of
commits automatically. Its header shows the private wiring
(`values: VALUES.local.md`). A gitignored declared doc resolves and
grounds drafting/review identically to a committed one — see
"Private grounding" below.

### The `vocab` reminder tool (shipped: issue #579)

Anvil ships a small **precision-vocabulary reminder** at
`anvil/lib/vocab_reminder.py` (`python -m anvil.lib.vocab_reminder
[count]`) — the *generative-reminder* complement to the judgment-side
`VOCABULARY.md` doc. It surfaces a random sample of precision words while
you draft; it is a **reminder, not an injector** — it never edits a
draft, and a word earns its place only when it clicks with a concept you
are already expressing (precision over novelty, 0–2 per 1000). The
`VOCABULARY.template.md` "## The Tool" section documents how to run it
and restates the discipline; the template does **not** depend on it.

Source order for the word list:

1. **Your own list** — a sibling `*.words.txt` next to the doc declared
   as `voice.vocabulary` (e.g. `VOCABULARY.words.txt` beside
   `VOCABULARY.md`). This is where the real value lives: drop a larger
   list (the rjwalters.info source ships ~3,800 words) and the tool
   prefers it. No schema change — it is a filename convention.
2. **The anvil default** — a small curated set
   (`anvil/templates/voice/vocab.words.txt`, ~150 words) so the tool
   works out of the box.

### Not scaffolded here (by design)

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
root** as `STYLE_GUIDE.md` / `VOCABULARY.md` / `VALUES.local.md`
(stripping the `.template` infix; the values doc keeps a `.local.md`
suffix so it stays private — see below) when a voice-consuming skill
(`essay` or `memo`) is among the selected skills. The stage:

- is **idempotent** — running the installer twice never errors and never
  produces a second copy;
- **never clobbers** an existing grounding doc — if `STYLE_GUIDE.md`,
  `VOCABULARY.md`, or `VALUES.local.md` already exists at the consumer
  root, the installer warns and skips that file, **per file** (a custom
  `STYLE_GUIDE.md` does not block `VOCABULARY.md` or `VALUES.local.md`
  from scaffolding);
- is **`--dry-run` aware** — it reports the would-scaffold action and
  writes nothing;
- does **not** auto-edit your `BRIEF.md`. The installer prints the exact
  `voice:` YAML snippet to paste, so the wiring stays explicit and a
  hand-authored BRIEF is never rewritten;
- **protects the private-grounding paths** (issue #577) by appending the
  `*.local.md` and `/.voice/` patterns to your `.gitignore` idempotently
  (it never duplicates an existing entry and never rewrites unrelated
  lines). See "Private grounding" below.

Zero-to-active path for a fresh adopter:

1. Run the installer (with `essay` or `memo` selected).
2. Paste the printed `voice:` snippet into your project `BRIEF.md`.
3. Fill in the `<!-- replace me -->` placeholders in the scaffolded docs.

## Customizing rhetoric rules

The judgment-side `VOCABULARY.md` doc has a deterministic complement: the
**rhetoric lint** (`anvil/lib/rhetoric_lint.py`), a rule-set-driven
anti-trope / AI-tell scan that ships ~28 conservative default rules. A
project points the lint at a consumer rule file by declaring the optional
`voice.rhetoric_rules` sub-key in its `BRIEF.md` frontmatter (resolved by
`anvil.lib.project_brief.resolve_rhetoric_rules`; wired into the memo
render gate — see `anvil/skills/memo/commands/memo-render.md`):

```yaml
voice:
  style_guide: STYLE_GUIDE.md
  vocabulary: VOCABULARY.md
  rhetoric_rules: rhetoric-rules.json   # optional consumer rule file
```

Consumer rules are **merged over** the framework defaults; a consumer
rule whose `id` collides with a default **replaces** it silently. That
id-collision override is the mechanism for the two most common tunings.

### Tightening em-dash density (worked example)

The default `em-dash-density` rule flags sustained em-dash use above
`8` per 1000 words (`max_per_1000_words: 8`). To enforce a **tighter**
threshold, ship a consumer rule reusing the same `id` — it replaces the
default, so only your threshold applies:

```json
{
  "name": "my-voice-rules",
  "rules": [
    {
      "id": "em-dash-density",
      "kind": "frequency",
      "pattern": "—",
      "max_per_1000_words": 5,
      "message": "Em-dash density exceeds the tighter voice threshold (5/1000); vary punctuation."
    }
  ]
}
```

`5/1000` (≈ 1 per 200 words) is the worked example from a surveyed
consumer's judgment-side em-dash discipline — noticeably stricter than
the framework's `8/1000` default. Because the `id` is `em-dash-density`,
the framework's rule is not *also* applied; your `5/1000` is the only
em-dash-density rule that runs. The same id-collision pattern loosens the
threshold (raise `max_per_1000_words`) or fully replaces any other
default rule.

### Positional (opening-line) tells

Beyond density, `phrase`/`regex` rules accept an optional
`scope: "first-line"` attribute that restricts the rule to the
document's first prose line (after front-matter/heading stripping). The
default `no-opening-emdash` rule uses it to flag **any** em-dash in the
opening line regardless of overall density — a documented generic-AI
cadence tell. Consumers author their own positional rules the same way:

```json
{"id": "no-opening-question", "kind": "regex", "scope": "first-line",
 "pattern": "\\?\\s*$", "message": "Avoid opening on a rhetorical question."}
```

`scope` is meaningful only for `phrase`/`regex` rules; `frequency` rules
are always document-level. Absent or unknown `scope` values default to
`"body"` (evaluate every line). Both tunings are advisory — the rhetoric
lint's warning-severity ceiling is a contract; no consumer rule can
change a gate/verdict.

## Private grounding (`.gitignored` personal docs)

The personal layer of voice grounding — `VALUES.md`-class stances,
anti-stances, and standing — is exactly the content many authors do NOT
want committed into a shared or public repo. Anvil makes private
grounding a **first-class, protected posture** (issue #577). The full
contract lives in `anvil/lib/snippets/voice_grounding.md` §"Private
grounding"; the practical summary:

- **It just works because resolution ignores git status.** A
  `.gitignored` declared doc resolves and activates the voice tier
  *identically* to a committed one — same load order, same grounding,
  same `major` finding if it is declared-but-missing. There is no
  separate private code path.
- **Convention.** The documented default is the **`*.local.md` suffix**
  (e.g. `VALUES.local.md`); a gitignored **`.voice/` locus** (e.g.
  `.voice/VALUES.md`) is the supported alternative. Pick one per repo.
- **Declare it like any other doc:**

  ```yaml
  voice:
    style_guide: STYLE_GUIDE.md      # committed — team-shared register
    values: VALUES.local.md          # private  — gitignored, never committed
  ```

- **What private guarantees:** the doc grounds drafting/review like any
  other; the installer gitignores its path; anvil's git-sync hook never
  stages or commits it.
- **What private does NOT guarantee:** it is **not encryption**, it does
  **not** stop a human's `git add -f` or a non-anvil tool, and it does
  **not** stop the doc's *influence* from showing up in committed prose
  (that is the point — the voice is grounded, the source stays private).

### Layering: deferred

A committed base + private overlay (e.g. `VALUES.md` committed +
`VALUES.local.md` gitignored, merged or last-wins) is **deliberately
deferred** to a follow-up (epic #575). Anvil ships the
**single-private-doc model first** — it solves the canary's stated need
(a private `VALUES.md`), avoids multiplying the resolver's
one-entry-per-kind surface, and the `*.local.md` convention leaves the
door open to add layering later without a breaking change.
