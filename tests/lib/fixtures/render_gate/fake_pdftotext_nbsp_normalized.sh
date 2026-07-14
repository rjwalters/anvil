#!/usr/bin/env bash
# Stub pdftotext for the NBSP-normalization regression (issue #692). The source
# (nbsp_only_source.md) carries a stray U+00A0 non-breaking space; pdftotext
# normalizes it to an ASCII space in its extraction, so this output has ZERO
# non-ASCII codepoints. The glyph gate must NOT flag the NBSP as a drop. Args
# are ignored (the gate calls `pdftotext <pdf> -`).
cat <<'EOF'
The price is 10 dollars

The value is 10 dollars per unit, with no other non-ASCII glyphs.
A stray non-breaking space (U+00A0) sits between "10" and "dollars" above.
EOF
exit 0
