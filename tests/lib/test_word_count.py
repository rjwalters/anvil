from anvil.lib.rhetoric_lint import lint_rhetoric
from anvil.lib.word_count import count_words, essay_word_count

DOC = """---
title: x
---
# The Title Here

Intro with a [linked phrase](https://example.com/a/very/long/url) and `code`.

## A Heading

<!-- hidden comment words -->
```
code block words
```
![alt text](img.png)
Visit https://example.com now — it's well-known.
"""


def test_canonical_method():
    # Intro(9: Intro with a linked phrase and code) wait: counted below
    # Intro with a linked phrase and code =7 ; A Heading =2 ; Visit now it's well-known =4
    assert essay_word_count(DOC) == 13


def test_title_toggle():
    assert essay_word_count(DOC, include_title=True) == 13 + 3


def test_dash_and_markup_not_words():
    assert count_words("a — b * c > d - e") == 5


def test_link_text_spanning_wrap():
    assert essay_word_count("see [two\nwords](http://x.y/z) ok") == 4


def test_lint_denominator_uses_canonical_tokenizer():
    text = "Alpha beta — gamma [delta](http://u.rl/p) don't stop.\n" * 3
    assert lint_rhetoric(text).words == count_words(
        "Alpha beta gamma delta don't stop.\n" * 3
    )
