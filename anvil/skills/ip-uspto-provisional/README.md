# anvil:ip-uspto-provisional

USPTO **provisional** patent application drafting skill — the claims-optional, enablement-depth-first sibling of `anvil:ip-uspto` (issue #433). A provisional's only legal job is to attach a §119(e) priority date to what it discloses at §112(a) depth; this skill exists to refuse to bless a thin disclosure.

## Quick overview

- **Artifact**: provisional patent application — specification + drawings (claims optional; an encouraged claim-seed raises conversion readiness, its absence is never penalized). No abstract, no 37 CFR 1.77(b) formal regime, no examination.
- **Pattern**: `intake (reuse ip-uspto-intake) → draft → (review + s112 + priorart) → revise → loop → READY`.
- **Rubric**: `anvil-ip-provisional-v1` — 9 dimensions, **/45**, threshold **≥39**, enablement-depth-dominant (dim 1 *§112(a) enablement depth* at weight 8; dim 9 *Conversion readiness* replaces ip-uspto's *Claim-spec correspondence*). `s112` critical flags short-circuit.
- **Renderer**: LaTeX via `anvil-uspto.cls`, **reused from `anvil/skills/ip-uspto/assets/`** (install the two skills together: `--skills=ip-uspto,ip-uspto-provisional`). The drafter copies the class into each version dir so versions compile standalone.
- **Scorecards**: `machine-summary` kind; every critic stamps `rubric_id` / `rubric_total` / `advance_threshold` (issue #346) and writes atomically via `anvil/lib/sidecar.py::staged_sidecar`.

## Lifecycle diagram

```
        ┌── ip-uspto-intake (reused from anvil:ip-uspto) ──┐
        │            <thread>/BRIEF.md                     │
        └────────────────────┬──────────────────────────────┘
                             ▼
        ┌──── ip-uspto-provisional-draft ────┐
        │  thread.1/ (spec + drawings,       │
        │  optional claim-seed; no abstract) │
        └────────────────────┬───────────────┘
                             ▼
        ┌──────── parallel critic fan-out ────────┐
        │  ip-uspto-provisional-review            │
        │  ip-uspto-provisional-112  (load-bearing)│
        │  ip-uspto-provisional-prior-art         │
        │  → thread.{N}.<tag>/ each               │
        └────────────────────┬────────────────────┘
                             ▼
        ┌──── ip-uspto-provisional-revise ────┐
        │  aggregate ≥39/45 + no flag?        │
        │  → READY (Phase 1 terminal)         │
        │  otherwise → thread.{N+1}/          │
        └─────────────────────────────────────┘
```

## Phase 1 scope (issue #433)

Shipped: skill skeleton, `anvil-ip-provisional-v1` rubric, orchestrator + draft/review/112/prior-art/revise convergence loop.

Tracked follow-ups (per the issue #433 curation): counsel-memo companion + COUNSEL-READY terminal state and the filing package; the audit command (`AUDITED` state is defined but not yet reachable via shipped commands); non-provisional conversion linkage (priority-claim text, 12-month deadline surfacing); provisional pre-flight, figures/vision adaptation, inventorship-lite, claims-seed critic; `anvil:project-migrate` enrollment of native provisional threads; snippet-promotion of prose duplicated with `anvil:ip-uspto`.

## Important caveats

This skill does not file anything and does not replace a licensed patent attorney. The prior-art critic only evaluates operator-supplied art. See `SKILL.md` for the full contract.
