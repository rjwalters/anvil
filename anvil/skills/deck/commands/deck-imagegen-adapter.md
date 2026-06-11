---
name: deck-imagegen-adapter
description: Adapter contract for `deck-imagegen`. Defines the minimal `ImageBackend.generate(prompt, style, steps) -> bytes` signature, the consumer registration mechanism via `.anvil/config.toml`, and the explicit non-goals (retry, rate-limit, deterministic seeds, auth) that remain consumer responsibilities.
---

# deck-imagegen-adapter — Adapter contract

This document is the **contract** between `deck-imagegen` (anvil's generative-imagery dispatcher) and a consumer-supplied image backend. Anvil ships zero *production* backends — only this contract plus one deterministic placeholder reference backend (`anvil/skills/deck/lib/placeholder_backend.py`, see § "Reference adapters" below) that exists to prove the wiring. Consumers register their own adapter via `.anvil/config.toml`; `deck-imagegen` imports it dynamically and calls it. For a worked walkthrough (smoke test, importability layouts, auth bootstrap, porting checklist), see `commands/deck-imagegen-onboarding.md`.

The contract is intentionally thin. Anvil's responsibility ends at "dispatch the call, surface the error, write the journal." Everything else — retry, rate limits, deterministic seeds, auth, secrets, model selection, cost accounting, prompt augmentation — is the consumer's responsibility. This is the same opinion-vs-mechanism split that produces `pyproject.toml`'s subprocess-only-by-default contract (see CLAUDE.md § "Working on this repo") and `anvil/lib/render.py`'s `check_*_available()` family.

The thinness is load-bearing. A fatter contract (built-in retry, built-in rate-limit, built-in seed control) means anvil ships behavior that interacts with backend-specific failure modes in ways anvil cannot test or maintain across the long tail of backends (DALL-E, Midjourney, Stable Diffusion, Replicate, Together, fal, in-house GPU pods, …). Keeping the surface to a single `generate(prompt, style, steps) -> bytes` call makes the consumer's job clear, makes anvil's audit story tractable (the journal records what was sent and what came back; the backend is opaque), and makes the contract testable with a five-line mock.

## Adapter contract

A backend is a Python object (class instance or module) exposing a single method:

```python
class ImageBackend:
    def generate(
        self,
        prompt: str,
        style: str,
        steps: int | None,
    ) -> bytes:
        """Generate an image from a prompt and return PNG bytes.

        Args:
            prompt: Full prompt string as resolved by deck-imagegen
                    (style preset is already prepended; this is the
                    final string the backend should send to its model).
            style: Style preset key (e.g., "brand-photo-a",
                   "concept-render-warm"). The backend MAY use this for
                   logging, model routing, or LoRA selection; or MAY
                   ignore it entirely (the prompt already includes the
                   preset's prompt prefix). Empty string when no preset
                   is configured.
            steps: Inference-step count when the backend exposes one
                   (typical for diffusion models). None means "use the
                   backend's default."

        Returns:
            PNG-encoded image bytes. Must start with the PNG signature
            (\\x89PNG\\r\\n\\x1a\\n). Non-PNG bytes cause deck-imagegen
            to write a *-FAILED.md stub and surface the type mismatch.

        Raises:
            BackendError: Any condition that prevented producing valid
                          PNG bytes. The message becomes the body of
                          the *-FAILED.md stub. deck-imagegen does NOT
                          retry.
        """
        ...
```

A backend MAY be a callable (a plain function with the same signature) instead of a class instance — the contract is duck-typed: `deck-imagegen` calls `adapter.generate(...)` if the resolved object has a `generate` attribute, otherwise it calls `adapter(...)` directly. The class form is documented because it is the recommended shape (lets the adapter hold state like an HTTP client instance across calls).

### BackendError

```python
class BackendError(Exception):
    """Raised by an adapter when generation cannot produce valid bytes.

    Any condition the backend cannot recover from: network failure
    after the consumer's retry budget is exhausted, content-policy
    refusal, model timeout, invalid prompt, auth failure, rate-limit
    rejection after the consumer's backoff is exhausted, etc.

    deck-imagegen catches BackendError per-prompt, writes a
    <prompt-id>.png-FAILED.md stub with the exception's str() as the
    body, and continues with the next prompt. It does NOT retry.
    """
```

Adapters MAY define `BackendError` themselves or import the canonical version that the Phase 2 implementation (Epic #130 / issue E) ships under `anvil/lib/` once the command lands. v0 contract: any exception type with `BackendError` in its MRO is caught as a backend error; bare `Exception` subclasses propagate (and fail the command). This decision keeps the contract decoupled from import order — a consumer adapter can define its own `BackendError` symbol without importing anvil internals.

## Consumer registration

The consumer registers their adapter via `.anvil/config.toml` at the repo root:

```toml
[deck.imagegen]
backend = "myrepo.imagery_adapter:MyBackend"
```

The `backend` value is a dotted Python path of the form `<module>:<attribute>`, mirroring the convention used by `entry_points` in `pyproject.toml` (Python packaging norm) and `gunicorn` / `uvicorn` app references. `deck-imagegen` does `importlib.import_module` on the module, then `getattr` on the attribute. The attribute can resolve to:

- An instance of a class with a `generate` method (recommended; lets the adapter hold state like an HTTP client).
- A class — `deck-imagegen` calls it with zero arguments to construct an instance, then calls `generate` on the instance.
- A plain function with the `generate` signature — `deck-imagegen` calls it directly.

The full resolution algorithm and edge cases (TOML parse errors, missing module, missing attribute, attribute not callable) are specified by the Phase 2 implementation (Epic #130 / issue E). v0 contract: this doc specifies the *shape* of the registration; it does not enumerate every error path.

### Why `.anvil/config.toml`

This is a file in the consumer-side `.anvil/` overlay (parallel to `.anvil/skills/`, `.anvil/lib/`, etc.). It was the first instance of a TOML-shaped config in anvil; per-skill JSON overrides like `<thread>/.anvil.json` (the `target_length` / `max_iterations` precedent) remain unchanged.

**Consolidation pending**: newer skill-level configuration has since standardized on the versioned `.anvil/config.json` (the #426 hooks precedent; reaffirmed by the #427 figure-adapter registry decision). The `[deck.imagegen] backend` key is explicitly **grandfathered** in `.anvil/config.toml` — it remains the correct, supported registration location until a separate maintenance issue ships the TOML→JSON consolidation with a migration note. Do not add new skill config sections to the TOML file.

## Non-goals (consumer responsibility)

Anvil's contract ends at "dispatch the call, surface the error, write the journal." The following concerns are intentionally **out of scope** for anvil — they are the consumer adapter's responsibility:

### Retry / backoff

The adapter's `generate` method either returns valid PNG bytes or raises `BackendError`. `deck-imagegen` does NOT retry on `BackendError` — it writes a `*-FAILED.md` stub and moves on. If the consumer wants retry on transient network errors, the consumer's adapter implements it internally (wrap the underlying HTTP call in `tenacity.retry` or similar; raise `BackendError` only when the retry budget is exhausted). Anvil cannot ship a one-size-fits-all retry policy because retry semantics are backend-specific: a 429 from one provider means "back off N seconds" with a `Retry-After` header; from another provider it means "your auth is bad, never retry." Encoding any of this in anvil would be a bug for at least half the backends.

### Rate limiting

Same logic. If the consumer's backend has a 10-requests-per-minute quota, the consumer's adapter holds the rate-limiter state (token bucket, sliding window, whatever). `deck-imagegen` dispatches prompts serially in markdown order; the consumer adapter is free to add delay between calls or implement client-side throttling. Anvil cannot ship a default rate limit because the quota varies by provider, plan tier, and model. The serial-dispatch order is the only rate-limit-adjacent guarantee anvil makes.

### Deterministic seeds

Reproducibility — "run `deck-imagegen` twice with the same prompt and get the same PNG bytes" — is the consumer adapter's responsibility. The `generate` signature does not include a `seed` parameter because seed semantics are model-specific: Stable Diffusion accepts an integer seed and is deterministic; DALL-E 3 does not expose a seed at all; Midjourney exposes a job-level `--seed` flag with its own semantics. If the consumer wants reproducibility, the adapter holds the seed (or derives it from the prompt hash) and passes it through to the underlying model. The prompt journal records the prompt+style+steps that were dispatched — that record is anvil's reproducibility guarantee. The bytes-level reproducibility is the consumer's.

### Auth / secrets / API keys

`deck-imagegen` reads `.anvil/config.toml` to discover the adapter and nothing else. It does not read environment variables for API keys, does not source `.env` files, does not handle OAuth flows, does not negotiate auth headers. The consumer adapter reads `os.environ` (or a secrets manager, or a `keyring`, or whatever the consumer prefers) and constructs the authenticated HTTP client itself. Encoding any auth machinery in anvil would either pick one provider's auth shape (and break the rest) or ship a pluggable auth layer that is itself a fatter contract than `generate(prompt, style, steps) -> bytes`. The minimal contract sidesteps the entire decision.

### Model selection

`deck-imagegen` does not specify which underlying model the adapter calls. A consumer's adapter might call DALL-E 3, or Stable Diffusion XL, or a fine-tuned LoRA, or route by style preset (brand photos → SDXL, concept renders → DALL-E) — none of that is anvil's business. The `style` parameter is a hint the adapter MAY use for routing; it is not a model selector.

### Cost accounting

The adapter is free to log per-call cost (count tokens, estimate API spend, write to a billing ledger). Anvil does not record cost in the prompt journal because cost is provider-specific (per-image, per-megapixel, per-step, per-token, free tier vs paid tier) and rapidly stale. Consumers who care about cost instrument their adapter; `_prompts.json` records what was sent, not what it cost.

### Prompt augmentation beyond the style preset

The style preset's prompt prefix is prepended to the user-authored prompt by `deck-imagegen` before the adapter is called (the resolution happens in step 4 of `deck-imagegen.md` § "Procedure"). Any further augmentation — adding negative prompts, appending model-specific quality tags, injecting LoRA references, applying ControlNet conditioning — is the adapter's responsibility. The adapter receives the fully-resolved prompt string; what it sends to the underlying model is its own concern.

## What anvil DOES provide

For clarity, the symmetric list — anvil's responsibilities in this contract:

1. **Adapter discovery**: read `[deck.imagegen] backend` from `.anvil/config.toml`, import the dotted path, verify the resulting object has a `generate` method (or is callable).
2. **Prompt resolution**: prepend the style preset's prompt prefix to the user-authored prompt before calling `generate`. The adapter receives the final string.
3. **Dispatch order**: call `generate` once per `<!-- anvil-imagegen: <prompt-id> -->` marker in `deck.md`, in markdown order, serially. (Backends that benefit from concurrency MUST batch internally; anvil does not parallelize.)
4. **Error containment**: catch `BackendError` per-prompt; write `<prompt-id>.png-FAILED.md` stubs; continue with remaining prompts.
5. **Journal write**: append every dispatched generation (prompt-id, prompt, style, steps, backend identifier, timestamp, returned bytes-length, returned dimensions) to `assets/_prompts.json` via the Phase 2 prompt-journal primitive.
6. **PNG validation**: verify the returned bytes start with the PNG signature (`\\x89PNG\\r\\n\\x1a\\n`). Non-PNG bytes produce a `*-FAILED.md` stub.

That is the entire surface. Six responsibilities; one method on the adapter.

## Reference adapters

### Shipped: deterministic placeholder backend

Anvil ships one reference adapter (issue #430): `anvil/skills/deck/lib/placeholder_backend.py`, exposing `PlaceholderBackend` in the recommended class form (zero-arg constructor). It is the executable spec of this contract:

- `generate(prompt, style, steps)` returns a valid 1280x720 solid-color PNG whose color derives from `sha256(prompt + style + str(steps))` — fully deterministic and byte-identical across runs, which makes the prompt-journal idempotence story observable end-to-end.
- Stdlib only (`hashlib`/`zlib`/`struct`); no Pillow, no new deps.
- A prompt containing the sentinel token `ANVIL-FORCE-FAIL` raises `BackendError`, giving a one-line way to exercise the `*-FAILED.md` stub + `partial` verdict path against a real registered adapter.
- It defines its own local `BackendError` (not imported from anvil internals), modeling the MRO-name decoupling rule above.

Register it for the five-minute smoke test (`commands/deck-imagegen-onboarding.md` § "Five-minute smoke test"):

```toml
[deck.imagegen]
backend = "anvil.skills.deck.lib.placeholder_backend:PlaceholderBackend"
```

It is NOT a production backend — it generates placeholder rectangles, not imagery. Its job is to de-risk a consumer's first adapter and to let anvil's tests cover the full `load_config → importlib → dispatch → journal` path.

### Illustrative: cloud HTTP backend sketch (NOT shipped)

No production/cloud backend is shipped in anvil. Studio's in-progress `imagine.spheresemi.xyz` adapter (per Epic #130's Risks & Considerations) is the closest existing reference but is NOT part of this contract — anvil-side work MUST NOT assume that adapter exists. Consumers writing a first cloud adapter can model the shape from this minimal example (for the short-lived-token auth-bootstrap variant, see `commands/deck-imagegen-onboarding.md` § "Auth bootstrap for cloud backends"):

```python
# myrepo/imagery_adapter.py
import os
import requests

class BackendError(Exception):
    pass

class MyBackend:
    def __init__(self):
        self.api_key = os.environ["MY_PROVIDER_API_KEY"]   # consumer's auth
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {self.api_key}"

    def generate(self, prompt: str, style: str, steps: int | None) -> bytes:
        try:
            resp = self.session.post(
                "https://api.my-provider.example/v1/images",
                json={"prompt": prompt, "style": style, "steps": steps},
                timeout=120,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise BackendError(f"my-provider API error: {exc}") from exc
        body = resp.content
        if not body.startswith(b"\\x89PNG"):
            raise BackendError("my-provider returned non-PNG bytes")
        return body
```

Registered via `.anvil/config.toml`:

```toml
[deck.imagegen]
backend = "myrepo.imagery_adapter:MyBackend"
```

That is the entire adapter. ~20 lines of Python; one HTTP call; one exception type. The consumer can add retry, rate-limit, seed pinning, model routing, and cost accounting incrementally — none of which require changing the contract.

## Cross-references

- `commands/deck-imagegen-onboarding.md` — the consumer **walkthrough** (smoke test with the shipped placeholder backend, importability layouts, auth bootstrap, porting checklist). This doc is the contract; that doc is the on-ramp.
- `commands/deck-imagegen.md` — the command that loads and dispatches adapters per this contract.
- `SKILL.md` § "Asset generation" — the opt-in framing (`imagery_policy: generative-eligible`).
- Epic #130 — the multi-phase plan. Phase 2 (issue E) ships the canonical `BackendError` and `_prompts.json` primitive; Phase 3 (issues F + G) wires the fabrication-attribution drafter prompts and the `deck-audit` extension.
- CLAUDE.md § "Working on this repo" — the "Add Python deps only when subprocess won't do" principle that motivates the thin-adapter design.
