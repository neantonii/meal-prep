"""Which migration a diary is at: ``diary/.migrations.yaml``."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from meal_prep.adapters._yaml import read_yaml, write_yaml_atomic
from meal_prep.migrations.errors import MigrationError
from meal_prep.migrations.registry import Migration


class MigrationState:
    """The diary's data version (0: before any migration) and the history of
    migrations applied to it."""

    FILE = ".migrations.yaml"

    def __init__(self, diary_dir: Path) -> None:
        self.path = diary_dir / self.FILE

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 0, "history": []}
        data = read_yaml(self.path, what="Migration state")
        if not isinstance(data, dict) or not isinstance(data.get("version"), int):
            raise MigrationError(f"{self.path} is invalid: expected a 'version' number")
        return data

    @property
    def version(self) -> int:
        return int(self._read()["version"])

    def record(self, version: int, migration: Migration | None = None) -> None:
        """Set the version; ``migration`` (if any) is added to the history."""
        history = list(self._read().get("history") or [])
        if migration is not None:
            now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
            history.append(
                {"number": migration.number, "name": migration.name, "applied": now}
            )
        write_yaml_atomic(self.path, {"version": version, "history": history})
