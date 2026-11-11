"""Step 7.12a (D-103): the weekday helper and the "my plan" specialist's wiring. Offline."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.agents.menu import default_menu
from app.agents.my_plan import MY_PLAN_SPEC, my_plan_registry
from app.agents.plan_tools import DayArgs, NoArgs
from app.calc.weekdays import day_name, resolve_day

WEDNESDAY = date(2026, 11, 11)


@pytest.mark.parametrize("name, expected", [("monday", 1), ("Wednesday", 3), ("  SUNDAY ", 7), ("today", 3), ("tomorrow", 4), ("yesterday", 2)])
def test_a_day_name_becomes_the_plans_day_number(name, expected):
    assert resolve_day(name, WEDNESDAY) == expected


def test_today_and_tomorrow_wrap_around_the_week():
    assert resolve_day("tomorrow", date(2026, 11, 15)) == 1                    # Sunday -> Monday
    assert resolve_day("yesterday", date(2026, 11, 16)) == 7                   # Monday -> Sunday


def test_an_unknown_day_is_refused_and_names_come_back_capitalised():
    with pytest.raises(ValueError):
        resolve_day("someday", WEDNESDAY)
    assert [day_name(n) for n in (1, 7)] == ["Monday", "Sunday"]


def test_the_day_argument_only_accepts_the_allowed_names_and_defaults_to_today():
    assert DayArgs().day == "today" and DayArgs(day="friday").day == "friday"
    for bad in ("someday", "3", "", "monday; drop table"):
        with pytest.raises(ValidationError):
            DayArgs(day=bad)
    with pytest.raises(ValidationError):
        DayArgs(day="monday", user_id="x")                                   # the model can never name a user
    with pytest.raises(ValidationError):
        NoArgs(user_id="x")


def test_the_specialist_is_wired_read_only_with_exactly_its_four_tools():
    registry = my_plan_registry()
    assert registry.names() == MY_PLAN_SPEC.tools == {"get_my_targets", "get_my_meal_plan_day", "get_my_workout_day", "get_today_logged", "get_week_logged", "get_my_weight"}
    assert all(t.scope == "read" for t in registry.all())                      # nothing here can propose or change anything
    MY_PLAN_SPEC.check(registry)                                              # the harness would refuse a bad spec
    assert MY_PLAN_SPEC.tier == "small" and MY_PLAN_SPEC.max_steps <= 5


def test_the_router_menu_lists_the_specialist_with_a_description_that_names_its_scope():
    menu = default_menu()
    assert {"nutrition", "my_plan"} <= set(menu)
    assert "OWN saved data" in menu["my_plan"].when and "food or dish" in menu["nutrition"].when


def test_the_prompt_forbids_inventing_numbers_and_changing_anything():
    prompt = MY_PLAN_SPEC.system_prompt.lower()
    for phrase in ("only from what it returns", "never invent", "never do arithmetic", "cannot change anything", "must not see calorie", "get_week_logged", "is not a day they ate nothing", "get_my_weight", "do not judge whether a change is good or bad"):
        assert phrase in prompt
