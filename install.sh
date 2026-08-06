#!/usr/bin/env bash
# install.sh - Entry point shim for the Anvil installer (issue #894 — C1).
#
# A caller need not know Anvil's internal script layout
# (scripts/install-anvil.sh) to install it into a consumer repo; this thin
# delegator is the documented, stable entry point. See
# scripts/install-anvil.sh for the full option/usage reference (--help).
set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/install-anvil.sh" "$@"
