"""Tests for the prep-session rules (``services/prep.py``,
``docs/prep-sessions.md``)."""

from __future__ import annotations

import datetime
import uuid

import pytest

from meal_prep.dtos.log import DiaryEntryDTO
from meal_prep.dtos.session import PrepSessionDTO
from meal_prep.enums import Aisle, Mealtime, RecipeCategory, StorageType
from meal_prep.models.ingredient import MacrosInfo
from meal_prep.models.recipe import Recipe, RecipeIngredient
from meal_prep.services import prep
from meal_prep.services.prep import Change, Diary, Mode, Policy, RuleError
from meal_prep.services.sessions import freeze_item, prepare_session

D = datetime.date
TODAY = D(2026, 10, 31)  # Saturday
SUN, MON, TUE, WED, THU = (D(2026, 11, day) for day in (1, 2, 3, 4, 5))
WEEK = "2026-W45"  # Mon 2 Nov - Sun 8 Nov
LAST_WEEK = "2026-W44"
PLAN = Policy(today=TODAY)
ADMIN = Policy(today=TODAY, admin=True)


def _recipe(recipe_id: str, servings: float = 4.0) -> Recipe:
    macros = MacrosInfo(400.0, 30.0, 10.0, 40.0, 5.0, 2.0, 3.0, 40.0, 50.0)
    return Recipe(
        id=recipe_id,
        title=recipe_id.replace("-", " ").title(),
        category=RecipeCategory.MODULAR_PROTEIN,
        servings=servings,
        cooked_g=800.0,
        fridge_days=4,
        freezer_friendly=False,
        equipment=(),
        cookware_by_token={},
        ingredients=(
            RecipeIngredient(
                id="chicken-breast",
                name="Chicken breast",
                step_name="chicken",
                aisle=Aisle.MEAT,
                storage=StorageType.REFRIGERATED,
                shelf_life_days=3,
                quantity=600.0,
                unit="g",
                grams=600.0,
                cost=12.0,
                macros=macros,
            ),
        ),
        instructions="Cook.",
    )


CHICKEN = _recipe("chicken")
RICE = _recipe("rice", servings=3.0)
EGG = _recipe("egg", servings=1.0)  # one portion per batch
RECIPES = {r.id: r for r in (CHICKEN, RICE, EGG)}
EMPTY = Diary(weeks={}, sessions={})


def _apply(diary: Diary, change: Change) -> Diary:
    weeks = dict(diary.weeks)
    for week, dto in change.weeks.items():
        if dto is None:
            weeks.pop(week, None)
        else:
            weeks[week] = dto
    sessions = dict(diary.sessions)
    for sid, session in change.sessions.items():
        if session is None:
            sessions.pop(sid, None)
        else:
            sessions[sid] = session
    return Diary(weeks=weeks, sessions=sessions)


def _session(date: D, *items: tuple[Recipe, int]) -> PrepSessionDTO:
    return PrepSessionDTO(
        id=uuid.uuid4(),
        date=date,
        items=[freeze_item(recipe, batches=batches) for recipe, batches in items],
    )


def _with(*sessions: PrepSessionDTO) -> Diary:
    return Diary(weeks={}, sessions={s.id: s for s in sessions})


def _add(
    diary: Diary,
    date: D,
    recipe: Recipe = CHICKEN,
    link: prep.Link = "auto",
    policy: Policy = PLAN,
) -> tuple[Diary, DiaryEntryDTO]:
    week = _week(date)
    change, entry = prep.add_entry(
        diary, policy, RECIPES, week, date, Mealtime.LUNCH, recipe, link=link
    )
    return _apply(diary, change), entry


def _week(date: D) -> str:
    year, number, _ = date.isocalendar()
    return f"{year}-W{number:02d}"


def _only(diary: Diary) -> PrepSessionDTO:
    [session] = diary.sessions.values()
    return session


def _entry(diary: Diary, entry_id: uuid.UUID, week: str = WEEK) -> DiaryEntryDTO:
    return next(
        e for d in diary.weeks[week].days for e in d.entries() if e.id == entry_id
    )


# -- modes and calendar -------------------------------------------------------


