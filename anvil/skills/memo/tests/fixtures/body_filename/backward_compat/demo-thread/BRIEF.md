# BRIEF — demo-thread (backward-compat fixture)

Minimal investment-memo brief used by the body_filename backward-compat
fixture (issue #279). This thread has NO `.anvil.json`, so the body
filename resolution path takes the default `memo.md` route — exactly the
behavior every memo thread written before issue #279 shipped saw.

The fixture exists to lock the backward-compat contract: a thread with
no `body_filename` declaration MUST continue to use `memo.md` with zero
behavioral change.

## Recommendation target

Invest, $500K seed.
