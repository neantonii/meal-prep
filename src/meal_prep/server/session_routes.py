"""Prep session routes: remove a batch; move a recipe line to another
session; move a session; the shopping checklist (ticks per session, staples
across sessions). Batches are added by putting a recipe on a day
(``diary_routes``). Batch and session edits return the page of ``week``
(the week the UI shows); checklist edits return the session's own page. The
rules live in ``meal_prep.services.prep``.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter

from meal_prep.server.api_models import (
    AlwaysUpdate,
    DiaryWeek,
    HaveUpdate,
    ItemMove,
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
            shares = [(s.recipe, s.ingredient) for s in body.shares]
            return prep.set_have(
                diary, editor.policy(False), session_id, shares, body.have
            )

        return editor.edit_session(
            session_id, op, action="session.have", params=body.model_dump(mode="json")
        )

    @router.put("/{session_id}/always/{ingredient_id}")
    def always_set(
        session_id: uuid.UUID, ingredient_id: str, body: AlwaysUpdate
    ) -> SessionDetail:
        """Staples span sessions; the reply is ``session_id``'s page."""
        editor.set_staple(ingredient_id, body.always)
        logger.info("staple %s: %s", ingredient_id, body.always)
        return editor.detail(session_id)

    @router.delete("/{session_id}/items/{recipe_id}/batch")
    def batch_remove(
        session_id: uuid.UUID, recipe_id: str, week: str, admin: bool = False
    ) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            change = prep.remove_batch(
                diary, editor.policy(admin), session_id, recipe_id
            )
            logger.info("removed a batch of %s from session %s", recipe_id, session_id)
            return change

        params = {"session": session_id, "recipe": recipe_id}
        return editor.edit(week, op, action="batch.remove", params=params, admin=admin)

    @router.put("/{session_id}/items/{recipe_id}/session")
    def item_move(
        session_id: uuid.UUID,
        recipe_id: str,
        week: str,
        body: ItemMove,
        admin: bool = False,
    ) -> DiaryWeek:
        """Move the whole recipe line, with every meal, to another session."""

        def op(diary: prep.Diary) -> prep.Change:
            change = prep.move_item(
                diary,
                editor.policy(admin),
                session_id,
                recipe_id,
                body.session,
                body.date,
            )
            logger.info(
                "moved %s from session %s to %s",
                recipe_id,
                session_id,
                body.session or body.date,
            )
            return change

        params = {
            "session": session_id,
            "recipe": recipe_id,
            "to": body.model_dump(mode="json"),
        }
        return editor.edit(week, op, action="item.move", params=params, admin=admin)

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

        params = {"session": session_id, **body.model_dump(mode="json")}
        return editor.edit(week, op, action="session.move", params=params, admin=admin)

    return router
