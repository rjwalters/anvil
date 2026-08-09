# AI-humanizer corpus mining report (issue #919)

**Status:** research/mining report. This issue closes on this document, not on
any code change — see "Follow-up issues" below for where the adopted findings
land.

**Method:** all ten repos were `git clone --depth 1`'d and read directly
(SKILL.md / README.md / the actual pattern-list files, not just marketing
copy). Wikipedia's "Signs of AI writing" was fetched via the MediaWiki
`action=parse&prop=wikitext` API (`en.wikipedia.org` is reachable from this
environment; the rendered HTML is not needed). Every candidate default-rule
addition below was tested against the current `DEFAULT_RHETORIC_RULES` (33
rules, confirmed via `len(DEFAULT_RHETORIC_RULES)` at commit `89b66328`) using
the real `anvil.lib.rhetoric_lint.lint_rhetoric` function — not a standalone
regex script — so code-fence/comment/inline-code exclusions and the
sources-block exemption apply exactly as they would in production. The corpus
scanned was every non-`_meta`/`_review`/`_progress` prose file under
`anvil/skills/*/examples/` (42 files: vendored worked examples across
datasheet, essay, installation, ip-uspto-provisional, ip-uspto, memoir,
primer, proposal, spec — the AUDITED/READY-quality reference prose named in
the issue).

## Corpus survey — what each repo actually contains

### 1. `hardikpandya/stop-slop`

A genuine, disciplined pattern catalogue — the highest signal-to-marketing
ratio of the eight primary repos. `SKILL.md` (68 lines) is a terse rules list;
`references/phrases.md` and `references/structures.md` (128 + 134 lines) hold
the actual taxonomy. Notably **not** Wikipedia-derived — it reads as an
independent, personally-curated style guide (author: Hardik Pandya). Content:

