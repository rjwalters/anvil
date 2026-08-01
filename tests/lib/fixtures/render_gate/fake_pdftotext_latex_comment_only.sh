#!/usr/bin/env bash
# Stub pdftotext for the LaTeX-comment-only non-ASCII regression (issue #856).
# The source (latex_comment_only_nonascii_source.tex) carries box-drawing
# dashes (U+2500) and an accented 'é' ONLY inside `%%`-prefixed LaTeX comment
# lines (a section-rule banner + a reviewer note) — neither reaches the
# rendered PDF body. This extraction has ZERO non-ASCII, mirroring what
# xelatex/pdftotext would actually emit for this body. The glyph gate must
# NOT flag the comment-only box-drawing/accented glyphs as drops. Args are
# ignored (the gate calls `pdftotext <pdf> -`).
cat <<'EOF'
The Item Pool

This section explains the item pool structure in plain ASCII prose.
EOF
exit 0
