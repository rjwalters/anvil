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
```

| Doc | Role | What it carries |
|-----|------|-----------------|
| **values** | Who the author is | Stances and anti-stances, standing (what the author has earned the right to say), voice signatures, named failure modes |
| **style_guide** | How the author sounds | Register, cadence, sentence-shape rules, structural habits |
| **vocabulary** | What the author would never say | AI-tell word guidance ("delve", "tapestry", …), frequency discipline notes |
| **corpus** | Proof | Published exemplars — the ground truth a reviewer quotes when judging whether new prose sounds like the author |

Every sub-key is optional; the block itself is optional.

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
- **Empty block (`voice: {}`) or unknown-sub-keys-only block →
  inactive**, same as absent (`VoiceDocs.is_empty`). Unknown sub-keys
  are preserved verbatim under `unknown_keys` with a warning
  (forward-compat — issue #463 may add a `rhetoric_rules` sub-key).

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
