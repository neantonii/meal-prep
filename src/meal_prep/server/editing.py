"""What every diary and session route shares: loading the diary, the editing
policy for a request, and running one edit under the lock (journaled).
"""

from __future__ import annotations

import datetime
import threading
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from fastapi import HTTPException

from meal_prep.dtos.staples import StaplesDTO
from meal_prep.models.library import Library
from meal_prep.models.recipe import Recipe
from meal_prep.server.api_models import DiaryWeek, SessionDetail
from meal_prep.server.journal import Journal
from meal_prep.server.store import DiaryFileError, DiaryStore
from meal_prep.server.week_view import session_detail, week_response
from meal_prep.server.weeks import week_dates
from meal_prep.services import prep
from meal_prep.services.diary import EntryNotFoundError

# Journal outcome per HTTP status of a refused edit.
_OUTCOMES = {404: "not_found", 409: "refused", 422: "invalid"}


class Editor:
    """Runs diary edits and builds the week page they return."""

    def __init__(
        self,
        library: Library,
        store: DiaryStore,
        today: Callable[[], datetime.date],
        journal: Journal | None = None,
    ) -> None:
        self.library = library
        self.store = store
        self.today = today
        self.journal = journal
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

    def _note(
        self,
        action: str,
        params: Mapping[str, Any],
        admin: bool,
        outcome: str,
        message: str | None = None,
        before: prep.Diary | None = None,
        change: prep.Change | None = None,
    ) -> None:
        if self.journal is not None:
            self.journal.record(
                action,
                params,
                today=self.today(),
                admin=admin,
                outcome=outcome,
                message=message,
                before=before,
                change=change,
            )

    def _run(
        self,
        op: Callable[[prep.Diary], prep.Change],
        action: str,
        params: Mapping[str, Any],
        admin: bool,
    ) -> None:
        """Load, run ``op``, write its change and journal how it went.
        Call under the lock. Rule refusals are 409, unknown entries or
        sessions 404, invalid input 422; every one is journaled too."""
        status, outcome = 0, "ok"
        error: Exception | None = None
        try:
            diary = self.load()
            change = op(diary)
        except HTTPException as e:
            self._note(
                action, params, admin, _OUTCOMES.get(e.status_code, "error"), e.detail
            )
            raise
        except prep.RuleError as e:
            status, outcome, error = 409, "refused", e
        except (EntryNotFoundError, prep.SessionNotFoundError) as e:
            status, outcome, error = 404, "not_found", e
        except ValueError as e:
            status, outcome, error = 422, "invalid", e
        except Exception as e:
            self._note(action, params, admin, "error", repr(e))
            raise
        if error is not None:
            self._note(action, params, admin, outcome, str(error))
            raise HTTPException(status_code=status, detail=str(error)) from error
        self.store.apply(diary, change)
        self._note(action, params, admin, outcome, before=diary, change=change)

    def edit_session(
        self,
        session_id: uuid.UUID,
        op: Callable[[prep.Diary], prep.Change],
        *,
        action: str,
        params: Mapping[str, Any],
    ) -> SessionDetail:
        """Run one session edit under the lock, write it, return its page."""
        with self._lock:
            self._run(op, action, {"session": session_id, **params}, admin=False)
        return self.detail(session_id)

    def set_staple(self, ingredient_id: str, always: bool) -> None:
        """Add or remove one staple (``staples.yaml``)."""
        params = {"ingredient": ingredient_id, "always": always}
        if ingredient_id not in self.library.ingredients:
            message = f"unknown ingredient '{ingredient_id}'"
            self._note("staple.set", params, False, "invalid", message)
            raise HTTPException(status_code=422, detail=message)
        with self._lock:
            try:
                ids = set(self.store.load_staples().always_have)
                ids = ids | {ingredient_id} if always else ids - {ingredient_id}
                self.store.save_staples(StaplesDTO(always_have=sorted(ids)))
            except (DiaryFileError, ValueError) as e:
                self._note("staple.set", params, False, "invalid", str(e))
                raise HTTPException(status_code=422, detail=str(e)) from e
            self._note("staple.set", params, False, "ok")

    def edit(
        self,
        week: str,
        op: Callable[[prep.Diary], prep.Change],
        *,
        action: str,
        params: Mapping[str, Any],
        admin: bool,
    ) -> DiaryWeek:
        """Run one edit under the lock, write it, return ``week``'s page."""
        params = {"week": week, **params}
        try:
            self.check_week(week)
        except HTTPException as e:
            self._note(action, params, admin, "invalid", e.detail)
            raise
        with self._lock:
            self._run(op, action, params, admin)
            after = self.load()
        return week_response(week, after, self.today(), self.library)
