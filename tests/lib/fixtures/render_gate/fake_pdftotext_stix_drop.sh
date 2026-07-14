#!/usr/bin/env bash
# Regression-pin fixture (issue #692): a stub pdftotext whose extraction has
# SILENTLY DROPPED the ≠ (U+2260) glyph that STIX Two Text failed to render,
# while keeping the × (U+00D7) glyph. The source
# (stix_glyph_drop_source.md) contains ≠ three times and × once; this
# extraction contains ≠ ZERO times and × once — the exact shape of the botho
# canary's silent glyph drop. Args are ignored (the gate calls
# `pdftotext <pdf> -`).
cat <<'EOF'
Why a  b

This section explains the inequality a  b and the product a × b.
The relation a  b holds whenever the two quantities differ.
EOF
exit 0
