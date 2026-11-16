"""Tests for the prep-session rules (``services/prep.py``,
``docs/prep-sessions.md``, ``docs/freezer.md``)."""

from __future__ import annotations

import datetime
import uuid

import pytest

from meal_prep.dtos.log import RecipeEntryDTO, TakeoutEntryDTO
from meal_prep.dtos.session import PrepSessionDTO
from meal_prep.enums import Aisle, Mealtime, RecipeCategory, StorageType
from meal_prep.models.ingredient import MacrosInfo, Package
from meal_prep.models.recipe import Recipe, RecipeIngredient
from meal_prep.services import diary as entries
from meal_prep.services import prep
from meal_prep.services.prep import Change, Day, Diary, Mode, Policy, RuleError
from meal_prep.services.sessions import freeze_item, portion_entry, prepare_session

D = datetime.date
TODAY = D(2026, 10, 31)  # Saturday
YESTERDAY = D(2026, 10, 30)
SUN, MON, TUE, WED, THU = (D(2026, 11, day) for day in (1, 2, 3, 4, 5))
LAST_THU = D(2026, 10, 29)
LAST_SUN, LAST_MON, LAST_TUE = D(2026, 10, 25), D(2026, 10, 26), D(2026, 10, 27)
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
                package=Package("Test 1 kg", 1.0, "kg", 1000.0),
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
    return Diary(
        weeks=weeks,
        sessions=sessions,
        unassigned=(
            diary.unassigned if change.unassigned is None else change.unassigned
        ),
        bin=diary.bin if change.bin is None else change.bin,
    )


def _session(date: D, *items: tuple[Recipe, int]) -> PrepSessionDTO:
    return PrepSessionDTO(
        id=uuid.uuid4(),
        date=date,
        items=[freeze_item(recipe, batches=batches) for recipe, batches in items],
    )


def _with(*sessions: PrepSessionDTO) -> Diary:
    return Diary(weeks={}, sessions={s.id: s for s in sessions})


def _week(date: D) -> str:
    return prep.week_id(date)


def _add(
    diary: Diary,
    date: D,
    recipe: Recipe = CHICKEN,
    session: uuid.UUID | None = None,
    policy: Policy = PLAN,
    meal: Mealtime = Mealtime.LUNCH,
) -> tuple[Diary, RecipeEntryDTO]:
    change, entry = prep.add_entry(
        diary, policy, _week(date), date, meal, recipe, session=session
    )
    return _apply(diary, change), entry


def _take(
    diary: Diary,
    date: D,
    recipe: Recipe = CHICKEN,
    policy: Policy = PLAN,
    meal: Mealtime = Mealtime.LUNCH,
) -> Diary:
    return _apply(diary, prep.take_unassigned(diary, policy, recipe.id, date, meal))


def _move(diary: Diary, entry_id: uuid.UUID, to: prep.Place, policy=PLAN) -> Diary:
    return _apply(diary, prep.move_meal(diary, policy, entry_id, to))


def _only(diary: Diary) -> PrepSessionDTO:
    [session] = diary.sessions.values()
    return session


def _on_days(diary: Diary) -> list[tuple[D, RecipeEntryDTO]]:
    return [
        (day.date, e)
        for week in diary.weeks.values()
        for day in week.days
        for e in day.entries()
    ]


