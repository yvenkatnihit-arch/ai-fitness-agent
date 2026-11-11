"""Step 8.6 (D-112): reading a weight history, offline. Every number comes from this code."""

from datetime import date

from app.calc.weight_trend import CLOSE_ENOUGH_KG, MIN_DAYS_FOR_WEEKLY_RATE, summarize

D = lambda n: date(2026, 11, n)      # noqa: E731


def test_an_empty_history_has_nothing_to_report_but_keeps_the_goal_weights():
    s = summarize([], 58.0, 54.0)
    assert s.latest_kg is None and s.entries == [] and s.change_since_start_kg is None and s.kg_to_target is None and s.percent_to_target is None
    assert (s.start_weight_kg, s.target_weight_kg) == (58.0, 54.0)


def test_entries_are_sorted_and_the_latest_is_the_newest_date_not_the_last_given():
    s = summarize([(D(9), 57.0), (D(1), 58.0), (D(5), 57.6)], 58.0, 54.0)
    assert [d.day for d, _ in s.entries] == [1, 5, 9] and s.latest_kg == 57.0 and s.latest_on == D(9)


def test_change_since_start_and_distance_to_target_are_signed_and_rounded():
    s = summarize([(D(1), 58.0), (D(9), 56.44)], 58.0, 54.0)
    assert s.change_since_start_kg == -1.6 and s.kg_to_target == -2.4 and s.latest_kg == 56.4          # negative: lost, and still above the target


def test_percent_to_target_is_how_far_from_start_to_target_and_stays_between_0_and_100():
    assert summarize([(D(1), 56.0)], 58.0, 54.0).percent_to_target == 50
    assert summarize([(D(1), 54.0)], 58.0, 54.0).percent_to_target == 100
    assert summarize([(D(1), 52.0)], 58.0, 54.0).percent_to_target == 100               # past the target: capped
    assert summarize([(D(1), 60.0)], 58.0, 54.0).percent_to_target == 0                 # moved the wrong way: floored, never negative
    assert summarize([(D(1), 68.0)], 65.0, 70.0).percent_to_target == 60                # a gain goal works the same way


def test_no_percent_when_there_is_no_target_or_the_target_is_the_start():
    assert summarize([(D(1), 56.0)], 58.0, None).percent_to_target is None
    assert summarize([(D(1), 56.0)], 58.0, 58.0 - CLOSE_ENOUGH_KG / 2).percent_to_target is None
    unknown_start = summarize([(D(1), 56.0)], None, 54.0)
    assert unknown_start.percent_to_target is None and unknown_start.change_since_start_kg is None


def test_a_weekly_rate_needs_at_least_a_week_of_weigh_ins():
    assert MIN_DAYS_FOR_WEEKLY_RATE == 7
    assert summarize([(D(1), 58.0), (D(6), 57.0)], 58.0, 54.0).weekly_change_kg is None          # 5 days: not enough
    assert summarize([(D(1), 58.0), (D(8), 57.0)], 58.0, 54.0).weekly_change_kg == -1.0          # exactly a week
    assert summarize([(D(1), 60.0), (D(11), 57.0)], 60.0, 54.0).weekly_change_kg == -2.1         # 3 kg in 10 days = 2.1 a week


def test_a_single_entry_gives_latest_but_no_rate():
    s = summarize([(D(3), 57.5)], 58.0, 54.0)
    assert s.latest_kg == 57.5 and s.weekly_change_kg is None and s.change_since_start_kg == -0.5