def test_mode_is_plan_after_today_log_otherwise_admin_overrides():
    assert PLAN.mode(SUN) is Mode.PLAN
    assert PLAN.mode(TODAY) is Mode.LOG
    assert PLAN.mode(TODAY - datetime.timedelta(days=3)) is Mode.LOG
    assert PLAN.mode(SUN, TODAY) is Mode.LOG  # any Log day wins
    assert ADMIN.mode(TODAY) is Mode.ADMIN


def test_session_window_runs_from_the_sunday_before_to_the_own_sunday():
    start, end = prep.session_window(MON)
    assert (start, end) == (SUN, D(2026, 11, 8))
    assert prep.default_session_dates(start, end) == (SUN, TUE, THU, D(2026, 11, 8))


def test_portions_are_whole_batches_times_whole_servings():
    assert prepare_session(_session(SUN, (RICE, 2))).items[0].portions == 6
    with pytest.raises(ValueError, match="whole number"):
        freeze_item(_recipe("stew", servings=2.5))


# -- freezing -----------------------------------------------------------------


def test_items_freeze_numbers_and_one_batch_of_ingredients():
    item = freeze_item(CHICKEN, batches=2)
    assert (item.title, item.servings, item.batches) == ("Chicken", 4, 2)
    assert item.cost == pytest.approx(3.0)
    assert item.calories_kcal == pytest.approx(100.0)
    [line] = item.ingredients
    assert (line.ingredient, line.grams, line.cost) == ("chicken-breast", 600.0, 12.0)


# -- adding entries -------------------------------------------------------------


def test_auto_link_creates_the_default_session_before_the_entry():
    diary, entry = _add(EMPTY, MON)
    session = _only(diary)
    assert session.date == SUN
    assert entry.session == session.id
    [item] = session.items
    assert (item.recipe, item.batches) == ("chicken", 1)

    # Sunday has no rice, so Wednesday's rice gets the nearer Tuesday session.
    diary, wed = _add(diary, WED, RICE)
    tue = next(s for s in diary.sessions.values() if s.date == TUE)
    assert wed.session == tue.id


def test_auto_link_prefers_a_session_with_a_free_portion():
    diary = _with(_session(SUN, (CHICKEN, 1)))
    diary, entry = _add(diary, WED)  # Tuesday is nearer, but Sunday has room
    assert entry.session == _only(diary).id


def test_auto_link_raises_batches_when_the_item_is_full():
    diary = _with(_session(SUN, (CHICKEN, 1)))
    for _ in range(4):
        diary, _ = _add(diary, MON)
    assert _only(diary).items[0].batches == 1
    diary, entry = _add(diary, MON)
    assert entry.session == _only(diary).id
    assert _only(diary).items[0].batches == 2


def test_auto_link_never_changes_a_session_that_already_happened():
    past = _session(TODAY, (EGG, 1))  # one portion
    diary, first = _add(_with(past), SUN, EGG)
    assert first.session == past.id
    # Full now; Sunday (Plan) gets a new session instead of raising Saturday's.
    diary, second = _add(diary, SUN, EGG)
    assert diary.sessions[past.id] == past
    assert diary.sessions[second.session].date == SUN  # type: ignore[index]


def test_log_mode_adds_unlinked_entries_only():
    diary, entry = _add(EMPTY, TODAY)
    assert entry.session is None
    assert diary.sessions == {}
    sun = _session(D(2026, 10, 25), (CHICKEN, 1))
    with pytest.raises(RuleError, match="Log mode"):
        _add(_with(sun), TODAY, link=sun.id)


def test_explicit_link_in_plan_adds_the_missing_item():
    sun = _session(SUN, (RICE, 1))
    diary, entry = _add(_with(sun), MON, link=sun.id)
    assert entry.session == sun.id
    assert [i.recipe for i in _only(diary).items] == ["rice", "chicken"]


def test_explicit_link_refuses_a_later_session():
    tue = _session(TUE, (CHICKEN, 1))
    with pytest.raises(RuleError, match="later"):
        _add(_with(tue), MON, link=tue.id)


def test_explicit_link_cannot_fill_a_session_that_already_happened():
    past = _session(TODAY, (RICE, 1))
    with pytest.raises(RuleError, match="has no Chicken"):
        _add(_with(past), SUN, link=past.id)


