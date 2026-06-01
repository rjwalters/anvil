"""Deck-skill-local helpers.

These modules implement small in-skill primitives that the deck commands
(`deck-draft`, `deck-revise`, `deck-figures`, `deck-imagegen`, …) lean
on. They live here rather than under ``anvil/lib/`` because they are
skill-specific (the Marp overflow lint mirrors a marp-vscode diagnostic;
the prompt-journal schema is part of the `deck-imagegen` contract) and
because anvil's v0 policy is to let the framework ``lib/`` emerge from
observed duplication rather than design it up-front.

If a future skill needs the same primitives, the lift to
``anvil/lib/`` is mechanical.
"""
