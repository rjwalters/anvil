<!--
  VALUES.template.md — anvil voice-grounding starter template (PRIVATE by default)

  This is a STARTING POINT, not finished content. It ships the proven
  STRUCTURE of a values doc — who you write for, what you argue, what you
  refuse, what you have standing to say, the moves that mark your prose,
  the defects to watch for — and NOT any one author's actual beliefs.
  Every place where a real author would put a stance, an anti-stance, a
  standing claim, or a named failure mode is left as a marked
  `<!-- replace me -->` placeholder. Fill those in (in the first person,
  with your own positions) before declaring this doc in a project
  BRIEF.md `voice:` block.

  PRIVATE BY DEFAULT. A values doc carries first-person stances,
  anti-stances, and standing — the half of voice grounding most authors
  do NOT want committed into a shared or public repo. Anvil makes private
  grounding a first-class, protected posture (issue #577): name this doc
  with a `.local.md` suffix so the installer's `*.local.md` .gitignore
  line keeps it out of commits, then declare the private path in your
  BRIEF.md `voice:` block exactly like any committed doc:

      voice:
        values: .anvil/voice/VALUES.local.md   # private — resolves, never committed

  A gitignored declared doc resolves and grounds drafting/review
  IDENTICALLY to a committed one (resolution is filesystem-driven and
  never consults git status). "Private" is not encryption and does not
  stop a manual `git add -f`; it keeps the source out of anvil's own
  commits, not out of every tool. See `anvil/templates/voice/README.md`
  §"Private grounding" and `anvil/lib/snippets/voice_grounding.md`
  §"Private grounding" for the full contract.
-->

# VALUES.md

**Purpose.** A reference for the voice-grounding contract
(`anvil/lib/snippets/voice_grounding.md`): who you write for, what you
believe and will argue for, what you refuse to say, the background
commitments you argue *from*, the positions you are still forming, what
you have firsthand standing to claim, the registers you legitimately write
in, the recurring moves that mark your prose, and the defects you want the
reviewer to catch. This is the
**judgment-side** persona doc. Deterministic word/em-dash screening is
the rhetoric lint's job (issue #463); this doc carries the positions and
named failure modes the reviewer calibrates against. Edit it freely —
ground truth is what you actually think.

> **This is a template.** The *section structure* below is the proven
> shape. The *content* is placeholders — replace each
> `<!-- replace me -->` with your own first-person material so the
> reviewer has something real to calibrate against. A values doc full of
> placeholders grounds nothing.

---

## Audience

<!--
  HOW TO FILL THIS. Name who you write for in one or two sentences — the
  reader over your shoulder. Then pick ONE one-line register test that
  subsumes a lot of your review: a single question you can ask of every
  pass that catches the dominant way your drafts drift off-voice. The
  test should be specific to YOUR failure mode (e.g. a register contrast
  you keep losing), not a generic "is this good writing?".
-->

You write for: <!-- replace me: one or two sentences naming your reader and the posture you take toward them -->

### The register test

Every review pass should ask one meta-question that subsumes much of the
rubric:

> **<!-- replace me: your one-line register test, phrased as a question — e.g. "Does this read like A, or like B?" where B is the register you keep drifting into -->**

Drift toward the wrong register shows up as:

- <!-- replace me: a concrete tell that signals you've drifted off-voice -->
- <!-- replace me: another tell -->
- <!-- replace me: another tell -->

---

## Stances

Things you believe and will argue for in writing. **Pin each stance to a
corpus exemplar** — a published passage that shows the stance in your own
voice — so the reviewer can quote it when checking whether a new draft is
consistent with you (this is the corpus-quote rule from
`anvil/lib/snippets/voice_grounding.md` §"Reviewer contract"). Without an
exemplar hook a stance is just an assertion the reviewer cannot ground.

### 1. <!-- replace me: a one-line statement of a position you hold -->

<!-- replace me: two or three sentences expanding the stance — what you mean, why you hold it -->

**Exemplar:** <!-- replace me: a corpus path + a short quoted passage where this stance shows up in your voice -->

### 2. <!-- replace me: a second position -->

<!-- replace me: expansion -->

**Exemplar:** <!-- replace me: corpus path + quoted passage -->

<!--
  replace me (add more): keep adding numbered stances. A handful of
  sharp, exemplar-pinned stances beats a long list of vague ones.
-->

---

## Anti-stances

Things you avoid saying or refuse to endorse. **Read between the lines:**
these usually show up in your corpus as positions argued *against*, not
as bald claims — so the reviewer should treat a draft that drifts toward
an anti-stance as suspect even when no positive stance forbids it. Note
the *tell* that signals each drift.

> **Cross-link to the deterministic gates.** An anti-stance is a
> *judgment* concern — the reviewer flags a passage that endorses a
> position you refuse. It is NOT a word-list. Deterministic word and
> em-dash screening belongs to the rhetoric lint (issue #463); keep the
> judgment here and let the lint do the counting. When the values tier
> is active, an anti-stance violation is a **critical-flag candidate**
> routed through the skill's existing critical-flag machinery (no new
> flag category) — see `anvil/lib/snippets/voice_grounding.md`
> §"Reviewer contract".

### 1. <!-- replace me: a framing or claim you refuse to make -->

<!-- replace me: why you refuse it; the tell that signals a draft is drifting toward it -->

### 2. <!-- replace me: a second anti-stance -->

<!-- replace me: why you refuse it; the drift tell -->

<!--
  replace me (add more): anti-stances are often more diagnostic than
  stances — they catch the drafts that sound plausible but aren't you.
-->

---

## Substrate

Background commitments you argue *from*, not positions you argue *for*. A
substrate item is the ground your audience assumes you stand on — a
disposition, value, or worldview so basic to your writing that you rarely
state it outright, yet a draft that quietly violates it reads as not-you.
Distinct from Stances (which you defend on the page) and from Anti-stances
(which you refuse): substrate is the assumed floor beneath both.

> **Cross-link to the critical-flag routing.** Like an anti-stance, a
> substrate item is a *judgment* concern, not a word-list. When the values
> tier is active, a passage that contradicts a declared substrate item is
> a **critical-flag candidate** routed through the skill's existing
> critical-flag machinery (no new flag category), and the reviewer (rubric
> dim 5) calibrates against the declared substrate alongside your stances
> and anti-stances — see `anvil/lib/snippets/voice_grounding.md`
> §"Reviewer contract".

### 1. <!-- replace me: a background commitment your audience assumes you hold — the ground you argue from, not a position you argue -->

<!-- replace me: two or three sentences on what the commitment is and how a draft would read if it quietly violated it -->

### 2. <!-- replace me: a second substrate item -->

<!-- replace me: expansion + the tell that a draft has drifted off it -->

<!--
  replace me (add more): substrate items are rarely stated outright in
  your corpus — they are the assumptions a careful reader infers. Naming
  them here gives the reviewer ground to catch the drafts that argue
  correctly but from the wrong floor.
-->

---

## Forming positions

Positions you are actively developing but have not fully published — the
half-formed arguments you are working toward. Declare them so the reviewer
treats a consistent-but-novel claim as a **positive signal**, not as
drift.

> **Positive signal for dim 5, not a violation.** Rubric dim 5 scores a
> forming position consistent with the values doc as *alignment*, not
> misalignment: a draft that advances a claim you have declared as forming
> is you thinking on the page, not you going off-voice. Without this
> section the reviewer has no way to tell a legitimate developing position
> from genuine drift, and may score consistent-but-novel material as a
> deduction.

### 1. <!-- replace me: a position you are developing but have not fully argued in your published corpus -->

<!-- replace me: two or three sentences on where the thinking currently stands and which direction it is moving -->

### 2. <!-- replace me: a second forming position -->

<!-- replace me: expansion -->

<!--
  replace me (add more): keep these honest — a forming position is one you
  are actually working toward, not a stance you already hold. Promote it to
  Stances (with an exemplar) once it settles.
-->

---

## Voice modes

The named registers you legitimately write in. Most authors move between a
few — a careful technical register, a looser observational one, a mode
that samples other voices — and a reviewer that knows only one of them
flags the others as drift. Name each mode with a one-line description so
the reviewer's register check calibrates against your actual range.

> **Dim 2 calibrates register against the declared modes.** The reviewer's
> voice-fidelity register check (rubric dim 2) tests a passage against the
> *declared* modes, not a single assumed voice — a register that matches a
> declared mode is on-voice even when it differs sharply from your default.
> In particular, **a declared sampling mode suppresses false anti-stance
> flags on sampled surface material**: when you have named a mode that
> quotes, echoes, or inhabits material you do not personally endorse
> (cultural sampling, satire, steelmanning an opposing view), the reviewer
> reads that surface as sampling rather than as a substrate / anti-stance
> violation. Without the declared mode the anti-stance critical flag fires
> on legitimate sampling.

### <!-- replace me: name a mode (e.g. a careful / technical register) -->

<!-- replace me: one line on when you write in it and how it reads -->

### <!-- replace me: a second mode (e.g. a looser observational register) -->

<!-- replace me: one line -->

### <!-- replace me: a sampling mode, if you use one — the register in which you quote or inhabit material you do not personally endorse -->

<!-- replace me: one line naming what kind of surface material this mode covers, so the reviewer reads it as sampling, not endorsement -->

<!--
  replace me (add more): a mode you never actually write in is noise —
  declare only the registers a reader would recognize across your corpus.
-->

---

## Standing

What you have **firsthand authority** to discuss versus what you'd cite
others for. The drift-out-of-standing check is one question:

> **Would your audience call you on this?**

If a sentence asserts firsthand authority on something your readers would
gently raise an eyebrow at, the draft has drifted out of standing — soften
to reference-level or cut it.

### Firsthand

<!--
  HOW TO FILL THIS. List the topics you can write about from direct
  experience — what you've actually built, run, shipped, or studied.
  When you describe these, you describe what you did.
-->

- <!-- replace me: a topic you have firsthand standing on -->
- <!-- replace me: another -->

### Reference-level

<!--
  HOW TO FILL THIS. List topics you engage with but should cite rather
  than claim as your own. Flag your moves as drawing on others.
-->

- <!-- replace me: a topic you cite rather than claim -->
- <!-- replace me: another -->

### Reference-scaffolding exemptions

<!--
  HOW TO FILL THIS. Rubric dim 4 asks that thinkers / concepts your
  audience may not know get a one-line orientation the first time they
  appear. That check is audience-relative: your specific readers already
  know some names cold, and orienting those insults them. List the
  thinkers / concepts / terms YOUR audience already knows so the reviewer
  does NOT flag a missing one-line orientation for them — this makes the
  dim 4 scaffolding check audience-aware.
-->

- <!-- replace me: a thinker / concept / term your specific audience already knows and therefore needs no one-line orientation -->
- <!-- replace me: another -->

---

## Voice signatures

Distinctive moves that recur in your prose — the patterns a careful
imitator would copy. The **reviser preserves these** when they appear and
the reviewer flags them when they've been smoothed away (the
read-and-preserve rule in `anvil/lib/snippets/voice_grounding.md`
§"Reviser contract"). Voice-grounded revision must not sand off the
persona while chasing rubric points.