def test_admin_links_only_when_the_rules_hold():
    sun = _session(SUN, (EGG, 1))
    diary, entry = _add(_with(sun), MON, EGG, link=sun.id, policy=ADMIN)
    assert entry.session == sun.id
    with pytest.raises(RuleError, match="full"):
        _add(diary, MON, EGG, link=sun.id, policy=ADMIN)
    # Admin palette drops are never auto-linked.
    _, unlinked = _add(diary, MON, policy=ADMIN)
    assert unlinked.session is None


# -- removing, moving, relinking ------------------------------------------------


def test_removing_an_entry_frees_its_portion():
    sun = _session(SUN, (EGG, 1))
    diary, entry = _add(_with(sun), MON, EGG, link=sun.id)
    diary = _apply(diary, prep.remove_entry(diary, PLAN, WEEK, entry.id))
    assert WEEK not in diary.weeks
    _, again = _add(diary, MON, EGG, link=sun.id)
    assert diary.sessions[sun.id].items[0].batches == 1
    assert again.session == sun.id


def test_plan_batches_follow_the_meals_both_ways():
    sun = _session(SUN, (CHICKEN, 1))  # 4 servings a batch
    diary = _with(sun)
    added = []
    for _ in range(5):
        diary, entry = _add(diary, MON, link=sun.id)
        added.append(entry)
    assert diary.sessions[sun.id].items[0].batches == 2
    diary = _apply(diary, prep.remove_entry(diary, PLAN, WEEK, added[0].id))
    assert diary.sessions[sun.id].items[0].batches == 1
    for entry in added[1:]:
        diary = _apply(diary, prep.remove_entry(diary, PLAN, WEEK, entry.id))
    # No meals left: the item stays listed, at one batch.
    assert diary.sessions[sun.id].items[0].batches == 1


def test_log_batches_stay_as_made_when_meals_go():
    past = _session(TODAY, (EGG, 3))
    diary, first = _add(_with(past), TODAY, EGG, link=past.id, policy=ADMIN)
    diary = _apply(diary, prep.remove_entry(diary, PLAN, LAST_WEEK, first.id))
    assert diary.sessions[past.id].items[0].batches == 3


def test_moving_before_the_session_relinks_in_plan():
    tue = _session(TUE, (CHICKEN, 1))
    diary, entry = _add(_with(tue), WED, link=tue.id)
    change = prep.move_entry(diary, PLAN, RECIPES, WEEK, entry.id, MON, Mealtime.DINNER)
    diary = _apply(diary, change)
    moved = _entry(diary, entry.id)
    assert moved.session is not None and moved.session != tue.id
    assert diary.sessions[moved.session].date == SUN


def test_moving_keeps_the_link_and_refuses_breaking_it_outside_plan():
    sun = _session(D(2026, 10, 27), (CHICKEN, 1))
    diary, entry = _add(_with(sun), D(2026, 10, 27), link=sun.id, policy=ADMIN)
    change = prep.move_entry(
        diary, PLAN, RECIPES, LAST_WEEK, entry.id, D(2026, 10, 28), Mealtime.DINNER
    )
    assert _entry(_apply(diary, change), entry.id, LAST_WEEK).session == sun.id
    with pytest.raises(RuleError, match="later"):
        prep.move_entry(
            diary, PLAN, RECIPES, LAST_WEEK, entry.id, D(2026, 10, 26), Mealtime.DINNER
        )


def test_relinking_plan_fills_log_refuses():
    sun = _session(SUN, (RICE, 1))
    diary, entry = _add(_with(sun), MON, link=None)
    change = prep.set_entry_session(diary, PLAN, RECIPES, WEEK, entry.id, sun.id)
    diary = _apply(diary, change)
    assert _entry(diary, entry.id).session == sun.id
    assert [i.recipe for i in diary.sessions[sun.id].items] == ["rice", "chicken"]
    unlink = prep.set_entry_session(diary, PLAN, RECIPES, WEEK, entry.id, None)
    assert _entry(_apply(diary, unlink), entry.id).session is None

    past, logged = _add(EMPTY, TODAY)
    with pytest.raises(RuleError, match="Admin"):
        prep.set_entry_session(past, PLAN, RECIPES, LAST_WEEK, logged.id, sun.id)


