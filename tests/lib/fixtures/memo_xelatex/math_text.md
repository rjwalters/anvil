---
title: "amsmath \\text{} math reproducer"
author: "Anvil framework tests"
date: "2026-06-17"
---

# Reproducer for issue #592

This fixture exercises markdown math that pandoc converts to LaTeX using
amsmath-only commands. Without `\usepackage{amsmath}` in the template
preamble, xelatex fails with `Undefined control sequence` at `\text`
(exit 43). With it, the chain compiles cleanly.

## Inline math with `\text{}` (requires `amsmath` via `amstext`)

The effective field is denoted $B_{\text{eff}}$ inline, a multi-letter
subscript pandoc emits as `\text{eff}` inside math mode.

## Display math with `\text{}` and `\frac`

$$B_{\text{eff}} \approx B \cdot \frac{k}{E}$$

## Symbols from amssymb (mathbb, lesssim)

The constant lives in $\mathbb{R}$ and the bound is $k \lesssim E$ — both
`\mathbb` and `\lesssim` come from `amssymb`, the documented next failure
in this class.
