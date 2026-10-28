"""The one error the migrations raise."""

from __future__ import annotations


class MigrationError(RuntimeError):
    """A migration can't run or failed; the message names the backup."""
