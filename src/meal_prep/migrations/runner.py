"""Brings a diary up to date: backup, pending migrations, load check."""

from __future__ import annotations

import logging
from pathlib import Path

from meal_prep.adapters.logs import diary_week_files, load_diary_file
from meal_prep.adapters.sessions import load_session_file, session_files
from meal_prep.migrations.backup import DiaryBackup
from meal_prep.migrations.errors import MigrationError
from meal_prep.migrations.registry import MIGRATIONS, Migration
from meal_prep.migrations.state import MigrationState
from meal_prep.models.library import Library

# A child of the server's logger, so its lines reach the server log file and
# the container's output (``meal_prep.server.logging``).
logger = logging.getLogger("meal_prep.server.migrations")


class Migrator:
    """Runs ``migrations`` (the released ones by default) over one diary."""

    def __init__(
        self,
        diary_dir: Path,
        library: Library,
        migrations: tuple[Migration, ...] = MIGRATIONS,
    ) -> None:
        self.diary_dir = Path(diary_dir)
        self.library = library
        self.migrations = migrations
        self.state = MigrationState(self.diary_dir)
        self.backup = DiaryBackup(self.diary_dir)

    @property
    def latest(self) -> int:
        return self.migrations[-1].number if self.migrations else 0

    def run(self) -> list[int]:
        """Apply every pending migration; returns their numbers."""
        self.diary_dir.mkdir(parents=True, exist_ok=True)
        current = self.state.version
        if current > self.latest:
            raise MigrationError(
                f"The diary is at migration {current}, newer than this release "
                f"knows ({self.latest}): an older image is running on migrated "
                f"data. Run a newer image, or restore a backup from "
                f"{DiaryBackup.DIR}/."
            )
        pending = [m for m in self.migrations if m.number > current]
        if not pending:
            return []
        if not self._has_data():
            self.state.record(self.latest)
            logger.info("new diary: marked as migration %d", self.latest)
            return []
        backup = self.backup.take(pending[0].number)
        logger.info("diary backed up to %s", backup)
        for migration in pending:
            self._apply(migration, backup)
        self._check_loads(backup)
        return [m.number for m in pending]

    def _has_data(self) -> bool:
        return bool(
            diary_week_files(self.diary_dir)
            or session_files(self.diary_dir / "sessions")
        )

    def _apply(self, migration: Migration, backup: Path) -> None:
        try:
            changed = migration.apply(self.diary_dir, self.library)
        except Exception as e:
            raise MigrationError(
                f"migration {migration.number} ({migration.name}) failed: {e}. "
                f"The diary before it is in {backup}"
            ) from e
        self.state.record(migration.number, migration)
        logger.info(
            "migration %d (%s): %d file(s) changed",
            migration.number,
            migration.name,
            changed,
        )

    def _check_loads(self, backup: Path) -> None:
        try:
            for path in diary_week_files(self.diary_dir):
                load_diary_file(path)
            for path in session_files(self.diary_dir / "sessions"):
                load_session_file(path)
        except ValueError as e:
            raise MigrationError(
                f"the migrated diary doesn't load: {e}. The diary before it is "
                f"in {backup}"
            ) from e
