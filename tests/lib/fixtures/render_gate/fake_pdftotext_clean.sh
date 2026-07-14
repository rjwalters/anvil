#!/usr/bin/env bash
# A stub pdftotext whose extraction preserves EVERY non-ASCII glyph present in
# stix_glyph_drop_source.md (≠ three times, × once) — the clean-render case
# where the glyph-verification gate must pass with zero findings. Args are
# ignored (the gate calls `pdftotext <pdf> -`).
cat <<'EOF'
Why a ≠ b

This section explains the inequality a ≠ b and the product a × b.
The relation a ≠ b holds whenever the two quantities differ.
EOF
exit 0
