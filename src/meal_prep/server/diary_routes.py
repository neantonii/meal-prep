"""Diary routes: a week page and single-entry edits (add, remove, move,
link to a prep session; add and edit a free-form entry), plus the free-form
meals eaten before (``/api/usuals``). The rules live in
``meal_prep.services.prep``.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter

from meal_prep.dtos.log import DiaryEntryDTO, EntryEstimateDTO
from meal_prep.server.api_models import (
    DiaryWeek,
    EntryLink,
    EntryPlacement,
    FreeFormFields,
    NewEntry,
    NewFreeEntry,
    Usual,
)
from meal_prep.server.editing import Editor
from meal_prep.services import diary as entries
from meal_prep.services import prep

logger = logging.getLogger("meal_prep.server")


# API number name -> diary entry field.
_FIELDS = {
    "kcal": "calories_kcal",
    "protein_g": "protein_g",
    "carbs_g": "carbs_g",
    "fat_g": "fat_g",
    "fiber_g": "fiber_g",
    "cost": "cost",
}


def _free_entry(
    body: FreeFormFields, entry_id: uuid.UUID | None = None
) -> DiaryEntryDTO:
    return entries.free_entry(
        body.title,
        {field: getattr(body, name) for name, field in _FIELDS.items()},
        portion=body.portion,
        estimate=EntryEstimateDTO(source="manual") if body.estimated else None,
        entry_id=entry_id,
    )


def usuals_router(editor: Editor) -> APIRouter:
    router = APIRouter(prefix="/api/usuals")

    @router.get("")
    def usuals_get() -> list[Usual]:
        """Free-form meals eaten before, latest first: what "+ other"
        offers to repeat."""
        return [
            Usual(
                title=u.title,
                **{name: u.order[field] for name, field in _FIELDS.items()},
                estimated=u.estimate is not None,
                last=u.last.isoformat(),
                times=u.times,
            )
            for u in entries.free_form_history(editor.load().weeks.values())
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

    @router.post("/{week}/others")
    def other_add(week: str, body: NewFreeEntry, admin: bool = False) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            entry = _free_entry(body)
            logger.info("added %r to %s %s", entry.title, body.date, body.mealtime)
            return prep.add_free_entry(
                diary,
                editor.policy(admin),
                week,
                body.date,
                body.mealtime,
                entry,
                body.position,
            )

        params = body.model_dump(mode="json")
        return editor.edit(week, op, action="other.add", params=params, admin=admin)

    @router.put("/{week}/others/{entry_id}")
    def other_edit(
        week: str, entry_id: uuid.UUID, body: FreeFormFields, admin: bool = False
    ) -> DiaryWeek:
        def op(diary: prep.Diary) -> prep.Change:
            entry = _free_entry(body, entry_id)
            logger.info("edited %s (%r)", entry_id, entry.title)
            return prep.edit_free_entry(diary, editor.policy(admin), week, entry)

        params = {"entry": entry_id, **body.model_dump(mode="json")}
        return editor.edit(week, op, action="other.edit", params=params, admin=admin)

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
