# Voice grounding: persona docs as drafting and review substrate

This snippet codifies the **voice/persona grounding-docs contract**
(issue #461) — how a project declares the voice artifacts that define
its author persona, how drafters ground new prose in them, and how
reviewers calibrate voice-fidelity judgment against them. The contract
generalizes the proven shape from the rjwalters.info blog pipeline
(`STYLE_GUIDE.md` / `VOCABULARY.md` / `VALUES.md` / published-post
corpus + `blog-review.md`), where every draft/review/revise pass is
grounded in four voice artifacts.

This is the **judgment-side** contract. Deterministic vocabulary
screening — AI-tell word counting, banned-phrase matching, em-dash
frequency analysis — belongs to the rhetoric lint (issue #463), NOT
here. A reviewer following this snippet MAY note vocabulary tells in
prose, but builds no counting machinery; the lint is the mechanical
pre-flight, this contract is the calibrated judgment that runs after
it.

## The four-doc taxonomy

A project declares up to four voice artifacts via ONE optional
top-level key in the project `BRIEF.md` frontmatter (parsed by
`anvil/lib/project_brief.py::VoiceDocs`):

```yaml
voice:
  style_guide: STYLE_GUIDE.md        # optional — register / cadence rules
  vocabulary: VOCABULARY.md          # optional — AI-tell guidance (judgment side only)
  values: VALUES.md                  # optional — stances / anti-stances / standing /
                                     #            voice signatures / failure modes
  corpus: writing-corpus/**/*.md     # optional glob — published exemplars quoted
                                     #                 as voice ground truth
  rhetoric_rules: rhetoric-rules.json  # optional — consumer JSON rules for the
                                       #            rhetoric lint (gate side; NOT
                                       #            a grounding doc — see below)
```

| Doc | Role | What it carries |
|-----|------|-----------------|
| **values** | Who the author is | Stances and anti-stances, standing (what the author has earned the right to say), voice signatures, named failure modes |
| **style_guide** | How the author sounds | Register, cadence, sentence-shape rules, structural habits |
| **vocabulary** | What the author would never say | AI-tell word guidance ("delve", "tapestry", …), frequency discipline notes |
| **corpus** | Proof | Published exemplars — the ground truth a reviewer quotes when judging whether new prose sounds like the author |

Every sub-key is optional; the block itself is optional.

**Starter templates ship for all three authored doc kinds** (issues
#576, #578): `anvil/templates/voice/STYLE_GUIDE.template.md`,
`anvil/templates/voice/VOCABULARY.template.md`, and
`anvil/templates/voice/VALUES.template.md` are generalized,
de-personalized starting points (schema, not content — every
author-specific example, stance, anti-stance, and standing claim is a
marked `<!-- replace me -->` placeholder; no real author beliefs ship).
A consumer adopting voice grounding does not start from a blank page:
`scripts/install-anvil.sh` scaffolds them to the consumer root as
`STYLE_GUIDE.md` / `VOCABULARY.md` / `VALUES.local.md` (per-file
skip-if-exists, never clobbering an existing grounding doc) when a
voice-consuming skill (`essay` / `memo`) is selected. **`VALUES.md` is
private by default** (issue #578): it carries first-person stances /
anti-stances / standing, so it scaffolds to a gitignored
`VALUES.local.md` (the `*.local.md` path #577 ships) rather than a
committed `VALUES.md` — a gitignored declared doc resolves and grounds
identically to a committed one (see "## Private grounding" below). See
`anvil/templates/voice/README.md`. The optional **vocab reminder tool**
(issue #579) ships at `anvil/lib/vocab_reminder.py` (`python -m
anvil.lib.vocab_reminder [count]`) — the generative-reminder complement
to the judgment-side `VOCABULARY.md`. It is a *reminder, not an
injector*: it surfaces precision-word candidates for a human to consider,
never auto-applies them, and the drafter MUST NOT mechanically substitute
sampled words (see the essay drafter's step-3 reminder note). It draws
from a sibling `*.words.txt` next to the declared `voice.vocabulary` doc
when present, else a small anvil default.

**`rhetoric_rules` is the asymmetric fifth sub-key** (issue #468): a
path to a consumer **JSON rule file** consumed by the render gate's
advisory `memo_rhetoric_lint` check (issue #463) — lint-side
configuration, NOT a grounding doc. It never enters the drafter's load
order or the reviewer's calibration, is excluded from
`resolve_voice_docs` output, and does NOT count toward
`VoiceDocs.is_empty`: a `rhetoric_rules`-only `voice:` block activates
only the lint wiring (resolved by
`anvil/lib/project_brief.py::resolve_rhetoric_rules`, same
project-root-then-consumer-root walk) and never the judgment tier
below. A declared-but-missing rule file is still forwarded to the gate,
where the lint emits one warning finding naming the error and runs
defaults-only (the same defect-to-surface posture as the grounding
docs, with zero extra machinery).

## Activation pattern (the #428/#452 contract)

- **No `voice:` block → byte-identical behavior.** No suffix, no
  `_summary.md` block, no `_progress.json` field, no extra reads.
  Consumers that never declare the block never see this contract.
- **Declared-but-missing file → the tier ACTIVATES** and the breakage
  surfaces as a **`major` review finding** directing the operator to
  create or fix the file. A broken declaration is a defect to surface,
  not an opt-out and not a crash (the
  `anvil/skills/report/lib/customer_context.py` posture).
  `resolve_voice_docs` carries missing files as structured
  `missing: true` entries; it never raises on absence.
- **Empty block (`voice: {}`), unknown-sub-keys-only block, or
  `rhetoric_rules`-only block → inactive** for this judgment tier,
  same as absent (`VoiceDocs.is_empty`; the `rhetoric_rules` sub-key
  is recognized but gate-side — it activates only the rhetoric-lint
  wiring, see above). Unknown sub-keys are preserved verbatim under
  `unknown_keys` with a warning (forward-compat).

## Path resolution: project root first, then consumer root

Relative declared paths resolve against the **project root first, then
the consumer root** (the directory carrying the `.anvil/` install
marker, located via `anvil/lib/theme.py::find_consumer_root` — the
#322/#394 walk; first hit wins). Voice docs are usually persona-level
repo-root artifacts shared across every project in the consumer repo,
but a project ghostwriting in a different persona can shadow them
locally. The `corpus` value is a glob (`**` supported); a root "hits"
when the glob matches at least one file; matches are sorted. Use
`anvil/lib/project_brief.py::resolve_voice_docs(project_dir,
consumer_root=None)` — do not re-implement the walk.

## Private grounding (`.gitignored` personal docs)

The personal layer of voice grounding — *what the author believes,
what they refuse to say, what they have standing to claim*
(`VALUES.md`-class content) — is exactly the material many consumers
will NOT want committed into a shared or public repo. Anvil makes
**private grounding a designed, tested, protected posture** so those
consumers neither commit personal stances publicly nor skip the
highest-leverage grounding doc.

This works because resolution is **filesystem-driven and never
consults git status**: `resolve_voice_docs` walks project-root then
consumer-root and resolves a declared doc whether or not it is tracked
by git. A `.gitignored` declared doc resolves and activates the tier
**identically to a committed one** — same load order, same drafter
grounding, same reviewer calibration, same `major` finding when it is
declared-but-missing. There is no separate "private" code path and no
special-casing; privacy is a property of where the file lives in git,
not of how anvil reads it.

### The convention

- **Default (documented): the `*.local.md` suffix.** Name a private
  grounding doc with a `.local.md` suffix (e.g. `VALUES.local.md`) and
  declare it in the `voice:` block like any other doc. The suffix has
  industry precedent (dotenv `.env.local`, Vite `*.local`) and reads
  unambiguously as "private overlay, do not commit." The scaffolder
  gitignores `*.local.md` with a single pattern line.
- **Supported alternative: a `.voice/` locus.** A consumer who prefers
  a directory boundary may keep private docs under a gitignored
  `.voice/` directory (e.g. `.voice/VALUES.md`) and declare that path.
  One `.gitignore` line (`/.voice/`) covers the whole locus. This is
  supported but not the documented default — pick one convention per
  repo and stay consistent.

Either way the declaration is ordinary `voice:` grammar — there is no
new config surface and no `--private` flag in the BRIEF:

```yaml
voice:
  style_guide: STYLE_GUIDE.md      # committed — team-shared register
  values: VALUES.local.md          # private  — gitignored personal stances
```

### What "private" guarantees

- The doc **resolves and grounds** drafting and review identically to
  a committed doc (the filesystem-driven resolver above).
- The scaffolder **appends its path to `.gitignore`** idempotently
  (see `scripts/install-anvil.sh` Stage 7.9 and
  `anvil/templates/voice/README.md`).
- **Anvil's own git-sync hook will never stage or commit it** (the
  opt-in per-phase commit hook, `anvil/lib/snippets/git_sync.md`; the
  guard is stated there under §"Staging scope").

### What "private" does NOT guarantee

State this plainly so operators do not over-trust the model:

- It is **not encryption.** The file sits in plaintext on disk; anyone
  with filesystem access reads it.
- It is **not protection against a human or a non-anvil tool.** A
  `git add -f <path>` force-adds a gitignored file, and any other tool
  that runs `git add -A`/`-f` can stage it. Anvil's guarantee is only
  about *anvil's own* git activity (the git-sync hook), which never
  uses `-f` and never `git add -A`.
- It **does not stop the doc's *influence* from appearing in committed
  prose.** That is the point: the voice is grounded by the private
  stances, but only the resulting artifact is committed — the source
  document stays private, its effect does not.

### Intended user

`VALUES.md`-class personal stances are the intended user of private
grounding (the canonical `VALUES.local.md`): stances and anti-stances,
standing, voice signatures, named failure modes — the content authored
in the first person that an author would not publish verbatim. The
`VALUES.md` schema + starter template is tracked by issue #578, which
is a **downstream consumer** of this private path: it simply declares a
`VALUES.local.md` (or `.voice/VALUES.md`) using the mechanism shipped
here.

### Layering (committed base + private overlay): DEFERRED

A committed team-level base supplemented by a private personal overlay
(e.g. `VALUES.md` committed + `VALUES.local.md` gitignored, merged or
last-wins) is **deliberately deferred** to a follow-up (epic #575).
Anvil ships the **single-private-doc model first**. Rationale:

1. Merge/last-wins semantics multiply the resolver's surface —
   `resolve_voice_docs` returns one `ResolvedVoiceDoc` per declared
   kind today; layering would require a list-per-kind or a merge step,
   touching every downstream consumer of `ResolvedVoiceDoc`.
2. The single-private-doc model already solves the stated need (a
   private `VALUES.md`).
3. The `*.local.md` suffix convention chosen above leaves the door
   open to add layering later without a breaking change (the overlay
   already has a name).

If layering is later shipped it must define merge semantics precisely
and update the four-doc load-order docs above.

## Drafter contract

When the voice tier is active, the drafter:

1. **Loads the declared docs in order: values → style_guide →
   vocabulary → corpus exemplars.** Values first — the stances and
   standing constrain what may be said before register shapes how it
   is said.
2. **Chooses 3–5 corpus exemplars** that are **voice-matched AND
   topically adjacent** to the artifact being drafted. Not the whole
   corpus — a handful of exemplars read closely beats fifty skimmed.
3. **Records the consulted exemplar paths in `_progress.json`** under
   `metadata.voice_exemplars` (a list of path strings) so the reviewer
   can check that grounding actually happened. No `voice:` block → the
   field is omitted entirely.
4. **Quotes a corpus passage when justifying a register or mode
   choice** in its self-check — the same evidence discipline the
   reviewer is held to below.

Missing declared docs do not block drafting: the drafter proceeds with
whatever resolved, and the reviewer surfaces the broken declaration.

## Reviewer contract

When the voice tier is active, the reviewing skill calibrates its
**owned dimension** (the skill names which one — memo uses dim 8
*Prose & structure*; see `anvil/skills/memo/rubric.md` §"Dim 8 —
voice-grounding calibration") against the resolved voice docs, via the
skill's triggered-suffix mechanism (the #348 composition-order
precedent). Rules:

- **Every voice deduction MUST quote a corpus passage** showing what
  the target voice sounds like. Vague feedback ("this doesn't sound
  like you") is insufficient — the deduction names the offending
  artifact passage AND quotes the exemplar passage it falls short of.
  This is the load-bearing discipline that makes the consumer's loop
  work; a voice deduction without a corpus quote is itself a defective
  finding. (Complementary, not conflicting, with the quoted-evidence
  sub-rule in `rubric.md` §"Dimension scoring guidance" rule 1, which
  quotes the *reviewed body* — a voice deduction under both contracts
  quotes BOTH the offending body passage and the corpus exemplar, as
  this rule already requires.)
- **The convergence-with-Claude adversarial check**: for each passage
  under voice scrutiny, the reviewer asks — *would I, the AI, also
  write this sentence?* If yes, scrutinize harder, never defend.
  Convergence between the artifact's voice and the reviewing model's
  own default register is the biggest meta-failure mode of AI-assisted
  voice work: the reviewer's instinct to approve prose it would have
  produced itself is precisely the signal that the persona has been
  flattened.
- **Anti-stance violations are critical-flag candidates.** When the
  values doc declares anti-stances, substrate, or standing limits, a
  violation routes through the skill's **existing** critical-issue
  machinery (the memo `hard_rules` precedent) — not a new flag
  category. The flag justification quotes the violated values-doc
  passage.
- **Vocabulary tells are noted, not counted.** The reviewer may cite
  vocabulary-doc guidance in prose findings, but deterministic
  screening (word counts, em-dash frequency) is the rhetoric lint's
  job (issue #463).

## `_summary.md` block

When the tier is active, the reviewer's `_summary.md` carries a
top-level `voice_grounding` block:

```json
"voice_grounding": {
  "ran": true,
  "docs_loaded": ["/abs/path/VALUES.md", "/abs/path/STYLE_GUIDE.md"],
  "exemplars_quoted": 2
}
```

`docs_loaded` lists the resolved paths actually read (load order);
`exemplars_quoted` counts the corpus passages quoted across the voice
findings. When declared docs were missing, add a `"missing":
["<declared path>", …]` list naming them (the `major` finding carries
the remediation).

**When the tier is inactive (no `voice:` block in the project BRIEF),
the block is NOT emitted at all** — no `{ran: false}` entry. This
deliberately matches the customer-context activation convention
(absent declaration = absent block = byte-identical output), NOT the
`ran: false` explicit-skip convention used for substrate-driven
sub-steps like `summary_detail_consistency`. The difference: those
sub-steps are always-on framework behavior whose skip needs
explaining; this tier simply does not exist for projects that never
declared it.

## Reviser contract (one line)

When the tier is active, the reviser reads the resolved voice docs
alongside the critic feedback and **preserves voice signatures the
reviewer flagged as working** — voice-grounded revision must not
sand off the persona while chasing rubric points.

## Adoption

Skills adopt this contract by wiring three touch-points: an advisory
load + exemplar record in the drafter command, a triggered suffix on
the owned dimension + the `_summary.md` block in the reviewer command,
and the one-line read-and-preserve rule in the reviser command. The
memo skill is the pilot consumer (issue #461); the essay skill (issue
#460) is the first heavy consumer — its rubric weights voice much
higher, but it consumes this contract, it does not redefine it.
