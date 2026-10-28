"""The released migrations, in order.

To add one: a module ``m<NNNN>_<name>.py`` with ``apply(diary_dir, library)``
returning how many files it rewrote, then append it here with the next
number. Never edit or renumber a released migration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from meal_prep.migrations import m0001_session_packages
from meal_prep.models.library import Library


@dataclass(frozen=True, slots=True)
class Migration:
    number: int
    name: str
    # Applies the change in place; returns how many files it rewrote.
    apply: Callable[[Path, Library], int]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        1,
        "session ingredient lines: aisle and retail package",
        m0001_session_packages.apply,
    ),
)
