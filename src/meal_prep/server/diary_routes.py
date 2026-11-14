"""Diary routes: a week page and single-entry edits (add, remove, move,
link to a prep session; add and edit takeout), plus the takeout meals eaten
before (``/api/usuals``). The rules live in ``meal_prep.services.prep``.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter

from meal_prep.dtos.log import TakeoutEntryDTO
from meal_prep.server.api_models import (
    DiaryWeek,
    EntryLink,
    EntryPlacement,
    NewEntry,
    NewTakeoutEntries,
    TakeoutFields,
    Usual,
)
from meal_prep.server.editing import Editor
from meal_prep.services import diary as entries
from meal_prep.services import prep

logger = logging.getLogger("meal_prep.server")


def _takeout(body: TakeoutFields, entry_id: uuid.UUID | None = None) -> TakeoutEntryDTO:
    return entries.takeout_entry(
        body.title,
        calories_kcal=body.kcal,
        protein_g=body.protein_g,
        carbs_g=body.carbs_g,
        fat_g=body.fat_g,
        cost=body.cost,
        entry_id=entry_id,
    )


def usuals_router(editor: Editor) -> APIRouter:
    router = APIRouter(prefix="/api/usuals")

    @router.get("")
    def usuals_get() -> list[Usual]:
        """Takeout meals eaten before, latest first: what the takeout form
        offers to repeat."""
        return [
            Usual(
                title=u.entry.title,
                kcal=u.entry.calories_kcal,
                protein_g=u.entry.protein_g,
                carbs_g=u.entry.carbs_g,
                fat_g=u.entry.fat_g,
                cost=u.entry.cost,
                last=u.last.isoformat(),
                times=u.times,
            )
            for u in entries.takeout_history(editor.load().weeks.values())
        ]

    return router


def diary_router(editor: Editor) -> APIRouter:
    router = APIRouter(prefix="/api/diary")
    recipes = editor.library.recipes

    @router.get("/{week}")
    def diary_get(week: str) -> DiaryWeek:
        return editor.page(week)

    @router.post("/{week}/entries")
    def entry_add(week: str, body: NewEntry, admin: bool = False) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            recipe = editor.recipe(body.recipe)  # unknown: 422, journaled
            change, entry = prep.add_entry(
                diary,
                editor.policy(admin),
                recipes,
                week,
                body.date,
                body.mealtime,
                recipe,
                body.position,
                body.session,
            )
            logger.info(
                "added %s to %s %s (%s, session %s)",
                recipe.id,
                body.date,
                body.mealtime.value,
                entry.id,
                entry.session,
            )
            return change

        return editor.edit(
            week,
            op,
            action="entry.add",
            params=body.model_dump(mode="json"),
            admin=admin,
        )

    @router.post("/{week}/takeout")
    def takeout_add(
        week: str, body: NewTakeoutEntries, admin: bool = False
    ) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            added = [_takeout(item) for item in body.items]
            logger.info(
                "added %s to %s %s",
                ", ".join(repr(e.title) for e in added),
                body.date,
                body.mealtime.value,
            )
            return prep.add_takeout_entries(
                diary,
                editor.policy(admin),
                week,
                body.date,
                body.mealtime,
                added,
                body.position,
            )

        params = body.model_dump(mode="json")
        return editor.edit(week, op, action="takeout.add", params=params, admin=admin)

    @router.put("/{week}/takeout/{entry_id}")
    def takeout_edit(
        week: str, entry_id: uuid.UUID, body: TakeoutFields, admin: bool = False
    ) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            entry = _takeout(body, entry_id)
            logger.info("edited %s (%r)", entry_id, entry.title)
            return prep.edit_takeout_entry(diary, editor.policy(admin), week, entry)

        params = {"entry": entry_id, **body.model_dump(mode="json")}
        return editor.edit(week, op, action="takeout.edit", params=params, admin=admin)

    @router.delete("/{week}/entries/{entry_id}")
    def entry_remove(week: str, entry_id: uuid.UUID, admin: bool = False) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            change = prep.remove_entry(diary, editor.policy(admin), week, entry_id)
            logger.info("removed entry %s from %s", entry_id, week)
            return change

        return editor.edit(
            week, op, action="entry.remove", params={"entry": entry_id}, admin=admin
        )

    @router.patch("/{week}/entries/{entry_id}")
    def entry_move(
        week: str, entry_id: uuid.UUID, body: EntryPlacement, admin: bool = False
    ) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            change = prep.move_entry(
                diary,
                editor.policy(admin),
                recipes,
                week,
                entry_id,
                body.date,
                body.mealtime,
                body.position,
            )
            logger.info(
                "moved entry %s to %s %s", entry_id, body.date, body.mealtime.value
            )
            return change

        params = {"entry": entry_id, **body.model_dump(mode="json")}
        return editor.edit(week, op, action="entry.move", params=params, admin=admin)

    @router.put("/{week}/entries/{entry_id}/session")
    def entry_link(
        week: str, entry_id: uuid.UUID, body: EntryLink, admin: bool = False
    ) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            change = prep.set_entry_session(
                diary,
                editor.policy(admin),
                recipes,
                week,
                entry_id,
                body.session,
                body.session_date,
            )
            logger.info(
                "linked entry %s to session %s",
                entry_id,
                body.session_date or body.session,
            )
            return change

        params = {"entry": entry_id, **body.model_dump(mode="json")}
        return editor.edit(week, op, action="entry.link", params=params, admin=admin)

    return router
