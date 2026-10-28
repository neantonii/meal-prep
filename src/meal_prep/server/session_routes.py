"""Prep session routes: add, change and remove items; move or delete a
session. Each returns the page of ``week`` (the week the UI shows). The
rules live in ``meal_prep.services.prep``.
"""

from __future__ import annotations

import datetime
import logging
import uuid

from fastapi import APIRouter

from meal_prep.server.api_models import DiaryWeek, ItemUpdate, NewItem, SessionMove
from meal_prep.server.editing import Editor
from meal_prep.services import prep

logger = logging.getLogger("meal_prep.server")


def session_router(editor: Editor) -> APIRouter:
    router = APIRouter(prefix="/api/sessions")

    @router.post("/{date}/items")
    def item_add(
        date: datetime.date, week: str, body: NewItem, admin: bool = False
    ) -> DiaryWeek:
        recipe = editor.recipe(body.recipe)

        def op(diary: prep.Diary) -> prep.Change:
            change, session_id = prep.add_item(
                diary, editor.policy(admin), date, recipe, body.batches
            )
            logger.info("added %s to session %s (%s)", recipe.id, date, session_id)
            return change

        return editor.edit(week, op)

    @router.patch("/{session_id}/items/{recipe_id}")
    def item_update(
        session_id: uuid.UUID,
        recipe_id: str,
        week: str,
        body: ItemUpdate,
        admin: bool = False,
    ) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            change = prep.update_item(
                diary, editor.policy(admin), session_id, recipe_id, body.batches
            )
            logger.info(
                "updated %s in session %s (batches %s)",
                recipe_id,
                session_id,
                body.batches,
            )
            return change

        return editor.edit(week, op)

    @router.delete("/{session_id}/items/{recipe_id}")
    def item_remove(
        session_id: uuid.UUID, recipe_id: str, week: str, admin: bool = False
    ) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            change = prep.remove_item(
                diary, editor.policy(admin), session_id, recipe_id
            )
            logger.info("removed %s from session %s", recipe_id, session_id)
            return change

        return editor.edit(week, op)

    @router.patch("/{session_id}")
    def session_move(
        session_id: uuid.UUID, week: str, body: SessionMove, admin: bool = False
    ) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            change = prep.move_session(
                diary, editor.policy(admin), session_id, body.date
            )
            logger.info("moved session %s to %s", session_id, body.date)
            return change

        return editor.edit(week, op)

    @router.delete("/{session_id}")
    def session_delete(
        session_id: uuid.UUID, week: str, admin: bool = False
    ) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            change = prep.delete_session(diary, editor.policy(admin), session_id)
            logger.info("deleted session %s", session_id)
            return change

        return editor.edit(week, op)

    return router
