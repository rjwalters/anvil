#!/usr/bin/env bash
# Regression-pin fixture (issue #692): a stub `pdfimages -list` for the botho
# v2 PDF that shipped with ZERO embedded images while every other gate was
# green. Prints only the two-line header (column names + dashed rule) with no
# data rows — the exact "zero embedded images" shape the embedded-image
# assertion must catch. Args are ignored (the gate calls
# `pdfimages -list <pdf>`).
cat <<'EOF'
page   num  type   width height color comp bpc  enc interp  object ID x-ppi y-ppi size ratio
-------------------------------------------------------------------------------------------
EOF
exit 0
