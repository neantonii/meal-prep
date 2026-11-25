"""Planner routes (``docs/planner.md``): plan the week ahead, clear every
plan, accept one session's plan. Each returns the week page asked for."""

from __future__ import annotations

import datetime
import logging
import uuid

from fastapi import APIRouter, HTTPException

from meal_prep.server.api_models import BillLine, DiaryWeek, Explanation, MealScore
from meal_prep.server.editing import Editor
from meal_prep.server.planning import (
    HORIZON_DAYS,
    explain_week_ahead,
    first_plan_day,
    plan_week_ahead,
)
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

    @router.get("/explain")
    def plan_explain() -> Explanation:
        """The bill of the week ahead as it stands, whoever placed the meals."""
        policy = editor.policy(False)
        try:
            result = explain_week_ahead(editor.load(), policy, editor.library)
        except prep.RuleError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        start = first_plan_day(policy.today)
        per_meal: dict[tuple[str, str], float] = {}
        for line in result.lines:
            if line.date is not None and line.mealtime is not None:
                key = (line.date.isoformat(), line.mealtime.value)
                per_meal[key] = per_meal.get(key, 0.0) + line.points
        return Explanation(
            start=start.isoformat(),
            end=(start + datetime.timedelta(days=HORIZON_DAYS - 1)).isoformat(),
            total=round(result.total_points, 2),
            terms=[{"name": n, "points": round(v, 2)} for n, v in result.points],
            lines=[
                BillLine(
                    term=line.term,
                    reason=line.reason,
                    points=round(line.points, 2),
                    date=line.date.isoformat() if line.date else None,
                    mealtime=line.mealtime.value if line.mealtime else None,
                    session=line.session.isoformat() if line.session else None,
                )
                for line in sorted(result.lines, key=lambda line: -line.points)
            ],
            meals=[
                MealScore(
                    date=date.isoformat(),
                    mealtime=mealtime.value,
                    archetype=name,
                    points=round(
                        per_meal.get((date.isoformat(), mealtime.value), 0.0), 2
                    ),
                )
                for date, mealtime, name in result.archetypes
            ],
            problems=list(result.problems),
        )

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
