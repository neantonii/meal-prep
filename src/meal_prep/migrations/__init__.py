"""Diary data migrations, applied automatically when the server starts.

The diary (``diary/``: week files and ``sessions/``) lives on the host and
outlives every image. When its stored format grows, a migration brings the
files along. ``migrate`` runs at start-up, before anything is served:

1. Read the data version from ``diary/.migrations.yaml`` (missing: 0).
2. If migrations newer than it exist, copy the diary to
   ``diary/.backups/<UTC time>-before-<n>/`` first.
3. Apply each pending migration in order, recording each one as it
   finishes, then check that every file still loads.

A failure stops the server (it never serves half-migrated data); the backup
stays where it is. Each migration is idempotent, so a fixed release simply
runs it again. An empty diary (a new install) is just marked current.

A migration edits raw YAML, never through today's DTOs, which keep changing
after the migration is written; see ``registry`` to add one.

Modules: ``registry`` (the released migrations), ``state`` (the version
file), ``backup`` (the copies), ``runner`` (the order of the steps above).
"""

from __future__ import annotations

from pathlib import Path

from meal_prep.migrations.errors import MigrationError
from meal_prep.migrations.registry import MIGRATIONS, Migration
from meal_prep.migrations.runner import Migrator
from meal_prep.models.library import Library

__all__ = ["MIGRATIONS", "Migration", "MigrationError", "Migrator", "migrate"]


def migrate(diary_dir: Path, library: Library) -> list[int]:
    """Bring ``diary_dir`` up to date; returns the migrations applied."""
    return Migrator(diary_dir, library).run()
