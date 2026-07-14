#!/usr/bin/env bash
# A stub `pdfimages -list` reporting TWO embedded images — the clean case for a
# body that references two figures (two_image_refs_source.md). The
# embedded-image assertion must pass (2 >= 2). Args are ignored (the gate
# calls `pdfimages -list <pdf>`).
cat <<'EOF'
page   num  type   width height color comp bpc  enc interp  object ID x-ppi y-ppi size ratio
-------------------------------------------------------------------------------------------
   1     0 image    1600   900  rgb     3   8  jpeg   no        12  0   150   150 42.1K 3.2%
   2     1 image    1600   900  rgb     3   8  jpeg   no        27  0   150   150 40.8K 3.1%
EOF
exit 0