- **Phrases**: throat-clearing openers ("Here's the thing:", "Here's what
  X"), emphasis crutches ("Full stop.", "Let that sink in."), a
  business-jargon table (Navigate→Handle, Deep dive→Analysis, ...), a blanket
  "kill all adverbs" rule with a specific offender list, meta-commentary
  ("The rest of this essay explains..."), vague declaratives ("The reasons
  are structural").
- **Structures**: binary contrasts ("Not because X. Because Y." / "The answer
  isn't X. It's Y."), negative listing ("Not a X... Not a Y... A Z."),
  dramatic fragmentation ("[Noun]. That's it. That's the [thing]."),
  rhetorical setups ("What if [reframe]?"), **false agency** ("a complaint
  becomes a fix", "the decision emerges", "the data tells us" — inanimate
  subjects performing human actions), narrator-from-a-distance ("Nobody
  designed this."), passive voice, Wh-question sentence starters, rhythm
  rules (two-item lists over three, no em dashes at all — a *hard* ban, not
  a density cap).
- A 5-dimension /50 scoring rubric (directness, rhythm, trust, authenticity,
  density), revise-below-35 threshold — structurally identical in shape to
  anvil's dim-9-drives-convergence pattern, just narrower in scope (one
  dimension family, not nine).

### 2. `blader/humanizer`

The most complete and highest-quality single artifact in the corpus (v2.9.1,
actively maintained, ships as both a Claude Code skill and a `.claude-plugin`
marketplace entry). Explicitly derived from — and cites — Wikipedia's "Signs
of AI writing." 33 numbered patterns across five families (Content / Language
& Grammar / Style / Communication / Filler & Hedging), each with a
before/after example. Distinguishing features beyond the pattern list itself:

- **Voice-sample precedence, stated explicitly**: "A sample outranks this
  skill's style rules, including the em dash rule in §14: if the sample uses
  em dashes, keep them at roughly the sample's frequency." This is the
  concrete mechanism the issue's gap 4 asks about.
- **A stated no-fabrication invariant**: "The rewrite must not contain any
  fact, name, number, date, quote, or citation that isn't in the source
  text," with a worked exception for opinions-as-voice vs. facts, and a
  fiction carve-out. This is checked by *asking a question* at revise time
  ("Does the rewrite state any fact, name, number, date, or citation that
  isn't in the source?"), not by a deterministic gate — it is LLM-judgment
  self-audit, same as the "obviously AI generated?" check.
- A "DETECTION GUIDANCE" section that is unusually disciplined about **false
  positives**: perfect grammar, mixed casual/formal register, one em dash,
  one "however," curly quotes alone, one short emphatic sentence — all
  explicitly named as *not* reliable signals. This section is close to a
  direct restatement of Wikipedia's own "Ineffective indicators" section (see
  below) and is good evidence the corpus converges on the same false-positive
  boundary anvil already respects in `rhetoric_lint.py`'s design ("Common
  discourse markers... are explicitly excluded").
- Also documents "signs of human writing to preserve" (specific hard-to-
  fabricate detail, mixed feelings, dated slang, self-corrections, sentence
  variety) — the inverse catalogue.

### 3. `abnahid/claude-humanizer`

A near-duplicate of `blader/humanizer` at an earlier state (24 patterns vs.
33; the same section structure, the same before/after examples verbatim in
many cases; missing #4's per-item severity nuance, the voice-sample
precedence framing, and the false-positive guidance section). Both explicitly
cite Wikipedia as the source. This is not independent corroboration of the
pattern set — it is the same lineage at a different point in time — but it
does confirm that Wikipedia's catalogue is the *de facto* shared upstream for
this entire ecosystem, not just `blader`'s repo.

### 4. `OrbitWebTools/Humanize-AI`

**Not a rule taxonomy.** A README-only "product" (a GitHub Pages-hosted
client-side web tool; no tool source is checked into this repo — only
`manifest.json`, `robots.txt`, and a marketing README). Explicitly and
repeatedly frames itself as a **Turnitin/GPTZero/Originality.ai bypass**
("Does it Bypass Turnitin? Yes.", "changes the Burstiness... making it 100%
undetectable"). This is squarely the issue's named non-goal (detector
evasion, not prose quality). No pattern list exists to mine.

### 5. `Khizer-Data/AI-Text-Humanizer`

A FastAPI scaffold, not a mature tool. `app/utils.py` (123 lines) is mostly
`# TODO`-shaped placeholder code: a random 70%-chance contraction
swap/un-swap per "style," and a `calculate_humanness_score` function whose
own docstring says "This is a placeholder implementation." One thing worth
keeping: it computes **sentence-length variance** as one input to its
humanness heuristic (`variance = sum((l - mean)**2 for l in lengths) /
len(lengths)`) — a crude but real precedent for treating length variance as a
signal, independent of the two synthesizer repos below that state the same
idea more directly. The README explicitly says the tool aims to "bypass AI
content detectors" — same non-goal problem as #4, though the code itself is
too skeletal to be a taxonomy either way.

### 6. `vardhin/Humanizer`

A full-stack (SvelteKit + Flask) app whose actual mechanism is (a) an
ML-model AI-*detector* wrapper (`detector.py`, loads `roberta-base-openai-
detector` and similar HuggingFace classifiers) and (b) an NLTK/spaCy/
WordNet-based **synonym-substitution paraphraser** (`rewriter.py`,
`paraphraser.py`, T5/BART/Pegasus models). There is no hand-authored rule
taxonomy to mine — the "humanization" is statistical paraphrase, not a
pattern catalogue, and the explicit purpose (per the README: "AI Detection...
Combined Humanize & Verify") is a detector-evasion loop, not a style guide.
Out of scope for the same reason as #4/#5.

### 7. `DadaNanjesha/AI-Text-Humanizer-App`

The inverse of what the issue is looking for. `transformer/app.py`'s
`AcademicTextHumanizer` **expands contractions**, **adds academic
transitions** ("Moreover", "Therefore" — words anvil's rules already flag as
overused connectors), and optionally **converts sentences to passive voice**
— i.e. it manufactures more of the AI-tell surface, not less, in service of
sounding more "formal/academic." The README bills this as making text "avoid
[an] AI detector." Confirms nothing adoptable; useful only as a negative data
point (a tool built by someone optimizing for the opposite of what anvil
wants).

### 8. `xszcs546/ai-text-humanizer`

**Not a tool at all.** The single-file README is an affiliate-style listicle
promoting paid SaaS humanizers (AISEO, Undetectable AI, StealthGPT,
WriteHuman, ...), each bypassing named detectors (Turnitin, GPTZero,
Originality.ai). No code, no pattern list. Worth noting for the report's own
amusement value: the listicle's opening line — *"Content creators face a
daily dilemma—AI tells you speed up writing, but detection software flags the
results."* — is itself a textbook instance of several patterns this mining
exercise catalogues (an em dash, a throat-clearing frame-setting opener, a
generalized "content creators" audience-address). It is prose about AI slop
that is itself AI slop. Zero adoptable content; flagged entirely as evidence
that this corner of the ecosystem is SEO content, not tooling.

### 9. `humanizer-tools/slop-humanizer` (synthesizer)

A single `SKILL.md` that states it "synthesizes patterns from: stop-slop,
blader/humanizer, abnahid/claude-humanizer, OrbitWebTools/Humanize-AI, and
Khizer-Data/AI-Text-Humanizer." Given the survey above, two of those five
named sources (`OrbitWebTools`, `Khizer-Data`) contribute essentially nothing
substantive — so the real synthesis is stop-slop + blader + abnahid (and
abnahid is itself downstream of blader). The synthesis itself is competently
done: a 5-pass pipeline (scan → rewrite → audit → rewrite → deliver), the
same /50 5-dimension rubric as stop-slop, and it is the first repo in the
corpus to explicitly name **burstiness** as a design target: "Two signals
detectors use: perplexity... and burstiness... Maximize both." This is the
one place in the corpus where the issue's named non-goal (detector-evasion
framing) leaks into an otherwise prose-quality-motivated skill — the rest of
its content (banned phrases, structural patterns, a copula-avoidance table,
notability name-dropping, hyphenated-word-pair table) is prose-quality
motivated and overlaps heavily with `blader`/`stop-slop`.

### 10. `haidrrrry/humanize-ai-writing` (synthesizer)

Independently derived from Wikipedia (not from the other seven repos) and the
most rigorously engineered artifact in the whole corpus. Three parts:

- `humanize-ai-writing/SKILL.md` — the 12-rule top-level ruleset (a condensed
  Wikipedia digest) plus an explicit **"don't overcorrect"** section: "A
  single flagged word is not proof of AI, and detectors are unreliable."
- `references/ai-tells.md` — a fuller catalogue organized exactly like
  Wikipedia's own section structure (Language & word choice / Sentence
  structure / Fake significance & analysis / Tone & voice / Hedging &
  attribution / Formatting & structure / Markup artifacts / Hollow
  conclusions), including the "not reliable on their own" and "composite
  signal" framing lifted near-verbatim from Wikipedia's caveats.
- **`bin/humanize-check.mjs`** — a zero-dependency, ~100-line Node.js CLI
  deterministic checker. This is the single most useful artifact in the
  entire corpus for anvil's purposes: it is structurally the same idea as
  `anvil/lib/rhetoric_lint.py` (a banned-word list plus a `[label, regex,
  suggestion]` triple list, evaluated per line, non-blocking, exit-code-only
  advisory), independently converged on by a different author working from
  the same Wikipedia source. Its `PHRASES` regex table is a good source of
  ready-made, already-battle-tested patterns (fake significance, negative
  parallelism, copula avoidance, weasel attribution, notability padding,
  hollow conclusions, formula sections, filler phrases, copy-paste artifacts,
  tracking params) — several of these regexes were reused near-verbatim
  as candidates in the false-positive check below.

### 11. Wikipedia: "Signs of AI writing" (WikiProject AI Cleanup)

The maintained, citable upstream almost everything above ultimately traces
back to. Fetched via `action=parse&prop=wikitext` (205KB / 1665 lines of
wikitext). Structure: Content (undue emphasis on significance/notability,
superficial `-ing` analyses, promotional language, vague attributions,
"Challenges and Future Prospects" outline sections) → Language and grammar
(AI-vocabulary word list **with an explicit per-era breakdown** — 2023–mid
2024 vs. mid-2024–mid-2025 vs. mid-2025-on, since which words get overused
has measurably drifted as models changed; copula avoidance; negative
parallelisms with three named sub-variants, "Not just X but Y" / "Not X but
Y" / "X rather than Y"; rule of three; elegant variation) → Style (title
case, boldface, inline-header lists, em dashes, emoji, curly quotes) →
Communication (collaborative artifacts, knowledge-cutoff disclaimers,
sycophantic tone) → Markup (per-vendor copy-paste artifacts: OpenAI's
`oaicite`/`contentReference`, Gemini's `[cite: 1]`, Grok's `grok_card`,
DeepSeek's lenticular brackets, Perplexity's `attached_file`) → Citations
(broken links, invalid DOIs, `utm_source=` leakage, unused named refs) →
**"Signs of human writing"** (a section none of the eight primary repos
reproduce in full) → **"Ineffective indicators"** (a named list of things
that do *not* reliably indicate AI authorship) → **"Historical indicators"**
(disclaimers, section-summary "Conclusion" headers, prompt refusals — mostly
obsolete against current models, dated by era).

Three things worth surfacing that none of the eight downstream repos capture
as clearly as the source:

1. **Caveats section, up front, load-bearing**: "Do not solely rely on AI
   detection tools... these tools have non-trivial error rates," "Do not
   rely too much on your own judgment. Humans are notoriously bad at
   distinguishing human and LLM-generated text" (citing a 2025 study showing
   human detection accuracy is "no better than random chance" in one
   population). This is the strongest possible citation for the issue's own
   explicit non-goal — Wikipedia's own guide, the shared upstream for this
   entire ecosystem, opens by warning that AI-detection itself is
   unreliable and that pattern-matching is for *editorial quality*, not
   forensic certainty.
