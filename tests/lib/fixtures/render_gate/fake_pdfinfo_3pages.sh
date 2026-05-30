#!/usr/bin/env bash
# A stub pdfinfo that always reports 3 pages. Used to exercise the page-fit
# gate without requiring real poppler-utils.
cat <<EOF
Title:          Test PDF
Producer:       FakePDF/1.0
CreationDate:   Thu May 29 00:00:00 2026
Pages:          3
Encrypted:      no
Page size:      612 x 792 pts (letter)
File size:      12345 bytes
PDF version:    1.5
EOF
exit 0
