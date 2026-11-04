"""What every diary and session route shares: loading the diary, the editing
policy for a request, and running one edit under the lock.
"""

from __future__ import annotations

import datetime
import threading
import uuid
from collections.abc import Callable

from fastapi import HTTPException

from meal_prep.dtos.staples import StaplesDTO
from meal_prep.models.library import Library
from meal_prep.models.recipe import Recipe
from meal_prep.server.api_models import DiaryWeek, SessionDetail
from meal_prep.server.store import DiaryFileError, DiaryStore
from meal_prep.server.week_view import session_detail, week_response
from meal_prep.server.weeks import week_dates
from meal_prep.services import prep
from meal_prep.services.diary import EntryNotFoundError


class Editor:
    """Runs diary edits and builds the week page they return."""

    def __init__(
        self,
        library: Library,
        store: DiaryStore,
        today: Callable[[], datetime.date],
    ) -> None:
        self.library = library
        self.store = store
        self.today = today
        # Every edit reads the whole diary, changes it and writes the touched
        # files; one lock keeps two overlapping requests from losing each
        # other's change.
        self._lock = threading.Lock()

    @staticmethod
    def check_week(week: str) -> None:
        try:
            week_dates(week)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    def load(self) -> prep.Diary:
        try:
            return self.store.load()
        except DiaryFileError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    def policy(self, admin: bool) -> prep.Policy:
        return prep.Policy(today=self.today(), admin=admin)

    def recipe(self, recipe_id: str) -> Recipe:
        recipe = self.library.recipes.get(recipe_id)
        if recipe is None:
            raise HTTPException(status_code=422, detail=f"unknown recipe '{recipe_id}'")
        return recipe

    def page(self, week: str) -> DiaryWeek:
        """The week page as the diary is now."""
        self.check_week(week)
        return week_response(week, self.load(), self.today(), self.library)

    def detail(self, session_id: uuid.UUID) -> SessionDetail:
        """A session's own page as the diary is now; 404 if unknown."""
        try:
            staples = self.store.load_staples().always_have
            return session_detail(
                session_id, self.load(), self.today(), self.library, staples
            )
        except DiaryFileError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except prep.SessionNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    def edit_session(
        self, session_id: uuid.UUID, op: Callable[[prep.Diary], prep.Change]
    ) -> SessionDetail:
        """Run one session edit under the lock, write it, return its page."""
        with self._lock:
            diary = self.load()
            try:
                change = op(diary)
            except prep.SessionNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e)) from e
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            self.store.apply(diary, change)
        return self.detail(session_id)

    def set_staple(self, ingredient_id: str, always: bool) -> None:
        """Add or remove one staple (``staples.yaml``)."""
        with self._lock:
            try:
                ids = set(self.store.load_staples().always_have)
                ids = ids | {ingredient_id} if always else ids - {ingredient_id}
                self.store.save_staples(StaplesDTO(always_have=sorted(ids)))
            except (DiaryFileError, ValueError) as e:
                raise HTTPException(status_code=422, detail=str(e)) from e

    def edit(self, week: str, op: Callable[[prep.Diary], prep.Change]) -> DiaryWeek:
        """Run one edit under the lock, write it, return ``week``'s page.

        Rule refusals are 409, unknown entries or sessions 404, invalid
        input 422.
        """
        self.check_week(week)
        with self._lock:
            diary = self.load()
            try:
                change = op(diary)
            except prep.RuleError as e:
                raise HTTPException(status_code=409, detail=str(e)) from e
            except (EntryNotFoundError, prep.SessionNotFoundError) as e:
                raise HTTPException(status_code=404, detail=str(e)) from e
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            self.store.apply(diary, change)
            after = self.load()
        return week_response(week, after, self.today(), self.library)
