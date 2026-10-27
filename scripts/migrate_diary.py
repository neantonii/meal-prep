"""Convert old diary weeks (bare recipe ids) to entries with frozen numbers.

One-off migration for #107. Before it, a diary week listed recipe ids and
recomputed cost and macros from the current data every time it was opened.
Now every entry carries an id and its own numbers. Old weeks get today's
numbers: the best still available.

Usage (run from the workspace root, or inside the container):
    python scripts/migrate_diary.py
    python scripts/migrate_diary.py --diary-dir /app/diary \\
        --data-dir /app/data --recipes-dir /app/recipes

Safe to re-run: weeks already in the new format are skipped. Each converted
file's original is kept next to it as ``<week>.yaml.bak``. Nothing is written
unless every old week converts (e.g. no unknown recipe ids).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from meal_prep.adapters._yaml import read_yaml
from meal_prep.adapters.logs import save_diary_week
from meal_prep.dtos import normalize_slug
from meal_prep.dtos.log import DiaryDayDTO, DiaryWeekDTO
from meal_prep.enums import Mealtime
from meal_prep.library import load_library
from meal_prep.models.recipe import Recipe
from meal_prep.services.diary import freeze_entry


def is_old_format(data: Any) -> bool:
    """Old weeks list bare recipe ids where entries are now mappings."""
    days = data.get("days") if isinstance(data, dict) else None
    return isinstance(days, list) and any(
        isinstance(item, str)
        for day in days
        if isinstance(day, dict)
        for mealtime in Mealtime
        for item in day.get(mealtime.value) or ()
    )


def convert(old: dict[str, Any], recipes: dict[str, Recipe]) -> DiaryWeekDTO:
    """Freeze every listed recipe id into a diary entry, in order.

    ``old`` is a pre-#107 week: ``{week, days: [{date, <mealtime>: [ids]}]}``.
    The result is validated as a diary week (real ISO week, ordered days).
    """
    week = old["week"]
    days = []
    for day in old["days"]:
        meals = {}
        for mealtime in Mealtime:
            ids = [
                normalize_slug(i, field="recipe id")
                for i in day.get(mealtime.value) or ()
            ]
            if not ids:
                continue
            missing = [i for i in ids if i not in recipes]
            if missing:
                raise ValueError(
                    f"{week} {day['date']} {mealtime.value}: unknown recipe(s) "
                    f"{', '.join(missing)}"
                )
            meals[mealtime.value] = [freeze_entry(recipes[i]) for i in ids]
        days.append(DiaryDayDTO(date=day["date"], **meals))
    return DiaryWeekDTO(week=week, days=days)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--diary-dir", type=Path, default=Path("diary"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--recipes-dir", type=Path, default=Path("recipes"))
    args = parser.parse_args()

    library = load_library(args.data_dir, args.recipes_dir)
    recipes = dict(library.recipes)

    files = sorted(args.diary_dir.glob("*.yaml"))
    converted: list[tuple[Path, DiaryWeekDTO]] = []
    for path in files:
        old = read_yaml(path, what="Diary week")
        if not is_old_format(old):
            continue
        week = convert(old, recipes)
        if week.week != path.stem:
            raise ValueError(f"{path} holds week {week.week}, not {path.stem}")
        converted.append((path, week))

    for path, week in converted:
        shutil.copy2(path, path.with_name(f"{path.name}.bak"))
        save_diary_week(args.diary_dir, week)
        entries = sum(len(day.entries()) for day in week.days)
        print(f"converted {path.name}: {entries} entries")
    print(
        f"{len(converted)} week(s) converted, "
        f"{len(files) - len(converted)} already in the new format"
    )


if __name__ == "__main__":
    main()