2. **"Signs of human writing" § Syntax** — an empirically-observed *positive*
   catalogue (simple is/has phrases score as MORE human than elaborate
   copula-avoidance constructions; plain synonyms — "wrote" vs. "authored",
   "used" vs. "utilized" — score as more human than their "stiffer"
   counterparts; hedging qualifiers and wordy constructions like "as a result
   of," "in order to" are *more* common in human writing, the reverse of what
   several of the downstream repos assume). This directly complicates a
   couple of the downstream repos' blanket claims (e.g. `stop-slop`'s "kill
   all adverbs," "no hedging" — Wikipedia's own evidence says hedging
   qualifiers are a *human* tell, not an AI one).
3. **"Ineffective indicators"**: perfect grammar, mixed casual/formal
   register, "bland"/"robotic" prose alone, fancy vocabulary in general
   (only *specific* words are AI-coded), transition words in isolation,
   unsourced content, em dashes alone — all explicitly named as unreliable
   on their own. This is the single clearest citation backing anvil's
   existing design bar ("Common discourse markers... are explicitly excluded
   — too many false positives") and should anchor any new rule's
   inclusion-bar language going forward.

## Cross-cutting observations

- **Convergent derivation, not independent corroboration.** Of the ten
  repos, at least six (`blader`, `abnahid`, `slop-humanizer`,
  `humanize-ai-writing`, and transitively `stop-slop`'s independently
  curated but topically overlapping list) trace to the same Wikipedia
  source or to each other. "8 humanizer repos agree on X" is mostly one
  signal counted eight times, not eight signals. Wikipedia itself, and its
  cited academic sources (Juzek & Ward 2025, Kobak et al. 2025, the
  Washington Post's November 2025 em-dash analysis), are the actual
  independent evidence base.
- **Two of the eight primary repos and one of the two synthesizers are
  explicitly detector-evasion tools** (`OrbitWebTools`, `vardhin`,
  contributing framing to `slop-humanizer`'s burstiness language), one more
  is a stub whose only working idea (sentence-variance scoring) is
  incidental to its stated detector-evasion goal (`Khizer-Data`), one
  actively manufactures MORE AI-tell surface (`DadaNanjesha`), and one is
  not a tool at all — an SEO listicle for paid detector-evasion services,
  ironically itself AI-slop (`xszcs546`). That is 5 of 10 corpus entries
  contributing zero adoptable prose-quality content, which is worth stating
  plainly: **the "8 open-source humanizers" framing overstates the size of
  the useful corpus.** The real yield is `stop-slop` + `blader` (+
  `abnahid` as a redundant snapshot) + the two synthesizers' original
  contributions + Wikipedia.
- **`rhetoric_lint.py`'s existing design bar already matches the corpus's
  own stated false-positive discipline.** Nothing here argues for loosening
  anvil's inclusion bar; if anything, the corpus (especially Wikipedia's
  "Ineffective indicators" and blader's "DETECTION GUIDANCE") argues for
  holding the line harder, since even the source material warns against
  over-firing on weak signals like isolated transition words or one em dash.
- **`haidrrrry`'s `bin/humanize-check.mjs`** is independent proof-of-concept
  that anvil's `rhetoric_lint.py` design (deterministic, advisory-only,
  phrase/regex table, non-blocking) is the right shape for this problem —
  a different author, working from the same source material, converged on
  the same architecture in a different language.

## Triage

### (a) Drop-in additions to `DEFAULT_RHETORIC_RULES`

All candidates below were tested with `lint_rhetoric(text, extra_rules=...)`
against the 42-file vendored-examples corpus described above. **Zero false
positives** unless noted.

| Candidate id | Kind | Pattern (essence) | FP result |
|---|---|---|---|
| `no-stands-as` | regex | `stands as (a\|an)` | 0 hits |
| `no-functions-as` | regex | `functions as (a\|an)` | 0 hits |
| `no-features-a-boasts` | regex | `(features\|boasts) (a\|an)` | 0 hits |
| `no-align-with` | phrase | `align with` | 0 hits |
| `no-garner` | regex | `garner(s\|ed\|ing)?` | 0 hits |
| `no-interplay` | phrase | `interplay` | 0 hits |
| `no-intricate` | regex | `intricat(e\|acy\|acies)` | 0 hits |
| `no-renowned` | phrase | `renowned` | 0 hits |
| `no-groundbreaking` | phrase | `groundbreaking` | 0 hits |
| `no-nestled` | phrase | `nestled` | 0 hits |
| `no-cornerstone` | phrase | `cornerstone` | 0 hits |
| `no-paradigm` | phrase | `paradigm` | 0 hits |
| `no-synergy` | phrase | `synergy` | 0 hits |
| `no-robust` | phrase | `robust` | 0 hits |
| `no-holistic` | phrase | `holistic` | 0 hits |
| `no-cutting-edge` / `no-state-of-the-art` / `no-world-class` | phrase | promo triad | 0 hits |
| `no-highlighting-ing` | phrase | `highlighting` | 0 hits |
| `no-showcasing` | regex | `showcas(e\|es\|ed\|ing)` | 0 hits |
| `no-underscoring-ing` | phrase | `underscoring` | 0 hits |
| `no-reflecting-ing` | phrase | `reflecting` | 0 hits |
| `no-symbolizing` | regex | `symboliz(e\|es\|ed\|ing)` | 0 hits |
| `no-fostering` | regex | `foster(s\|ed\|ing)?` | 0 hits |
| `no-negative-parallel-notonly` | regex | `not only ... but` (span-capped) | 0 hits |
| `no-negative-parallel-notjust` | regex | `not just ... but` (span-capped) | 0 hits |
| `no-negative-parallel-itsnotx` | regex | `it's not ..., it's` | 0 hits |
| `no-more-than-just` | phrase | `more than just` | 0 hits |
| `no-indelible-mark` / `no-turning-point` / `no-focal-point` / `no-deeply-rooted` / `no-evolving-landscape` | phrase | fake-significance cluster | 0 hits |
| `no-sets-the-stage` | regex | `sett?ing the stage` | 0 hits |
| `no-it-is-believed` | regex | `it is (widely )?(believed\|considered\|known\|thought)` | 0 hits |
| `no-sycophantic-cluster` | regex | `i hope this helps\|great question\|you're absolutely right` | 0 hits |
| `no-knowledge-cutoff` | regex | `up to my last training update\|as of my (last\|knowledge) (update\|cutoff)` | 0 hits |
| `no-copy-paste-artifact` | regex | `oaicite\|contentReference\|oai_citation\|turn0search0\|grok_card\|attached_file` | 0 hits |
| `no-curly-quotes` | frequency | `[‘’“”]` | 0 hits |
| `no-weasel-attribution` | regex | `(experts?\|studies\|researchers?\|observers?\|critics?) (say\|show\|argue\|note\|...)` | **1 FP** (see below) |
| `hyphen-pair-density` | frequency | 11-term hyphenated-pair list, 3/1000 words | **2 FPs** (see below) |

Two calibration issues surfaced by the check, both fixable before shipping:

1. **`no-weasel-attribution` collided with `## Critic note → change`** in
   `anvil/skills/spec/examples/.../changelog.md` — `critics?` (the `?` makes
   the `s` optional) matched the singular "Critic" against the following
   " note", producing a false hit on a routine section heading, not an
   attribution phrase. Fix before adoption: drop the singular form (require
   `critics` plural) and/or drop `note` from the trailing-verb alternation
   (too generic a verb to pair with a singular "critic" heading). This is
   exactly the kind of narrow miscalibration the issue's FP-check bar exists
   to catch.
2. **`hyphen-pair-density` at 3/1000 words fired twice**, both in short
   `expected-thread.1/README.md` dev-docs (not the AUDITED artifact bodies
   themselves) driven entirely by "end-to-end" appearing in repeated
   `## End-to-end smoke flow` headings. `end-to-end`, `real-time`, and
   `long-term` are domain-neutral engineering vocabulary, not the
   marketing-register compounds (`data-driven`, `cross-functional`,
   `best-in-class`, `future-proof`, `value-add`, `client-facing`,
   `decision-making`, `third-party`) the pattern is actually meant to catch.
   Fix before adoption: either drop the three neutral-engineering terms from
   the word list, or raise the threshold to ~6-8/1000 (the em-dash-density
   precedent) — the follow-up issue should test both against a larger
   in-house corpus before picking one.

None of the above (once the two fixes are applied) needs new lint
infrastructure — they compose directly onto the existing `phrase` /
`regex` / `frequency` rule kinds.

### (b) Patterns needing a new rule kind

**Sentence-length variance ("burstiness") as a `sentence_variance` rule
kind.** The issue names this explicitly as a candidate, and three
independent corpus entries converge on it as a *measurable, deterministic*
signal distinct from the existing `long_sentence` tail-density rule:

- `stop-slop` / `slop-humanizer`: "Mix sentence lengths... Two items beat
  three... genuinely irregular," scored under the "Rhythm" dimension of the
  /50 rubric.
- `Khizer-Data/AI-Text-Humanizer`'s `calculate_humanness_score` computes raw
  sentence-length variance as one input (a real, if crude, precedent for
  the metric shape).
- Wikipedia does not name "burstiness" directly but its "elegant variation"
  and general uniformity observations are adjacent.

This is a genuinely different signal from `long_sentence` (issue #750):
`long_sentence` measures the *tail* (how many sentences exceed a word-count
threshold, per 1000 words); it says nothing about whether the *rest* of the
document reads as monotonously mid-length. A document could pass
`long_sentence` cleanly (no individual sentence is pathologically long) while
still reading as "every sentence is 18-22 words" — the flattened-rhythm
failure mode none of anvil's 33 existing rules can see. A
`sentence_variance` kind (coefficient of variation — stdev/mean — over the
same naive sentence tokenization `long_sentence` already uses, flagging when
CV falls *below* a floor rather than above a ceiling) is the natural sibling.

Important framing constraint for the follow-up issue, given the issue's own
non-goal: this must ship as a **readability/rhythm** signal (the same
justification anvil already uses for `long_sentence` — "a reader must
re-parse"), explicitly NOT documented or tuned as an anti-detector metric.
The module docstring for the new rule kind should say so directly, the same
way `long_sentence`'s docstring is explicit about not being a mean-length cap
("mean length is style, the pathology is..."). Calibration (the floor value)
needs the same "audit N real documents, find the healthy range" process
`long_sentence` used against the sentinel memo.4→memo.5 canary — that
calibration work belongs in the follow-up issue, not this report.

### (c) Skill/rubric contract changes

Three items from the issue's own gap list are genuine contract questions,
not lint additions. Two have concrete, adoptable proposals; one is a research
question this report defers rather than pre-answers.

1. **No-fabrication invariant gate on `deslop`'s revise loop — adoptable,
   concrete.** `blader/humanizer` states the invariant explicitly ("The
   rewrite must not contain any fact, name, number, date, quote, or citation
   that isn't in the source text") and checks it with an LLM self-audit
   question at revise time, not a deterministic gate. `anvil:deslop`
   (`anvil/skills/deslop/commands/deslop.md` step 3c) has no equivalent
   invariant at all today — `rhetorical_economy` and `voice_adherence` are
   the only two scored dimensions, and neither is about factual fidelity.
   Given the composition point the issue names (#917's parity-quarantine
   machinery — a deterministic diff-based check that already exists for a
   structurally similar problem, "did a revision introduce content that
   wasn't there before"), a deterministic post-revise diff gate (flag
   numerals, proper nouns, and citation-shaped tokens present in iteration
   N+1 but absent from iteration N and from any voice/grounding doc) is a
   concrete, testable addition — not just an LLM self-audit question layered
   on top the way blader does it. This is the single highest-value bucket
   (c) item: deslop is explicitly a rewrite tool over prose anvil doesn't own
   the provenance of, so a deterministic backstop matters more here than
   almost anywhere else in the framework.
2. **Document the voice-sample precedence contract — adoptable, concrete,
   docs-only.** `blader/humanizer` states its precedence rule in one
   sentence: a user-provided writing sample outranks the generic rule set,
   specifically naming that it overrides the em-dash ban. Anvil's
   `voice.rhetoric_rules` (`anvil/lib/project_brief.py::resolve_rhetoric_rules`,
   issue #468) already has the *mechanism* to do this — a consumer rule file
   can `disable` any default rule id by id, including `em-dash-density` and
   `no-opening-emdash` — but the *contract* is not documented anywhere as a
   named pattern: nothing today tells a consumer "if your voice sample uses
   em dashes at a measured frequency, here is how to encode that as a
   `rhetoric_rules` override" as opposed to leaving them to independently
   rediscover that `disable` exists. This is a documentation-only follow-up
   (a new subsection in `rhetoric_lint.py`'s module docstring plus
   `anvil/lib/snippets/voice_grounding.md`), not a code change — genuinely
   adoptable at near-zero cost.
3. **Dim 9 decomposition (rhythm vs. density vs. directness) — NOT adopted
   as a follow-up issue; deferred with reasoning.** The issue itself frames
   this as a question, not a proposal ("The question is not whether to adopt
   their /50 — it's whether a single dim 9 score hides a rhythm failure mode
   our critics have no vocabulary for"). This report agrees it's a real
   question but declines to file a follow-up issue for it now, for two
   reasons: (i) it has no concrete proposal yet — filing it today would be
   exactly the kind of vague, pre-curation-unready issue the builder
   playbook says not to hand to the curator; (ii) it has a natural
   dependency on item (b) above — once `sentence_variance` ships and
   produces real calibration data (the same way `long_sentence`'s adoption
   in #750 was informed by the sentinel memo canary), there will be an
   actual rhythm *signal* to decide whether dim 9 needs a decomposition to
   carry, instead of a hypothetical one. Recommend revisiting after the
   bucket (b) follow-up lands and has run against a few real memo/essay
   threads.

### (d) Rejected, with reason

| Item | Source(s) | Reason |
|---|---|---|
| Everything from `OrbitWebTools/Humanize-AI`, `vardhin/Humanizer`, `Khizer-Data/AI-Text-Humanizer` (its detector framing, not its incidental variance metric), `DadaNanjesha/AI-Text-Humanizer-App` | repos 4, 5, 6, 7 | Explicit AI-detector-evasion tools (Turnitin/GPTZero/Originality.ai bypass framing) or a tool that manufactures MORE AI-tell surface. Squarely the issue's named non-goal. |
| `xszcs546/ai-text-humanizer` in its entirety | repo 8 | Not a tool or pattern list — an affiliate listicle for paid detector-bypass SaaS products. No adoptable content. |
| A hard ban on em dashes ("no em dashes at all," "cut them," "the final rewrite contains no em dashes") | `stop-slop`, `blader`, `slop-humanizer`, `humanize-ai-writing` | Anvil already ships this as a **density** rule (`em-dash-density`, ≤8/1000 words) rather than a hard ban, and Wikipedia's own July 2026 citation notes contemporary models vary widely (Claude uses em dashes *more* than professional writers; ChatGPT now uses them *less* since GPT-5.1 suppression). A density cap that composes with per-project voice overrides (item c.2 above) is the correct anvil-shaped answer; a hard ban is not — it would conflict with legitimate human/voice-sample usage the corpus's own "DETECTION GUIDANCE" section warns against over-firing on. |
| Rule-of-three as a deterministic default rule | Wikipedia, `stop-slop`, `blader` | No reliable regex shape exists for "three coordinate items/clauses" without a real parse of list/comma structure, and even a working detector would have a high legitimate-technical-writing false-positive rate (three-item enumerations are extremely common in correct technical prose — parameter lists, requirement lists). Leave to LLM critic judgment (already implicit in dim 9's holistic pass); not a lint candidate. |
| Bare figurative-vocabulary bans without phrase-anchoring (e.g. banning bare `beacon`, generic `acts as a X`) | Wikipedia, `blader`, `slop-humanizer` | Confirmed false positives in the vendored corpus itself: `botho-from-the-basics.md` (an AUDITED, 44/44-scored primer) uses "beacon" twice in its correct, literal cryptographic-randomness-beacon and tracking-beacon senses, and "acts as a" once in a non-metaphorical technical gloss. Only the specific figurative-collocation forms already adopted above (e.g. `a beacon of`, `acts as an? bridge`) are safe; the bare word/verb is not. |
| `rather than` as a banned/flagged phrase | Wikipedia (names it as a Grok-specific idiosyncrasy), `haidrrrry`'s checker | Fired 22 times across the vendored corpus in ordinary, correct contrastive technical prose ("the shared-vs-per-SKU partition rather than...", "pointed at the central chamber rather than at the viewer's face"). Wikipedia itself frames this pattern as weak and model-specific, not a general tell. Reject as a default; too common in legitimate writing of any register. |
| A strict/hard ban on inline-header bold-lettered lists (`- **Label:** text`) | Wikipedia, `blader`, `slop-humanizer`, `humanize-ai-writing` | Confirmed false positive: the same AUDITED `botho-from-the-basics.md` primer (44/44) uses exactly this construction twice for a two-phase emission-schedule definition list — legitimate, load-bearing structure, not AI padding. A frequency-gated version (analogous to `emphasis-density`) might be viable at a much higher threshold than "any occurrence," but no concrete threshold was validated here; not proposed as a follow-up. |
| Line-anchored structural bans (Wh-question sentence openers, paragraphs starting with "So,"/"Look,", "hollow conclusion" openers keyed to literal source-line start) | `stop-slop`, `blader`, `slop-humanizer`, `haidrrrry` | Anvil's vendored bodies are hard-wrapped prose (~72-100 col source lines), so a literal-line-start anchor collides with mid-sentence wrap points. Demonstrated directly: a naive `^(in conclusion\|overall\|...)\b` check matched "overall" as a false hit in `ip-uspto-provisional/.../BRIEF.md` purely because a hard-wrapped sentence happened to break with "overall" starting the next source line ("...sets the / overall span gain at room temperature."). Any structural rule that depends on "start of sentence" or "start of paragraph" needs a join-then-resplit preprocessing step (the way `_sentence_word_counts` already joins scan lines before tokenizing) — `rhetoric_lint.py`'s existing `scope: "first-line"` mechanism only anchors to the document's first prose line, not to arbitrary sentence/paragraph boundaries, and extending it would be new, nontrivial infrastructure. Not proposed as a follow-up in this pass; flag as a prerequisite if this class of rule is revisited later. |
| Deterministic false-agency / passive-voice / "narrator-from-a-distance" lint rules | `stop-slop`, `slop-humanizer` | These require distinguishing legitimate passive/impersonal technical constructions ("the data shows," "the report was reviewed," "no configuration file needed") from AI-tell agency-avoidance — a semantic judgment call regex cannot make reliably. Wikipedia itself only recommends rewriting these "when active voice makes the sentence clearer," i.e. case-by-case. Leave to critic judgment; not a lint candidate. |
| Wholesale "add personality/soul" voice-injection guidance (have opinions, use "I," let mess in) | `blader`, `abnahid` | Out of scope for anvil's architecture, not merely rejected on merits: voice ownership is already artifact-class-scoped (`essay` owns dim 2 *Voice fidelity* at weight 7; `report`/`memo`/`datasheet` deliberately want neutral technical register, where Wikipedia's own guidance agrees neutral IS the correct human voice for encyclopedic/technical/reference text). Importing a blanket "inject personality" rule would conflict with the register anvil's other artifact classes correctly enforce. Not a gap; the existing per-skill rubric ownership already handles this better than a generic rule could. |
| Burstiness/perplexity as an *explicit optimization target* (as opposed to the readability-framed `sentence_variance` rule kind adopted in bucket b) | `slop-humanizer`, `OrbitWebTools` | The issue's explicit non-goal. The *metric shape* (sentence-length variance) is adopted in bucket (b); the *framing* ("maximize burstiness to beat detectors") is rejected. The follow-up issue for bucket (b) must state this distinction explicitly in the new rule kind's docstring, the same way `long_sentence`'s docstring already forecloses being read as a detector-evasion knob. |

## Follow-up issues

Filed per the adopted buckets above (entering at `loom:triage`, not
pre-curated):

1. **(bucket a)** batch addition of ~28 zero-false-positive default rhetoric-
   lint rules from the humanizer-corpus audit, including the two calibration
   fixes (`no-weasel-attribution`'s singular-"critic" collision;
   `hyphen-pair-density`'s neutral-engineering-term over-trigger).
2. **(bucket b)** new `sentence_variance` rule kind in `rhetoric_lint.py`
   (burstiness-as-readability, explicitly not detector-evasion-framed).
3. **(bucket c.1)** deterministic no-fabrication invariant gate on
   `anvil:deslop`'s revise loop, composing the #917 parity-quarantine
   diff-checking precedent.
4. **(bucket c.2)** document the voice-sample rhetoric-rules precedence
   contract (docs-only: `rhetoric_lint.py` module docstring +
   `anvil/lib/snippets/voice_grounding.md`).

(Issue numbers are recorded in the PR description that closes this issue,
once filed, so this document does not need editing after the fact.)
