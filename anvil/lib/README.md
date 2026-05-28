# anvil/lib/

Framework code that skills consume. Planned as Python.

## Planned modules

| Module | Responsibility |
|---|---|
| `progress.py` | `_progress.json` reader/writer; phase state (`pending`/`in_progress`/`done`/`failed`); validate-by-file (existence-based) rather than flag-based |
| `rubric.py` | 8-dimension scoring schema, convergence logic (≥32/40, ≥35/40 for legal/customer-facing), critical-flag short-circuit |
| `state_machine.py` | `EMPTY → DRAFTED → REVIEWED → REVISED → … → READY → AUDITED` transitions, with skill-specific extensions |
| `version_layout.py` | `{thread}.{N}/` directory naming, sibling critic dir naming (`.review/`, `.audit/`, `.critic/`, ...), `N+1` allocation |
| `critics.py` | "N parallel critics, one reviser" orchestration — discover sibling critic dirs, assemble combined input for reviser |

None of these exist yet. The framework `lib/` will be extracted from observed duplication after the first few skill implementations land — do not design it up-front.
