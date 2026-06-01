---
name: deck-imagegen
description: Generative-imagery command for the deck skill. Opt-in via `imagery_policy: generative-eligible` in BRIEF.md. Dispatches to a consumer-registered backend adapter, writes rendered PNGs into `<thread>.{N}/assets/`, and records every prompt + parameters into a prompt journal at `assets/_prompts.json`.
---

# deck-imagegen — Generative-imagery command (opt-in)

**Role**: generative-imagery dispatcher.
**Reads**: latest `<thread>.{N}/deck.md`, `<thread>/BRIEF.md` (for the `imagery_policy` opt-in + style preset), and the consumer-registered backend adapter (per `commands/deck-imagegen-adapter.md`).
**Writes**: PNG assets into `<thread>.{N}/assets/` and a prompt journal at `<thread>.{N}/assets/_prompts.json`.

Generative imagery is opt-in. Decks without `imagery_policy: generative-eligible` in `BRIEF.md` frontmatter are unaffected — `deck-imagegen` is a no-op (or a refusal) on those threads. The default policy is `deterministic-only`, which preserves the historical hybrid asset policy (Mermaid + matplotlib + consumer-provided assets; see `SKILL.md` § "Asset generation").

This command exists because aesthetic-craft venture categories (consumer products, lifestyle, art, hospitality, home, food, fashion) have hero/lifestyle imagery that is load-bearing for the investor visual landing. The consumer-extension framing (every consumer rebuilds from scratch) made the safety contracts — fabrication attribution, prompt-claim divergence audit — impossible to enforce at framework level. Shipping `deck-imagegen` as a first-class command lets `deck-audit` see the prompt journal, lets the drafter attribute generative slides as "concept render" automatically, and lets style coherence be checked across slides. See Epic #130 for the design rationale.

## Inputs

