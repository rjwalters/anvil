#!/usr/bin/env bash
# A stub pdfinfo that always reports 50 pages. Used to exercise the
# page_cap=None first-class skip path.
cat <<EOF
Title:          Long PDF
Producer:       FakePDF/1.0
Pages:          50
PDF version:    1.5
EOF
exit 0