### <!-- replace me: name a signature move (e.g. a structural device you favor) -->

<!-- replace me: describe the move -->

> <!-- replace me: a corpus quote that shows the move in action -->

### <!-- replace me: a second signature move -->

<!-- replace me: describe it -->

> <!-- replace me: a corpus quote -->

<!--
  replace me (add more): these are the load-bearing positives. The
  reviewer protects them; the reviser must not flatten them.
-->

---

## Failure modes the review should flag

Named recurring defects to watch for. These are **cross-dimensional** —
they apply across the rubric rather than living in one dimension — so the
reviewer surfaces them wherever they appear.

> **Cross-link to the deterministic gates (avoid duplication).** Some
> defects are the deterministic gates' job, not this doc's:
> deterministic word / em-dash / banned-phrase screening is the
> **rhetoric lint** (issue #463); claim/figure or example coherence and
> numeric consistency are **gate** concerns. List those failure modes
> here so the reviewer knows to look, but point at the gate rather than
> re-implement the count — the values doc and the gates should
> **reinforce**, not duplicate.

### <!-- replace me: name a judgment-side failure mode specific to your writing -->

<!-- replace me: what it looks like, how to catch it -->

### Convergence with the reviewing model's default voice

The biggest meta-failure mode of AI-assisted voice work. The more you and
the model write together, the more your voices drift toward each other.
The reviewer (which is the model) must actively resist drifting toward its
own default register — if it finds itself defending a move *it* would also
make, that is a flag, not a defense.

**Implementation hint:** at review time, ask "would I, the AI, also write
this sentence?" If yes, scrutinize it harder than the rest.

### Example / claim coherence (gate-reinforced)

A central worked example must physically support the abstract claim that
frames it. This is partly a **gate** concern — example-coherence and
numeric-consistency gates catch the mechanical cases; flag the judgment
cases here:

- <!-- replace me: a coherence trap specific to your domain (e.g. a framing that names a constraint the example doesn't actually depend on) -->
- The draft conflates distinct resources as if they were one.
- A closing image reaches for effect at the cost of plausibility.

Before scoring craft, restate the draft's central claim in one sentence
and its central example in another, then ask whether the example actually
needs what the claim says is the gate. If a sharp reader would catch the
gap in thirty seconds, it is a coherence problem regardless of how the
prose flows — and it routes to the relevant gate / critical-flag path,
not to a craft deduction.

---

<!--
  Maintenance note: keep this doc grounded in what you ACTUALLY think,
  not in what reads well. The corpus and any author interview inform it,
  but ground truth is your real positions. Update it freely as your
  stances sharpen — a stale values doc grounds the wrong persona.
-->