# -- session edits -------------------------------------------------------------


def test_add_item_creates_the_session_and_refuses_duplicates_and_log():
    change, sid = prep.add_item(EMPTY, PLAN, TUE, CHICKEN, batches=2)
    diary = _apply(EMPTY, change)
    item = diary.sessions[sid].items[0]
    # In Plan, batches follow the meals: none yet, so one batch.
    assert (diary.sessions[sid].date, item.batches) == (TUE, 1)
    with pytest.raises(RuleError, match="already has"):
        prep.add_item(diary, PLAN, TUE, CHICKEN)
    with pytest.raises(RuleError, match="already happened"):
        prep.add_item(EMPTY, PLAN, TODAY, CHICKEN)
    change, _ = prep.add_item(EMPTY, ADMIN, TODAY, CHICKEN)
    assert change.sessions


def test_setting_batches_is_admin_only_and_never_below_links():
    past = _session(TODAY, (EGG, 3))
    diary, _ = _add(_with(past), TODAY, EGG, link=past.id, policy=ADMIN)
    diary, _ = _add(diary, TODAY, EGG, link=past.id, policy=ADMIN)
    with pytest.raises(RuleError, match="Admin only"):
        prep.update_item(diary, PLAN, past.id, "egg", batches=2)
    lowered = _apply(diary, prep.update_item(diary, ADMIN, past.id, "egg", 2))
    assert lowered.sessions[past.id].items[0].batches == 2
    with pytest.raises(RuleError, match="full"):
        prep.update_item(lowered, ADMIN, past.id, "egg", batches=1)
    with pytest.raises(ValueError):
        prep.update_item(lowered, ADMIN, past.id, "egg", batches=0)


def test_items_with_links_stay_and_the_last_item_deletes_the_session():
    sun = _session(SUN, (CHICKEN, 1), (RICE, 1))
    diary, _ = _add(_with(sun), MON, link=sun.id)
    with pytest.raises(RuleError, match="linked"):
        prep.remove_item(diary, PLAN, sun.id, "chicken")
    with pytest.raises(RuleError, match="linked"):
        prep.delete_session(diary, PLAN, sun.id)
    diary = _apply(diary, prep.remove_item(diary, PLAN, sun.id, "rice"))
    assert [i.recipe for i in diary.sessions[sun.id].items] == ["chicken"]
    alone = _with(_session(SUN, (RICE, 1)))
    gone = prep.remove_item(alone, PLAN, _only(alone).id, "rice")
    assert gone.sessions == {_only(alone).id: None}
    with pytest.raises(prep.SessionNotFoundError):
        prep.remove_item(alone, PLAN, _only(alone).id, "chicken")


def test_moving_a_session_keeps_links_on_or_after_it():
    sun = _session(SUN, (CHICKEN, 1))
    tue = _session(TUE, (RICE, 1))
    diary, _ = _add(_with(sun, tue), TUE, link=sun.id)
    moved = _apply(diary, prep.move_session(diary, PLAN, sun.id, MON))
    assert moved.sessions[sun.id].date == MON
    with pytest.raises(RuleError, match="later"):
        prep.move_session(diary, PLAN, sun.id, WED)
    with pytest.raises(RuleError, match="already has"):
        prep.move_session(diary, PLAN, sun.id, TUE)
    past = _session(TODAY, (RICE, 1))
    with pytest.raises(RuleError, match="haven't happened"):
        prep.move_session(_with(past), PLAN, past.id, SUN)
    assert prep.move_session(_with(past), ADMIN, past.id, SUN).sessions


def test_usual_session_is_the_latest_one_strictly_before_the_day():
    sun = _session(SUN, (CHICKEN, 1))
    tue = _session(TUE, (RICE, 1))
    sessions = [tue, sun]
    assert prep.usual_session(sessions, MON) == sun.id
    assert prep.usual_session(sessions, TUE) == sun.id  # same day is unusual
    assert prep.usual_session(sessions, WED) == tue.id
    assert prep.usual_session(sessions, SUN) is None