def _counts(diary: Diary, session: PrepSessionDTO, recipe: Recipe = CHICKEN):
    """(on days, unassigned, binned) meals of one recipe line."""
    key = (session.id, recipe.id)
    days = sum(1 for _, e in _on_days(diary) if (e.session, e.recipe) == key)
    return (
        days,
        prep.slot_counts(diary.unassigned)[key],
        prep.slot_counts(diary.bin)[key],
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


def test_cycle_day_counts_a_session_days_own_evening():
    assert prep.cycle_day(MON, Mealtime.LUNCH) == SUN
    assert prep.cycle_day(TUE, Mealtime.LUNCH) == SUN  # before Tuesday's prep
    assert prep.cycle_day(TUE, Mealtime.DINNER) == TUE  # after it
    assert prep.cycle_day(TUE, Mealtime.SNACKS) == TUE
    assert prep.cycle_day(TODAY, Mealtime.BREAKFAST) == LAST_THU
    assert prep.next_session_day(SUN) == TUE
    assert prep.next_session_day(LAST_THU) == SUN


def test_a_cycle_locks_the_day_after_the_next_session_day():
    # Today (Sat) is in Thursday's cycle, which locks on Mon 2 Nov.
    assert not PLAN.locked(YESTERDAY, Mealtime.LUNCH)
    assert not PLAN.locked(LAST_THU, Mealtime.DINNER)
    # Tuesday's dinner was in Tuesday's cycle: locked since Friday.
    assert PLAN.locked(LAST_TUE, Mealtime.DINNER)
    assert PLAN.locked(LAST_MON, Mealtime.LUNCH)
    # Generous border: on a session day both cycles are open; the old one
    # locks the next day. Today's meals never lock; Admin edits any.
    on_tue = Policy(today=LAST_TUE)
    assert not on_tue.locked(LAST_MON, Mealtime.LUNCH)
    assert Policy(today=D(2026, 10, 28)).locked(LAST_MON, Mealtime.LUNCH)
    assert not PLAN.locked(TODAY, Mealtime.LUNCH)
    assert not ADMIN.locked(LAST_MON, Mealtime.LUNCH)


# -- freezing the numbers -------------------------------------------------------


def test_items_freeze_numbers_and_one_batch_of_ingredients():
    item = freeze_item(CHICKEN, batches=2)
    assert (item.title, item.servings, item.batches) == ("Chicken", 4, 2)
    assert item.cost == pytest.approx(3.0)
    assert item.calories_kcal == pytest.approx(100.0)
    assert (item.fridge_days, item.freezer_friendly) == (4, False)
    [line] = item.ingredients
    assert (line.ingredient, line.grams, line.cost) == ("chicken-breast", 600.0, 12.0)


def test_a_portion_copies_the_numbers_of_its_batch():
    item = freeze_item(CHICKEN).model_copy(update={"title": "As cooked", "cost": 9.0})
    session_id = uuid.uuid4()
    meal = portion_entry(item, session_id)
    assert (meal.title, meal.cost, meal.recipe) == ("As cooked", 9.0, "chicken")
    assert meal.session == session_id
    assert meal.calories_kcal == item.calories_kcal


# -- cooking a batch ------------------------------------------------------------


def test_a_recipe_on_a_day_cooks_a_batch_and_the_rest_is_unassigned():
    diary, entry = _add(EMPTY, MON)
    session = _only(diary)
    assert session.date == SUN  # Monday lunch is in Sunday's cycle
    [item] = session.items
    assert (item.recipe, item.batches) == ("chicken", 1)
    assert entry.session == session.id
    # Four portions: one on Monday, three with no day yet.
    assert _counts(diary, session) == (1, 3, 0)
    assert {m.title for m in diary.unassigned} == {"Chicken"}


def test_another_drop_always_cooks_another_batch():
    diary, _ = _add(EMPTY, MON)
    diary, _ = _add(diary, TUE)  # same cycle: not one of the unassigned three
    session = _only(diary)
    assert session.items[0].batches == 2
    assert _counts(diary, session) == (2, 6, 0)


def test_a_one_portion_recipe_leaves_nothing_unassigned():
    diary, _ = _add(EMPTY, MON, EGG)
    assert diary.unassigned == ()
    assert _counts(diary, _only(diary), EGG) == (1, 0, 0)


def test_a_session_days_evening_belongs_to_that_days_cycle():
    diary, snack = _add(EMPTY, TUE, meal=Mealtime.SNACKS)
    assert diary.sessions[snack.session].date == TUE  # type: ignore[index]
    diary, lunch = _add(diary, TUE)
    assert diary.sessions[lunch.session].date == SUN  # type: ignore[index]


def test_a_cooked_session_takes_no_new_batch_except_in_admin():
    # Today's lunch is in Thursday's cycle, and Thursday has passed.
    with pytest.raises(RuleError, match="already cooked"):
        _add(EMPTY, TODAY)
    thu = _session(LAST_THU, (RICE, 1))
    with pytest.raises(RuleError, match="already cooked"):
        _add(_with(thu), TODAY)
    # Admin treats it as planned again: the batch is added there.
    diary, entry = _add(_with(thu), TODAY, policy=ADMIN)
    assert entry.session == thu.id
    assert [i.recipe for i in diary.sessions[thu.id].items] == ["rice", "chicken"]
    assert _counts(diary, thu) == (1, 3, 0)
    # A session day's own dinner is cooked that evening: still planned.
    diary, dinner = _add(EMPTY, D(2026, 11, 1), meal=Mealtime.DINNER)
    assert diary.sessions[dinner.session].date == SUN  # type: ignore[index]


def test_a_named_session_cooks_the_batch_unless_it_is_later():
    tue = _session(TUE, (RICE, 1))
    _, entry = _add(_with(tue), WED, session=tue.id)
    assert entry.session == tue.id
    with pytest.raises(RuleError, match="later"):
        _add(_with(tue), MON, session=tue.id)


# -- using what exists ----------------------------------------------------------


def test_taking_an_unassigned_portion_moves_it_and_cooks_nothing():
    diary, _ = _add(EMPTY, MON)
    session = _only(diary)
    unassigned = {m.id for m in diary.unassigned}
    diary = _take(diary, TUE)
    assert _only(diary).items[0].batches == 1
    assert _counts(diary, session) == (2, 2, 0)
    [taken] = [e for date, e in _on_days(diary) if date == TUE]
    assert taken.id in unassigned  # the same meal, not a new one


def test_taking_picks_the_latest_session_that_fits_the_day():
    diary, _ = _add(EMPTY, MON)  # Sunday's batch
    diary, _ = _add(diary, WED)  # Tuesday's batch
    sun, tue = sorted(diary.sessions.values(), key=lambda s: s.date)
    diary = _take(diary, THU)
    assert _counts(diary, tue) == (2, 2, 0)
    assert _counts(diary, sun) == (1, 3, 0)
    # Monday is before Tuesday's cooking: Sunday's portion.
    diary = _take(diary, MON, meal=Mealtime.DINNER)
    assert _counts(diary, sun) == (2, 2, 0)


def test_taking_is_refused_when_nothing_fits():
    with pytest.raises(RuleError, match="no unassigned portion"):
        prep.take_unassigned(EMPTY, PLAN, "chicken", MON, Mealtime.LUNCH)
    diary, _ = _add(EMPTY, WED)  # cooked on Tuesday
    with pytest.raises(RuleError, match="can't be eaten on Mon"):
        prep.take_unassigned(diary, PLAN, "chicken", MON, Mealtime.LUNCH)


# -- moving meals -----------------------------------------------------------------


def test_moving_a_meal_never_changes_its_session():
    diary, entry = _add(EMPTY, WED)  # Tuesday's session
    tue = _only(diary)
    # Into a later cycle: still Tuesday's portion, and Thursday cooks nothing.
    diary = _move(diary, entry.id, Day(THU, Mealtime.DINNER))
    assert [(d, e.session) for d, e in _on_days(diary)] == [(THU, tue.id)]
    assert list(diary.sessions) == [tue.id]
    # Onto the session's own day is fine; before it is refused.
    diary = _move(diary, entry.id, Day(TUE, Mealtime.BREAKFAST))
    with pytest.raises(RuleError, match="cooked on Tue"):
        prep.move_meal(diary, PLAN, entry.id, Day(MON, Mealtime.LUNCH))


def test_a_meal_moves_to_another_week():
    diary, entry = _add(EMPTY, MON)
    diary = _move(diary, entry.id, Day(D(2026, 11, 10), Mealtime.LUNCH))
    assert list(diary.weeks) == ["2026-W46"]
    assert _on_days(diary)[0][1].id == entry.id


def test_removing_a_meal_sends_its_portion_to_unassigned():
    diary, entry = _add(EMPTY, MON)
    session = _only(diary)
    diary = _apply(diary, prep.remove_entry(diary, PLAN, WEEK, entry.id))
    assert diary.weeks == {}
    assert _counts(diary, session) == (0, 4, 0)
    assert _only(diary).items[0].batches == 1  # the batch stays


def test_removing_takeout_or_a_meal_without_a_session_deletes_it():
    takeout = TakeoutEntryDTO(
        id=uuid.uuid4(),
        title="Pizza",
        calories_kcal=800,
        protein_g=30,
        fat_g=30,
        carbs_g=90,
    )
    change = prep.add_takeout_entries(EMPTY, PLAN, WEEK, MON, Mealtime.LUNCH, [takeout])
    diary = _apply(EMPTY, change)
    week, old = entries.add_entry(diary.weeks[WEEK], WEEK, MON, Mealtime.LUNCH, CHICKEN)
    diary = Diary(weeks={WEEK: week}, sessions={})  # as older files have them
    for entry_id in (takeout.id, old.id):
        with pytest.raises(RuleError, match="not a portion"):
            prep.move_meal(diary, PLAN, entry_id, "unassigned")
        diary = _apply(diary, prep.remove_entry(diary, PLAN, WEEK, entry_id))
    assert diary.weeks == {} and diary.unassigned == ()


def test_the_bin_keeps_the_portion_and_its_day():
    diary, entry = _add(EMPTY, MON)
    session = _only(diary)
    diary = _move(diary, entry.id, "bin")
    assert _counts(diary, session) == (0, 3, 1)
    [binned] = diary.bin
    assert (binned.id, binned.binned) == (entry.id, TODAY)
    # An unassigned portion goes there the same way...
    diary = _move(diary, diary.unassigned[0].id, "bin")
    assert _counts(diary, session) == (0, 2, 2)
    # ...and a binned one comes back out, to a day or to unassigned.
    diary = _move(diary, entry.id, Day(TUE, Mealtime.LUNCH))
    assert _counts(diary, session) == (1, 2, 1)
    assert not hasattr(_on_days(diary)[0][1], "binned")
    diary = _move(diary, diary.bin[0].id, "unassigned")
    assert _counts(diary, session) == (1, 3, 0)
    with pytest.raises(entries.EntryNotFoundError):
        prep.move_meal(diary, PLAN, uuid.uuid4(), "bin")


def test_settled_meals_need_admin_for_every_edit():
    diary, entry = _add(EMPTY, LAST_MON, policy=ADMIN)
    with pytest.raises(RuleError, match="settled"):
        _add(diary, LAST_MON)
    with pytest.raises(RuleError, match="settled"):
        prep.take_unassigned(diary, PLAN, "chicken", LAST_MON, Mealtime.LUNCH)
    with pytest.raises(RuleError, match="settled"):
        prep.remove_entry(diary, PLAN, LAST_WEEK, entry.id)
    for to in (Day(TODAY, Mealtime.LUNCH), "unassigned", "bin"):
        with pytest.raises(RuleError, match="settled"):
            prep.move_meal(diary, PLAN, entry.id, to)
    # The slots never settle: a cooked session's unassigned portions move.
    diary = _move(diary, diary.unassigned[0].id, "bin")
    diary = _take(diary, TODAY)
    prep.remove_entry(diary, ADMIN, LAST_WEEK, entry.id)  # Admin: fine


def test_an_item_never_has_more_meals_than_portions():
    diary, _ = _add(EMPTY, MON, EGG)
    session = _only(diary)
    extra = portion_entry(session.items[0], session.id)  # e.g. a hand edit
    broken = Diary(diary.weeks, diary.sessions, unassigned=(extra,))
    with pytest.raises(RuleError, match="full: 1 portion, 2 meals"):
        prep.take_unassigned(broken, PLAN, "egg", TUE, Mealtime.LUNCH)


# -- batches ------------------------------------------------------------------------


def test_removing_a_batch_takes_its_unassigned_portions():
    diary, _ = _add(EMPTY, MON)
    diary, _ = _add(diary, TUE)  # two batches: 2 on days, 6 unassigned
    session = _only(diary)
    diary = _apply(diary, prep.remove_batch(diary, PLAN, session.id, "chicken"))
    assert _only(diary).items[0].batches == 1
    assert _counts(diary, session) == (2, 2, 0)


def test_the_last_batch_needs_every_meal_unassigned_and_takes_the_session():
    diary, entry = _add(EMPTY, MON)
    session = _only(diary)
    with pytest.raises(RuleError, match="move 1 to unassigned first"):
        prep.remove_batch(diary, PLAN, session.id, "chicken")
    # A binned portion blocks it just the same.
    binned = _move(diary, entry.id, "bin")
    with pytest.raises(RuleError, match="move 1 to unassigned first"):
        prep.remove_batch(binned, PLAN, session.id, "chicken")
    diary = _apply(diary, prep.remove_entry(diary, PLAN, WEEK, entry.id))
    diary = _apply(diary, prep.remove_batch(diary, PLAN, session.id, "chicken"))
    assert diary.sessions == {} and diary.unassigned == ()


def test_removing_the_last_batch_of_one_recipe_keeps_the_others():
    session = _session(SUN, (CHICKEN, 1), (RICE, 1))
    session = session.model_copy(update={"have": {"chicken": ["chicken-breast"]}})
    # No meals at all (a session from before portions were meals): fine.
    diary = _apply(
        _with(session), prep.remove_batch(_with(session), PLAN, session.id, "chicken")
    )
    left = _only(diary)
    assert [i.recipe for i in left.items] == ["rice"]
    assert left.have == {}
    with pytest.raises(prep.SessionNotFoundError):
        prep.remove_batch(diary, PLAN, session.id, "chicken")


def test_a_cooked_batch_is_a_fact_except_in_admin():
    thu = _session(LAST_THU, (CHICKEN, 1))
    with pytest.raises(RuleError, match="already cooked"):
        prep.remove_batch(_with(thu), PLAN, thu.id, "chicken")
    diary = _apply(_with(thu), prep.remove_batch(_with(thu), ADMIN, thu.id, "chicken"))
    assert diary.sessions == {}


# -- moving a recipe line ------------------------------------------------------------


def test_a_recipe_line_moves_with_every_meal():
    diary, entry = _add(EMPTY, WED)  # Tuesday's session: 1 on Wed, 3 unassigned
    diary, _ = _add(diary, WED, RICE)
    tue = _only(diary)
    diary = _move(diary, diary.unassigned[0].id, "bin")
    diary = _apply(
        diary,
        prep.set_have(diary, PLAN, tue.id, [("chicken", "chicken-breast")], True),
    )
    # To a day without a session: it is created.
    diary = _apply(diary, prep.move_item(diary, PLAN, tue.id, "chicken", to_date=SUN))
    sun = next(s for s in diary.sessions.values() if s.date == SUN)
    assert [i.recipe for i in sun.items] == ["chicken"]
    assert sun.have == {"chicken": ["chicken-breast"]}
    assert _counts(diary, sun) == (1, 2, 1)
    assert [i.recipe for i in diary.sessions[tue.id].items] == ["rice"]
    assert diary.sessions[tue.id].have == {}
    assert next(e for _, e in _on_days(diary) if e.id == entry.id).session == sun.id


def test_a_recipe_line_cannot_move_past_its_meals_or_out_of_a_cooked_session():
    diary, _ = _add(EMPTY, MON)  # Sunday's session, eaten on Monday
    sun = _only(diary)
    with pytest.raises(RuleError, match="Mon 2 Nov lunch is before Tue 3 Nov"):
        prep.move_item(diary, PLAN, sun.id, "chicken", to_date=TUE)
    thu = _session(LAST_THU, (CHICKEN, 1))
    with pytest.raises(RuleError, match="already cooked"):
        prep.move_item(_with(thu), PLAN, thu.id, "chicken", to_date=SUN)
    with pytest.raises(RuleError, match="already cooked"):
        prep.move_item(_with(thu, sun), PLAN, sun.id, "chicken", to_session=thu.id)
    with pytest.raises(ValueError, match="session or the day"):
        prep.move_item(diary, PLAN, sun.id, "chicken")


def test_moving_onto_a_session_that_cooks_the_recipe_merges_the_lines():
    diary, _ = _add(EMPTY, WED)  # Tuesday
    diary, _ = _add(diary, D(2026, 11, 6))  # Thursday
    tue, thu = sorted(diary.sessions.values(), key=lambda s: s.date)
    diary = _apply(
        diary, prep.move_item(diary, PLAN, thu.id, "chicken", to_session=tue.id)
    )
    merged = _only(diary)
    assert (merged.id, merged.items[0].batches) == (tue.id, 2)
    assert _counts(diary, merged) == (2, 6, 0)
    # Onto itself: nothing to do.
    assert prep.move_item(diary, PLAN, tue.id, "chicken", to_session=tue.id) == Change()


# -- sessions -----------------------------------------------------------------------


def test_moving_a_session_keeps_its_meals_on_or_after_it():
    diary, _ = _add(EMPTY, WED)  # Tuesday's session, eaten on Wednesday
    tue = _only(diary)
    with pytest.raises(RuleError, match="can't come from the later"):
        prep.move_session(diary, PLAN, tue.id, THU)
    moved = _apply(diary, prep.move_session(diary, PLAN, tue.id, MON))
    assert _only(moved).date == MON
    with pytest.raises(RuleError, match="haven't happened"):
        prep.move_session(diary, PLAN, tue.id, YESTERDAY)
    sun = _session(SUN, (RICE, 1))
    crowded = Diary(diary.weeks, {**diary.sessions, sun.id: sun}, diary.unassigned)
    with pytest.raises(RuleError, match="already has a session"):
        prep.move_session(crowded, PLAN, tue.id, SUN)