- **Thread slug** (positional argument).
- **Latest version directory**: highest `N` with `<thread>.{N}/deck.md`.
- **`<thread>/BRIEF.md`**: read frontmatter for `imagery_policy` (REQUIRED gate) and `imagery_style` (optional style preset key; see `commands/imagery-style-presets.md` when shipped per Epic #130 Phase 1C / issue #133).
- **`.anvil/config.toml`**: read `[deck.imagegen] backend` to discover the consumer-registered adapter. See `commands/deck-imagegen-adapter.md` for the adapter contract and registration mechanics.
- **`deck.md` imagery markers**: the drafter MAY annotate a slide that needs a generative asset with an HTML comment of the form `<!-- anvil-imagegen: <prompt-id> [style=<preset>] -->` immediately above the `![alt](assets/<prompt-id>.png)` reference. `<prompt-id>` is the asset's stable filename stem; `<style>` (optional) overrides the brief-level style preset for this single slide.

## Outputs

```
<thread>.{N}/
  assets/
    <prompt-id>.png           Rendered generative asset (PNG bytes from backend)
    _prompts.json             Prompt journal — append-only record of every dispatched generation
  _progress.json              phases.imagegen.state = done
```

The asset directory is the same `assets/` directory that holds consumer-provided imagery (logos, screenshots, team photos). Generative assets live alongside consumer-provided assets and follow the same `![alt](assets/<name>.png)` reference convention from `deck.md`. The prompt journal `_prompts.json` is the load-bearing artifact: `deck-audit` reads it to verify every generative asset is attributed; `deck-revise` reads it to avoid re-prompting the backend when re-rendering a slide that did not change.

The prompt-journal schema is defined by the Phase 2 prompt-journal primitive (Epic #130 Phase 2 / issue D) and is intentionally NOT specified in this command doc — that primitive lives at `anvil/lib/<TBD>` and is the canonical source. This command is a journal *consumer*, not a schema owner.

## Preconditions

The following gates MUST pass before `deck-imagegen` will dispatch any generation:

1. **Opt-in gate**: `<thread>/BRIEF.md` frontmatter MUST contain `imagery_policy: generative-eligible`. Any other value (or a missing field) is treated as `deterministic-only` — `deck-imagegen` refuses to run with a clear pointer to the opt-in mechanism. See `SKILL.md` § "Asset generation" and Epic #130 Phase 1B (issue #132) for the frontmatter contract.
2. **Adapter gate**: `.anvil/config.toml` MUST register a backend under `[deck.imagegen] backend = "<dotted.path>"`. Refer to `commands/deck-imagegen-adapter.md` for the adapter contract (the minimal `generate(prompt, style, steps) -> bytes` signature) and the registration mechanics. Anvil ships zero backends; backend selection is per-consumer.
3. **Latest-version gate**: a `<thread>.{N}/deck.md` MUST exist (the command runs after `deck-draft`, before `deck-figures`, OR in parallel with `deck-figures` on a different asset class).
4. **Imagery-marker gate**: at least one `<!-- anvil-imagegen: <prompt-id> -->` marker (or the brief-level equivalent for hero slides) MUST exist in `deck.md`. A deck with `imagery_policy: generative-eligible` but no markers is a no-op (warning in the run report; not an error).

When any precondition fails, the command surfaces the gap with a clear remediation pointer and exits without dispatching a single backend call — the failure must be legible at the command-line, not buried in a backend error.

## Postconditions

After a successful run:

1. Every `<!-- anvil-imagegen: <prompt-id> -->` marker in `deck.md` resolves to an actual `assets/<prompt-id>.png` file.
2. `assets/_prompts.json` records, for every dispatched generation: the prompt-id, the full prompt string sent to the backend, the style preset used, the steps parameter (if any), the backend identifier, an ISO-8601 UTC timestamp, and the bytes-length / image dimensions of the returned PNG. The schema is owned by the Phase 2 prompt-journal primitive.
3. `_progress.json` records `phases.imagegen.state = done` with `started` / `completed` ISO-8601 UTC timestamps per `anvil/lib/snippets/progress.md`.
4. `deck-audit` (per Epic #130 Phase 3 / issue G) can read the journal and verify every generative asset is attributed in `deck.md` (e.g., the slide carries a "concept render" caption — see Phase 3 / issue F).

## Procedure

1. **Discover state**: find the highest `N` with `<thread>.{N}/deck.md`. Read `<thread>/BRIEF.md` frontmatter and `.anvil/config.toml`.
2. **Run preconditions** (in order — short-circuit on first failure):
   - Read `imagery_policy` from BRIEF.md frontmatter. If absent or != `generative-eligible`, surface the opt-in pointer and exit cleanly (`phases.imagegen.state = skipped`, exit 0 — this is not a failure; the deck simply isn't on the generative-imagery path).
   - Read `[deck.imagegen] backend` from `.anvil/config.toml`. If absent, surface the adapter-contract pointer (`commands/deck-imagegen-adapter.md`) and exit failed.
   - Enumerate `<!-- anvil-imagegen: <prompt-id> -->` markers in `deck.md`. If zero, emit a warning ("imagery_policy is generative-eligible but no imagery markers found in deck.md") and exit cleanly (`phases.imagegen.state = done`, no-op).
3. **Load adapter**: import the dotted path from config and verify it is a callable / class instance matching the `ImageBackend` protocol. See `commands/deck-imagegen-adapter.md` for what "matching" means.
4. **Resolve prompts**: for each marker, resolve the prompt text. The drafter is expected to have written the prompt body into `speaker-notes.md` under a "Imagery prompt" subsection for that slide, OR into a sibling `assets/<prompt-id>.prompt.md` file. The exact prompt-resolution contract is specified by the Phase 2 implementation (issue E); v0 spec only requires that prompts are NOT inferred from slide body text (anvil refuses to fabricate prompts).
5. **Initialize `_progress.json`**: `phases.imagegen.state = in_progress`, `phases.imagegen.started = <ISO>`.
6. **Dispatch generations**: for each `<prompt-id>`, in markdown order:
   - Resolve the style preset (slide-level marker overrides brief-level frontmatter overrides `default`).
   - Resolve the `steps` parameter (slide-level marker overrides brief-level frontmatter overrides `None` — backend's default).
   - Call `adapter.generate(prompt, style, steps)`. On `BackendError`, write a stub `assets/<prompt-id>.png-FAILED.md` describing the error and the prompt, leave any prior PNG in place, and continue with the next prompt.
   - On success: write the returned bytes to `assets/<prompt-id>.png`. Append a journal entry to `assets/_prompts.json` (the Phase 2 primitive handles read-merge-write).
7. **Validate references**: re-walk `deck.md` and verify every `<!-- anvil-imagegen: <prompt-id> -->` marker resolves to an actual `assets/<prompt-id>.png` (or a `assets/<prompt-id>.png-FAILED.md` stub). Both are legible; a silently-absent asset is the failure mode this validation prevents.
8. **Update `_progress.json`**: `phases.imagegen.state = done` (or `failed` if any blocker fired), `phases.imagegen.completed = <ISO>`.
9. **Report**: one-line status (e.g., `Generated 3 assets for acme-seed.2/ (3 dispatched, 0 failed; 1.4MB written; brand-A preset; brief gate: generative-eligible)`).

## Failure modes

| Failure | Surface | Exit |
|---|---|---|
| `imagery_policy` absent or `deterministic-only` | One-line note pointing at SKILL.md § "Asset generation" and the BRIEF.md frontmatter contract | clean (`phases.imagegen.state = skipped`) |
| `imagery_policy: generative-eligible` but no `[deck.imagegen] backend` in `.anvil/config.toml` | One-line note pointing at `commands/deck-imagegen-adapter.md` | failed |
| `imagery_policy: generative-eligible` but no `<!-- anvil-imagegen -->` markers in `deck.md` | Warning (deck is gated but has no imagery to generate) | clean (`phases.imagegen.state = done`, no-op) |
| Adapter import fails (dotted path invalid, class missing `generate`) | Stack trace + pointer to `commands/deck-imagegen-adapter.md` § "Adapter contract" | failed |
| `adapter.generate(...)` raises `BackendError` for one or more prompts | `assets/<prompt-id>.png-FAILED.md` stub per failed prompt; the command continues with the remaining prompts | partial (`phases.imagegen.state = done`, exit non-zero) |
| Adapter returns non-PNG bytes (no PNG signature) | `assets/<prompt-id>.png-FAILED.md` stub describing the type mismatch | partial |
| Prompt cannot be resolved (no `speaker-notes.md` entry, no `assets/<prompt-id>.prompt.md` file) | Refuse to dispatch; emit a `[blocker]` describing the missing prompt source | failed (no fabrication — anvil does not invent prompts from slide body) |

The command never retries on `BackendError`. Retry/backoff is the consumer's responsibility per the adapter contract (see `commands/deck-imagegen-adapter.md` § "Non-goals").

## Cross-references

- `commands/deck-imagegen-adapter.md` — adapter contract (minimal `generate()` signature, consumer registration via `.anvil/config.toml`, explicit non-goals).
- `SKILL.md` § "Asset generation" — the opt-in framing and the `imagery_policy` contract.
- `commands/imagery-style-presets.md` (Epic #130 Phase 1C / issue #133) — the style-preset library (keys + prompt-prefix definitions).
- Epic #130 — the multi-phase plan that ships `deck-imagegen`, the prompt-journal primitive, the fabrication-contract drafter prompts, and the `deck-audit` extension.
- `commands/deck-figures.md` — the deterministic figure pipeline; `deck-imagegen` is a *parallel* asset path, not a replacement.
- `commands/deck-audit.md` — Phase 3 (Epic #130 / issue G) extends the auditor with three new findings: `unattributed-generative-imagery`, `prompt-claim-divergence`, `style-incoherence`.

## When to run

- **After `deck-draft`** (or any revise that introduces new imagery markers): the drafter MUST have placed the `<!-- anvil-imagegen -->` markers and written the prompt sources before `deck-imagegen` can dispatch.
- **Before `deck-figures`** OR **in parallel with `deck-figures`**: `deck-imagegen` writes to `assets/`; `deck-figures` reads `figures/` and renders the final PDF. The two commands touch disjoint asset directories and can run concurrently. `deck-figures` MUST run after `deck-imagegen` to pick up the rendered PNGs in the final PDF.
- **Idempotence**: re-running on a thread where every marker already resolves to an existing PNG AND the corresponding journal entry's prompt+style+steps matches the current source is a no-op (no backend dispatch). This is the load-bearing reason for the prompt journal — `deck-revise` re-runs `deck-imagegen` after touching the deck, but slides whose imagery contract did not change cost zero backend calls.

## Backwards compatibility

Decks without `imagery_policy: generative-eligible` are byte-identical to today's behavior. The `imagery_policy` field is OPTIONAL in BRIEF.md frontmatter; absence defaults to `deterministic-only`. Existing threads continue to use the hybrid asset policy (Mermaid + matplotlib + consumer-provided assets) with no changes required. See Epic #130 for the explicit backwards-compat decision.

## `_progress.json` snippet

```json
{
  "phases": {
    "imagegen": { "state": "done", "started": "<ISO>", "completed": "<ISO>" }
  }
}
```

Merge rule: preserve all other phases. This command only touches `phases.imagegen`.

**Snippet references**: See `anvil/lib/snippets/progress.md` for the `_progress.json` read-merge-write recipe and `anvil/lib/snippets/timestamp.md` for the ISO-8601 UTC timestamp convention. The merge is shallow: preserve fields and phases not touched by this command.
