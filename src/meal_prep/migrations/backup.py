"""Copies of the diary taken before migrating: ``diary/.backups/``."""

from __future__ import annotations

import datetime
import shutil
from pathlib import Path


class DiaryBackup:
    """Backups live inside the diary (the only persistent mount besides logs)
    as dot-folders, which no loader reads. Nothing prunes them."""

    DIR = ".backups"

    def __init__(self, diary_dir: Path) -> None:
        self.diary_dir = diary_dir

    def take(self, before: int) -> Path:
        """Copy the diary (everything but dot-entries) to a new folder named
        for the time and the first migration about to run."""
        stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        target = self.diary_dir / self.DIR / f"{stamp}-before-{before:04d}"
        target.mkdir(parents=True)
        for entry in self.diary_dir.iterdir():
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                shutil.copytree(entry, target / entry.name)
            else:
                shutil.copy2(entry, target / entry.name)
        return target
