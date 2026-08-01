#!/usr/bin/env bash
# Stub pdftotext for the comment-vs-body glyph-drop regression (issue #856).
# The source (latex_comment_and_body_nonascii_source.tex) carries box-drawing
# dashes / accented 'é' inside `%%` comment lines (never rendered) AND a
# genuine in-body ≠ (U+2260) used twice in real prose (a silently dropped
# glyph, e.g. a fontspec fallback). This extraction has ZERO occurrences of
# ≠ — proving comment-stripping does not swallow a real glyph drop; the gate
# must still flag U+2260 as missing. Args are ignored (the gate calls
# `pdftotext <pdf> -`).
cat <<'EOF'
The Item Pool

This section explains the inequality a  b in plain body text.
The relation a  b holds whenever the two quantities differ.
EOF
exit 0
