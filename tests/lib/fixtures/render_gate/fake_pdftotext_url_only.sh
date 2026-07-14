#!/usr/bin/env bash
# Stub pdftotext for the non-rendered-URL regression (issue #692). The source
# (url_only_nonascii_source.md) carries 'é'/'ï' ONLY inside link/image URL
# targets, an HTML comment, and an autolink — none reach the rendered body. The
# rendered body text (what pandoc emits) shows only the visible link text and
# the resolved URL as an href, so this extraction has ZERO body non-ASCII. The
# glyph gate must NOT flag those URL/comment glyphs as drops. Args are ignored
# (the gate calls `pdftotext <pdf> -`).
cat <<'EOF'
See the caf page

Read more at the cafe page for details.
An image ref:
An autolink: https://ex.com/resume.
EOF
exit 0
