"""Diary routes: a week page and single-entry edits (add, remove, move,
link to a prep session). The rules live in ``meal_prep.services.prep``.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter

from meal_prep.server.api_models import DiaryWeek, EntryLink, EntryPlacement, NewEntry
from meal_prep.server.editing import Editor
from meal_prep.services import prep

logger = logging.getLogger("meal_prep.server")


def diary_router(editor: Editor) -> APIRouter:
    router = APIRouter(prefix="/api/diary")
    recipes = editor.library.recipes

    @router.get("/{week}")
    def diary_get(week: str) -> DiaryWeek:
        return editor.page(week)

    @router.post("/{week}/entries")
    def entry_add(week: str, body: NewEntry, admin: bool = False) -> DiaryWeek:
        recipe = editor.recipe(body.recipe)

        def op(diary: prep.Diary) -> prep.Change:
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

        return editor.edit(week, op)

    @router.delete("/{week}/entries/{entry_id}")
    def entry_remove(week: str, entry_id: uuid.UUID, admin: bool = False) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            change = prep.remove_entry(diary, editor.policy(admin), week, entry_id)
            logger.info("removed entry %s from %s", entry_id, week)
            return change

        return editor.edit(week, op)

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

        return editor.edit(week, op)

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

        return editor.edit(week, op)

    return router
