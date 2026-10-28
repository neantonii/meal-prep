"""Prep session routes: remove items; move or delete a session. Items are
added by linking meals (``diary_routes``). Each returns the page of ``week``
(the week the UI shows). The rules live in ``meal_prep.services.prep``.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException

from meal_prep.server.api_models import DiaryWeek, SessionDetail, SessionMove
from meal_prep.server.editing import Editor
from meal_prep.server.week_view import session_detail
from meal_prep.services import prep

logger = logging.getLogger("meal_prep.server")


def session_router(editor: Editor) -> APIRouter:
    router = APIRouter(prefix="/api/sessions")

    @router.get("/{session_id}")
    def session_get(session_id: uuid.UUID) -> SessionDetail:
        try:
            return session_detail(
                session_id, editor.load(), editor.today(), editor.library
            )
        except prep.SessionNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

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
