"""Prep session routes: remove items; move or delete a session; the
shopping checklist (ticks per session, staples across sessions). Items are
added by linking meals (``diary_routes``). Item and session edits return the
page of ``week`` (the week the UI shows); checklist edits return the
session's own page. The rules live in ``meal_prep.services.prep``.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException

from meal_prep.server.api_models import (
    AlwaysUpdate,
    DiaryWeek,
    HaveUpdate,
    SessionDetail,
    SessionMove,
)
from meal_prep.server.editing import Editor
from meal_prep.services import prep

logger = logging.getLogger("meal_prep.server")


def session_router(editor: Editor) -> APIRouter:
    router = APIRouter(prefix="/api/sessions")

    @router.get("/{session_id}")
    def session_get(session_id: uuid.UUID) -> SessionDetail:
        return editor.detail(session_id)

    @router.put("/{session_id}/have")
    def have_set(session_id: uuid.UUID, body: HaveUpdate) -> SessionDetail:
        def op(diary: prep.Diary) -> prep.Change:
            return prep.set_have(
                diary, editor.policy(False), session_id, body.ingredients, body.have
            )

        return editor.edit_session(session_id, op)

    @router.put("/{session_id}/always/{ingredient_id}")
    def always_set(
        session_id: uuid.UUID, ingredient_id: str, body: AlwaysUpdate
    ) -> SessionDetail:
        """Staples span sessions; the reply is ``session_id``'s page."""
        if ingredient_id not in editor.library.ingredients:
            raise HTTPException(
                status_code=422, detail=f"unknown ingredient '{ingredient_id}'"
            )
        editor.set_staple(ingredient_id, body.always)
        logger.info("staple %s: %s", ingredient_id, body.always)
        return editor.detail(session_id)

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
