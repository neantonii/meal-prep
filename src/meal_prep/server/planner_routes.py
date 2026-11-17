"""Planner routes (``docs/planner.md``): plan the week ahead, clear every
plan, accept one session's plan. Each returns the week page asked for."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter

from meal_prep.server.api_models import DiaryWeek
from meal_prep.server.editing import Editor
from meal_prep.server.planning import plan_week_ahead
from meal_prep.services import prep

logger = logging.getLogger("meal_prep.server")


def planner_router(editor: Editor) -> APIRouter:
    router = APIRouter(prefix="/api/plan")

    @router.post("")
    def plan_run(week: str) -> DiaryWeek:
        """Fill the empty slots of the week ahead with flagged meals."""

        def op(diary: prep.Diary) -> prep.Change:
            change = plan_week_ahead(diary, editor.policy(False), editor.library)
            logger.info("planned the week ahead")
            return change

        return editor.edit(week, op, action="plan.run", params={}, admin=False)

    @router.delete("")
    def plan_clear(week: str) -> DiaryWeek:
        """Remove every planned meal of every planned session."""

        def op(diary: prep.Diary) -> prep.Change:
            change = prep.clear_plans(diary, editor.policy(False))
            logger.info("cleared the plans")
            return change

        return editor.edit(week, op, action="plan.clear", params={}, admin=False)

    @router.post("/accept/{session_id}")
    def plan_accept(session_id: uuid.UUID, week: str) -> DiaryWeek:
        """Make one session's planned meals manual."""

        def op(diary: prep.Diary) -> prep.Change:
            change = prep.accept_session(diary, editor.policy(False), session_id)
            logger.info("accepted the plan of session %s", session_id)
            return change

        params = {"session": session_id}
        return editor.edit(week, op, action="plan.accept", params=params, admin=False)

    return router
